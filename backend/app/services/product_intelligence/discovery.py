from __future__ import annotations

import asyncio
import contextlib
import logging
import re
from dataclasses import dataclass
from typing import Awaitable, Callable
from urllib.parse import parse_qs, urlencode, urljoin, urlsplit

from app.services.dom.html_parser import BeautifulSoup
import httpx

from app.services.acquisition.runtime import classify_blocked_page
from app.services.acquisition.browser_runtime import (
    get_browser_runtime,
    real_chrome_browser_available,
)
from app.services.acquisition.dom_runtime import get_page_html
from app.services.config.product_intelligence import (
    AGGREGATOR_DOMAINS,
    BRAND_DOMAIN_MAP,
    DISCOVERY_SOURCE_TYPE_PRIORITY,
    MARKETPLACE_DOMAINS,
    RETAILER_DOMAINS,
    SEARCH_EXCLUDED_DOMAIN_PREFIX,
    SEARCH_PROVIDER_GOOGLE_NATIVE,
    SEARCH_PROVIDER_SERPAPI,
    SEARCH_SITE_PREFIX,
    SERPAPI_ENGINE,
    SERPAPI_ENGINE_PARAM,
    SERPAPI_IMMERSIVE_PRODUCT_ENGINE,
    SERPAPI_KEY_PARAM,
    SERPAPI_MORE_STORES_PARAM,
    SERPAPI_PAGE_TOKEN_PARAM,
    SERPAPI_QUERY_PARAM,
    SERPAPI_RESULT_COUNT_PARAM,
    SERPAPI_SEARCH_URL,
    SERPAPI_SHOPPING_ENGINE,
    SERPAPI_SHOPPING_IMMERSIVE_API_FIELD,
    SERPAPI_SHOPPING_IMMERSIVE_TOKEN_FIELD,
    SERPAPI_SHOPPING_RESULTS_FIELD,
    SOURCE_TYPE_AGGREGATOR,
    SOURCE_TYPE_BRAND_DTC,
    SOURCE_TYPE_MARKETPLACE,
    SOURCE_TYPE_RETAILER,
    SOURCE_TYPE_UNKNOWN,
    GOOGLE_NATIVE_BROWSER_ENGINE,
    GOOGLE_NATIVE_BLOCKED_HTML_PATTERNS,
    GOOGLE_NATIVE_BLOCKED_CLASSIFICATION_OFFSET,
    GOOGLE_NATIVE_BLOCKED_URL_PATTERNS,
    GOOGLE_NATIVE_HOME_URL,
    GOOGLE_NATIVE_IGNORED_DOMAINS,
    GOOGLE_NATIVE_NAVIGATION_TIMEOUT_MS,
    GOOGLE_NATIVE_PROVIDER_PAYLOAD,
    GOOGLE_NATIVE_QUERY_PARAM,
    GOOGLE_NATIVE_REDIRECT_PATH,
    GOOGLE_NATIVE_REDIRECT_TARGET_PARAM,
    GOOGLE_NATIVE_RESULT_COUNT_PARAM,
    GOOGLE_NATIVE_RESULT_LINK_SELECTOR,
    GOOGLE_NATIVE_RESULT_WAIT_MS,
    GOOGLE_NATIVE_SEARCH_INPUT_SELECTOR,
    GOOGLE_NATIVE_SEARCH_URL,
    GOOGLE_NATIVE_SUBMIT_KEY,
    GOOGLE_NATIVE_THUMBNAIL_ANCESTOR_DEPTH,
    GOOGLE_NATIVE_THUMBNAIL_MIN_SRC_LENGTH,
    GOOGLE_NATIVE_TITLE_SELECTOR,
    GOOGLE_NATIVE_TYPING_EXTRA_WAIT_MS,
    product_intelligence_settings,
)
from app.services.shared.field_coerce import clean_text
from app.services.product_intelligence.candidate_urls import (
    candidate_dedupe_key,
    clean_result_url,
    looks_like_product_detail_url,
)
from app.services.product_intelligence.matching import (
    normalize_brand,
    source_domain,
)
from app.services.product_intelligence.query_builder import build_search_queries
from app.services.product_intelligence.search_types import SearchResult
from app.services.product_intelligence.serpapi_parsing import (
    dedupe_search_results as _dedupe_search_results,
    parse_immersive_results as _parse_serpapi_immersive_results,
    parse_organic_results as _parse_serpapi_organic_results,
    parse_shopping_results as _parse_serpapi_shopping_results,
)
from app.services.product_intelligence.candidate_identity import (
    candidate_has_shopping_group as _candidate_has_shopping_group,
    candidate_matches_product as _candidate_matches_product,
    candidate_model_token_match as _candidate_model_token_match,
    candidate_rank_text as _candidate_rank_text,
    candidate_title_overlap as _candidate_title_overlap,
    domain_allowed as _domain_allowed,
    domain_matches as _domain_matches,
    identity_token_match as _identity_token_match,
    same_source_url as _same_source_url,
    source_excluded_domains as _source_excluded_domains,
    source_excluded_urls as _source_excluded_urls,
)

logger = logging.getLogger(__name__)

QueryRunner = Callable[[str, int], Awaitable[list["SearchResult"]]]


@dataclass(slots=True)
class DiscoveredCandidate:
    url: str
    domain: str
    source_type: str
    query_used: str
    search_rank: int
    payload: dict[str, object] | None = None
    query_order: int = 0


async def discover_candidates(
    product: dict[str, object],
    *,
    source_domain_value: str,
    provider: str,
    allowed_domains: list[str],
    excluded_domains: list[str],
    max_candidates: int,
    run_query: QueryRunner | None = None,
) -> list[DiscoveredCandidate]:
    queries = build_search_queries(product, source_domain_value=source_domain_value)
    if not queries:
        return []
    provider_name = (
        str(provider or product_intelligence_settings.default_search_provider)
        .strip()
        .lower()
    )
    pool_limit = max(
        max_candidates,
        max_candidates * product_intelligence_settings.discovery_pool_multiplier,
    )

    # In-memory execution cache for deduplication during the lifecycle of this discovery pass
    query_cache: dict[str, list[SearchResult]] = {}

    def make_cached_runner(target_runner: QueryRunner) -> QueryRunner:
        async def cached_run_query(q: str, lim: int) -> list[SearchResult]:
            normalized_q = " ".join(q.strip().lower().split())
            if normalized_q in query_cache:
                logger.info("Product Intelligence cache hit for query: %r", q)
                return query_cache[normalized_q]
            res = await target_runner(q, lim)
            query_cache[normalized_q] = res
            return res

        return cached_run_query

    if run_query is not None:
        cached_runner = make_cached_runner(run_query)
        return await _collect_candidates(
            queries=queries,
            run_query=cached_runner,
            product=product,
            source_domain_value=source_domain_value,
            allowed_domains=allowed_domains,
            excluded_domains=excluded_domains,
            max_candidates=max_candidates,
            pool_limit=pool_limit,
        )
    async with shared_query_runner(provider_name) as shared_run_query:
        if shared_run_query is None:
            return []
        cached_runner = make_cached_runner(shared_run_query)
        return await _collect_candidates(
            queries=queries,
            run_query=cached_runner,
            product=product,
            source_domain_value=source_domain_value,
            allowed_domains=allowed_domains,
            excluded_domains=excluded_domains,
            max_candidates=max_candidates,
            pool_limit=pool_limit,
        )


async def _collect_candidates(
    *,
    queries: list[str],
    run_query: QueryRunner,
    product: dict[str, object],
    source_domain_value: str,
    allowed_domains: list[str],
    excluded_domains: list[str],
    max_candidates: int,
    pool_limit: int,
) -> list[DiscoveredCandidate]:
    candidates: list[DiscoveredCandidate] = []
    seen: set[str] = set()
    domain_counts: dict[str, int] = {}
    source_domains = _source_excluded_domains(product, source_domain_value)
    source_urls = _source_excluded_urls(product)

    for query_order, query in enumerate(queries):
        results = await run_query(query, pool_limit)
        for rank, result in enumerate(results, start=1):
            normalized_url = clean_result_url(result.url)
            if not normalized_url:
                continue
            # Collapse the same listing offered at multiple sizes/colors (URLs differing only
            # by volatile query params) to one canonical key so a single product at N sizes
            # does not consume N per-product candidate slots.
            dedupe_key = candidate_dedupe_key(normalized_url)
            if dedupe_key in seen:
                continue
            if _same_source_url(normalized_url, source_urls):
                continue
            domain = source_domain(normalized_url)
            if not _domain_allowed(
                domain, allowed_domains, excluded_domains, source_domains
            ):
                continue
            if not _candidate_matches_product(product, normalized_url, result.payload):
                continue
            if (
                domain_counts.get(domain, 0)
                >= product_intelligence_settings.max_urls_per_result_domain
            ):
                continue
            seen.add(dedupe_key)
            domain_counts[domain] = domain_counts.get(domain, 0) + 1
            candidates.append(
                DiscoveredCandidate(
                    url=normalized_url,
                    domain=domain,
                    source_type=classify_source_type(domain, product),
                    query_used=query,
                    search_rank=rank,
                    payload=result.payload,
                    query_order=query_order,
                )
            )
            if len(candidates) >= pool_limit:
                return _rank_discovered_candidates(candidates, product=product)[
                    :max_candidates
                ]
        if (
            product_intelligence_settings.search_delay_ms > 0
            and len(candidates) < pool_limit
            and query_order < len(queries) - 1
        ):
            await asyncio.sleep(product_intelligence_settings.search_delay_ms / 1000)
    return _rank_discovered_candidates(candidates, product=product)[:max_candidates]


@contextlib.asynccontextmanager
async def shared_query_runner(provider: str):
    if provider == SEARCH_PROVIDER_GOOGLE_NATIVE:
        if not real_chrome_browser_available():
            logger.error(
                "Product intelligence google_native discovery requires real Chrome (BROWSER_REAL_CHROME_ENABLED + executable path); refusing to silently downgrade to chromium"
            )
            yield None
            return
        async with _google_native_session() as run:
            yield run
        return

    async def _http_run(query: str, limit: int) -> list[SearchResult]:
        return await _search_results(provider, query, limit=limit)

    yield _http_run


def classify_source_type(domain: str, product: dict[str, object]) -> str:
    normalized_domain = str(domain or "").removeprefix("www.").lower()
    brand_domain = BRAND_DOMAIN_MAP.get(normalize_brand(product.get("brand")))
    if brand_domain and _domain_matches(normalized_domain, brand_domain):
        return SOURCE_TYPE_BRAND_DTC
    if any(_domain_matches(normalized_domain, item) for item in MARKETPLACE_DOMAINS):
        return SOURCE_TYPE_MARKETPLACE
    if any(_domain_matches(normalized_domain, item) for item in AGGREGATOR_DOMAINS):
        return SOURCE_TYPE_AGGREGATOR
    if any(_domain_matches(normalized_domain, item) for item in RETAILER_DOMAINS):
        return SOURCE_TYPE_RETAILER
    return SOURCE_TYPE_UNKNOWN


def _rank_discovered_candidates(
    candidates: list[DiscoveredCandidate],
    *,
    product: dict[str, object] | None = None,
) -> list[DiscoveredCandidate]:
    return sorted(
        candidates,
        key=lambda candidate: (
            -int(_identity_token_match(product or {}, _candidate_rank_text(candidate))),
            -int(_candidate_model_token_match(product or {}, candidate)),
            -int(_candidate_has_shopping_group(candidate)),
            -_candidate_title_overlap(product or {}, candidate),
            int(DISCOVERY_SOURCE_TYPE_PRIORITY.get(candidate.source_type, 99)),
            candidate.query_order,
            candidate.search_rank,
        ),
    )


async def _search_results(
    provider: str, query: str, *, limit: int | None = None
) -> list[SearchResult]:
    logger.info(
        "Product intelligence search dispatch provider=%r query=%r limit=%s",
        provider,
        query,
        limit,
    )
    if provider == SEARCH_PROVIDER_SERPAPI:
        if not product_intelligence_settings.serpapi_key:
            logger.warning(
                "Product intelligence SerpAPI discovery skipped: missing API key"
            )
            return []
        return await _search_serpapi(query, limit=limit)
    logger.warning(
        "Product intelligence discovery received unknown provider: %r", provider
    )
    return []


async def _search_serpapi(
    query: str, *, limit: int | None = None
) -> list[SearchResult]:
    shopping_query = _shopping_query(query)
    brand_scoped_query = _brand_scoped_query(query)

    # 1. Google Shopping is the most precise matching engine. Execute it first.
    shopping_raw = await _search_serpapi_engine(
        shopping_query, engine=SERPAPI_SHOPPING_ENGINE, limit=limit
    )
    shopping_results = _parse_serpapi_shopping_results(shopping_raw)
    immersive_results = await _expand_serpapi_immersive_results(
        shopping_raw, limit=limit
    )

    dtc_results: list[SearchResult] = []
    if brand_scoped_query:
        dtc_raw = await _search_serpapi_engine(
            brand_scoped_query,
            engine=SERPAPI_ENGINE,
            limit=limit,
        )
        dtc_results = _parse_serpapi_organic_results(dtc_raw)

    results = _dedupe_search_results(
        [*dtc_results, *immersive_results, *shopping_results]
    )

    # 2. Only fallback to broad organic web searches when brand-site lookup
    # did not produce a candidate and shopping coverage still looks thin.
    if len(results) < 2 and not dtc_results:
        organic_raw = await _search_serpapi_engine(
            shopping_query, engine=SERPAPI_ENGINE, limit=limit
        )
        organic_results = _parse_serpapi_organic_results(organic_raw)
        results = _dedupe_search_results([*dtc_results, *results, *organic_results])

    return results


def _shopping_query(query: str) -> str:
    natural_tokens = [
        token
        for token in str(query or "").split()
        if not token.lower().startswith(SEARCH_EXCLUDED_DOMAIN_PREFIX)
        and not token.lower().startswith(SEARCH_SITE_PREFIX)
    ]
    return " ".join(natural_tokens).strip() or str(query or "").strip()


def _brand_scoped_query(query: str) -> str:
    tokens = str(query or "").split()
    return (
        str(query or "").strip()
        if any(token.lower().startswith(SEARCH_SITE_PREFIX) for token in tokens)
        else ""
    )


def _query_has_identifier(query: str) -> bool:
    for token in str(query or "").split():
        lowered = token.strip().strip('"').casefold()
        if lowered.startswith(SEARCH_SITE_PREFIX) or lowered.startswith(
            SEARCH_EXCLUDED_DOMAIN_PREFIX
        ):
            continue
        compact = re.sub(r"[^a-z0-9]+", "", lowered)
        if len(compact) >= 5 and any(char.isdigit() for char in compact):
            return True
    return False


async def _empty_search_payload() -> dict[str, object]:
    return {}


async def _search_serpapi_engine(
    query: str,
    *,
    engine: str,
    limit: int | None = None,
) -> dict[str, object]:
    params = {
        SERPAPI_ENGINE_PARAM: engine,
        SERPAPI_QUERY_PARAM: query,
        SERPAPI_KEY_PARAM: product_intelligence_settings.serpapi_key,
    }
    if limit is not None:
        params[SERPAPI_RESULT_COUNT_PARAM] = str(max(1, int(limit)))
    try:
        async with httpx.AsyncClient(
            timeout=product_intelligence_settings.search_timeout_seconds
        ) as client:
            response = await client.get(SERPAPI_SEARCH_URL, params=params)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError, OSError) as exc:
        logger.warning(
            "Product intelligence SerpAPI discovery failed engine=%s: %s", engine, exc
        )
        return {}
    return payload if isinstance(payload, dict) else {}


async def _expand_serpapi_immersive_results(
    payload: dict[str, object],
    *,
    limit: int | None = None,
) -> list[SearchResult]:
    rows = payload.get(SERPAPI_SHOPPING_RESULTS_FIELD)
    if not isinstance(rows, list):
        return []
    max_products = int(
        product_intelligence_settings.serpapi_immersive_products_per_query
    )
    if max_products <= 0:
        return []
    results: list[SearchResult] = []
    for item in rows[:max_products]:
        if not isinstance(item, dict):
            continue
        immersive_payload = await _search_serpapi_immersive_product(item)
        if not immersive_payload:
            continue
        results.extend(
            _parse_serpapi_immersive_results(
                immersive_payload,
                parent=item,
                limit=limit,
            )
        )
    return results


async def _search_serpapi_immersive_product(
    item: dict[str, object],
) -> dict[str, object]:
    params = _serpapi_immersive_params(item)
    if not params:
        return {}
    try:
        async with httpx.AsyncClient(
            timeout=product_intelligence_settings.search_timeout_seconds
        ) as client:
            response = await client.get(SERPAPI_SEARCH_URL, params=params)
            response.raise_for_status()
            payload = response.json()
    except (httpx.HTTPError, ValueError, OSError) as exc:
        logger.warning("Product intelligence SerpAPI immersive lookup failed: %s", exc)
        return {}
    return payload if isinstance(payload, dict) else {}


def _serpapi_immersive_params(item: dict[str, object]) -> dict[str, str]:
    api_url = str(item.get(SERPAPI_SHOPPING_IMMERSIVE_API_FIELD) or "").strip()
    page_token = ""  # nosec B105
    if api_url:
        try:
            parsed = urlsplit(api_url)
        except ValueError:
            parsed = None
        if parsed is not None:
            page_token = parse_qs(parsed.query).get(SERPAPI_PAGE_TOKEN_PARAM, [""])[0]
    if not page_token:
        page_token = str(
            item.get(SERPAPI_SHOPPING_IMMERSIVE_TOKEN_FIELD)
            or item.get(SERPAPI_PAGE_TOKEN_PARAM)
            or ""
        ).strip()
    if not page_token:
        return {}
    return {
        SERPAPI_ENGINE_PARAM: SERPAPI_IMMERSIVE_PRODUCT_ENGINE,
        SERPAPI_PAGE_TOKEN_PARAM: page_token,
        SERPAPI_MORE_STORES_PARAM: "true",
        SERPAPI_KEY_PARAM: product_intelligence_settings.serpapi_key,
    }


@contextlib.asynccontextmanager
async def _google_native_session():
    """Open one real-Chrome page on google.com and reuse it across multiple queries."""
    runtime = await get_browser_runtime(browser_engine=GOOGLE_NATIVE_BROWSER_ENGINE)
    blocked = False

    async with runtime.page(domain=source_domain(GOOGLE_NATIVE_HOME_URL)) as page:

        async def _run(query: str, limit: int) -> list[SearchResult]:
            nonlocal blocked
            normalized_query = str(query or "").strip()
            if blocked or not normalized_query:
                return []
            result_limit = min(
                max(
                    1,
                    int(
                        limit or product_intelligence_settings.google_native_max_results
                    ),
                ),
                int(product_intelligence_settings.google_native_max_results),
            )
            logger.info(
                "Product intelligence search dispatch provider='google_native' query=%r limit=%s",
                normalized_query,
                limit,
            )
            try:
                await page.goto(
                    GOOGLE_NATIVE_HOME_URL,
                    wait_until="domcontentloaded",
                    timeout=int(GOOGLE_NATIVE_NAVIGATION_TIMEOUT_MS),
                )

                locator_factory = getattr(page, "locator", None)
                if not callable(locator_factory):
                    logger.warning(
                        "Product intelligence native Google query aborted: page locator API unavailable"
                    )
                    return []
                locator = locator_factory(GOOGLE_NATIVE_SEARCH_INPUT_SELECTOR)
                fill = getattr(locator, "fill", None)
                press = getattr(locator, "press", None)
                if not callable(fill) or not callable(press):
                    logger.warning(
                        "Product intelligence native Google query aborted: search input does not support fill/press"
                    )
                    return []
                await fill(normalized_query)
                await press(GOOGLE_NATIVE_SUBMIT_KEY)
                await page.wait_for_timeout(
                    int(GOOGLE_NATIVE_RESULT_WAIT_MS)
                    + int(GOOGLE_NATIVE_TYPING_EXTRA_WAIT_MS)
                )

                html = await get_page_html(page)
                current_url = _page_url(page)
            except Exception as exc:
                logger.warning(
                    "Product intelligence native Google query failed: %s", exc
                )
                return []

            if _google_native_blocked(current_url, html):
                blocked = True
                logger.warning(
                    "Product intelligence native Google query blocked by challenge page; stopping searches for this session"
                )
                return []

            return _parse_google_native_results(html, limit=result_limit)

        yield _run


def _google_native_search_url(query: str, limit: int) -> str:
    return (
        f"{GOOGLE_NATIVE_SEARCH_URL}?"
        f"{urlencode({GOOGLE_NATIVE_QUERY_PARAM: query, GOOGLE_NATIVE_RESULT_COUNT_PARAM: str(limit)})}"
    )


def _page_url(page: object) -> str:
    value = getattr(page, "url", "")
    if callable(value):
        try:
            value = value()
        except Exception:
            value = ""
    return str(value or "").strip()


def _google_native_blocked(url: str, html: str) -> bool:
    normalized_url = str(url or "").lower()
    if any(pattern in normalized_url for pattern in GOOGLE_NATIVE_BLOCKED_URL_PATTERNS):
        return True
    normalized_html = str(html or "").lower()
    if any(
        pattern in normalized_html for pattern in GOOGLE_NATIVE_BLOCKED_HTML_PATTERNS
    ):
        return True
    classification = classify_blocked_page(
        str(html or ""), GOOGLE_NATIVE_BLOCKED_CLASSIFICATION_OFFSET
    )
    return bool(classification.blocked)


def _parse_google_native_results(html: str, *, limit: int) -> list[SearchResult]:
    soup = BeautifulSoup(str(html or ""), "html.parser")
    results: list[SearchResult] = []
    seen: set[str] = set()

    for anchor in soup.select(GOOGLE_NATIVE_RESULT_LINK_SELECTOR):
        href = str(anchor.get("href") or "").strip()
        url = _google_native_result_url(href)
        if not url or url in seen:
            continue

        domain = source_domain(url).removeprefix("www.").lower()
        if any(_domain_matches(domain, item) for item in GOOGLE_NATIVE_IGNORED_DOMAINS):
            continue
        title = _google_native_anchor_title(anchor, url=url)
        if not title:
            continue
        thumbnail = _google_native_anchor_thumbnail(anchor)

        seen.add(url)
        results.append(
            SearchResult(
                url=url,
                payload={
                    "provider": GOOGLE_NATIVE_PROVIDER_PAYLOAD,
                    "title": title,
                    "snippet": "",
                    "thumbnail": thumbnail,
                    "position": len(results) + 1,
                    "raw": {"href": href, "thumbnail": thumbnail},
                },
            )
        )
        if len(results) >= max(1, int(limit)):
            break

    return results


def _google_native_anchor_title(anchor, *, url: str) -> str:
    heading = anchor.select_one(GOOGLE_NATIVE_TITLE_SELECTOR)
    if heading is not None:
        return clean_text(heading.get_text(" ", strip=True))
    if not looks_like_product_detail_url(url):
        return ""
    for attr in ("aria-label", "title"):
        value = clean_text(anchor.get(attr))
        if value:
            return value
    return clean_text(anchor.get_text(" ", strip=True))


def _google_native_anchor_thumbnail(anchor) -> str:
    parent = anchor
    for _ in range(int(GOOGLE_NATIVE_THUMBNAIL_ANCESTOR_DEPTH)):
        parent = getattr(parent, "parent", None)
        if parent is None:
            break
        for img in parent.find_all("img"):
            src = str(img.get("src") or img.get("data-src") or "").strip()
            if len(src) >= int(GOOGLE_NATIVE_THUMBNAIL_MIN_SRC_LENGTH):
                return src
    return ""


def _google_native_result_url(href: str) -> str:
    raw = str(href or "").strip()
    if not raw:
        return ""
    parsed = urlsplit(raw)
    if parsed.scheme in {"http", "https"}:
        host = (parsed.hostname or "").lower()
        if (
            host == "google.com" or host.endswith(".google.com")
        ) and parsed.path == GOOGLE_NATIVE_REDIRECT_PATH:
            target = parse_qs(parsed.query).get(
                GOOGLE_NATIVE_REDIRECT_TARGET_PARAM, [""]
            )[0]
            return clean_result_url(target)
        return clean_result_url(raw)
    if raw.startswith(GOOGLE_NATIVE_REDIRECT_PATH):
        target = parse_qs(urlsplit(raw).query).get(
            GOOGLE_NATIVE_REDIRECT_TARGET_PARAM, [""]
        )[0]
        return clean_result_url(target)
    if raw.startswith("/"):
        return clean_result_url(urljoin(GOOGLE_NATIVE_HOME_URL, raw))
    return ""


google_native_blocked = _google_native_blocked
google_native_session = _google_native_session
parse_google_native_results = _parse_google_native_results
parse_serpapi_shopping_results = _parse_serpapi_shopping_results
parse_serpapi_immersive_results = _parse_serpapi_immersive_results

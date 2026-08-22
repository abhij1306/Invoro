from __future__ import annotations

__all__ = (
    "prune_irrelevant_detail_dom_nodes",
    "detail_title_fallback_looks_like_code",
    "listing_url_is_structural",
    "listing_detail_like_path",
    "detail_identity_codes_match",
    "detail_identity_codes_from_record_fields",
    "detail_identity_codes_from_url",
    "detail_query_identity_codes_from_url",
    "detail_identity_tokens",
    "detail_redirect_identity_is_mismatched",
    "detail_slug_title_fallback_from_url",
    "detail_title_from_url",
    "detail_url_candidate_is_low_signal",
    "detail_url_is_collection_like",
    "detail_url_is_utility",
    "detail_url_looks_like_product",
    "detail_url_matches_requested_identity",
    "preferred_detail_identity_url",
    "record_matches_requested_detail_identity",
    "semantic_detail_identity_tokens",
)

import json
import logging
import re
from urllib.parse import parse_qsl, urlparse

from app.services.dom.html_parser import BeautifulSoup

from app.services.config.extraction_rules import (
    DETAIL_NOISE_SECTION_SELECTORS,
    JOB_LISTING_DETAIL_ROOT_MARKERS,
    JOB_LISTING_DETAIL_PATH_MARKERS,
    LISTING_CATEGORY_PATH_SEGMENTS,
    LISTING_CATEGORY_PATH_PREFIXES,
    LISTING_DETAIL_PATH_MARKERS,
    LISTING_LOCALE_PATH_SEGMENT_PATTERN,
    LISTING_NON_LISTING_PATH_TOKENS,
    LISTING_PRODUCT_DETAIL_ID_RE,
    LISTING_STRUCTURAL_QUERY_CATEGORY_TOKENS,
    LISTING_STRUCTURAL_QUERY_FILTER_TOKENS,
    PRODUCT_SLUG_MIN_TERMINAL_TOKENS,
    YEAR_SLUG_PATTERN,
)
from app.services.config.surface_hints import detail_path_hints
from app.services.extract.listing_candidate_ranking import (
    job_listing_url_is_hub as _job_listing_url_is_hub,
    job_listing_url_looks_like_posting as _job_listing_url_looks_like_posting,
)
from app.services.shared.field_coerce import absolute_url
from app.services.extract.detail.identity.jsonld_identity import (
    jsonld_item_candidate_record,
    jsonld_item_product_name,
    jsonld_item_supports_identity,
    jsonld_items,
    prune_duplicate_product_headings,
)

logger = logging.getLogger(__name__)
_LISTING_CATEGORY_PATH_SEGMENTS = frozenset(
    {
        str(value).strip().lower()
        for value in tuple(LISTING_CATEGORY_PATH_SEGMENTS or ())
        if str(value).strip()
    }
)
_LISTING_LOCALE_PATH_SEGMENT_RE = re.compile(
    str(LISTING_LOCALE_PATH_SEGMENT_PATTERN or ""), re.IGNORECASE
)


def _listing_url_has_product_detail_identity(url: str) -> bool:
    return LISTING_PRODUCT_DETAIL_ID_RE.search(str(url or "")) is not None


def _jsonld_item_matches_requested_identity(
    item: dict[str, object],
    *,
    page_url: str,
    requested_page_url: str,
) -> bool:
    raw_url = item.get("url") or item.get("@id")
    if raw_url:
        abs_url = absolute_url(page_url, raw_url)
        if detail_url_matches_requested_identity(
            abs_url,
            requested_page_url=requested_page_url,
        ):
            return True
    return record_matches_requested_detail_identity(
        jsonld_item_candidate_record(item),
        requested_page_url=requested_page_url,
    )


def prune_irrelevant_detail_dom_nodes(
    soup: BeautifulSoup,
    *,
    page_url: str,
    requested_page_url: str,
) -> None:
    pruned_product_names: list[str] = []
    for script in soup.select("script[type='application/ld+json']"):
        try:
            payload = json.loads(script.get_text())
            items = jsonld_items(payload)
            if not items:
                continue

            match_found = False
            script_product_name = ""
            for item in items:
                if not isinstance(item, dict) or not jsonld_item_supports_identity(
                    item
                ):
                    continue
                if not script_product_name:
                    script_product_name = jsonld_item_product_name(item)
                if _jsonld_item_matches_requested_identity(
                    item,
                    page_url=page_url,
                    requested_page_url=requested_page_url,
                ):
                    match_found = True
                    break

            if not match_found:
                if script_product_name:
                    pruned_product_names.append(script_product_name)
                script.decompose()
        except json.JSONDecodeError as exc:
            logger.debug(
                "Skipping malformed detail JSON-LD",
                extra={
                    "page_url": page_url,
                    "requested_page_url": requested_page_url,
                    "error": str(exc),
                    "snippet": script.get_text()[:200],
                },
            )
            continue

    if pruned_product_names:
        prune_duplicate_product_headings(
            soup,
            pruned_product_names=pruned_product_names,
        )

    for selector in tuple(DETAIL_NOISE_SECTION_SELECTORS or ()):
        for node in soup.select(str(selector)):
            node.decompose()


def _listing_url_has_category_path_segment(path: str) -> bool:
    segments = [
        segment.strip().lower()
        for segment in str(path or "").split("/")
        if segment.strip()
    ]
    for segment in segments:
        # Broader split is intentional here, unlike path_segment_tokens:
        # _LISTING_CATEGORY_PATH_SEGMENTS may be embedded behind "_" or mixed punctuation.
        segment_tokens = {token for token in LOWER_NON_ALNUM_RE.split(segment) if token}
        if segment in _LISTING_CATEGORY_PATH_SEGMENTS:
            return True
        if _LISTING_CATEGORY_PATH_SEGMENTS.intersection(segment_tokens):
            return True
    return False


def _listing_query_looks_structural(query: str) -> bool:
    pairs = [
        (
            str(key or "").strip().lower(),
            str(value or "").strip().lower(),
        )
        for key, value in parse_qsl(str(query or ""), keep_blank_values=True)
    ]
    if not pairs:
        return False
    generic_filter_keys = {"f", "filter", "filters", "facet", "facets", "rf"}
    filter_tokens = tuple(
        str(token or "").strip().lower().rstrip("=")
        for token in LISTING_STRUCTURAL_QUERY_FILTER_TOKENS
        if str(token or "").strip()
    )
    return any(
        _listing_filter_pair_is_structural(
            key,
            value,
            generic_filter_keys=generic_filter_keys,
            filter_tokens=filter_tokens,
        )
        for key, value in pairs
    )


def _listing_filter_pair_is_structural(
    key: str,
    value: str,
    *,
    generic_filter_keys: set[str],
    filter_tokens: tuple[str, ...],
) -> bool:
    if key not in generic_filter_keys:
        return False
    haystack = " ".join(filter(None, (key, value)))
    has_category = any(
        token in haystack for token in LISTING_STRUCTURAL_QUERY_CATEGORY_TOKENS
    )
    return has_category and any(token in haystack for token in filter_tokens)


def _strip_listing_locale_segments(segments: list[str]) -> list[str]:
    index = 0
    while index < len(segments) and _LISTING_LOCALE_PATH_SEGMENT_RE.fullmatch(
        segments[index]
    ):
        index += 1
    return segments[index:]


def _listing_url_is_sibling_category(
    *,
    candidate_path: str,
    page_path: str,
) -> bool:
    if _listing_url_has_category_path_segment(
        page_path
    ) and _listing_url_has_category_path_segment(candidate_path):
        return True
    return any(
        page_path.startswith(prefix) and candidate_path.startswith(prefix)
        for prefix in LISTING_CATEGORY_PATH_PREFIXES
    )


def _listing_url_is_locale_sibling_category(
    *,
    candidate_path: str,
    page_path: str,
) -> bool:
    candidate_segments = [seg for seg in candidate_path.strip("/").split("/") if seg]
    page_segments = [seg for seg in page_path.strip("/").split("/") if seg]
    if not candidate_segments or not page_segments:
        return False
    candidate_remainder_segments = _strip_listing_locale_segments(candidate_segments)
    page_remainder_segments = _strip_listing_locale_segments(page_segments)
    if len(candidate_remainder_segments) == len(candidate_segments) and len(
        page_remainder_segments
    ) == len(page_segments):
        return False
    if not candidate_remainder_segments or not page_remainder_segments:
        return False
    return _listing_url_is_sibling_category(
        candidate_path="/" + "/".join(candidate_remainder_segments),
        page_path="/" + "/".join(page_remainder_segments),
    )


def _listing_terminal_looks_like_product_slug(
    *,
    terminal_token_list: list[str],
    terminal_raw: str,
) -> bool:
    year_led_terminal = bool(
        terminal_token_list and re.fullmatch(YEAR_SLUG_PATTERN, terminal_token_list[0])
    )
    return (
        len(terminal_token_list) >= PRODUCT_SLUG_MIN_TERMINAL_TOKENS
        and any(re.search(r"[a-z]", token) for token in terminal_token_list)
        and "-" in terminal_raw
        and not year_led_terminal
    )


def _listing_url_has_non_listing_prefix(
    *,
    leading_tokens: list[set[str]],
    leading_raw: list[str],
    non_listing_tokens: set[str],
) -> bool:
    return any(tokens & non_listing_tokens for tokens in leading_tokens) or any(
        segment in non_listing_tokens for segment in leading_raw
    )


def listing_url_is_structural(url: str, page_url: str) -> bool:
    lowered = url.lower()
    if lowered.startswith(("javascript:", "#", "mailto:")):
        return True
    if lowered == page_url.lower():
        return True
    try:
        parsed = urlparse(url)
        page_parsed = urlparse(page_url)
        if parsed.path in ("", "/"):
            return True
        same_path = (
            parsed.path.rstrip("/").lower() == page_parsed.path.rstrip("/").lower()
        )
        if same_path and _job_detail_query_has_identity(parsed.query):
            return False
        if same_path:
            return True
        if _listing_url_has_product_detail_identity(lowered):
            return False
        # Detail-like URLs (product pages) are exempt from sibling-category
        # rejection even when they share a category path prefix with the page.
        # This covers sites like B&H Photo where product URLs start with /c/product/
        # and the listing page starts with /c/buy/ — both share /c/ but the
        # product URL is clearly a detail page, not a sibling category.
        if listing_detail_like_path(lowered, is_job=False):
            return False
        # Sibling-category rejection.
        # When both the listing page and the candidate share a known
        # category path prefix (e.g. both /c/<slug>), the candidate is
        # a navigation link to another category, not a product.
        candidate_path = parsed.path.lower()
        page_path = page_parsed.path.lower()
        if _listing_url_is_sibling_category(
            candidate_path=candidate_path,
            page_path=page_path,
        ) or _listing_url_is_locale_sibling_category(
            candidate_path=candidate_path,
            page_path=page_path,
        ):
            return True
        return _listing_path_tail_is_structural(parsed.path, parsed.query)
    except ValueError:
        logger.debug("URL structural check failed for %s", page_url, exc_info=True)
    return False


def _listing_path_tail_is_structural(path: str, query: str) -> bool:
    raw_segments = [
        segment.strip().lower() for segment in path.split("/") if segment.strip()
    ]
    tokenized = [path_segment_tokens(segment) for segment in raw_segments]
    terminal_tokens = tokenized[-1] if tokenized else set()
    terminal_raw = raw_segments[-1] if raw_segments else ""
    non_listing = set(LISTING_NON_LISTING_PATH_TOKENS)
    if terminal_tokens & non_listing or terminal_raw in non_listing:
        return True
    terminal_list = [token for token in re.split(r"[-.]+", terminal_raw) if token]
    if _listing_terminal_looks_like_product_slug(
        terminal_token_list=terminal_list, terminal_raw=terminal_raw
    ):
        return False
    leading_tokens = tokenized[:-1] if len(tokenized) <= 2 else []
    leading_raw = raw_segments[:-1] if len(raw_segments) <= 2 else []
    return _listing_query_looks_structural(
        query
    ) or _listing_url_has_non_listing_prefix(
        leading_tokens=leading_tokens,
        leading_raw=leading_raw,
        non_listing_tokens=non_listing,
    )


def listing_detail_like_path(url: str, *, is_job: bool) -> bool:
    lowered = url.lower()
    if is_job:
        return _job_detail_like_path(lowered)
    parsed = urlparse(lowered)
    if _listing_url_has_product_detail_identity(lowered):
        return True
    if _listing_url_has_category_path_segment(parsed.path):
        return False
    segments = [
        segment.strip().lower() for segment in parsed.path.split("/") if segment.strip()
    ]
    if "products" in segments:
        products_index = segments.index("products")
        tail_segments = segments[products_index + 1 :]
        if (
            len(tail_segments) > 2
            and not parsed.query
            and not any(re.search(r"\d", segment) for segment in tail_segments[-2:])
        ):
            return False
    if any(
        _detail_marker_matches(lowered, marker)
        for marker in LISTING_DETAIL_PATH_MARKERS
    ):
        return True
    hints = detail_path_hints("ecommerce_detail")
    return any(_detail_marker_matches(lowered, marker) for marker in hints)


def _detail_marker_matches(url: str, marker: str) -> bool:
    """Check if *marker* matches in *url* at a segment boundary.

    Prevents false positives like ``/product`` matching ``/product-care``
    or ``/product-advice``.  When the marker does NOT end with a path
    separator, the character following the match must be a boundary
    (``/``, ``?``, ``.``, ``#``, ``&``, end-of-string, or a digit) — not
    a hyphen or letter continuation.  Markers ending with ``/`` already
    encode their own boundary and are matched as plain substrings.
    """
    # Markers that end with '/' already have a built-in boundary.
    if marker.endswith("/"):
        return marker in url
    start = 0
    while True:
        idx = url.find(marker, start)
        if idx < 0:
            return False
        end = idx + len(marker)
        if end >= len(url):
            return True
        next_char = url[end]
        # Valid boundary: path separator, query, fragment, or digit (product ID)
        if next_char in "/?.#&" or next_char.isdigit():
            return True
        # Continuation character (hyphen, letter, underscore) → not a boundary
        start = end


def _job_detail_like_path(url: str) -> bool:
    parsed = urlparse(url)
    segments = [segment for segment in parsed.path.split("/") if segment]
    if not segments:
        return False
    terminal = segments[-1].strip().lower()
    if not terminal or _job_listing_url_is_hub(url):
        return False
    query = parsed.query.lower()
    if _job_detail_query_has_identity(query):
        return True
    if any(marker in parsed.path.lower() for marker in JOB_LISTING_DETAIL_PATH_MARKERS):
        return True
    if _job_listing_url_looks_like_posting(url):
        return True
    if re.match(r"jobs?-\d", terminal):
        return True
    for index, segment in enumerate(segments[:-1]):
        normalized = segment.strip().lower()
        if normalized not in JOB_LISTING_DETAIL_ROOT_MARKERS:
            continue
        next_segment = segments[index + 1].strip().lower()
        if next_segment and not _job_listing_url_is_hub(
            f"https://example.com/{next_segment}/"
        ):
            return True
    return False


def _job_detail_query_has_identity(query: str) -> bool:
    lowered = str(query or "").lower()
    return any(
        token in lowered for token in ("showjob=", "jobid=", "job_id=", "gh_jid=")
    )


from .record_identity import (  # noqa: E402
    LOWER_NON_ALNUM_RE,
    path_segment_tokens,
    detail_identity_codes_match,
    detail_identity_codes_from_record_fields,
    detail_identity_codes_from_url,
    detail_query_identity_codes_from_url,
    detail_identity_tokens,
    detail_redirect_identity_is_mismatched,
    detail_slug_title_fallback_from_url,
    detail_title_from_url,
    detail_title_fallback_looks_like_code,
    detail_url_candidate_is_low_signal,
    detail_url_is_collection_like,
    detail_url_is_utility,
    detail_url_looks_like_product,
    detail_url_matches_requested_identity,
    preferred_detail_identity_url,
    record_matches_requested_detail_identity,
    semantic_detail_identity_tokens,
)

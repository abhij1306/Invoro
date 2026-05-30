from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

from bs4 import BeautifulSoup

from app.services.config import aid_score as config
from app.services.fetch.fetch_context import fetch_page
from app.services.pipeline.extract_records import extract_records
from app.services.structured_sources import parse_json_ld, parse_opengraph

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class CatalogCrawlResult:
    domain: str
    pages_crawled: int
    jsonld_blocks: list[dict[str, Any]] = field(default_factory=list)
    og_tags: dict[str, str] = field(default_factory=dict)
    product_records: list[dict[str, Any]] = field(default_factory=list)
    robots_directives: dict[str, list[str]] = field(default_factory=dict)
    sitemap_found: bool = False
    crawl_errors: list[str] = field(default_factory=list)
    sampled_urls: list[str] = field(default_factory=list)
    jsonld_parse_errors: list[str] = field(default_factory=list)


async def crawl_catalog(domain: str, *, sample_size: int = 5) -> CatalogCrawlResult:
    root_url = _root_url(domain)
    result = CatalogCrawlResult(domain=_hostname(root_url), pages_crawled=0)
    bounded_sample_size = max(1, min(int(sample_size or 1), config.AID_AUDIT_MAX_SAMPLE_SIZE))

    listing = await _fetch(root_url, surface="ecommerce_listing", result=result)
    detail_urls: list[str] = []
    if listing is not None:
        result.pages_crawled += 1
        listing_url = _final_url(listing, root_url)
        result.sampled_urls.append(listing_url)
        _collect_page_signals(result, html=str(getattr(listing, "html", "") or ""), url=listing_url)
        detail_urls = _listing_detail_urls(listing, listing_url, bounded_sample_size, result)
    if not detail_urls:
        detail_urls = [root_url]

    seen: set[str] = set()
    for detail_url in detail_urls:
        if detail_url in seen or len(result.product_records) >= bounded_sample_size:
            continue
        seen.add(detail_url)
        detail = await _fetch(detail_url, surface="ecommerce_detail", result=result)
        if detail is None:
            continue
        result.pages_crawled += 1
        final_url = _final_url(detail, detail_url)
        result.sampled_urls.append(final_url)
        html = str(getattr(detail, "html", "") or "")
        _collect_page_signals(result, html=html, url=final_url)
        records = _extract_detail_records(detail, final_url)
        if records:
            for record in records:
                if len(result.product_records) >= bounded_sample_size:
                    break
                result.product_records.append(_product_record(record, html=html, page_url=final_url))
        else:
            result.product_records.append(_product_record({}, html=html, page_url=final_url))

    result.robots_directives = await _fetch_robots(root_url, result=result)
    result.sitemap_found = await _fetch_sitemap(root_url, result=result)
    result.sampled_urls = list(dict.fromkeys(result.sampled_urls))
    return result


def _collect_page_signals(
    result: CatalogCrawlResult,
    *,
    html: str,
    url: str,
) -> None:
    soup = BeautifulSoup(html or "", "html.parser")
    result.jsonld_blocks.extend(parse_json_ld(soup))
    result.jsonld_parse_errors.extend(_jsonld_parse_errors(soup, url))
    for row in parse_opengraph(soup, html or "", url):
        for key, value in row.items():
            if value in (None, "", [], {}):
                continue
            result.og_tags[str(key)] = _string_value(value)
    result.og_tags.update(_raw_og_tags(soup))


def _listing_detail_urls(
    page: object,
    page_url: str,
    sample_size: int,
    result: CatalogCrawlResult,
) -> list[str]:
    try:
        records = extract_records(
            str(getattr(page, "html", "") or ""),
            page_url,
            "ecommerce_listing",
            max_records=sample_size,
            network_payloads=list(getattr(page, "network_payloads", []) or []),
            artifacts=dict(getattr(page, "artifacts", {}) or {}),
            content_type=str(getattr(page, "content_type", "") or ""),
            browser_diagnostics=dict(getattr(page, "browser_diagnostics", {}) or {}),
        )
    except Exception as exc:
        result.crawl_errors.append(f"{page_url}: listing extraction {type(exc).__name__}: {exc}")
        return []
    urls: list[str] = []
    for record in records:
        if not isinstance(record, dict):
            continue
        candidate = str(record.get("url") or record.get("source_url") or "").strip()
        if not candidate:
            continue
        absolute = urljoin(page_url, candidate)
        if _same_host(page_url, absolute):
            urls.append(_clean_url(absolute))
    return list(dict.fromkeys(urls))[:sample_size]


def _extract_detail_records(page: object, page_url: str) -> list[dict[str, Any]]:
    try:
        return [
            record
            for record in extract_records(
                str(getattr(page, "html", "") or ""),
                page_url,
                "ecommerce_detail",
                max_records=1,
                requested_page_url=page_url,
                network_payloads=list(getattr(page, "network_payloads", []) or []),
                artifacts=dict(getattr(page, "artifacts", {}) or {}),
                content_type=str(getattr(page, "content_type", "") or ""),
                browser_diagnostics=dict(getattr(page, "browser_diagnostics", {}) or {}),
            )
            if isinstance(record, dict)
        ]
    except Exception as exc:
        logger.warning("_extract_detail_records failed for %s: %s", page_url, exc, exc_info=True)
        return []


def _product_record(record: dict[str, Any], *, html: str, page_url: str) -> dict[str, Any]:
    soup = BeautifulSoup(html or "", "html.parser")
    shaped = dict(record or {})
    shaped.setdefault("source_url", page_url)
    jsonld_rows = parse_json_ld(soup)
    og_rows = parse_opengraph(soup, html or "", page_url)
    og_tags = _raw_og_tags(soup)
    for row in og_rows:
        og_tags.update({str(key): _string_value(value) for key, value in row.items() if value})
    _backfill_structured_product_fields(shaped, jsonld_rows=jsonld_rows, og_rows=og_rows)
    shaped["_page_text"] = soup.get_text(" ", strip=True)
    shaped["_dom_price"] = _first_text(
        *_selector_texts(
            soup,
            (
                "[itemprop='price']",
                "[data-testid*='price']",
                "[class*='price' i]",
                "[id*='price' i]",
            ),
        ),
    )
    shaped["_jsonld"] = jsonld_rows
    shaped["_og_tags"] = og_tags
    return shaped


def _backfill_structured_product_fields(
    record: dict[str, Any],
    *,
    jsonld_rows: list[dict[str, Any]],
    og_rows: list[dict[str, Any]],
) -> None:
    product = _first_product_jsonld(jsonld_rows)
    og = og_rows[0] if og_rows else {}
    organization = _first_typed_jsonld(jsonld_rows, "organization")
    offers = _first_offer(product)
    brand = product.get("brand") if isinstance(product, dict) else None
    if isinstance(brand, dict):
        brand = brand.get("name")
    _set_missing(record, "title", product.get("name") or og.get("name"))
    _set_missing(record, "description", product.get("description") or og.get("description"))
    _set_missing(record, "image_url", product.get("image") or og.get("image"))
    _set_missing(record, "price", offers.get("price") or product.get("price") or og.get("price"))
    _set_missing(record, "currency", offers.get("priceCurrency") or product.get("priceCurrency"))
    _set_missing(record, "availability", _availability_value(offers.get("availability") or product.get("availability")))
    _set_missing(record, "sku", product.get("sku"))
    _set_missing(record, "gtin", product.get("gtin") or product.get("gtin13") or product.get("gtin14"))
    _set_missing(record, "mpn", product.get("mpn"))
    _set_missing(record, "product_id", product.get("productID") or product.get("productId"))
    _set_missing(record, "brand", brand or organization.get("name"))


def _set_missing(record: dict[str, Any], key: str, value: object) -> None:
    if record.get(key) not in (None, "", [], {}):
        return
    if isinstance(value, list):
        value = _first_text(*value)
    if value in (None, "", [], {}):
        return
    record[key] = value


def _first_product_jsonld(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return _first_typed_jsonld(rows, "product")


def _first_typed_jsonld(rows: list[dict[str, Any]], expected_type: str) -> dict[str, Any]:
    for row in rows:
        raw_type = row.get("@type") or row.get("type")
        values = raw_type if isinstance(raw_type, list) else [raw_type]
        if any(str(value or "").strip().lower().endswith(expected_type) for value in values):
            return row
    return {}


def _first_offer(product: dict[str, Any]) -> dict[str, Any]:
    offers = product.get("offers") if isinstance(product, dict) else None
    if isinstance(offers, dict):
        return offers
    if isinstance(offers, list):
        return next((offer for offer in offers if isinstance(offer, dict)), {})
    return {}


def _availability_value(value: object) -> str:
    text = _string_value(value)
    if "/" in text:
        return text.rsplit("/", 1)[-1]
    return text


async def _fetch(
    url: str,
    *,
    surface: str,
    result: CatalogCrawlResult,
    timeout_seconds: float | None = None,
) -> object | None:
    try:
        return await fetch_page(
            url,
            timeout_seconds=timeout_seconds or config.AID_CRAWL_TIMEOUT_SECONDS,
            surface=surface,
            max_pages=1,
            max_scrolls=1,
            max_records=config.AID_AUDIT_MAX_SAMPLE_SIZE,
        )
    except Exception as exc:
        result.crawl_errors.append(f"{url}: {type(exc).__name__}: {exc}")
        return None


async def _fetch_robots(root_url: str, *, result: CatalogCrawlResult) -> dict[str, list[str]]:
    page = await _fetch(
        urljoin(root_url + "/", "robots.txt"),
        surface="content_detail",
        result=result,
        timeout_seconds=config.AID_ROBOTS_TIMEOUT_SECONDS,
    )
    if page is None:
        return {}
    return parse_robots_txt(str(getattr(page, "html", "") or ""))


async def _fetch_sitemap(root_url: str, *, result: CatalogCrawlResult) -> bool:
    page = await _fetch(
        urljoin(root_url + "/", "sitemap.xml"),
        surface="content_detail",
        result=result,
        timeout_seconds=config.AID_SITEMAP_TIMEOUT_SECONDS,
    )
    if page is None:
        return False
    status_code = int(getattr(page, "status_code", 0) or 0)
    return 200 <= status_code < 300 and bool(str(getattr(page, "html", "") or "").strip())


def parse_robots_txt(text: str) -> dict[str, list[str]]:
    directives: dict[str, list[str]] = {}
    agents: list[str] = []
    for raw_line in str(text or "").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line or ":" not in line:
            continue
        key, value = [part.strip() for part in line.split(":", 1)]
        key = key.lower()
        if key == "user-agent":
            agents = [value.lower()]
            directives.setdefault(value.lower(), [])
            continue
        if key == "disallow" and agents:
            for agent in agents:
                directives.setdefault(agent, []).append(value)
    return directives


def _jsonld_parse_errors(soup: BeautifulSoup, url: str) -> list[str]:
    errors: list[str] = []
    for index, node in enumerate(soup.find_all("script", attrs={"type": "application/ld+json"})):
        raw = node.string or node.get_text()
        if not raw:
            continue
        try:
            json.loads(raw)
        except json.JSONDecodeError as exc:
            errors.append(f"{url} script[{index}]: {exc.msg}")
    return errors


def _selector_texts(soup: BeautifulSoup, selectors: tuple[str, ...]) -> list[str]:
    values: list[str] = []
    for selector in selectors:
        for node in soup.select(selector)[:3]:
            value = node.get("content") or node.get_text(" ", strip=True)
            if value:
                values.append(str(value).strip())
    return values


def _raw_og_tags(soup: BeautifulSoup) -> dict[str, str]:
    tags: dict[str, str] = {}
    for node in soup.find_all("meta"):
        key = str(node.get("property") or node.get("name") or "").strip()
        value = str(node.get("content") or "").strip()
        if key.startswith(("og:", "product:")) and value:
            tags[key] = value
    return tags


def _first_text(*values: object) -> str:
    for value in values:
        text = _string_value(value)
        if text:
            return text
    return ""


def _string_value(value: object) -> str:
    if isinstance(value, list):
        return _first_text(*value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True)
    return str(value or "").strip()


def _root_url(domain: str) -> str:
    parsed = urlparse(str(domain or "").strip())
    if not parsed.scheme:
        parsed = urlparse(f"{config.AID_DEFAULT_URL_SCHEME}://{domain}")
    return urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))


def _hostname(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.lower()


def _final_url(page: object, fallback: str) -> str:
    return _clean_url(str(getattr(page, "final_url", "") or getattr(page, "url", "") or fallback))


def _clean_url(url: str) -> str:
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path or "/", "", parsed.query, ""))


def _same_host(left: str, right: str) -> bool:
    return urlparse(left).netloc.lower() == urlparse(right).netloc.lower()

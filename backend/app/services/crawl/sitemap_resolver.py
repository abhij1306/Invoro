from __future__ import annotations

from xml.etree import ElementTree

import httpx

from app.services.config.sitemap import (
    SITEMAP_DEFAULT_FILTER_KEYWORD,
    SITEMAP_DEFAULT_MAX_URLS,
    SITEMAP_FETCH_TIMEOUT_SECONDS,
    SITEMAP_USER_AGENT,
)
from app.services.url_safety import validate_public_target

SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"


def _normalize_sitemap_url(domain: str) -> str:
    candidate = str(domain or "").strip().rstrip("/")
    if not candidate:
        raise ValueError("empty domain")
    if candidate.startswith(("http://", "https://")):
        if candidate.endswith(".xml"):
            return candidate
        return f"{candidate}/sitemap.xml"
    return f"https://{candidate}/sitemap.xml"


async def resolve_category_urls_from_sitemap(
    domain: str,
    filter_keyword: str = SITEMAP_DEFAULT_FILTER_KEYWORD,
    max_urls: int = SITEMAP_DEFAULT_MAX_URLS,
) -> list[str]:
    root_url = _normalize_sitemap_url(domain)
    keyword = str(filter_keyword or SITEMAP_DEFAULT_FILTER_KEYWORD).strip().lower()
    limit = max(1, int(max_urls or SITEMAP_DEFAULT_MAX_URLS))

    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=SITEMAP_FETCH_TIMEOUT_SECONDS,
    ) as client:
        root_xml = await _fetch_xml(client, root_url)

    root_tag = _local_tag(root_xml.tag)
    if root_tag == "sitemapindex":
        child_urls = [
            loc.text.strip()
            for sitemap in root_xml.findall(f"{{{SITEMAP_NS}}}sitemap")
            if (loc := sitemap.find(f"{{{SITEMAP_NS}}}loc")) is not None
            and loc.text
            and keyword in loc.text.lower()
        ]
        if not child_urls:
            raise ValueError(
                f"No child sitemaps matched filter '{keyword}' in {root_url}. "
                "Available sitemaps did not contain this keyword."
            )
        return await _resolve_child_sitemap_urls(child_urls, limit)

    if root_tag == "urlset":
        urls = [url for url in await _safe_locs(root_xml) if keyword in url.lower()]
        if not urls:
            raise ValueError(f"No URLs matched filter '{keyword}' in {root_url}.")
        return urls[:limit]

    raise ValueError(f"Unrecognised sitemap root tag: {root_tag}")


async def _resolve_child_sitemap_urls(child_urls: list[str], max_urls: int) -> list[str]:
    all_urls: list[str] = []
    async with httpx.AsyncClient(
        follow_redirects=True,
        timeout=SITEMAP_FETCH_TIMEOUT_SECONDS,
    ) as client:
        for child_url in child_urls:
            child_xml = await _fetch_xml(client, child_url)
            all_urls.extend(await _safe_locs(child_xml))
            if len(all_urls) >= max_urls:
                break
    return all_urls[:max_urls]


async def _fetch_xml(client: httpx.AsyncClient, url: str) -> ElementTree.Element:
    await validate_public_target(url)
    response = await client.get(url, headers={"User-Agent": SITEMAP_USER_AGENT})
    if response.status_code != 200:
        raise ValueError(
            f"Sitemap fetch failed: {url} returned HTTP {response.status_code}"
        )
    try:
        return ElementTree.fromstring(response.content)
    except ElementTree.ParseError as exc:
        raise ValueError(f"Invalid XML in sitemap: {url} - {exc}") from exc


async def _safe_locs(xml: ElementTree.Element) -> list[str]:
    urls = _extract_locs(xml)
    for url in urls:
        await validate_public_target(url)
    return urls


def _extract_locs(xml: ElementTree.Element) -> list[str]:
    return [
        loc.text.strip()
        for url_el in xml.findall(f"{{{SITEMAP_NS}}}url")
        if (loc := url_el.find(f"{{{SITEMAP_NS}}}loc")) is not None and loc.text
    ]


def _local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]

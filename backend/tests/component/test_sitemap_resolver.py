from __future__ import annotations

import httpx
import pytest

from app.services.crawl.sitemap_resolver import (
    _normalize_sitemap_url,
    resolve_category_urls_from_sitemap,
)
from app.services.url_safety import SecurityError, ValidatedTarget


SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"


class _FakeClient:
    def __init__(self, responses: dict[str, httpx.Response]) -> None:
        self._responses = responses
        self.requested_urls: list[str] = []

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *args: object) -> None:
        return None

    async def get(self, url: str, headers: dict[str, str]) -> httpx.Response:
        del headers
        self.requested_urls.append(url)
        return self._responses[url]


def _xml_response(url: str, content: str, status_code: int = 200) -> httpx.Response:
    return httpx.Response(
        status_code,
        content=content.encode(),
        request=httpx.Request("GET", url),
    )


async def _valid_target(url: str) -> ValidatedTarget:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return ValidatedTarget(
        hostname=parsed.hostname or "example.com",
        scheme=parsed.scheme or "https",
        port=443,
        resolved_ips=("93.184.216.34",),
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("example.com", "https://example.com/sitemap.xml"),
        ("https://example.com", "https://example.com/sitemap.xml"),
        ("https://example.com/custom.xml", "https://example.com/custom.xml"),
    ],
)
@pytest.mark.component
def test_normalize_sitemap_url(raw: str, expected: str) -> None:
    assert _normalize_sitemap_url(raw) == expected


@pytest.mark.component
def test_normalize_sitemap_url_rejects_empty_domain() -> None:
    with pytest.raises(ValueError, match="empty domain"):
        _normalize_sitemap_url(" ")


@pytest.mark.asyncio
@pytest.mark.component
async def test_resolve_sitemap_index_filters_final_urls_not_child_sitemaps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_url = "https://example.com/sitemap.xml"
    child_url = "https://example.com/sitemap_pages_1.xml"
    fake_client = _FakeClient(
        {
            root_url: _xml_response(
                root_url,
                f"""<sitemapindex xmlns="{SITEMAP_NS}">
                  <sitemap><loc>https://example.com/sitemap_products_1.xml</loc></sitemap>
                  <sitemap><loc>{child_url}</loc></sitemap>
                  <sitemap><loc>https://example.com/sitemap_pages_2.xml</loc></sitemap>
                </sitemapindex>""",
            ),
            "https://example.com/sitemap_products_1.xml": _xml_response(
                "https://example.com/sitemap_products_1.xml",
                f"""<urlset xmlns="{SITEMAP_NS}">
                  <url><loc>https://example.com/products/p</loc></url>
                </urlset>""",
            ),
            child_url: _xml_response(
                child_url,
                f"""<urlset xmlns="{SITEMAP_NS}">
                  <url><loc>https://example.com/collections/a</loc></url>
                  <url><loc>https://example.com/collections/b</loc></url>
                </urlset>""",
            ),
            "https://example.com/sitemap_pages_2.xml": _xml_response(
                "https://example.com/sitemap_pages_2.xml",
                f"""<urlset xmlns="{SITEMAP_NS}">
                  <url><loc>https://example.com/collections/c</loc></url>
                </urlset>""",
            ),
        }
    )
    monkeypatch.setattr(
        "app.services.crawl.sitemap_resolver.httpx.AsyncClient",
        lambda **kwargs: fake_client,
    )
    monkeypatch.setattr(
        "app.services.crawl.sitemap_resolver.validate_public_target",
        _valid_target,
    )

    urls = await resolve_category_urls_from_sitemap("example.com", "collections", 2)

    assert urls == [
        "https://example.com/collections/a",
        "https://example.com/collections/b",
    ]
    assert fake_client.requested_urls == [
        root_url,
        "https://example.com/sitemap_products_1.xml",
        child_url,
        "https://example.com/sitemap_pages_2.xml",
    ]


@pytest.mark.asyncio
@pytest.mark.component
async def test_resolve_direct_urlset_filters_urls_and_clamps(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_url = "https://example.com/sitemap.xml"
    fake_client = _FakeClient(
        {
            root_url: _xml_response(
                root_url,
                f"""<urlset xmlns="{SITEMAP_NS}">
                  <url><loc>https://example.com/collections/a</loc></url>
                  <url><loc>https://example.com/products/p</loc></url>
                  <url><loc>https://example.com/collections/b</loc></url>
                </urlset>""",
            ),
        }
    )
    monkeypatch.setattr(
        "app.services.crawl.sitemap_resolver.httpx.AsyncClient",
        lambda **kwargs: fake_client,
    )
    monkeypatch.setattr(
        "app.services.crawl.sitemap_resolver.validate_public_target",
        _valid_target,
    )

    urls = await resolve_category_urls_from_sitemap("example.com", "collections", 1)

    assert urls == ["https://example.com/collections/a"]


@pytest.mark.asyncio
@pytest.mark.component
async def test_resolver_raises_when_no_final_urls_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_url = "https://example.com/sitemap.xml"
    child_url = "https://example.com/sitemap_products_1.xml"
    fake_client = _FakeClient(
        {
            root_url: _xml_response(
                root_url,
                f"""<sitemapindex xmlns="{SITEMAP_NS}">
                  <sitemap><loc>{child_url}</loc></sitemap>
                </sitemapindex>""",
            ),
            child_url: _xml_response(
                child_url,
                f"""<urlset xmlns="{SITEMAP_NS}">
                  <url><loc>https://example.com/products/p</loc></url>
                </urlset>""",
            ),
        }
    )
    monkeypatch.setattr(
        "app.services.crawl.sitemap_resolver.httpx.AsyncClient",
        lambda **kwargs: fake_client,
    )
    monkeypatch.setattr(
        "app.services.crawl.sitemap_resolver.validate_public_target",
        _valid_target,
    )

    with pytest.raises(ValueError, match="No URLs matched filter"):
        await resolve_category_urls_from_sitemap("example.com", "collections", 500)


@pytest.mark.asyncio
@pytest.mark.component
async def test_resolver_default_does_not_filter_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_url = "https://example.com/sitemap.xml"
    fake_client = _FakeClient(
        {
            root_url: _xml_response(
                root_url,
                f"""<urlset xmlns="{SITEMAP_NS}">
                  <url><loc>https://example.com/pages/a</loc></url>
                  <url><loc>https://example.com/products/p</loc></url>
                </urlset>""",
            ),
        }
    )
    monkeypatch.setattr(
        "app.services.crawl.sitemap_resolver.httpx.AsyncClient",
        lambda **kwargs: fake_client,
    )
    monkeypatch.setattr(
        "app.services.crawl.sitemap_resolver.validate_public_target",
        _valid_target,
    )

    urls = await resolve_category_urls_from_sitemap("example.com")

    assert urls == [
        "https://example.com/pages/a",
        "https://example.com/products/p",
    ]


@pytest.mark.asyncio
@pytest.mark.component
async def test_resolver_empty_urlset_without_filter_reports_no_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_url = "https://example.com/sitemap.xml"
    fake_client = _FakeClient(
        {
            root_url: _xml_response(
                root_url,
                f"""<urlset xmlns="{SITEMAP_NS}"></urlset>""",
            ),
        }
    )
    monkeypatch.setattr(
        "app.services.crawl.sitemap_resolver.httpx.AsyncClient",
        lambda **kwargs: fake_client,
    )
    monkeypatch.setattr(
        "app.services.crawl.sitemap_resolver.validate_public_target",
        _valid_target,
    )

    with pytest.raises(ValueError, match="No URLs found in sitemap"):
        await resolve_category_urls_from_sitemap("example.com", "", 500)


@pytest.mark.asyncio
@pytest.mark.component
async def test_resolver_raises_for_invalid_xml(monkeypatch: pytest.MonkeyPatch) -> None:
    root_url = "https://example.com/sitemap.xml"
    fake_client = _FakeClient({root_url: _xml_response(root_url, "<not-closed")})
    monkeypatch.setattr(
        "app.services.crawl.sitemap_resolver.httpx.AsyncClient",
        lambda **kwargs: fake_client,
    )
    monkeypatch.setattr(
        "app.services.crawl.sitemap_resolver.validate_public_target",
        _valid_target,
    )

    with pytest.raises(ValueError, match="Invalid XML in sitemap"):
        await resolve_category_urls_from_sitemap("example.com", "collections", 500)


@pytest.mark.asyncio
@pytest.mark.component
async def test_resolver_raises_for_non_200(monkeypatch: pytest.MonkeyPatch) -> None:
    root_url = "https://example.com/sitemap.xml"
    fake_client = _FakeClient({root_url: _xml_response(root_url, "missing", 404)})
    monkeypatch.setattr(
        "app.services.crawl.sitemap_resolver.httpx.AsyncClient",
        lambda **kwargs: fake_client,
    )
    monkeypatch.setattr(
        "app.services.crawl.sitemap_resolver.validate_public_target",
        _valid_target,
    )

    with pytest.raises(ValueError, match="returned HTTP 404"):
        await resolve_category_urls_from_sitemap("example.com", "collections", 500)


@pytest.mark.asyncio
@pytest.mark.component
async def test_resolver_rejects_unsafe_discovered_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_url = "https://example.com/sitemap.xml"
    fake_client = _FakeClient(
        {
            root_url: _xml_response(
                root_url,
                f"""<urlset xmlns="{SITEMAP_NS}">
                  <url><loc>http://127.0.0.1/collections/a</loc></url>
                </urlset>""",
            ),
        }
    )

    async def _reject_loopback(url: str) -> ValidatedTarget:
        if "127.0.0.1" in url:
            raise SecurityError("Target host resolves to a non-public IP address")
        return await _valid_target(url)

    monkeypatch.setattr(
        "app.services.crawl.sitemap_resolver.httpx.AsyncClient",
        lambda **kwargs: fake_client,
    )
    monkeypatch.setattr(
        "app.services.crawl.sitemap_resolver.validate_public_target",
        _reject_loopback,
    )

    with pytest.raises(SecurityError):
        await resolve_category_urls_from_sitemap("example.com", "collections", 500)

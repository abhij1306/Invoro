from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.ucp_audit import catalog_crawl


def _page(url: str, html: str, *, status_code: int = 200):
    return SimpleNamespace(
        url=url,
        final_url=url,
        html=html,
        status_code=status_code,
        content_type="text/html",
        network_payloads=[],
        artifacts={},
        browser_diagnostics={},
    )


@pytest.mark.asyncio
@pytest.mark.component
async def test_crawl_catalog_samples_listing_details_and_side_files(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_fetch_page(url: str, **kwargs):
        del kwargs
        if url == "https://example.com":
            return _page(url, "<html><body>listing</body></html>")
        if url.endswith("/p/1"):
            return _page(
                url,
                """
                <html><head>
                  <meta property="og:type" content="product" />
                  <script type="application/ld+json">
                    {"@context":"https://schema.org","@type":"Product","name":"One",
                     "offers":{"@type":"Offer","price":"10","availability":"InStock"}}
                  </script>
                </head><body><h1>One</h1><span class="price">$10</span></body></html>
                """,
            )
        if url.endswith("/p/2"):
            return _page(
                url,
                """
                <html><head>
                  <script type="application/ld+json">
                    {"@context":"https://schema.org","@type":"Product","name":"Two",
                     "offers":{"@type":"Offer","price":"20","availability":"InStock"}}
                  </script>
                </head><body><h1>Two</h1><span class="price">$20</span></body></html>
                """,
            )
        if url.endswith("/robots.txt"):
            return _page(url, "User-agent: GPTBot\nDisallow: /")
        if url.endswith("/sitemap.xml"):
            return _page(url, "<urlset />")
        raise AssertionError(f"unexpected fetch {url}")

    def fake_extract_records(html: str, page_url: str, surface: str, **kwargs):
        del html, kwargs
        if surface == "ecommerce_listing":
            return [{"url": "/p/1"}, {"url": "https://example.com/p/2"}]
        if page_url.endswith("/p/1"):
            return [{"title": "One", "price": "10", "description": "x" * 120}]
        if page_url.endswith("/p/2"):
            return [{"title": "Two", "price": "20", "description": "x" * 120}]
        return []

    monkeypatch.setattr(catalog_crawl, "fetch_page", fake_fetch_page)
    monkeypatch.setattr(catalog_crawl, "extract_records", fake_extract_records)

    result = await catalog_crawl.crawl_catalog("example.com", sample_size=2)

    assert result.domain == "example.com"
    assert result.pages_crawled == 3
    assert len(result.product_records) == 2
    assert len(result.jsonld_blocks) == 2
    assert "product" in set(result.og_tags.values())
    assert result.robots_directives["gptbot"] == ["/"]
    assert result.sitemap_found is True
    assert result.crawl_errors == []


@pytest.mark.asyncio
@pytest.mark.component
async def test_crawl_catalog_records_errors_without_failing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_fetch_page(url: str, **kwargs):
        del kwargs
        if url == "https://example.com":
            return _page(url, "<html>listing</html>")
        if url.endswith("/p/1"):
            raise TimeoutError("slow")
        if url.endswith("/robots.txt"):
            return _page(url, "")
        if url.endswith("/sitemap.xml"):
            return _page(url, "", status_code=404)
        raise AssertionError(f"unexpected fetch {url}")

    def fake_extract_records(html: str, page_url: str, surface: str, **kwargs):
        del html, page_url, kwargs
        return [{"url": "/p/1"}] if surface == "ecommerce_listing" else []

    monkeypatch.setattr(catalog_crawl, "fetch_page", fake_fetch_page)
    monkeypatch.setattr(catalog_crawl, "extract_records", fake_extract_records)

    result = await catalog_crawl.crawl_catalog("example.com", sample_size=1)

    assert result.product_records == []
    assert any("TimeoutError" in error for error in result.crawl_errors)
    assert result.sitemap_found is False


@pytest.mark.asyncio
@pytest.mark.component
async def test_crawl_catalog_backfills_empty_detail_record_from_jsonld(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_fetch_page(url: str, **kwargs):
        del kwargs
        if url == "https://example.com":
            return _page(url, "<html>listing</html>")
        if url.endswith("/p/1"):
            return _page(
                url,
                """
                <html><head>
                  <meta property="og:type" content="product" />
                  <script type="application/ld+json">
                    {"@context":"https://schema.org","@type":"Product",
                     "name":"JSON Product","description":"Long useful description for a product page that agents can read.",
                     "image":"https://example.com/p.jpg",
                     "offers":{"@type":"Offer","price":"42","priceCurrency":"INR","availability":"https://schema.org/InStock"}}
                  </script>
                  <script type="application/ld+json">
                    {"@context":"https://schema.org","@type":"Organization","name":"Example Brand"}
                  </script>
                </head><body><span class="price">Earn Cashback</span></body></html>
                """,
            )
        if url.endswith("/robots.txt"):
            return _page(url, "")
        if url.endswith("/sitemap.xml"):
            return _page(url, "<urlset />")
        raise AssertionError(f"unexpected fetch {url}")

    def fake_extract_records(html: str, page_url: str, surface: str, **kwargs):
        del html, page_url, kwargs
        return [{"url": "/p/1"}] if surface == "ecommerce_listing" else []

    monkeypatch.setattr(catalog_crawl, "fetch_page", fake_fetch_page)
    monkeypatch.setattr(catalog_crawl, "extract_records", fake_extract_records)

    result = await catalog_crawl.crawl_catalog("example.com", sample_size=1)

    assert result.product_records[0]["title"] == "JSON Product"
    assert result.product_records[0]["price"] == "42"
    assert result.product_records[0]["currency"] == "INR"
    assert result.product_records[0]["availability"] == "InStock"
    assert result.product_records[0]["image_url"] == "https://example.com/p.jpg"
    assert result.product_records[0]["brand"] == "Example Brand"


@pytest.mark.asyncio
@pytest.mark.component
async def test_crawl_catalog_uses_category_pages_to_find_real_product_urls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fetched: list[tuple[str, str]] = []

    async def fake_fetch_page(url: str, **kwargs):
        surface = str(kwargs.get("surface") or "")
        fetched.append((url, surface))
        if url == "https://example.com":
            return _page(url, "<html><body>homepage tiles</body></html>")
        if url == "https://example.com/minecraft":
            return _page(url, "<html><body>category products</body></html>")
        if url == "https://example.com/products/creeper-pyjamas-123":
            return _page(
                url,
                """
                <html><head>
                  <script type="application/ld+json">
                    {"@context":"https://schema.org","@type":"Product","name":"Creeper Pyjamas",
                     "offers":{"@type":"Offer","price":"28","priceCurrency":"AUD","availability":"InStock"}}
                  </script>
                </head><body><h1>Creeper Pyjamas</h1><span class="price">$28</span></body></html>
                """,
            )
        if url.endswith("/robots.txt"):
            return _page(url, "")
        if url.endswith("/sitemap.xml"):
            return _page(url, "<urlset />")
        raise AssertionError(f"unexpected fetch {url}")

    def fake_extract_records(html: str, page_url: str, surface: str, **kwargs):
        del html, kwargs
        if surface == "ecommerce_listing" and page_url == "https://example.com/":
            return [
                {"url": "/minecraft"},
                {"url": "/state-of-origin-supporter-gear%3Fintpromo%3Dhomepage_tile"},
            ]
        if (
            surface == "ecommerce_listing"
            and page_url == "https://example.com/minecraft"
        ):
            return [{"url": "/products/creeper-pyjamas-123"}]
        if surface == "ecommerce_detail":
            return [{"title": "Creeper Pyjamas", "price": "28"}]
        return []

    monkeypatch.setattr(catalog_crawl, "fetch_page", fake_fetch_page)
    monkeypatch.setattr(catalog_crawl, "extract_records", fake_extract_records)

    result = await catalog_crawl.crawl_catalog("example.com", sample_size=1)

    assert [row["source_url"] for row in result.product_records] == [
        "https://example.com/products/creeper-pyjamas-123"
    ]
    assert result.sampled_urls == [
        "https://example.com/",
        "https://example.com/products/creeper-pyjamas-123",
    ]
    assert not any(
        "state-of-origin-supporter-gear" in url for url in result.sampled_urls
    )
    assert ("https://example.com/minecraft", "ecommerce_listing") in fetched
    assert (
        "https://example.com/products/creeper-pyjamas-123",
        "ecommerce_detail",
    ) in fetched


@pytest.mark.asyncio
@pytest.mark.component
async def test_crawl_catalog_does_not_create_product_sample_for_category_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_fetch_page(url: str, **kwargs):
        del kwargs
        if url == "https://example.com":
            return _page(url, "<html><body>homepage tiles</body></html>")
        if url == "https://example.com/minecraft":
            return _page(
                url, "<html><body>category without extracted products</body></html>"
            )
        if url.endswith("/robots.txt"):
            return _page(url, "")
        if url.endswith("/sitemap.xml"):
            return _page(url, "<urlset />")
        raise AssertionError(f"unexpected fetch {url}")

    def fake_extract_records(html: str, page_url: str, surface: str, **kwargs):
        del html, kwargs
        if surface == "ecommerce_listing" and page_url == "https://example.com/":
            return [{"url": "/minecraft"}]
        return []

    monkeypatch.setattr(catalog_crawl, "fetch_page", fake_fetch_page)
    monkeypatch.setattr(catalog_crawl, "extract_records", fake_extract_records)

    result = await catalog_crawl.crawl_catalog("example.com", sample_size=1)

    assert result.product_records == []
    assert result.sampled_urls == ["https://example.com/"]


@pytest.mark.component
def test_clean_url_decodes_encoded_query_and_removes_tracking_parameters() -> None:
    assert (
        catalog_crawl._clean_url(
            "https://example.com/products/item%3Fintpromo%3Dhome%26sku%3D123"
        )
        == "https://example.com/products/item?sku=123"
    )


@pytest.mark.component
def test_parse_robots_txt_groups_ai_agent_disallows() -> None:
    directives = catalog_crawl.parse_robots_txt(
        """
        User-agent: GPTBot
        Disallow: /

        User-agent: PerplexityBot
        Disallow: /private
        """
    )

    assert directives == {"gptbot": ["/"], "perplexitybot": ["/private"]}

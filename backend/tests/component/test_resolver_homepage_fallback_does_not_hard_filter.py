from __future__ import annotations

from .test_sitemap_resolver import SITEMAP_NS, SecurityError, ValidatedTarget, _FakeClient, _valid_target, _xml_response, httpx, pytest, resolve_category_urls_from_sitemap, sitemap_resolver  # fmt: skip

@pytest.mark.asyncio
@pytest.mark.component
async def test_resolver_homepage_fallback_does_not_hard_filter_by_keyword(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sitemap_url = "https://example.com/sitemap.xml"
    homepage_url = "https://example.com"
    fake_client = _FakeClient(
        {
            sitemap_url: _xml_response(sitemap_url, "missing", 404),
            homepage_url: httpx.Response(
                200,
                text="""
                <html><body>
                  <nav>
                    <a href="/women">Women</a>
                    <a href="/shop/sale">Sale</a>
                  </nav>
                  <a href="/products/widget-123">Widget</a>
                </body></html>
                """,
                request=httpx.Request("GET", homepage_url),
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

    urls = await resolve_category_urls_from_sitemap(
        "example.com",
        "collections",
        5,
        allow_homepage_fallback=True,
    )

    assert urls == [
        "https://example.com/shop/sale",
        "https://example.com/women",
        "https://example.com/products/widget-123",
    ]

@pytest.mark.asyncio
@pytest.mark.component
async def test_homepage_fallback_caps_anchor_scan_and_validations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    validated: list[str] = []

    async def _record_target(url: str) -> ValidatedTarget:
        validated.append(url)
        return await _valid_target(url)

    monkeypatch.setattr(sitemap_resolver, "SITEMAP_HOMEPAGE_FALLBACK_MAX_ANCHORS", 3)
    monkeypatch.setattr(
        sitemap_resolver,
        "SITEMAP_HOMEPAGE_FALLBACK_MAX_VALIDATIONS",
        2,
    )
    monkeypatch.setattr(sitemap_resolver, "validate_public_target", _record_target)

    urls = await sitemap_resolver._extract_homepage_candidate_urls(
        homepage_url="https://example.com",
        html="""
        <nav>
          <a href="/women">Women</a>
          <a href="/men">Men</a>
          <a href="/kids">Kids</a>
          <a href="/sale">Sale</a>
        </nav>
        """,
        keyword="",
        limit=10,
    )

    assert urls == ["https://example.com/women", "https://example.com/men"]
    assert validated == ["https://example.com/women", "https://example.com/men"]

@pytest.mark.asyncio
@pytest.mark.component
async def test_homepage_fallback_requires_exact_same_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.crawl.sitemap_resolver.validate_public_target",
        _valid_target,
    )

    urls = await sitemap_resolver._extract_homepage_candidate_urls(
        homepage_url="https://example.com",
        html="""
        <nav>
          <a href="http://example.com/women">Wrong Scheme</a>
          <a href="https://shop.example.com/men">Subdomain</a>
          <a href="/collections/all">All</a>
        </nav>
        """,
        keyword="",
        limit=10,
    )

    assert urls == ["https://example.com/collections/all"]

@pytest.mark.asyncio
@pytest.mark.component
async def test_resolver_rejects_private_redirect_chain_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_url = "https://example.com/sitemap.xml"
    private_url = "http://169.254.169.254/latest/meta-data"
    fake_client = _FakeClient(
        {
            root_url: httpx.Response(
                200,
                content=f"""<urlset xmlns="{SITEMAP_NS}">
                  <url><loc>https://example.com/collections/a</loc></url>
                </urlset>""".encode(),
                request=httpx.Request("GET", root_url),
                history=[
                    httpx.Response(
                        302,
                        request=httpx.Request("GET", private_url),
                    )
                ],
            )
        }
    )

    async def _reject_private(url: str) -> ValidatedTarget:
        if "169.254.169.254" in url:
            raise SecurityError("Target host resolves to a non-public IP address")
        return await _valid_target(url)

    monkeypatch.setattr(
        "app.services.crawl.sitemap_resolver.httpx.AsyncClient",
        lambda **kwargs: fake_client,
    )
    monkeypatch.setattr(
        "app.services.crawl.sitemap_resolver.validate_public_target",
        _reject_private,
    )

    with pytest.raises(SecurityError):
        await resolve_category_urls_from_sitemap("example.com", "collections", 500)

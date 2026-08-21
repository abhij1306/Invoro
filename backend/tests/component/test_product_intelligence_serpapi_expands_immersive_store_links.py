from __future__ import annotations

from .test_product_intelligence import *  # noqa: F403


@pytest.mark.asyncio
@pytest.mark.component
async def test_product_intelligence_serpapi_expands_immersive_store_links(
    monkeypatch,
) -> None:
    engines: list[str] = []

    async def fake_engine(
        query: str, *, engine: str, limit: int | None = None
    ) -> dict[str, object]:
        del query, limit
        engines.append(engine)
        if engine == "google_shopping":
            return {
                "shopping_results": [
                    {
                        "position": 1,
                        "title": "Columbia Men's Tamiami II Short Sleeve Shirt",
                        "source": "Columbia Sportswear",
                        "product_id": "shopping-product-id",
                        "product_link": "https://www.google.com/search?ibp=oshop&q=columbia",
                        "serpapi_immersive_product_api": "https://serpapi.com/search.json?engine=google_immersive_product&page_token=abc",
                    }
                ]
            }
        return {"organic_results": []}

    async def fake_immersive(item: dict[str, object]) -> dict[str, object]:
        assert item["product_id"] == "shopping-product-id"
        return {
            "product_results": {
                "title": "Columbia Men's Tamiami II Short Sleeve Shirt",
                "product_id": "immersive-product-id",
                "stores": [
                    {
                        "name": "Columbia Sportswear",
                        "title": "Men's PFG Tamiami II Short Sleeve Shirt",
                        "link": "https://www.columbia.com/p/mens-pfg-tamiami-ii-short-sleeve-shirt-big-FM7253.html",
                    }
                ],
            }
        }

    monkeypatch.setattr(discovery_module, "_search_serpapi_engine", fake_engine)
    monkeypatch.setattr(
        discovery_module, "_search_serpapi_immersive_product", fake_immersive
    )

    results = await discovery_module._search_serpapi(
        "columbia big tall tamiami II SS Shirt",
        limit=5,
    )

    assert engines == ["google_shopping"]
    assert (
        results[0].url
        == "https://www.columbia.com/p/mens-pfg-tamiami-ii-short-sleeve-shirt-big-FM7253.html"
    )
    assert results[0].payload["provider"] == "serpapi_immersive"
    assert results[0].payload["product_id"] == "immersive-product-id"

@pytest.mark.asyncio
@pytest.mark.component
async def test_product_intelligence_serpapi_runs_identifier_organic_without_immersive(
    monkeypatch,
) -> None:
    engines: list[str] = []

    async def fake_engine(
        query: str, *, engine: str, limit: int | None = None
    ) -> dict[str, object]:
        del limit
        engines.append(engine)
        if engine == "google_shopping":
            return {
                "shopping_results": [
                    {
                        "position": 1,
                        "title": "Wrangler Relaxed Bootcut Jeans",
                        "source": "Wrangler",
                        "product_id": "shopping-product-id",
                        "link": "https://www.macys.com/p/wrangler-jeans/123.html",
                    }
                ]
            }
        return {
            "organic_results": [
                {
                    "position": 1,
                    "title": "Wrangler Relaxed Bootcut Jeans",
                    "link": "https://www.wrangler.com/shop/relaxed-bootcut-jeans.html",
                    "snippet": "Official product page.",
                }
            ]
        }

    monkeypatch.setattr(discovery_module, "_search_serpapi_engine", fake_engine)

    results = await discovery_module._search_serpapi(
        "wrangler relaxed bootcut jeans 1123425700 site:wrangler.com",
        limit=5,
    )

    assert engines.count("google") == 1
    assert engines.count("google_shopping") == 1
    assert [result.payload["provider"] for result in results] == [
        "serpapi",
        "serpapi_shopping",
    ]
    assert results[0].url == "https://www.wrangler.com/shop/relaxed-bootcut-jeans.html"

@pytest.mark.asyncio
@pytest.mark.component
async def test_product_intelligence_serpapi_keeps_brand_site_lookup_when_shopping_has_multiple_results(
    monkeypatch,
) -> None:
    engines: list[tuple[str, str]] = []

    async def fake_engine(
        query: str, *, engine: str, limit: int | None = None
    ) -> dict[str, object]:
        del limit
        engines.append((engine, query))
        if engine == "google_shopping":
            return {
                "shopping_results": [
                    {
                        "position": 1,
                        "title": "Levi's 511 Slim Fit Jeans",
                        "source": "Macy's",
                        "link": "https://www.macys.com/p/levi-511/1.html",
                    },
                    {
                        "position": 2,
                        "title": "Levi's 511 Slim Fit Jeans",
                        "source": "Amazon",
                        "link": "https://www.amazon.com/levi-511/2.html",
                    },
                ]
            }
        if query == "levi 511 site:levi.com":
            return {
                "organic_results": [
                    {
                        "position": 1,
                        "title": "Levi's 511 Slim Fit Jeans",
                        "link": "https://www.levi.com/p/04511.html",
                        "snippet": "Official product page",
                    }
                ]
            }
        return {"organic_results": []}

    monkeypatch.setattr(discovery_module, "_search_serpapi_engine", fake_engine)

    results = await discovery_module._search_serpapi(
        "levi 511 site:levi.com",
        limit=5,
    )

    assert ("google", "levi 511 site:levi.com") in engines
    assert ("google", "levi 511") not in engines
    assert results[0].url == "https://www.levi.com/p/04511.html"
    assert results[0].payload["provider"] == "serpapi"

@pytest.mark.component
def test_product_intelligence_serpapi_shopping_query_strips_site_filters() -> None:
    assert (
        discovery_module._shopping_query(
            "wrangler relaxed bootcut jeans site:wrangler.com -site:belk.com"
        )
        == "wrangler relaxed bootcut jeans"
    )

@pytest.mark.component
def test_product_intelligence_parses_serpapi_immersive_limit_before_about_link() -> (
    None
):
    results = parse_serpapi_immersive_results(
        {
            "product_results": {
                "title": "Levi's 511 Slim Fit Jeans",
                "product_id": "immersive-product-id",
                "stores": [
                    {
                        "name": "Levi's",
                        "title": "Levi's 511 Slim Fit Jeans",
                        "link": "https://www.levi.com/p/04511.html",
                    }
                ],
                "about_the_product": {
                    "title": "About Levi's 511 Slim Fit Jeans",
                    "link": "https://www.levi.com/us/en_us/product/511",
                    "displayed_link": "levi.com",
                },
            }
        },
        parent={"product_link": "https://www.google.com/search?ibp=oshop&q=levi"},
        limit=1,
    )

    assert len(results) == 1
    assert results[0].url == "https://www.levi.com/p/04511.html"

@pytest.mark.component
def test_product_intelligence_parses_serpapi_immersive_when_about_payload_is_not_a_dict() -> (
    None
):
    results = parse_serpapi_immersive_results(
        {
            "product_results": {
                "title": "Levi's 511 Slim Fit Jeans",
                "product_id": "immersive-product-id",
                "about_the_product": "unexpected",
                "stores": [
                    {
                        "name": "Levi's",
                        "title": "Levi's 511 Slim Fit Jeans",
                        "link": "https://www.levi.com/p/04511.html",
                    }
                ],
            }
        },
        parent={"product_link": "https://www.google.com/search?ibp=oshop&q=levi"},
        limit=5,
    )

    assert len(results) == 1
    assert results[0].payload["raw"]["product"]["description"] == ""

@pytest.mark.asyncio
@pytest.mark.component
async def test_product_intelligence_discovery_passes_pool_limit_to_search(
    monkeypatch,
) -> None:
    limits: list[int | None] = []

    async def fake_search_results(
        provider: str, query: str, *, limit: int | None = None
    ) -> list[SearchResult]:
        limits.append(limit)
        return [
            SearchResult(
                url="https://www.levi.com/p/04511.html", payload={"title": "Levi 511"}
            ),
        ]

    monkeypatch.setattr(
        "app.services.product_intelligence.discovery._search_results",
        fake_search_results,
    )
    monkeypatch.setattr(product_intelligence_settings, "discovery_pool_multiplier", 4)

    await discover_candidates(
        {"brand": "Levis", "title": "Men 511 Slim Fit Jeans", "sku": "04511"},
        source_domain_value="belk.com",
        provider="serpapi",
        allowed_domains=[],
        excluded_domains=[],
        max_candidates=5,
    )

    assert limits
    assert set(limits) == {20}

@pytest.mark.asyncio
@pytest.mark.component
async def test_product_intelligence_discovery_keeps_multiple_listings_per_domain(
    monkeypatch,
) -> None:
    # A product can be listed by multiple third-party sellers on one marketplace,
    # so discovery must keep more than one distinct listing per domain (bounded only
    # by the user's max_candidates request), not collapse to one per domain.
    async def fake_search_results(
        provider: str, query: str, *, limit: int | None = None
    ) -> list[SearchResult]:
        return [
            SearchResult(
                url="https://www.ebay.com/itm/1", payload={"title": "Levi 511"}
            ),
            SearchResult(
                url="https://www.ebay.com/itm/2", payload={"title": "Levi 511 sale"}
            ),
            SearchResult(
                url="https://www.macys.com/p/1.html", payload={"title": "Levi 511"}
            ),
        ]

    monkeypatch.setattr(
        "app.services.product_intelligence.discovery._search_results",
        fake_search_results,
    )

    candidates = await discover_candidates(
        {
            "brand": "Levis",
            "title": "Men 511 Slim Fit Jeans",
        },
        source_domain_value="belk.com",
        provider="serpapi",
        allowed_domains=[],
        excluded_domains=[],
        max_candidates=5,
    )

    domains = sorted(candidate.domain for candidate in candidates)
    # Both eBay third-party listings survive alongside the macys listing.
    assert domains == ["ebay.com", "ebay.com", "macys.com"]
    urls = {candidate.url for candidate in candidates}
    assert "https://www.ebay.com/itm/1" in urls
    assert "https://www.ebay.com/itm/2" in urls

@pytest.mark.asyncio
@pytest.mark.component
async def test_product_intelligence_discovery_prioritizes_brand_site_over_aggregator_pool(
    monkeypatch,
) -> None:
    async def fake_search_results(
        provider: str, query: str, *, limit: int | None = None
    ) -> list[SearchResult]:
        if "site:levi.com" in query:
            return [
                SearchResult(
                    url="https://thesummitbirmingham.com/buy/product/511",
                    payload={"title": "Levi 511"},
                ),
                SearchResult(
                    url="https://www.hamiltonplace.com/products/product/511",
                    payload={"title": "Levi 511"},
                ),
                SearchResult(
                    url="https://www.coolspringsgalleria.com/products/product/511",
                    payload={"title": "Levi 511"},
                ),
            ]
        return [
            SearchResult(
                url="https://www.levi.com/p/04511.html", payload={"title": "Levi 511"}
            ),
            SearchResult(
                url="https://www.macys.com/p/04511.html", payload={"title": "Levi 511"}
            ),
        ]

    monkeypatch.setattr(
        "app.services.product_intelligence.discovery._search_results",
        fake_search_results,
    )
    monkeypatch.setattr(product_intelligence_settings, "discovery_pool_multiplier", 4)

    candidates = await discover_candidates(
        {
            "brand": "Levis",
            "title": "Men 511 Slim Fit Jeans",
            "sku": "04511",
        },
        source_domain_value="belk.com",
        provider="serpapi",
        allowed_domains=[],
        excluded_domains=[],
        max_candidates=2,
    )

    assert [candidate.domain for candidate in candidates] == ["levi.com", "macys.com"]

@pytest.mark.asyncio
@pytest.mark.component
async def test_product_intelligence_discovery_skips_invalid_result_urls(
    monkeypatch,
) -> None:
    async def fake_search_results(
        provider: str, query: str, *, limit: int | None = None
    ) -> list[SearchResult]:
        return [
            SearchResult(
                url="javascript:void(0)",
                payload={"provider": provider, "title": "Bad scheme"},
            ),
            SearchResult(
                url="",
                payload={"provider": provider, "title": "Empty"},
            ),
            SearchResult(
                url="https://www.levi.com/p/04511.html",
                payload={"provider": provider, "title": "Levi 511"},
            ),
        ]

    monkeypatch.setattr(
        "app.services.product_intelligence.discovery._search_results",
        fake_search_results,
    )

    candidates = await discover_candidates(
        {"brand": "Levis", "title": "Men 511 Slim Fit Jeans", "sku": "04511"},
        source_domain_value="belk.com",
        provider="serpapi",
        allowed_domains=[],
        excluded_domains=[],
        max_candidates=1,
    )

    assert len(candidates) == 1
    assert candidates[0].domain == "levi.com"

@pytest.mark.asyncio
@pytest.mark.component
async def test_product_intelligence_discovery_rejects_listing_urls_from_serpapi() -> (
    None
):
    async def fake_run_query(query: str, limit: int) -> list[SearchResult]:
        del query, limit
        return [
            SearchResult(
                url="https://www.ralphlauren.com/men-clothing-jeans/",
                payload={
                    "provider": "serpapi",
                    "title": "Men's Jeans & Denim",
                    "snippet": "Shop fits, washes and denim styles.",
                },
            ),
            SearchResult(
                url="https://www.ralphlauren.com/men-clothing-jeans/varick-slim-straight-garment-dyed-jean/123.html",
                payload={
                    "provider": "serpapi",
                    "title": "Polo Ralph Lauren Varick Slim Straight Garment-Dyed Jean",
                    "snippet": "Product page for Varick garment-dyed jeans.",
                },
            ),
        ]

    candidates = await discover_candidates(
        {
            "brand": "Polo Ralph Lauren",
            "title": "Varick Slim Straight Garment-Dyed Jeans",
            "url": "https://www.belk.com/p/polo-ralph-lauren-varick-jeans/1.html",
        },
        source_domain_value="belk.com",
        provider="serpapi",
        allowed_domains=[],
        excluded_domains=[],
        max_candidates=1,
        run_query=fake_run_query,
    )

    assert [candidate.url for candidate in candidates] == [
        "https://www.ralphlauren.com/men-clothing-jeans/varick-slim-straight-garment-dyed-jean/123.html"
    ]

@pytest.mark.asyncio
@pytest.mark.component
async def test_product_intelligence_discovery_rejects_html_listing_urls() -> None:
    async def fake_run_query(query: str, limit: int) -> list[SearchResult]:
        del query, limit
        return [
            SearchResult(
                url="https://www.ralphlauren.com/men-clothing-jeans.html",
                payload={
                    "provider": "serpapi",
                    "title": "Men's Jeans & Denim",
                    "snippet": "Shop denim by fit and wash.",
                },
            ),
            SearchResult(
                url="https://www.ralphlauren.com/men-clothing-jeans/varick-slim-straight-garment-dyed-jean/123.html",
                payload={
                    "provider": "serpapi",
                    "title": "Polo Ralph Lauren Varick Slim Straight Garment-Dyed Jean",
                    "snippet": "Product page for Varick garment-dyed jeans.",
                },
            ),
        ]

    candidates = await discover_candidates(
        {
            "brand": "Polo Ralph Lauren",
            "title": "Varick Slim Straight Garment-Dyed Jeans",
            "url": "https://www.belk.com/p/polo-ralph-lauren-varick-jeans/1.html",
        },
        source_domain_value="belk.com",
        provider="serpapi",
        allowed_domains=[],
        excluded_domains=[],
        max_candidates=1,
        run_query=fake_run_query,
    )

    assert [candidate.url for candidate in candidates] == [
        "https://www.ralphlauren.com/men-clothing-jeans/varick-slim-straight-garment-dyed-jean/123.html"
    ]

@pytest.mark.asyncio
@pytest.mark.component
async def test_product_intelligence_discovery_keeps_matching_slug_without_detail_marker() -> (
    None
):
    async def fake_run_query(query: str, limit: int) -> list[SearchResult]:
        del query, limit
        return [
            SearchResult(
                url="https://www.levi.com/men/jeans/511-slim-fit-stretch-denim",
                payload={
                    "provider": "serpapi",
                    "title": "Levi's 511 Slim Fit Stretch Denim Jeans",
                    "snippet": "Official Levi's product page.",
                },
            )
        ]

    candidates = await discover_candidates(
        {
            "brand": "Levis",
            "title": "Men 511 Slim Fit Stretch Denim Jeans",
            "url": "https://www.belk.com/p/levis-511-slim-fit-jeans/1.html",
        },
        source_domain_value="belk.com",
        provider="serpapi",
        allowed_domains=[],
        excluded_domains=[],
        max_candidates=1,
        run_query=fake_run_query,
    )

    assert [candidate.url for candidate in candidates] == [
        "https://www.levi.com/men/jeans/511-slim-fit-stretch-denim"
    ]

@pytest.mark.asyncio
@pytest.mark.component
async def test_product_intelligence_discovery_allows_marketplace_item_ids_when_title_matches() -> (
    None
):
    async def fake_run_query(query: str, limit: int) -> list[SearchResult]:
        del query, limit
        return [
            SearchResult(
                url="https://www.ebay.com/itm/188098451561",
                payload={
                    "provider": "serpapi_immersive",
                    "title": "Izod Men's Comfort Stretch Blue Denim Jeans",
                    "source": "eBay",
                    "product_id": "3501016343738340012",
                },
            )
        ]

    candidates = await discover_candidates(
        {
            "brand": "IZOD",
            "title": "Comfort Stretch Blue Denim Jeans",
            "sku": "3203394I39JN16",
            "url": "https://www.belk.com/p/izod-jeans/1.html",
        },
        source_domain_value="belk.com",
        provider="serpapi",
        allowed_domains=[],
        excluded_domains=[],
        max_candidates=1,
        run_query=fake_run_query,
    )

    assert [candidate.url for candidate in candidates] == [
        "https://www.ebay.com/itm/188098451561"
    ]

@pytest.mark.asyncio
@pytest.mark.component
async def test_product_intelligence_discovery_rejects_editorial_brand_pages() -> None:
    async def fake_run_query(query: str, limit: int) -> list[SearchResult]:
        del query, limit
        return [
            SearchResult(
                url="https://eu.wrangler.com/uk-en/how%20to%20style%20bootcut%20jeans/how-to-wear-bootcut-jeans.html",
                payload={
                    "provider": "serpapi",
                    "title": "How to Wear Bootcut Jeans",
                    "snippet": "A styling guide from Wrangler.",
                },
            ),
            SearchResult(
                url="https://www.wrangler.com/browse/relaxed-fit-bootcut-jeans.html",
                payload={
                    "provider": "serpapi",
                    "title": "Relaxed Fit Bootcut Jeans",
                    "snippet": "Wrangler product page.",
                },
            ),
        ]

    candidates = await discover_candidates(
        {
            "brand": "Wrangler�",
            "title": "Wrangler� Relaxed Bootcut Jeans",
            "url": "https://www.belk.com/p/wrangler--relaxed-bootcut-jeans-/3200040112342570.html",
        },
        source_domain_value="belk.com",
        provider="serpapi",
        allowed_domains=[],
        excluded_domains=[],
        max_candidates=1,
        run_query=fake_run_query,
    )

    assert [candidate.url for candidate in candidates] == [
        "https://www.wrangler.com/browse/relaxed-fit-bootcut-jeans.html"
    ]

@pytest.mark.asyncio
@pytest.mark.component
async def test_product_intelligence_discovery_rejects_unrelated_google_native_products() -> (
    None
):
    async def fake_run_query(query: str, limit: int) -> list[SearchResult]:
        del query, limit
        return [
            SearchResult(
                url="https://www.levi.com/p/505-regular-fit-mens-jeans/005050260.html",
                payload={
                    "provider": "google_native",
                    "title": "Levi's 505 Regular Fit Men's Jeans",
                    "snippet": "Classic straight leg jeans.",
                },
            ),
            SearchResult(
                url="https://www.levi.com/p/511-slim-fit-mens-jeans/045112406.html",
                payload={
                    "provider": "google_native",
                    "title": "Levi's 511 Slim Fit Men's Jeans",
                    "snippet": "Slim fit jeans, style 04511-2406.",
                },
            ),
        ]

    candidates = await discover_candidates(
        {
            "brand": "Levis",
            "title": "Men 511 Slim Fit Jeans",
            "sku": "04511-2406",
            "url": "https://www.belk.com/p/levis-511-slim-fit-jeans/1.html",
        },
        source_domain_value="belk.com",
        provider="google_native",
        allowed_domains=[],
        excluded_domains=[],
        max_candidates=1,
        run_query=fake_run_query,
    )

    assert [candidate.url for candidate in candidates] == [
        "https://www.levi.com/p/511-slim-fit-mens-jeans/045112406.html"
    ]

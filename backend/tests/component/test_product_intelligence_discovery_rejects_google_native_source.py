from __future__ import annotations

from .test_product_intelligence import AsyncSession, CrawlRecord, LLMTaskResult, ProductIntelligenceMatch, ProductIntelligenceSourceProduct, SearchResult, create_product_intelligence_job, discover_candidates, discover_product_intelligence_candidates, product_intelligence_settings, pytest, select  # fmt: skip


@pytest.mark.asyncio
@pytest.mark.component
async def test_product_intelligence_discovery_rejects_google_native_source_domain_and_url() -> (
    None
):
    async def fake_run_query(query: str, limit: int) -> list[SearchResult]:
        assert "belk.com" not in query
        del limit
        return [
            SearchResult(
                url="https://www.belk.com/p/nike-womens-run-defy-sneakers/2900020HM9593.html",
                payload={
                    "provider": "google_native",
                    "title": "Women's Run Defy Sneakers",
                    "snippet": "Nike sneakers at Belk.",
                },
            ),
            SearchResult(
                url="https://www.nike.com/t/run-defy-womens-road-running-shoes/HM9593",
                payload={
                    "provider": "google_native",
                    "title": "Nike Run Defy Women's Road Running Shoes",
                    "snippet": "Style HM9593.",
                },
            ),
        ]

    candidates = await discover_candidates(
        {
            "brand": "Nike",
            "title": "Women's Run Defy Sneakers",
            "sku": "HM9593",
            "url": "https://www.belk.com/p/nike-womens-run-defy-sneakers/2900020HM9593.html",
        },
        source_domain_value="belk.com",
        provider="google_native",
        allowed_domains=[],
        excluded_domains=[],
        max_candidates=1,
        run_query=fake_run_query,
    )

    assert [candidate.url for candidate in candidates] == [
        "https://www.nike.com/t/run-defy-womens-road-running-shoes/HM9593"
    ]


@pytest.mark.asyncio
@pytest.mark.component
async def test_product_intelligence_discovery_keeps_search_delay_while_filling_pool(
    monkeypatch,
) -> None:
    recorded_delays: list[float] = []

    async def fake_search_results(
        provider: str, query: str, *, limit: int | None = None
    ) -> list[SearchResult]:
        if query == "query one":
            return [
                SearchResult(
                    url="https://www.levi.com/p/04511.html",
                    payload={"title": "Levi 511"},
                ),
            ]
        return [
            SearchResult(
                url="https://www.macys.com/p/04511.html", payload={"title": "Levi 511"}
            ),
        ]

    async def fake_sleep(delay: float) -> None:
        recorded_delays.append(delay)

    monkeypatch.setattr(
        "app.services.product_intelligence.discovery.build_search_queries",
        lambda product, *, source_domain_value: ["query one", "query two"],
    )
    monkeypatch.setattr(
        "app.services.product_intelligence.discovery._search_results",
        fake_search_results,
    )
    monkeypatch.setattr(
        "app.services.product_intelligence.discovery.asyncio.sleep",
        fake_sleep,
    )
    monkeypatch.setattr(product_intelligence_settings, "search_delay_ms", 25)
    monkeypatch.setattr(product_intelligence_settings, "discovery_pool_multiplier", 2)

    candidates = await discover_candidates(
        {"brand": "Levis", "title": "Men 511 Slim Fit Jeans", "sku": "04511"},
        source_domain_value="belk.com",
        provider="serpapi",
        allowed_domains=[],
        excluded_domains=[],
        max_candidates=1,
    )

    assert recorded_delays == [0.025]
    assert len(candidates) == 1
    assert candidates[0].domain == "levi.com"


@pytest.mark.asyncio
@pytest.mark.component
async def test_product_intelligence_discovery_fills_requested_count_after_strong_first_query_brand_dtc(
    monkeypatch,
) -> None:
    seen_queries: list[str] = []
    recorded_delays: list[float] = []

    async def fake_search_results(
        provider: str, query: str, *, limit: int | None = None
    ) -> list[SearchResult]:
        del provider, limit
        seen_queries.append(query)
        if query == "query one":
            return [
                SearchResult(
                    url="https://www.levi.com/p/04511-2406.html",
                    payload={"title": "Levi's Men 511 Slim Fit Jeans"},
                )
            ]
        return [
            SearchResult(
                url="https://www.macys.com/p/04511.html", payload={"title": "Levi 511"}
            ),
        ]

    async def fake_sleep(delay: float) -> None:
        recorded_delays.append(delay)

    monkeypatch.setattr(
        "app.services.product_intelligence.discovery.build_search_queries",
        lambda product, *, source_domain_value: ["query one", "query two"],
    )
    monkeypatch.setattr(
        "app.services.product_intelligence.discovery._search_results",
        fake_search_results,
    )
    monkeypatch.setattr(
        "app.services.product_intelligence.discovery.asyncio.sleep",
        fake_sleep,
    )
    monkeypatch.setattr(product_intelligence_settings, "search_delay_ms", 25)

    candidates = await discover_candidates(
        {"brand": "Levis", "title": "Men 511 Slim Fit Jeans", "sku": "04511-2406"},
        source_domain_value="belk.com",
        provider="serpapi",
        allowed_domains=[],
        excluded_domains=[],
        max_candidates=2,
    )

    assert seen_queries == ["query one", "query two"]
    assert recorded_delays == [0.025]
    assert [candidate.domain for candidate in candidates] == ["levi.com", "macys.com"]


@pytest.mark.asyncio
@pytest.mark.component
async def test_product_intelligence_job_stores_source_products_and_llm_option(
    db_session: AsyncSession,
    test_user,
    create_test_run,
) -> None:
    run = await create_test_run(
        url="https://www.belk.com/category",
        surface="ecommerce_listing",
    )
    record = CrawlRecord(
        run_id=run.id,
        source_url="https://www.belk.com/p/new-directions-shirt/1.html",
        data={
            "brand": "New Directions",
            "title": "Relaxed Shirt",
            "price": "$19.99",
            "url": "https://www.belk.com/p/new-directions-shirt/1.html",
        },
        raw_data={},
        discovered_data={},
        source_trace={},
    )
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(record)

    job = await create_product_intelligence_job(
        db_session,
        user=test_user,
        payload={
            "source_run_id": run.id,
            "source_record_ids": [record.id],
            "options": {
                "llm_enrichment_enabled": True,
                "private_label_mode": "flag",
            },
        },
    )

    assert job.options["llm_enrichment_enabled"] is True
    source = await db_session.scalar(
        select(ProductIntelligenceSourceProduct).where(
            ProductIntelligenceSourceProduct.job_id == job.id
        )
    )
    assert source is not None
    assert source.is_private_label is True
    assert source.price == pytest.approx(19.99)


@pytest.mark.asyncio
@pytest.mark.component
async def test_product_intelligence_discovery_preview_returns_source_and_payload(
    db_session: AsyncSession,
    test_user,
    monkeypatch,
    create_test_run,
) -> None:
    run = await create_test_run(
        url="https://www.belk.com/category",
        surface="ecommerce_listing",
    )
    record = CrawlRecord(
        run_id=run.id,
        source_url="https://www.belk.com/p/polo-ralph-lauren-varick-jeans/1.html",
        data={
            "title": "Varick Slim Straight Garment-Dyed Jeans",
            "price": "$125.00",
            "url": "https://www.belk.com/p/polo-ralph-lauren-varick-jeans/1.html",
        },
        raw_data={},
        discovered_data={},
        source_trace={},
    )
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(record)

    async def fake_search_results(
        provider: str, query: str, *, limit: int | None = None
    ) -> list[SearchResult]:
        return [
            SearchResult(
                url="https://www.ralphlauren.com/men-clothing-jeans/varick/123.html",
                payload={"provider": provider, "title": "Varick jean"},
            )
        ]

    monkeypatch.setattr(
        "app.services.product_intelligence.discovery._search_results",
        fake_search_results,
    )

    response = await discover_product_intelligence_candidates(
        db_session,
        user=test_user,
        payload={
            "source_run_id": run.id,
            "source_record_ids": [record.id],
            "options": {
                "max_source_products": 1,
                "max_candidates_per_product": 1,
                "search_provider": "serpapi",
                "confidence_threshold": 0.0,
            },
        },
    )

    assert response["source_count"] == 1
    assert response["candidate_count"] == 1
    assert isinstance(response["job_id"], int)
    assert response["candidates"][0]["source_brand"] == "ralph lauren"
    assert response["candidates"][0]["payload"]["provider"] == "serpapi"
    assert (
        response["candidates"][0]["intelligence"]["canonical_record"]["title"]
        == "Varick jean"
    )
    assert (
        response["candidates"][0]["intelligence"]["canonical_record"]["price"] is None
    )
    assert response["candidates"][0]["intelligence"]["confidence_score"] >= 0
    persisted_match = await db_session.scalar(
        select(ProductIntelligenceMatch).where(
            ProductIntelligenceMatch.job_id == response["job_id"]
        )
    )
    assert persisted_match is not None
    assert persisted_match.candidate_price is None


@pytest.mark.asyncio
@pytest.mark.component
async def test_product_intelligence_discovery_preview_skips_search_result_llm_enrichment(
    db_session: AsyncSession,
    test_user,
    monkeypatch,
    create_test_run,
) -> None:
    run = await create_test_run(
        url="https://www.belk.com/category",
        surface="ecommerce_listing",
    )
    record = CrawlRecord(
        run_id=run.id,
        source_url="https://www.belk.com/p/levis-511-slim-fit-jeans/1.html",
        data={
            "brand": "Levis",
            "title": "Men 511 Slim Fit Jeans",
            "url": "https://www.belk.com/p/levis-511-slim-fit-jeans/1.html",
        },
        raw_data={},
        discovered_data={},
        source_trace={},
    )
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(record)

    async def fake_search_results(
        provider: str, query: str, *, limit: int | None = None
    ) -> list[SearchResult]:
        del provider, query, limit
        return [
            SearchResult(
                url="https://www.levi.com/p/04511.html",
                payload={
                    "provider": "serpapi",
                    "title": "Levi's Men 511 Slim Fit Jeans",
                },
            )
        ]

    async def fake_run_prompt_task(session, *, task_type, run_id, domain, variables):
        del session, run_id, domain, variables
        if task_type == "product_intelligence_enrichment":
            raise AssertionError("Discovery preview must not call enrichment LLM")
        return LLMTaskResult(
            payload={"brand": "Levis", "confidence": 0.95},
            provider="groq",
            model="llama",
        )

    monkeypatch.setattr(
        "app.services.product_intelligence.discovery._search_results",
        fake_search_results,
    )
    monkeypatch.setattr(
        "app.services.product_intelligence.service.run_prompt_task",
        fake_run_prompt_task,
    )

    response = await discover_product_intelligence_candidates(
        db_session,
        user=test_user,
        payload={
            "source_run_id": run.id,
            "source_record_ids": [record.id],
            "options": {
                "max_source_products": 1,
                "max_candidates_per_product": 1,
                "search_provider": "serpapi",
                "llm_enrichment_enabled": True,
            },
        },
    )

    assert response["candidate_count"] == 1
    assert response["candidates"][0]["intelligence"]["llm_enrichment"] == {
        "requested": False,
        "applied": False,
    }


@pytest.mark.asyncio
@pytest.mark.component
async def test_product_intelligence_discovery_prefers_row_source_url_for_query_exclusion(
    db_session: AsyncSession,
    test_user,
    monkeypatch,
) -> None:
    seen_queries: list[str] = []

    async def fake_search_results(
        provider: str, query: str, *, limit: int | None = None
    ) -> list[SearchResult]:
        del provider, limit
        seen_queries.append(query)
        return [
            SearchResult(
                url="https://www.example-brand.com/p/item.html",
                payload={"provider": "google_native", "title": "Example Item"},
            )
        ]

    monkeypatch.setattr(
        "app.services.product_intelligence.discovery._search_results",
        fake_search_results,
    )

    response = await discover_product_intelligence_candidates(
        db_session,
        user=test_user,
        payload={
            "source_records": [
                {
                    "source_url": "https://www.myntra.com/p/shoes/example-item.html",
                    "data": {
                        "title": "Example Item",
                        "brand": "Example Brand",
                        "url": "https://www.belk.com/p/stale-item.html",
                    },
                }
            ],
            "options": {
                "max_source_products": 1,
                "max_candidates_per_product": 1,
                "search_provider": "serpapi",
                "confidence_threshold": 0.0,
            },
        },
    )

    assert seen_queries
    assert all("myntra.com" not in query for query in seen_queries)
    assert all("belk.com" not in query for query in seen_queries)
    assert (
        response["candidates"][0]["source_url"]
        == "https://www.myntra.com/p/shoes/example-item.html"
    )


@pytest.mark.asyncio
@pytest.mark.component
async def test_product_intelligence_discovery_uses_product_url_from_listing_record(
    db_session: AsyncSession,
    test_user,
    monkeypatch,
    create_test_run,
) -> None:
    run = await create_test_run(
        url="https://www.belk.com/men/mens-clothing/jeans/",
        surface="ecommerce_listing",
    )
    record = CrawlRecord(
        run_id=run.id,
        source_url="https://www.belk.com/men/mens-clothing/jeans/",
        data={
            "brand": "Wrangler\u00ae",
            "title": "Wrangler\u00ae Relaxed Bootcut Jeans",
            "url": "https://www.belk.com/p/wrangler--relaxed-bootcut-jeans-/3200040112342570.html",
            "price": "39.95",
        },
        raw_data={},
        discovered_data={},
        source_trace={},
    )
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(record)

    seen_queries: list[str] = []

    async def fake_search_results(
        provider: str, query: str, *, limit: int | None = None
    ) -> list[SearchResult]:
        del provider, limit
        seen_queries.append(query)
        return [
            SearchResult(
                url="https://www.wrangler.com/shop/relaxed-bootcut-jeans.html",
                payload={
                    "provider": "serpapi",
                    "title": "Wrangler Relaxed Bootcut Jeans",
                },
            )
        ]

    monkeypatch.setattr(
        "app.services.product_intelligence.discovery._search_results",
        fake_search_results,
    )

    response = await discover_product_intelligence_candidates(
        db_session,
        user=test_user,
        payload={
            "source_record_ids": [record.id],
            "options": {
                "max_source_products": 1,
                "max_candidates_per_product": 1,
                "search_provider": "serpapi",
                "confidence_threshold": 0.0,
            },
        },
    )

    assert response["candidates"][0]["source_url"] == (
        "https://www.belk.com/p/wrangler--relaxed-bootcut-jeans-/3200040112342570.html"
    )
    assert response["candidates"][0]["source_price"] == pytest.approx(39.95)
    assert seen_queries[0] == "site:wrangler.com wrangler Relaxed Bootcut Jeans"


@pytest.mark.asyncio
@pytest.mark.component
async def test_product_intelligence_discovery_reuses_one_query_runner_for_multiple_sources(
    db_session: AsyncSession,
    test_user,
    monkeypatch,
) -> None:
    enter_count = 0
    seen_queries: list[str] = []

    class _Runner:
        async def __aenter__(self):
            nonlocal enter_count
            enter_count += 1

            async def _run(query: str, limit: int) -> list[SearchResult]:
                del limit
                seen_queries.append(query)
                token = len(seen_queries)
                return [
                    SearchResult(
                        url=f"https://www.levi.com/p/{token}.html",
                        payload={
                            "provider": "google_native",
                            "title": f"Product {token} 511 Jeans",
                            "price": "$55.00",
                        },
                    )
                ]

            return _run

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "app.services.product_intelligence.service.shared_query_runner",
        lambda provider: _Runner(),
    )

    response = await discover_product_intelligence_candidates(
        db_session,
        user=test_user,
        payload={
            "source_records": [
                {
                    "source_url": "https://www.belk.com/p/one.html",
                    "data": {
                        "brand": "Levis",
                        "title": "Product One 511 Jeans",
                        "url": "https://www.belk.com/p/one.html",
                    },
                },
                {
                    "source_url": "https://www.belk.com/p/two.html",
                    "data": {
                        "brand": "Levis",
                        "title": "Product Two 511 Jeans",
                        "url": "https://www.belk.com/p/two.html",
                    },
                },
            ],
            "options": {
                "max_source_products": 2,
                "max_candidates_per_product": 1,
                "search_provider": "google_native",
            },
        },
    )

    assert response["candidate_count"] == 2
    assert enter_count == 1
    assert len(seen_queries) >= 2


@pytest.mark.asyncio
@pytest.mark.component
async def test_product_intelligence_discovery_returns_max_urls_per_input_source(
    db_session: AsyncSession,
    test_user,
    monkeypatch,
) -> None:
    async def fake_search_results(
        provider: str, query: str, *, limit: int | None = None
    ) -> list[SearchResult]:
        quoted = query.split('"')
        title_source = (
            quoted[3]
            if len(quoted) > 3
            else quoted[1]
            if len(quoted) > 1
            else quoted[0]
        )
        title_token = title_source.split()[0]
        return [
            SearchResult(
                url=f"https://www.levi.com/p/{title_token}.html",
                payload={"provider": provider, "title": title_token},
            ),
            SearchResult(
                url=f"https://www.macys.com/p/{title_token}.html",
                payload={"provider": provider, "title": title_token},
            ),
            SearchResult(
                url=f"https://www.nordstrom.com/p/{title_token}.html",
                payload={"provider": provider, "title": title_token},
            ),
        ]

    monkeypatch.setattr(
        "app.services.product_intelligence.discovery._search_results",
        fake_search_results,
    )

    response = await discover_product_intelligence_candidates(
        db_session,
        user=test_user,
        payload={
            "source_records": [
                {
                    "source_url": f"https://www.belk.com/p/{index}.html",
                    "data": {
                        "brand": "Levis",
                        "title": f"Product {index} 511 Jeans",
                        "url": f"https://www.belk.com/p/{index}.html",
                    },
                }
                for index in range(4)
            ],
            "options": {
                "max_source_products": 4,
                "max_candidates_per_product": 3,
                "search_provider": "serpapi",
                "confidence_threshold": 0.0,
            },
        },
    )

    assert response["source_count"] == 4
    assert response["candidate_count"] == 12
    assert {candidate["source_index"] for candidate in response["candidates"]} == {
        0,
        1,
        2,
        3,
    }

from __future__ import annotations

from .test_product_intelligence import GOOGLE_NATIVE_HOME_URL, LLMErrorCategory, LLMTaskResult, SearchResult, _build_candidate_intelligence, backfill_candidate_brand, discover_candidates, discovery_module, get_prompt_task, google_native_session, parse_serpapi_immersive_results, parse_serpapi_shopping_results, pytest, resolve_source_snapshot  # fmt: skip


@pytest.mark.asyncio
@pytest.mark.component
async def test_google_native_session_reuses_single_page_across_queries(
    monkeypatch,
) -> None:
    actions: list[str] = []
    current_url = GOOGLE_NATIVE_HOME_URL
    last_query = ""
    html_by_query: dict[str, str] = {}

    class _Locator:
        async def fill(self, value: str) -> None:
            nonlocal last_query
            last_query = value
            actions.append(f"fill:{value}")

        async def press(self, value: str) -> None:
            actions.append(f"press:{value}")

    class _Page:
        async def goto(self, url: str, *, wait_until: str, timeout: int):
            nonlocal current_url
            current_url = url
            actions.append(f"goto:{url}")

        def locator(self, selector: str):
            actions.append(f"locator:{selector}")
            return _Locator()

        async def wait_for_timeout(self, timeout_ms: int) -> None:
            actions.append(f"wait:{timeout_ms}")

        @property
        def url(self) -> str:
            return current_url

    class _Runtime:
        def page(self, **kwargs):
            actions.append(f"page-acquired:{kwargs.get('domain')}")

            class _Context:
                async def __aenter__(self):
                    return _Page()

                async def __aexit__(self, exc_type, exc, tb):
                    actions.append("page-released")
                    return None

            return _Context()

    async def _fake_runtime(*, browser_engine: str):
        actions.append(f"engine:{browser_engine}")
        return _Runtime()

    async def _fake_html(_page):
        return html_by_query.get(
            last_query,
            """
            <a href="/url?q=https%3A%2F%2Fshop.example.com%2Fp%2Fwidget"><h3>Widget</h3></a>
            """,
        )

    monkeypatch.setattr(
        "app.services.product_intelligence.discovery.get_browser_runtime",
        _fake_runtime,
    )
    monkeypatch.setattr(
        "app.services.product_intelligence.discovery.get_page_html",
        _fake_html,
    )

    async with google_native_session() as run_query:
        html_by_query["blue shoe"] = """
        <a href="/url?q=https%3A%2F%2Fshop.example.com%2Fp%2Fwidget"><h3>Widget</h3></a>
        """
        html_by_query["red shoe"] = """
        <a href="/url?q=https%3A%2F%2Fshop.example.com%2Fp%2Fother"><h3>Other Widget</h3></a>
        """
        html_by_query["green shoe"] = """
        <a href="/url?q=https%3A%2F%2Fshop.example.com%2Fp%2Fthird"><h3>Third Widget</h3></a>
        """
        first = await run_query("blue shoe", 3)
        second = await run_query("red shoe", 3)
        third = await run_query("green shoe", 3)

    assert actions.count("page-acquired:google.com") == 1
    assert actions.count("page-released") == 1
    assert actions.count(f"goto:{GOOGLE_NATIVE_HOME_URL}") == 3
    assert "fill:blue shoe" in actions
    assert "fill:red shoe" in actions
    assert "fill:green shoe" in actions
    assert actions.count("press:Enter") == 3
    assert first[0].url == "https://shop.example.com/p/widget"
    assert second and third


@pytest.mark.asyncio
@pytest.mark.component
async def test_google_native_session_stops_after_google_sorry_page(monkeypatch) -> None:
    actions: list[str] = []
    current_url = GOOGLE_NATIVE_HOME_URL
    last_query = ""
    html_by_query: dict[str, str] = {}

    class _Locator:
        async def fill(self, value: str) -> None:
            nonlocal last_query
            last_query = value
            actions.append(f"fill:{value}")

        async def press(self, value: str) -> None:
            actions.append(f"press:{value}")

    class _Page:
        async def goto(self, url: str, *, wait_until: str, timeout: int):
            nonlocal current_url
            current_url = url
            actions.append(f"goto:{url}")

        def locator(self, selector: str):
            actions.append(f"locator:{selector}")
            return _Locator()

        async def wait_for_timeout(self, timeout_ms: int) -> None:
            actions.append(f"wait:{timeout_ms}")

        @property
        def url(self) -> str:
            return current_url

    class _Runtime:
        def page(self, **kwargs):
            actions.append(f"page-acquired:{kwargs.get('domain')}")

            class _Context:
                async def __aenter__(self):
                    return _Page()

                async def __aexit__(self, exc_type, exc, tb):
                    actions.append("page-released")
                    return None

            return _Context()

    async def _fake_runtime(*, browser_engine: str):
        actions.append(f"engine:{browser_engine}")
        return _Runtime()

    async def _fake_html(_page):
        return html_by_query.get(last_query, "")

    monkeypatch.setattr(
        "app.services.product_intelligence.discovery.get_browser_runtime",
        _fake_runtime,
    )
    monkeypatch.setattr(
        "app.services.product_intelligence.discovery.get_page_html",
        _fake_html,
    )
    html_by_query["blue shoe"] = """
    <html><body>
      <p>Our systems have detected unusual traffic from your computer network.</p>
      <p>This page checks to see if it's really you sending the requests.</p>
    </body></html>
    """

    async with google_native_session() as run_query:
        first = await run_query("blue shoe", 3)
        second = await run_query("red shoe", 3)

    assert first == []
    assert second == []
    assert actions.count(f"goto:{GOOGLE_NATIVE_HOME_URL}") == 1
    assert "fill:blue shoe" in actions
    assert "fill:red shoe" not in actions


@pytest.mark.component
def test_product_intelligence_llm_prompt_registered() -> None:
    task = get_prompt_task("product_intelligence_enrichment")

    assert task is not None
    assert task["system_file"] == "product_intelligence_enrichment.system.txt"


@pytest.mark.component
def test_product_intelligence_brand_inference_prompt_registered() -> None:
    task = get_prompt_task("product_intelligence_brand_inference")

    assert task is not None
    assert task["system_file"] == "product_intelligence_brand_inference.system.txt"
    assert task["user_file"] == "product_intelligence_brand_inference.user.txt"


@pytest.mark.asyncio
@pytest.mark.component
async def test_resolve_source_snapshot_skips_llm_when_brand_present(
    monkeypatch,
) -> None:
    calls: list[str] = []

    async def fake_run_prompt_task(*args, **kwargs):
        calls.append(kwargs.get("task_type", ""))
        raise AssertionError("LLM must not be called when brand already resolved")

    monkeypatch.setattr(
        "app.services.product_intelligence.service.run_prompt_task",
        fake_run_prompt_task,
    )

    snapshot = await resolve_source_snapshot(
        session=None,  # never used because LLM path is gated off
        raw={
            "brand": "Levis",
            "title": "Men 511 Slim Fit Jeans",
            "url": "https://www.belk.com/p/1.html",
        },
        llm_enabled=True,
    )

    assert snapshot["brand"] == "Levis"
    assert snapshot["normalized_brand"] == "levi's"
    assert calls == []


@pytest.mark.asyncio
@pytest.mark.component
async def test_resolve_source_snapshot_skips_llm_when_disabled(monkeypatch) -> None:
    async def fake_run_prompt_task(*args, **kwargs):
        raise AssertionError("LLM must not be called when llm_enabled is False")

    monkeypatch.setattr(
        "app.services.product_intelligence.service.run_prompt_task",
        fake_run_prompt_task,
    )

    snapshot = await resolve_source_snapshot(
        session=None,
        raw={
            "title": "Wundermost Bodysuit",
            "url": "https://shop.example.com/products/wundermost.html",
        },
        llm_enabled=False,
    )

    assert snapshot["brand"] == ""
    assert snapshot["normalized_brand"] == ""


@pytest.mark.asyncio
@pytest.mark.component
async def test_resolve_source_snapshot_uses_llm_brand_when_confident(
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    async def fake_run_prompt_task(session, *, task_type, run_id, domain, variables):
        captured["task_type"] = task_type
        captured["domain"] = domain
        captured["variables"] = variables
        return LLMTaskResult(
            payload={
                "brand": "Lululemon",
                "confidence": 0.92,
                "rationale": "DTC URL match",
            },
            provider="groq",
            model="llama",
        )

    monkeypatch.setattr(
        "app.services.product_intelligence.service.run_prompt_task",
        fake_run_prompt_task,
    )

    snapshot = await resolve_source_snapshot(
        session=None,
        raw={
            "title": "Wundermost Bodysuit",
            "url": "https://www.lululemon.com/products/p/wundermost-bodysuit.html",
        },
        llm_enabled=True,
    )

    assert snapshot["brand"] == "Lululemon"
    assert snapshot["normalized_brand"] == "lululemon"
    assert captured["task_type"] == "product_intelligence_brand_inference"
    assert captured["domain"] == "lululemon.com"
    assert captured["variables"]["product_title"] == "Wundermost Bodysuit"
    assert captured["variables"]["source_domain"] == "lululemon.com"


@pytest.mark.asyncio
@pytest.mark.component
async def test_resolve_source_snapshot_drops_low_confidence_llm_brand(
    monkeypatch,
) -> None:
    async def fake_run_prompt_task(session, *, task_type, run_id, domain, variables):
        return LLMTaskResult(
            payload={
                "brand": "MaybeBrand",
                "confidence": 0.2,
                "rationale": "weak signal",
            },
            provider="groq",
            model="llama",
        )

    monkeypatch.setattr(
        "app.services.product_intelligence.service.run_prompt_task",
        fake_run_prompt_task,
    )

    snapshot = await resolve_source_snapshot(
        session=None,
        raw={"title": "Random Title", "url": "https://retailer.example.com/p/123.html"},
        llm_enabled=True,
    )

    assert snapshot["brand"] == ""
    assert snapshot["normalized_brand"] == ""


@pytest.mark.asyncio
@pytest.mark.component
async def test_resolve_source_snapshot_swallows_llm_error(monkeypatch) -> None:
    async def fake_run_prompt_task(session, *, task_type, run_id, domain, variables):
        return LLMTaskResult(
            payload=None,
            error_message="provider unavailable",
            error_category=LLMErrorCategory.PROVIDER_ERROR,
        )

    monkeypatch.setattr(
        "app.services.product_intelligence.service.run_prompt_task",
        fake_run_prompt_task,
    )

    snapshot = await resolve_source_snapshot(
        session=None,
        raw={"title": "Random Title", "url": "https://retailer.example.com/p/123.html"},
        llm_enabled=True,
    )

    assert snapshot["brand"] == ""
    assert snapshot["normalized_brand"] == ""


@pytest.mark.asyncio
@pytest.mark.component
async def test_resolve_source_snapshot_skips_llm_when_no_inputs(monkeypatch) -> None:
    async def fake_run_prompt_task(*args, **kwargs):
        raise AssertionError("LLM must not be called without title or url")

    monkeypatch.setattr(
        "app.services.product_intelligence.service.run_prompt_task",
        fake_run_prompt_task,
    )

    snapshot = await resolve_source_snapshot(
        session=None,
        raw={},
        llm_enabled=True,
    )

    assert snapshot["brand"] == ""


@pytest.mark.asyncio
@pytest.mark.component
async def test_backfill_candidate_brand_skips_when_disabled(monkeypatch) -> None:
    async def fake_run_prompt_task(*args, **kwargs):
        raise AssertionError("LLM must not be called when llm_enabled is False")

    monkeypatch.setattr(
        "app.services.product_intelligence.service.run_prompt_task",
        fake_run_prompt_task,
    )

    intelligence = _build_candidate_intelligence()
    result = await backfill_candidate_brand(
        session=None,
        source={"title": "Lululemon Wundermost Bodysuit", "brand": "Lululemon"},
        intelligence=intelligence,
        source_type="brand_dtc",
        llm_enabled=False,
    )

    assert result is intelligence


@pytest.mark.asyncio
@pytest.mark.component
async def test_backfill_candidate_brand_skips_when_brand_present(monkeypatch) -> None:
    async def fake_run_prompt_task(*args, **kwargs):
        raise AssertionError("LLM must not be called when candidate brand is set")

    monkeypatch.setattr(
        "app.services.product_intelligence.service.run_prompt_task",
        fake_run_prompt_task,
    )

    intelligence = _build_candidate_intelligence(brand="Lululemon")
    result = await backfill_candidate_brand(
        session=None,
        source={"title": "Lululemon Wundermost Bodysuit", "brand": "Lululemon"},
        intelligence=intelligence,
        source_type="brand_dtc",
        llm_enabled=True,
    )

    assert result is intelligence


@pytest.mark.asyncio
@pytest.mark.component
async def test_backfill_candidate_brand_applies_llm_brand_and_rescores(
    monkeypatch,
) -> None:
    async def fake_run_prompt_task(session, *, task_type, run_id, domain, variables):
        return LLMTaskResult(
            payload={
                "brand": "Lululemon",
                "confidence": 0.91,
                "rationale": "DTC URL match",
            },
            provider="groq",
            model="llama",
        )

    monkeypatch.setattr(
        "app.services.product_intelligence.service.run_prompt_task",
        fake_run_prompt_task,
    )

    intelligence = _build_candidate_intelligence()
    source = {
        "title": "Lululemon Wundermost Bodysuit",
        "brand": "Lululemon",
        "normalized_brand": "lululemon",
    }
    result = await backfill_candidate_brand(
        session=None,
        source=source,
        intelligence=intelligence,
        source_type="brand_dtc",
        llm_enabled=True,
    )

    canonical = result["canonical_record"]
    assert canonical["brand"] == "Lululemon"
    assert canonical["normalized_brand"] == "lululemon"
    assert result["score_reasons"]["brand_match"] is True
    assert result["confidence_score"] > intelligence["confidence_score"]


@pytest.mark.asyncio
@pytest.mark.component
async def test_backfill_candidate_brand_drops_low_confidence(monkeypatch) -> None:
    async def fake_run_prompt_task(session, *, task_type, run_id, domain, variables):
        return LLMTaskResult(
            payload={"brand": "Maybe", "confidence": 0.1, "rationale": "weak"},
            provider="groq",
            model="llama",
        )

    monkeypatch.setattr(
        "app.services.product_intelligence.service.run_prompt_task",
        fake_run_prompt_task,
    )

    intelligence = _build_candidate_intelligence()
    result = await backfill_candidate_brand(
        session=None,
        source={"title": "Wundermost Bodysuit", "brand": ""},
        intelligence=intelligence,
        source_type="unknown",
        llm_enabled=True,
    )

    assert result is intelligence


@pytest.mark.asyncio
@pytest.mark.component
async def test_backfill_candidate_brand_handles_llm_error(monkeypatch) -> None:
    async def fake_run_prompt_task(session, *, task_type, run_id, domain, variables):
        return LLMTaskResult(
            payload=None,
            error_message="provider down",
            error_category=LLMErrorCategory.PROVIDER_ERROR,
        )

    monkeypatch.setattr(
        "app.services.product_intelligence.service.run_prompt_task",
        fake_run_prompt_task,
    )

    intelligence = _build_candidate_intelligence()
    result = await backfill_candidate_brand(
        session=None,
        source={"title": "Anything", "brand": ""},
        intelligence=intelligence,
        source_type="retailer",
        llm_enabled=True,
    )

    assert result is intelligence


@pytest.mark.asyncio
@pytest.mark.component
async def test_product_intelligence_discovery_preserves_serpapi_payload(
    monkeypatch,
) -> None:
    async def fake_search_results(
        provider: str, query: str, *, limit: int | None = None
    ) -> list[SearchResult]:
        return [
            SearchResult(
                url="https://www.levi.com/p/04511.html",
                payload={
                    "provider": "serpapi",
                    "title": "Levi's 511 Slim Fit Jeans",
                    "snippet": "Official product page",
                },
            )
        ]

    monkeypatch.setattr(
        "app.services.product_intelligence.discovery._search_results",
        fake_search_results,
    )

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
        max_candidates=1,
    )

    assert candidates[0].payload["provider"] == "serpapi"
    assert candidates[0].payload["snippet"] == "Official product page"


@pytest.mark.component
def test_product_intelligence_parses_serpapi_shopping_payload() -> None:
    results = parse_serpapi_shopping_results(
        {
            "shopping_results": [
                {
                    "position": 1,
                    "title": "Crown & Ivy Floral Midi Dress",
                    "source": "Belk",
                    "link": "https://www.example.com/p/crown-ivy-floral-midi-dress/123.html",
                    "product_id": "987654321",
                    "product_link": "https://www.google.com/search?ibp=oshop&q=dress",
                    "serpapi_immersive_product_api": "https://serpapi.com/search.json?engine=google_immersive_product&page_token=abc",
                    "price": "$49.99",
                    "extracted_price": 49.99,
                    "thumbnail": "https://example.com/image.jpg",
                    "rating": 4.8,
                    "reviews": 27,
                    "delivery": "Free delivery",
                }
            ]
        }
    )

    assert (
        results[0].url
        == "https://www.example.com/p/crown-ivy-floral-midi-dress/123.html"
    )
    assert results[0].payload["provider"] == "serpapi_shopping"
    assert results[0].payload["product_id"] == "987654321"
    assert results[0].payload["extracted_price"] == pytest.approx(49.99)
    assert results[0].payload["thumbnail"] == "https://example.com/image.jpg"


@pytest.mark.component
def test_product_intelligence_parses_serpapi_immersive_store_links() -> None:
    results = parse_serpapi_immersive_results(
        {
            "product_results": {
                "title": "Levi's 511 Slim Fit Jeans",
                "product_id": "immersive-product-id",
                "description": "Slim fit jeans.",
                "thumbnails": ["https://example.com/image.jpg"],
                "stores": [
                    {
                        "name": "Levi's",
                        "title": "Levi's 511 Slim Fit Jeans",
                        "link": "https://www.levi.com/p/04511.html",
                        "price": "$69.50",
                        "extracted_price": 69.5,
                        "shipping": "Free shipping",
                    }
                ],
            }
        },
        parent={
            "product_id": "shopping-product-id",
            "product_link": "https://www.google.com/search?ibp=oshop&q=levi",
        },
        limit=5,
    )

    assert results[0].url == "https://www.levi.com/p/04511.html"
    assert results[0].payload["provider"] == "serpapi_immersive"
    assert results[0].payload["product_id"] == "immersive-product-id"
    assert (
        results[0].payload["product_link"]
        == "https://www.google.com/search?ibp=oshop&q=levi"
    )
    assert results[0].payload["extracted_price"] == pytest.approx(69.5)


@pytest.mark.asyncio
@pytest.mark.component
async def test_product_intelligence_serpapi_searches_brand_organic_then_shopping(
    monkeypatch,
) -> None:
    engines: list[str] = []
    queries: list[str] = []

    async def fake_engine(
        query: str, *, engine: str, limit: int | None = None
    ) -> dict[str, object]:
        del limit
        engines.append(engine)
        queries.append(query)
        if engine == "google_shopping":
            return {
                "shopping_results": [
                    {
                        "position": 1,
                        "title": "Levi's 511 Slim Fit Jeans",
                        "source": "Levi's",
                        "link": "https://www.levi.com/p/04511.html",
                        "product_id": "shopping-product-id",
                    }
                ]
            }
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

    monkeypatch.setattr(discovery_module, "_search_serpapi_engine", fake_engine)

    results = await discovery_module._search_serpapi(
        "levi 511 site:levi.com",
        limit=5,
    )

    assert set(engines) == {"google_shopping", "google"}
    assert sorted(queries) == [
        "levi 511",
        "levi 511 site:levi.com",
    ]
    assert [result.payload["provider"] for result in results] == ["serpapi"]
    assert results[0].url == "https://www.levi.com/p/04511.html"

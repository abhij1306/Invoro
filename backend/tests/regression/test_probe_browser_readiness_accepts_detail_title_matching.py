from __future__ import annotations

from .test_browser_expansion_runtime import SimpleNamespace, _FakeExpansionPage, _FakeHandle, _FakeRuntime, _async_checkpoint, browser_capture, browser_detail, browser_page_helpers, browser_readiness, browser_recovery, browser_runtime, pytest  # fmt: skip

@pytest.mark.asyncio
@pytest.mark.regression
async def test_probe_browser_readiness_accepts_detail_title_matching_url() -> None:
    visible_text = (
        "This vintage bracelet is crafted in 18-karat gold with coral cabochons "
        "and diamond accents. The product page includes condition notes, "
        "shipping information, returns, and authenticated packaging details."
    )
    probe = await browser_readiness.probe_browser_readiness_impl(
        object(),
        url=(
            "https://www.net-a-porter.com/en-us/shop/product/eleuteri/"
            "jewelry-and-watches/vintage-bracelets/"
            "plus-bulgari-vintage-1980s-doppio-cuore-18-karat-gold-coral-and-diamond-bracelet/"
            "46376663163120086"
        ),
        surface="ecommerce_detail",
        html=(
            "<html><head><title>ELEUTERI + Bulgari Vintage 1980s Doppio Cuore "
            "18-karat gold, coral and diamond bracelet | NET-A-PORTER</title></head>"
            f"<body><main><p>{visible_text}</p></main></body></html>"
        ),
        detail_readiness_hint_count=browser_readiness.detail_readiness_hint_count,
    )

    assert probe["is_ready"] is True
    assert probe["detail_title_matches_url"] is True

@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_bounds_response_capture_workers_under_burst_load(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeResponse:
        def __init__(self, index: int) -> None:
            self.url = f"https://example.com/api/{index}"
            self.headers = {"content-type": "application/json"}
            self.request = SimpleNamespace(method="GET")
            self.status = 200

    page = _FakeExpansionPage(
        base_html="<html><body><h1>Widget Prime</h1></body></html>",
        response_events=[_FakeResponse(index) for index in range(200)],
    )

    async def _fake_runtime(**_kwargs):
        await _async_checkpoint()
        return _FakeRuntime(page)

    async def _fake_read_network_payload_body(response, **_kwargs):
        await _async_checkpoint()
        return browser_runtime.NetworkPayloadReadResult(
            body=f'{{"id": "{response.url}"}}'.encode("utf-8"),
            outcome="ok",
        )

    create_task_calls = 0
    original_create_task = browser_capture.asyncio.create_task

    def _counting_create_task(coro):
        nonlocal create_task_calls
        code = getattr(coro, "cr_code", None)
        if getattr(code, "co_name", "") == "_capture_worker":
            create_task_calls += 1
        return original_create_task(coro)

    monkeypatch.setattr(browser_capture.asyncio, "create_task", _counting_create_task)
    monkeypatch.setattr(
        browser_runtime,
        "should_capture_network_payload",
        lambda **kwargs: True,
    )
    monkeypatch.setattr(
        browser_runtime,
        "read_network_payload_body",
        _fake_read_network_payload_body,
    )
    monkeypatch.setattr(
        browser_runtime,
        "classify_network_endpoint",
        lambda **kwargs: {"type": "api", "family": "generic"},
    )

    result = await browser_runtime.browser_fetch(
        "https://example.com/products/widget",
        5,
        surface="ecommerce_detail",
        runtime_provider=_fake_runtime,
    )

    assert create_task_calls == browser_runtime.BROWSER_CAPTURE_WORKERS
    assert (
        len(result.network_payloads)
        == browser_runtime.BROWSER_CAPTURE_MAX_NETWORK_PAYLOADS
    )
    assert (
        result.browser_diagnostics["dropped_network_payload_events"]
        >= 200 - browser_runtime.BROWSER_CAPTURE_QUEUE_SIZE
    )

@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_expands_detail_accordions_before_collecting_html() -> None:
    page = _FakeExpansionPage(
        base_html="<html><body><details><summary>Specifications</summary></details></body></html>",
        expanded_html="""
        <html><body>
          <details open><summary>Specifications</summary>
            <div class="product-features">Rubber outsole, reinforced toe cap.</div>
          </details>
        </body></html>
        """,
        labels=[{"label": "product specifications"}, {"label": "share"}],
    )

    async def _fake_runtime(**_kwargs):
        await _async_checkpoint()
        return _FakeRuntime(page)

    result = await browser_runtime.browser_fetch(
        "https://example.com/products/widget",
        5,
        surface="ecommerce_detail",
        runtime_provider=_fake_runtime,
    )

    assert "Rubber outsole" in result.html
    assert result.browser_diagnostics["detail_expansion"]["clicked_count"] == 1
    assert result.browser_diagnostics["detail_expansion"]["expanded_elements"] == [
        "product specifications"
    ]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_expands_requested_field_sections_even_when_probe_is_ready() -> (
    None
):
    page = _FakeExpansionPage(
        base_html="<html><body><h1>Widget Prime</h1><button>Materials</button></body></html>",
        expanded_html="""
        <html><body>
          <h1>Widget Prime</h1>
          <button aria-controls="materials-panel">Materials</button>
          <section id="materials-panel">Full-grain leather upper.</section>
        </body></html>
        """,
        labels=[
            {
                "label": "materials",
                "attributes": {"aria-controls": "materials-panel"},
            }
        ],
    )

    async def _fake_runtime(**_kwargs):
        await _async_checkpoint()
        return _FakeRuntime(page)

    result = await browser_runtime.browser_fetch(
        "https://example.com/products/widget",
        5,
        surface="ecommerce_detail",
        requested_fields=["materials"],
        runtime_provider=_fake_runtime,
    )

    assert "Full-grain leather upper." in result.html
    assert result.browser_diagnostics["detail_expansion"]["clicked_count"] == 1

@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_skips_detail_expansion_when_requested_section_is_already_extractable() -> (
    None
):
    page = _FakeExpansionPage(
        base_html="""
        <html><body>
          <h1>Widget Prime</h1>
          <section>
            <h2>FEATURES &amp; BENEFITS</h2>
            <p>Responsive foam and carbon plate propulsion.</p>
          </section>
        </body></html>
        """,
        labels=[
            {
                "label": "new",
                "attributes": {"aria-controls": "nav-new"},
            }
        ],
    )

    async def _fake_runtime(**_kwargs):
        await _async_checkpoint()
        return _FakeRuntime(page)

    result = await browser_runtime.browser_fetch(
        "https://example.com/products/widget",
        5,
        surface="ecommerce_detail",
        requested_fields=["Features & Benefits"],
        runtime_provider=_fake_runtime,
    )

    assert "Responsive foam and carbon plate propulsion." in result.html
    assert result.browser_diagnostics["detail_expansion"]["clicked_count"] == 0
    assert (
        result.browser_diagnostics["detail_expansion"]["reason"]
        == "requested_content_already_extractable"
    )

@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_expands_requested_dom_pattern_content_without_heading_sections() -> (
    None
):
    page = _FakeExpansionPage(
        base_html="""
        <html><body>
          <main>
            <h1>Widget Prime</h1>
            <button aria-controls="materials-panel">Materials</button>
            <div id="materials-panel">
              <div class="material-composition">Full-grain leather upper.</div>
            </div>
          </main>
        </body></html>
        """,
    )

    async def _fake_runtime(**_kwargs):
        await _async_checkpoint()
        return _FakeRuntime(page)

    result = await browser_runtime.browser_fetch(
        "https://example.com/products/widget",
        5,
        surface="ecommerce_detail",
        requested_fields=["materials"],
        runtime_provider=_fake_runtime,
    )

    assert result.browser_diagnostics["detail_expansion"]["clicked_count"] == 0
    assert (
        result.browser_diagnostics["detail_expansion"]["reason"]
        == "requested_content_already_extractable"
    )
    assert result.browser_diagnostics["detail_expansion"]["extractability"][
        "matched_requested_fields"
    ] == ["materials"]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_expand_detail_content_if_needed_skips_aom_when_page_is_already_ready(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _unexpected_aom(*args, **kwargs):
        await _async_checkpoint()
        raise AssertionError("AOM expansion should be skipped")

    monkeypatch.setattr(
        browser_runtime,
        "expand_interactive_elements_via_accessibility",
        _unexpected_aom,
    )

    diagnostics = await browser_runtime.expand_detail_content_if_needed(
        _FakeExpansionPage(base_html="<html><body><h1>Widget Prime</h1></body></html>"),
        surface="ecommerce_detail",
        readiness_probe={"is_ready": True, "detail_like": True},
    )

    assert diagnostics["status"] == "attempted"
    assert diagnostics["reason"] == "missing_detail_content"
    assert diagnostics["clicked_count"] == 0
    assert diagnostics["aom"]["status"] == "skipped"
    assert diagnostics["aom"]["reason"] == "not_needed"

@pytest.mark.regression
def test_accessibility_expand_candidates_ignores_navigation_roles() -> None:
    candidates = browser_detail.accessibility_expand_candidates(
        {
            "role": "document",
            "children": [
                {"role": "link", "name": "Product details"},
                {"role": "menuitem", "name": "Materials"},
                {"role": "button", "name": "Product details"},
            ],
        },
        surface="ecommerce_detail",
    )

    assert candidates == [("button", "product details")]

@pytest.mark.regression
def test_finish_expansion_diagnostics_marks_attempt_without_clicks_as_no_matches() -> (
    None
):
    diagnostics = browser_detail._finish_expansion_diagnostics(
        {"status": "attempted"},
        clicked_count=0,
        expanded_elements=[],
        interaction_failures=[],
        started_at=0.0,
        elapsed_ms=lambda _started_at: 0,
    )

    assert diagnostics["status"] == "no_matches"

@pytest.mark.regression
def test_finish_expansion_diagnostics_marks_attempt_failures_as_interaction_failed() -> (
    None
):
    diagnostics = browser_detail._finish_expansion_diagnostics(
        {"status": "attempted"},
        clicked_count=0,
        expanded_elements=[],
        interaction_failures=["click_failed:size"],
        started_at=0.0,
        elapsed_ms=lambda _started_at: 7,
    )

    assert diagnostics["status"] == "interaction_failed"
    assert diagnostics["interaction_failures"] == ["click_failed:size"]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_expand_all_interactive_elements_skips_blocked_commerce_actions() -> None:
    page = _FakeExpansionPage(
        base_html="<html><body></body></html>",
        labels=[
            {"label": "add to cart"},
            {
                "label": "materials",
                "attributes": {"aria-controls": "materials-panel"},
            },
        ],
    )

    diagnostics = await browser_runtime.expand_all_interactive_elements(
        page,
        surface="ecommerce_detail",
        requested_fields=["materials"],
    )

    assert diagnostics["clicked_count"] == 1
    assert diagnostics["expanded_elements"] == ["materials"]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_expand_all_interactive_elements_skips_blocked_label_tokens_without_requested_fields() -> (
    None
):
    page = _FakeExpansionPage(
        base_html="<html><body></body></html>",
        labels=[
            {
                "label": "Auto-Replenish Save 5% on this item",
                "attributes": {"aria-controls": "auto-replenish-panel"},
            },
            {
                "label": "Product details",
                "attributes": {"aria-controls": "details-panel"},
            },
        ],
    )

    diagnostics = await browser_runtime.expand_all_interactive_elements(
        page,
        surface="ecommerce_detail",
        requested_fields=[],
    )

    assert diagnostics["clicked_count"] == 1
    assert diagnostics["expanded_elements"] == ["product details"]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_expand_all_interactive_elements_scans_past_non_expandable_early_candidates() -> (
    None
):
    page = _FakeExpansionPage(
        base_html="<html><body></body></html>",
        labels=[
            {"label": "add to cart"},
            {"label": "materials", "actionable": False},
            {
                "label": "materials",
                "attributes": {"aria-controls": "materials-panel"},
            },
        ],
    )

    diagnostics = await browser_runtime.expand_all_interactive_elements(
        page,
        surface="ecommerce_detail",
        requested_fields=["materials"],
    )

    assert diagnostics["clicked_count"] == 1
    assert diagnostics["expanded_elements"] == ["materials"]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_flattens_shadow_dom_before_serializing_html() -> None:
    page = _FakeExpansionPage(
        base_html="<html><body><shop-product></shop-product></body></html>",
        shadow_html=(
            "<html><body><shop-product></shop-product>"
            "<section class='specifications'>Shadow DOM specifications</section>"
            "</body></html>"
        ),
    )

    async def _fake_runtime(**_kwargs):
        await _async_checkpoint()
        return _FakeRuntime(page)

    result = await browser_runtime.browser_fetch(
        "https://example.com/products/widget",
        5,
        surface="ecommerce_detail",
        runtime_provider=_fake_runtime,
    )

    assert page.shadow_flattened is True
    assert "Shadow DOM specifications" in result.html

@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_keeps_markdown_removed() -> None:
    page = _FakeExpansionPage(
        base_html="""
        <html>
          <body>
            <header>Brand header</header>
            <main>
              <h1>Widget Prime</h1>
              <p>Built for long mileage.</p>
              <a href="/products/widget/specs">View specs</a>
            </main>
          </body>
        </html>
        """,
    )

    async def _fake_runtime(**_kwargs):
        await _async_checkpoint()
        return _FakeRuntime(page)

    result = await browser_runtime.browser_fetch(
        "https://example.com/products/widget",
        5,
        surface="ecommerce_detail",
        runtime_provider=_fake_runtime,
    )

    assert hasattr(result, "page_markdown") is False

@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_captures_rendered_listing_fragments_artifact() -> None:
    page = _FakeExpansionPage(
        base_html="""
        <html>
          <body>
            <article class="product-card">
              <a href="/products/widget-prime"><h2>Widget Prime</h2></a>
              <div class="price">$19.99</div>
              <img src="/images/widget-prime.jpg" alt="Widget Prime" />
            </article>
          </body>
        </html>
        """,
        rendered_listing_fragments=[
            """
            <article class="product-card">
              <a href="/products/widget-prime"><h2>Widget Prime</h2></a>
              <div class="price">$19.99</div>
              <img src="/images/widget-prime.jpg" alt="Widget Prime" />
            </article>
            """
        ],
    )

    async def _fake_runtime(**_kwargs):
        await _async_checkpoint()
        return _FakeRuntime(page)

    result = await browser_runtime.browser_fetch(
        "https://example.com/collections/widgets",
        5,
        surface="ecommerce_listing",
        runtime_provider=_fake_runtime,
    )

    assert result.artifacts["rendered_listing_fragments"] == [
        """
            <article class="product-card">
              <a href="/products/widget-prime"><h2>Widget Prime</h2></a>
              <div class="price">$19.99</div>
              <img src="/images/widget-prime.jpg" alt="Widget Prime" />
            </article>
            """.strip()
    ]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_ignores_non_string_rendered_listing_fragments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = _FakeExpansionPage(
        base_html="<html><body><article><a href='/products/widget'>Widget</a></article></body></html>",
        selector_counts={".product-card": 1},
        card_count=1,
    )
    page.url = "https://example.com/collections/widgets"

    async def _fake_runtime(**_kwargs):
        await _async_checkpoint()
        return _FakeRuntime(page)

    async def _bad_fragments(*args, **kwargs):
        await _async_checkpoint()
        del args, kwargs
        return [123, {"html": "<article>bad</article>"}, " <article>good</article> "]

    monkeypatch.setattr(
        browser_recovery, "capture_rendered_listing_fragments", _bad_fragments
    )

    result = await browser_runtime.browser_fetch(
        "https://example.com/collections/widgets",
        5,
        surface="ecommerce_listing",
        runtime_provider=_fake_runtime,
    )

    assert result.artifacts["rendered_listing_fragments"] == ["<article>good</article>"]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_keeps_empty_successful_listing_artifacts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = _FakeExpansionPage(
        base_html="<html><body><article><a href='/products/widget'>Widget</a></article></body></html>",
        selector_counts={".product-card": 1},
        card_count=1,
    )
    page.url = "https://example.com/collections/widgets"

    async def _fake_runtime(**_kwargs):
        await _async_checkpoint()
        return _FakeRuntime(page)

    async def _empty_fragments(*args, **kwargs):
        await _async_checkpoint()
        del args, kwargs
        return []

    async def _empty_visuals(*args, **kwargs):
        await _async_checkpoint()
        del args, kwargs
        return []

    monkeypatch.setattr(
        browser_recovery, "capture_rendered_listing_fragments", _empty_fragments
    )
    monkeypatch.setattr(
        browser_page_helpers, "capture_listing_visual_elements", _empty_visuals
    )

    result = await browser_runtime.browser_fetch(
        "https://example.com/collections/widgets",
        5,
        surface="ecommerce_listing",
        runtime_provider=_fake_runtime,
    )

    assert result.artifacts["rendered_listing_fragments"] == []
    assert result.artifacts["listing_visual_elements"] == []

@pytest.mark.asyncio
@pytest.mark.regression
async def test_detail_expansion_keywords_include_ecommerce_fallbacks_without_requested_fields() -> (
    None
):
    await _async_checkpoint()
    default_keywords = browser_runtime.detail_expansion_keywords("ecommerce_detail")
    requested_keywords = browser_runtime.detail_expansion_keywords(
        "ecommerce_detail",
        requested_fields=["description"],
    )

    assert "shipping" in default_keywords
    assert "shipping" in requested_keywords

@pytest.mark.asyncio
@pytest.mark.regression
async def test_interactive_candidate_snapshot_excludes_class_names_from_probe() -> None:
    page = _FakeExpansionPage(base_html="<html><body></body></html>")
    handle = _FakeHandle(
        "Care instructions",
        page,
        attributes={
            "class": "btn btn--size-selector utility-token",
            "data-testid": "care-panel-toggle",
        },
    )

    snapshot = await browser_runtime.interactive_candidate_snapshot(handle)

    assert snapshot["class_name"] == "btn btn--size-selector utility-token"
    assert "utility-token" not in str(snapshot["probe"])
    assert "care-panel-toggle" in str(snapshot["probe"])

@pytest.mark.regression
def test_acquisition_package_exports_interactive_candidate_snapshot() -> None:
    from app.services import acquisition

    assert (
        acquisition.interactive_candidate_snapshot
        is browser_runtime.interactive_candidate_snapshot
    )

@pytest.mark.asyncio
@pytest.mark.regression
async def test_expand_all_interactive_elements_matches_keywords_from_class_names() -> (
    None
):
    page = _FakeExpansionPage(
        base_html="<html><body></body></html>",
        labels=[
            {
                "label": "",
                "attributes": {"class": "accordion materials-panel-toggle"},
            }
        ],
    )

    diagnostics = await browser_runtime.expand_all_interactive_elements(
        page,
        surface="ecommerce_detail",
    )

    assert diagnostics["clicked_count"] == 1

@pytest.mark.asyncio
@pytest.mark.regression
async def test_expand_all_interactive_elements_allows_relevant_footer_controls() -> (
    None
):
    page = _FakeExpansionPage(
        base_html="<html><body></body></html>",
        labels=[
            {
                "label": "Main menu",
                "attributes": {"aria-controls": "site-menu"},
                "inside_footer": True,
            },
            {
                "label": "Size guide",
                "attributes": {"aria-controls": "size-panel"},
                "inside_footer": True,
            },
        ],
    )

    diagnostics = await browser_runtime.expand_all_interactive_elements(
        page,
        surface="ecommerce_detail",
        requested_fields=["size"],
    )

    assert diagnostics["clicked_count"] == 1
    assert diagnostics["expanded_elements"] == ["size guide"]

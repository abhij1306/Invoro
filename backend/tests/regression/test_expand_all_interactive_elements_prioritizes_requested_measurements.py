from __future__ import annotations

from .test_browser_expansion_runtime import SimpleNamespace, _FakeExpansionPage, _FakeHandle, _FakeRuntime, _async_checkpoint, browser_detail, browser_page_flow, browser_result_builder, browser_runtime, extract_records, httpx, pytest  # fmt: skip

pytest_plugins = ["tests.regression.test_browser_expansion_runtime"]


@pytest.mark.asyncio
@pytest.mark.regression
async def test_expand_all_interactive_elements_prioritizes_requested_measurements_over_media_zoom() -> (
    None
):
    page = _FakeExpansionPage(
        base_html="<html><body></body></html>",
        labels=[
            {
                "label": "enlarge image rustic t-shirt",
                "attributes": {
                    "aria-label": "Enlarge image rustic t-shirt",
                    "data-qa-action": "media-zoom",
                    "class": "product-detail-image product-detail-view__main-image",
                },
                "tag_name": "button",
            },
            {
                "label": "product measurements",
                "attributes": {
                    "class": "product-detail-actions__action-button",
                    "data-qa-action": "open-interactive-size-guide-accordion",
                },
                "tag_name": "button",
            },
        ],
    )

    diagnostics = await browser_runtime.expand_all_interactive_elements(
        page,
        surface="ecommerce_detail",
        requested_fields=["product measurements"],
    )

    assert diagnostics["clicked_count"] == 1
    assert diagnostics["expanded_elements"] == ["product measurements"]


@pytest.mark.asyncio
@pytest.mark.regression
async def test_expand_all_interactive_elements_allows_visible_generic_detail_toggle_for_requested_fields() -> (
    None
):
    page = _FakeExpansionPage(
        base_html="<html><body></body></html>",
        labels=[
            {
                "label": "details",
                "attributes": {"aria-controls": "details-panel"},
                "tag_name": "button",
            }
        ],
    )

    diagnostics = await browser_runtime.expand_all_interactive_elements(
        page,
        surface="ecommerce_detail",
        requested_fields=["materials"],
    )

    assert diagnostics["clicked_count"] == 1
    assert diagnostics["expanded_elements"] == ["details"]


@pytest.mark.asyncio
@pytest.mark.regression
async def test_expand_detail_content_if_needed_attempts_generic_ecommerce_expansion_when_ready() -> (
    None
):
    page = _FakeExpansionPage(
        base_html="<html><body></body></html>",
        labels=[
            {
                "label": "shipping and returns",
                "attributes": {"aria-controls": "shipping-panel"},
                "tag_name": "button",
            }
        ],
    )

    diagnostics = await browser_runtime.expand_detail_content_if_needed(
        page,
        surface="ecommerce_detail",
        readiness_probe={"is_ready": True, "detail_like": True},
    )

    assert diagnostics["clicked_count"] == 1
    assert page.expanded is True


@pytest.mark.asyncio
@pytest.mark.regression
async def test_expand_detail_content_if_needed_attempts_ready_job_detail_without_requested_fields() -> (
    None
):
    page = _FakeExpansionPage(
        base_html="<html><body></body></html>",
        labels=[
            {
                "label": "responsibilities",
                "attributes": {"aria-controls": "responsibilities-panel"},
                "tag_name": "button",
            }
        ],
    )

    diagnostics = await browser_runtime.expand_detail_content_if_needed(
        page,
        surface="job_detail",
        readiness_probe={"is_ready": True, "detail_like": True},
    )

    assert diagnostics["clicked_count"] == 1
    assert page.expanded is True


@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_records_extractable_sections_after_detail_expansion() -> (
    None
):
    page = _FakeExpansionPage(
        base_html="<html><body><h1>Widget Prime</h1><button>Materials</button></body></html>",
        expanded_html="""
        <html><body>
          <h1>Widget Prime</h1>
          <div class="accordion-item">
            <button>Materials</button>
            <div class="accordion-item__body">
              <div class="rich-content">Full-grain leather upper.</div>
            </div>
          </div>
        </body></html>
        """,
        labels=[{"label": "materials"}],
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

    extractability = result.browser_diagnostics["detail_expansion"]["extractability"]

    assert extractability["verified"] is True
    assert extractability["matched_requested_fields"] == ["materials"]


@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_does_not_skip_requested_dom_pattern_when_selector_is_empty() -> (
    None
):
    page = _FakeExpansionPage(
        base_html="""
        <html><body>
          <main>
            <h1>Widget Prime</h1>
            <button aria-controls="specs-panel">Specifications</button>
            <div class="specifications"></div>
          </main>
        </body></html>
        """,
        expanded_html="""
        <html><body>
          <main>
            <h1>Widget Prime</h1>
            <button aria-controls="specs-panel">Specifications</button>
            <div class="specifications">Weight: 2kg</div>
          </main>
        </body></html>
        """,
        labels=[
            {
                "label": "specifications",
                "attributes": {"aria-controls": "specs-panel"},
                "tag_name": "button",
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
        requested_fields=["specifications"],
        runtime_provider=_fake_runtime,
    )

    assert result.browser_diagnostics["detail_expansion"]["clicked_count"] == 1
    assert "Weight: 2kg" in result.html


@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_extracts_requested_features_from_dell_like_tab() -> None:
    page = _FakeExpansionPage(
        base_html="""
        <html><body>
          <main>
            <h1>Dell 27 All-in-One</h1>
            <section>
              <h2>Description</h2>
              <p>27-inch all-in-one desktop.</p>
            </section>
            <a href="#tech">Tech Specs</a>
            <a href="#features_section">Features &amp; Design</a>
          </main>
        </body></html>
        """,
        expanded_html="""
        <html><body>
          <main>
            <h1>Dell 27 All-in-One</h1>
            <section>
              <h2>Description</h2>
              <p>27-inch all-in-one desktop.</p>
            </section>
            <a href="#tech">Tech Specs</a>
            <div id="tech">
              <p>Memory: 16 GB DDR5</p>
            </div>
            <a href="#features_section">Features &amp; Design</a>
            <div id="features_section">
              <p>13th Generation Intel® Core™ i5-1334U</p>
              <p>27-inch FHD Infinity display</p>
            </div>
          </main>
        </body></html>
        """,
        labels=[
            {
                "label": "tech specs",
                "attributes": {"href": "#tech"},
                "tag_name": "a",
            },
            {
                "label": "features & design",
                "attributes": {"href": "#features_section"},
                "tag_name": "a",
            },
        ],
    )

    async def _fake_runtime(**_kwargs):
        await _async_checkpoint()
        return _FakeRuntime(page)

    result = await browser_runtime.browser_fetch(
        "https://example.com/products/widget",
        5,
        surface="ecommerce_detail",
        requested_fields=["features"],
        runtime_provider=_fake_runtime,
    )

    rows = extract_records(
        result.html,
        "https://example.com/products/widget",
        "ecommerce_detail",
        max_records=1,
        requested_fields=["features"],
    )

    assert result.browser_diagnostics["detail_expansion"]["clicked_count"] >= 1
    assert result.browser_diagnostics["detail_expansion"]["expanded_elements"][0] == (
        "features & design"
    )
    assert rows[0]["features"] == [
        "13th Generation Intel® Core™ i5-1334U",
        "27-inch FHD Infinity display",
    ]


@pytest.mark.asyncio
@pytest.mark.regression
async def test_expand_detail_content_uses_data_qa_action_to_open_size_selector() -> (
    None
):
    page = _FakeExpansionPage(
        base_html="<html><body><button aria-label='Add to bag'>Add</button></body></html>",
        labels=[
            {
                "label": "add",
                "attributes": {
                    "aria-label": "Add to bag",
                    "data-qa-action": "product-grid-open-size-selector",
                },
                "tag_name": "button",
            }
        ],
    )

    diagnostics = await browser_runtime.expand_all_interactive_elements(
        page,
        surface="ecommerce_detail",
        requested_fields=None,
    )

    assert diagnostics["clicked_count"] == 1
    assert page.expanded is True


@pytest.mark.asyncio
@pytest.mark.regression
async def test_expand_detail_content_skips_menu_toggles() -> None:
    page = _FakeExpansionPage(
        base_html="<html><body><button aria-controls='site-menu'>Open menu</button></body></html>",
        labels=[
            {
                "label": "open menu",
                "attributes": {
                    "aria-controls": "site-menu",
                },
                "tag_name": "button",
            }
        ],
    )

    diagnostics = await browser_runtime.expand_all_interactive_elements(
        page,
        surface="ecommerce_detail",
        requested_fields=["materials"],
    )

    assert diagnostics["clicked_count"] == 0
    assert page.expanded is False


@pytest.mark.asyncio
@pytest.mark.regression
async def test_expand_detail_content_prefers_requested_section_labels_over_unrelated_nav() -> (
    None
):
    page = _FakeExpansionPage(
        base_html="""
        <html><body>
          <button aria-controls='nav-new'>New</button>
          <button aria-controls='nav-men'>Men</button>
          <button aria-controls='details-panel'>Details</button>
        </body></html>
        """,
        labels=[
            {
                "label": "new",
                "attributes": {"aria-controls": "nav-new"},
                "tag_name": "button",
            },
            {
                "label": "men",
                "attributes": {"aria-controls": "nav-men"},
                "tag_name": "button",
            },
            {
                "label": "details",
                "attributes": {"aria-controls": "details-panel"},
                "tag_name": "button",
            },
        ],
    )

    diagnostics = await browser_runtime.expand_all_interactive_elements(
        page,
        surface="ecommerce_detail",
        requested_fields=["Details"],
    )

    assert diagnostics["clicked_count"] == 1
    assert diagnostics["expanded_elements"] == ["details"]
    assert page.expanded is True


@pytest.mark.asyncio
@pytest.mark.regression
async def test_expand_detail_content_skips_navigation_anchors_that_match_generic_keywords() -> (
    None
):
    page = _FakeExpansionPage(
        base_html="""
        <html><body>
          <a href="/returns-and-refunds">Returns &amp; refunds</a>
          <a href="/about-us">About us</a>
          <a href="/careers">Careers</a>
        </body></html>
        """,
        labels=[
            {
                "label": "returns & refunds",
                "attributes": {"href": "/returns-and-refunds"},
                "tag_name": "a",
            },
            {
                "label": "about us",
                "attributes": {"href": "/about-us"},
                "tag_name": "a",
            },
            {
                "label": "careers",
                "attributes": {"href": "/careers"},
                "tag_name": "a",
            },
        ],
    )

    diagnostics = await browser_runtime.expand_all_interactive_elements(
        page,
        surface="ecommerce_detail",
        requested_fields=["title", "size", "availability"],
    )

    assert diagnostics["clicked_count"] == 0
    assert page.expanded is False


@pytest.mark.asyncio
@pytest.mark.regression
async def test_expand_detail_content_skips_header_controls_outside_main_content() -> (
    None
):
    page = _FakeExpansionPage(
        base_html="""
        <html><body>
          <header><button aria-controls='about-panel'>About</button></header>
          <main><button aria-controls='details-panel'>Details</button></main>
        </body></html>
        """,
        labels=[
            {
                "label": "about",
                "attributes": {"aria-controls": "about-panel"},
                "tag_name": "button",
                "inside_header": True,
            },
            {
                "label": "details",
                "attributes": {"aria-controls": "details-panel"},
                "tag_name": "button",
                "inside_main": True,
            },
        ],
    )

    diagnostics = await browser_runtime.expand_all_interactive_elements(
        page,
        surface="ecommerce_detail",
        requested_fields=None,
    )

    assert diagnostics["clicked_count"] == 1
    assert diagnostics["expanded_elements"] == ["details"]
    assert page.expanded is True


@pytest.mark.asyncio
@pytest.mark.regression
async def test_expand_detail_content_does_not_match_requested_keywords_from_hidden_probe_only() -> (
    None
):
    page = _FakeExpansionPage(
        base_html="<html><body><button aria-controls='lifestyle-panel'>Lifestyle</button></body></html>",
        labels=[
            {
                "label": "lifestyle",
                "probe": "details drawer",
                "attributes": {"aria-controls": "lifestyle-panel"},
                "tag_name": "button",
            }
        ],
    )

    diagnostics = await browser_runtime.expand_all_interactive_elements(
        page,
        surface="ecommerce_detail",
        requested_fields=["Details"],
    )

    assert diagnostics["clicked_count"] == 0
    assert page.expanded is False


@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_waits_for_challenge_recovery_before_settling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    page = _FakeExpansionPage(
        base_html="<html><body><div>challenge</div></body></html>",
        wait_html_sequence=["<html><body><h1>Widget Prime</h1></body></html>"],
        cookie_snapshots=[[], [{"name": "_abck"}]],
    )
    calls = {"count": 0}

    async def _fake_classify_blocked_page_async(_html: str, _status: int):
        await _async_checkpoint()
        calls["count"] += 1
        blocked = calls["count"] == 1
        return SimpleNamespace(
            blocked=blocked,
            outcome="challenge_page" if blocked else "ok",
            evidence=["provider:akamai"] if blocked else [],
            provider_hits=["akamai"] if blocked else [],
            active_provider_hits=[],
            strong_hits=[],
            weak_hits=[],
            title_matches=[],
            challenge_element_hits=[],
        )

    async def _fake_runtime(**_kwargs):
        await _async_checkpoint()
        return _FakeRuntime(page)

    monkeypatch.setattr(
        browser_page_flow,
        "classify_blocked_page_async",
        _fake_classify_blocked_page_async,
    )

    result = await browser_runtime.browser_fetch(
        "https://example.com/products/widget",
        5,
        surface="ecommerce_detail",
        runtime_provider=_fake_runtime,
    )

    assert "Widget Prime" in result.html
    assert page.wait_function_calls
    assert page.goto_calls == ["domcontentloaded"]
    assert page.load_state_calls == ["networkidle"]


@pytest.mark.asyncio
@pytest.mark.regression
async def test_finalize_browser_fetch_keeps_blocked_html_checker_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_capture_close(_page):
        await _async_checkpoint()
        return SimpleNamespace(
            payloads=[],
            network_payload_count=0,
            malformed_network_payloads=0,
            network_payload_read_failures=0,
            network_payload_read_timeouts=0,
            closed_network_payloads=0,
            skipped_oversized_network_payloads=0,
            dropped_payload_events=0,
        )

    async def _fake_capture_fragments(*_args, **_kwargs):
        await _async_checkpoint()
        return []

    async def _fake_capture_visuals(*_args, **_kwargs):
        await _async_checkpoint()
        return []

    async def _fake_classify_blocked_page_async(_html: str, _status: int):
        await _async_checkpoint()
        return SimpleNamespace(blocked=False, outcome="ok", evidence=[])

    async def _fake_emit_browser_event(*_args, **_kwargs):
        await _async_checkpoint()
        return None

    payload = browser_result_builder.BrowserFinalizeInput(
        page=SimpleNamespace(url="https://example.com/products/widget"),
        url="https://example.com/products/widget",
        surface="ecommerce_detail",
        browser_reason=None,
        on_event=None,
        response=SimpleNamespace(
            status=200, headers=httpx.Headers({"content-type": "text/html"})
        ),
        navigation_strategy="goto",
        readiness_probes=[],
        networkidle_timed_out=False,
        networkidle_skip_reason=None,
        readiness_policy={},
        readiness_diagnostics={},
        expansion_diagnostics={},
        listing_recovery_diagnostics={},
        payload_capture=SimpleNamespace(close=_fake_capture_close),
        html="<html><body><h1>Widget Prime</h1></body></html>",
        traversal_result=None,
        rendered_html="",
        phase_timings_ms={},
        started_at=0.0,
    )

    result = await browser_result_builder.finalize_browser_fetch(
        payload,
        blocked_html_checker=lambda *_args, **_kwargs: True,
        classify_blocked_page_async=_fake_classify_blocked_page_async,
        classify_low_content_reason=lambda *_args, **_kwargs: None,
        classify_browser_outcome=lambda **kwargs: (
            "challenge_page" if kwargs["blocked"] else "usable_content"
        ),
        capture_browser_screenshot=_fake_emit_browser_event,
        emit_browser_event=_fake_emit_browser_event,
        elapsed_ms=lambda _started_at: 0,
        capture_rendered_listing_fragments_impl=_fake_capture_fragments,
        capture_listing_visual_elements_impl=_fake_capture_visuals,
    )

    assert result["blocked"] is True
    assert result["diagnostics"]["challenge_evidence"] == ["blocked_html_checker"]


@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_uses_aom_expansion_when_dom_keyword_scan_misses() -> None:
    page = _FakeExpansionPage(
        base_html="<html><body><h1>Widget Prime</h1><div>Overview</div></body></html>",
        expanded_html="""
        <html><body>
          <h1>Widget Prime</h1>
          <div>Overview</div>
          <section>Specifications</section>
          <div>Rubber outsole, reinforced toe cap.</div>
        </body></html>
        """,
        labels=[{"label": "share"}],
        accessibility_snapshot={
            "role": "document",
            "children": [
                {"role": "tab", "name": "Product specifications"},
                {"role": "button", "name": "Share"},
            ],
        },
        role_targets={("tab", "product specifications")},
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
    assert result.browser_diagnostics["detail_expansion"]["dom"]["clicked_count"] == 0
    assert result.browser_diagnostics["detail_expansion"]["aom"]["clicked_count"] == 1
    assert (
        result.browser_diagnostics["detail_expansion"]["reason"]
        == "missing_detail_content"
    )


@pytest.mark.asyncio
@pytest.mark.regression
async def test_dom_detail_expansion_stops_after_click_exceeds_time_budget() -> None:
    page = _FakeExpansionPage(
        base_html="<html><body><h1>Widget Prime</h1></body></html>",
        labels=[
            {"label": "Details", "attributes": {"aria-controls": "details"}},
            {"label": "Materials", "attributes": {"aria-controls": "materials"}},
        ],
    )

    async def _snapshot(handle: _FakeHandle) -> dict[str, object]:
        await _async_checkpoint()
        return {
            "probe": handle.label.lower(),
            "label": handle.label.lower(),
            "aria_expanded": "",
            "href": "",
            "aria_controls": handle.attributes.get("aria-controls", ""),
            "data_qa_action": "",
            "class_name": "",
            "tag_name": handle.tag_name,
            "visible": True,
            "actionable": True,
        }

    diagnostics = await browser_detail.expand_all_interactive_elements_impl(
        page,
        surface="ecommerce_detail",
        requested_fields=None,
        detail_expand_selectors=("button",),
        detail_expansion_keywords=lambda *_args, **_kwargs: ("details", "materials"),
        interactive_candidate_snapshot=_snapshot,
        elapsed_ms=lambda _started_at: 999 if page.expanded else 0,
        max_elapsed_ms=10,
    )

    assert diagnostics["status"] == "time_budget_reached"
    assert diagnostics["clicked_count"] == 1
    assert diagnostics["expanded_elements"] == ["details"]

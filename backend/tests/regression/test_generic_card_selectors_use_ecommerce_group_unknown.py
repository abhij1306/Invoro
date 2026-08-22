from __future__ import annotations

from .test_browser_expansion_runtime import BeautifulSoup, SimpleNamespace, _FakeExpansionPage, _async_checkpoint, _network_capture_summary, asynccontextmanager, browser_page_flow, browser_page_helpers, browser_readiness, browser_result_builder, browser_runtime, crawler_runtime_settings, pytest  # fmt: skip

pytest_plugins = ["tests.regression.test_browser_expansion_runtime"]

@pytest.mark.regression
def test_generic_card_selectors_use_ecommerce_group_for_unknown_listing_surface(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        browser_page_flow,
        "CARD_SELECTORS",
        {"ecommerce": [".product-card"], "jobs": [".job-card", ".product-card"]},
    )

    selectors = browser_page_flow._generic_card_selectors_for_surface(
        "automobile_listing"
    )

    # Non-job surfaces route to ecommerce group only, matching listing_selector_group.
    assert selectors == [".product-card"]

@pytest.mark.regression
def test_select_primary_browser_html_prefers_full_rendered_when_traversal_fragment_is_capped() -> (
    None
):
    traversal_result = SimpleNamespace(
        activated=True,
        progress_events=1,
        card_count=236,
        stop_reason="target_records_reached",
    )

    html = browser_page_helpers.select_primary_browser_html(
        surface="ecommerce_listing",
        traversal_result=traversal_result,
        traversal_html="<html><body><a href='/products/a'>A</a></body></html>",
        rendered_html=(
            "<html><body>"
            "<a href='/products/a'>A</a>"
            "<a href='/products/b'>B</a>"
            "</body></html>"
        ),
        listing_min_items=2,
    )

    assert "products/b" in html

@pytest.mark.regression
def test_select_primary_browser_html_uses_surface_specific_detail_hints() -> None:
    traversal_result = SimpleNamespace(
        activated=True,
        progress_events=0,
        card_count=0,
        stop_reason="target_records_reached",
    )

    html = browser_page_helpers.select_primary_browser_html(
        surface="job_listing",
        traversal_result=traversal_result,
        traversal_html=(
            "<html><body>"
            "<a href='/products/a'>Product A</a>"
            "<a href='/products/b'>Product B</a>"
            "</body></html>"
        ),
        rendered_html="<html><body><a href='/jobs/123'>Job</a></body></html>",
        listing_min_items=2,
    )

    assert "jobs/123" in html

@pytest.mark.regression
def test_location_interstitial_diagnostics_marks_location_required() -> None:
    html = """
    <html><body>
      <div role="dialog" class="location-modal"><h2>Choose your location</h2><button>Continue</button></div>
    </body></html>
    """
    assert browser_page_helpers.location_interstitial_detected(html) is True

    diagnostics = browser_result_builder.build_browser_diagnostics(
        browser_reason="http-escalation",
        browser_outcome="location_required",
        navigation_strategy="domcontentloaded",
        response_missing=False,
        networkidle_timed_out=False,
        networkidle_skip_reason=None,
        readiness_policy={},
        phase_timings_ms={},
        html_bytes=len(html.encode("utf-8")),
        challenge_evidence=[],
        blocked_classification=SimpleNamespace(
            provider_hits=[],
            challenge_element_hits=[],
        ),
        low_content_reason=None,
        readiness_probes=[],
        capture_summary=SimpleNamespace(
            network_payload_count=0,
            malformed_network_payloads=0,
            network_payload_read_failures=0,
            network_payload_read_timeouts=0,
            closed_network_payloads=0,
            skipped_oversized_network_payloads=0,
            dropped_payload_events=0,
        ),
        readiness_diagnostics={},
        expansion_diagnostics={},
        listing_recovery_diagnostics={},
        listing_artifact_diagnostics={},
        interstitial_diagnostics={"location_required": True},
        traversal_result=None,
    )

    assert diagnostics["browser_outcome"] == "location_required"
    assert diagnostics["failure_reason"] == "location_required"
    assert diagnostics["interstitial"]["location_required"] is True

@pytest.mark.asyncio
@pytest.mark.regression
async def test_finalize_browser_fetch_marks_location_interstitial_blocked(
    browser_finalize_support: SimpleNamespace,
) -> None:
    html = (
        "<html><body><div role='dialog' class='location-modal'>"
        "<h2>Choose your location</h2><button>Continue</button>"
        "</div></body></html>"
    )
    payload = browser_finalize_support.make_payload(html=html)

    result = await browser_result_builder.finalize_browser_fetch(
        payload,
        blocked_html_checker=lambda *_args, **_kwargs: False,
        classify_blocked_page_async=browser_finalize_support.classify_blocked_page_async,
        classify_low_content_reason=lambda *_args, **_kwargs: None,
        classify_browser_outcome=lambda **_kwargs: "usable_content",
        capture_browser_screenshot=lambda _page: "",
        emit_browser_event=browser_finalize_support.emit_browser_event,
        elapsed_ms=lambda _started_at: 0,
        capture_rendered_listing_fragments_impl=browser_finalize_support.capture_fragments,
        capture_listing_visual_elements_impl=browser_finalize_support.capture_visuals,
    )

    assert result["blocked"] is True
    assert result["diagnostics"]["browser_outcome"] == "location_required"
    assert result["diagnostics"]["failure_reason"] == "location_required"
    assert result["diagnostics"]["low_content_reason"] == "location_required"
    assert "location_interstitial" in result["diagnostics"]["challenge_evidence"]
    assert browser_finalize_support.visual_calls == []

@pytest.mark.asyncio
@pytest.mark.regression
async def test_finalize_browser_fetch_keeps_usable_detail_without_ready_probe(
    browser_finalize_support: SimpleNamespace,
) -> None:
    html = """
    <html><body>
      <main>
        <div class="product-title">Widget Prime</div>
        <div class="price">$19.99</div>
        <p>Durable cotton shirt with complete product copy.</p>
      </main>
    </body></html>
    """
    payload = browser_finalize_support.make_payload(
        html=html,
        readiness_probes=[
            {
                "is_ready": False,
                "detail_like": False,
                "structured_data_present": False,
                "visible_text_length": 70,
            }
        ],
    )

    result = await browser_result_builder.finalize_browser_fetch(
        payload,
        blocked_html_checker=lambda *_args, **_kwargs: False,
        classify_blocked_page_async=browser_finalize_support.classify_blocked_page_async,
        classify_low_content_reason=lambda *_args, **_kwargs: None,
        classify_browser_outcome=lambda **_kwargs: "usable_content",
        capture_browser_screenshot=lambda _page: "",
        emit_browser_event=browser_finalize_support.emit_browser_event,
        elapsed_ms=lambda _started_at: 0,
        capture_rendered_listing_fragments_impl=browser_finalize_support.capture_fragments,
        capture_listing_visual_elements_impl=browser_finalize_support.capture_visuals,
    )

    assert result["blocked"] is False
    assert result["diagnostics"]["browser_outcome"] == "usable_content"
    assert result["diagnostics"].get("low_content_reason") in (None, "")

@pytest.mark.regression
def test_location_interstitial_detects_text_only_fallback() -> None:
    html = """
    <html><body>
      <section>
        <h2>Choose your location</h2>
        <p>Enter zip code to deliver to your area.</p>
      </section>
    </body></html>
    """

    assert browser_page_helpers.location_interstitial_detected(html) is True

@pytest.mark.asyncio
@pytest.mark.regression
async def test_probe_browser_readiness_detects_spaced_jsonld_detail_type() -> None:
    html = """
    <html><body>
      <script type="application/ld+json">
        {"@context": "https://schema.org", "@type" : "Product", "name": "Widget"}
      </script>
    </body></html>
    """

    probe = await browser_readiness.probe_browser_readiness_impl(
        SimpleNamespace(),
        url="https://example.com/products/widget",
        surface="ecommerce_detail",
        html=html,
        detail_readiness_hint_count=lambda *_args, **_kwargs: 0,
    )

    assert probe["structured_data_present"] is True
    assert probe["is_ready"] is False

    ready_probe = await browser_readiness.probe_browser_readiness_impl(
        SimpleNamespace(),
        url="https://example.com/products/widget",
        surface="ecommerce_detail",
        html=html.replace(
            "</body>",
            (
                "<h1>Widget</h1>"
                "<p>Detailed rendered product content. " * 12 + "</p></body>"
            ),
        ),
        detail_readiness_hint_count=lambda *_args, **_kwargs: 0,
    )

    assert ready_probe["structured_data_present"] is True
    assert ready_probe["is_ready"] is True

@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_closes_payload_capture_after_policy_resolution_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed: list[object] = []

    class _FakePayloadCapture:
        def attach(self, _page):
            return None

        async def close(self, page):
            closed.append(page)
            return _network_capture_summary()

    page = SimpleNamespace(
        url="https://example.com/products/widget",
        route=lambda *_args, **_kwargs: _async_checkpoint(),
    )

    @asynccontextmanager
    async def _page_context():
        yield page

    async def _fake_resolve_page_context(**_kwargs):
        return None, _page_context()

    async def _fake_prepare_context(**_kwargs):
        return "chromium", "chromium", False, True

    def _raise_policy_error(**_kwargs):
        raise RuntimeError("policy failed")

    monkeypatch.setattr(
        browser_runtime,
        "_resolve_browser_fetch_page_context",
        _fake_resolve_page_context,
    )
    monkeypatch.setattr(
        browser_runtime,
        "_prepare_browser_fetch_launch_context",
        _fake_prepare_context,
    )
    monkeypatch.setattr(
        browser_runtime,
        "_build_payload_capture",
        lambda **_kwargs: _FakePayloadCapture(),
    )
    monkeypatch.setattr(
        browser_runtime,
        "resolve_browser_fetch_policy_impl",
        _raise_policy_error,
    )

    with pytest.raises(RuntimeError, match="policy failed"):
        await browser_runtime.browser_fetch(
            "https://example.com/products/widget",
            timeout_seconds=1,
            surface="ecommerce_detail",
        )

    assert closed == [page]

@pytest.mark.regression
def test_ready_probe_supports_fast_finalize_for_strong_detail_page() -> None:
    assert (
        browser_result_builder.ready_probe_supports_fast_finalize(
            [
                {
                    "is_ready": True,
                    "visible_text_length": 5000,
                    "structured_data_present": True,
                    "detail_hint_count": 4,
                }
            ],
            surface="ecommerce_detail",
            status_code=200,
        )
        is True
    )

@pytest.mark.regression
def test_ready_probe_fast_finalize_rejects_for_forced_block_status() -> None:
    assert (
        browser_result_builder.ready_probe_supports_fast_finalize(
            [
                {
                    "is_ready": True,
                    "visible_text_length": 5000,
                    "structured_data_present": True,
                    "detail_hint_count": 4,
                }
            ],
            surface="ecommerce_detail",
            status_code=403,
        )
        is False
    )

@pytest.mark.regression
def test_fast_finalize_accepts_verified_extractability_without_probe_payload() -> None:
    assert (
        browser_result_builder.ready_probe_supports_fast_finalize(
            [],
            surface="ecommerce_detail",
            status_code=200,
            expansion_diagnostics={
                "extractability": {
                    "verified": True,
                    "matched_requested_fields": ["title", "image_url"],
                }
            },
        )
        is True
    )

@pytest.mark.asyncio
@pytest.mark.regression
async def test_fast_finalize_keeps_location_clear_when_precheck_found_no_signal(
    browser_finalize_support: SimpleNamespace,
) -> None:
    payload = browser_finalize_support.make_payload(
        readiness_probes=[
            {
                "is_ready": True,
                "visible_text_length": 5000,
                "structured_data_present": True,
                "detail_hint_count": 4,
            }
        ],
        networkidle_skip_reason="fast_path_ready",
        interstitial_diagnostics={
            "status": "not_found",
            "reason": "no_location_signal",
        },
    )

    result = await browser_result_builder.finalize_browser_fetch(
        payload,
        blocked_html_checker=lambda *_args, **_kwargs: False,
        classify_blocked_page_async=browser_finalize_support.classify_blocked_page_async,
        classify_low_content_reason=lambda *_args, **_kwargs: None,
        classify_browser_outcome=lambda **_kwargs: "usable_content",
        capture_browser_screenshot=lambda _page: "",
        emit_browser_event=browser_finalize_support.emit_browser_event,
        elapsed_ms=lambda _started_at: 0,
        capture_rendered_listing_fragments_impl=browser_finalize_support.capture_fragments,
        capture_listing_visual_elements_impl=browser_finalize_support.capture_visuals,
    )

    assert result["blocked"] is False
    assert result["diagnostics"]["browser_outcome"] == "usable_content"
    assert result["diagnostics"]["interstitial"]["location_required"] is False

@pytest.mark.asyncio
@pytest.mark.regression
async def test_location_interstitial_dismisses_by_safe_text_token() -> None:
    class _MissingLocator:
        async def count(self) -> int:
            await _async_checkpoint()
            return 0

        @property
        def first(self):
            return self

    class _Page:
        url = "https://www.newbalance.com/pd/574-core/ML574V3-40377.html"

        def __init__(self) -> None:
            self.waited = False
            self.dismissed = False

        def locator(self, selector: str):
            del selector
            return _MissingLocator()

        async def evaluate(self, script: str, payload: dict[str, object]):
            await _async_checkpoint()
            if "selectors" in payload:
                return not self.dismissed
            assert "Continue" in payload["tokens"]
            assert "document.body.innerText" not in script
            self.dismissed = True
            return {"status": "dismissed", "selector": "text:continue"}

        async def wait_for_timeout(self, timeout_ms: int) -> None:
            await _async_checkpoint()
            del timeout_ms
            self.waited = True

    page = _Page()

    result = await browser_page_helpers.dismiss_safe_location_interstitial(page)

    assert result == {"status": "dismissed", "selector": "text:continue"}
    assert page.waited is True

@pytest.mark.asyncio
@pytest.mark.regression
async def test_location_interstitial_dismissal_counts_before_first_locator() -> None:
    class _FirstLocator:
        def __init__(self, page: "_Page") -> None:
            self._page = page

        async def wait_for(self, **_kwargs) -> None:
            await _async_checkpoint()
            return None

        async def click(self, **_kwargs) -> None:
            await _async_checkpoint()
            self._page.dismissed = True
            return None

    class _Locator:
        def __init__(self, page: "_Page") -> None:
            self._page = page

        @property
        def first(self):
            return _FirstLocator(self._page)

        async def count(self) -> int:
            await _async_checkpoint()
            return 1

    class _Page:
        url = "https://example.com/products/widget"

        def __init__(self) -> None:
            self.waited = False
            self.dismissed = False

        def locator(self, _selector: str):
            return _Locator(self)

        async def evaluate(self, _script: str, payload: dict[str, object]):
            await _async_checkpoint()
            if "selectors" in payload:
                return not self.dismissed
            return {"status": "not_found"}

        async def wait_for_timeout(self, _timeout_ms: int) -> None:
            await _async_checkpoint()
            self.waited = True

    result = await browser_page_helpers.dismiss_safe_location_interstitial(_Page())

    assert result["status"] == "dismissed"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_location_interstitial_dismissal_requires_modal_to_clear() -> None:
    class _FirstLocator:
        async def wait_for(self, **_kwargs) -> None:
            await _async_checkpoint()
            return None

        async def click(self, **_kwargs) -> None:
            await _async_checkpoint()
            return None

    class _Locator:
        @property
        def first(self):
            return _FirstLocator()

        async def count(self) -> int:
            await _async_checkpoint()
            return 1

    class _Page:
        url = "https://example.com/products/widget"

        def locator(self, _selector: str):
            return _Locator()

        async def wait_for_timeout(self, _timeout_ms: int) -> None:
            await _async_checkpoint()
            return None

        async def evaluate(self, _script: str, _payload: dict[str, object]):
            await _async_checkpoint()
            return True

    result = await browser_page_helpers.dismiss_safe_location_interstitial(_Page())

    assert result["status"] == "still_present"
    assert "selector" in result
    assert isinstance(result["selector"], str)
    assert result["selector"].strip()

@pytest.mark.asyncio
@pytest.mark.regression
async def test_location_interstitial_dismissal_skips_when_no_signal_present() -> None:
    class _Page:
        url = "https://example.com/products/widget"

        def locator(self, _selector: str):
            raise AssertionError(
                "locator probe should be skipped when no signal exists"
            )

        async def evaluate(self, script: str, payload: dict[str, object]):
            await _async_checkpoint()
            if "selectors" in payload:
                return False
            raise AssertionError(
                "dismiss-by-text should be skipped when no signal exists"
            )

        async def wait_for_timeout(self, *_args, **_kwargs) -> None:
            await _async_checkpoint()
            raise AssertionError(
                "wait_for_timeout should be skipped when no signal exists"
            )

        async def content(self) -> str:
            await _async_checkpoint()
            raise AssertionError("content should be skipped when no signal exists")

    result = await browser_page_helpers.dismiss_safe_location_interstitial(_Page())

    assert result == {"status": "not_found", "reason": "no_location_signal"}

@pytest.mark.asyncio
@pytest.mark.regression
async def test_serialize_browser_page_content_reuses_prefetched_html_without_page_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    html = "<html><body><h1>Widget Prime</h1></body></html>"
    page = _FakeExpansionPage(
        base_html=html,
    )
    prefetched_analysis = browser_page_flow.analyze_html(html)

    def _unexpected_analyze_html(*_args, **_kwargs):
        raise AssertionError("analyze_html should not run for prefetched analysis")

    monkeypatch.setattr(browser_page_flow, "analyze_html", _unexpected_analyze_html)
    (
        html,
        traversal_result,
        rendered_html,
        listing_recovery_diagnostics,
    ) = await browser_page_flow.serialize_browser_page_content_impl(
        page,
        surface="ecommerce_detail",
        traversal_mode=None,
        listing_recovery_mode=None,
        traversal_active=False,
        timeout_seconds=5,
        max_pages=1,
        max_scrolls=1,
        max_records=1,
        prefetched_html=None,
        prefetched_analysis=prefetched_analysis,
        phase_timings_ms={},
        execute_listing_traversal=None,
        recover_listing_page_content=None,
        elapsed_ms=lambda _started_at: 0,
        on_event=None,
    )

    assert page.content_calls == 0
    assert html == rendered_html
    assert traversal_result is None
    assert listing_recovery_diagnostics["status"] == "skipped"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_settle_browser_page_skips_platform_selector_when_probe_is_ready() -> (
    None
):
    probe_analyses: list[object] = []
    current_html = "<html><body>Searching...</body></html>"

    async def get_page_html_impl(_page):
        await _async_checkpoint()
        return current_html

    async def probe_browser_readiness(*_args, **kwargs):
        await _async_checkpoint()
        probe_analyses.append(kwargs.get("analysis"))
        return {
            "is_ready": True,
            "matched_listing_selectors": len(probe_analyses) - 1,
            "structured_data_present": False,
        }

    async def wait_for_listing_readiness(*_args, **_kwargs):
        raise AssertionError("ready probes must skip platform selector waiting")

    result = await browser_page_flow.settle_browser_page_impl(
        SimpleNamespace(),
        url="https://careers.clarkassociatesinc.biz/",
        surface="job_listing",
        requested_fields=None,
        timeout_seconds=5,
        readiness_override={
            "platform": "clark_careers",
            "selectors": ["li[data-testid='careers-search-result-listing']"],
            "max_wait_ms": 20000,
        },
        readiness_policy={"require_networkidle": True},
        phase_timings_ms={},
        crawler_runtime_settings=crawler_runtime_settings,
        get_page_html_impl=get_page_html_impl,
        probe_browser_readiness=probe_browser_readiness,
        wait_for_listing_readiness=wait_for_listing_readiness,
        expand_detail_content_if_needed=None,
        append_readiness_probe=browser_page_flow.append_readiness_probe,
        elapsed_ms=lambda _started_at: 0,
    )

    _current_probe, readiness_probes, *_rest = result

    assert [
        (analysis.html, analysis.lowered_html, analysis.normalized_text)
        for analysis in probe_analyses
    ] == [(current_html, current_html.lower(), "Searching...")]
    assert [probe["stage"] for probe in readiness_probes] == ["after_navigation"]

@pytest.mark.regression
def test_detail_expansion_extractability_reuses_supplied_soup_without_reparse() -> None:
    soup = BeautifulSoup(
        "<html><body><section><h2>Materials</h2><p>Leather upper.</p></section></body></html>",
        "html.parser",
    )

    def _unexpected_bs4(*_args, **_kwargs):
        raise AssertionError("BeautifulSoup should not be called when soup is supplied")

    extractability = browser_page_helpers.detail_expansion_extractability(
        html="",
        soup=soup,
        surface="ecommerce_detail",
        requested_fields=["materials"],
        beautiful_soup_factory=_unexpected_bs4,
    )

    assert extractability["matched_requested_fields"] == ["materials"]

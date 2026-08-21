from __future__ import annotations

from .test_browser_expansion_runtime import *  # noqa: F403


@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_aom_expansion_respects_interaction_cap(
    patch_settings,
) -> None:
    patch_settings(detail_aom_expand_max_interactions=1)
    page = _FakeExpansionPage(
        base_html="<html><body><h1>Widget Prime</h1><div>Overview</div></body></html>",
        expanded_html="""
        <html><body>
          <h1>Widget Prime</h1>
          <div>Specifications</div>
          <div>Rubber outsole, reinforced toe cap.</div>
        </body></html>
        """,
        labels=[{"label": "share"}],
        accessibility_snapshot={
            "role": "document",
            "children": [
                {"role": "tab", "name": "Product specifications"},
                {"role": "tab", "name": "Product dimensions"},
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
    assert result.browser_diagnostics["detail_expansion"]["aom"]["limit"] == 1
    assert result.browser_diagnostics["detail_expansion"]["aom"]["clicked_count"] == 1
    assert result.browser_diagnostics["detail_expansion"]["aom"]["attempted"] is True

@pytest.mark.asyncio
@pytest.mark.regression
async def test_expand_interactive_elements_via_accessibility_supports_locators_without_visibility_timeout() -> (
    None
):
    page = _FakeExpansionPage(
        base_html="<html><body><h1>Widget Prime</h1></body></html>",
        accessibility_snapshot={
            "role": "document",
            "children": [{"role": "tab", "name": "Product specifications"}],
        },
        role_targets={("tab", "product specifications")},
    )

    def _get_by_role(
        role: str, *, name: str, exact: bool = True
    ) -> _NoTimeoutRoleLocator:
        del exact
        return _NoTimeoutRoleLocator(page, role, name)

    page.get_by_role = _get_by_role

    diagnostics = await browser_detail.expand_interactive_elements_via_accessibility_impl(
        page,
        surface="ecommerce_detail",
        requested_fields=None,
        detail_expansion_keywords=browser_runtime.detail_expansion_keywords,
        accessibility_expand_candidates=browser_runtime.accessibility_expand_candidates,
        elapsed_ms=browser_runtime._elapsed_ms,
    )

    assert diagnostics["clicked_count"] == 1
    assert diagnostics["expanded_elements"] == ["product specifications"]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_expand_interactive_elements_via_accessibility_waits_for_visibility_with_configured_timeout(
    patch_settings,
) -> None:
    page = _FakeExpansionPage(
        base_html="<html><body><h1>Widget Prime</h1></body></html>",
        accessibility_snapshot={
            "role": "document",
            "children": [{"role": "tab", "name": "Product specifications"}],
        },
        role_targets={("tab", "product specifications")},
    )
    locator = _WaitingRoleLocator(page, "tab", "product specifications")
    patch_settings(detail_expand_visibility_timeout_ms=375)

    def _get_by_role(
        role: str, *, name: str, exact: bool = True
    ) -> _WaitingRoleLocator:
        del role, name, exact
        return locator

    page.get_by_role = _get_by_role
    diagnostics = await browser_detail.expand_interactive_elements_via_accessibility_impl(
        page,
        surface="ecommerce_detail",
        requested_fields=None,
        detail_expansion_keywords=browser_runtime.detail_expansion_keywords,
        accessibility_expand_candidates=browser_runtime.accessibility_expand_candidates,
        elapsed_ms=browser_runtime._elapsed_ms,
    )

    assert locator.wait_for_calls == [("visible", 375)]
    assert diagnostics["clicked_count"] == 1

@pytest.mark.asyncio
@pytest.mark.regression
async def test_expand_interactive_elements_via_accessibility_times_out_slow_snapshot(
    patch_settings,
) -> None:
    patch_settings(browser_accessibility_snapshot_timeout_seconds=0.05)
    page = _FakeExpansionPage(
        base_html="<html><body><h1>Widget Prime</h1></body></html>",
        accessibility_snapshot={"role": "document", "children": []},
    )

    async def _slow_snapshot() -> dict[str, object]:
        await asyncio.sleep(1)
        return {"role": "document", "children": []}

    page.accessibility = SimpleNamespace(snapshot=_slow_snapshot)
    diagnostics = await browser_detail.expand_interactive_elements_via_accessibility_impl(
        page,
        surface="ecommerce_detail",
        requested_fields=None,
        detail_expansion_keywords=browser_runtime.detail_expansion_keywords,
        accessibility_expand_candidates=browser_runtime.accessibility_expand_candidates,
        elapsed_ms=browser_runtime._elapsed_ms,
    )

    assert diagnostics["status"] == "snapshot_timeout"
    assert diagnostics["clicked_count"] == 0
    assert diagnostics["attempted"] is True

@pytest.mark.regression
def test_detail_title_url_match_scans_past_nonmatching_trailing_segments() -> None:
    assert browser_readiness._detail_title_matches_url(
        "https://example.com/products/widget/reviews",
        "Widget",
        min_matches=1,
    )

@pytest.mark.asyncio
@pytest.mark.regression
async def test_expand_detail_content_if_needed_skips_non_detail_like_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _unexpected_dom_expand(*args, **kwargs):
        await _async_checkpoint()
        raise AssertionError("DOM expansion should be skipped")

    monkeypatch.setattr(
        browser_runtime,
        "expand_all_interactive_elements",
        _unexpected_dom_expand,
    )

    diagnostics = await browser_runtime.expand_detail_content_if_needed(
        _FakeExpansionPage(base_html="<html><body></body></html>"),
        surface="ecommerce_detail",
        readiness_probe={"is_ready": False, "detail_like": False},
    )

    assert diagnostics["status"] == "skipped"
    assert diagnostics["reason"] == "not_detail_like"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_listing_card_signal_count_uses_heuristic_card_fallback_after_selector_miss(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[bool] = []

    async def _fake_count_listing_cards(
        page, *, surface: str, allow_heuristic: bool = True
    ) -> int:
        await _async_checkpoint()
        del page, surface
        calls.append(bool(allow_heuristic))
        return 9 if allow_heuristic else 0

    monkeypatch.setattr(
        browser_readiness,
        "count_listing_cards",
        _fake_count_listing_cards,
    )

    count = await browser_runtime.listing_card_signal_count(
        _FakeExpansionPage(base_html="<html><body></body></html>"),
        surface="ecommerce_listing",
    )

    assert count == 9
    assert calls == [True]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_probe_browser_readiness_uses_heuristic_listing_card_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[bool] = []

    async def _fake_count_listing_cards(
        page, *, surface: str, allow_heuristic: bool = True
    ) -> int:
        await _async_checkpoint()
        del page, surface
        calls.append(bool(allow_heuristic))
        return 12 if allow_heuristic else 0

    monkeypatch.setattr(
        browser_readiness,
        "listing_card_signal_count_impl",
        _fake_count_listing_cards,
    )

    probe = await browser_runtime.probe_browser_readiness(
        _FakeExpansionPage(
            base_html="<html><body><h1>adidas Sneakers</h1><p>Grid loaded</p></body></html>"
        ),
        url="https://example.com/collections/adidas-shoes",
        surface="ecommerce_listing",
    )

    assert probe["is_ready"] is True
    assert probe["listing_card_count"] == 12
    assert calls == [True]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_capture_close_drains_inflight_response_callbacks() -> None:
    class _FakeResponse:
        url = "https://example.com/api/product"
        headers = {"content-type": "application/json"}
        request = SimpleNamespace(method="GET")
        status = 200

    class _LateDispatchPage:
        def __init__(self) -> None:
            self.listener = None

        def on(self, event_name: str, callback: Any) -> None:
            assert event_name == "response"
            self.listener = callback

        def remove_listener(self, event_name: str, callback: Any) -> None:
            assert event_name == "response"
            self.listener = None
            asyncio.get_running_loop().call_soon(callback, _FakeResponse())

    async def _fake_read_payload_body(response, **_kwargs):
        await _async_checkpoint()
        del response
        return browser_runtime.NetworkPayloadReadResult(
            body=b'{"id":"captured"}',
            outcome="ok",
        )

    capture = BrowserNetworkCapture(
        surface="ecommerce_detail",
        should_capture_payload=lambda **_kwargs: True,
        classify_endpoint=lambda **_kwargs: {"type": "api", "family": "generic"},
        read_payload_body=_fake_read_payload_body,
    )
    page = _LateDispatchPage()
    capture.attach(page)

    summary = await capture.close(page)

    assert summary.network_payload_count == 1
    assert summary.payloads[0]["body"]["id"] == "captured"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_capture_decodes_react_server_component_payloads() -> None:
    class _RscResponse:
        def __init__(self) -> None:
            self.url = "https://example.com/products/widget"
            self.status = 200
            self.headers = {"content-type": "text/x-component"}
            self.request = SimpleNamespace(method="GET")

        async def body(self) -> bytes:
            await _async_checkpoint()
            return (
                b'0:["$","$L1",null,{"title":"Trail Runner","price":"109.00"}]\n'
                b'1:{"product":{"title":"Trail Runner","sku":"TRAIL-1"}}\n'
            )

    page = _FakeExpansionPage(base_html="<html><body></body></html>")
    capture = BrowserNetworkCapture(surface="ecommerce_detail")
    capture.attach(page)

    listeners = page.listeners.get("response") or []
    assert listeners
    listeners[0](_RscResponse())

    summary = await capture.close(page)

    assert summary.network_payload_count == 1
    assert summary.malformed_network_payloads == 0
    assert isinstance(summary.payloads[0]["body"], list)
    assert summary.payloads[0]["body"][0][3]["title"] == "Trail Runner"
    assert summary.payloads[0]["body"][1]["product"]["sku"] == "TRAIL-1"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_capture_offloads_payload_decoding_to_thread() -> None:
    class _JsonResponse:
        def __init__(self) -> None:
            self.url = "https://example.com/api/product"
            self.status = 200
            self.headers = {"content-type": "application/json"}
            self.request = SimpleNamespace(method="GET")

        async def body(self) -> bytes:
            await _async_checkpoint()
            return b'{"id":"captured"}'

    page = _FakeExpansionPage(base_html="<html><body></body></html>")
    capture = BrowserNetworkCapture(surface="ecommerce_detail")
    capture.attach(page)

    listeners = page.listeners.get("response") or []
    assert listeners
    listeners[0](_JsonResponse())

    summary = await capture.close(page)

    assert summary.network_payload_count == 1
    assert summary.payloads[0]["body"]["id"] == "captured"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_capture_close_uses_bounded_queue_join_timeout(
    patch_settings,
) -> None:
    patch_settings(browser_capture_queue_join_timeout_ms=50)
    capture = BrowserNetworkCapture(
        surface="ecommerce_detail",
        should_capture_payload=lambda **_kwargs: True,
        classify_endpoint=lambda **_kwargs: {"type": "api", "family": "generic"},
        read_payload_body=lambda *_args, **_kwargs: (
            browser_runtime.NetworkPayloadReadResult(
                body=b'{"id":"captured"}',
                outcome="ok",
            )
        ),
    )
    page = _FakeExpansionPage(base_html="<html><body></body></html>")
    capture.attach(page)

    async def _stalled_join() -> None:
        await asyncio.sleep(1)

    capture._queue.join = _stalled_join  # type: ignore[method-assign]

    started_at = asyncio.get_running_loop().time()
    summary = await capture.close(page)
    elapsed = asyncio.get_running_loop().time() - started_at

    assert summary.network_payload_count == 0
    assert elapsed < 0.5

@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_capture_close_awaits_sentinel_enqueue_when_queue_put_blocks() -> (
    None
):
    capture = BrowserNetworkCapture(surface="ecommerce_detail")

    class _Queue:
        def __init__(self) -> None:
            self.put_calls: list[object] = []

        async def join(self) -> None:
            await _async_checkpoint()
            return None

        async def put(self, value: object) -> None:
            self.put_calls.append(value)
            await asyncio.sleep(0)

    fake_queue = _Queue()
    capture._queue = fake_queue  # type: ignore[assignment]
    capture._workers = {asyncio.create_task(asyncio.sleep(0))}

    summary = await capture.close(
        _FakeExpansionPage(base_html="<html><body></body></html>")
    )

    assert summary.network_payload_count == 0
    assert fake_queue.put_calls == [None]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_capture_close_cancels_workers_when_sentinel_enqueue_times_out(
    patch_settings,
) -> None:
    patch_settings(browser_capture_queue_join_timeout_ms=50)
    capture = BrowserNetworkCapture(surface="ecommerce_detail")

    class _Queue:
        async def join(self) -> None:
            await _async_checkpoint()
            return None

        async def put(self, value: object) -> None:
            del value
            await asyncio.sleep(1)

    worker = asyncio.create_task(asyncio.sleep(1))
    capture._queue = _Queue()  # type: ignore[assignment]
    capture._workers = {worker}

    summary = await capture.close(
        _FakeExpansionPage(base_html="<html><body></body></html>")
    )

    assert summary.network_payload_count == 0
    assert worker.cancelled() or worker.done()

@pytest.mark.asyncio
@pytest.mark.regression
async def test_probe_browser_readiness_skips_listing_queries_for_detail_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _unexpected_listing_card_count(*args, **kwargs):
        await _async_checkpoint()
        raise AssertionError("listing card count should not run for detail pages")

    async def _unexpected_selector_count(*args, **kwargs):
        await _async_checkpoint()
        raise AssertionError("listing selector count should not run for detail pages")

    monkeypatch.setattr(
        "app.services.acquisition.browser_readiness.listing_card_signal_count_impl",
        _unexpected_listing_card_count,
    )
    monkeypatch.setattr(
        "app.services.acquisition.browser_readiness.count_matching_selectors",
        _unexpected_selector_count,
    )

    probe = await browser_runtime.probe_browser_readiness(
        _FakeExpansionPage(base_html="<html><body><h1>Widget Prime</h1></body></html>"),
        url="https://example.com/products/widget",
        surface="ecommerce_detail",
    )

    assert probe["is_ready"] is False
    assert probe["listing_card_count"] == 0
    assert probe["matched_listing_selectors"] == 0

@pytest.mark.asyncio
@pytest.mark.regression
async def test_count_matching_selectors_ignores_timeout_misses() -> None:
    class _Locator:
        async def count(self) -> int:
            await _async_checkpoint()
            raise PlaywrightTimeoutError("timed out")

    class _Page:
        def locator(self, selector: str) -> _Locator:
            del selector
            return _Locator()

    matches = await browser_readiness.count_matching_selectors(
        _Page(),
        selectors=[".product-card"],
    )

    assert matches == 0

@pytest.mark.asyncio
@pytest.mark.regression
async def test_expand_all_interactive_elements_respects_small_interaction_cap(
    patch_settings,
) -> None:
    patch_settings(detail_expand_max_interactions=1)
    page = _FakeExpansionPage(
        base_html="<html><body></body></html>",
        labels=[
            {"label": "product details"},
            {"label": "product dimensions"},
        ],
    )
    diagnostics = await browser_runtime.expand_all_interactive_elements(
        page,
        surface="ecommerce_detail",
    )

    assert diagnostics["limit"] == 1
    assert diagnostics["clicked_count"] == 1
    assert diagnostics["expanded_elements"] == ["product details"]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_expand_all_interactive_elements_skips_non_actionable_candidates() -> (
    None
):
    page = _FakeExpansionPage(
        base_html="<html><body></body></html>",
        labels=[
            {"label": "product details", "actionable": False},
            {"label": "product specifications", "actionable": True},
        ],
    )

    diagnostics = await browser_runtime.expand_all_interactive_elements(
        page,
        surface="ecommerce_detail",
    )

    assert diagnostics["clicked_count"] == 1
    assert diagnostics["expanded_elements"] == ["product specifications"]

@pytest.mark.regression
def test_classify_browser_outcome_marks_empty_category_as_low_content_shell() -> None:
    html = "<html><body><h1>Empty category</h1></body></html>"

    outcome = browser_runtime.classify_browser_outcome(
        html=html,
        html_bytes=len(html.encode("utf-8")),
        blocked=False,
    )

    assert outcome == "low_content_shell"
    assert (
        browser_runtime.classify_low_content_reason(
            html,
            html_bytes=len(html.encode("utf-8")),
        )
        == "empty_terminal_page"
    )

@pytest.mark.regression
def test_classify_browser_outcome_marks_site_maintenance_title_as_low_content_shell() -> (
    None
):
    html = """
    <html>
      <head><title>Site Maintenance</title></head>
      <body>
        <main>
          <h1>Site Maintenance</h1>
          <p>
            We're making a few updates to our site and working through a short
            maintenance window so shopping is unavailable right now, but we will
            be back shortly with full product access.
          </p>
        </main>
      </body>
    </html>
    """

    outcome = browser_runtime.classify_browser_outcome(
        html=html,
        html_bytes=len(html.encode("utf-8")),
        blocked=False,
    )

    assert outcome == "low_content_shell"
    assert (
        browser_runtime.classify_low_content_reason(
            html,
            html_bytes=len(html.encode("utf-8")),
        )
        == "empty_terminal_page"
    )

@pytest.mark.regression
def test_classify_browser_outcome_marks_error_page_title_as_low_content_shell() -> None:
    html = """
    <html>
      <head><title>Error Page</title></head>
      <body>
        <main>
          <h1>Error Page</h1>
          <p>
            The requested page cannot be displayed right now. Please try again
            later or return to the previous page.
          </p>
        </main>
      </body>
    </html>
    """

    outcome = browser_runtime.classify_browser_outcome(
        html=html,
        html_bytes=len(html.encode("utf-8")),
        blocked=False,
    )

    assert outcome == "low_content_shell"
    assert (
        browser_runtime.classify_low_content_reason(
            html,
            html_bytes=len(html.encode("utf-8")),
        )
        == "empty_terminal_page"
    )

@pytest.mark.regression
def test_classify_low_content_reason_ignores_empty_phrase_on_contentful_page() -> None:
    html = """
    <html><body>
      <p>Filter summary: 0 results for XXL.</p>
      <article><a href="/products/widget-1">Widget One</a><span>$10</span></article>
      <article><a href="/products/widget-2">Widget Two</a><span>$20</span></article>
      <article><a href="/products/widget-3">Widget Three</a><span>$30</span></article>
      <article><a href="/products/widget-4">Widget Four</a><span>$40</span></article>
      <article><a href="/products/widget-5">Widget Five</a><span>$50</span></article>
    </body></html>
    """

    assert (
        browser_runtime.classify_low_content_reason(
            html,
            html_bytes=len(html.encode("utf-8")),
        )
        is None
    )

@pytest.mark.regression
def test_classify_browser_outcome_keeps_ready_listing_with_no_pagination_progress_usable() -> (
    None
):
    html = """
    <html><body>
      <article class='product-card'><a href='/products/widget-1'>Widget One</a><span>$10</span></article>
      <article class='product-card'><a href='/products/widget-2'>Widget Two</a><span>$20</span></article>
      <article class='product-card'><a href='/products/widget-3'>Widget Three</a><span>$30</span></article>
    </body></html>
    """

    outcome = browser_runtime.classify_browser_outcome(
        html=html,
        html_bytes=len(html.encode("utf-8")),
        blocked=False,
        traversal_result=TraversalResult(
            requested_mode="paginate",
            selected_mode="paginate",
            activated=True,
            stop_reason="next_page_not_found",
            progress_events=0,
            card_count=3,
        ),
    )

    assert outcome == "usable_content"

@pytest.mark.regression
def test_classify_browser_outcome_keeps_extractable_listing_usable_below_threshold() -> (
    None
):
    html = """
    <html><body>
      <article class='product-card'><a href='/products/widget-1'>Widget One</a><span>$10</span></article>
      <article class='product-card'><a href='/products/widget-2'>Widget Two</a><span>$20</span></article>
      <article class='product-card'><a href='/products/widget-3'>Widget Three</a><span>$30</span></article>
    </body></html>
    """

    outcome = browser_runtime.classify_browser_outcome(
        html=html,
        html_bytes=len(html.encode("utf-8")),
        blocked=False,
        traversal_result=TraversalResult(
            requested_mode="paginate",
            selected_mode="paginate",
            activated=True,
            stop_reason="paginate_no_progress",
            progress_events=0,
            card_count=0,
        ),
    )

    assert outcome == "usable_content"

@pytest.mark.regression
def test_build_failed_browser_diagnostics_marks_page_closed_explicitly() -> None:
    diagnostics = browser_runtime.build_failed_browser_diagnostics(
        browser_reason="http-escalation",
        exc=RuntimeError("Target closed"),
    )

    assert diagnostics["browser_outcome"] == "navigation_failed"
    assert diagnostics["failure_kind"] == "page_closed"
    assert diagnostics["failure_stage"] == "navigation"

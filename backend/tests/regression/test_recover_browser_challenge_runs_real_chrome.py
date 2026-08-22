from __future__ import annotations

from .test_browser_expansion_runtime import Any, PlaywrightError, PlaywrightTimeoutError, SimpleNamespace, _FakeExpansionPage, _FakeRuntime, _async_checkpoint, asyncio, browser_page_flow, browser_page_helpers, browser_readiness, browser_recovery, browser_runtime, build_browser_fetch_result, crawler_runtime_settings, dom_runtime, pytest, time  # fmt: skip

pytest_plugins = ["tests.regression.test_browser_expansion_runtime"]


@pytest.mark.asyncio
@pytest.mark.regression
async def test_recover_browser_challenge_runs_for_real_chrome() -> None:
    original_response = SimpleNamespace(
        status=403, headers={"content-type": "text/html"}
    )
    retried_response = SimpleNamespace(
        status=200, headers={"content-type": "text/html"}
    )

    class _Page:
        mouse = None

        def __init__(self) -> None:
            self.goto_calls = 0
            self.wait_calls = 0

        async def goto(self, *_args, **_kwargs):
            await _async_checkpoint()
            self.goto_calls += 1
            return retried_response

        async def wait_for_timeout(self, _ms: int) -> None:
            await _async_checkpoint()
            self.wait_calls += 1
            return None

    page = _Page()
    classify_calls = {"count": 0}

    async def _get_page_html(_page: Any) -> str:
        await _async_checkpoint()
        return "<html><body>product title $12.00 add to cart</body></html>"

    async def _classify_blocked_page(_html: str, _status_code: int):
        await _async_checkpoint()
        classify_calls["count"] += 1
        return SimpleNamespace(blocked=classify_calls["count"] == 1, provider_hits=[])

    result = await browser_recovery.recover_browser_challenge(
        page,
        url="https://example.com/products/widget",
        response=original_response,
        browser_engine="real_chrome",
        timeout_seconds=5,
        phase_timings_ms={},
        challenge_wait_max_seconds=1,
        challenge_poll_interval_ms=100,
        navigation_timeout_ms=1000,
        elapsed_ms=lambda _started_at: 0,
        classify_blocked_page=_classify_blocked_page,
        get_page_html=_get_page_html,
    )

    assert result is original_response
    assert result.browser_recovered_status == 200
    # The recovery loop re-checks for clear at the top of the first poll
    # iteration (before waiting), so a challenge that clears immediately needs
    # no wait_for_timeout and no retry-goto.
    assert page.wait_calls == 0
    assert page.goto_calls == 0


@pytest.mark.asyncio
@pytest.mark.regression
async def test_recover_browser_challenge_waits_on_provider_low_content_shell() -> None:
    original_response = SimpleNamespace(
        status=200, headers={"content-type": "text/html"}
    )

    class _Page:
        def __init__(self) -> None:
            self.mouse = None
            self.wait_calls = 0
            self.html = "<html><body>akamai shell</body></html>"

        async def wait_for_timeout(self, _timeout: int) -> None:
            await _async_checkpoint()
            self.wait_calls += 1
            self.html = (
                "<html><body><h1>Widget Prime</h1><span>$12.00</span>"
                "<button>Add to cart</button></body></html>"
            )

        async def goto(self, *_args, **_kwargs):
            await _async_checkpoint()
            raise AssertionError("wait recovery should clear before retry navigation")

    page = _Page()

    async def _get_page_html(active_page: Any) -> str:
        await _async_checkpoint()
        return active_page.html

    async def _classify_blocked_page(_html: str, _status_code: int):
        await _async_checkpoint()
        return SimpleNamespace(blocked=False, provider_hits=["akamai"])

    result = await browser_recovery.recover_browser_challenge(
        page,
        url="https://example.com/products/widget",
        response=original_response,
        browser_engine="real_chrome",
        timeout_seconds=5,
        phase_timings_ms={},
        challenge_wait_max_seconds=1,
        challenge_poll_interval_ms=100,
        navigation_timeout_ms=1000,
        elapsed_ms=lambda _started_at: 0,
        classify_blocked_page=_classify_blocked_page,
        get_page_html=_get_page_html,
        looks_like_low_content_shell=lambda html, **_kwargs: "akamai shell" in html,
    )

    assert result is original_response
    assert page.wait_calls == 1


@pytest.mark.asyncio
@pytest.mark.regression
async def test_recover_browser_challenge_clears_akamai_shell_without_cookie() -> None:
    """Lock INVARIANTS §6: challenge recovery re-reads the DOM every poll and
    never gates the clear-check on a provider cookie.

    Models an Akamai provider shell on a page that exposes no cookie API (so a
    cookie-based gate could never observe `_abck`). The shell swaps to real
    product content after one wait. Patchright must recognize the cleared page
    in-place and must NOT fall through to the retry-goto (which is the path that
    would otherwise trigger a needless real-Chrome escalation). Reintroducing the
    old `_abck` cookie gate would make this spin until the budget is exhausted.
    """
    original_response = SimpleNamespace(
        status=200, headers={"content-type": "text/html"}
    )

    class _Page:
        # No `context` attribute on purpose: a cookie-gated check can never pass.
        def __init__(self) -> None:
            self.mouse = None
            self.wait_calls = 0
            self.html = "<html><body>akamai shell</body></html>"

        async def wait_for_timeout(self, _timeout: int) -> None:
            await _async_checkpoint()
            self.wait_calls += 1
            self.html = (
                "<html><body><h1>Widget Prime</h1><span>$12.00</span>"
                "<button>Add to cart</button></body></html>"
            )

        async def goto(self, *_args, **_kwargs):
            await _async_checkpoint()
            raise AssertionError(
                "in-place wait recovery must clear before the retry-goto / escalation"
            )

    page = _Page()

    async def _get_page_html(active_page: Any) -> str:
        await _async_checkpoint()
        return active_page.html

    async def _classify_blocked_page(html: str, _status_code: int):
        await _async_checkpoint()
        return SimpleNamespace(blocked=False, provider_hits=["akamai"])

    result = await browser_recovery.recover_browser_challenge(
        page,
        url="https://example.com/products/widget",
        response=original_response,
        browser_engine="patchright",
        timeout_seconds=5,
        phase_timings_ms={},
        challenge_wait_max_seconds=1,
        challenge_poll_interval_ms=100,
        navigation_timeout_ms=1000,
        elapsed_ms=lambda _started_at: 0,
        classify_blocked_page=_classify_blocked_page,
        get_page_html=_get_page_html,
        looks_like_low_content_shell=lambda html, **_kwargs: "akamai shell" in html,
    )

    assert result is original_response
    # Exactly one wait swaps the shell to real content; the next poll's DOM
    # re-read clears it in-place. No retry-goto, no escalation.
    assert page.wait_calls == 1


@pytest.mark.asyncio
@pytest.mark.regression
async def test_recover_browser_challenge_drops_stale_block_status_after_wait_clear() -> (
    None
):
    original_response = SimpleNamespace(
        status=403, headers={"content-type": "text/html"}
    )
    status_codes: list[int] = []

    class _Page:
        mouse = None

        async def goto(self, *_args, **_kwargs):
            await _async_checkpoint()
            raise AssertionError("retry should not run after challenge clears")

        async def wait_for_timeout(self, _ms: int) -> None:
            await _async_checkpoint()
            return None

    async def _get_page_html(_page: Any) -> str:
        await _async_checkpoint()
        return "<html><body>product title $12.00 add to cart</body></html>"

    async def _classify_blocked_page(_html: str, status_code: int):
        await _async_checkpoint()
        status_codes.append(status_code)
        return SimpleNamespace(blocked=len(status_codes) == 1, provider_hits=[])

    result = await browser_recovery.recover_browser_challenge(
        _Page(),
        url="https://example.com/products/widget",
        response=original_response,
        timeout_seconds=5,
        phase_timings_ms={},
        challenge_wait_max_seconds=1,
        challenge_poll_interval_ms=100,
        navigation_timeout_ms=1000,
        elapsed_ms=lambda _started_at: 0,
        classify_blocked_page=_classify_blocked_page,
        get_page_html=_get_page_html,
    )

    assert status_codes == [403, 200]
    assert result is original_response
    assert result.browser_recovered_status == 200
    assert result.headers == original_response.headers


@pytest.mark.asyncio
@pytest.mark.regression
async def test_recover_browser_challenge_bounds_slow_activity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_response = SimpleNamespace(
        status=200, headers={"content-type": "text/html"}
    )

    class _Page:
        mouse = None

        async def wait_for_timeout(self, _timeout: int) -> None:
            await asyncio.sleep(1)

        async def goto(self, *_args, **_kwargs):
            return original_response

    async def _get_page_html(_page: Any) -> str:
        await _async_checkpoint()
        return "<html><body>akamai shell</body></html>"

    async def _classify_blocked_page(_html: str, _status_code: int):
        await _async_checkpoint()
        return SimpleNamespace(blocked=False, provider_hits=["akamai"])

    async def _slow_activity(_page: Any) -> None:
        await asyncio.sleep(1)

    monkeypatch.setattr(browser_recovery, "_emit_challenge_activity", _slow_activity)

    started_at = time.perf_counter()
    await browser_recovery.recover_browser_challenge(
        _Page(),
        url="https://example.com/products/widget",
        response=original_response,
        browser_engine="patchright",
        timeout_seconds=5,
        phase_timings_ms={},
        challenge_wait_max_seconds=0.05,
        challenge_poll_interval_ms=100,
        navigation_timeout_ms=1000,
        elapsed_ms=lambda start: int((time.perf_counter() - start) * 1000),
        classify_blocked_page=_classify_blocked_page,
        get_page_html=_get_page_html,
        looks_like_low_content_shell=lambda html, **_kwargs: "akamai shell" in html,
    )

    assert time.perf_counter() - started_at < 0.5


@pytest.mark.asyncio
@pytest.mark.regression
async def test_recover_browser_challenge_marks_retry_response_without_wrapping() -> (
    None
):
    retried_response = SimpleNamespace(
        status=403,
        headers={"content-type": "text/html"},
        url="https://example.com/products/widget",
        request=SimpleNamespace(method="GET"),
        name="retried",
    )

    class _Page:
        mouse = None

        def __init__(self) -> None:
            self.retried = False

        async def goto(self, *_args, **_kwargs):
            await _async_checkpoint()
            self.retried = True
            return retried_response

        async def wait_for_timeout(self, _ms: int) -> None:
            await _async_checkpoint()
            return None

    async def _get_page_html(page: Any) -> str:
        await _async_checkpoint()
        return (
            "<html><body>product title $12.00 add to cart</body></html>"
            if page.retried
            else "<html><body>blocked</body></html>"
        )

    async def _classify_blocked_page(html: str, _status_code: int):
        await _async_checkpoint()
        return SimpleNamespace(blocked="blocked" in html, provider_hits=[])

    page = _Page()
    result = await browser_recovery.recover_browser_challenge(
        page,
        url="https://example.com/products/widget",
        response=SimpleNamespace(status=403, headers={"content-type": "text/html"}),
        timeout_seconds=5,
        phase_timings_ms={},
        challenge_wait_max_seconds=1,
        challenge_poll_interval_ms=100,
        navigation_timeout_ms=1000,
        elapsed_ms=lambda _started_at: 0,
        classify_blocked_page=_classify_blocked_page,
        get_page_html=_get_page_html,
    )

    assert result is retried_response
    assert result.browser_recovered_status == 200
    assert result.url == retried_response.url
    assert result.request is retried_response.request
    assert result.name == "retried"
    assert result.browser_navigation_strategy == "domcontentloaded"


@pytest.mark.asyncio
@pytest.mark.regression
async def test_get_page_html_falls_back_to_outer_html_after_driver_close(
    patch_settings,
) -> None:
    patch_settings(browser_error_retry_attempts=1, browser_error_retry_delay_ms=0)

    class _Page:
        def __init__(self) -> None:
            self.content_calls = 0

        async def content(self) -> str:
            await _async_checkpoint()
            self.content_calls += 1
            raise RuntimeError(
                "Page.content: Connection closed while reading from the driver"
            )

        async def evaluate(self, script: str):
            await _async_checkpoint()
            if "flattenedRoots" in script:
                return 0
            return "<html><body><main><h1>Recovered</h1></main></body></html>"

    html = await dom_runtime.get_page_html(_Page())

    assert "Recovered" in html


@pytest.mark.asyncio
@pytest.mark.regression
async def test_get_page_html_outer_html_fallback_preserves_doctype(
    patch_settings,
) -> None:
    patch_settings(browser_error_retry_attempts=0, browser_error_retry_delay_ms=0)

    class _Page:
        async def content(self) -> str:
            await _async_checkpoint()
            raise RuntimeError(
                "Page.content: Connection closed while reading from the driver"
            )

        async def evaluate(self, script: str):
            await _async_checkpoint()
            if "flattenedRoots" in script:
                return 0
            return "<!DOCTYPE html><html><body>Recovered</body></html>"

    html = await dom_runtime.get_page_html(_Page())

    assert html.startswith("<!DOCTYPE html>")


@pytest.mark.asyncio
@pytest.mark.regression
async def test_get_page_html_falls_back_after_live_navigation_content_error(
    patch_settings,
) -> None:
    patch_settings(browser_error_retry_attempts=0, browser_error_retry_delay_ms=0)

    class _Page:
        async def content(self) -> str:
            await _async_checkpoint()
            raise RuntimeError(
                "Page.content: Unable to retrieve content because the page is navigating and changing the content."
            )

        async def evaluate(self, script: str):
            await _async_checkpoint()
            if "flattenedRoots" in script:
                return 0
            return "<html><body><main><h1>Recovered live DOM</h1></main></body></html>"

    html = await dom_runtime.get_page_html(_Page())

    assert "Recovered live DOM" in html


@pytest.mark.regression
def test_shadow_dom_flattener_avoids_inner_html_assignment() -> None:
    assert ".innerHTML" not in dom_runtime._SHADOW_DOM_FLATTENER_SCRIPT
    assert "cloneNode(true)" in dom_runtime._SHADOW_DOM_FLATTENER_SCRIPT


@pytest.mark.asyncio
@pytest.mark.regression
async def test_page_might_have_location_interstitial_uses_live_selector_probe() -> None:
    class _Page:
        url = "https://example.com/product"

        async def evaluate(self, script: str, payload: dict[str, object]):
            await _async_checkpoint()
            assert "document.querySelector" in script
            assert "selectors" in payload
            return True

    detected = await browser_page_helpers.page_might_have_location_interstitial(_Page())

    assert detected is True


@pytest.mark.regression
def test_browser_diagnostics_preserves_existing_retry_reason_and_timings() -> None:
    diagnostics = browser_runtime.build_browser_diagnostics_contract(
        diagnostics={
            "retry_reason": "empty_extraction",
            "phase_timings_ms": {"navigation": 120},
        },
        retry_reason="",
        phase_timings_ms={"content_serialization": 20},
    )

    assert diagnostics["retry_reason"] is None
    assert diagnostics["phase_timings_ms"] == {
        "navigation": 120,
        "content_serialization": 20,
    }


@pytest.mark.regression
def test_browser_diagnostics_preserves_existing_retry_reason_when_unspecified() -> None:
    diagnostics = browser_runtime.build_browser_diagnostics_contract(
        diagnostics={"retry_reason": "empty_extraction"},
        retry_reason=None,
    )

    assert diagnostics["retry_reason"] == "empty_extraction"


@pytest.mark.regression
def test_build_failed_browser_diagnostics_rejects_non_mapping_phase_timings() -> None:
    exc = RuntimeError("broken timings payload")
    setattr(exc, "browser_phase_timings_ms", [("navigation", 42)])

    diagnostics = browser_runtime.build_failed_browser_diagnostics(
        browser_reason="http-escalation",
        exc=exc,
    )

    assert diagnostics["phase_timings_ms"] == {}
    assert diagnostics["phase_timings_error"] == "invalid_phase_timings_ms:incoming"


@pytest.mark.regression
def test_build_browser_fetch_result_coerces_bad_status_and_none_content_type() -> None:
    result = build_browser_fetch_result(
        url="https://example.com",
        final_url="https://example.com",
        html="<html></html>",
        finalized={"content_type": None},
        finalized_status_code="not-a-status",
        finalized_platform_family=None,
        diagnostics={},
    )

    assert result.status_code == 0
    assert result.content_type == ""


@pytest.mark.regression
def test_browser_diagnostics_marks_invalid_phase_timing_payload() -> None:
    diagnostics = browser_runtime.build_browser_diagnostics_contract(
        diagnostics={"phase_timings_ms": {"navigation": 120}},
        phase_timings_ms=["broken"],
    )

    assert diagnostics["phase_timings_ms"] == {"navigation": 120}
    assert diagnostics["phase_timings_error"] == "invalid_phase_timings_ms:incoming"


@pytest.mark.regression
def test_browser_diagnostics_contract_clears_stale_nested_outcome_fields() -> None:
    diagnostics = browser_runtime.build_browser_diagnostics_contract(
        diagnostics={
            "browser_reason": "nested",
            "browser_outcome": "location_required",
            "failure_reason": "location_required",
        },
        browser_reason="",
        browser_outcome="",
        failure_reason="",
    )

    assert diagnostics["browser_reason"] is None
    assert diagnostics["browser_outcome"] is None
    assert diagnostics["failure_reason"] is None


@pytest.mark.asyncio
@pytest.mark.regression
async def test_wait_for_listing_readiness_treats_only_playwright_timeout_as_recoverable() -> (
    None
):
    page = _FakeExpansionPage(
        base_html="<html><body></body></html>",
        wait_for_selector_error=PlaywrightTimeoutError("listing readiness timeout"),
    )

    diagnostics = await browser_readiness.wait_for_listing_readiness_impl(
        page,
        override={
            "platform": "example",
            "selectors": [".listing-card"],
            "max_wait_ms": 250,
        },
    )

    assert diagnostics["status"] == "timed_out"
    assert diagnostics["attempted_selectors"] == [".listing-card"]


@pytest.mark.asyncio
@pytest.mark.regression
async def test_wait_for_listing_readiness_propagates_browser_closure() -> None:
    page = _FakeExpansionPage(
        base_html="<html><body></body></html>",
        wait_for_selector_error=PlaywrightError(
            "Target page, context or browser has been closed"
        ),
    )

    with pytest.raises(PlaywrightError, match="closed"):
        await browser_readiness.wait_for_listing_readiness_impl(
            page,
            override={
                "platform": "example",
                "selectors": [".listing-card"],
                "max_wait_ms": 250,
            },
        )


@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_records_navigation_timing_when_fallback_navigation_fails() -> (
    None
):
    page = _FakeExpansionPage(
        base_html="<html><body>Widget</body></html>",
        goto_failures={
            "networkidle": PlaywrightTimeoutError("primary timeout"),
            "domcontentloaded": PlaywrightError("secondary fallback failed"),
            "commit": PlaywrightError("fallback failed"),
        },
    )

    async def _fake_runtime(**_kwargs):
        await _async_checkpoint()
        return _FakeRuntime(page)

    with pytest.raises(PlaywrightError, match="fallback failed") as excinfo:
        await browser_runtime.browser_fetch(
            "https://example.com/products/widget",
            5,
            surface="ecommerce_detail",
            browser_reason="http-escalation",
            runtime_provider=_fake_runtime,
        )

    diagnostics = browser_runtime.build_failed_browser_diagnostics(
        browser_reason="http-escalation",
        exc=excinfo.value,
    )

    assert page.goto_calls == ["domcontentloaded", "commit"]
    assert diagnostics["navigation_strategy"] == "commit"
    assert diagnostics["phase_timings_ms"]["navigation"] >= 0


@pytest.mark.asyncio
@pytest.mark.regression
async def test_networkidle_navigation_uses_primary_budget_cap(patch_settings) -> None:
    patch_settings(
        browser_navigation_networkidle_timeout_ms=30000,
        browser_navigation_networkidle_primary_budget_ratio=0.4,
    )
    page = _FakeExpansionPage(
        base_html="<html><body>Widget</body></html>",
        goto_failures={"networkidle": PlaywrightTimeoutError("primary timeout")},
    )

    _response, strategy = await browser_page_flow.navigate_browser_page_impl(
        page,
        url="https://example.com/products/widget",
        timeout_seconds=5,
        phase_timings_ms={},
        readiness_policy={"navigation_wait_until": "networkidle"},
        crawler_runtime_settings=crawler_runtime_settings,
        elapsed_ms=lambda _started_at: 0,
    )

    assert strategy == "domcontentloaded"
    assert page.goto_calls == ["networkidle", "domcontentloaded"]
    assert page.goto_timeout_calls[:2] == [2000, 5000]

from __future__ import annotations

from .test_browser_expansion_runtime import Any, PlaywrightError, SimpleNamespace, _FakeExpansionPage, _FakeRuntime, _async_checkpoint, asyncio, browser_page_flow, browser_page_helpers, browser_recovery, browser_result_builder, browser_runtime, crawler_runtime_settings, pytest  # fmt: skip

@pytest.mark.regression
def test_build_failed_browser_diagnostics_marks_timeout_explicitly() -> None:
    diagnostics = browser_runtime.build_failed_browser_diagnostics(
        browser_reason="http-escalation",
        exc=TimeoutError("navigation timeout"),
    )

    assert diagnostics["browser_outcome"] == "render_timeout"
    assert diagnostics["failure_kind"] == "timeout"
    assert diagnostics["timeout_phase"] == "navigation"

@pytest.mark.regression
def test_build_failed_browser_diagnostics_preserves_failure_stage() -> None:
    exc = TimeoutError("listing readiness timeout")
    setattr(exc, "browser_failure_stage", "settle")
    setattr(exc, "browser_phase_timings_ms", {"navigation": 420})

    diagnostics = browser_runtime.build_failed_browser_diagnostics(
        browser_reason="http-escalation",
        exc=exc,
    )

    assert diagnostics["failure_stage"] == "settle"
    assert diagnostics["timeout_phase"] == "settle"
    assert diagnostics["phase_timings_ms"] == {"navigation": 420}

@pytest.mark.regression
def test_build_failed_browser_diagnostics_marks_unsupported_proxy_explicitly() -> None:
    diagnostics = browser_runtime.build_failed_browser_diagnostics(
        browser_reason="http-escalation",
        exc=RuntimeError("Browser does not support socks5 proxy authentication"),
    )

    assert diagnostics["browser_outcome"] == "navigation_failed"
    assert diagnostics["failure_kind"] == "unsupported_proxy"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_attaches_failure_diagnostics_to_direct_errors() -> None:
    async def _failing_runtime(**_kwargs):
        await _async_checkpoint()
        raise RuntimeError("runtime bootstrap failed")

    with pytest.raises(RuntimeError, match="runtime bootstrap failed") as excinfo:
        await browser_runtime.browser_fetch(
            "https://example.com/products/widget",
            5,
            surface="ecommerce_detail",
            browser_reason="http-escalation",
            runtime_provider=_failing_runtime,
        )

    diagnostics = excinfo.value.browser_diagnostics
    assert diagnostics["browser_outcome"] == "navigation_failed"
    assert diagnostics["failure_kind"] == "navigation_error"

@pytest.mark.regression
def test_build_failed_browser_diagnostics_uses_exception_proxy_mode() -> None:
    exc = RuntimeError("proxied page failed")
    setattr(exc, "browser_proxy_mode", "page")

    diagnostics = browser_runtime.build_failed_browser_diagnostics(
        browser_reason="http-escalation",
        exc=exc,
        proxy="http://proxy.example:8080",
    )

    assert diagnostics["browser_proxy_mode"] == "page"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_logs_non_usable_outcomes(
    caplog: pytest.LogCaptureFixture,
) -> None:
    page = _FakeExpansionPage(
        base_html="<html><body><h1>Empty category</h1></body></html>"
    )

    async def _fake_runtime(**_kwargs):
        await _async_checkpoint()
        return _FakeRuntime(page)

    with caplog.at_level("WARNING", logger=browser_page_flow.logger.name):
        result = await browser_runtime.browser_fetch(
            "https://example.com/empty",
            5,
            surface="ecommerce_listing",
            capture_screenshot=True,
            runtime_provider=_fake_runtime,
        )

    assert result.browser_diagnostics["browser_outcome"] == "low_content_shell"
    assert any(
        "Browser acquisition outcome=low_content_shell url=https://example.com/empty"
        in record.message
        for record in caplog.records
    )

@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_respects_disabled_screenshot_capture(
    caplog: pytest.LogCaptureFixture,
) -> None:
    page = _FakeExpansionPage(
        base_html="<html><body><h1>Empty category</h1></body></html>"
    )

    async def _fake_runtime(**_kwargs):
        await _async_checkpoint()
        return _FakeRuntime(page)

    with caplog.at_level("WARNING", logger=browser_page_flow.logger.name):
        result = await browser_runtime.browser_fetch(
            "https://example.com/empty",
            5,
            surface="ecommerce_listing",
            capture_screenshot=False,
            runtime_provider=_fake_runtime,
        )

    assert result.browser_diagnostics["browser_outcome"] == "low_content_shell"
    assert result.browser_diagnostics["phase_timings_ms"]["screenshot_capture"] == 0
    assert not result.artifacts.get("browser_screenshot_path")
    assert not any(
        "Browser acquisition outcome=low_content_shell url=https://example.com/empty"
        in record.message
        for record in caplog.records
    )

@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_surfaces_rendered_listing_evidence_counts() -> None:
    page = _FakeExpansionPage(
        base_html=(
            "<html><body>"
            "<article class='product-card'><a href='/products/widget-1'>Widget One</a><span>$10</span></article>"
            "</body></html>"
        ),
        selector_counts={".product-card": 1},
        card_count=1,
        rendered_listing_fragments=[
            "<article class='product-card'><a href='/products/widget-1'>Widget One</a><span>$10</span></article>"
        ],
    )
    page.url = "https://example.com/collections/widgets"

    async def _fake_runtime(**_kwargs):
        await _async_checkpoint()
        return _FakeRuntime(page)

    result = await browser_runtime.browser_fetch(
        "https://example.com/collections/widgets",
        5,
        surface="ecommerce_listing",
        runtime_provider=_fake_runtime,
    )

    assert result.browser_diagnostics["rendered_listing_fragment_count"] == 1
    assert result.browser_diagnostics["listing_visual_element_count"] >= 0
    assert (
        result.browser_diagnostics["extractable_listing_evidence"][
            "rendered_listing_fragments"
        ]
        == 1
    )

@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_fetch_bounds_listing_artifact_capture_time(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    patch_settings,
) -> None:
    patch_settings(browser_artifact_capture_timeout_ms=50)
    page = _FakeExpansionPage(
        base_html=(
            "<html><body>"
            "<article class='product-card'><a href='/products/widget-1'>Widget One</a></article>"
            "</body></html>"
        ),
        selector_counts={".product-card": 1},
        card_count=1,
    )
    page.url = "https://example.com/collections/widgets"

    async def _fake_runtime(**_kwargs):
        await _async_checkpoint()
        return _FakeRuntime(page)

    async def _slow_rendered_listing_fragments(*args, **kwargs):
        del args, kwargs
        await asyncio.sleep(0.2)
        return ["<article><a href='/products/widget-1'>Widget One</a></article>"]

    async def _slow_listing_visual_elements(*args, **kwargs):
        del args, kwargs
        await asyncio.sleep(0.2)
        return [{"tag": "a"}]

    monkeypatch.setattr(
        browser_recovery,
        "capture_rendered_listing_fragments",
        _slow_rendered_listing_fragments,
    )
    monkeypatch.setattr(
        browser_page_helpers,
        "capture_listing_visual_elements",
        _slow_listing_visual_elements,
    )
    with caplog.at_level("WARNING", logger=browser_result_builder.logger.name):
        result = await browser_runtime.browser_fetch(
            "https://example.com/collections/widgets",
            5,
            surface="ecommerce_listing",
            runtime_provider=_fake_runtime,
        )

    assert result.browser_diagnostics["rendered_listing_fragment_count"] == 0
    assert result.browser_diagnostics["listing_visual_element_count"] == 0
    assert (
        result.browser_diagnostics["phase_timings_ms"][
            "rendered_listing_fragment_capture"
        ]
        >= 0
    )
    assert result.browser_diagnostics["phase_timings_ms"]["listing_visual_capture"] >= 0
    assert result.browser_diagnostics["listing_artifact_capture"] == {
        "rendered_listing_fragment_capture": {"status": "timeout"},
        "listing_visual_capture": {"status": "timeout"},
    }
    assert any(
        "Timed out during rendered_listing_fragment_capture" in record.message
        for record in caplog.records
    )

@pytest.mark.asyncio
@pytest.mark.regression
async def test_capture_listing_artifact_with_timeout_reports_playwright_error(
    caplog: pytest.LogCaptureFixture,
) -> None:
    async def _boom():
        await _async_checkpoint()
        raise PlaywrightError("Target page, context or browser has been closed")

    with caplog.at_level("DEBUG", logger=browser_result_builder.logger.name):
        (
            artifacts,
            diagnostics,
        ) = await browser_result_builder.capture_listing_artifact_with_timeout(
            _boom(),
            stage="listing_visual_capture",
            url="https://example.com/collections/widgets",
        )

    assert artifacts == []
    assert diagnostics == {"status": "closed"}
    assert any(
        "Listing artifact capture Playwright error" in record.message
        for record in caplog.records
    )

@pytest.mark.asyncio
@pytest.mark.regression
async def test_capture_rendered_listing_fragments_returns_fragment_html() -> None:
    class _RegressionPage:
        async def evaluate(self, script: str, arg: Any | None = None) -> list[str]:
            await _async_checkpoint()
            del arg
            assert "const selectors = Array.isArray(args?.selectors)" in script
            assert "const seenFragments = new Set();" in script
            assert "fragments.push(fragment);" in script
            return [
                "<article><a href='https://example.com/products/widget-one'>Widget One</a><span>$19.99</span></article>"
            ]

    rows = await browser_recovery.capture_rendered_listing_fragments(
        _RegressionPage(),
        surface="ecommerce_listing",
        limit=5,
    )

    assert rows == [
        "<article><a href='https://example.com/products/widget-one'>Widget One</a><span>$19.99</span></article>"
    ]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_capture_rendered_listing_fragments_ignores_non_listing_surfaces() -> (
    None
):
    class _RegressionPage:
        async def evaluate(self, script: str, arg: Any | None = None) -> list[str]:
            await _async_checkpoint()
            raise AssertionError("evaluate should not be called")

    rows = await browser_recovery.capture_rendered_listing_fragments(
        _RegressionPage(),
        surface="ecommerce_detail",
        limit=5,
    )

    assert rows == []

@pytest.mark.asyncio
@pytest.mark.regression
async def test_emit_challenge_activity_randomizes_mouse_targets(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    move_calls: list[tuple[int, int]] = []
    wheel_calls: list[tuple[int, int]] = []
    wait_calls: list[int] = []

    class _Mouse:
        async def move(self, x: int, y: int) -> None:
            await _async_checkpoint()
            move_calls.append((x, y))

        async def wheel(self, delta_x: int, delta_y: int) -> None:
            await _async_checkpoint()
            wheel_calls.append((delta_x, delta_y))

    class _Page:
        mouse = _Mouse()

        async def evaluate(self, script: str, arg: Any | None = None) -> dict[str, int]:
            await _async_checkpoint()
            del script, arg
            return {"width": 900, "height": 700}

        async def wait_for_timeout(self, delay_ms: int) -> None:
            await _async_checkpoint()
            wait_calls.append(delay_ms)

    random_counter = {"value": 0}

    def _fake_randbelow(limit: int) -> int:
        random_counter["value"] += 1
        return random_counter["value"] % max(1, int(limit))

    monkeypatch.setattr(browser_recovery.secrets, "randbelow", _fake_randbelow)

    await browser_recovery._emit_challenge_activity(_Page())

    assert len(move_calls) == 1 + (
        int(crawler_runtime_settings.challenge_activity_jitter_moves)
        * int(crawler_runtime_settings.challenge_activity_mouse_steps)
    )
    assert all(len(call) == 2 for call in move_calls)
    assert len(set(move_calls)) > 2
    assert wait_calls
    assert wheel_calls == [
        (0, int(crawler_runtime_settings.challenge_activity_scroll_px))
    ]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_emit_challenge_activity_ignores_negative_scroll(
    monkeypatch: pytest.MonkeyPatch,
    patch_settings,
) -> None:
    wheel_calls: list[tuple[int, int]] = []

    class _Mouse:
        async def move(self, x: int, y: int, *, steps: int) -> None:
            await _async_checkpoint()

        async def wheel(self, delta_x: int, delta_y: int) -> None:
            await _async_checkpoint()
            wheel_calls.append((delta_x, delta_y))

    class _Page:
        mouse = _Mouse()

        async def evaluate(self, script: str, arg: Any | None = None) -> dict[str, int]:
            await _async_checkpoint()
            del script, arg
            return {"width": 900, "height": 700}

        async def wait_for_timeout(self, delay_ms: int) -> None:
            await _async_checkpoint()

    monkeypatch.setattr(browser_recovery.secrets, "randbelow", lambda limit: 0)
    patch_settings(challenge_activity_scroll_px=-120)
    await browser_recovery._emit_challenge_activity(_Page())

    assert wheel_calls == []

@pytest.mark.asyncio
@pytest.mark.regression
async def test_emit_browser_behavior_activity_adds_scroll_physics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    move_calls: list[tuple[int, int]] = []
    wheel_calls: list[tuple[int, int]] = []
    wait_calls: list[int] = []

    class _Mouse:
        async def move(self, x: int, y: int) -> None:
            await _async_checkpoint()
            move_calls.append((x, y))

        async def wheel(self, delta_x: int, delta_y: int) -> None:
            await _async_checkpoint()
            wheel_calls.append((delta_x, delta_y))

    class _Page:
        mouse = _Mouse()

        async def evaluate(self, script: str, arg: Any | None = None) -> dict[str, int]:
            await _async_checkpoint()
            del script, arg
            return {"width": 900, "height": 700}

        async def wait_for_timeout(self, delay_ms: int) -> None:
            await _async_checkpoint()
            wait_calls.append(delay_ms)

    monkeypatch.setattr(browser_recovery.secrets, "randbelow", lambda limit: 0)
    diagnostics = await browser_recovery.emit_browser_behavior_activity(_Page())

    assert diagnostics["enabled"] is True
    assert int(diagnostics["pointer_moves"]) == len(move_calls)
    assert int(diagnostics["scroll_steps"]) == int(
        crawler_runtime_settings.browser_behavior_scroll_steps
    )
    assert len(wheel_calls) == 1 + int(
        crawler_runtime_settings.browser_behavior_scroll_steps
    )
    assert wait_calls

@pytest.mark.asyncio
@pytest.mark.regression
async def test_emit_browser_behavior_activity_ignores_scroll_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _Mouse:
        async def move(self, x: int, y: int) -> None:
            await _async_checkpoint()

        async def wheel(self, delta_x: int, delta_y: int) -> None:
            await _async_checkpoint()

    class _Page:
        mouse = _Mouse()

        async def evaluate(self, script: str, arg: Any | None = None) -> dict[str, int]:
            await _async_checkpoint()
            del script, arg
            return {"width": 900, "height": 700}

    async def _raise_scroll_failure(_page: object) -> int:
        await _async_checkpoint()
        raise RuntimeError("scroll failed")

    monkeypatch.setattr(browser_recovery.secrets, "randbelow", lambda limit: 0)
    monkeypatch.setattr(browser_recovery, "_emit_scroll_physics", _raise_scroll_failure)

    diagnostics = await browser_recovery.emit_browser_behavior_activity(_Page())

    assert diagnostics["enabled"] is True
    assert int(diagnostics["scroll_steps"]) == 0

@pytest.mark.regression
def test_should_run_behavior_realism_skips_detail_shell_retry_for_real_chrome() -> None:
    assert (
        browser_runtime._should_run_behavior_realism(
            "real_chrome",
            browser_reason="detail-shell retry",
        )
        is False
    )

@pytest.mark.regression
def test_should_run_behavior_realism_for_real_chrome_with_vendor_block() -> None:
    assert (
        browser_runtime._should_run_behavior_realism(
            "real_chrome",
            browser_reason="vendor-block:akamai",
        )
        is True
    )

@pytest.mark.asyncio
@pytest.mark.regression
async def test_browser_behavior_realism_is_timeout_bounded(
    patch_settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _slow_behavior(_page):
        await asyncio.sleep(1)
        return {"enabled": True}

    patch_settings(browser_behavior_realism_timeout_seconds=0.01)
    monkeypatch.setattr(
        browser_runtime,
        "emit_browser_behavior_activity",
        _slow_behavior,
    )

    diagnostics = await browser_runtime._emit_browser_behavior_activity_bounded(
        object()
    )

    assert isinstance(diagnostics, dict)
    assert diagnostics["enabled"] is True
    assert diagnostics["timed_out"] is True
    assert "timeout_seconds" in diagnostics
    assert isinstance(diagnostics["timeout_seconds"], float)
    assert diagnostics["timeout_seconds"] == pytest.approx(0.01)

@pytest.mark.asyncio
@pytest.mark.regression
async def test_type_text_like_human_types_one_character_at_a_time(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    typed: list[str] = []
    clicks: list[int] = []

    class _Locator:
        async def click(self, **kwargs) -> None:
            await _async_checkpoint()
            timeout = kwargs.get("timeout")
            clicks.append(timeout)

    class _Keyboard:
        async def type(self, value: str) -> None:
            await _async_checkpoint()
            typed.append(value)

    class _Page:
        keyboard = _Keyboard()

        def locator(self, selector: str) -> _Locator:
            assert selector == "input[name=q]"
            return _Locator()

        async def wait_for_timeout(self, delay_ms: int) -> None:
            await _async_checkpoint()
            assert delay_ms >= 0

    monkeypatch.setattr(browser_recovery.secrets, "randbelow", lambda limit: 0)

    diagnostics = await browser_recovery.type_text_like_human(
        _Page(),
        "input[name=q]",
        "shoe",
    )

    assert diagnostics == {"typed_chars": 4}
    assert typed == ["s", "h", "o", "e"]
    assert clicks == [int(crawler_runtime_settings.traversal_click_timeout_ms)]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_recover_browser_challenge_keeps_original_response_when_retry_stays_blocked() -> (
    None
):
    original_response = SimpleNamespace(status=403, name="original")
    retried_response = SimpleNamespace(status=200, name="retried")

    class _Page:
        def __init__(self) -> None:
            self.mouse = None
            self.goto_calls = 0

        async def goto(self, *_args, **_kwargs):
            await _async_checkpoint()
            self.goto_calls += 1
            return retried_response

        async def wait_for_timeout(self, _ms: int) -> None:
            await _async_checkpoint()
            return None

    page = _Page()

    async def _get_page_html(_page: Any) -> str:
        await _async_checkpoint()
        return "<html><body>blocked</body></html>"

    async def _classify_blocked_page(_html: str, _status_code: int):
        await _async_checkpoint()
        return SimpleNamespace(blocked=True, provider_hits=[])

    result = await browser_recovery.recover_browser_challenge(
        page,
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

    assert result is original_response
    assert page.goto_calls == 1

@pytest.mark.asyncio
@pytest.mark.regression
async def test_recover_browser_challenge_propagates_inner_timeout_errors() -> None:
    response = SimpleNamespace(status=403)

    class _Page:
        mouse = None

        async def wait_for_timeout(self, _ms: int) -> None:
            await _async_checkpoint()

    html_calls = 0

    async def _get_page_html(_page: Any) -> str:
        nonlocal html_calls
        await _async_checkpoint()
        html_calls += 1
        if html_calls > 1:
            raise asyncio.TimeoutError("inner html timeout")
        return "<html><body>blocked</body></html>"

    async def _classify_blocked_page(_html: str, _status_code: int):
        await _async_checkpoint()
        return SimpleNamespace(blocked=True, provider_hits=[])

    recovered = await browser_recovery.recover_browser_challenge(
        _Page(),
        url="https://example.com/products/widget",
        response=response,
        timeout_seconds=5,
        phase_timings_ms={},
        challenge_wait_max_seconds=1,
        challenge_poll_interval_ms=100,
        navigation_timeout_ms=1000,
        elapsed_ms=lambda _started_at: 0,
        classify_blocked_page=_classify_blocked_page,
        get_page_html=_get_page_html,
    )

    assert recovered is response

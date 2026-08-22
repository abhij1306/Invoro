from __future__ import annotations

from .test_crawl_fetch_runtime import AsyncMock, FetchRuntimeContext, HostProtectionPolicy, PageFetchResult, PlaywrightError, _as_async, _default_fetch_context, asyncio, browser_policy, crawl_fetch_runtime, httpx, pytest, time  # fmt: skip

pytest_plugins = ["tests.component.test_crawl_fetch_runtime"]


@pytest.mark.asyncio
@pytest.mark.component
async def test_explicit_browser_preference_skips_host_handoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await crawl_fetch_runtime.reset_fetch_runtime_state()
    url = "https://example.com/products/widget"
    browser_engines: list[str] = []

    @_as_async
    def _unexpected_export_cookie_header_for_domain(*_args, **_kwargs):
        raise AssertionError("explicit browser run should not export handoff cookies")

    @_as_async
    def _unexpected_curl(*_args, **_kwargs):
        raise AssertionError("explicit browser run should not use HTTP handoff")

    @_as_async
    def _browser_fetch(request_url: str, _timeout_seconds: float, **kwargs):
        browser_engines.append(str(kwargs.get("browser_engine")))
        return PageFetchResult(
            url=request_url,
            final_url=request_url,
            html="<html><body>rendered</body></html>",
            status_code=200,
            method="browser",
            browser_diagnostics={"browser_engine": kwargs.get("browser_engine")},
        )

    monkeypatch.setattr(
        crawl_fetch_runtime,
        "load_host_protection_policy",
        AsyncMock(
            return_value=HostProtectionPolicy(
                host="example.com",
                prefer_browser=True,
                real_chrome_success=True,
            )
        ),
    )
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "export_cookie_header_for_domain",
        _unexpected_export_cookie_header_for_domain,
    )
    monkeypatch.setattr(crawl_fetch_runtime, "_curl_fetch", _unexpected_curl)
    monkeypatch.setattr(crawl_fetch_runtime, "_browser_fetch", _browser_fetch)
    try:
        result = await crawl_fetch_runtime.fetch_page(
            url,
            surface="ecommerce_detail",
            prefer_browser=True,
            forced_browser_engine="real_chrome",
        )
    finally:
        await crawl_fetch_runtime.reset_fetch_runtime_state()

    assert result.method == "browser"
    assert browser_engines == ["real_chrome"]


@pytest.mark.asyncio
@pytest.mark.component
async def test_fetch_page_emits_http_strategy_and_escalation_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await crawl_fetch_runtime.reset_fetch_runtime_state()
    url = "https://example.com/products/widget"
    events: list[tuple[str, str]] = []

    @_as_async
    def _on_event(level: str, message: str) -> None:
        events.append((level, message))

    @_as_async
    def _fake_curl(request_url: str, timeout: float, *, proxy: str | None = None):
        del timeout, proxy
        return PageFetchResult(
            url=request_url,
            final_url=request_url,
            html="<html><body>thin shell</body></html>",
            status_code=200,
            method="curl_cffi",
            blocked=False,
        )

    @_as_async
    def _fake_browser(request_url, timeout, **kwargs):
        del timeout, kwargs
        return PageFetchResult(
            url=request_url,
            final_url=request_url,
            html="<html><body><h1>Widget Prime</h1></body></html>",
            status_code=200,
            method="browser",
            blocked=False,
            browser_diagnostics={"browser_engine": "patchright"},
        )

    monkeypatch.setattr(
        crawl_fetch_runtime,
        "load_host_protection_policy",
        AsyncMock(return_value=HostProtectionPolicy(host="example.com")),
    )
    monkeypatch.setattr(crawl_fetch_runtime, "_curl_fetch", _fake_curl)
    monkeypatch.setattr(crawl_fetch_runtime, "_browser_fetch", _fake_browser)
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "_should_escalate_to_browser_async",
        AsyncMock(return_value=True),
    )
    try:
        result = await crawl_fetch_runtime.fetch_page(
            url,
            surface="ecommerce_detail",
            on_event=_on_event,
        )
    finally:
        await crawl_fetch_runtime.reset_fetch_runtime_state()

    assert result.method == "browser"
    messages = [message for _level, message in events]
    assert any(
        message.startswith("Acquisition strategy: http-first") for message in messages
    )
    assert any(
        "curl=primary, httpx_fallback=on_transport_failure" in message
        for message in messages
    )
    assert any("HTTP fetch via" in message for message in messages)
    assert any(
        "Escalating to browser after HTTP result" in message for message in messages
    )


@pytest.mark.asyncio
@pytest.mark.component
async def test_fetch_page_http_only_returns_retryable_status_without_hidden_retry(
    monkeypatch: pytest.MonkeyPatch,
    patch_settings,
) -> None:
    await crawl_fetch_runtime.reset_fetch_runtime_state()
    patch_settings(force_httpx=True)
    url = "https://example.com/products/widget"
    http_attempts: list[int] = []

    @_as_async
    def _http_retryable_status(
        request_url: str,
        timeout: float,
        *,
        proxy: str | None = None,
    ):
        del timeout, proxy
        http_attempts.append(1)
        return PageFetchResult(
            url=request_url,
            final_url=request_url,
            html="<html><body>retry me</body></html>",
            status_code=503,
            method="httpx",
            blocked=False,
        )

    @_as_async
    def _always_escalate(*args, **kwargs):
        del args, kwargs
        return True

    @_as_async
    def _unexpected_browser(request_url, timeout, **kwargs):
        raise AssertionError(
            f"browser should not run for http_only retry path: {request_url} {timeout} {kwargs}"
        )

    monkeypatch.setattr(crawl_fetch_runtime, "_http_fetch", _http_retryable_status)
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "_should_escalate_to_browser_async",
        _always_escalate,
    )
    monkeypatch.setattr(crawl_fetch_runtime, "_browser_fetch", _unexpected_browser)

    try:
        result = await crawl_fetch_runtime.fetch_page(
            url,
            surface="ecommerce_detail",
            fetch_mode="http_only",
        )
    finally:
        await crawl_fetch_runtime.reset_fetch_runtime_state()

    assert result.method == "httpx"
    assert result.status_code == 503
    assert len(http_attempts) == 1


@pytest.mark.asyncio
@pytest.mark.component
async def test_fetch_page_retries_patchright_http2_protocol_error_with_real_chrome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await crawl_fetch_runtime.reset_fetch_runtime_state()
    url = "https://www.bestbuy.com/product/widget"
    events: list[tuple[str, str]] = []
    browser_engines: list[str] = []

    @_as_async
    def _on_event(level: str, message: str) -> None:
        events.append((level, message))

    @_as_async
    def _failing_curl(request_url: str, _timeout: float, *, proxy: str | None = None):
        del request_url, _timeout, proxy
        raise httpx.ReadTimeout("curl timed out")

    @_as_async
    def _failing_http(request_url: str, _timeout: float, *, proxy: str | None = None):
        del request_url, _timeout, proxy
        raise httpx.ReadTimeout("httpx timed out")

    @_as_async
    def _browser_fetch(request_url, _timeout, **kwargs):
        del _timeout
        engine = str(kwargs.get("browser_engine") or "")
        browser_engines.append(engine)
        if engine == "patchright":
            raise PlaywrightError(
                f"Page.goto: net::ERR_HTTP2_PROTOCOL_ERROR at {request_url}"
            )
        return PageFetchResult(
            url=request_url,
            final_url=request_url,
            html="<html><body><h1>BestBuy Widget</h1></body></html>",
            status_code=200,
            method="browser",
            blocked=False,
            browser_diagnostics={"browser_engine": engine},
        )

    monkeypatch.setattr(crawl_fetch_runtime, "_curl_fetch", _failing_curl)
    monkeypatch.setattr(crawl_fetch_runtime, "_http_fetch", _failing_http)
    monkeypatch.setattr(crawl_fetch_runtime, "_browser_fetch", _browser_fetch)
    monkeypatch.setattr(
        crawl_fetch_runtime, "real_chrome_browser_available", lambda: True
    )

    try:
        result = await crawl_fetch_runtime.fetch_page(
            url,
            surface="ecommerce_detail",
            on_event=_on_event,
        )
    finally:
        await crawl_fetch_runtime.reset_fetch_runtime_state()

    assert result.method == "browser"
    assert result.browser_diagnostics["browser_engine"] == "real_chrome"
    assert browser_engines == ["patchright", "real_chrome"]
    messages = [message for _level, message in events]
    assert any("Patchright navigation failed" in message for message in messages)


@pytest.mark.asyncio
@pytest.mark.component
async def test_fetch_page_uses_remaining_timeout_budget_across_http_and_browser_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "https://example.com/products/widget"
    browser_timeouts: list[float] = []

    @_as_async
    def _load_policy(*_args, **_kwargs):
        return HostProtectionPolicy(host="example.com")

    async def _vendor_blocked_curl(
        request_url: str,
        timeout: float,
        *,
        proxy: str | None = None,
        cookie_header: str | None = None,
    ):
        del proxy, cookie_header
        await asyncio.sleep(0.06)
        return PageFetchResult(
            url=request_url,
            final_url=request_url,
            html="<html><body>blocked</body></html>",
            status_code=403,
            method="curl_cffi",
            blocked=True,
            headers={"x-datadome": "blocked"},
        )

    async def _browser_fetch(request_url: str, browser_budget: float, **kwargs):
        del request_url
        browser_timeouts.append(browser_budget)
        engine = str(kwargs.get("browser_engine") or "")
        if engine == "patchright":
            await asyncio.sleep(0.06)
            raise TimeoutError("patchright budget exhausted")
        return PageFetchResult(
            url=url,
            final_url=url,
            html="<html><body><h1>Rendered</h1></body></html>",
            status_code=200,
            method="browser",
            blocked=False,
            browser_diagnostics={"browser_engine": engine},
        )

    monkeypatch.setattr(crawl_fetch_runtime, "_curl_fetch", _vendor_blocked_curl)
    monkeypatch.setattr(crawl_fetch_runtime, "_browser_fetch", _browser_fetch)
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "load_host_protection_policy",
        _load_policy,
    )
    monkeypatch.setattr(crawl_fetch_runtime, "_update_host_result_memory", AsyncMock())
    monkeypatch.setattr(crawl_fetch_runtime, "note_host_hard_block", AsyncMock())
    monkeypatch.setattr(crawl_fetch_runtime, "wait_for_host_slot", AsyncMock())
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "browser_engine_attempts",
        lambda **_kwargs: ["patchright", "real_chrome"],
    )
    monkeypatch.setattr(
        crawl_fetch_runtime.crawler_runtime_settings,
        "browser_post_block_cooldown_ms",
        0,
    )

    result = await crawl_fetch_runtime.fetch_page(
        url,
        timeout_seconds=0.2,
        surface="ecommerce_detail",
    )

    assert result.browser_diagnostics["browser_engine"] == "real_chrome"
    assert browser_timeouts[0] < 0.16
    assert browser_timeouts[1] < browser_timeouts[0]


@pytest.mark.asyncio
@pytest.mark.component
async def test_run_browser_attempts_skips_engine_when_shared_deadline_expired(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _default_fetch_context()
    context.deadline_monotonic = time.perf_counter() - 1.0
    browser_fetch = AsyncMock()
    host_slot = AsyncMock()

    monkeypatch.setattr(crawl_fetch_runtime, "_browser_fetch", browser_fetch)
    monkeypatch.setattr(crawl_fetch_runtime, "wait_for_host_slot", host_slot)

    with pytest.raises(TimeoutError, match="budget exhausted before patchright"):
        await crawl_fetch_runtime.run_browser_attempts(
            context,
            reason="test shared deadline",
            host_policy=HostProtectionPolicy(host="example.com"),
        )

    host_slot.assert_not_awaited()
    browser_fetch.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.component
async def test_run_browser_attempts_caps_patchright_probe_timeout_for_vendor_block(
    monkeypatch: pytest.MonkeyPatch,
    patch_settings,
) -> None:
    patch_settings(browser_vendor_block_probe_timeout_seconds=12.0)
    browser_calls: list[tuple[str, float]] = []
    context = FetchRuntimeContext(
        url="https://example.com/products/widget",
        resolved_timeout=30.0,
        deadline_monotonic=time.perf_counter() + 30.0,
        run_id=None,
        surface="ecommerce_detail",
        traversal_mode=None,
        max_pages=1,
        max_scrolls=1,
        max_records=None,
        on_event=None,
        browser_reason=None,
        requested_fields=[],
        listing_recovery_mode=None,
        proxies=[None],
        proxy_profile={},
        traversal_required=False,
        fetch_mode="browser_only",
        runtime_policy={},
        host_memory_ttl_seconds=crawl_fetch_runtime.crawler_runtime_settings.coerce_host_memory_ttl_seconds(
            None
        ),
    )

    @_as_async
    def _fake_browser_fetch(url: str, browser_timeout: float, **kwargs):
        del url
        engine = str(kwargs.get("browser_engine") or "")
        browser_calls.append((engine, browser_timeout))
        if engine == "patchright":
            raise TimeoutError("patchright budget exhausted")
        return PageFetchResult(
            url="https://example.com/products/widget",
            final_url="https://example.com/products/widget",
            html="<html><body><h1>Rendered</h1></body></html>",
            status_code=200,
            method="browser",
            blocked=False,
            browser_diagnostics={"browser_engine": engine},
        )

    monkeypatch.setattr(crawl_fetch_runtime, "_browser_fetch", _fake_browser_fetch)
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "browser_engine_attempts",
        lambda **_kwargs: ["patchright", "real_chrome"],
    )
    monkeypatch.setattr(crawl_fetch_runtime, "wait_for_host_slot", AsyncMock())
    monkeypatch.setattr(crawl_fetch_runtime, "note_host_hard_block", AsyncMock())
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "load_host_protection_policy",
        AsyncMock(
            return_value=HostProtectionPolicy(
                host="example.com",
                patchright_blocked=True,
                prefer_browser=True,
                last_block_vendor="datadome",
            )
        ),
    )
    monkeypatch.setattr(
        crawl_fetch_runtime.crawler_runtime_settings,
        "browser_post_block_cooldown_ms",
        0,
    )

    result = await crawl_fetch_runtime.run_browser_attempts(
        context,
        reason="vendor-block:datadome",
        host_policy=HostProtectionPolicy(
            host="example.com",
            patchright_blocked=True,
            prefer_browser=True,
            last_block_vendor="datadome",
        ),
    )

    assert result.browser_diagnostics["browser_engine"] == "real_chrome"
    assert browser_calls[0][0] == "patchright"
    assert browser_calls[0][1] == pytest.approx(12.0, abs=0.05)
    assert browser_calls[1][0] == "real_chrome"
    assert browser_calls[1][1] < 30.0


@pytest.mark.asyncio
@pytest.mark.component
async def test_run_browser_attempts_caps_patchright_probe_when_real_chrome_is_queued(
    monkeypatch: pytest.MonkeyPatch,
    patch_settings,
) -> None:
    """Vendor-blocked Patchright probes stay short when real Chrome is queued.

    Otherwise Patchright can consume most of the acquisition budget and leave
    the stronger engine too little time to navigate.
    """
    patch_settings(browser_vendor_block_probe_timeout_seconds=12.0)
    browser_calls: list[tuple[str, float]] = []
    context = FetchRuntimeContext(
        url="https://example.com/products/widget",
        resolved_timeout=30.0,
        deadline_monotonic=time.perf_counter() + 30.0,
        run_id=None,
        surface="ecommerce_detail",
        traversal_mode=None,
        max_pages=1,
        max_scrolls=1,
        max_records=None,
        on_event=None,
        browser_reason=None,
        requested_fields=[],
        listing_recovery_mode=None,
        proxies=[None],
        proxy_profile={},
        traversal_required=False,
        fetch_mode="browser_only",
        runtime_policy={},
        host_memory_ttl_seconds=crawl_fetch_runtime.crawler_runtime_settings.coerce_host_memory_ttl_seconds(
            None
        ),
    )

    @_as_async
    def _fake_browser_fetch(url: str, browser_timeout: float, **kwargs):
        del url
        engine = str(kwargs.get("browser_engine") or "")
        browser_calls.append((engine, browser_timeout))
        return PageFetchResult(
            url="https://example.com/products/widget",
            final_url="https://example.com/products/widget",
            html="<html><body><h1>Rendered</h1></body></html>",
            status_code=200,
            method="browser",
            blocked=False,
            browser_diagnostics={"browser_engine": engine},
        )

    monkeypatch.setattr(crawl_fetch_runtime, "_browser_fetch", _fake_browser_fetch)
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "browser_engine_attempts",
        lambda **_kwargs: ["patchright", "real_chrome"],
    )
    monkeypatch.setattr(crawl_fetch_runtime, "wait_for_host_slot", AsyncMock())
    monkeypatch.setattr(crawl_fetch_runtime, "note_host_hard_block", AsyncMock())
    fresh_policy = HostProtectionPolicy(host="example.com")
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "load_host_protection_policy",
        AsyncMock(return_value=fresh_policy),
    )
    monkeypatch.setattr(
        crawl_fetch_runtime.crawler_runtime_settings,
        "browser_post_block_cooldown_ms",
        0,
    )

    result = await crawl_fetch_runtime.run_browser_attempts(
        context,
        reason="vendor-block:cloudflare",
        host_policy=fresh_policy,
    )

    assert result.browser_diagnostics["browser_engine"] == "patchright"
    assert browser_calls[0][0] == "patchright"
    assert browser_calls[0][1] <= 12.1
    # Real Chrome must not be called when patchright succeeds.
    assert len(browser_calls) == 1


@pytest.mark.component
def test_browser_attempt_timeout_skips_patchright_probe_cap_without_vendor(
    patch_settings,
) -> None:
    patch_settings(browser_vendor_block_probe_timeout_seconds=1.0)
    context = _default_fetch_context()

    timeout_seconds = browser_policy.browser_attempt_timeout_seconds(
        context=context,
        reason="vendor-block:",
        browser_engine="patchright",
        engine_attempts=["patchright", "real_chrome"],
        host_policy=HostProtectionPolicy(
            host="example.com",
            patchright_blocked=True,
            prefer_browser=True,
            last_block_vendor="datadome",
        ),
    )

    assert timeout_seconds > 1.5


@pytest.mark.component
def test_browser_attempt_timeout_caps_patchright_when_real_chrome_is_queued(
    patch_settings,
) -> None:
    patch_settings(browser_vendor_block_probe_timeout_seconds=1.0)
    context = _default_fetch_context()

    timeout_seconds = browser_policy.browser_attempt_timeout_seconds(
        context=context,
        reason="vendor-block:akamai",
        browser_engine="patchright",
        engine_attempts=["patchright", "real_chrome"],
        host_policy=HostProtectionPolicy(host="example.com"),
    )

    assert timeout_seconds <= 1.1


@pytest.mark.asyncio
@pytest.mark.component
async def test_fetch_page_skips_cookie_handoff_when_proxy_identity_would_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await crawl_fetch_runtime.reset_fetch_runtime_state()
    url = "https://example.com/products/widget"
    browser_calls: list[str | None] = []

    @_as_async
    def _unexpected_export(*_args, **_kwargs):
        raise AssertionError("proxy handoff must not reuse unscoped domain cookies")

    @_as_async
    def _browser_ok(request_url, timeout, **kwargs):
        del request_url, timeout
        browser_calls.append(kwargs.get("proxy"))
        return PageFetchResult(
            url=url,
            final_url=url,
            html="<html><body>Rendered</body></html>",
            status_code=200,
            method="browser",
            blocked=False,
            browser_diagnostics={"browser_engine": "real_chrome"},
        )

    monkeypatch.setattr(
        crawl_fetch_runtime,
        "load_host_protection_policy",
        AsyncMock(
            return_value=HostProtectionPolicy(
                host="example.com",
                prefer_browser=True,
                real_chrome_success=True,
            )
        ),
    )
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "export_cookie_header_for_domain",
        _unexpected_export,
    )
    monkeypatch.setattr(crawl_fetch_runtime, "_browser_fetch", _browser_ok)
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "browser_engine_attempts",
        lambda **_kwargs: ["real_chrome"],
    )
    try:
        result = await crawl_fetch_runtime.fetch_page(
            url,
            surface="ecommerce_detail",
            proxy_list=["http://proxy-a"],
        )
    finally:
        await crawl_fetch_runtime.reset_fetch_runtime_state()

    assert result.method == "browser"
    assert browser_calls == ["http://proxy-a"]

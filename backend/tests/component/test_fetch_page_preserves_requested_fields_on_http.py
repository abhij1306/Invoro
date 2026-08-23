from __future__ import annotations

from .test_crawl_fetch_runtime import AsyncMock, FetchRuntimeContext, HostProtectionPolicy, PageFetchResult, _as_async, _default_fetch_context, browser_policy, crawl_fetch_runtime, pytest, time  # fmt: skip

pytest_plugins = ["tests.component.test_crawl_fetch_runtime"]


@pytest.mark.asyncio
@pytest.mark.component
async def test_fetch_page_preserves_requested_fields_on_http_to_browser_escalation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_requested_fields: list[str] = []

    @_as_async
    def _fake_curl(url: str, timeout_seconds: float, *, proxy: str | None = None):
        del timeout_seconds, proxy
        return PageFetchResult(
            url=url,
            final_url=url,
            html="<html><body>challenge</body></html>",
            status_code=403,
            method="curl_cffi",
            blocked=False,
        )

    @_as_async
    def _fake_should_escalate(*args, **kwargs):
        del args, kwargs
        return True

    @_as_async
    def _fake_run_browser_attempts(
        context,
        *,
        reason: str,
        requested_fields: list[str] | None = None,
        listing_recovery_mode: str | None = None,
        capture_page_markdown: bool = False,
        proxies: list[str | None] | None = None,
        **_kwargs,
    ):
        del (
            context,
            reason,
            listing_recovery_mode,
            capture_page_markdown,
            proxies,
            _kwargs,
        )
        nonlocal captured_requested_fields
        captured_requested_fields = list(requested_fields or [])
        return PageFetchResult(
            url="https://example.com/products/widget",
            final_url="https://example.com/products/widget",
            html="<html><body><h1>Widget</h1></body></html>",
            status_code=200,
            method="browser",
        )

    monkeypatch.setattr(crawl_fetch_runtime, "_curl_fetch", _fake_curl)
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "_should_escalate_to_browser_async",
        _fake_should_escalate,
    )
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "run_browser_attempts",
        _fake_run_browser_attempts,
    )

    await crawl_fetch_runtime.fetch_page(
        "https://example.com/products/widget",
        surface="ecommerce_detail",
        requested_fields=["product measurements"],
    )

    assert captured_requested_fields == ["product measurements"]


@pytest.mark.asyncio
@pytest.mark.component
async def test_fetch_page_preserves_requested_fields_on_browser_first_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_requested_fields: list[str] = []

    @_as_async
    def _fake_run_browser_attempts(
        context,
        *,
        reason: str,
        requested_fields: list[str] | None = None,
        listing_recovery_mode: str | None = None,
        capture_page_markdown: bool = False,
        proxies: list[str | None] | None = None,
        **_kwargs,
    ):
        del (
            context,
            reason,
            listing_recovery_mode,
            capture_page_markdown,
            proxies,
            _kwargs,
        )
        nonlocal captured_requested_fields
        captured_requested_fields = list(requested_fields or [])
        return PageFetchResult(
            url="https://example.com/products/widget",
            final_url="https://example.com/products/widget",
            html="<html><body><h1>Widget</h1></body></html>",
            status_code=200,
            method="browser",
        )

    monkeypatch.setattr(
        crawl_fetch_runtime,
        "run_browser_attempts",
        _fake_run_browser_attempts,
    )

    await crawl_fetch_runtime.fetch_page(
        "https://example.com/products/widget",
        surface="ecommerce_detail",
        prefer_browser=True,
        requested_fields=["product measurements"],
    )

    assert captured_requested_fields == ["product measurements"]


@pytest.mark.asyncio
@pytest.mark.component
async def test_fetch_page_prefer_browser_falls_back_to_http_after_browser_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    @_as_async
    def _failing_browser(*_args, **_kwargs):
        calls.append("browser")
        raise TimeoutError("Page.goto: Timeout 15000ms exceeded")

    @_as_async
    def _fake_curl(url: str, timeout_seconds: float, *, proxy: str | None = None):
        del timeout_seconds, proxy
        calls.append("curl")
        return PageFetchResult(
            url=url,
            final_url=url,
            html="<html><body><h1>Widget</h1></body></html>",
            status_code=200,
            method="curl_cffi",
        )

    monkeypatch.setattr(crawl_fetch_runtime, "run_browser_attempts", _failing_browser)
    monkeypatch.setattr(crawl_fetch_runtime, "_curl_fetch", _fake_curl)

    result = await crawl_fetch_runtime.fetch_page(
        "https://www.harrods.com/en-gb/p/widget",
        surface="ecommerce_detail",
        prefer_browser=True,
    )

    assert calls == ["browser", "curl"]
    assert result.method == "curl_cffi"


@pytest.mark.asyncio
@pytest.mark.component
async def test_fetch_page_kitchenaid_prefer_browser_timeout_falls_back_to_http(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    url = "https://www.kitchenaid.com/countertop-appliances/food-processors/processors/p.13-cup-food-processor.KFP1318CU.html"

    @_as_async
    def _failing_browser(*_args, **_kwargs):
        calls.append("browser")
        raise TimeoutError("Browser navigation stage exceeded timeout_seconds=45.00")

    @_as_async
    def _fake_curl(url: str, timeout_seconds: float, *, proxy: str | None = None):
        del timeout_seconds, proxy
        calls.append("curl")
        return PageFetchResult(
            url=url,
            final_url=url,
            html="<html><body><h1>13 Cup Food Processor</h1></body></html>",
            status_code=200,
            method="curl_cffi",
        )

    monkeypatch.setattr(crawl_fetch_runtime, "run_browser_attempts", _failing_browser)
    monkeypatch.setattr(crawl_fetch_runtime, "_curl_fetch", _fake_curl)

    result = await crawl_fetch_runtime.fetch_page(
        url,
        surface="ecommerce_detail",
        prefer_browser=True,
    )

    assert calls == ["browser", "curl"]
    assert result.method == "curl_cffi"


@pytest.mark.asyncio
@pytest.mark.component
async def test_http_escalation_timeout_keeps_prior_http_observation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _default_fetch_context()
    context.fetch_mode = "auto"
    original = PageFetchResult(
        url=context.url,
        final_url=context.url,
        html="<html><body><h1>Widget</h1></body></html>",
        status_code=200,
        method="curl_cffi",
    )

    async def _failing_browser(*_args, **_kwargs):
        raise TimeoutError("Browser navigation stage exceeded timeout_seconds=30.00")

    monkeypatch.setattr(crawl_fetch_runtime, "run_browser_attempts", _failing_browser)
    monkeypatch.setattr(crawl_fetch_runtime, "_update_host_result_memory", AsyncMock())

    result = await crawl_fetch_runtime._escalate_http_result_to_browser(
        context,
        result=original,
        proxy=None,
        vendor=None,
    )

    assert result is original
    assert result.method == "curl_cffi"
    assert result.browser_diagnostics["browser_outcome"] == "render_timeout"
    assert result.browser_diagnostics["failure_kind"] == "timeout"


@pytest.mark.asyncio
@pytest.mark.component
async def test_platform_required_browser_timeout_still_tries_http_in_auto_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []
    url = "https://www.ulta.com/p/shape-tape-concealer-xlsImpprod14251035"

    @_as_async
    def _failing_browser(*_args, **_kwargs):
        calls.append("browser")
        raise TimeoutError("Browser navigation stage exceeded timeout_seconds=30.00")

    @_as_async
    def _fake_curl(url: str, timeout_seconds: float, *, proxy: str | None = None):
        del timeout_seconds, proxy
        calls.append("curl")
        return PageFetchResult(
            url=url,
            final_url=url,
            html="<html><body><h1>Shape Tape Concealer</h1></body></html>",
            status_code=200,
            method="curl_cffi",
        )

    monkeypatch.setattr(crawl_fetch_runtime, "run_browser_attempts", _failing_browser)
    monkeypatch.setattr(crawl_fetch_runtime, "_curl_fetch", _fake_curl)

    result = await crawl_fetch_runtime.fetch_page(
        url,
        surface="ecommerce_detail",
        fetch_mode="auto",
    )

    assert calls == ["browser", "curl"]
    assert result.method == "curl_cffi"


@pytest.mark.asyncio
@pytest.mark.component
async def test_handle_http_result_retries_browser_after_browser_first_failure_and_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = _default_fetch_context()
    context.fetch_mode = "auto"
    context.browser_first_failed = True
    context.last_browser_attempt_diagnostics = {"failure_kind": "timeout"}
    browser_calls: list[list[str]] = []

    async def _fake_run_browser_attempts(*_args, **kwargs):
        browser_calls.append(list(kwargs.get("requested_fields") or []))
        return PageFetchResult(
            url=context.url,
            final_url=context.url,
            html="<html><body><h1>Rendered</h1></body></html>",
            status_code=200,
            method="browser",
            blocked=False,
            browser_diagnostics={"browser_engine": "patchright"},
        )

    monkeypatch.setattr(
        crawl_fetch_runtime,
        "run_browser_attempts",
        _fake_run_browser_attempts,
    )
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "_browser_escalation_allowed",
        lambda **_kwargs: True,
    )
    monkeypatch.setattr(
        crawl_fetch_runtime, "apply_protected_host_backoff", AsyncMock()
    )
    monkeypatch.setattr(crawl_fetch_runtime, "note_host_hard_block", AsyncMock())
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "load_host_protection_policy",
        AsyncMock(return_value=HostProtectionPolicy(host="example.com")),
    )
    monkeypatch.setattr(crawl_fetch_runtime, "_update_host_result_memory", AsyncMock())

    result, vendor_block_confirmed = await crawl_fetch_runtime._handle_http_result(
        context,
        result=PageFetchResult(
            url=context.url,
            final_url=context.url,
            html="<html><body>blocked</body></html>",
            status_code=403,
            method="curl_cffi",
            blocked=True,
        ),
        proxy=None,
    )

    assert isinstance(result, PageFetchResult)
    assert result.method == "browser"
    assert vendor_block_confirmed is False
    assert browser_calls == [[]]


@pytest.mark.asyncio
@pytest.mark.component
async def test_fetch_page_browser_only_skips_http_fetchers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @_as_async
    def _unexpected_curl(url: str, timeout_seconds: float, *, proxy: str | None = None):
        raise AssertionError(
            f"curl should not run for browser_only: {url} {timeout_seconds} {proxy}"
        )

    @_as_async
    def _fake_browser(url, timeout, **kwargs):
        del timeout, kwargs
        return PageFetchResult(
            url=url,
            final_url=url,
            html="<html><body>browser</body></html>",
            status_code=200,
            method="browser",
        )

    monkeypatch.setattr(crawl_fetch_runtime, "_curl_fetch", _unexpected_curl)
    monkeypatch.setattr(crawl_fetch_runtime, "_browser_fetch", _fake_browser)

    result = await crawl_fetch_runtime.fetch_page(
        "https://example.com/products/widget",
        surface="ecommerce_detail",
        fetch_mode="browser_only",
    )

    assert result.method == "browser"


@pytest.mark.asyncio
@pytest.mark.component
async def test_fetch_page_http_only_disables_browser_escalation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @_as_async
    def _fake_curl(url: str, timeout_seconds: float, *, proxy: str | None = None):
        del timeout_seconds, proxy
        return PageFetchResult(
            url=url,
            final_url=url,
            html="<html><body>challenge</body></html>",
            status_code=403,
            method="curl_cffi",
            blocked=False,
        )

    @_as_async
    def _fake_should_escalate(*args, **kwargs):
        del args, kwargs
        return True

    @_as_async
    def _unexpected_browser(url, timeout, **kwargs):
        raise AssertionError(
            f"browser should not run for http_only: {url} {timeout} {kwargs}"
        )

    monkeypatch.setattr(crawl_fetch_runtime, "_curl_fetch", _fake_curl)
    monkeypatch.setattr(
        crawl_fetch_runtime, "_should_escalate_to_browser_async", _fake_should_escalate
    )
    monkeypatch.setattr(crawl_fetch_runtime, "_browser_fetch", _unexpected_browser)

    result = await crawl_fetch_runtime.fetch_page(
        "https://example.com/products/widget",
        surface="ecommerce_detail",
        fetch_mode="http_only",
    )

    assert result.method == "curl_cffi"
    assert result.status_code == 403


@pytest.mark.asyncio
@pytest.mark.component
async def test_fetch_page_http_then_browser_escalates_after_http_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @_as_async
    def _fake_curl(url: str, timeout_seconds: float, *, proxy: str | None = None):
        del timeout_seconds, proxy
        return PageFetchResult(
            url=url,
            final_url=url,
            html="<html><body>challenge</body></html>",
            status_code=403,
            method="curl_cffi",
            blocked=False,
        )

    @_as_async
    def _fake_should_escalate(*args, **kwargs):
        del args, kwargs
        return True

    @_as_async
    def _fake_browser(url, timeout, **kwargs):
        del timeout, kwargs
        return PageFetchResult(
            url=url,
            final_url=url,
            html="<html><body>browser</body></html>",
            status_code=200,
            method="browser",
        )

    monkeypatch.setattr(crawl_fetch_runtime, "_curl_fetch", _fake_curl)
    monkeypatch.setattr(
        crawl_fetch_runtime, "_should_escalate_to_browser_async", _fake_should_escalate
    )
    monkeypatch.setattr(crawl_fetch_runtime, "_browser_fetch", _fake_browser)

    result = await crawl_fetch_runtime.fetch_page(
        "https://example.com/products/widget",
        surface="ecommerce_detail",
        fetch_mode="http_then_browser",
    )

    assert result.method == "browser"


@pytest.mark.asyncio
@pytest.mark.component
async def test_fetch_page_prefers_browser_from_learned_host_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @_as_async
    def _unexpected_curl(url: str, timeout_seconds: float, *, proxy: str | None = None):
        raise AssertionError(
            f"http should be skipped for learned browser-first host: {url} {timeout_seconds} {proxy}"
        )

    @_as_async
    def _fake_load_policy(url: str, *, session=None, ttl_seconds=None):
        del session, ttl_seconds
        return HostProtectionPolicy(host="example.com", prefer_browser=True)

    @_as_async
    def _fake_browser(url, timeout, **kwargs):
        del timeout, kwargs
        return PageFetchResult(
            url=url,
            final_url=url,
            html="<html><body>browser</body></html>",
            status_code=200,
            method="browser",
        )

    monkeypatch.setattr(crawl_fetch_runtime, "_curl_fetch", _unexpected_curl)
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "load_host_protection_policy",
        _fake_load_policy,
    )
    monkeypatch.setattr(crawl_fetch_runtime, "_browser_fetch", _fake_browser)

    result = await crawl_fetch_runtime.fetch_page(
        "https://example.com/products/widget",
        surface="ecommerce_detail",
    )

    assert result.method == "browser"


@pytest.mark.asyncio
@pytest.mark.component
async def test_fetch_page_preserves_proxy_list_on_browser_first_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_proxies: list[str | None] | None = None

    @_as_async
    def _fake_run_browser_attempts(
        context,
        *,
        reason: str,
        requested_fields: list[str] | None = None,
        listing_recovery_mode: str | None = None,
        capture_page_markdown: bool = False,
        proxies: list[str | None] | None = None,
        **_kwargs,
    ):
        del (
            context,
            reason,
            requested_fields,
            listing_recovery_mode,
            capture_page_markdown,
            _kwargs,
        )
        nonlocal captured_proxies
        captured_proxies = list(proxies or [])
        return PageFetchResult(
            url="https://example.com/products/widget",
            final_url="https://example.com/products/widget",
            html="<html><body><h1>Widget</h1></body></html>",
            status_code=200,
            method="browser",
        )

    monkeypatch.setattr(
        crawl_fetch_runtime,
        "run_browser_attempts",
        _fake_run_browser_attempts,
    )

    await crawl_fetch_runtime.fetch_page(
        "https://example.com/products/widget",
        surface="ecommerce_detail",
        prefer_browser=True,
        proxy_list=["http://proxy-one", "http://proxy-two"],
    )

    assert (captured_proxies or []) == ["http://proxy-one", "http://proxy-two"]


@pytest.mark.component
def test_resolve_proxy_attempts_preserves_order_and_deduplicates() -> None:
    proxies = browser_policy.resolve_proxy_attempts(
        [
            "socks5://proxy-b",
            "http://proxy-a",
            "socks5://proxy-b",
            "http://proxy-c",
        ]
    )

    assert proxies == [
        "socks5://proxy-b",
        "http://proxy-a",
        "http://proxy-c",
    ]


@pytest.mark.component
def test_attach_proxy_run_session_replaces_existing_session_marker() -> None:
    proxy = "socks5://user-session-oldvalue:pass@rp.scrapegw.com:6060"

    resolved = browser_policy.attach_proxy_run_session(proxy, run_id=42)

    assert resolved == "socks5://user-session-r42:pass@rp.scrapegw.com:6060"


@pytest.mark.component
def test_resolve_proxy_attempts_does_not_rewrite_proxy_session_by_default() -> None:
    proxies = browser_policy.resolve_proxy_attempts(
        [
            "socks5://user-session-oldvalue:pass@rp.scrapegw.com:6060",
            "socks5://user-session-other:pass@rp.scrapegw.com:6060",
        ],
        run_id=42,
    )

    assert proxies == [
        "socks5://user-session-oldvalue:pass@rp.scrapegw.com:6060",
        "socks5://user-session-other:pass@rp.scrapegw.com:6060",
    ]


@pytest.mark.component
def test_resolve_proxy_attempts_rewrites_proxy_session_when_explicitly_enabled() -> (
    None
):
    proxies = browser_policy.resolve_proxy_attempts(
        [
            "socks5://user-session-oldvalue:pass@rp.scrapegw.com:6060",
            "socks5://user-session-other:pass@rp.scrapegw.com:6060",
        ],
        run_id=42,
        proxy_profile={"session_rewrite_enabled": True},
    )

    assert proxies == [
        "socks5://user-session-r42:pass@rp.scrapegw.com:6060",
    ]


@pytest.mark.asyncio
@pytest.mark.component
async def test_fetch_page_browser_only_retries_proxies_in_user_order_and_stamps_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempted_proxies: list[str | None] = []

    @_as_async
    def _fake_browser_fetch(url: str, timeout: float, **kwargs):
        del url, timeout
        proxy = kwargs.get("proxy")
        attempted_proxies.append(proxy)
        if proxy == "socks5://proxy-a":
            raise RuntimeError("proxy-a failed")
        return PageFetchResult(
            url="https://example.com/products/widget",
            final_url="https://example.com/products/widget",
            html="<html><body><h1>Widget</h1></body></html>",
            status_code=200,
            method="browser",
            browser_diagnostics={"browser_attempted": True},
        )

    monkeypatch.setattr(crawl_fetch_runtime, "_browser_fetch", _fake_browser_fetch)
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "browser_engine_attempts",
        lambda **_kwargs: ["patchright"],
    )

    result = await crawl_fetch_runtime.fetch_page(
        "https://example.com/products/widget",
        surface="ecommerce_detail",
        fetch_mode="browser_only",
        proxy_list=["socks5://proxy-a", "socks5://proxy-b", "socks5://proxy-a"],
    )

    assert attempted_proxies == ["socks5://proxy-a", "socks5://proxy-b"]
    assert result.method == "browser"
    assert result.browser_diagnostics["proxy_scheme"] == "socks5"
    assert result.browser_diagnostics["browser_proxy_mode"] == "launch"
    assert result.browser_diagnostics["proxy_attempt_index"] == 2


@pytest.mark.asyncio
@pytest.mark.component
async def test_run_browser_attempts_records_driver_closed_exception(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = FetchRuntimeContext(
        url="https://example.com/products/widget",
        resolved_timeout=5.0,
        deadline_monotonic=time.perf_counter() + 5.0,
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
    )

    class BrowserDriverError(Exception):
        pass

    @_as_async
    def _failing_browser_fetch(url: str, timeout: float, **kwargs):
        del url, timeout, kwargs
        raise BrowserDriverError(
            "Page.content: Connection closed while reading from the driver"
        )

    monkeypatch.setattr(crawl_fetch_runtime, "_browser_fetch", _failing_browser_fetch)
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "browser_engine_attempts",
        lambda **_kwargs: ["patchright"],
    )
    monkeypatch.setattr(crawl_fetch_runtime, "wait_for_host_slot", AsyncMock())

    with pytest.raises(BrowserDriverError):
        await crawl_fetch_runtime.run_browser_attempts(
            context,
            reason="browser-only",
            host_policy=HostProtectionPolicy(host="example.com"),
        )

    assert context.last_browser_attempt_diagnostics["failure_kind"] == (
        "browser_driver_closed"
    )
    assert context.last_browser_attempt_diagnostics["browser_outcome"] == (
        "navigation_failed"
    )


@pytest.mark.asyncio
@pytest.mark.component
async def test_fetch_page_browser_only_escalates_to_real_chrome_after_patchright_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempted_engines: list[str] = []

    @_as_async
    def _fake_browser_fetch(url: str, timeout: float, **kwargs):
        del url, timeout
        attempted_engines.append(str(kwargs.get("browser_engine")))
        return PageFetchResult(
            url="https://example.com/products/widget",
            final_url="https://example.com/products/widget",
            html="<html><body><h1>Widget</h1></body></html>",
            status_code=200,
            method="browser",
            browser_diagnostics={
                "browser_engine": str(kwargs.get("browser_engine")),
                "browser_binary": "chrome.exe",
                "bridge_used": False,
                "escalation_lane": str(kwargs.get("escalation_lane")),
                "host_policy_snapshot": dict(kwargs.get("host_policy_snapshot") or {}),
            },
        )

    monkeypatch.setattr(crawl_fetch_runtime, "_browser_fetch", _fake_browser_fetch)
    monkeypatch.setattr(
        crawl_fetch_runtime.crawler_runtime_settings,
        "browser_real_chrome_enabled",
        True,
    )
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "real_chrome_browser_available",
        lambda: True,
    )
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "load_host_protection_policy",
        AsyncMock(
            return_value=HostProtectionPolicy(
                host="example.com",
                prefer_browser=True,
                patchright_blocked=True,
            )
        ),
    )

    result = await crawl_fetch_runtime.fetch_page(
        "https://example.com/products/widget",
        surface="ecommerce_detail",
        fetch_mode="browser_only",
    )

    assert attempted_engines == ["real_chrome"]
    assert result.browser_diagnostics["browser_engine"] == "real_chrome"
    assert result.browser_diagnostics["escalation_lane"] == "browser_only"
    assert (
        result.browser_diagnostics["host_policy_snapshot"]["patchright_blocked"] is True
    )

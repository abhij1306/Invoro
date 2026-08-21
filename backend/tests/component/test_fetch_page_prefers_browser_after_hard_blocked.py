from __future__ import annotations

from .test_crawl_fetch_runtime import *  # noqa: F403


@pytest.mark.asyncio
@pytest.mark.component
async def test_fetch_page_prefers_browser_after_hard_blocked_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await crawl_fetch_runtime.reset_fetch_runtime_state()
    url = "https://wellfound.com/location/united-states"
    curl_calls: list[str] = []
    browser_reasons: list[str | None] = []
    learned_policy = HostProtectionPolicy(host="wellfound.com")

    @_as_async
    def _vendor_blocked_curl(
        request_url: str,
        timeout: float,
        *,
        proxy: str | None = None,
    ):
        del timeout, proxy
        curl_calls.append(request_url)
        return PageFetchResult(
            url=request_url,
            final_url=request_url,
            html="<html><body>blocked</body></html>",
            status_code=403,
            method="curl_cffi",
            blocked=True,
            headers={"x-datadome": "blocked"},
        )

    @_as_async
    def _browser_blocked(request_url, timeout, **kwargs):
        del timeout
        browser_reasons.append(kwargs.get("browser_reason"))
        return PageFetchResult(
            url=request_url,
            final_url=request_url,
            html="<html><body>still blocked</body></html>",
            status_code=403,
            method="browser",
            blocked=True,
        )

    @_as_async
    def _fake_load_policy(url: str, *, session=None, ttl_seconds=None):
        del url, session, ttl_seconds
        return learned_policy

    @_as_async
    def _fake_note_host_hard_block(value: str | None, **kwargs):
        del value, kwargs
        nonlocal learned_policy
        learned_policy = HostProtectionPolicy(host="wellfound.com", prefer_browser=True)
        return learned_policy

    monkeypatch.setattr(crawl_fetch_runtime, "_curl_fetch", _vendor_blocked_curl)
    monkeypatch.setattr(crawl_fetch_runtime, "_browser_fetch", _browser_blocked)
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "browser_engine_attempts",
        lambda **_kwargs: ["patchright"],
    )
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "load_host_protection_policy",
        _fake_load_policy,
    )
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "note_host_hard_block",
        _fake_note_host_hard_block,
    )
    try:
        first = await crawl_fetch_runtime.fetch_page(url, surface="job_listing")
        second = await crawl_fetch_runtime.fetch_page(url, surface="job_listing")
    finally:
        await crawl_fetch_runtime.reset_fetch_runtime_state()

    assert first.method == "browser"
    assert second.method == "browser"
    assert first.blocked is True
    assert second.blocked is True
    assert curl_calls == [url]
    assert browser_reasons == ["vendor-block:datadome", "host-preference"]

@pytest.mark.asyncio
@pytest.mark.component
async def test_http_fetch_surfaces_dns_failure_without_hidden_ipv4_retry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _SharedClient:
        @_as_async
        def get(self, url: str, timeout: float):
            del url, timeout
            raise OSError(11001, "getaddrinfo failed")

    @_as_async
    def _fake_get_shared_http_client(*, proxy: str | None = None):
        del proxy
        return _SharedClient()

    monkeypatch.setattr(
        crawl_fetch_runtime, "_get_shared_http_client", _fake_get_shared_http_client
    )

    with pytest.raises(OSError, match="getaddrinfo failed"):
        await crawl_fetch_runtime._http_fetch("https://example.com/jobs", 10.0)

@pytest.mark.asyncio
@pytest.mark.component
async def test_fetch_page_surfaces_browser_error_when_http_exhausts_and_browser_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    curl_error = httpx.ConnectError("getaddrinfo failed")
    httpx_error = httpx.ReadTimeout("httpx fallback timed out")
    browser_error = RuntimeError("browser launch failed")

    @_as_async
    def _failing_curl(url: str, timeout: float, *, proxy: str | None = None):
        del proxy
        raise curl_error

    @_as_async
    def _failing_http(url: str, timeout: float, *, proxy: str | None = None):
        del url, timeout, proxy
        raise httpx_error

    @_as_async
    def _failing_browser(url, timeout, **kwargs):
        raise browser_error

    monkeypatch.setattr(crawl_fetch_runtime, "_curl_fetch", _failing_curl)
    monkeypatch.setattr(crawl_fetch_runtime, "_http_fetch", _failing_http)
    monkeypatch.setattr(crawl_fetch_runtime, "_browser_fetch", _failing_browser)

    with pytest.raises(RuntimeError, match="browser launch failed") as excinfo:
        await crawl_fetch_runtime.fetch_page("https://paycomonline.net/career-page")

    assert excinfo.value.__cause__ is httpx_error
    assert excinfo.value.browser_diagnostics["browser_attempted"] is True
    assert excinfo.value.browser_diagnostics["browser_outcome"] == "navigation_failed"
    assert excinfo.value.browser_diagnostics["failure_kind"] == "navigation_error"

@pytest.mark.asyncio
@pytest.mark.component
async def test_reset_fetch_runtime_state_closes_adapter_and_runtime_http_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    @_as_async
    def _fake_shutdown_browser_runtime() -> None:
        calls.append("browser")

    @_as_async
    def _fake_close_runtime_http_client() -> None:
        calls.append("runtime_http")

    @_as_async
    def _fake_close_adapter_http_client() -> None:
        calls.append("adapter_http")

    @_as_async
    def _fake_reset_pacing_state() -> None:
        calls.append("pacing")

    @_as_async
    def _fake_clear_cookie_store_cache() -> None:
        calls.append("cookie_store")

    monkeypatch.setattr(
        crawl_fetch_runtime,
        "shutdown_browser_runtime",
        _fake_shutdown_browser_runtime,
    )
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "clear_cookie_store_cache",
        _fake_clear_cookie_store_cache,
    )
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "reset_pacing_state",
        _fake_reset_pacing_state,
    )
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "close_shared_http_client",
        _fake_close_runtime_http_client,
    )
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "close_adapter_shared_http_client",
        _fake_close_adapter_http_client,
    )

    await crawl_fetch_runtime.reset_fetch_runtime_state()

    assert calls == [
        "browser",
        "cookie_store",
        "pacing",
        "runtime_http",
        "adapter_http",
    ]

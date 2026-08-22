from __future__ import annotations

from .test_crawl_fetch_runtime import AsyncMock, FakeBodyResponse, FetchRuntimeContext, HostProtectionPolicy, PageFetchResult, SimpleNamespace, _as_async, asyncio, browser_capture, crawl_fetch_runtime, http_fetch, pytest, read_network_payload_body, should_escalate_to_browser_async, time  # fmt: skip

pytest_plugins = ["tests.component.test_crawl_fetch_runtime"]


@pytest.mark.asyncio
@pytest.mark.component
async def test_fetch_page_browser_only_escalates_to_real_chrome_for_forum_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempted_engines: list[str] = []

    @_as_async
    def _fake_browser_fetch(url: str, timeout: float, **kwargs):
        del url, timeout
        attempted_engines.append(str(kwargs.get("browser_engine")))
        return PageFetchResult(
            url="https://www.reddit.com/r/python/comments/abc123/example/",
            final_url="https://www.reddit.com/r/python/comments/abc123/example/",
            html="<html><body><main>Thread</main></body></html>",
            status_code=200,
            method="browser",
            browser_diagnostics={
                "browser_engine": str(kwargs.get("browser_engine")),
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
                host="reddit.com",
                prefer_browser=True,
                patchright_blocked=True,
            )
        ),
    )

    result = await crawl_fetch_runtime.fetch_page(
        "https://www.reddit.com/r/python/comments/abc123/example/",
        surface="forum_detail",
        fetch_mode="browser_only",
    )

    assert attempted_engines == ["real_chrome"]
    assert result.browser_diagnostics["browser_engine"] == "real_chrome"
    assert result.browser_diagnostics["escalation_lane"] == "browser_only"
    assert (
        result.browser_diagnostics["host_policy_snapshot"]["patchright_blocked"] is True
    )


@pytest.mark.asyncio
@pytest.mark.component
async def test_run_browser_attempts_replans_to_real_chrome_after_same_proxy_patchright_block(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempted_engines: list[str] = []
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

    @_as_async
    def _fake_browser_fetch(url: str, timeout: float, **kwargs):
        del url, timeout
        browser_engine = str(kwargs.get("browser_engine"))
        attempted_engines.append(browser_engine)
        return PageFetchResult(
            url="https://example.com/products/widget",
            final_url="https://example.com/products/widget",
            html="<html><body><h1>Rendered</h1></body></html>",
            status_code=200,
            method="browser",
            blocked=browser_engine == "patchright",
            browser_diagnostics={"browser_engine": browser_engine},
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
    monkeypatch.setattr(crawl_fetch_runtime, "wait_for_host_slot", AsyncMock())
    monkeypatch.setattr(crawl_fetch_runtime, "_update_host_result_memory", AsyncMock())
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "load_host_protection_policy",
        AsyncMock(
            side_effect=[
                HostProtectionPolicy(
                    host="example.com",
                    patchright_blocked=True,
                    prefer_browser=True,
                ),
            ]
        ),
    )

    result = await crawl_fetch_runtime.run_browser_attempts(
        context,
        reason="browser-only",
        host_policy=HostProtectionPolicy(host="example.com"),
    )

    assert attempted_engines == ["patchright", "real_chrome"]
    assert result.browser_diagnostics["browser_engine"] == "real_chrome"


@pytest.mark.asyncio
@pytest.mark.component
async def test_run_browser_attempts_lets_browser_runtime_own_stage_timeouts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempted_engines: list[str] = []
    context = FetchRuntimeContext(
        url="https://example.com/products/widget",
        resolved_timeout=0.01,
        deadline_monotonic=time.perf_counter() + 0.01,
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

    async def _fake_browser_fetch(url: str, stage_budget: float, **kwargs):
        del url, stage_budget
        browser_engine = str(kwargs.get("browser_engine"))
        attempted_engines.append(browser_engine)
        if browser_engine == "patchright":
            await asyncio.sleep(0.05)
        return PageFetchResult(
            url="https://example.com/products/widget",
            final_url="https://example.com/products/widget",
            html="<html><body><h1>Rendered</h1></body></html>",
            status_code=200,
            method="browser",
            browser_diagnostics={"browser_engine": browser_engine},
        )

    monkeypatch.setattr(crawl_fetch_runtime, "_browser_fetch", _fake_browser_fetch)
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "browser_engine_attempts",
        lambda **_kwargs: ["patchright", "real_chrome"],
    )
    monkeypatch.setattr(crawl_fetch_runtime, "wait_for_host_slot", AsyncMock())

    result = await crawl_fetch_runtime.run_browser_attempts(
        context,
        reason="browser-only",
        host_policy=HostProtectionPolicy(host="example.com"),
    )

    assert attempted_engines == ["patchright"]
    assert result.browser_diagnostics["browser_engine"] == "patchright"
    assert context.last_browser_attempt_diagnostics == {}


@pytest.mark.asyncio
@pytest.mark.component
async def test_fetch_page_browser_only_stamps_engine_and_lane_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @_as_async
    def _fake_browser_fetch(url: str, timeout: float, **kwargs):
        del url, timeout
        return PageFetchResult(
            url="https://example.com/products/widget",
            final_url="https://example.com/products/widget",
            html="<html><body><h1>Widget</h1></body></html>",
            status_code=200,
            method="browser",
            browser_diagnostics={
                "browser_engine": str(kwargs.get("browser_engine")),
                "browser_binary": "C:/Program Files/Google/Chrome/Application/chrome.exe",
                "bridge_used": True,
                "escalation_lane": str(kwargs.get("escalation_lane")),
                "host_policy_snapshot": dict(kwargs.get("host_policy_snapshot") or {}),
            },
        )

    monkeypatch.setattr(crawl_fetch_runtime, "_browser_fetch", _fake_browser_fetch)
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "browser_engine_attempts",
        lambda **_kwargs: ["patchright"],
    )
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "load_host_protection_policy",
        AsyncMock(
            return_value=HostProtectionPolicy(
                host="example.com",
                prefer_browser=True,
                request_blocked=True,
                last_block_vendor="datadome",
            )
        ),
    )

    result = await crawl_fetch_runtime.fetch_page(
        "https://example.com/products/widget",
        surface="ecommerce_detail",
        fetch_mode="browser_only",
        proxy_list=["socks5://proxy-a"],
    )

    assert result.browser_diagnostics["browser_engine"] == "patchright"
    assert result.browser_diagnostics["bridge_used"] is True
    assert result.browser_diagnostics["escalation_lane"] == "browser_only_proxy"
    assert result.browser_diagnostics["host_policy_snapshot"]["prefer_browser"] is True


@pytest.mark.asyncio
@pytest.mark.component
async def test_fetch_page_forwards_proxy_profile_to_browser_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_proxy_profile: dict[str, object] = {}

    @_as_async
    def _fake_browser_fetch(url: str, _timeout: float, **kwargs):
        del url, _timeout
        nonlocal captured_proxy_profile
        captured_proxy_profile = dict(kwargs.get("proxy_profile") or {})
        return PageFetchResult(
            url="https://example.com/products/widget",
            final_url="https://example.com/products/widget",
            html="<html><body><h1>Widget</h1></body></html>",
            status_code=200,
            method="browser",
            browser_diagnostics={"browser_attempted": True},
        )

    monkeypatch.setattr(crawl_fetch_runtime, "_browser_fetch", _fake_browser_fetch)

    result = await crawl_fetch_runtime.fetch_page(
        "https://example.com/products/widget",
        surface="ecommerce_detail",
        fetch_mode="browser_only",
        proxy_list=["socks5://proxy-a"],
        proxy_profile={"enabled": True, "rotation": "rotating"},
    )

    assert result.method == "browser"
    assert captured_proxy_profile == {"enabled": True, "rotation": "rotating"}


@pytest.mark.asyncio
@pytest.mark.component
async def test_run_browser_attempts_treats_none_cooldown_as_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempted_engines: list[str] = []
    host_policy = HostProtectionPolicy(host="example.com")
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

    @_as_async
    def _fake_browser_fetch(url: str, timeout: float, **kwargs):
        del url, timeout
        browser_engine = str(kwargs.get("browser_engine"))
        attempted_engines.append(browser_engine)
        return PageFetchResult(
            url="https://example.com/products/widget",
            final_url="https://example.com/products/widget",
            html="<html><body><h1>Rendered</h1></body></html>",
            status_code=200,
            method="browser",
            blocked=browser_engine == "patchright",
            browser_diagnostics={},
        )

    monkeypatch.setattr(crawl_fetch_runtime, "_browser_fetch", _fake_browser_fetch)
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "browser_engine_attempts",
        lambda **_kwargs: ["patchright", "real_chrome"],
    )
    monkeypatch.setattr(crawl_fetch_runtime, "wait_for_host_slot", AsyncMock())
    monkeypatch.setattr(crawl_fetch_runtime, "_update_host_result_memory", AsyncMock())
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "load_host_protection_policy",
        AsyncMock(return_value=host_policy),
    )
    monkeypatch.setattr(
        crawl_fetch_runtime.crawler_runtime_settings,
        "browser_post_block_cooldown_ms",
        None,
    )

    result = await crawl_fetch_runtime.run_browser_attempts(
        context,
        reason="browser-only",
        host_policy=host_policy,
    )

    assert attempted_engines == ["patchright", "real_chrome"]
    assert result.method == "browser"
    assert result.blocked is False


@pytest.mark.asyncio
@pytest.mark.component
async def test_read_network_payload_body_rejects_oversized_body_before_decode() -> None:
    response = FakeBodyResponse(b"x" * 3_500_000)

    body = await read_network_payload_body(response)

    assert body.outcome == "too_large"
    assert body.body is None
    assert response.body_calls == 1


@pytest.mark.asyncio
@pytest.mark.component
async def test_read_network_payload_body_accepts_small_body_when_content_length_too_large() -> (
    None
):
    response = FakeBodyResponse(
        b"x",
        headers={"content-length": "3500000"},
    )

    body = await read_network_payload_body(response)

    assert body.outcome == "read"
    assert body.body == b"x"
    assert response.body_calls == 1


@pytest.mark.asyncio
@pytest.mark.component
async def test_read_network_payload_body_accepts_large_but_in_budget_body() -> None:
    response = FakeBodyResponse(b"x" * 600_000)

    body = await read_network_payload_body(response)

    assert body.outcome == "read"
    assert body.body == b"x" * 600_000
    assert response.body_calls == 1


@pytest.mark.asyncio
@pytest.mark.component
async def test_read_network_payload_body_accepts_high_value_large_body_with_scaled_budget() -> (
    None
):
    response = FakeBodyResponse(
        b"x" * 3_500_000,
        url="https://example.com/products/widget/product.js",
    )

    body = await read_network_payload_body(response, surface="ecommerce_detail")

    assert body.outcome == "read"
    assert body.body == b"x" * 3_500_000
    assert response.body_calls == 1


@pytest.mark.asyncio
@pytest.mark.component
async def test_read_network_payload_body_marks_closed_page_failures_explicitly() -> (
    None
):
    response = FakeBodyResponse(error=RuntimeError("Target closed"))

    result = await read_network_payload_body(response)

    assert result.outcome == "response_closed"
    assert result.body is None
    assert "RuntimeError" in str(result.error)


@pytest.mark.asyncio
@pytest.mark.component
async def test_read_network_payload_body_marks_generic_read_failures_explicitly() -> (
    None
):
    response = FakeBodyResponse(error=RuntimeError("socket reset"))

    result = await read_network_payload_body(response)

    assert result.outcome == "read_error"
    assert result.body is None
    assert "socket reset" in str(result.error)


@pytest.mark.asyncio
@pytest.mark.component
async def test_read_network_payload_body_maps_read_timeouts_to_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = FakeBodyResponse(b"x")

    @_as_async
    def _fake_wait_for(awaitable, timeout: float):
        awaitable.close()
        del timeout
        raise asyncio.TimeoutError

    monkeypatch.setattr(browser_capture.asyncio, "wait_for", _fake_wait_for)

    result = await read_network_payload_body(response)

    assert result.outcome == "timeout"
    assert result.body is None
    assert response.body_calls == 0


@pytest.mark.asyncio
@pytest.mark.component
async def test_should_escalate_to_browser_async_uses_thread_offload(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[object] = []

    @_as_async
    def _fake_to_thread(func, *args, **kwargs):
        calls.append(func.__name__)
        return func(*args, **kwargs)

    monkeypatch.setattr(
        "app.services.acquisition.runtime.asyncio.to_thread", _fake_to_thread
    )

    result = await should_escalate_to_browser_async(
        PageFetchResult(
            url="https://example.com",
            final_url="https://example.com",
            html="<html><body><div id='__next'></div><script></script><script></script><script></script></body></html>",
            status_code=200,
            method="httpx",
            blocked=False,
        )
    )

    assert result is True
    assert calls == ["should_escalate_to_browser"]


@pytest.mark.asyncio
@pytest.mark.component
async def test_http_fetch_populates_platform_family_from_response_url() -> None:
    class _FakeClient:
        @_as_async
        def get(self, url: str, timeout: float) -> SimpleNamespace:
            del url, timeout
            return SimpleNamespace(
                text="<html><body>Jobs</body></html>",
                headers={"content-type": "text/html"},
                status_code=200,
                url="https://boards.greenhouse.io/acme",
            )

    @_as_async
    def _fake_get_client(*, proxy: str | None = None):
        del proxy
        return _FakeClient()

    @_as_async
    def _not_blocked(*_args, **_kwargs) -> bool:
        return False

    result = await http_fetch(
        "https://example.com/jobs",
        5,
        get_client=_fake_get_client,
        blocked_html_checker=_not_blocked,
    )

    assert result.platform_family == "greenhouse"


@pytest.mark.asyncio
@pytest.mark.component
async def test_http_fetch_accepts_legacy_client_builder_keyword() -> None:
    class _FakeClient:
        @_as_async
        def get(self, url: str, timeout: float) -> SimpleNamespace:
            del url, timeout
            return SimpleNamespace(
                text="<html><body>ok</body></html>",
                headers={"content-type": "text/html"},
                status_code=200,
                url="https://example.com/products/widget",
            )

    @_as_async
    def _legacy_client_builder(*, proxy: str | None = None):
        assert proxy is None
        return _FakeClient()

    @_as_async
    def _not_blocked(*_args, **_kwargs) -> bool:
        return False

    result = await http_fetch(
        "https://example.com/products/widget",
        5,
        client_builder=_legacy_client_builder,
        blocked_html_checker=_not_blocked,
    )

    assert result.final_url == "https://example.com/products/widget"


@pytest.mark.asyncio
@pytest.mark.component
async def test_detail_surface_without_signals_escalates_even_when_html_is_not_a_js_shell() -> (
    None
):
    listing_shell_html = (
        "<html><body><h1>Careers</h1>"
        + "<ul>"
        + "".join(f"<li><a href='#'>Job {index}</a></li>" for index in range(20))
        + "</ul>"
        + "<p>"
        + ("Lots of visible non-detail copy. " * 30)
        + "</p>"
        + "</body></html>"
    )
    result = PageFetchResult(
        url="https://ats.example.com/careers?ShowJob=123",
        final_url="https://ats.example.com/careers?ShowJob=123",
        html=listing_shell_html,
        status_code=200,
        method="httpx",
        blocked=False,
    )

    assert await should_escalate_to_browser_async(result, surface="job_detail") is True
    assert (
        await should_escalate_to_browser_async(result, surface="job_listing") is False
    )


@pytest.mark.asyncio
@pytest.mark.component
async def test_should_escalate_to_browser_async_uses_runtime_policy_for_missing_detail_signals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.services.acquisition.runtime.resolve_platform_runtime_policy",
        lambda url, html="", *, surface=None: {
            "family": None,
            "requires_browser": False,
            "proxy_policy": None,
            "http_browser_escalation": {
                "js_shell_without_detail_signals": False,
                "missing_detail_signals": False,
                "listing_shell_without_listing_signals": False,
            },
        },
    )
    result = PageFetchResult(
        url="https://ats.example.com/careers?ShowJob=123",
        final_url="https://ats.example.com/careers?ShowJob=123",
        html=(
            "<html><body><h1>Careers</h1>"
            + "<ul>"
            + "".join(f"<li><a href='#'>Job {index}</a></li>" for index in range(20))
            + "</ul>"
            + "<p>"
            + ("Lots of visible non-detail copy. " * 30)
            + "</p>"
            + "</body></html>"
        ),
        status_code=200,
        method="httpx",
        blocked=False,
    )

    assert await should_escalate_to_browser_async(result, surface="job_detail") is False


@pytest.mark.asyncio
@pytest.mark.component
async def test_listing_hash_router_shell_escalates_to_browser() -> None:
    result = PageFetchResult(
        url="https://practicesoftwaretesting.com/#/",
        final_url="https://practicesoftwaretesting.com/#/",
        html=(
            "<html><body><div id='root'></div>"
            "<script></script><script></script><script></script>"
            "</body></html>"
        ),
        status_code=200,
        method="httpx",
        blocked=False,
    )

    assert (
        await should_escalate_to_browser_async(result, surface="ecommerce_listing")
        is True
    )


@pytest.mark.asyncio
@pytest.mark.component
async def test_listing_202_shell_escalates_to_browser() -> None:
    result = PageFetchResult(
        url="https://www.govplanet.com/for-sale/equipment",
        final_url="https://www.govplanet.com/for-sale/equipment",
        html=(
            "<html><body><div id='app'></div>"
            "<script type='application/json'>{\"pending\":true}</script>"
            "<script></script><script></script>"
            "</body></html>"
        ),
        status_code=202,
        method="httpx",
        blocked=False,
    )

    assert (
        await should_escalate_to_browser_async(result, surface="ecommerce_listing")
        is True
    )


@pytest.mark.asyncio
@pytest.mark.component
async def test_listing_single_product_json_ld_shell_escalates_to_browser() -> None:
    result = PageFetchResult(
        url="https://shop.example.com/hair-care/hair-straighteners",
        final_url="https://shop.example.com/hair-care/hair-straighteners",
        html=(
            "<html><body><h1>Hair straighteners</h1>"
            "<script type='application/ld+json'>"
            '{"@context":"https://schema.org","@type":"Product","name":"SEO Product"}'
            "</script>"
            "<script>window.dataLayer=[{pageInfo:{pageType:'catalog/category/view'}}]</script>"
            "<div id='layer-product-list'></div>"
            "<p>" + ("Category copy. " * 80) + "</p>"
            "</body></html>"
        ),
        status_code=200,
        method="httpx",
        blocked=False,
    )

    assert (
        await should_escalate_to_browser_async(result, surface="ecommerce_listing")
        is True
    )

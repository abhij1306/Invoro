from __future__ import annotations

from .test_crawl_fetch_runtime import AsyncMock, HostProtectionPolicy, PageFetchResult, SimpleNamespace, _as_async, _default_fetch_context, _page_fetch_result, acquisition_runtime, browser_policy, classify_network_endpoint, crawl_fetch_runtime, httpx, pytest, should_capture_network_payload, sys  # fmt: skip

pytest_plugins = ["tests.component.test_crawl_fetch_runtime"]


@pytest.mark.asyncio
@pytest.mark.component
async def test_real_chrome_success_updates_host_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    usable_fetches: list[dict[str, object]] = []

    @_as_async
    def _fake_note_host_usable_fetch(value: str | None, **kwargs):
        usable_fetches.append({"value": value, **kwargs})

    monkeypatch.setattr(
        crawl_fetch_runtime,
        "note_host_usable_fetch",
        _fake_note_host_usable_fetch,
    )
    context = _default_fetch_context()
    result = _page_fetch_result(
        "<html><body>Widget</body></html>",
        blocked=False,
        browser_diagnostics={"browser_engine": "real_chrome"},
    )

    await crawl_fetch_runtime._update_host_result_memory(context, result=result)

    assert usable_fetches == [
        {
            "value": "https://example.com/products/widget",
            "method": "browser:real_chrome",
            "proxy_used": False,
            "ttl_seconds": crawl_fetch_runtime.crawler_runtime_settings.coerce_host_memory_ttl_seconds(
                None
            ),
        }
    ]


@pytest.mark.asyncio
@pytest.mark.component
async def test_patchright_success_updates_host_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    usable_fetches: list[dict[str, object]] = []

    @_as_async
    def _fake_note_host_usable_fetch(value: str | None, **kwargs):
        usable_fetches.append({"value": value, **kwargs})

    monkeypatch.setattr(
        crawl_fetch_runtime,
        "note_host_usable_fetch",
        _fake_note_host_usable_fetch,
    )
    context = _default_fetch_context()
    result = _page_fetch_result(
        "<html><body>Widget</body></html>",
        blocked=False,
        browser_diagnostics={"browser_engine": "patchright"},
    )

    await crawl_fetch_runtime._update_host_result_memory(context, result=result)

    assert usable_fetches == [
        {
            "value": "https://example.com/products/widget",
            "method": "browser:patchright",
            "proxy_used": False,
            "ttl_seconds": crawl_fetch_runtime.crawler_runtime_settings.coerce_host_memory_ttl_seconds(
                None
            ),
        }
    ]


@pytest.mark.asyncio
@pytest.mark.component
async def test_location_required_diagnostics_do_not_write_hard_block_memory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hard_blocks: list[dict[str, object]] = []
    usable_fetches: list[dict[str, object]] = []

    @_as_async
    def _fake_note_host_hard_block(value: str | None, **kwargs):
        hard_blocks.append({"value": value, **kwargs})

    @_as_async
    def _fake_note_host_usable_fetch(value: str | None, **kwargs):
        usable_fetches.append({"value": value, **kwargs})

    monkeypatch.setattr(
        crawl_fetch_runtime,
        "note_host_hard_block",
        _fake_note_host_hard_block,
    )
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "note_host_usable_fetch",
        _fake_note_host_usable_fetch,
    )
    context = _default_fetch_context()
    result = _page_fetch_result(
        "<html><body>Choose your location</body></html>",
        blocked=True,
        browser_diagnostics={
            "browser_engine": "real_chrome",
            "browser_outcome": "location_required",
            "failure_reason": "location_required",
        },
    )

    await crawl_fetch_runtime._update_host_result_memory(context, result=result)

    assert hard_blocks == []
    assert usable_fetches == []


@pytest.mark.component
def test_should_capture_network_payload_skips_noise_and_large_declared_payloads() -> (
    None
):
    assert not should_capture_network_payload(
        url="https://cdn.cookielaw.org/consent/site/en.json",
        content_type="application/json",
        headers={},
        captured_count=0,
    )
    assert not should_capture_network_payload(
        url="https://cdn0.forter.com/site/prop.json",
        content_type="application/json",
        headers={},
        captured_count=0,
    )
    assert not should_capture_network_payload(
        url="https://bam.nr-data.net/1/NRBR",
        content_type="application/json",
        headers={},
        captured_count=0,
    )
    assert not should_capture_network_payload(
        url="https://arcteryx.us-5.evergage.com/api2/event/site",
        content_type="application/json",
        headers={},
        captured_count=0,
    )
    assert not should_capture_network_payload(
        url="https://example.com/telemetry/events",
        content_type="application/json",
        headers={},
        captured_count=0,
    )
    assert not should_capture_network_payload(
        url="https://example.com/api/products",
        content_type="application/json",
        headers={"content-length": "9999999"},
        captured_count=0,
    )
    assert should_capture_network_payload(
        url="https://example.com/api/products",
        content_type="application/json",
        headers={"content-length": "512"},
        captured_count=0,
    )
    assert should_capture_network_payload(
        url="https://example.com/api/products",
        content_type="application/json",
        headers={"content-length": "600000"},
        captured_count=0,
    )
    assert should_capture_network_payload(
        url="https://example.com/products/widget/product.js",
        content_type="application/json",
        headers={"content-length": "6000000"},
        captured_count=0,
        surface="ecommerce_detail",
    )


@pytest.mark.component
def test_should_capture_network_payload_accepts_chunked_json_without_content_length() -> (
    None
):
    assert should_capture_network_payload(
        url="https://example.com/api/products",
        content_type="application/json",
        headers={"transfer-encoding": "chunked"},
        captured_count=0,
    )


@pytest.mark.component
def test_content_aware_http_blocking_ignores_vendor_headers_when_detail_signals_exist() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Widget Prime",
          "offers": {
            "price": "19.99",
            "priceCurrency": "USD"
          }
        }
        </script>
      </head>
      <body>
        <h1>Widget Prime</h1>
      </body>
    </html>
    """

    assert not acquisition_runtime._content_aware_http_blocked(
        httpx.Headers({"akamai-grn": "0.abc"}),
        html,
        200,
    )


@pytest.mark.component
def test_select_http_fetcher_uses_httpx_when_forced(patch_settings) -> None:
    patch_settings(force_httpx=True)
    fetcher = crawl_fetch_runtime._select_http_fetcher(object())

    assert fetcher is crawl_fetch_runtime._http_fetch


@pytest.mark.component
def test_should_capture_network_payload_ignores_misleading_content_length_when_chunked() -> (
    None
):
    assert should_capture_network_payload(
        url="https://example.com/api/products",
        content_type="application/json",
        headers={
            "transfer-encoding": "chunked",
            "content-length": "9999999",
        },
        captured_count=0,
    )


@pytest.mark.component
def test_should_capture_network_payload_accepts_react_server_component_streams() -> (
    None
):
    assert should_capture_network_payload(
        url="https://example.com/products/widget",
        content_type="text/x-component",
        headers={},
        captured_count=0,
    )


@pytest.mark.component
def test_should_capture_network_payload_accepts_trpc_and_rsc_url_hints() -> None:
    assert should_capture_network_payload(
        url="https://example.com/api/trpc/product.get",
        content_type="application/trpc+json",
        headers={},
        captured_count=0,
    )
    assert should_capture_network_payload(
        url="https://example.com/products/widget?_rsc=abc123",
        content_type="text/plain",
        headers={},
        captured_count=0,
    )


@pytest.mark.component
def test_classify_network_endpoint_uses_platform_config_family_signatures() -> None:
    assert classify_network_endpoint(
        response_url="https://boards-api.greenhouse.io/v1/boards/acme/jobs/1234",
        surface="job_detail",
    ) == {"type": "job_api", "family": "greenhouse"}
    assert classify_network_endpoint(
        response_url="https://jobs.example.com/api/positions/1234",
        surface="job_detail",
    ) == {"type": "job_api", "family": "generic"}
    assert classify_network_endpoint(
        response_url="https://shop.example.com/products/widget/product.js",
        surface="ecommerce_detail",
    ) == {"type": "product_api", "family": "shopify"}
    assert classify_network_endpoint(
        response_url="https://shop.example.com/api/variants/123",
        surface="ecommerce_detail",
    ) == {"type": "product_api", "family": "generic"}
    assert classify_network_endpoint(
        response_url="https://store.example.com/_next/data/build-id/widget.json",
        surface="ecommerce_detail",
    ) == {"type": "generic_json", "family": "nextjs"}


@pytest.mark.asyncio
@pytest.mark.component
async def test_curl_fetch_uses_runtime_owned_default_request_headers(
    monkeypatch: pytest.MonkeyPatch,
    patch_settings,
) -> None:
    captured_headers: dict[str, str] = {}
    patch_settings(
        http_user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        )
    )

    def _fake_get(url: str, **kwargs):
        del url
        captured_headers.update(dict(kwargs.get("headers") or {}))
        return SimpleNamespace(
            text="<html><body>ok</body></html>",
            headers={"content-type": "text/html"},
            status_code=200,
            url="https://example.com/products/widget",
        )

    monkeypatch.setitem(
        sys.modules,
        "curl_cffi",
        SimpleNamespace(requests=SimpleNamespace(get=_fake_get)),
    )
    result = await acquisition_runtime.curl_fetch(
        "https://example.com/products/widget",
        5.0,
    )

    assert result.method == "curl_cffi"
    assert captured_headers["User-Agent"].endswith("Chrome/131.0.0.0 Safari/537.36")
    assert "Accept" in captured_headers
    assert "Accept-Language" in captured_headers
    assert captured_headers["Upgrade-Insecure-Requests"] == "1"
    assert "sec-ch-ua" in captured_headers


@pytest.mark.asyncio
@pytest.mark.component
async def test_curl_fetch_coerces_blank_impersonate_target_to_none(
    monkeypatch: pytest.MonkeyPatch,
    patch_settings,
) -> None:
    captured_impersonate: list[object] = []

    def _fake_get(url: str, **kwargs):
        del url
        captured_impersonate.append(kwargs.get("impersonate"))
        return SimpleNamespace(
            text="<html><body>ok</body></html>",
            headers={"content-type": "text/html"},
            status_code=200,
            url="https://example.com/products/widget",
        )

    monkeypatch.setitem(
        sys.modules,
        "curl_cffi",
        SimpleNamespace(requests=SimpleNamespace(get=_fake_get)),
    )
    patch_settings(curl_impersonate_target="   ")
    await acquisition_runtime.curl_fetch(
        "https://example.com/products/widget",
        5.0,
    )

    assert captured_impersonate == [None]


@pytest.mark.asyncio
@pytest.mark.component
async def test_fetch_page_waits_for_host_slot_before_http_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wait_calls: list[str] = []

    @_as_async
    def _fake_wait_for_host_slot(
        url: str,
        *,
        ttl_seconds: int | None = None,
    ) -> None:
        del ttl_seconds
        wait_calls.append(url)

    @_as_async
    def _fake_curl(url: str, timeout_seconds: float, *, proxy: str | None = None):
        del timeout_seconds, proxy
        return PageFetchResult(
            url=url,
            final_url=url,
            html=(
                "<html><body><article class='product-card'>"
                "<a href='/products/widget'>Widget</a><span>$19.99</span>"
                "</article></body></html>"
            ),
            status_code=200,
            method="curl_cffi",
        )

    monkeypatch.setattr(
        crawl_fetch_runtime, "wait_for_host_slot", _fake_wait_for_host_slot
    )
    monkeypatch.setattr(crawl_fetch_runtime, "_curl_fetch", _fake_curl)

    result = await crawl_fetch_runtime.fetch_page(
        "https://example.com/collections/widgets",
        surface="ecommerce_listing",
    )

    assert result.method == "curl_cffi"
    assert wait_calls == ["https://example.com/collections/widgets"]


@pytest.mark.component
def test_browser_engine_attempts_uses_patchright_by_default() -> None:
    context = _default_fetch_context()

    attempts = browser_policy.browser_engine_attempts(
        context=context,
        host_policy=HostProtectionPolicy(host="example.com"),
        real_chrome_available=False,
    )

    assert attempts == ["patchright"]


@pytest.mark.component
def test_browser_engine_attempts_uses_real_chrome_after_patchright_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    context = _default_fetch_context()

    attempts = browser_policy.browser_engine_attempts(
        context=context,
        host_policy=HostProtectionPolicy(
            host="example.com",
            patchright_blocked=True,
            prefer_browser=True,
            last_block_vendor="datadome",
        ),
        real_chrome_available=True,
    )

    assert attempts == ["real_chrome", "patchright"]


@pytest.mark.component
def test_browser_engine_attempts_uses_real_chrome_for_blocked_forum_detail_when_available(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    context = _default_fetch_context(
        url="https://www.reddit.com/r/python/comments/abc123/example/",
        surface="forum_detail",
    )

    attempts = browser_policy.browser_engine_attempts(
        context=context,
        host_policy=HostProtectionPolicy(
            host="reddit.com",
            patchright_blocked=True,
            prefer_browser=True,
        ),
        real_chrome_available=True,
    )

    assert attempts == ["real_chrome", "patchright"]


@pytest.mark.component
def test_browser_engine_attempts_keeps_forced_patchright_explicit_when_unavailable() -> (
    None
):
    context = _default_fetch_context(forced_browser_engine="patchright")

    attempts = browser_policy.browser_engine_attempts(
        context=context,
        host_policy=HostProtectionPolicy(host="example.com"),
        real_chrome_available=False,
    )

    assert attempts == ["patchright"]


@pytest.mark.component
def test_browser_engine_attempts_does_not_escalate_from_patchright_block_memory_alone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
    context = _default_fetch_context()

    attempts = browser_policy.browser_engine_attempts(
        context=context,
        host_policy=HostProtectionPolicy(
            host="example.com",
            patchright_blocked=True,
            prefer_browser=False,
        ),
        real_chrome_available=True,
    )

    assert attempts == ["patchright"]


@pytest.mark.component
def test_saved_real_chrome_contract_skips_patchright(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        crawl_fetch_runtime.crawler_runtime_settings,
        "browser_real_chrome_enabled",
        True,
    )
    monkeypatch.setattr(
        crawl_fetch_runtime, "real_chrome_browser_available", lambda: True
    )
    context = _default_fetch_context(forced_browser_engine="real_chrome")

    attempts = browser_policy.browser_engine_attempts(
        context=context,
        host_policy=HostProtectionPolicy(host="example.com"),
        real_chrome_available=True,
    )

    assert attempts == ["real_chrome"]


@pytest.mark.parametrize(
    ("engine_attempts", "vendor", "method", "expected"),
    [
        (
            ["real_chrome", "patchright"],
            "datadome",
            "browser:real_chrome",
            ["patchright"],
        ),
        (
            ["patchright", "real_chrome"],
            "akamai",
            "curl_cffi",
            ["patchright", "real_chrome"],
        ),
    ],
)
@pytest.mark.component
def test_durable_vendor_block_engine_attempts(
    engine_attempts: list[str],
    vendor: str,
    method: str,
    expected: list[str],
) -> None:
    attempts = browser_policy.durable_vendor_block_engine_attempts(
        engine_attempts=engine_attempts,
        host_policy=HostProtectionPolicy(
            host="example.com",
            prefer_browser=True,
            last_block_vendor=vendor,
            last_block_method=method,
        ),
        forced_engine=None,
    )

    assert attempts == expected


@pytest.mark.asyncio
@pytest.mark.component
async def test_real_chrome_cookie_contract_tries_curl_cffi_handoff_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await crawl_fetch_runtime.reset_fetch_runtime_state()
    url = "https://example.com/products/widget"
    calls: list[dict[str, object]] = []

    @_as_async
    def _export_cookie_header_for_domain(request_url, **kwargs):
        calls.append({"url": request_url, "engine": kwargs.get("browser_engine")})
        return "session=ok"

    @_as_async
    def _curl_fetch(request_url, timeout_seconds, *, proxy=None, cookie_header=None):
        return PageFetchResult(
            url=request_url,
            final_url=request_url,
            html="<html><body>ok</body></html>",
            status_code=200,
            method="curl_cffi",
            blocked=False,
        )

    @_as_async
    def _browser_unexpected(*_args, **_kwargs):
        raise AssertionError("browser should not run when handoff succeeds")

    monkeypatch.setattr(
        crawl_fetch_runtime,
        "load_host_protection_policy",
        AsyncMock(return_value=HostProtectionPolicy(host="example.com")),
    )
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "export_cookie_header_for_domain",
        _export_cookie_header_for_domain,
    )
    monkeypatch.setattr(crawl_fetch_runtime, "_curl_fetch", _curl_fetch)
    monkeypatch.setattr(crawl_fetch_runtime, "_browser_fetch", _browser_unexpected)
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "_should_escalate_to_browser_async",
        AsyncMock(return_value=False),
    )

    result = await crawl_fetch_runtime.fetch_page(
        url,
        surface="ecommerce_detail",
        prefer_curl_handoff=True,
        handoff_cookie_engine="real_chrome",
        forced_browser_engine="real_chrome",
    )

    assert result.method == "curl_cffi"
    assert result.browser_diagnostics["browser_http_handoff"] is True
    assert calls == [{"url": url, "engine": "real_chrome"}]


@pytest.mark.asyncio
@pytest.mark.component
async def test_curl_handoff_failure_falls_back_to_real_chrome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await crawl_fetch_runtime.reset_fetch_runtime_state()
    url = "https://example.com/products/widget"
    engines: list[str] = []

    @_as_async
    def _export_cookie_header_for_domain(*_args, **_kwargs):
        return "session=bad"

    @_as_async
    def _curl_fetch(request_url, timeout_seconds, *, proxy=None, cookie_header=None):
        return PageFetchResult(
            url=request_url,
            final_url=request_url,
            html="<html><body>blocked</body></html>",
            status_code=403,
            method="curl_cffi",
            blocked=True,
        )

    @_as_async
    def _browser_fetch(request_url, timeout_seconds, **kwargs):
        engines.append(str(kwargs.get("browser_engine")))
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
        AsyncMock(return_value=HostProtectionPolicy(host="example.com")),
    )
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "export_cookie_header_for_domain",
        _export_cookie_header_for_domain,
    )
    monkeypatch.setattr(crawl_fetch_runtime, "_curl_fetch", _curl_fetch)
    monkeypatch.setattr(crawl_fetch_runtime, "_browser_fetch", _browser_fetch)

    result = await crawl_fetch_runtime.fetch_page(
        url,
        surface="ecommerce_detail",
        prefer_curl_handoff=True,
        handoff_cookie_engine="real_chrome",
        forced_browser_engine="real_chrome",
    )

    assert result.method == "browser"
    assert engines == ["real_chrome"]

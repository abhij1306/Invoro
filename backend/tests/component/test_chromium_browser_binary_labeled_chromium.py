from __future__ import annotations

from .test_browser_context import Path, SimpleNamespace, _context_spec, _credential_url, _secret_mapping, acquisition_browser_pool, acquisition_browser_runtime, analyze_html, asyncio, browser_proxy_bridge, cookie_store, crawl_fetch_runtime, crawler_runtime_settings, has_extractable_dom_content_detail_signals, has_extractable_listing_signals, is_special_use_domain, normalize_domain, pytest  # fmt: skip

pytest_plugins = ["tests.component._cookie_store_test_support"]

@pytest.mark.component
def test_chromium_browser_binary_is_labeled_chromium() -> None:
    assert acquisition_browser_pool._resolve_browser_binary("chromium") == (
        None,
        "chromium",
    )

@pytest.mark.component
def test_content_detail_signals_accept_meaningful_body_without_paragraph() -> None:
    analysis = analyze_html(
        """
        <html><body><main>
          <h1>Forum Thread</h1>
          <div class="post-body">This answer explains the workaround with enough detail to be useful for extraction.</div>
        </main></body></html>
        """
    )

    assert has_extractable_dom_content_detail_signals(analysis) is True

@pytest.mark.component
def test_content_detail_signals_reject_empty_and_heading_only_body() -> None:
    empty_analysis = analyze_html(
        "<html><body><main><h1>Thread</h1><div></div></main></body></html>"
    )
    heading_only_analysis = analyze_html(
        "<html><body><main><h1>Thread</h1><div>Thread</div></main></body></html>"
    )

    assert has_extractable_dom_content_detail_signals(empty_analysis) is False
    assert has_extractable_dom_content_detail_signals(heading_only_analysis) is False

@pytest.mark.component
def test_content_detail_signals_accept_common_content_descendant() -> None:
    analysis = analyze_html(
        """
        <html><body><main>
          <h1>Thread</h1>
          <section class="post-body"><span>Useful answer</span></section>
        </main></body></html>
        """
    )

    assert has_extractable_dom_content_detail_signals(analysis) is True

@pytest.mark.component
def test_listing_signals_detect_item_list_and_ignore_non_list_type() -> None:
    item_list_html = """
    <html><body><script type="application/ld+json">
      {"@context":"https://schema.org","@type":"ItemList","itemListElement":[]}
    </script></body></html>
    """
    non_list_html = """
    <html><body><script type="application/ld+json">
      {"@context":"https://schema.org","@type":"Article","headline":"News"}
    </script></body></html>
    """

    assert has_extractable_listing_signals(item_list_html) is True
    assert has_extractable_listing_signals(non_list_html) is False

@pytest.mark.component
def test_listing_signals_respect_typed_item_threshold(monkeypatch) -> None:
    monkeypatch.setattr(crawler_runtime_settings, "listing_min_items", 3)

    def typed_products(count: int) -> str:
        payloads = "\n".join(
            '<script type="application/ld+json">{"@type":"Product","name":"Item"}</script>'
            for _ in range(count)
        )
        return f"<html><body>{payloads}</body></html>"

    assert has_extractable_listing_signals(typed_products(2)) is False
    assert has_extractable_listing_signals(typed_products(3)) is True
    assert has_extractable_listing_signals(typed_products(4)) is True

@pytest.mark.component
def test_listing_signals_detect_list_item_type() -> None:
    html = """
    <html><body><script type="application/ld+json">
      {"@context":"https://schema.org","@type":"ListItem","name":"Result"}
    </script></body></html>
    """

    assert has_extractable_listing_signals(html) is True

@pytest.mark.component
def test_acquisition_package_exports_runtime_expand_function() -> None:
    from app.services import acquisition

    assert (
        acquisition.expand_all_interactive_elements
        is acquisition_browser_runtime.expand_all_interactive_elements
    )

@pytest.mark.component
def test_is_special_use_domain_ignores_ports() -> None:
    assert is_special_use_domain("localhost:3000") is True
    assert is_special_use_domain("http://localhost:3000/products/widget") is True

@pytest.mark.component
def test_is_special_use_domain_treats_test_suffix_as_special_use() -> None:
    assert is_special_use_domain("https://api.example.test/path") is True

@pytest.mark.component
def test_normalize_domain_strips_credentials() -> None:
    assert (
        normalize_domain(
            _credential_url(
                scheme="https",
                username="user",
                secret="pass",
                host="example.com",
                path="/path",
            )
        )
        == "example.com"
    )

@pytest.mark.component
def test_normalize_domain_preserves_non_standard_port() -> None:
    assert normalize_domain("https://example.com:8443/path") == "example.com:8443"

@pytest.mark.component
def test_normalize_domain_strips_standard_https_port() -> None:
    assert normalize_domain("https://example.com:443/path") == "example.com"

@pytest.mark.component
def test_normalize_domain_handles_domain_only_input() -> None:
    assert normalize_domain("example.com") == "example.com"

@pytest.mark.component
def test_normalize_domain_strips_credentials_without_password() -> None:
    assert normalize_domain("https://user@example.com/path") == "example.com"

@pytest.mark.asyncio
@pytest.mark.component
async def test_read_socks5_response_rejects_unexpected_upstream_version() -> None:
    reader = asyncio.StreamReader()
    reader.feed_data(bytes([4, 0, 0, 1, 127, 0, 0, 1, 0, 80]))
    reader.feed_eof()

    with pytest.raises(ValueError, match="Unexpected upstream SOCKS response version"):
        await browser_proxy_bridge._read_socks5_response(reader)

@pytest.mark.asyncio
@pytest.mark.component
async def test_read_client_request_rejects_missing_no_auth_method() -> None:
    class _Writer:
        def __init__(self) -> None:
            self.data = bytearray()

        def write(self, data: bytes) -> None:
            self.data.extend(data)

        async def drain(self) -> None:
            return None

    reader = asyncio.StreamReader()
    reader.feed_data(bytes([5, 1, 2]))
    reader.feed_eof()
    writer = _Writer()

    with pytest.raises(ValueError, match="no-auth method"):
        await browser_proxy_bridge._read_client_request(reader, writer)

    assert bytes(writer.data) == bytes([5, 0xFF])

@pytest.mark.asyncio
@pytest.mark.component
async def test_read_client_request_rebuilds_validated_connect_request() -> None:
    class _Writer:
        def write(self, _data: bytes) -> None:
            return None

        async def drain(self) -> None:
            return None

    raw_request = bytes([5, 1, 0, 5, 1, 0, 3, 11]) + b"example.com" + bytes([1, 187])
    reader = asyncio.StreamReader()
    reader.feed_data(raw_request)
    reader.feed_eof()

    request = await browser_proxy_bridge._read_client_request(reader, _Writer())

    assert request.to_upstream_bytes() == raw_request[3:]

@pytest.mark.asyncio
@pytest.mark.component
async def test_socks5_auth_bridge_start_is_singleflight(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    start_calls = 0

    class _Socket:
        def getsockname(self):
            return ("127.0.0.1", 41001)

    class _Server:
        sockets = [_Socket()]

        def close(self) -> None:
            return None

        async def wait_closed(self) -> None:
            return None

    async def _fake_start_server(*_args, **_kwargs):
        nonlocal start_calls
        start_calls += 1
        await asyncio.sleep(0)
        return _Server()

    monkeypatch.setattr(
        browser_proxy_bridge.asyncio, "start_server", _fake_start_server
    )
    bridge = browser_proxy_bridge.Socks5AuthBridge(
        browser_proxy_bridge.Socks5UpstreamProxy(
            scheme="socks5",
            host="proxy.example",
            port=1080,
            username="user",
            **_secret_mapping("pass"),
        )
    )

    first, second = await asyncio.gather(bridge.start(), bridge.start())
    await bridge.close()

    assert first == second == "socks5://127.0.0.1:41001"
    assert start_calls == 1

@pytest.mark.component
def test_browser_storage_state_persist_policy_rejects_challenge_shell_without_ready_probe() -> (
    None
):
    assert (
        acquisition_browser_runtime._browser_storage_state_is_persistable(
            blocked=False,
            finalized_diagnostics={
                "browser_outcome": "usable_content",
                "challenge_provider_hits": ["perimeterx"],
                "readiness_probes": [
                    {
                        "is_ready": False,
                    }
                ],
            },
        )
        is False
    )

@pytest.mark.asyncio
@pytest.mark.component
async def test_load_storage_state_for_run_ignores_invalid_run_id() -> None:
    assert await cookie_store.load_storage_state_for_run("invalid") is None

@pytest.mark.asyncio
@pytest.mark.component
async def test_load_storage_state_for_run_scopes_by_browser_engine(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(cookie_store.settings, "cookie_store_dir", tmp_path)
    await cookie_store.clear_cookie_store_cache()

    await cookie_store.persist_storage_state_for_run(
        77,
        {
            "cookies": [
                {
                    "name": "chromium-session",
                    "value": "1",
                    "domain": ".example.com",
                    "path": "/",
                }
            ],
            "origins": [],
        },
        browser_engine="chromium",
    )
    await cookie_store.persist_storage_state_for_run(
        77,
        {
            "cookies": [
                {
                    "name": "real-chrome-session",
                    "value": "2",
                    "domain": ".example.com",
                    "path": "/",
                }
            ],
            "origins": [],
        },
        browser_engine="real_chrome",
    )

    chromium_state = await cookie_store.load_storage_state_for_run(
        77,
        browser_engine="chromium",
    )
    real_chrome_state = await cookie_store.load_storage_state_for_run(
        77,
        browser_engine="real_chrome",
    )

    assert chromium_state == {
        "cookies": [
            {
                "name": "chromium-session",
                "value": "1",
                "domain": ".example.com",
                "path": "/",
            }
        ],
        "origins": [],
    }
    assert real_chrome_state == {
        "cookies": [
            {
                "name": "real-chrome-session",
                "value": "2",
                "domain": ".example.com",
                "path": "/",
            }
        ],
        "origins": [],
    }

@pytest.mark.asyncio
@pytest.mark.component
async def test_persist_storage_state_for_run_replaces_existing_state(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(cookie_store.settings, "cookie_store_dir", tmp_path)
    await cookie_store.clear_cookie_store_cache()

    await cookie_store.persist_storage_state_for_run(
        77,
        {
            "cookies": [
                {
                    "name": "stale",
                    "value": "1",
                    "domain": ".example.com",
                    "path": "/",
                }
            ],
            "origins": [
                {
                    "origin": "https://example.com",
                    "localStorage": [{"name": "old", "value": "1"}],
                }
            ],
        },
    )
    await cookie_store.persist_storage_state_for_run(
        77,
        {
            "cookies": [
                {
                    "name": "fresh",
                    "value": "2",
                    "domain": ".example.com",
                    "path": "/",
                }
            ],
            "origins": [
                {
                    "origin": "https://example.com",
                    "localStorage": [{"name": "new", "value": "2"}],
                }
            ],
        },
    )

    assert await cookie_store.load_storage_state_for_run(77) == {
        "cookies": [
            {
                "name": "fresh",
                "value": "2",
                "domain": ".example.com",
                "path": "/",
            }
        ],
        "origins": [],
    }

@pytest.mark.asyncio
@pytest.mark.component
async def test_persist_storage_state_for_run_keeps_cache_clean_when_write_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(cookie_store.settings, "cookie_store_dir", tmp_path)
    await cookie_store.clear_cookie_store_cache()

    def _raise_write(path, storage_state) -> None:
        del path, storage_state
        raise OSError("write failed")

    monkeypatch.setattr(cookie_store, "_write_storage_state_file", _raise_write)

    with pytest.raises(OSError, match="write failed"):
        await cookie_store.persist_storage_state_for_run(
            77,
            {
                "cookies": [
                    {
                        "name": "fresh",
                        "value": "2",
                        "domain": ".example.com",
                        "path": "/",
                    }
                ],
                "origins": [],
            },
        )

    assert await cookie_store.load_storage_state_for_run(77) is None

@pytest.mark.component
def test_write_storage_state_file_retries_permission_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    path = tmp_path / "state.json"
    attempts: list[int] = []
    original_replace = Path.replace

    def _flaky_replace(self: Path, target: Path) -> Path:
        attempts.append(1)
        if len(attempts) == 1:
            raise PermissionError("busy")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", _flaky_replace)
    monkeypatch.setattr(cookie_store.time, "sleep", lambda _seconds: None)

    cookie_store._write_storage_state_file(
        path,
        {"cookies": [], "origins": []},
    )

    assert path.exists()
    assert len(attempts) == 2

@pytest.mark.asyncio
@pytest.mark.component
async def test_shared_browser_runtime_passes_generated_context_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_kwargs: list[dict[str, object]] = []
    created_pages: list[object] = []
    routed_patterns: list[str] = []

    class FakeContext:
        async def route(self, pattern: str, handler) -> None:
            del handler
            routed_patterns.append(pattern)

        async def new_page(self):
            page = object()
            created_pages.append(page)
            return page

        async def close(self) -> None:
            return None

    class FakeBrowser:
        async def new_context(self, **kwargs):
            captured_kwargs.append(kwargs)
            return FakeContext()

    runtime = crawl_fetch_runtime.SharedBrowserRuntime(max_contexts=1)
    runtime._browser = FakeBrowser()
    runtime._playwright = object()

    monkeypatch.setattr(
        acquisition_browser_pool,
        "build_playwright_context_spec",
        lambda **_: _context_spec(
            {
                "user_agent": "Mozilla/5.0 Runtime/145.0",
                "viewport": {"width": 1600, "height": 900},
                "extra_http_headers": {"Accept": "text/html"},
                "locale": "en-US",
                "device_scale_factor": 1.0,
                "has_touch": False,
                "is_mobile": False,
                "service_workers": "block",
                "bypass_csp": False,
            }
        ),
    )

    async with runtime.page() as page:
        assert page in created_pages

    assert captured_kwargs == [
        {
            "user_agent": "Mozilla/5.0 Runtime/145.0",
            "viewport": {"width": 1600, "height": 900},
            "extra_http_headers": {"Accept": "text/html"},
            "locale": "en-US",
            "device_scale_factor": 1.0,
            "has_touch": False,
            "is_mobile": False,
            "service_workers": "block",
            "bypass_csp": False,
        }
    ]
    assert routed_patterns == []

@pytest.mark.asyncio
@pytest.mark.component
async def test_shared_browser_runtime_uses_native_context_for_real_chrome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_kwargs: list[dict[str, object]] = []

    class FakeContext:
        async def route(self, pattern: str, handler) -> None:
            del pattern, handler
            return None

        async def add_init_script(self, script: str) -> None:
            return None

        async def new_page(self):
            return SimpleNamespace(context=self)

        async def close(self) -> None:
            return None

    class FakeBrowser:
        async def new_context(self, **kwargs):
            captured_kwargs.append(kwargs)
            return FakeContext()

    monkeypatch.setattr(
        acquisition_browser_pool,
        "_resolve_browser_binary",
        lambda _engine: ("C:/Chrome/chrome.exe", "C:/Chrome/chrome.exe"),
    )
    monkeypatch.setattr(
        acquisition_browser_pool,
        "build_playwright_context_spec",
        lambda **_: _context_spec({"user_agent": "Mozilla/5.0 Runtime/145.0"}),
    )
    monkeypatch.setattr(
        acquisition_browser_runtime.crawler_runtime_settings,
        "browser_real_chrome_native_context",
        True,
    )
    runtime = acquisition_browser_runtime.SharedBrowserRuntime(
        max_contexts=1,
        browser_engine="real_chrome",
    )
    runtime._browser = FakeBrowser()
    runtime._playwright = object()

    async with runtime.page():
        pass

    assert captured_kwargs == [{"no_viewport": True}]

@pytest.mark.asyncio
@pytest.mark.component
async def test_shared_browser_runtime_skips_init_script_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    init_scripts: list[str] = []

    class FakeContext:
        async def route(self, pattern: str, handler) -> None:
            del pattern, handler
            return None

        async def add_init_script(self, script: str) -> None:
            init_scripts.append(script)

        async def new_page(self):
            return SimpleNamespace(context=self)

        async def close(self) -> None:
            return None

    class FakeBrowser:
        async def new_context(self, **kwargs):
            del kwargs
            return FakeContext()

    runtime = crawl_fetch_runtime.SharedBrowserRuntime(max_contexts=1)
    runtime._browser = FakeBrowser()
    runtime._playwright = object()

    monkeypatch.setattr(
        acquisition_browser_pool,
        "build_playwright_context_spec",
        lambda **_: _context_spec(init_script="window.__browserforge = true;"),
    )
    async with runtime.page():
        pass

    assert init_scripts == []

@pytest.mark.asyncio
@pytest.mark.component
async def test_shared_browser_runtime_uses_socks5_auth_bridge_and_keeps_context_proxy_free(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_launch_kwargs: list[dict[str, object]] = []
    captured_context_kwargs: list[dict[str, object]] = []
    bridge_start_calls: list[str] = []
    bridge_close_calls: list[str] = []

    class FakeContext:
        async def route(self, pattern: str, handler) -> None:
            del pattern, handler
            return None

        async def add_init_script(self, script: str) -> None:
            return None

        async def new_page(self):
            return object()

        async def close(self) -> None:
            return None

    class FakeBrowser:
        async def new_context(self, **kwargs):
            captured_context_kwargs.append(kwargs)
            return FakeContext()

    class FakePlaywrightInstance:
        def __init__(self) -> None:
            self.chromium = SimpleNamespace(launch=self._launch)

        async def _launch(self, **kwargs):
            captured_launch_kwargs.append(kwargs)
            return FakeBrowser()

        async def stop(self) -> None:
            return None

    class FakePlaywrightManager:
        async def start(self) -> FakePlaywrightInstance:
            return FakePlaywrightInstance()

    class FakeBridge:
        def __init__(self, upstream) -> None:
            self.upstream = upstream

        async def start(self) -> str:
            bridge_start_calls.append(
                f"{self.upstream.scheme}://{self.upstream.username}:***@{self.upstream.host}:{self.upstream.port}"
            )
            return "socks5://127.0.0.1:8899"

        async def close(self) -> None:
            bridge_close_calls.append("closed")

    monkeypatch.setattr(
        acquisition_browser_pool,
        "build_playwright_context_spec",
        lambda **_: _context_spec(),
    )
    monkeypatch.setattr(acquisition_browser_pool, "Socks5AuthBridge", FakeBridge)
    monkeypatch.setattr(
        "patchright.async_api.async_playwright",
        lambda: FakePlaywrightManager(),
    )

    runtime = crawl_fetch_runtime.SharedBrowserRuntime(
        max_contexts=1,
        launch_proxy="socks5://user-name:pass-word@31.58.9.4:6077",
    )

    async with runtime.page():
        pass

    assert captured_launch_kwargs == [
        {
            "headless": False,
            "args": [
                "--disable-features=IsolateOrigins,site-per-process",
                "--force-webrtc-ip-handling-policy=disable_non_proxied_udp",
                "--window-size=1920,1080",
                "--disable-search-engine-choice-screen",
                "--disable-background-networking",
                "--disable-client-side-phishing-detection",
                "--disable-domain-reliability",
                "--disable-sync",
                "--no-first-run",
                "--headless=new",
            ],
            "proxy": {
                "server": "socks5://127.0.0.1:8899",
            },
        }
    ]
    assert captured_context_kwargs == [{}]
    assert bridge_start_calls == ["socks5://user-name:***@31.58.9.4:6077"]
    await runtime.close()
    assert bridge_close_calls == ["closed"]

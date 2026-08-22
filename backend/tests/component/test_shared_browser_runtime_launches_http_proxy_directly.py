from __future__ import annotations

from .test_browser_context import SimpleNamespace, _authority_with_credentials, _context_spec, _credential_url, _masked_proxy_display, _secret_mapping, acquisition_browser_pool, acquisition_browser_runtime, build_browser_proxy_config, cookie_store, crawl_fetch_runtime, pytest  # fmt: skip
from app.services.acquisition.browser_proxy_config import display_proxy

pytest_plugins = ["tests.component._cookie_store_test_support"]


@pytest.mark.asyncio
@pytest.mark.component
async def test_shared_browser_runtime_launches_http_proxy_directly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_launch_kwargs: list[dict[str, object]] = []

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
            del kwargs
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

    monkeypatch.setattr(
        acquisition_browser_pool,
        "build_playwright_context_spec",
        lambda **_: _context_spec(),
    )
    monkeypatch.setattr(
        "patchright.async_api.async_playwright",
        lambda: FakePlaywrightManager(),
    )

    runtime = crawl_fetch_runtime.SharedBrowserRuntime(
        max_contexts=1,
        launch_proxy=_credential_url(
            scheme="http",
            username="user-name",
            secret="pass-word",
            host="31.58.9.4",
            port=6077,
        ),
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
                "server": "http://31.58.9.4:6077",
                "username": "user-name",
                **_secret_mapping("pass-word"),
            },
        }
    ]


@pytest.mark.asyncio
@pytest.mark.component
async def test_shared_browser_runtime_launches_real_chrome_headful_for_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_launch_kwargs: list[dict[str, object]] = []

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
            del kwargs
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

    monkeypatch.setattr(
        acquisition_browser_pool,
        "build_playwright_context_spec",
        lambda **_: _context_spec(),
    )
    monkeypatch.setattr(
        acquisition_browser_pool,
        "_resolve_browser_binary",
        lambda _engine: ("C:/Chrome/chrome.exe", "C:/Chrome/chrome.exe"),
    )
    monkeypatch.setattr(
        acquisition_browser_runtime.crawler_runtime_settings,
        "browser_real_chrome_force_headful",
        True,
    )
    monkeypatch.setattr(
        acquisition_browser_pool,
        "REAL_CHROME_IGNORE_DEFAULT_ARGS",
        ("--enable-automation", "--remote-debugging-pipe"),
    )
    monkeypatch.setattr(
        "patchright.async_api.async_playwright",
        lambda: FakePlaywrightManager(),
    )

    runtime = crawl_fetch_runtime.SharedBrowserRuntime(
        max_contexts=1,
        browser_engine="real_chrome",
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
            ],
            "executable_path": "C:/Chrome/chrome.exe",
            "ignore_default_args": [
                "--enable-automation",
                "--remote-debugging-pipe",
            ],
        }
    ]


@pytest.mark.component
def test_display_proxy_masks_authenticated_proxy_credentials() -> None:
    assert display_proxy(
        _credential_url(
            scheme="http",
            username="user-name",
            secret="pass-word",
            host="31.58.9.4",
            port=6077,
        )
    ) == _masked_proxy_display(scheme="http", host="31.58.9.4", port=6077)


@pytest.mark.component
def test_build_browser_proxy_config_normalizes_scheme_and_requires_username_for_password() -> (
    None
):
    assert build_browser_proxy_config(
        _credential_url(
            scheme="HTTP",
            username="user",
            secret="pass",
            host="31.58.9.4",
            port=6077,
        )
    ) == {
        "server": "http://31.58.9.4:6077",
        "username": "user",
        **_secret_mapping("pass"),
    }


@pytest.mark.component
def test_display_proxy_redacts_invalid_proxy_credentials() -> None:
    assert (
        display_proxy(
            _authority_with_credentials(
                username="user",
                secret="pass",
                host="31.58.9.4",
                port=6077,
            )
        )
        == "REDACTED"
    )


@pytest.mark.component
def test_storage_state_entry_count_ignores_generators() -> None:
    assert cookie_store._storage_state_entry_count((item for item in range(3))) == 0


@pytest.mark.asyncio
@pytest.mark.component
async def test_block_unneeded_route_allows_fonts_and_protected_challenge_urls() -> None:
    events: list[str] = []

    class FakeRoute:
        def __init__(self, *, resource_type: str, url: str) -> None:
            self.request = SimpleNamespace(resource_type=resource_type, url=url)

        async def abort(self) -> None:
            events.append(f"abort:{self.request.resource_type}:{self.request.url}")

        async def continue_(self) -> None:
            events.append(f"continue:{self.request.resource_type}:{self.request.url}")

    await acquisition_browser_runtime._block_unneeded_route(
        FakeRoute(
            resource_type="font",
            url="https://www.autozone.com/assets/fonts/site-font.woff2",
        )
    )
    await acquisition_browser_runtime._block_unneeded_route(
        FakeRoute(
            resource_type="script",
            url="https://geo.captcha-delivery.com/captcha/?initialCid=abc",
        )
    )

    assert events == [
        "continue:font:https://www.autozone.com/assets/fonts/site-font.woff2",
        "continue:script:https://geo.captcha-delivery.com/captcha/?initialCid=abc",
    ]


@pytest.mark.asyncio
@pytest.mark.component
async def test_block_unneeded_route_aborts_third_party_trackers() -> None:
    events: list[str] = []

    class FakeRoute:
        def __init__(self, *, resource_type: str, url: str) -> None:
            self.request = SimpleNamespace(resource_type=resource_type, url=url)

        async def abort(self) -> None:
            events.append(f"abort:{self.request.resource_type}:{self.request.url}")

        async def continue_(self) -> None:
            events.append(f"continue:{self.request.resource_type}:{self.request.url}")

    await acquisition_browser_runtime._block_unneeded_route(
        FakeRoute(
            resource_type="script",
            url="https://tr.snapchat.com/p?pid=abc",
        )
    )

    assert events == ["abort:script:https://tr.snapchat.com/p?pid=abc"]


@pytest.mark.asyncio
@pytest.mark.component
async def test_shared_browser_runtime_reuses_run_storage_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_kwargs: list[dict[str, object]] = []
    persisted_states: list[tuple[int, dict[str, object]]] = []

    class FakeContext:
        async def route(self, pattern: str, handler) -> None:
            del pattern, handler
            return None

        async def add_init_script(self, script: str) -> None:
            return None

        async def new_page(self):
            return object()

        async def storage_state(self) -> dict[str, object]:
            return {
                "cookies": [
                    {
                        "name": "dd_session",
                        "value": "next-cookie",
                        "domain": ".etsy.com",
                        "path": "/",
                    }
                ],
                "origins": [
                    {
                        "origin": "https://www.etsy.com",
                        "localStorage": [
                            {"name": "consent", "value": "accepted"},
                        ],
                    }
                ],
            }

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
        lambda **_: _context_spec(),
    )

    async def _fake_load_storage_state_for_run(run_id: int | None, **_kwargs):
        del _kwargs
        assert run_id == 77
        return {
            "cookies": [
                {
                    "name": "dd_session",
                    "value": "existing-cookie",
                    "domain": ".etsy.com",
                    "path": "/",
                }
            ],
            "origins": [
                {
                    "origin": "https://www.etsy.com",
                    "localStorage": [
                        {"name": "consent", "value": "accepted"},
                    ],
                }
            ],
        }

    async def _fake_persist_storage_state_for_run(
        run_id: int | None,
        storage_state: dict[str, object],
        **_kwargs,
    ) -> None:
        del _kwargs
        assert run_id == 77
        persisted_states.append((int(run_id), dict(storage_state)))

    monkeypatch.setattr(
        cookie_store,
        "load_storage_state_for_run",
        _fake_load_storage_state_for_run,
    )
    monkeypatch.setattr(
        cookie_store,
        "persist_storage_state_for_run",
        _fake_persist_storage_state_for_run,
    )

    async with runtime.page(run_id=77):
        pass

    assert captured_kwargs == [
        {
            "storage_state": {
                "cookies": [
                    {
                        "name": "dd_session",
                        "value": "existing-cookie",
                        "domain": ".etsy.com",
                        "path": "/",
                    }
                ],
                "origins": [
                    {
                        "origin": "https://www.etsy.com",
                        "localStorage": [
                            {"name": "consent", "value": "accepted"},
                        ],
                    }
                ],
            }
        }
    ]
    assert persisted_states == [
        (
            77,
            {
                "cookies": [
                    {
                        "name": "dd_session",
                        "value": "next-cookie",
                        "domain": ".etsy.com",
                        "path": "/",
                    }
                ],
                "origins": [
                    {
                        "origin": "https://www.etsy.com",
                        "localStorage": [
                            {"name": "consent", "value": "accepted"},
                        ],
                    }
                ],
            },
        )
    ]


@pytest.mark.asyncio
@pytest.mark.component
async def test_real_chrome_context_still_loads_engine_scoped_domain_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    storage_state = {
        "cookies": [
            {
                "name": "session",
                "value": "existing-cookie",
                "domain": ".example.com",
                "path": "/",
            }
        ],
        "origins": [],
    }

    async def _no_run_state(*_args, **_kwargs):
        return None

    async def _domain_state(domain: str | None, *, browser_engine: str):
        assert domain == "example.com"
        assert browser_engine == "real_chrome"
        return storage_state

    monkeypatch.setattr(cookie_store, "load_storage_state_for_run", _no_run_state)
    monkeypatch.setattr(cookie_store, "load_storage_state_for_domain", _domain_state)
    runtime = crawl_fetch_runtime.SharedBrowserRuntime(
        max_contexts=1,
        browser_engine="real_chrome",
    )

    options = await runtime._context_options_with_storage(
        _context_spec(),
        run_id=None,
        domain="example.com",
        allow_storage_state=True,
        allow_domain_storage_state=True,
        phase_timings_ms={},
    )

    assert options["storage_state"] == storage_state


@pytest.mark.asyncio
@pytest.mark.component
async def test_shared_browser_runtime_skips_storage_state_reuse_when_disallowed(
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
            return object()

        async def storage_state(self) -> dict[str, object]:
            return {"cookies": [], "origins": []}

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
        lambda **_: _context_spec(),
    )

    async def _boom(*args, **kwargs):
        raise AssertionError(f"storage state should not load: {args} {kwargs}")

    monkeypatch.setattr(
        cookie_store,
        "load_storage_state_for_run",
        _boom,
    )
    monkeypatch.setattr(
        cookie_store,
        "load_storage_state_for_domain",
        _boom,
    )

    async with runtime.page(
        run_id=77,
        domain="example.com",
        allow_storage_state=False,
    ):
        pass

    assert captured_kwargs == [{}]


@pytest.mark.asyncio
@pytest.mark.component
async def test_shared_browser_runtime_skips_domain_storage_for_proxied_runtime_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_kwargs: list[dict[str, object]] = []
    domain_load_calls: list[str | None] = []
    domain_persist_calls: list[str] = []

    class FakeContext:
        async def route(self, pattern: str, handler) -> None:
            del pattern, handler
            return None

        async def add_init_script(self, script: str) -> None:
            return None

        async def new_page(self):
            return object()

        async def storage_state(self) -> dict[str, object]:
            return {"cookies": [], "origins": []}

        async def close(self) -> None:
            return None

    class FakeBrowser:
        async def new_context(self, **kwargs):
            captured_kwargs.append(kwargs)
            return FakeContext()

    runtime = crawl_fetch_runtime.SharedBrowserRuntime(
        max_contexts=1,
        launch_proxy="http://proxy-one",
    )
    runtime._browser = FakeBrowser()
    runtime._playwright = object()

    monkeypatch.setattr(
        acquisition_browser_pool,
        "build_playwright_context_spec",
        lambda **_: _context_spec(),
    )

    async def _load_run(run_id: int | None, **_kwargs):
        del run_id, _kwargs
        return None

    async def _load_domain(domain: str | None, **_kwargs):
        del _kwargs
        domain_load_calls.append(domain)
        return {"cookies": [], "origins": []}

    async def _persist_domain(
        domain: str, storage_state: dict[str, object], **_kwargs
    ) -> None:
        del storage_state, _kwargs
        domain_persist_calls.append(domain)

    monkeypatch.setattr(
        cookie_store,
        "load_storage_state_for_run",
        _load_run,
    )
    monkeypatch.setattr(
        cookie_store,
        "load_storage_state_for_domain",
        _load_domain,
    )
    monkeypatch.setattr(
        cookie_store,
        "persist_storage_state_for_domain",
        _persist_domain,
    )

    async with runtime.page(run_id=77, domain="example.com"):
        pass

    assert captured_kwargs == [{}]
    assert domain_load_calls == []
    assert domain_persist_calls == []


@pytest.mark.asyncio
@pytest.mark.component
async def test_shared_browser_runtime_suppresses_storage_state_persist_failures(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    class FakeContext:
        async def route(self, pattern: str, handler) -> None:
            del pattern, handler
            return None

        async def add_init_script(self, script: str) -> None:
            return None

        async def new_page(self):
            return object()

        async def storage_state(self) -> dict[str, object]:
            return {"cookies": [], "origins": []}

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
        lambda **_: _context_spec(),
    )

    async def _boom(*args, **kwargs) -> None:
        del args, kwargs
        raise RuntimeError("boom")

    monkeypatch.setattr(
        cookie_store,
        "persist_storage_state_for_run",
        _boom,
    )

    async def _no_state(run_id: int | None, **_kwargs):
        del run_id, _kwargs
        return None

    monkeypatch.setattr(
        cookie_store,
        "load_storage_state_for_run",
        _no_state,
    )

    with caplog.at_level("ERROR", logger=acquisition_browser_runtime.logger.name):
        async with runtime.page(run_id=77):
            pass

    assert any(
        "Failed to persist browser storage state for run_id=77" in record.message
        for record in caplog.records
    )

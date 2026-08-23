from __future__ import annotations

from .test_browser_context import AsyncSession, SimpleNamespace, _context_spec, acquisition_browser_pool, acquisition_browser_runtime, async_sessionmaker, asyncio, cookie_store, crawl_fetch_runtime, crawler_runtime_settings, pytest, uuid4  # fmt: skip

pytest_plugins = ["tests.component._cookie_store_test_support"]


@pytest.mark.asyncio
@pytest.mark.component
async def test_browser_shutdown_bounds_cancel_resistant_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    release_cleanup = asyncio.Event()

    async def _cancel_resistant_cleanup() -> None:
        while not release_cleanup.is_set():
            try:
                await release_cleanup.wait()
            except asyncio.CancelledError:
                continue

    monkeypatch.setattr(
        acquisition_browser_pool.crawler_runtime_settings,
        "browser_close_timeout_ms",
        10,
    )
    cleanup_task = asyncio.create_task(_cancel_resistant_cleanup())
    acquisition_browser_pool.register_browser_cleanup_task(cleanup_task)
    await asyncio.sleep(0)

    await asyncio.wait_for(
        acquisition_browser_runtime.shutdown_browser_runtime(), timeout=1
    )

    assert cleanup_task in acquisition_browser_pool._BROWSER_POOL.eviction_cleanup_tasks
    assert not cleanup_task.done()
    release_cleanup.set()
    await cleanup_task
    await asyncio.sleep(0)
    assert (
        cleanup_task
        not in acquisition_browser_pool._BROWSER_POOL.eviction_cleanup_tasks
    )


@pytest.mark.asyncio
@pytest.mark.component
async def test_browser_runtime_creation_waits_for_shutdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    close_started = asyncio.Event()
    release_close = asyncio.Event()

    class FakeRuntime:
        browser_engine = "chromium"

        async def close(self) -> None:
            close_started.set()
            await release_close.wait()

    await acquisition_browser_runtime.shutdown_browser_runtime()
    acquisition_browser_pool._BROWSER_POOL.direct["chromium"] = FakeRuntime()
    shutdown_task = asyncio.create_task(
        acquisition_browser_runtime.shutdown_browser_runtime()
    )
    await close_started.wait()

    get_task = asyncio.create_task(
        acquisition_browser_runtime.get_browser_runtime(browser_engine="chromium")
    )
    await asyncio.sleep(0)
    assert not get_task.done()

    release_close.set()
    await shutdown_task
    runtime = await get_task

    assert runtime is acquisition_browser_pool._BROWSER_POOL.direct["chromium"]
    await acquisition_browser_runtime.shutdown_browser_runtime()


@pytest.mark.asyncio
@pytest.mark.component
async def test_shared_browser_runtime_bounds_hung_browser_launch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocker = asyncio.Event()
    events: list[str] = []

    class FakePlaywrightInstance:
        def __init__(self) -> None:
            self.chromium = SimpleNamespace(launch=self._launch)

        async def _launch(self, **kwargs):
            del kwargs
            await blocker.wait()

        async def stop(self) -> None:
            events.append("playwright_stopped")

    class FakePlaywrightManager:
        async def start(self) -> FakePlaywrightInstance:
            return FakePlaywrightInstance()

    runtime = acquisition_browser_runtime.SharedBrowserRuntime(max_contexts=1)
    monkeypatch.setattr(
        acquisition_browser_pool,
        "_patchright_async_playwright_factory",
        lambda: lambda: FakePlaywrightManager(),
    )
    monkeypatch.setattr(
        acquisition_browser_runtime.crawler_runtime_settings,
        "browser_launch_timeout_seconds",
        0.05,
    )
    monkeypatch.setattr(
        acquisition_browser_runtime.crawler_runtime_settings,
        "browser_close_timeout_ms",
        50,
    )

    with pytest.raises(asyncio.TimeoutError, match="Timed out launching browser"):
        async with asyncio.timeout(0.5):
            await runtime.ensure()

    assert events == ["playwright_stopped"]
    assert runtime._browser is None
    assert runtime._playwright is None


@pytest.mark.asyncio
@pytest.mark.component
async def test_shared_browser_runtime_bounds_hung_new_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocker = asyncio.Event()

    class FakeBrowser:
        async def new_context(self, **kwargs):
            del kwargs
            await blocker.wait()

    runtime = acquisition_browser_runtime.SharedBrowserRuntime(max_contexts=1)
    runtime._browser = FakeBrowser()
    runtime._playwright = object()

    monkeypatch.setattr(
        acquisition_browser_pool,
        "build_playwright_context_spec",
        lambda **_: _context_spec(),
    )
    monkeypatch.setattr(
        acquisition_browser_runtime.crawler_runtime_settings,
        "browser_context_timeout_ms",
        50,
    )

    with pytest.raises(asyncio.TimeoutError, match="Timed out opening browser context"):
        async with asyncio.timeout(0.5):
            async with runtime.page(allow_storage_state=False):
                pass

    assert runtime._active_contexts == 0


@pytest.mark.asyncio
@pytest.mark.component
async def test_shared_browser_runtime_bounds_hung_new_page_and_closes_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    blocker = asyncio.Event()
    closed: list[str] = []

    class FakeContext:
        async def new_page(self):
            await blocker.wait()

        async def close(self) -> None:
            closed.append("context_closed")

    class FakeBrowser:
        async def new_context(self, **kwargs):
            del kwargs
            return FakeContext()

    runtime = acquisition_browser_runtime.SharedBrowserRuntime(max_contexts=1)
    runtime._browser = FakeBrowser()
    runtime._playwright = object()

    monkeypatch.setattr(
        acquisition_browser_pool,
        "build_playwright_context_spec",
        lambda **_: _context_spec(),
    )
    monkeypatch.setattr(
        acquisition_browser_runtime.crawler_runtime_settings,
        "browser_new_page_timeout_ms",
        50,
    )

    with pytest.raises(asyncio.TimeoutError, match="Timed out opening browser page"):
        async with asyncio.timeout(0.5):
            async with runtime.page(allow_storage_state=False):
                pass

    assert closed == ["context_closed"]
    assert runtime._active_contexts == 0


@pytest.mark.component
def test_browser_runtime_snapshot_reports_runtime_capacity_without_host_cache() -> None:
    snapshot = crawl_fetch_runtime.browser_runtime_snapshot()

    assert "preferred_hosts" not in snapshot
    assert "capacity" in snapshot


@pytest.mark.component
def test_real_chrome_candidate_paths_include_common_platform_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        acquisition_browser_runtime.crawler_runtime_settings,
        "browser_real_chrome_executable_path",
        "",
    )

    candidates = acquisition_browser_runtime._real_chrome_candidate_paths()

    assert "/usr/bin/google-chrome" in candidates
    assert "/opt/google/chrome/chrome" in candidates
    assert "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" in candidates


@pytest.mark.component
def test_real_chrome_browser_available_requires_enabled_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        acquisition_browser_runtime.crawler_runtime_settings,
        "browser_real_chrome_enabled",
        False,
    )

    assert acquisition_browser_runtime.real_chrome_browser_available() is False


@pytest.mark.asyncio
@pytest.mark.component
async def test_get_browser_runtime_evicts_idle_proxied_runtime_when_pool_is_full(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[tuple[str | None, str]] = []
    closed: list[tuple[str | None, str]] = []

    class FakeRuntime:
        def __init__(
            self,
            *,
            max_contexts: int,
            launch_proxy: str | None = None,
            browser_engine: str = "chromium",
        ) -> None:
            del max_contexts
            self.launch_proxy = launch_proxy
            self.browser_engine = browser_engine
            self.browser_binary = browser_engine
            self._last_used_at = 0.0
            created.append((launch_proxy, browser_engine))

        def touch(self) -> None:
            self._last_used_at += 1

        def idle_seconds(self) -> float:
            return 999.0

        def bridge_used(self) -> bool:
            return False

        def eviction_key(self) -> tuple[int, float]:
            return (0, self._last_used_at)

        def snapshot(self) -> dict[str, int | bool | str]:
            return {
                "active": 0,
                "queued": 0,
                "ready": False,
                "browser_engine": self.browser_engine,
            }

        async def close(self) -> None:
            closed.append((self.launch_proxy, self.browser_engine))

    monkeypatch.setattr(
        acquisition_browser_pool,
        "SharedBrowserRuntime",
        FakeRuntime,
    )
    monkeypatch.setattr(
        acquisition_browser_runtime.crawler_runtime_settings,
        "browser_runtime_pool_max_entries",
        1,
    )
    monkeypatch.setattr(
        acquisition_browser_runtime.crawler_runtime_settings,
        "browser_runtime_pool_idle_ttl_seconds",
        0,
    )
    await acquisition_browser_runtime.shutdown_browser_runtime()
    first = await acquisition_browser_runtime.get_browser_runtime(
        proxy="http://proxy-one",
        browser_engine="chromium",
    )
    second = await acquisition_browser_runtime.get_browser_runtime(
        proxy="http://proxy-two",
        browser_engine="real_chrome",
    )

    assert first is not second
    assert created == [
        ("http://proxy-one", "chromium"),
        ("http://proxy-two", "real_chrome"),
    ]
    # Eviction close now runs in a background task; yield to let it complete.
    await asyncio.sleep(0)
    assert closed == [("http://proxy-one", "chromium")]
    await acquisition_browser_runtime.shutdown_browser_runtime()


@pytest.mark.asyncio
@pytest.mark.component
async def test_get_browser_runtime_uses_context_capacity_for_runtime_capacity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        acquisition_browser_pool.crawler_runtime_settings,
        "browser_runtime_context_capacity",
        10,
    )
    monkeypatch.setattr(
        acquisition_browser_pool.crawler_runtime_settings,
        "browser_runtime_pool_max_entries",
        1,
    )

    await acquisition_browser_runtime.shutdown_browser_runtime()
    runtime = await acquisition_browser_runtime.get_browser_runtime(
        browser_engine="chromium"
    )

    try:
        snapshot = runtime.snapshot()
        assert isinstance(runtime, acquisition_browser_pool.SharedBrowserRuntime)
        assert snapshot["capacity"] == 10
        assert snapshot["max_size"] == 10
        assert "browser_instances" not in snapshot
        assert "contexts_per_instance" not in snapshot
    finally:
        await acquisition_browser_runtime.shutdown_browser_runtime()


@pytest.mark.asyncio
@pytest.mark.component
async def test_get_browser_runtime_evicts_idle_direct_runtime_when_pool_is_full(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    created: list[tuple[str | None, str]] = []
    closed: list[tuple[str | None, str]] = []

    class FakeRuntime:
        def __init__(
            self,
            *,
            max_contexts: int,
            launch_proxy: str | None = None,
            browser_engine: str = "chromium",
        ) -> None:
            del max_contexts
            self.launch_proxy = launch_proxy
            self.browser_engine = browser_engine
            self.browser_binary = browser_engine
            self._last_used_at = 0.0
            created.append((launch_proxy, browser_engine))

        def touch(self) -> None:
            self._last_used_at += 1

        def idle_seconds(self) -> float:
            return 999.0

        def eviction_key(self) -> tuple[int, float]:
            return (0, self._last_used_at)

        def snapshot(self) -> dict[str, int | bool | str]:
            return {
                "active": 0,
                "queued": 0,
                "ready": False,
                "browser_engine": self.browser_engine,
            }

        async def close(self) -> None:
            closed.append((self.launch_proxy, self.browser_engine))

    monkeypatch.setattr(
        acquisition_browser_pool,
        "SharedBrowserRuntime",
        FakeRuntime,
    )
    monkeypatch.setattr(
        acquisition_browser_runtime.crawler_runtime_settings,
        "browser_runtime_pool_max_entries",
        1,
    )
    monkeypatch.setattr(
        acquisition_browser_runtime.crawler_runtime_settings,
        "browser_runtime_pool_idle_ttl_seconds",
        0,
    )
    await acquisition_browser_runtime.shutdown_browser_runtime()
    first = await acquisition_browser_runtime.get_browser_runtime(
        browser_engine="chromium"
    )
    second = await acquisition_browser_runtime.get_browser_runtime(
        browser_engine="real_chrome"
    )

    assert first is not second
    assert created == [(None, "chromium"), (None, "real_chrome")]
    # Eviction close now runs in a background task; yield to let it complete.
    await asyncio.sleep(0)
    assert closed == [(None, "chromium")]
    await acquisition_browser_runtime.shutdown_browser_runtime()


@pytest.mark.asyncio
@pytest.mark.component
async def test_browser_pool_skip_evicts_runtime_reused_after_candidate_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    closed: list[str] = []

    class FakeRuntime:
        def __init__(self, name: str, *, last_used: float, idle_seconds: float) -> None:
            self.name = name
            self._last_used_at = last_used
            self._idle_seconds = idle_seconds

        def touch(self) -> None:
            self._last_used_at += 100

        def idle_seconds(self) -> float:
            return self._idle_seconds

        def eviction_key(self) -> tuple[int, float]:
            if self.name == "second":
                first.touch()
            return (0, self._last_used_at)

        async def close(self) -> None:
            closed.append(self.name)

    monkeypatch.setattr(
        acquisition_browser_runtime.crawler_runtime_settings,
        "browser_runtime_pool_max_entries",
        1,
    )
    monkeypatch.setattr(
        acquisition_browser_runtime.crawler_runtime_settings,
        "browser_runtime_pool_idle_ttl_seconds",
        1,
    )

    await acquisition_browser_runtime.shutdown_browser_runtime()
    first = FakeRuntime("first", last_used=1.0, idle_seconds=999.0)
    second = FakeRuntime("second", last_used=2.0, idle_seconds=0.0)
    acquisition_browser_pool._BROWSER_POOL.direct["chromium"] = first
    acquisition_browser_pool._BROWSER_POOL.direct["real_chrome"] = second

    try:
        async with acquisition_browser_pool._BROWSER_POOL.lock:
            to_close = acquisition_browser_pool._evict_idle_browser_runtimes_locked()
        for r in to_close:
            await r.close()

        assert closed == ["second"]
        assert acquisition_browser_pool._BROWSER_POOL.direct["chromium"] is first
    finally:
        await acquisition_browser_runtime.shutdown_browser_runtime()


@pytest.mark.component
def test_browser_launch_args_exclude_detectable_flags() -> None:
    assert (
        "--disable-component-update" not in crawler_runtime_settings.browser_launch_args
    )
    assert (
        "--disable-blink-features=AutomationControlled"
        not in crawler_runtime_settings.browser_launch_args
    )


@pytest.mark.asyncio
@pytest.mark.component
async def test_persist_storage_state_for_domain_commits_owned_session(
    db_session,
    monkeypatch,
) -> None:
    session_factory = async_sessionmaker(
        db_session.bind,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    monkeypatch.setattr(cookie_store, "SessionLocal", session_factory)
    domain = f"owned-session-{uuid4().hex}.example.com"
    saved = await cookie_store.persist_storage_state_for_domain(
        f"https://{domain}/products/widget",
        {
            "cookies": [
                {
                    "name": "session",
                    "value": "abc",
                    "domain": f".{domain}",
                    "path": "/",
                }
            ],
            "origins": [],
        },
    )

    rows = await cookie_store.list_domain_cookie_memory(domain)

    assert saved is True
    assert len(rows) == 1
    assert rows[0]["domain"] == domain


@pytest.mark.asyncio
@pytest.mark.component
async def test_persist_storage_state_for_domain_persists_test_domains(
    db_session,
) -> None:
    domain = f"owned-session-{uuid4().hex}.example.test"

    saved = await cookie_store.persist_storage_state_for_domain(
        f"https://{domain}/products/widget",
        {
            "cookies": [
                {
                    "name": "session",
                    "value": "abc",
                    "domain": f".{domain}",
                    "path": "/",
                }
            ],
            "origins": [],
        },
        session=db_session,
    )

    rows = await cookie_store.list_domain_cookie_memory(domain, session=db_session)
    loaded = await cookie_store.load_storage_state_for_domain(
        domain, session=db_session
    )

    assert saved is True
    assert len(rows) == 1
    assert rows[0]["domain"] == domain
    assert loaded is not None


@pytest.mark.asyncio
@pytest.mark.component
async def test_persist_storage_state_for_domain_strips_null_bytes(db_session) -> None:
    domain = f"null-byte-{uuid4().hex}.example.com"

    saved = await cookie_store.persist_storage_state_for_domain(
        f"https://{domain}/products/widget",
        {
            "cookies": [
                {
                    "name": "session",
                    "value": "abc\x00def",
                    "domain": f".{domain}",
                    "path": "/",
                }
            ],
            "origins": [
                {
                    "origin": f"https://{domain}",
                    "localStorage": [
                        {"name": "cart", "value": '{"id":"123\x00"}'},
                    ],
                }
            ],
        },
        session=db_session,
    )

    loaded = await cookie_store.load_storage_state_for_domain(
        domain, session=db_session
    )

    assert saved is True
    assert loaded is not None
    assert loaded["cookies"][0]["value"] == "abcdef"
    assert loaded["origins"] == []


@pytest.mark.asyncio
@pytest.mark.component
async def test_persist_storage_state_for_domain_keeps_engine_specific_rows(
    db_session,
) -> None:
    domain = f"engine-scoped-{uuid4().hex}.example.com"

    chromium_saved = await cookie_store.persist_storage_state_for_domain(
        f"https://{domain}/products/widget",
        {
            "cookies": [
                {
                    "name": "chromium-session",
                    "value": "1",
                    "domain": f".{domain}",
                    "path": "/",
                }
            ],
            "origins": [],
        },
        session=db_session,
        browser_engine="chromium",
    )
    real_chrome_saved = await cookie_store.persist_storage_state_for_domain(
        f"https://{domain}/products/widget",
        {
            "cookies": [
                {
                    "name": "real-chrome-session",
                    "value": "2",
                    "domain": f".{domain}",
                    "path": "/",
                }
            ],
            "origins": [],
        },
        session=db_session,
        browser_engine="real_chrome",
    )

    rows = await cookie_store.list_domain_cookie_memory(domain, session=db_session)
    chromium_state = await cookie_store.load_storage_state_for_domain(
        domain,
        session=db_session,
        browser_engine="chromium",
    )
    real_chrome_state = await cookie_store.load_storage_state_for_domain(
        domain,
        session=db_session,
        browser_engine="real_chrome",
    )

    assert chromium_saved is True
    assert real_chrome_saved is True
    assert len(rows) == 2
    assert {str(row["browser_engine"]) for row in rows} == {"chromium", "real_chrome"}
    assert chromium_state == {
        "cookies": [
            {
                "name": "chromium-session",
                "value": "1",
                "domain": f".{domain}",
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
                "domain": f".{domain}",
                "path": "/",
            }
        ],
        "origins": [],
    }


@pytest.mark.asyncio
@pytest.mark.component
async def test_persist_storage_state_for_domain_persists_localhost_with_port(
    db_session,
) -> None:
    domain = "http://localhost:3000/products/widget"

    saved = await cookie_store.persist_storage_state_for_domain(
        domain,
        {
            "cookies": [
                {
                    "name": "session",
                    "value": "abc",
                    "domain": "localhost",
                    "path": "/",
                }
            ],
            "origins": [],
        },
        session=db_session,
    )

    rows = await cookie_store.list_domain_cookie_memory(
        "localhost:3000", session=db_session
    )
    all_rows = await cookie_store.list_domain_cookie_memory(session=db_session)
    loaded = await cookie_store.load_storage_state_for_domain(
        "localhost:3000", session=db_session
    )

    assert saved is True
    assert len(rows) == 1
    assert rows[0]["domain"] == "localhost:3000"
    assert any(row["domain"] == "localhost:3000" for row in all_rows)
    assert loaded is not None


@pytest.mark.asyncio
@pytest.mark.component
async def test_persist_storage_state_for_domain_accepts_iterable_storage_rows(
    db_session,
) -> None:
    domain = f"iterable-state-{uuid4().hex}.example.com"

    saved = await cookie_store.persist_storage_state_for_domain(
        f"https://{domain}/products/widget",
        {
            "cookies": (
                {
                    "name": "session",
                    "value": "abc",
                    "domain": f".{domain}",
                    "path": "/",
                },
            ),
            "origins": (
                {
                    "origin": f"https://{domain}",
                    "localStorage": ({"name": "consent", "value": "accepted"},),
                },
            ),
        },
        session=db_session,
    )

    rows = await cookie_store.list_domain_cookie_memory(domain, session=db_session)
    loaded = await cookie_store.load_storage_state_for_domain(
        domain, session=db_session
    )

    assert saved is True
    assert len(rows) == 1
    assert rows[0]["cookie_count"] == 1
    assert rows[0]["origin_count"] == 0
    assert loaded == {
        "cookies": [
            {
                "name": "session",
                "value": "abc",
                "domain": f".{domain}",
                "path": "/",
            }
        ],
        "origins": [],
    }

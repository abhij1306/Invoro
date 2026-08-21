from __future__ import annotations

from .test_browser_context import SimpleNamespace, _context_spec, acquisition_browser_pool, acquisition_browser_runtime, asyncio, browser_storage_state, cookie_store, crawl_fetch_runtime, pytest  # fmt: skip

pytest_plugins = ["tests.component._cookie_store_test_support"]

@pytest.mark.asyncio
@pytest.mark.component
async def test_shared_browser_runtime_bounds_hung_context_cleanup(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    blocker = asyncio.Event()

    class FakeContext:
        async def route(self, pattern: str, handler) -> None:
            del pattern, handler
            return None

        async def add_init_script(self, script: str) -> None:
            return None

        async def new_page(self):
            return object()

        async def storage_state(self) -> dict[str, object]:
            await blocker.wait()
            return {"cookies": [], "origins": []}

        async def close(self) -> None:
            await blocker.wait()

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
    monkeypatch.setattr(
        acquisition_browser_runtime.crawler_runtime_settings,
        "browser_context_timeout_ms",
        50,
    )
    monkeypatch.setattr(
        acquisition_browser_runtime.crawler_runtime_settings,
        "browser_close_timeout_ms",
        50,
    )

    with caplog.at_level("WARNING", logger=acquisition_browser_runtime.logger.name):
        async with asyncio.timeout(1.0):
            async with runtime.page(
                run_id=77,
                domain="example.com",
                allow_storage_state=False,
            ):
                pass

    assert any(
        "Timed out capturing browser storage state" in record.message
        for record in caplog.records
    )
    assert any(
        (
            "Timed out closing browser context" in record.message
            or "Browser context close was cancelled" in record.message
        )
        for record in caplog.records
    )

@pytest.mark.asyncio
@pytest.mark.component
async def test_shared_browser_runtime_releases_pool_slot_when_cleanup_is_cancelled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    close_started = asyncio.Event()
    close_release = asyncio.Event()
    close_calls = 0

    class FakeContext:
        async def route(self, pattern: str, handler) -> None:
            del pattern, handler
            return None

        async def add_init_script(self, script: str) -> None:
            del script
            return None

        async def new_page(self):
            return object()

        async def close(self) -> None:
            nonlocal close_calls
            close_calls += 1
            if close_calls == 1:
                close_started.set()
                await close_release.wait()

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

    async def _use_page() -> None:
        async with runtime.page(allow_storage_state=False):
            await asyncio.sleep(0)

    task = asyncio.create_task(_use_page())
    await asyncio.wait_for(close_started.wait(), timeout=1.0)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        _ = await task

    async def _acquire_again() -> None:
        async with runtime.page(allow_storage_state=False):
            await asyncio.sleep(0)

    await asyncio.wait_for(_acquire_again(), timeout=1.0)
    assert close_calls == 2

@pytest.mark.asyncio
@pytest.mark.component
async def test_shared_browser_runtime_close_bounds_hung_shutdown(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    blocker = asyncio.Event()

    class FakeBrowser:
        async def close(self) -> None:
            await blocker.wait()

    class FakePlaywright:
        async def stop(self) -> None:
            await blocker.wait()

    class FakeBridge:
        async def close(self) -> None:
            await blocker.wait()

    runtime = crawl_fetch_runtime.SharedBrowserRuntime(max_contexts=1)
    runtime._browser = FakeBrowser()
    runtime._playwright = FakePlaywright()
    runtime._socks5_auth_bridge = FakeBridge()

    monkeypatch.setattr(
        acquisition_browser_runtime.crawler_runtime_settings,
        "browser_close_timeout_ms",
        50,
    )

    with caplog.at_level("WARNING", logger=acquisition_browser_runtime.logger.name):
        async with asyncio.timeout(1.0):
            await runtime.close()

    assert runtime._browser is None
    assert runtime._playwright is None
    assert runtime._socks5_auth_bridge is None
    assert any(
        "Timed out closing browser runtime" in record.message
        for record in caplog.records
    )
    assert any(
        "Timed out stopping playwright" in record.message for record in caplog.records
    )
    assert any(
        "Timed out closing SOCKS5 auth bridge" in record.message
        for record in caplog.records
    )

@pytest.mark.asyncio
@pytest.mark.component
async def test_persist_context_storage_state_normalizes_domain_before_persist(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeContext:
        async def storage_state(self) -> dict[str, object]:
            return {"cookies": [], "origins": []}

    persisted_domains: list[str] = []

    async def _persist_domain(
        domain: str, storage_state: dict[str, object], **_kwargs
    ) -> None:
        del storage_state, _kwargs
        persisted_domains.append(domain)

    monkeypatch.setattr(
        cookie_store,
        "persist_storage_state_for_domain",
        _persist_domain,
    )

    await browser_storage_state.persist_context_storage_state(
        FakeContext(),
        run_id=None,
        domain="  example.com  ",
    )

    assert persisted_domains == ["example.com"]

@pytest.mark.asyncio
@pytest.mark.component
async def test_persist_context_storage_state_skips_domain_persist_when_disallowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeContext:
        async def storage_state(self) -> dict[str, object]:
            return {
                "cookies": [
                    {
                        "name": "session",
                        "value": "abc",
                        "domain": ".example.com",
                        "path": "/",
                    }
                ],
                "origins": [],
            }

    persisted_domains: list[str] = []

    async def _persist_domain(
        domain: str, storage_state: dict[str, object], **_kwargs
    ) -> None:
        del storage_state, _kwargs
        persisted_domains.append(domain)

    monkeypatch.setattr(
        cookie_store,
        "persist_storage_state_for_domain",
        _persist_domain,
    )

    await browser_storage_state.persist_context_storage_state(
        FakeContext(),
        run_id=None,
        domain="example.com",
        persist_domain_storage_state=False,
    )

    assert persisted_domains == []

@pytest.mark.asyncio
@pytest.mark.component
async def test_persist_context_storage_state_skips_run_persist_when_disallowed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeContext:
        async def storage_state(self) -> dict[str, object]:
            return {
                "cookies": [
                    {
                        "name": "session",
                        "value": "abc",
                        "domain": ".example.com",
                        "path": "/",
                    }
                ],
                "origins": [],
            }

    persisted_run_ids: list[int] = []

    async def _persist_run(
        run_id: int | None, storage_state: dict[str, object], **_kwargs
    ) -> None:
        del storage_state, _kwargs
        persisted_run_ids.append(int(run_id or 0))

    monkeypatch.setattr(
        cookie_store,
        "persist_storage_state_for_run",
        _persist_run,
    )

    await browser_storage_state.persist_context_storage_state(
        FakeContext(),
        run_id=77,
        domain=None,
        persist_run_storage_state=False,
    )

    assert persisted_run_ids == []

@pytest.mark.asyncio
@pytest.mark.component
async def test_shared_browser_runtime_snapshot_tracks_queue_without_private_semaphore_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered = asyncio.Event()
    release = asyncio.Event()

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

    runtime = crawl_fetch_runtime.SharedBrowserRuntime(max_contexts=1)
    runtime._browser = FakeBrowser()
    runtime._playwright = object()

    monkeypatch.setattr(
        acquisition_browser_pool,
        "build_playwright_context_spec",
        lambda **_: _context_spec(),
    )

    async def _hold_page() -> None:
        async with runtime.page():
            entered.set()
            await release.wait()

    first = asyncio.create_task(_hold_page())
    await entered.wait()
    second = asyncio.create_task(_hold_page())
    await asyncio.sleep(0)

    snapshot = runtime.snapshot()

    assert snapshot["active"] == 1
    assert snapshot["queued"] == 1

    release.set()
    await asyncio.gather(first, second)

@pytest.mark.asyncio
@pytest.mark.component
async def test_shared_browser_runtime_bounds_context_slot_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered = asyncio.Event()
    release = asyncio.Event()

    class FakeContext:
        async def route(self, pattern: str, handler) -> None:
            del pattern, handler
            return None

        async def add_init_script(self, script: str) -> None:
            del script
            return None

        async def new_page(self):
            return object()

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
    monkeypatch.setattr(
        acquisition_browser_pool.crawler_runtime_settings,
        "browser_context_slot_timeout_seconds",
        0.01,
    )
    phase_timings_ms_first: dict[str, int] = {}
    phase_timings_ms_second: dict[str, int] = {}

    async def _hold_page() -> None:
        async with runtime.page(phase_timings_ms=phase_timings_ms_first):
            entered.set()
            await release.wait()

    first = asyncio.create_task(_hold_page())
    await entered.wait()
    try:
        with pytest.raises(TimeoutError, match="browser context slot"):
            async with runtime.page(phase_timings_ms=phase_timings_ms_second):
                await asyncio.sleep(0)
    finally:
        release.set()
        _ = await first

    snapshot = runtime.snapshot()
    assert snapshot["active"] == 0
    assert snapshot["queued"] == 0
    assert phase_timings_ms_first["context_open_ms"] >= 0
    assert phase_timings_ms_first["context_close_ms"] >= 0
    assert phase_timings_ms_second["context_slot_wait_ms"] >= 0
    assert "context_open_ms" not in phase_timings_ms_second
    assert "context_close_ms" not in phase_timings_ms_second

@pytest.mark.asyncio
@pytest.mark.component
async def test_shared_browser_runtime_recycles_browser_without_deadlocking(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_events: list[str] = []
    new_events: list[str] = []

    class FakeContext:
        async def route(self, pattern: str, handler) -> None:
            del pattern, handler
            return None

        async def add_init_script(self, script: str) -> None:
            return None

        async def new_page(self):
            return object()

        async def close(self) -> None:
            new_events.append("context_closed")

    class FakeBrowser:
        def __init__(self, events: list[str]) -> None:
            self._events = events

        def is_connected(self) -> bool:
            return True

        async def new_context(self, **kwargs):
            del kwargs
            self._events.append("new_context")
            return FakeContext()

        async def close(self) -> None:
            self._events.append("browser_closed")

    class FakePlaywrightInstance:
        def __init__(self, events: list[str]) -> None:
            self.chromium = SimpleNamespace(launch=self._launch)
            self._events = events

        async def _launch(self, **kwargs):
            del kwargs
            self._events.append("launched")
            return FakeBrowser(self._events)

        async def stop(self) -> None:
            self._events.append("playwright_stopped")

    class FakePlaywrightManager:
        async def start(self) -> FakePlaywrightInstance:
            return FakePlaywrightInstance(new_events)

    class OldPlaywright:
        async def stop(self) -> None:
            old_events.append("playwright_stopped")

    runtime = crawl_fetch_runtime.SharedBrowserRuntime(max_contexts=1)
    runtime._browser = FakeBrowser(old_events)
    runtime._playwright = OldPlaywright()
    runtime._browser_launched_at = 1.0
    runtime._total_contexts_created = 1

    monkeypatch.setattr(
        acquisition_browser_pool,
        "build_playwright_context_spec",
        lambda **_: _context_spec(),
    )
    monkeypatch.setattr(
        crawl_fetch_runtime.crawler_runtime_settings,
        "browser_max_contexts_before_recycle",
        1,
    )
    monkeypatch.setattr(
        "patchright.async_api.async_playwright", lambda: FakePlaywrightManager()
    )

    async with asyncio.timeout(1):
        async with runtime.page():
            pass

    assert old_events == ["browser_closed", "playwright_stopped"]
    assert new_events == ["launched", "new_context", "context_closed"]

@pytest.mark.asyncio
@pytest.mark.component
async def test_shared_browser_runtime_does_not_recycle_with_active_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entered = asyncio.Event()
    release = asyncio.Event()
    events: list[str] = []

    class FakeContext:
        async def route(self, pattern: str, handler) -> None:
            del pattern, handler
            return None

        async def add_init_script(self, script: str) -> None:
            del script
            return None

        async def new_page(self):
            return object()

        async def close(self) -> None:
            events.append("context_closed")

    class FakeBrowser:
        def is_connected(self) -> bool:
            return True

        async def new_context(self, **kwargs):
            del kwargs
            events.append("new_context")
            return FakeContext()

        async def close(self) -> None:
            events.append("browser_closed")

    runtime = crawl_fetch_runtime.SharedBrowserRuntime(max_contexts=2)
    runtime._browser = FakeBrowser()
    runtime._playwright = object()
    runtime._browser_launched_at = acquisition_browser_pool.time.monotonic()

    monkeypatch.setattr(
        acquisition_browser_pool,
        "build_playwright_context_spec",
        lambda **_: _context_spec(),
    )
    monkeypatch.setattr(
        crawl_fetch_runtime.crawler_runtime_settings,
        "browser_max_contexts_before_recycle",
        1,
    )

    async def _hold_page() -> None:
        async with runtime.page():
            entered.set()
            await release.wait()

    first = asyncio.create_task(_hold_page())
    await entered.wait()
    runtime._total_contexts_created = 1
    async with runtime.page():
        await asyncio.sleep(0)
    release.set()
    _ = await first

    assert "browser_closed" not in events

@pytest.mark.asyncio
@pytest.mark.component
async def test_acquisition_shared_browser_runtime_recycles_after_driver_closed_on_new_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_events: list[str] = []
    new_events: list[str] = []

    class FakeContext:
        async def route(self, pattern: str, handler) -> None:
            del pattern, handler
            return None

        async def add_init_script(self, script: str) -> None:
            return None

        async def new_page(self):
            return object()

        async def close(self) -> None:
            new_events.append("context_closed")

    class DeadBrowser:
        def is_connected(self) -> bool:
            return True

        async def new_context(self, **kwargs):
            del kwargs
            raise Exception(
                "Browser.new_context: Connection closed while reading from the driver"
            )

        async def close(self) -> None:
            old_events.append("browser_closed")

    class FreshBrowser:
        def is_connected(self) -> bool:
            return True

        async def new_context(self, **kwargs):
            del kwargs
            new_events.append("new_context")
            return FakeContext()

        async def close(self) -> None:
            new_events.append("browser_closed")

    class FakePlaywrightInstance:
        def __init__(self) -> None:
            self.chromium = SimpleNamespace(launch=self._launch)

        async def _launch(self, **kwargs):
            del kwargs
            new_events.append("launched")
            return FreshBrowser()

        async def stop(self) -> None:
            old_events.append("playwright_stopped")

    class FakePlaywrightManager:
        async def start(self) -> FakePlaywrightInstance:
            return FakePlaywrightInstance()

    class OldPlaywright:
        async def stop(self) -> None:
            old_events.append("playwright_stopped")

    runtime = acquisition_browser_runtime.SharedBrowserRuntime(max_contexts=1)
    runtime._browser = DeadBrowser()
    runtime._playwright = OldPlaywright()
    runtime._browser_launched_at = 1.0

    monkeypatch.setattr(
        acquisition_browser_pool,
        "build_playwright_context_spec",
        lambda **_: _context_spec(),
    )
    monkeypatch.setattr(
        acquisition_browser_pool,
        "_patchright_async_playwright_factory",
        lambda: lambda: FakePlaywrightManager(),
    )

    async with runtime.page():
        pass

    assert old_events == ["browser_closed", "playwright_stopped"]
    assert new_events == ["launched", "new_context", "context_closed"]

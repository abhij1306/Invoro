from __future__ import annotations

import asyncio
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from app.services.acquisition import cookie_store
from app.services.acquisition.browser_diagnostics import (
    CHROMIUM_BROWSER_ENGINE as _CHROMIUM_BROWSER_ENGINE,
    PATCHRIGHT_BROWSER_ENGINE as _PATCHRIGHT_BROWSER_ENGINE,
    REAL_CHROME_BROWSER_ENGINE as _REAL_CHROME_BROWSER_ENGINE,
    browser_failure_kind as _browser_failure_kind,
    browser_profile_diagnostics as _browser_profile_diagnostics,
    launch_headless_for_engine as _launch_headless_for_engine,
    normalize_browser_engine as _normalize_browser_engine,
    use_native_real_chrome_context as _use_native_real_chrome_context,
)
from app.services.acquisition.browser_identity import (
    PlaywrightContextSpec,
    build_native_real_chrome_context_spec,
    clear_browser_identity_cache,
)
from app.services.acquisition.browser_pool_spec import (
    BrowserRuntimePool,
    aggregate_runtime_snapshots as _aggregate_runtime_snapshots,
    browser_close_timeout_seconds as _browser_close_timeout_seconds,
    browser_context_slot_timeout_seconds as _browser_context_slot_timeout_seconds,
    browser_context_timeout_seconds as _browser_context_timeout_seconds,
    browser_launch_timeout_seconds as _browser_launch_timeout_seconds,
    browser_new_page_timeout_seconds as _browser_new_page_timeout_seconds,
    browser_runtime_context_capacity as _browser_runtime_context_capacity,
    build_playwright_context_spec,
    close_browser_context_safely as _close_browser_context_safely,
    patchright_async_playwright_factory as _patchright_async_playwright_factory,
    real_chrome_candidate_paths as _real_chrome_candidate_paths,
    record_timing as _record_timing,
    Socks5AuthBridge,
    persist_context_storage_state,
    REAL_CHROME_IGNORE_DEFAULT_ARGS,
    wait_for_browser_step as _wait_for_browser_step,
)
from app.services.acquisition.browser_page_helpers import (
    block_unneeded_route as _block_unneeded_route,
    object_int as _int_or_zero,
)
from app.services.acquisition.browser_proxy_bridge import (
    parse_socks5_upstream_proxy,
)
from app.services.acquisition.browser_proxy_config import (
    build_browser_proxy_config as _build_browser_proxy_config,
    normalized_proxy_value as _normalized_proxy_value,
)
from app.services.acquisition.browser_storage_state import (
    DOMAIN_STORAGE_PERSIST_ATTR as _DOMAIN_STORAGE_PERSIST_ATTR,
    RUN_STORAGE_PERSIST_ATTR as _RUN_STORAGE_PERSIST_ATTR,
)
from app.services.config.runtime_settings import crawler_runtime_settings

if TYPE_CHECKING:
    from patchright.async_api import Browser, BrowserContext, Playwright

logger = logging.getLogger(__name__)


_BROWSER_POOL = BrowserRuntimePool()


def register_popup_guard_task(task: asyncio.Task[Any]) -> None:
    _BROWSER_POOL.popup_guard_tasks.add(task)
    task.add_done_callback(_BROWSER_POOL.popup_guard_tasks.discard)


def patchright_browser_available() -> bool:
    if not bool(crawler_runtime_settings.browser_patchright_enabled):
        return False
    try:
        _patchright_async_playwright_factory()
    except Exception:
        return False
    return True


def real_chrome_executable_path() -> str | None:
    if not crawler_runtime_settings.browser_real_chrome_enabled:
        return None
    for candidate in _real_chrome_candidate_paths():
        if Path(candidate).is_file():
            return candidate
    return None


def real_chrome_browser_available() -> bool:
    return real_chrome_executable_path() is not None


def _resolve_browser_binary(engine: str) -> tuple[str | None, str]:
    normalized_engine = _normalize_browser_engine(engine)
    if normalized_engine == _PATCHRIGHT_BROWSER_ENGINE:
        return None, _PATCHRIGHT_BROWSER_ENGINE
    if normalized_engine == _CHROMIUM_BROWSER_ENGINE:
        return None, _CHROMIUM_BROWSER_ENGINE
    executable_path = real_chrome_executable_path()
    if executable_path is None:
        return None, _REAL_CHROME_BROWSER_ENGINE
    return executable_path, executable_path


def _async_playwright_manager_for_engine(engine: str):
    normalized_engine = _normalize_browser_engine(engine)
    try:
        playwright_factory = _patchright_async_playwright_factory
        return playwright_factory()
    except Exception as exc:
        raise RuntimeError(f"Patchright package is not available for {normalized_engine} browser runtime") from exc


class SharedBrowserRuntime:
    def __init__(
        self,
        *,
        max_contexts: int,
        launch_proxy: str | None = None,
        browser_engine: str = _CHROMIUM_BROWSER_ENGINE,
    ) -> None:
        self.max_contexts = max(1, int(max_contexts))
        self.browser_engine = _normalize_browser_engine(browser_engine)
        resolve_binary = _resolve_browser_binary
        self.executable_path, self.browser_binary = resolve_binary(self.browser_engine)
        self.engine_available = bool(
            (
                self.browser_engine in {_PATCHRIGHT_BROWSER_ENGINE, _CHROMIUM_BROWSER_ENGINE}
                and patchright_browser_available()
            )
            or self.executable_path
        )
        self.launch_proxy = _normalized_proxy_value(launch_proxy)
        self.launch_proxy_config = _build_browser_proxy_config(self.launch_proxy)
        self._authenticated_socks5_proxy = parse_socks5_upstream_proxy(self.launch_proxy)
        self._socks5_auth_bridge: Socks5AuthBridge | None = None
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._semaphore = asyncio.Semaphore(self.max_contexts)
        self._lock = asyncio.Lock()
        self._active_contexts = 0
        self._queued_count = 0
        self._total_contexts_created = 0
        self._browser_launched_at: float = 0.0
        self._last_used_at: float = time.monotonic()

    def _should_recycle_browser(self) -> bool:
        if self._browser is None:
            return False
        if not getattr(self._browser, "is_connected", lambda: True)():
            return True
        if self._active_contexts > 0:
            return False
        if self._context_recycle_threshold_reached():
            return True
        max_lifetime = int(crawler_runtime_settings.browser_max_lifetime_seconds)
        if max_lifetime > 0 and self._browser_launched_at > 0:
            if time.monotonic() - self._browser_launched_at >= max_lifetime:
                return True
        return False

    def _context_recycle_threshold_reached(self) -> bool:
        max_contexts = int(crawler_runtime_settings.browser_max_contexts_before_recycle)
        return max_contexts > 0 and self._total_contexts_created >= max_contexts

    async def _yield_slot_until_recycle_window(self, timeout_seconds: float) -> bool:
        if self._browser is None or not self._context_recycle_threshold_reached() or self._active_contexts > 0:
            return False
        deadline = time.monotonic() + max(0.0, timeout_seconds)
        self._semaphore.release()
        while self._active_contexts > 0 and self._context_recycle_threshold_reached():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise asyncio.TimeoutError(f"Timed out waiting for browser context slot after {timeout_seconds:.1f}s")
            await asyncio.sleep(min(0.05, remaining))
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise asyncio.TimeoutError(f"Timed out waiting for browser context slot after {timeout_seconds:.1f}s")
        await asyncio.wait_for(self._semaphore.acquire(), timeout=remaining)
        return True

    async def _ensure(self) -> None:
        if self._browser is not None and not self._should_recycle_browser():
            return
        async with self._lock:
            if self._should_recycle_browser():
                logger.info(
                    "Recycling browser instance (contexts=%d, lifetime=%.0fs)",
                    self._total_contexts_created,
                    time.monotonic() - self._browser_launched_at if self._browser_launched_at else 0,
                )
                await self._close_locked()
            if self._browser is not None:
                return
            try:
                async_playwright = _async_playwright_manager_for_engine(self.browser_engine)
                self._playwright = await _wait_for_browser_step(
                    async_playwright().start(),
                    timeout_seconds=_browser_launch_timeout_seconds(),
                    message="Timed out launching browser driver",
                )
                launch_kwargs = self._browser_launch_kwargs()
                launch_proxy_config = await self._launch_proxy_config_for_browser()
                if launch_proxy_config is not None:
                    launch_kwargs["proxy"] = launch_proxy_config
                self._browser = await _wait_for_browser_step(
                    self._playwright.chromium.launch(**launch_kwargs),
                    timeout_seconds=_browser_launch_timeout_seconds(),
                    message="Timed out launching browser",
                )
                self._browser_launched_at = time.monotonic()
                self._total_contexts_created = 0
            except Exception:
                await self._close_locked()
                raise

    def _browser_launch_kwargs(self) -> dict[str, Any]:
        launch_args = [
            str(value).strip() for value in crawler_runtime_settings.browser_launch_args or () if str(value).strip()
        ]
        launch_headless = _launch_headless_for_engine(self.browser_engine)
        if (
            launch_headless
            and bool(crawler_runtime_settings.browser_use_new_headless)
            and "--headless=new" not in launch_args
        ):
            launch_args.append("--headless=new")
            launch_headless = False
        kwargs: dict[str, Any] = {"headless": launch_headless}
        if launch_args:
            kwargs["args"] = launch_args
        if self.browser_engine == _REAL_CHROME_BROWSER_ENGINE:
            self._apply_real_chrome_launch_options(kwargs)
        return kwargs

    def _apply_real_chrome_launch_options(self, kwargs: dict[str, Any]) -> None:
        if not self.executable_path:
            raise RuntimeError("Real Chrome executable is not available for browser runtime")
        kwargs["executable_path"] = self.executable_path
        ignore_default_args = [str(arg).strip() for arg in REAL_CHROME_IGNORE_DEFAULT_ARGS or () if str(arg).strip()]
        if ignore_default_args:
            kwargs["ignore_default_args"] = ignore_default_args

    async def ensure(self) -> None:
        """Public browser warm-up API."""
        await self._ensure()

    async def _recycle_after_driver_disconnect(self) -> None:
        async with self._lock:
            await self._close_locked()
        await self.ensure()

    async def _open_context_page(
        self,
        *,
        context_options: dict[str, Any],
    ) -> tuple[BrowserContext, Any]:
        last_error: Exception | None = None
        for attempt in range(2):
            if self._browser is None:
                raise RuntimeError("Browser runtime failed to initialize")
            context: BrowserContext | None = None
            try:
                context = await _wait_for_browser_step(
                    self._browser.new_context(**cast(Any, context_options)),
                    timeout_seconds=_browser_context_timeout_seconds(),
                    message="Timed out opening browser context",
                )
                self._total_contexts_created += 1
                page = await _wait_for_browser_step(
                    context.new_page(),
                    timeout_seconds=_browser_new_page_timeout_seconds(),
                    message="Timed out opening browser page",
                )
                return context, page
            except Exception as exc:
                last_error = exc
                if context is not None:
                    await _close_browser_context_safely(context)
                if attempt >= 1 or _browser_failure_kind(exc) not in {
                    "browser_driver_closed",
                    "page_closed",
                }:
                    raise
                logger.warning("Browser runtime disconnected during context bootstrap; recycling runtime")
                await self._recycle_after_driver_disconnect()
        if last_error is not None:
            raise last_error
        raise RuntimeError("Browser runtime failed to create page context")

    async def _launch_proxy_config_for_browser(self) -> dict[str, str] | None:
        if self.launch_proxy_config is None:
            return None
        if self._authenticated_socks5_proxy is None:
            return dict(self.launch_proxy_config)
        if self._socks5_auth_bridge is None:
            bridge_cls = Socks5AuthBridge
            self._socks5_auth_bridge = bridge_cls(self._authenticated_socks5_proxy)
        bridge_proxy = await self._socks5_auth_bridge.start()
        bridge_proxy_config = _build_browser_proxy_config(bridge_proxy)
        if bridge_proxy_config is None:
            raise RuntimeError("SOCKS5 auth bridge failed to expose a browser proxy")
        return bridge_proxy_config

    def touch(self) -> None:
        self._last_used_at = time.monotonic()

    def idle_seconds(self) -> float:
        return max(0.0, time.monotonic() - self._last_used_at)

    def bridge_used(self) -> bool:
        return self._socks5_auth_bridge is not None

    def eviction_key(self) -> tuple[int, float]:
        snapshot = self.snapshot()
        return (
            _int_or_zero(snapshot.get("active")) + _int_or_zero(snapshot.get("queued")),
            self._last_used_at,
        )

    def _build_context_spec(
        self,
        *,
        run_id: int | None = None,
        locality_profile: dict[str, object] | None = None,
    ) -> PlaywrightContextSpec:
        native_real_chrome = _use_native_real_chrome_context(self.browser_engine)
        if native_real_chrome:
            return build_native_real_chrome_context_spec(locality_profile=locality_profile)
        browser_major_version = None
        if self._browser is not None:
            raw_version = str(getattr(self._browser, "version", "") or "")
            try:
                browser_major_version = int(raw_version.split(".", 1)[0])
            except ValueError:
                browser_major_version = None
        spec_builder = build_playwright_context_spec
        spec = spec_builder(
            run_id=run_id,
            browser_major_version=browser_major_version,
            locality_profile=locality_profile,
        )
        return PlaywrightContextSpec(
            context_options=dict(spec.context_options),
            init_script=None,
        )

    @asynccontextmanager
    async def page(
        self,
        *,
        proxy: str | None = None,
        run_id: int | None = None,
        domain: str | None = None,
        locality_profile: dict[str, object] | None = None,
        allow_storage_state: bool = True,
        phase_timings_ms: dict[str, int] | None = None,
    ):
        self._validate_page_proxy(proxy)
        self.touch()
        await self._acquire_context_slot(phase_timings_ms)
        await self._ensure_for_page(phase_timings_ms)
        self._update_active_contexts(1)
        if self._browser is None:
            self._update_active_contexts(-1)
            self._semaphore.release()
            raise RuntimeError("Browser runtime failed to initialize")
        context: BrowserContext | None = None
        try:
            context_spec = self._build_context_spec(
                run_id=run_id,
                locality_profile=locality_profile,
            )
            allow_domain_storage_state = bool(
                allow_storage_state
                and (self.launch_proxy is None or bool(crawler_runtime_settings.browser_proxy_domain_storage_enabled))
            )
            context_options = await self._context_options_with_storage(
                context_spec,
                run_id=run_id,
                domain=domain,
                allow_storage_state=allow_storage_state,
                allow_domain_storage_state=allow_domain_storage_state,
                phase_timings_ms=phase_timings_ms,
            )
            context_open_started_at = time.perf_counter()
            try:
                context, page = await self._open_context_page(
                    context_options=context_options,
                )
            finally:
                _record_timing(
                    phase_timings_ms,
                    "context_open_ms",
                    context_open_started_at,
                )
            yield page
        finally:
            try:
                if context is not None:
                    await self._persist_and_close_context(
                        context,
                        run_id=run_id,
                        domain=domain,
                        allow_domain_storage_state=allow_domain_storage_state,
                        phase_timings_ms=phase_timings_ms,
                    )
            finally:
                self._update_active_contexts(-1)
                self._semaphore.release()

    def _validate_page_proxy(self, proxy: str | None) -> None:
        normalized_proxy = _normalized_proxy_value(proxy)
        if self.launch_proxy is None and normalized_proxy is not None:
            raise RuntimeError("Proxied browser pages require a launch-owned browser runtime")
        if self.launch_proxy is not None and normalized_proxy not in {
            None,
            self.launch_proxy,
        }:
            raise RuntimeError("Browser runtime proxy does not match requested proxy")

    async def _acquire_context_slot(self, phase_timings_ms: dict[str, int] | None) -> None:
        self._update_queue_count(1)
        timeout_seconds = _browser_context_slot_timeout_seconds()
        started_at = time.perf_counter()
        deadline = time.monotonic() + timeout_seconds
        try:
            await asyncio.wait_for(self._semaphore.acquire(), timeout=timeout_seconds)
            await self._yield_slot_until_recycle_window(max(0.0, deadline - time.monotonic()))
        except asyncio.TimeoutError as exc:
            raise asyncio.TimeoutError(
                f"Timed out waiting for browser context slot after {timeout_seconds:.1f}s"
            ) from exc
        finally:
            _record_timing(phase_timings_ms, "context_slot_wait_ms", started_at)
            self._update_queue_count(-1)

    async def _ensure_for_page(self, phase_timings_ms: dict[str, int] | None) -> None:
        should_record = self._browser is None or self._should_recycle_browser()
        started_at = time.perf_counter()
        try:
            await self._ensure()
        except Exception:
            self._semaphore.release()
            raise
        if should_record:
            _record_timing(phase_timings_ms, "browser_start_ms", started_at)

    async def _context_options_with_storage(
        self,
        context_spec: PlaywrightContextSpec,
        *,
        run_id: int | None,
        domain: str | None,
        allow_storage_state: bool,
        allow_domain_storage_state: bool,
        phase_timings_ms: dict[str, int] | None,
    ) -> dict[str, Any]:
        options = dict(context_spec.context_options)
        if not allow_storage_state:
            return options
        started_at = time.perf_counter()
        storage_state = await cookie_store.load_storage_state_for_run(run_id, browser_engine=self.browser_engine)
        if not storage_state and allow_domain_storage_state:
            storage_state = await cookie_store.load_storage_state_for_domain(domain, browser_engine=self.browser_engine)
        if storage_state:
            options["storage_state"] = storage_state
        _record_timing(phase_timings_ms, "storage_state_load_ms", started_at)
        return options

    async def _persist_and_close_context(
        self,
        context: BrowserContext,
        *,
        run_id: int | None,
        domain: str | None,
        allow_domain_storage_state: bool,
        phase_timings_ms: dict[str, int] | None,
    ) -> None:
        persist_started_at = time.perf_counter()
        try:
            await persist_context_storage_state(
                context,
                run_id=run_id,
                domain=domain,
                browser_engine=self.browser_engine,
                persist_run_storage_state=bool(getattr(context, _RUN_STORAGE_PERSIST_ATTR, True)),
                persist_domain_storage_state=bool(
                    allow_domain_storage_state and getattr(context, _DOMAIN_STORAGE_PERSIST_ATTR, True)
                ),
                timeout_seconds=_browser_context_timeout_seconds(),
            )
        finally:
            _record_timing(phase_timings_ms, "storage_state_persist_ms", persist_started_at)
            close_started_at = time.perf_counter()
            await _close_browser_context_safely(context)
            _record_timing(phase_timings_ms, "context_close_ms", close_started_at)

    async def close(self) -> None:
        async with self._lock:
            await self._close_locked()

    async def _close_locked(self) -> None:
        if self._browser is not None:
            try:
                await asyncio.wait_for(
                    self._browser.close(),
                    timeout=_browser_close_timeout_seconds(),
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "Timed out closing browser runtime after %.1fs",
                    _browser_close_timeout_seconds(),
                )
            except Exception:
                logger.debug("Failed to close browser", exc_info=True)
        if self._playwright is not None:
            try:
                await asyncio.wait_for(
                    self._playwright.stop(),
                    timeout=_browser_close_timeout_seconds(),
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "Timed out stopping playwright after %.1fs",
                    _browser_close_timeout_seconds(),
                )
            except Exception:
                logger.debug("Failed to stop playwright", exc_info=True)
        if self._socks5_auth_bridge is not None:
            try:
                await asyncio.wait_for(
                    self._socks5_auth_bridge.close(),
                    timeout=_browser_close_timeout_seconds(),
                )
            except asyncio.TimeoutError:
                logger.warning(
                    "Timed out closing SOCKS5 auth bridge after %.1fs",
                    _browser_close_timeout_seconds(),
                )
            except Exception:
                logger.debug("Failed to close SOCKS5 auth bridge", exc_info=True)
        self._browser = None
        self._playwright = None
        self._socks5_auth_bridge = None
        self._browser_launched_at = 0.0

    def _update_active_contexts(self, delta: int) -> None:
        self._active_contexts = max(0, self._active_contexts + delta)

    def _update_queue_count(self, delta: int) -> None:
        self._queued_count = max(0, self._queued_count + delta)

    def snapshot(self) -> dict[str, object]:
        snapshot: dict[str, object] = {
            "ready": self._browser is not None,
            "size": self._active_contexts,
            "max_size": self.max_contexts,
            "active": self._active_contexts,
            "queued": self._queued_count,
            "capacity": self.max_contexts,
            "total_contexts_created": self._total_contexts_created,
            "browser_lifetime_seconds": int(time.monotonic() - self._browser_launched_at)
            if self._browser_launched_at
            else 0,
            "browser_engine": self.browser_engine,
            **_browser_profile_diagnostics(self.browser_engine),
            "bridge_used": self.bridge_used(),
        }
        return snapshot


async def temporary_browser_page(
    *,
    proxy: str,
    run_id: int | None = None,
    domain: str | None = None,
    browser_engine: str = _CHROMIUM_BROWSER_ENGINE,
    locality_profile: dict[str, object] | None = None,
    allow_storage_state: bool = True,
):
    runtime = await get_browser_runtime(proxy=proxy, browser_engine=browser_engine)
    async with runtime.page(
        run_id=run_id,
        domain=domain,
        locality_profile=locality_profile,
        allow_storage_state=allow_storage_state,
    ) as page:
        yield page


def _evict_idle_browser_runtimes_locked() -> list[SharedBrowserRuntime]:
    return cast(list[SharedBrowserRuntime], _BROWSER_POOL.evict_idle_runtimes_locked())


async def get_browser_runtime(
    *,
    proxy: str | None = None,
    browser_engine: str = _CHROMIUM_BROWSER_ENGINE,
) -> SharedBrowserRuntime:
    normalized_proxy = _normalized_proxy_value(proxy)
    normalized_engine = _normalize_browser_engine(browser_engine)
    if normalized_proxy is None:
        runtime = _BROWSER_POOL.direct.get(normalized_engine)
        if runtime is not None:
            runtime.touch()
            return runtime
    else:
        runtime = _BROWSER_POOL.proxied.get((normalized_engine, normalized_proxy))
        if runtime is not None:
            runtime.touch()
            return runtime
    runtimes_to_close: list[SharedBrowserRuntime] = []
    async with _BROWSER_POOL.lock:
        if normalized_proxy is None:
            runtime = _BROWSER_POOL.direct.get(normalized_engine)
            if runtime is None:
                runtimes_to_close = _evict_idle_browser_runtimes_locked()
                runtime = _build_browser_runtime_entry(
                    max_contexts=_browser_runtime_context_capacity(),
                    browser_engine=normalized_engine,
                )
                _BROWSER_POOL.direct[normalized_engine] = runtime
            runtime.touch()
        else:
            runtimes_to_close = _evict_idle_browser_runtimes_locked()
            runtime = _BROWSER_POOL.proxied.get((normalized_engine, normalized_proxy))
            if runtime is None:
                runtime = _build_browser_runtime_entry(
                    max_contexts=_browser_runtime_context_capacity(),
                    launch_proxy=normalized_proxy,
                    browser_engine=normalized_engine,
                )
                _BROWSER_POOL.proxied[(normalized_engine, normalized_proxy)] = runtime
            runtime.touch()
    for stale_runtime in runtimes_to_close:
        task = asyncio.create_task(_close_evicted_runtime(stale_runtime))
        _BROWSER_POOL.eviction_cleanup_tasks.add(task)
        task.add_done_callback(_BROWSER_POOL.eviction_cleanup_tasks.discard)
    return runtime


async def _close_evicted_runtime(runtime: SharedBrowserRuntime) -> None:
    """Best-effort teardown of an evicted runtime in the background."""
    try:
        await runtime.close()
    except Exception:
        logger.warning(
            "Background eviction cleanup failed for %s runtime",
            getattr(runtime, "browser_engine", "unknown"),
            exc_info=True,
        )


def _build_browser_runtime_entry(
    *,
    max_contexts: int,
    launch_proxy: str | None = None,
    browser_engine: str = _CHROMIUM_BROWSER_ENGINE,
) -> SharedBrowserRuntime:
    total_contexts = max(1, int(max_contexts))
    return SharedBrowserRuntime(
        max_contexts=total_contexts,
        launch_proxy=launch_proxy,
        browser_engine=browser_engine,
    )


async def shutdown_browser_runtime() -> None:
    pending_eviction_tasks = list(_BROWSER_POOL.eviction_cleanup_tasks)
    _BROWSER_POOL.eviction_cleanup_tasks.clear()
    if pending_eviction_tasks:
        await asyncio.gather(*pending_eviction_tasks, return_exceptions=True)
    async with _BROWSER_POOL.lock:
        runtimes = [
            runtime
            for runtime in (
                *_BROWSER_POOL.direct.values(),
                *_BROWSER_POOL.proxied.values(),
            )
            if runtime is not None
        ]
        _BROWSER_POOL.direct.clear()
        _BROWSER_POOL.proxied.clear()
    results = await asyncio.gather(
        *(runtime.close() for runtime in runtimes),
        return_exceptions=True,
    )
    for result in results:
        if isinstance(result, Exception):
            logger.warning(
                "Browser runtime close failed during shutdown: %s",
                result,
            )
    clear_browser_identity_cache()


def shutdown_browser_runtime_sync() -> None:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(shutdown_browser_runtime())
        return
    task = loop.create_task(shutdown_browser_runtime())
    task.add_done_callback(_log_shutdown_task_result)


def browser_runtime_snapshot() -> dict[str, int | bool]:
    runtimes = [
        runtime
        for runtime in (
            *_BROWSER_POOL.direct.values(),
            *_BROWSER_POOL.proxied.values(),
        )
        if runtime is not None
    ]
    return _aggregate_runtime_snapshots(runtimes, default_capacity=_browser_runtime_context_capacity())


def _log_shutdown_task_result(task: asyncio.Task[None]) -> None:
    try:
        task.result()
    except asyncio.CancelledError:
        logger.debug("Browser runtime shutdown task was cancelled")
    except Exception:
        logger.exception("Browser runtime shutdown task failed")


browser_pool_state = _BROWSER_POOL
block_unneeded_route = _block_unneeded_route
real_chrome_candidate_paths = _real_chrome_candidate_paths
resolve_browser_binary = _resolve_browser_binary
patchright_async_playwright_factory = _patchright_async_playwright_factory

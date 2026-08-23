from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from app.services.acquisition.browser_identity import build_playwright_context_spec
from app.services.acquisition.browser_proxy_bridge import Socks5AuthBridge
from app.services.acquisition.browser_storage_state import persist_context_storage_state
from app.services.config.browser_fingerprint_profiles import (
    REAL_CHROME_FALLBACK_EXECUTABLE_PATHS,
    REAL_CHROME_IGNORE_DEFAULT_ARGS,
)
from app.services.config.runtime_settings import crawler_runtime_settings

logger = logging.getLogger(__name__)


class BrowserRuntimePool:
    def __init__(self) -> None:
        self.direct: dict[str, Any] = {}
        self.proxied: dict[tuple[str, str], Any] = {}
        self.lock = asyncio.Lock()
        self.shutdown_lock = asyncio.Lock()
        self.shutdown_complete = asyncio.Event()
        self.shutdown_complete.set()
        self.shutting_down = False
        self.popup_guard_tasks: set[asyncio.Task[Any]] = set()
        self.eviction_cleanup_tasks: set[asyncio.Task[Any]] = set()

    def register_cleanup_task(self, task: asyncio.Task[Any]) -> None:
        self.eviction_cleanup_tasks.add(task)
        task.add_done_callback(self._consume_cleanup_task)
        if self.shutting_down:
            task.cancel()

    def begin_shutdown(self) -> None:
        self.shutting_down = True
        self.shutdown_complete.clear()

    def finish_shutdown(self) -> None:
        self.shutting_down = False
        self.shutdown_complete.set()

    def _consume_cleanup_task(self, task: asyncio.Task[Any]) -> None:
        self.eviction_cleanup_tasks.discard(task)
        if task.cancelled():
            return
        try:
            task.result()
        except Exception:
            logger.debug("Browser background cleanup task failed", exc_info=True)

    def evict_idle_runtimes_locked(self) -> list[Any]:
        idle_ttl = max(
            0, int(crawler_runtime_settings.browser_runtime_pool_idle_ttl_seconds)
        )
        max_entries = max(
            1, int(crawler_runtime_settings.browser_runtime_pool_max_entries)
        )
        expired = [
            entry
            for entry in self._inactive_entries()
            if idle_ttl > 0 and entry[2].idle_seconds() >= idle_ttl
        ]
        candidate_keys = {(pool_name, key) for pool_name, key, *_ in expired}
        remaining = [
            entry
            for entry in self._inactive_entries()
            if (entry[0], entry[1]) not in candidate_keys
        ]
        remaining.sort(key=lambda item: (item[2].eviction_key()[0], item[3]))
        reserve_slot_removals = max(0, self.size() - len(expired) - max_entries + 1)
        candidates = [*expired, *remaining[:reserve_slot_removals]]
        removed = [runtime for entry in candidates if (runtime := self._remove(entry))]
        while self.size() > max_entries:
            inactive = self._inactive_entries()
            if not inactive:
                break
            inactive.sort(key=lambda item: (item[2].eviction_key()[0], item[3]))
            runtime = self._remove(inactive[0])
            if runtime is not None:
                removed.append(runtime)
        return removed

    def _inactive_entries(self) -> list[tuple[str, object, Any, float]]:
        entries: list[tuple[str, object, Any, float]] = []
        for pool_name, pool in (("direct", self.direct), ("proxied", self.proxied)):
            for key, runtime in tuple(pool.items()):
                active_and_queued, last_used = runtime.eviction_key()
                if active_and_queued == 0:
                    entries.append((pool_name, key, runtime, last_used))
        return entries

    def _remove(self, entry: tuple[str, object, Any, float]) -> Any | None:
        pool_name, key, runtime, candidate_last_used = entry
        pool = self.direct if pool_name == "direct" else self.proxied
        current = pool.get(key)  # type: ignore[call-overload]
        if current is not runtime:
            return None
        active_and_queued, last_used = runtime.eviction_key()
        if active_and_queued != 0 or last_used != candidate_last_used:
            return None
        pool.pop(key, None)  # type: ignore[call-overload]
        return runtime

    def size(self) -> int:
        return len(self.direct) + len(self.proxied)


def patchright_async_playwright_factory():
    from patchright.async_api import async_playwright as patchright_async_playwright

    return patchright_async_playwright


def real_chrome_candidate_paths() -> tuple[str, ...]:
    configured = str(
        crawler_runtime_settings.browser_real_chrome_executable_path or ""
    ).strip()
    if configured:
        return (configured,)
    return REAL_CHROME_FALLBACK_EXECUTABLE_PATHS


def browser_context_timeout_seconds() -> float:
    return max(0.1, float(crawler_runtime_settings.browser_context_timeout_ms) / 1000)


def browser_launch_timeout_seconds() -> float:
    return max(0.1, float(crawler_runtime_settings.browser_launch_timeout_seconds))


def browser_context_slot_timeout_seconds() -> float:
    return max(
        0.1, float(crawler_runtime_settings.browser_context_slot_timeout_seconds)
    )


def browser_new_page_timeout_seconds() -> float:
    return max(0.1, float(crawler_runtime_settings.browser_new_page_timeout_ms) / 1000)


def browser_close_timeout_seconds() -> float:
    return max(0.1, float(crawler_runtime_settings.browser_close_timeout_ms) / 1000)


def browser_runtime_context_capacity() -> int:
    return max(1, int(crawler_runtime_settings.browser_runtime_context_capacity))


async def wait_for_browser_step(
    awaitable: Any, *, timeout_seconds: float, message: str
) -> Any:
    bounded_timeout = max(0.1, float(timeout_seconds))
    try:
        return await asyncio.wait_for(awaitable, timeout=bounded_timeout)
    except asyncio.TimeoutError as exc:
        raise asyncio.TimeoutError(f"{message} after {bounded_timeout:.1f}s") from exc


async def close_browser_context_safely(context: Any) -> None:
    try:
        await asyncio.wait_for(context.close(), timeout=browser_close_timeout_seconds())
    except asyncio.TimeoutError:
        logger.warning(
            "Timed out closing browser context after %.1fs",
            browser_close_timeout_seconds(),
        )
    except asyncio.CancelledError:
        logger.warning("Browser context close was cancelled")
        raise
    except Exception:
        logger.debug("Failed to close browser context", exc_info=True)


def record_timing(
    phase_timings_ms: dict[str, int] | None, key: str, started_at: float
) -> None:
    if phase_timings_ms is not None:
        phase_timings_ms[key] = max(0, int((time.perf_counter() - started_at) * 1000))


def aggregate_runtime_snapshots(
    runtimes: list[Any], *, default_capacity: int
) -> dict[str, int | bool]:
    if not runtimes:
        return {
            "ready": False,
            "size": 0,
            "max_size": default_capacity,
            "active": 0,
            "queued": 0,
            "capacity": default_capacity,
        }
    snapshots = [runtime.snapshot() for runtime in runtimes]
    return {
        "ready": any(bool(snapshot.get("ready")) for snapshot in snapshots),
        "size": sum(_snapshot_count(snapshot, "size") for snapshot in snapshots),
        "max_size": sum(
            _snapshot_count(snapshot, "max_size", "capacity") for snapshot in snapshots
        ),
        "active": sum(_snapshot_count(snapshot, "active") for snapshot in snapshots),
        "queued": sum(_snapshot_count(snapshot, "queued") for snapshot in snapshots),
        "capacity": sum(
            _snapshot_count(snapshot, "capacity", "max_size") for snapshot in snapshots
        ),
        "total_contexts_created": sum(
            _snapshot_count(snapshot, "total_contexts_created")
            for snapshot in snapshots
        ),
        "browser_lifetime_seconds": max(
            _snapshot_count(snapshot, "browser_lifetime_seconds")
            for snapshot in snapshots
        ),
    }


def _snapshot_count(snapshot: dict[str, object], *keys: str) -> int:
    for key in keys:
        value = snapshot.get(key)
        if value is not None:
            return _object_int(value)
    return 0


def _object_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    try:
        return int(str(value or 0))
    except (TypeError, ValueError):
        return 0


__all__ = [
    "build_playwright_context_spec",
    "Socks5AuthBridge",
    "persist_context_storage_state",
    "REAL_CHROME_IGNORE_DEFAULT_ARGS",
    "BrowserRuntimePool",
]

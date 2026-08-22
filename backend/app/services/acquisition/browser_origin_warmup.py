import asyncio
import logging
import time
from contextlib import suppress
from typing import Any
from urllib.parse import urlparse
from weakref import WeakKeyDictionary

from app.services.acquisition.browser_diagnostics import (
    CHROMIUM_BROWSER_ENGINE,
    REAL_CHROME_BROWSER_ENGINE,
    normalize_browser_engine,
)
from app.services.acquisition.browser_readiness import looks_like_low_content_shell
from app.services.acquisition.browser_recovery import recover_browser_challenge
from app.services.acquisition.dom_runtime import get_page_html
from app.services.acquisition.runtime import classify_blocked_page_async
from app.services.config.browser_fingerprint_profiles import (
    WARMUP_ELIGIBLE_BROWSER_REASONS,
    WARMUP_VENDOR_BLOCK_PREFIX,
)
from app.services.config.runtime_settings import (
    crawler_runtime_settings,
    proxy_rotation_mode,
)

logger = logging.getLogger(__name__)

ORIGIN_WARMUP_STATE_LOCKS: WeakKeyDictionary[asyncio.AbstractEventLoop, asyncio.Lock] = WeakKeyDictionary()
ORIGIN_WARMUP_IN_FLIGHT: set[tuple[str, str, str, str]] = set()
ORIGIN_WARMUP_RECENT: dict[tuple[str, str, str, str], float] = {}
ORIGIN_WARMUP_RECENT_MAX_ENTRIES = 512


def origin_warmup_state_lock() -> asyncio.Lock:
    loop = asyncio.get_running_loop()
    lock = ORIGIN_WARMUP_STATE_LOCKS.get(loop)
    if lock is None:
        lock = asyncio.Lock()
        ORIGIN_WARMUP_STATE_LOCKS[loop] = lock
    return lock


async def maybe_warm_origin_before_navigation(
    page: Any,
    *,
    url: str,
    surface: str,
    browser_engine: str = CHROMIUM_BROWSER_ENGINE,
    browser_reason: str | None,
    host_policy_snapshot: dict[str, object] | None,
    proxy: str | None = None,
    proxy_profile: dict[str, object] | None,
    skip_for_reusable_domain_state: bool = False,
    timeout_seconds: float,
    phase_timings_ms: dict[str, int],
) -> None:
    request = _origin_warmup_request(
        url=url,
        surface=surface,
        browser_engine=browser_engine,
        browser_reason=browser_reason,
        host_policy_snapshot=host_policy_snapshot,
        proxy_profile=proxy_profile,
        skip_for_reusable_domain_state=skip_for_reusable_domain_state,
        timeout_seconds=timeout_seconds,
    )
    if request is None:
        return
    warm_url, warm_pause_ms, warm_budget_ms = request
    warmup_key = origin_warmup_key(
        url=url,
        browser_engine=browser_engine,
        proxy=proxy,
        proxy_profile=proxy_profile,
    )
    if not await begin_origin_warmup(warmup_key):
        phase_timings_ms["origin_warmup"] = 0
        return
    if warm_budget_ms < 750:
        await asyncio.shield(finish_origin_warmup(warmup_key))
        return
    await _perform_origin_warmup(
        page,
        url=url,
        warm_url=warm_url,
        browser_engine=browser_engine,
        warm_pause_ms=warm_pause_ms,
        warm_budget_ms=warm_budget_ms,
        warmup_key=warmup_key,
        phase_timings_ms=phase_timings_ms,
    )


def _origin_warmup_request(
    *,
    url: str,
    surface: str,
    browser_engine: str,
    browser_reason: str | None,
    host_policy_snapshot: dict[str, object] | None,
    proxy_profile: dict[str, object] | None,
    skip_for_reusable_domain_state: bool,
    timeout_seconds: float,
) -> tuple[str, int, int] | None:
    reason = str(browser_reason or "").strip().lower()
    if not _origin_warmup_is_eligible(
        surface=surface,
        browser_engine=browser_engine,
        reason=reason,
        host_policy_snapshot=host_policy_snapshot,
        proxy_profile=proxy_profile,
        skip_for_reusable_domain_state=skip_for_reusable_domain_state,
    ):
        return None
    warm_pause_ms = max(0, int(crawler_runtime_settings.origin_warm_pause_ms or 0))
    parsed = urlparse(url)
    warm_url = f"{parsed.scheme}://{parsed.netloc}/"
    if (
        warm_pause_ms <= 0
        or not parsed.scheme
        or not parsed.netloc
        or warm_url.rstrip("/") == str(url or "").strip().rstrip("/")
    ):
        return None
    ratio = max(0.0, float(crawler_runtime_settings.origin_warmup_max_budget_ratio))
    budget_ms = min(
        max(750, int(max(0.1, float(timeout_seconds)) * 1000 * ratio)),
        int(crawler_runtime_settings.browser_navigation_domcontentloaded_timeout_ms),
    )
    return warm_url, warm_pause_ms, budget_ms


def _origin_warmup_is_eligible(
    *,
    surface: str,
    browser_engine: str,
    reason: str,
    host_policy_snapshot: dict[str, object] | None,
    proxy_profile: dict[str, object] | None,
    skip_for_reusable_domain_state: bool,
) -> bool:
    if "detail" not in str(surface or "").strip().lower():
        return False
    if proxy_rotation_mode(proxy_profile) == "rotating" or skip_for_reusable_domain_state:
        return False
    if reason in {
        "detail-shell retry",
        "challenge-shell retry",
        "low-quality-extraction retry",
    }:
        return False
    if not (reason in WARMUP_ELIGIBLE_BROWSER_REASONS or reason.startswith(WARMUP_VENDOR_BLOCK_PREFIX)):
        return False
    host_policy = dict(host_policy_snapshot or {})
    non_native_vendor_preference = (
        normalize_browser_engine(browser_engine) != REAL_CHROME_BROWSER_ENGINE
        and bool(host_policy.get("prefer_browser"))
        and bool(str(host_policy.get("last_block_vendor") or "").strip())
    )
    return not non_native_vendor_preference


async def _perform_origin_warmup(
    page: Any,
    *,
    url: str,
    warm_url: str,
    browser_engine: str,
    warm_pause_ms: int,
    warm_budget_ms: int,
    warmup_key: tuple[str, str, str, str],
    phase_timings_ms: dict[str, int],
) -> None:
    started_at = time.perf_counter()
    use_active_page = normalize_browser_engine(browser_engine) == REAL_CHROME_BROWSER_ENGINE
    warm_page = None
    succeeded = False
    try:
        warm_page = await _warmup_page(page, use_active_page=use_active_page, url=url)
        if warm_page is None:
            return
        warm_phase_timings_ms = await _navigate_warmup_page(
            warm_page,
            warm_url=warm_url,
            browser_engine=browser_engine,
            warm_budget_ms=warm_budget_ms,
            started_at=started_at,
        )
        phase_timings_ms["origin_warmup_behavior"] = 0
        remaining_ms = max(0, warm_budget_ms - elapsed_ms(started_at))
        await warm_page.wait_for_timeout(min(warm_pause_ms, remaining_ms))
        succeeded = True
        _copy_challenge_timings(phase_timings_ms, warm_phase_timings_ms)
    except Exception:
        logger.debug("Origin warmup failed for %s", url, exc_info=True)
    finally:
        if warm_page is not None and not use_active_page:
            close_page = getattr(warm_page, "close", None)
            if callable(close_page):
                with suppress(Exception):
                    await close_page()
        phase_timings_ms["origin_warmup"] = elapsed_ms(started_at)
        await asyncio.shield(finish_origin_warmup(warmup_key, succeeded=succeeded))


async def _warmup_page(page: Any, *, use_active_page: bool, url: str) -> Any | None:
    if use_active_page:
        return page
    context = getattr(page, "context", None)
    if callable(context):
        with suppress(Exception):
            context = context()
    new_page = getattr(context, "new_page", None)
    if not callable(new_page):
        logger.debug(
            "Skipping origin warmup for %s because page context cannot spawn a sibling page",
            url,
        )
        return None
    return await new_page()


async def _navigate_warmup_page(
    warm_page: Any,
    *,
    warm_url: str,
    browser_engine: str,
    warm_budget_ms: int,
    started_at: float,
) -> dict[str, int]:
    response = await warm_page.goto(warm_url, wait_until="domcontentloaded", timeout=warm_budget_ms)
    remaining_ms = max(750, warm_budget_ms - elapsed_ms(started_at))
    timings: dict[str, int] = {}
    await recover_browser_challenge(
        warm_page,
        url=warm_url,
        response=response,
        browser_engine=browser_engine,
        timeout_seconds=max(1.0, remaining_ms / 1000),
        phase_timings_ms=timings,
        challenge_wait_max_seconds=min(
            max(0.0, float(crawler_runtime_settings.challenge_wait_max_seconds or 0)),
            max(1.0, remaining_ms / 1000),
        ),
        challenge_poll_interval_ms=int(crawler_runtime_settings.challenge_poll_interval_ms),
        navigation_timeout_ms=remaining_ms,
        elapsed_ms=elapsed_ms,
        classify_blocked_page=classify_blocked_page_async,
        get_page_html=get_page_html,
        looks_like_low_content_shell=looks_like_low_content_shell,
    )
    return timings


def _copy_challenge_timings(phase_timings_ms: dict[str, int], warm_timings: dict[str, int]) -> None:
    for source, target in (
        ("challenge_wait", "origin_warmup_challenge_wait"),
        ("challenge_retry", "origin_warmup_challenge_retry"),
    ):
        if warm_timings.get(source):
            phase_timings_ms[target] = int(warm_timings[source])


def origin_warmup_key(
    *,
    url: str,
    browser_engine: str,
    proxy: str | None,
    proxy_profile: dict[str, object] | None,
) -> tuple[str, str, str, str]:
    parsed = urlparse(url)
    return (
        normalize_browser_engine(browser_engine),
        str(parsed.scheme or "").lower(),
        str(parsed.netloc or "").lower(),
        str(proxy or proxy_rotation_mode(proxy_profile) or "direct").lower(),
    )


async def begin_origin_warmup(key: tuple[str, str, str, str]) -> bool:
    now = time.monotonic()
    ttl_seconds = max(0.0, float(crawler_runtime_settings.origin_warmup_dedupe_ttl_seconds))
    async with origin_warmup_state_lock():
        _prune_recent_warmups(now=now, ttl_seconds=ttl_seconds)
        if key in ORIGIN_WARMUP_IN_FLIGHT:
            return False
        completed_at = ORIGIN_WARMUP_RECENT.get(key)
        if ttl_seconds > 0 and completed_at is not None:
            if now - completed_at < ttl_seconds:
                return False
        ORIGIN_WARMUP_IN_FLIGHT.add(key)
        return True


def _prune_recent_warmups(*, now: float, ttl_seconds: float) -> None:
    if ttl_seconds <= 0:
        ORIGIN_WARMUP_RECENT.clear()
        return
    for key, completed_at in tuple(ORIGIN_WARMUP_RECENT.items()):
        if now - completed_at >= ttl_seconds:
            ORIGIN_WARMUP_RECENT.pop(key, None)
    if len(ORIGIN_WARMUP_RECENT) <= ORIGIN_WARMUP_RECENT_MAX_ENTRIES:
        return
    keep_count = ORIGIN_WARMUP_RECENT_MAX_ENTRIES // 2
    excess = len(ORIGIN_WARMUP_RECENT) - keep_count
    for key in list(ORIGIN_WARMUP_RECENT.keys())[:excess]:
        ORIGIN_WARMUP_RECENT.pop(key, None)


async def finish_origin_warmup(key: tuple[str, str, str, str], *, succeeded: bool = False) -> None:
    async with origin_warmup_state_lock():
        ORIGIN_WARMUP_IN_FLIGHT.discard(key)
        ttl_seconds = max(0.0, float(crawler_runtime_settings.origin_warmup_dedupe_ttl_seconds))
        if succeeded and ttl_seconds > 0:
            ORIGIN_WARMUP_RECENT[key] = time.monotonic()


def elapsed_ms(started_at: float) -> int:
    return max(0, int((time.perf_counter() - started_at) * 1000))

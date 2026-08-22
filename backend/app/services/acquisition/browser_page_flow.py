from __future__ import annotations
import asyncio
import logging
import time
from typing import Any
from urllib.parse import urlsplit
from patchright.async_api import Error as PlaywrightError
from patchright.async_api import TimeoutError as PlaywrightTimeoutError

from app.services.acquisition.browser_readiness import (
    HtmlAnalysis,
    analyze_html,
    looks_like_low_content_shell,
)
from app.services.acquisition.browser_page_helpers import (
    dismiss_safe_location_interstitial,
    location_interstitial_detected,
    normalize_listing_recovery_mode as _normalize_listing_recovery_mode,
    page_might_have_location_interstitial,
    run_detail_expansion,
    select_primary_browser_html as _select_primary_browser_html,
)
from app.services.acquisition.dom_runtime import get_page_html
from app.services.acquisition.browser_recovery import (
    recover_browser_challenge,
)
from app.services.acquisition.runtime import (
    BlockPageClassification,
    classify_blocked_page_async,
)
from app.services.config.selectors import (
    CARD_SELECTORS,
)
from app.services.config.runtime_settings import crawler_runtime_settings
from app.services.platform_policy import (
    resolve_browser_readiness_policy,
)

logger = logging.getLogger(__name__)

__all__ = [
    "BlockPageClassification",
    "dismiss_safe_location_interstitial",
    "location_interstitial_detected",
    "page_might_have_location_interstitial",
]


def _generic_card_selectors_for_surface(surface: str | None) -> list[str]:
    if not isinstance(CARD_SELECTORS, dict):
        return []
    normalized_surface = str(surface or "").strip().lower()
    if normalized_surface == "jobs" or normalized_surface.startswith("job_"):
        groups = ("jobs",)
    else:
        # All non-job listing surfaces use the ecommerce selector group for
        # readiness detection, matching the extractor's listing_selector_group.
        groups = ("ecommerce",)
    selectors: list[str] = []
    seen: set[str] = set()
    for group in groups:
        for selector in CARD_SELECTORS.get(group) or []:
            normalized = str(selector or "").strip()
            if normalized and normalized not in seen:
                selectors.append(normalized)
                seen.add(normalized)
    return selectors


def remaining_timeout_factory(deadline: float):
    def _remaining() -> float:
        return max(2.0, deadline - time.perf_counter())

    return _remaining


def _is_navigation_interrupted_error(exc: Exception) -> bool:
    return "interrupted by another navigation" in str(exc or "").strip().lower()


def _urls_match_for_navigation(expected_url: str, current_url: str) -> bool:
    expected = urlsplit(str(expected_url or "").strip())
    current = urlsplit(str(current_url or "").strip())
    if not expected.scheme or not expected.netloc:
        return False
    return (
        expected.scheme.lower(),
        expected.netloc.lower(),
        expected.path.rstrip("/") or "/",
        expected.query,
    ) == (
        current.scheme.lower(),
        current.netloc.lower(),
        current.path.rstrip("/") or "/",
        current.query,
    )


async def _recover_interrupted_navigation(
    page: Any,
    *,
    url: str,
    wait_until: str,
    timeout_ms: int,
) -> bool:
    if timeout_ms <= 0:
        return False
    recovery_state = "domcontentloaded" if wait_until == "commit" else wait_until
    if recovery_state not in {"load", "domcontentloaded", "networkidle"}:
        recovery_state = "domcontentloaded"
    try:
        await page.wait_for_load_state(recovery_state, timeout=timeout_ms)
    except (asyncio.TimeoutError, PlaywrightTimeoutError, PlaywrightError):
        return False
    return _urls_match_for_navigation(url, str(getattr(page, "url", "") or ""))


async def _goto_with_interrupted_navigation_recovery(
    page: Any,
    *,
    url: str,
    wait_until: str,
    timeout_ms: int,
):
    try:
        return await page.goto(
            url,
            wait_until=wait_until,
            timeout=timeout_ms,
        )
    except PlaywrightError as exc:
        if not _is_navigation_interrupted_error(exc):
            raise
        if not await _recover_interrupted_navigation(
            page,
            url=url,
            wait_until=wait_until,
            timeout_ms=timeout_ms,
        ):
            raise
        logger.debug(
            "Recovered interrupted navigation url=%s wait_until=%s current_url=%s",
            url,
            wait_until,
            getattr(page, "url", ""),
        )
        return None


async def navigate_browser_page_impl(
    page: Any,
    *,
    url: str,
    browser_engine: str | None = None,
    timeout_seconds: float,
    phase_timings_ms: dict[str, int],
    readiness_policy: dict[str, object] | None,
    crawler_runtime_settings,
    elapsed_ms,
):
    navigation_wait_until = (
        str((readiness_policy or {}).get("navigation_wait_until") or "domcontentloaded")
        .strip()
        .lower()
    )
    total_timeout_ms = int(timeout_seconds * 1000)
    primary_timeout_cap_ms = int(
        crawler_runtime_settings.browser_navigation_domcontentloaded_timeout_ms
    )
    if navigation_wait_until == "networkidle":
        primary_timeout_cap_ms = min(
            int(crawler_runtime_settings.browser_navigation_networkidle_timeout_ms),
            max(
                1,
                int(
                    total_timeout_ms
                    * float(
                        crawler_runtime_settings.browser_navigation_networkidle_primary_budget_ratio
                    )
                ),
            ),
        )
    goto_timeout_ms = min(total_timeout_ms, primary_timeout_cap_ms)
    fallback_timeout_ms = min(
        total_timeout_ms,
        int(crawler_runtime_settings.browser_navigation_min_final_commit_timeout_ms),
    )
    navigation_strategy = navigation_wait_until
    navigation_started_at = time.perf_counter()
    try:
        response = await _goto_with_interrupted_navigation_recovery(
            page,
            url=url,
            wait_until=navigation_wait_until,
            timeout_ms=goto_timeout_ms,
        )
    except (PlaywrightTimeoutError, PlaywrightError):
        fallback_strategy = (
            "domcontentloaded" if navigation_wait_until == "networkidle" else "commit"
        )
        navigation_strategy = fallback_strategy
        try:
            fallback_timeout = (
                min(
                    total_timeout_ms,
                    int(
                        crawler_runtime_settings.browser_navigation_domcontentloaded_timeout_ms
                    ),
                )
                if fallback_strategy == "domcontentloaded"
                else fallback_timeout_ms
            )
            response = await _goto_with_interrupted_navigation_recovery(
                page,
                url=url,
                wait_until=fallback_strategy,
                timeout_ms=fallback_timeout,
            )
        except Exception as exc:
            if fallback_strategy != "commit":
                navigation_strategy = "commit"
                try:
                    response = await _goto_with_interrupted_navigation_recovery(
                        page,
                        url=url,
                        wait_until="commit",
                        timeout_ms=fallback_timeout_ms,
                    )
                except Exception as final_exc:
                    phase_timings_ms["navigation"] = elapsed_ms(navigation_started_at)
                    setattr(
                        final_exc, "browser_phase_timings_ms", dict(phase_timings_ms)
                    )
                    setattr(
                        final_exc, "browser_navigation_strategy", navigation_strategy
                    )
                    raise
            else:
                phase_timings_ms["navigation"] = elapsed_ms(navigation_started_at)
                setattr(exc, "browser_phase_timings_ms", dict(phase_timings_ms))
                setattr(exc, "browser_navigation_strategy", navigation_strategy)
                raise
    finally:
        phase_timings_ms["navigation"] = elapsed_ms(navigation_started_at)
    response = await recover_browser_challenge(
        page,
        url=url,
        response=response,
        browser_engine=browser_engine,
        timeout_seconds=timeout_seconds,
        phase_timings_ms=phase_timings_ms,
        challenge_wait_max_seconds=float(
            crawler_runtime_settings.challenge_wait_max_seconds or 0
        ),
        challenge_poll_interval_ms=int(
            crawler_runtime_settings.challenge_poll_interval_ms
        ),
        navigation_timeout_ms=int(
            crawler_runtime_settings.browser_navigation_domcontentloaded_timeout_ms
        ),
        elapsed_ms=elapsed_ms,
        classify_blocked_page=classify_blocked_page_async,
        get_page_html=get_page_html,
        looks_like_low_content_shell=looks_like_low_content_shell,
    )
    if response is not None:
        recovered_strategy = getattr(response, "browser_navigation_strategy", None)
        if recovered_strategy is not None:
            navigation_strategy = str(recovered_strategy) or navigation_strategy
    return response, navigation_strategy


async def settle_browser_page_impl(
    page: Any,
    *,
    url: str,
    surface: str,
    requested_fields: list[str] | None,
    timeout_seconds: float,
    readiness_override: dict[str, object] | None,
    readiness_policy: dict[str, object],
    phase_timings_ms: dict[str, int],
    crawler_runtime_settings,
    get_page_html_impl=get_page_html,
    probe_browser_readiness,
    wait_for_listing_readiness,
    expand_detail_content_if_needed,
    append_readiness_probe,
    elapsed_ms,
):
    readiness_probes: list[dict[str, object]] = []
    cached_html: str | None = None
    cached_analysis: HtmlAnalysis | None = None

    async def _cached_probe(*, refresh_html: bool = False) -> dict[str, object]:
        nonlocal cached_html, cached_analysis
        if refresh_html or cached_html is None:
            cached_html = await get_page_html_impl(page)
            cached_analysis = analyze_html(cached_html or "")
        elif cached_analysis is None:
            cached_analysis = analyze_html(cached_html or "")
        return await probe_browser_readiness(
            page,
            url=url,
            surface=surface,
            listing_override=readiness_override,
            html=cached_html,
            analysis=cached_analysis,
        )

    current_probe = await _cached_probe(refresh_html=True)
    append_readiness_probe(
        readiness_probes, stage="after_navigation", probe=current_probe
    )
    is_listing_surface = "listing" in str(surface or "").lower()
    is_detail_surface = "detail" in str(surface or "").lower()
    current_probe = await _run_optimistic_readiness_wait(
        page,
        current_probe=current_probe,
        timeout_seconds=timeout_seconds,
        settings=crawler_runtime_settings,
        phase_timings_ms=phase_timings_ms,
        cached_probe=_cached_probe,
        readiness_probes=readiness_probes,
        append_readiness_probe=append_readiness_probe,
        elapsed_ms=elapsed_ms,
    )
    (
        current_probe,
        networkidle_timed_out,
        networkidle_skip_reason,
    ) = await _run_networkidle_settle(
        page,
        current_probe=current_probe,
        timeout_seconds=timeout_seconds,
        readiness_policy=readiness_policy,
        is_listing_surface=is_listing_surface,
        is_detail_surface=is_detail_surface,
        settings=crawler_runtime_settings,
        phase_timings_ms=phase_timings_ms,
        cached_probe=_cached_probe,
        readiness_probes=readiness_probes,
        append_readiness_probe=append_readiness_probe,
        elapsed_ms=elapsed_ms,
    )
    current_probe, readiness_diagnostics = await _run_surface_readiness_wait(
        page,
        url=url,
        surface=surface,
        current_probe=current_probe,
        timeout_seconds=timeout_seconds,
        readiness_override=readiness_override,
        is_listing_surface=is_listing_surface,
        is_detail_surface=is_detail_surface,
        settings=crawler_runtime_settings,
        phase_timings_ms=phase_timings_ms,
        cached_probe=_cached_probe,
        readiness_probes=readiness_probes,
        wait_for_listing_readiness=wait_for_listing_readiness,
        append_readiness_probe=append_readiness_probe,
        elapsed_ms=elapsed_ms,
    )
    current_probe, expansion_diagnostics = await run_detail_expansion(
        page,
        surface=surface,
        requested_fields=requested_fields,
        current_probe=current_probe,
        is_detail_surface=is_detail_surface,
        cached_html=lambda: cached_html or "",
        cached_analysis=lambda: cached_analysis,
        phase_timings_ms=phase_timings_ms,
        cached_probe=_cached_probe,
        readiness_probes=readiness_probes,
        expand_detail_content_if_needed=expand_detail_content_if_needed,
        append_readiness_probe=append_readiness_probe,
        elapsed_ms=elapsed_ms,
    )
    return (
        current_probe,
        readiness_probes,
        networkidle_timed_out,
        networkidle_skip_reason,
        readiness_diagnostics,
        expansion_diagnostics,
        cached_html or "",
        cached_analysis,
    )


async def _run_optimistic_readiness_wait(
    page: Any,
    *,
    current_probe: dict[str, object],
    timeout_seconds: float,
    settings: Any,
    phase_timings_ms: dict[str, int],
    cached_probe,
    readiness_probes: list[dict[str, object]],
    append_readiness_probe,
    elapsed_ms,
) -> dict[str, object]:
    wait_ms = min(
        int(timeout_seconds * 1000),
        int(settings.browser_navigation_optimistic_wait_ms),
    )
    if wait_ms <= 0 or current_probe["is_ready"]:
        phase_timings_ms["optimistic_wait"] = 0
        return current_probe
    started_at = time.perf_counter()
    try:
        await page.wait_for_function(
            "({visibleTextMin}) => String((document.body && (document.body.innerText || document.body.textContent)) || '').trim().length >= Number(visibleTextMin || 0)",
            arg={"visibleTextMin": int(settings.browser_readiness_visible_text_min)},
            timeout=wait_ms,
        )
    except PlaywrightTimeoutError:
        pass  # Readiness is re-probed after the bounded wait.
    phase_timings_ms["optimistic_wait"] = elapsed_ms(started_at)
    probe = await cached_probe(refresh_html=True)
    append_readiness_probe(readiness_probes, stage="after_optimistic_wait", probe=probe)
    return probe


async def _run_networkidle_settle(
    page: Any,
    *,
    current_probe: dict[str, object],
    timeout_seconds: float,
    readiness_policy: dict[str, object],
    is_listing_surface: bool,
    is_detail_surface: bool,
    settings: Any,
    phase_timings_ms: dict[str, int],
    cached_probe,
    readiness_probes: list[dict[str, object]],
    append_readiness_probe,
    elapsed_ms,
) -> tuple[dict[str, object], bool, str | None]:
    explicit = bool(readiness_policy.get("require_networkidle"))
    implicit = bool(
        not current_probe["is_ready"]
        and not explicit
        and (is_listing_surface or not current_probe.get("structured_data_present"))
    )
    if not current_probe["is_ready"] and (explicit or implicit):
        timeout_cap_ms = int(
            settings.browser_navigation_networkidle_timeout_ms
            if explicit
            else settings.browser_spa_implicit_networkidle_timeout_ms
        )
        started_at = time.perf_counter()
        timed_out = await _wait_for_networkidle(
            page, timeout_ms=min(int(timeout_seconds * 1000), timeout_cap_ms)
        )
        phase_timings_ms["networkidle_wait"] = elapsed_ms(started_at)
        probe = await cached_probe(refresh_html=True)
        append_readiness_probe(readiness_probes, stage="after_networkidle", probe=probe)
        return probe, timed_out, None
    phase_timings_ms["networkidle_wait"] = 0
    skip_reason = _networkidle_skip_reason(current_probe)
    await _settle_detail_payloads_if_needed(
        page,
        timeout_seconds=timeout_seconds,
        is_detail_surface=is_detail_surface,
        skip_reason=skip_reason,
        settings=settings,
        phase_timings_ms=phase_timings_ms,
        elapsed_ms=elapsed_ms,
    )
    return current_probe, False, skip_reason


async def _wait_for_networkidle(page: Any, *, timeout_ms: int) -> bool:
    try:
        await page.wait_for_load_state("networkidle", timeout=timeout_ms)
    except PlaywrightTimeoutError:
        return True
    return False


def _networkidle_skip_reason(current_probe: dict[str, object]) -> str:
    if current_probe["is_ready"]:
        return "fast_path_ready"
    if current_probe.get("structured_data_present"):
        return "structured_data_present"
    return "not_required"


async def _settle_detail_payloads_if_needed(
    page: Any,
    *,
    timeout_seconds: float,
    is_detail_surface: bool,
    skip_reason: str,
    settings: Any,
    phase_timings_ms: dict[str, int],
    elapsed_ms,
) -> None:
    settle_ms = max(0, int(settings.browser_detail_payload_settle_timeout_ms or 0))
    if not is_detail_surface or settle_ms <= 0 or skip_reason == "fast_path_ready":
        return
    started_at = time.perf_counter()
    await _wait_for_networkidle(
        page, timeout_ms=min(int(timeout_seconds * 1000), settle_ms)
    )
    phase_timings_ms["detail_payload_settle"] = elapsed_ms(started_at)


async def _run_surface_readiness_wait(
    page: Any,
    *,
    url: str,
    surface: str,
    current_probe: dict[str, object],
    timeout_seconds: float,
    readiness_override: dict[str, object] | None,
    is_listing_surface: bool,
    is_detail_surface: bool,
    settings: Any,
    phase_timings_ms: dict[str, int],
    cached_probe,
    readiness_probes: list[dict[str, object]],
    wait_for_listing_readiness,
    append_readiness_probe,
    elapsed_ms,
) -> tuple[dict[str, object], dict[str, object]]:
    if current_probe["is_ready"]:
        return _skipped_readiness(current_probe, phase_timings_ms)
    if readiness_override is not None:
        return await _wait_with_listing_override(
            page,
            url=url,
            override=readiness_override,
            stage="after_platform_readiness",
            phase_timings_ms=phase_timings_ms,
            cached_probe=cached_probe,
            readiness_probes=readiness_probes,
            wait_for_listing_readiness=wait_for_listing_readiness,
            append_readiness_probe=append_readiness_probe,
            elapsed_ms=elapsed_ms,
        )
    if is_listing_surface:
        selectors = _generic_card_selectors_for_surface(surface)
        if not selectors:
            phase_timings_ms["readiness_wait"] = 0
            return current_probe, {"status": "skipped", "reason": "no_card_selectors"}
        return await _wait_with_listing_override(
            page,
            url=url,
            override={
                "platform": "generic",
                "selectors": selectors,
                "max_wait_ms": int(settings.listing_readiness_max_wait_ms or 0),
            },
            stage="after_generic_readiness",
            phase_timings_ms=phase_timings_ms,
            cached_probe=cached_probe,
            readiness_probes=readiness_probes,
            wait_for_listing_readiness=wait_for_listing_readiness,
            append_readiness_probe=append_readiness_probe,
            elapsed_ms=elapsed_ms,
        )
    if is_detail_surface:
        return await _wait_for_generic_detail_readiness(
            page,
            current_probe=current_probe,
            timeout_seconds=timeout_seconds,
            settings=settings,
            phase_timings_ms=phase_timings_ms,
            cached_probe=cached_probe,
            readiness_probes=readiness_probes,
            append_readiness_probe=append_readiness_probe,
            elapsed_ms=elapsed_ms,
        )
    return _skipped_readiness(current_probe, phase_timings_ms)


def _skipped_readiness(
    current_probe: dict[str, object], phase_timings_ms: dict[str, int]
) -> tuple[dict[str, object], dict[str, object]]:
    phase_timings_ms["readiness_wait"] = 0
    reason = "fast_path_ready" if current_probe["is_ready"] else "no_platform_override"
    return current_probe, {"status": "skipped", "reason": reason}


async def _wait_with_listing_override(
    page: Any,
    *,
    url: str,
    override: dict[str, object],
    stage: str,
    phase_timings_ms: dict[str, int],
    cached_probe,
    readiness_probes: list[dict[str, object]],
    wait_for_listing_readiness,
    append_readiness_probe,
    elapsed_ms,
) -> tuple[dict[str, object], dict[str, object]]:
    started_at = time.perf_counter()
    diagnostics = await wait_for_listing_readiness(page, url, override=override)
    phase_timings_ms["readiness_wait"] = elapsed_ms(started_at)
    probe = await cached_probe(refresh_html=True)
    append_readiness_probe(readiness_probes, stage=stage, probe=probe)
    return probe, diagnostics


async def _wait_for_generic_detail_readiness(
    page: Any,
    *,
    current_probe: dict[str, object],
    timeout_seconds: float,
    settings: Any,
    phase_timings_ms: dict[str, int],
    cached_probe,
    readiness_probes: list[dict[str, object]],
    append_readiness_probe,
    elapsed_ms,
) -> tuple[dict[str, object], dict[str, object]]:
    started_at = time.perf_counter()
    max_wait_ms = max(0, int(settings.surface_readiness_max_wait_ms or 0))
    if max_wait_ms > 0:
        try:
            await page.wait_for_function(
                """() => Boolean(document.querySelector('h1')
                    || document.querySelector('[itemtype*="Product" i]')
                    || document.querySelector('[data-testid*="product" i]')
                    || document.querySelector('[class*="product" i]')
                    || document.querySelector('script[type="application/ld+json"]'))""",
                timeout=min(int(timeout_seconds * 1000), max_wait_ms),
            )
        except PlaywrightTimeoutError:
            pass  # The final readiness probe owns the outcome.
    phase_timings_ms["readiness_wait"] = elapsed_ms(started_at)
    probe = await cached_probe(refresh_html=True)
    append_readiness_probe(
        readiness_probes, stage="after_generic_detail_readiness", probe=probe
    )
    return probe, {
        "status": "ready" if probe["is_ready"] else "timeout",
        "reason": "generic_detail_readiness",
    }


async def serialize_browser_page_content_impl(
    page: Any,
    *,
    surface: str | None,
    traversal_mode: str | None,
    listing_recovery_mode: str | None,
    traversal_active: bool,
    timeout_seconds: float,
    max_pages: int,
    max_scrolls: int,
    max_records: int | None = None,
    prefetched_html: str | None = None,
    prefetched_analysis: HtmlAnalysis | None = None,
    phase_timings_ms: dict[str, int],
    execute_listing_traversal,
    recover_listing_page_content,
    elapsed_ms,
    on_event=None,
):
    should_flatten_shadow = "listing" not in str(surface or "").strip().lower()
    traversal_result = None
    traversal_html = ""
    rendered_html = ""
    listing_recovery_diagnostics = {
        "status": "skipped",
        "reason": "not_requested",
        "clicked_count": 0,
        "actions_taken": [],
    }
    recovery_started_at = time.perf_counter()
    normalized_listing_recovery_mode = _normalize_listing_recovery_mode(
        listing_recovery_mode
    )
    if normalized_listing_recovery_mode is not None:
        listing_recovery_diagnostics["requested_mode"] = (
            normalized_listing_recovery_mode
        )
    if traversal_active and normalized_listing_recovery_mode == "thin_listing":
        listing_recovery_diagnostics = await recover_listing_page_content(
            page,
            on_event=on_event,
        )
        listing_recovery_diagnostics["requested_mode"] = (
            normalized_listing_recovery_mode
        )
    elif normalized_listing_recovery_mode is not None:
        listing_recovery_diagnostics["reason"] = (
            "traversal_inactive" if not traversal_active else "unsupported_mode"
        )
    phase_timings_ms["listing_recovery"] = elapsed_ms(recovery_started_at)
    traversal_started_at = time.perf_counter()
    if traversal_active:
        traversal_result = await execute_listing_traversal(
            page,
            surface=str(surface or ""),
            traversal_mode=str(traversal_mode or ""),
            max_pages=max_pages,
            max_scrolls=max_scrolls,
            max_records=max_records,
            timeout_seconds=timeout_seconds,
            on_event=on_event,
        )
        traversal_html = traversal_result.compose_html()
        rendered_html = await get_page_html(
            page,
            flatten_shadow=should_flatten_shadow,
        )
        html = _select_primary_browser_html(
            surface=surface,
            traversal_result=traversal_result,
            traversal_html=traversal_html,
            rendered_html=rendered_html,
            listing_min_items=int(crawler_runtime_settings.listing_min_items),
        )
    else:
        html = ""
    phase_timings_ms["traversal"] = elapsed_ms(traversal_started_at)
    serialization_started_at = time.perf_counter()
    if traversal_result is None:
        html = str(prefetched_html or "")
        if not html.strip() and prefetched_analysis is not None:
            html = prefetched_analysis.html
        if not html.strip():
            html = await get_page_html(
                page,
                flatten_shadow=should_flatten_shadow,
            )
        rendered_html = html
    phase_timings_ms["content_serialization"] = elapsed_ms(serialization_started_at)
    return (
        html,
        traversal_result,
        rendered_html,
        listing_recovery_diagnostics,
    )


def resolve_browser_fetch_policy(
    *,
    url: str,
    surface: str,
    traversal_mode: str | None,
    should_run_traversal,
) -> tuple[bool, dict[str, object], dict[str, object] | None]:
    traversal_active = should_run_traversal(surface, traversal_mode)
    readiness_policy = resolve_browser_readiness_policy(
        url,
        surface=surface,
        traversal_active=traversal_active,
    )
    readiness_override = readiness_policy.get("listing_override")
    return traversal_active, readiness_policy, readiness_override


def append_readiness_probe(
    readiness_probes: list[dict[str, object]],
    *,
    stage: str,
    probe: dict[str, object],
) -> None:
    readiness_probes.append({"stage": stage, **probe})

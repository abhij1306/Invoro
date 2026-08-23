from __future__ import annotations

import asyncio
from functools import partial
import logging
import time
from typing import Any
import httpx

from app.services.acquisition.browser_runtime import (
    SharedBrowserRuntime,
    build_failed_browser_diagnostics,
    browser_fetch,
    browser_runtime_snapshot,
    expand_all_interactive_elements,
    get_browser_runtime,
    real_chrome_browser_available,
    shutdown_browser_runtime,
    temporary_browser_page,
)
from app.services.acquisition.browser_proxy_config import display_proxy, proxy_scheme
from app.services.acquisition.host_protection_memory import (
    HostProtectionPolicy,
    load_host_protection_policy,
    note_host_hard_block,
    note_host_usable_fetch,
)
from app.services.acquisition.cookie_store import (
    clear_cookie_store_cache,
    export_cookie_header_for_domain,
)
from app.services.acquisition.http_client import (
    close_shared_http_client as close_adapter_shared_http_client,
)
from app.services.acquisition.pacing import (
    apply_protected_host_backoff,
    reset_pacing_state,
    wait_for_host_slot,
)
from app.services.acquisition.runtime import (
    PageFetchResult,
    close_shared_http_client,
    curl_fetch,
    get_shared_http_client,
    http_fetch,
    is_blocked_html,
    is_blocked_html_async,
    is_non_retryable_http_status,
    should_escalate_to_browser,
)
from app.services.acquisition.traversal import should_run_traversal
from app.services.config.runtime_settings import (
    crawler_runtime_settings,
)
from app.services.platform_policy import resolve_platform_runtime_policy
from app.services.fetch.browser_policy import (
    acquisition_strategy_message as _acquisition_strategy_message,
    browser_engine_attempts,
    browser_escalation_allowed as _browser_escalation_allowed,
    browser_escalation_proxies as _browser_escalation_proxies,
    browser_first_decision as _browser_first_decision,
    attach_browser_attempt_diagnostics as _attach_browser_attempt_diagnostics,
    attach_exception_browser_diagnostics as _attach_exception_browser_diagnostics,
    hard_browser_requirement as _hard_browser_requirement,
    normalize_fetch_mode as _normalize_fetch_mode,
    normalize_proxy_profile as _normalize_proxy_profile,
    handoff_cookie_engines,
    resolve_http_timeout,
    resolve_browser_reason as _resolve_browser_reason,
    resolve_proxy_attempts as _resolve_proxy_attempts,
    vendor_confirmed_block as _vendor_confirmed_block,
)
from app.services.fetch.types import FetchPageCall, FetchRuntimeContext
from app.services.fetch.browser_attempts import execute_browser_attempts
from app.services.fetch.host_memory import record_fetch_result
from app.services.shared.url_utils import ensure_scheme

logger = logging.getLogger(__name__)


async def _emit_fetch_event(on_event: Any | None, level: str, message: str) -> None:
    if not callable(on_event):
        return
    try:
        await on_event(level, message)
    except Exception:
        logger.debug("Fetch event callback failed", exc_info=True)


async def _get_shared_http_client(*, proxy: str | None = None):
    return await get_shared_http_client(proxy=proxy)


async def _http_fetch(
    url: str,
    timeout_seconds: float,
    *,
    proxy: str | None = None,
) -> PageFetchResult:
    return await http_fetch(
        url,
        timeout_seconds,
        proxy=proxy,
        get_client=_get_shared_http_client,
        blocked_html_checker=is_blocked_html_async,
    )


async def _should_escalate_to_browser_async(
    result: PageFetchResult,
    *,
    surface: str | None = None,
    runtime_policy: dict[str, object] | None = None,
) -> bool:
    return await asyncio.to_thread(
        should_escalate_to_browser,
        result,
        surface=surface,
        runtime_policy=runtime_policy,
    )


_curl_fetch = curl_fetch
_browser_fetch = partial(
    browser_fetch,
    runtime_provider=get_browser_runtime,
    proxied_page_factory=temporary_browser_page,
    blocked_html_checker=is_blocked_html_async,
)


async def reset_fetch_runtime_state() -> None:
    await shutdown_browser_runtime()
    await clear_cookie_store_cache()
    await reset_pacing_state()
    await close_shared_http_client()
    await close_adapter_shared_http_client()


def _build_fetch_runtime_context(call: FetchPageCall) -> FetchRuntimeContext:
    resolved_timeout_source = call.timeout_seconds
    if resolved_timeout_source is None:
        resolved_timeout_source = (
            crawler_runtime_settings.acquisition_attempt_timeout_seconds
        )
    if resolved_timeout_source is None:
        raise ValueError(
            "fetch_page requires timeout_seconds or crawler_runtime_settings.acquisition_attempt_timeout_seconds"
        )
    return FetchRuntimeContext(
        url=call.url,
        resolved_timeout=float(resolved_timeout_source),
        deadline_monotonic=time.perf_counter() + float(resolved_timeout_source),
        run_id=call.run_id,
        surface=call.surface,
        traversal_mode=call.traversal_mode,
        max_pages=call.max_pages,
        max_scrolls=call.max_scrolls,
        max_records=call.max_records,
        on_event=call.on_event,
        browser_reason=call.browser_reason,
        requested_fields=list(call.requested_fields or []),
        listing_recovery_mode=str(call.listing_recovery_mode or "").strip() or None,
        capture_screenshot=bool(call.capture_screenshot),
        host_memory_ttl_seconds=crawler_runtime_settings.coerce_host_memory_ttl_seconds(
            call.host_memory_ttl_seconds
        ),
        prefer_browser=bool(call.prefer_browser),
        prefer_curl_handoff=bool(call.prefer_curl_handoff),
        handoff_cookie_engine=str(call.handoff_cookie_engine or "").strip().lower()
        or None,
        proxies=_resolve_proxy_attempts(
            call.proxy_list,
            run_id=call.run_id,
            proxy_profile=call.proxy_profile,
        ),
        proxy_profile=_normalize_proxy_profile(call.proxy_profile),
        locality_profile=dict(call.locality_profile or {})
        if isinstance(call.locality_profile, dict)
        else {},
        traversal_required=should_run_traversal(call.surface, call.traversal_mode),
        fetch_mode=_normalize_fetch_mode(call.fetch_mode),
        runtime_policy=resolve_platform_runtime_policy(call.url, surface=call.surface),
        forced_browser_engine=str(call.forced_browser_engine or "").strip().lower()
        or None,
    )


async def fetch_page(
    url: str,
    *,
    run_id: int | None = None,
    timeout_seconds: float | None = None,
    proxy_list: list[str] | None = None,
    proxy_profile: dict[str, object] | None = None,
    locality_profile: dict[str, object] | None = None,
    fetch_mode: str = "auto",
    prefer_browser: bool = False,
    browser_reason: str | None = None,
    surface: str | None = None,
    traversal_mode: str | None = None,
    requested_fields: list[str] | None = None,
    listing_recovery_mode: str | None = None,
    capture_screenshot: bool = False,
    host_memory_ttl_seconds: int | None = None,
    prefer_curl_handoff: bool = False,
    handoff_cookie_engine: str | None = None,
    forced_browser_engine: str | None = None,
    max_pages: int = 1,
    max_scrolls: int = 1,
    max_records: int | None = None,
    on_event: Any | None = None,
) -> PageFetchResult:
    call = FetchPageCall(
        url=ensure_scheme(url),
        run_id=run_id,
        timeout_seconds=timeout_seconds,
        proxy_list=proxy_list,
        proxy_profile=proxy_profile,
        locality_profile=locality_profile,
        fetch_mode=fetch_mode,
        prefer_browser=prefer_browser,
        browser_reason=browser_reason,
        surface=surface,
        traversal_mode=traversal_mode,
        requested_fields=requested_fields,
        listing_recovery_mode=listing_recovery_mode,
        capture_screenshot=capture_screenshot,
        host_memory_ttl_seconds=host_memory_ttl_seconds,
        prefer_curl_handoff=prefer_curl_handoff,
        handoff_cookie_engine=handoff_cookie_engine,
        forced_browser_engine=forced_browser_engine,
        max_pages=max_pages,
        max_scrolls=max_scrolls,
        max_records=max_records,
        on_event=on_event,
    )
    context = _build_fetch_runtime_context(call)
    context.host_policy = await load_host_protection_policy(
        call.url,
        ttl_seconds=context.host_memory_ttl_seconds,
    )
    host_preference_enabled = bool(context.host_policy.prefer_browser)
    browser_first = _browser_first_decision(
        context=context,
        prefer_browser=call.prefer_browser,
        host_preference_enabled=host_preference_enabled,
    )
    await _emit_fetch_event(
        context.on_event,
        "info",
        _acquisition_strategy_message(
            context=context,
            prefer_browser=call.prefer_browser,
            host_preference_enabled=host_preference_enabled,
            browser_first=browser_first,
        ),
    )
    browser_first_result = await _run_browser_first_if_selected(
        context,
        call=call,
        browser_first=browser_first,
        host_preference_enabled=host_preference_enabled,
    )
    if browser_first_result is not None:
        return browser_first_result

    if context.prefer_curl_handoff:
        handoff_result = await try_browser_http_handoff(context)
        if handoff_result is not None:
            await _update_host_result_memory(
                context,
                result=handoff_result,
            )
            return handoff_result

    http_result, vendor_block_confirmed = await _run_http_fetch_chain(context)
    if http_result is not None:
        return http_result
    if vendor_block_confirmed and context.last_error is not None:
        raise context.last_error
    if context.last_error is not None:
        cause = (
            context.last_error if isinstance(context.last_error, Exception) else None
        )
        logger.info(
            "HTTP fetchers exhausted for %s (%s); attempting browser fallback",
            context.url,
            type(context.last_error).__name__,
        )
        try:
            return await run_browser_attempts(
                context,
                reason=call.browser_reason or "http-escalation",
                requested_fields=context.requested_fields,
                listing_recovery_mode=context.listing_recovery_mode,
                capture_screenshot=context.capture_screenshot,
                proxies=context.proxies,
            )
        except Exception as exc:
            _attach_exception_browser_diagnostics(
                exc,
                context.last_browser_attempt_diagnostics,
            )
            raise exc from cause
    raise RuntimeError(f"Failed to fetch {call.url}")


async def _run_browser_first_if_selected(
    context: FetchRuntimeContext,
    *,
    call: FetchPageCall,
    browser_first: bool,
    host_preference_enabled: bool,
) -> PageFetchResult | None:
    if not browser_first:
        return None
    handoff_result = await try_browser_http_handoff(context)
    if handoff_result is not None:
        await _update_host_result_memory(context, result=handoff_result)
        return handoff_result
    reason = _resolve_browser_reason(
        browser_reason=call.browser_reason,
        requires_browser=bool(context.runtime_policy.get("requires_browser")),
        traversal_required=context.traversal_required,
        host_preference_enabled=host_preference_enabled,
    )
    try:
        result = await run_browser_attempts(
            context,
            reason=reason,
            requested_fields=context.requested_fields,
            listing_recovery_mode=context.listing_recovery_mode,
            capture_screenshot=context.capture_screenshot,
            proxies=context.proxies,
        )
    except Exception as exc:
        await _handle_browser_failure_with_http_fallback(
            context, reason=reason, exc=exc
        )
        return None
    await _update_host_result_memory(context, result=result)
    return result


async def _handle_browser_failure_with_http_fallback(
    context: FetchRuntimeContext,
    *,
    reason: str,
    exc: Exception,
    retain_http_result: bool = False,
) -> None:
    context.last_error = exc
    context.browser_first_failed = True
    if not context.last_browser_attempt_diagnostics:
        context.last_browser_attempt_diagnostics = build_failed_browser_diagnostics(
            browser_reason=reason, exc=exc
        )
    _attach_exception_browser_diagnostics(exc, context.last_browser_attempt_diagnostics)
    if context.fetch_mode == "browser_only" or context.traversal_required:
        raise exc
    fallback_text = (
        "keeping prior HTTP observation"
        if retain_http_result
        else "falling back to HTTP"
    )
    await _emit_fetch_event(
        context.on_event,
        "warning",
        f"Browser acquisition failed; {fallback_text} ({type(exc).__name__})",
    )


async def _run_browser_attempts(
    context: FetchRuntimeContext,
    *,
    reason: str,
    requested_fields: list[str] | None = None,
    listing_recovery_mode: str | None = None,
    capture_screenshot: bool = False,
    proxies: list[str | None] | None = None,
    host_policy: HostProtectionPolicy | None = None,
) -> PageFetchResult:
    return await execute_browser_attempts(
        context,
        reason=reason,
        browser_fetcher=_browser_fetch,
        emit_event=_emit_fetch_event,
        engine_selector=browser_engine_attempts,
        real_chrome_available=real_chrome_browser_available,
        wait_for_slot=wait_for_host_slot,
        record_result=_update_host_result_memory,
        record_hard_block=note_host_hard_block,
        policy_loader=load_host_protection_policy,
        requested_fields=requested_fields,
        listing_recovery_mode=listing_recovery_mode,
        capture_screenshot=capture_screenshot,
        proxies=proxies,
        host_policy=host_policy,
    )


run_browser_attempts = _run_browser_attempts


async def _run_http_fetch_chain(
    context: FetchRuntimeContext,
) -> tuple[PageFetchResult | None, bool]:
    vendor_block_confirmed = False
    primary_fetcher = _select_http_fetcher(context)
    result, vendor_block_confirmed = await _run_http_fetch_chain_with_fetcher(
        context,
        fetcher=primary_fetcher,
    )
    if result is not None or vendor_block_confirmed:
        return result, vendor_block_confirmed
    if (
        primary_fetcher is _curl_fetch
        and not crawler_runtime_settings.force_httpx
        and context.last_error is not None
    ):
        await _emit_fetch_event(
            context.on_event,
            "info",
            (
                f"HTTP transport fallback via _http_fetch after curl_fetch failed: {type(context.last_error).__name__}"
            ),
        )
        logger.info(
            "curl_cffi transport failed for %s (%s); retrying via httpx",
            context.url,
            type(context.last_error).__name__,
        )
        return await _run_http_fetch_chain_with_fetcher(
            context,
            fetcher=_http_fetch,
        )
    return None, vendor_block_confirmed


async def _run_http_fetch_chain_with_fetcher(
    context: FetchRuntimeContext,
    *,
    fetcher,
) -> tuple[PageFetchResult | None, bool]:
    vendor_block_confirmed = False
    for proxy in context.proxies:
        result, proxy_vendor_block_confirmed = await _run_http_fetcher_attempts(
            context,
            fetcher=fetcher,
            proxy=proxy,
        )
        vendor_block_confirmed = vendor_block_confirmed or proxy_vendor_block_confirmed
        if result is not None:
            return result, vendor_block_confirmed
    return None, vendor_block_confirmed


async def _try_browser_http_handoff(
    context: FetchRuntimeContext,
) -> PageFetchResult | None:
    host_policy = context.host_policy
    if not _browser_http_handoff_eligible(context, host_policy=host_policy):
        return None
    engines = handoff_cookie_engines(
        preferred_engine=context.handoff_cookie_engine,
    )
    for proxy in context.proxies:
        if proxy is not None:
            continue
        for engine in engines:
            try:
                cookie_header = await export_cookie_header_for_domain(
                    context.url,
                    browser_engine=engine,
                )
            except Exception:
                logger.warning(
                    "Cookie export failed for handoff engine=%s url=%s",
                    engine,
                    context.url,
                    exc_info=True,
                )
                cookie_header = None
            if not cookie_header:
                continue
            handoff_timeout = min(
                float(crawler_runtime_settings.browser_http_handoff_timeout_seconds),
                resolve_http_timeout(context),
            )
            if handoff_timeout <= 0:
                return None
            try:
                result = await _curl_fetch(
                    context.url,
                    handoff_timeout,
                    proxy=proxy,
                    cookie_header=cookie_header,
                )
            except (httpx.HTTPError, OSError):
                logger.debug(
                    "Handoff curl_fetch failed for %s; skipping handoff",
                    context.url,
                    exc_info=True,
                )
                return None
            result.browser_diagnostics = {
                **dict(result.browser_diagnostics or {}),
                "browser_http_handoff": True,
                "handoff_cookie_engine": engine,
                "proxy_url_redacted": display_proxy(proxy),
                "proxy_scheme": proxy_scheme(proxy),
            }
            if not bool(result.blocked) and not await _should_escalate_to_browser_async(
                result,
                surface=context.surface,
                runtime_policy=resolve_platform_runtime_policy(
                    result.final_url or result.url,
                    result.html,
                    surface=context.surface,
                ),
            ):
                return result
            await apply_protected_host_backoff(
                result.final_url or result.url or context.url,
                ttl_seconds=context.host_memory_ttl_seconds,
            )
            context.last_browser_attempt_diagnostics = dict(result.browser_diagnostics)
            return None
    return None


def _browser_http_handoff_eligible(
    context: FetchRuntimeContext, *, host_policy: HostProtectionPolicy | None
) -> bool:
    if host_policy is None or not bool(
        crawler_runtime_settings.browser_http_handoff_enabled
    ):
        return False
    if (
        _hard_browser_requirement(context=context)
        or context.fetch_mode == "browser_only"
    ):
        return False
    if context.prefer_browser and not context.prefer_curl_handoff:
        return False
    return bool(host_policy.prefer_browser or context.prefer_curl_handoff)


try_browser_http_handoff = _try_browser_http_handoff


def _select_http_fetcher(context: FetchRuntimeContext):
    del context
    if crawler_runtime_settings.force_httpx:
        return _http_fetch
    return _curl_fetch


async def _run_http_fetcher_attempts(
    context: FetchRuntimeContext,
    *,
    fetcher,
    proxy: str | None,
) -> tuple[PageFetchResult | None, bool]:
    result = await _attempt_http_fetch(
        context,
        fetcher=fetcher,
        proxy=proxy,
    )
    if not isinstance(result, PageFetchResult):
        return None, False
    handled_result, vendor_block_confirmed = await _handle_http_result(
        context,
        result=result,
        proxy=proxy,
    )
    if isinstance(handled_result, PageFetchResult):
        return handled_result, vendor_block_confirmed
    return None, False


_http_attempt_failed = object()


async def _attempt_http_fetch(
    context: FetchRuntimeContext,
    *,
    fetcher,
    proxy: str | None,
) -> PageFetchResult | object:
    try:
        await wait_for_host_slot(
            context.url,
            ttl_seconds=context.host_memory_ttl_seconds,
        )
        logged_timeout = resolve_http_timeout(context)
        if logged_timeout <= 0:
            return _http_attempt_failed
        await _emit_fetch_event(
            context.on_event,
            "info",
            (
                f"HTTP fetch via {fetcher.__name__} (timeout={logged_timeout:.1f}s, proxy={display_proxy(proxy)})"
            ),
        )
        # Event callbacks are awaited and may consume the remaining deadline.
        http_timeout = resolve_http_timeout(context)
        if http_timeout <= 0:
            return _http_attempt_failed
        if proxy is not None:
            return await fetcher(context.url, http_timeout, proxy=proxy)
        return await fetcher(context.url, http_timeout)
    except (httpx.HTTPError, OSError) as exc:
        context.last_error = exc
        logger.debug(
            "Fetch failure for %s via %s (%s)",
            context.url,
            fetcher.__name__,
            proxy or "direct",
            exc_info=True,
        )
        await _emit_fetch_event(
            context.on_event,
            "warning",
            f"HTTP fetch failed via {fetcher.__name__}: {type(exc).__name__}",
        )
        return _http_attempt_failed
    except RuntimeError as exc:
        context.last_error = exc
        logger.debug(
            "Fetch failed for %s via %s (%s)",
            context.url,
            fetcher.__name__,
            proxy or "direct",
            exc_info=True,
        )
        await _emit_fetch_event(
            context.on_event,
            "warning",
            f"HTTP fetch failed via {fetcher.__name__}: {type(exc).__name__}",
        )
        return _http_attempt_failed


async def _handle_http_result(
    context: FetchRuntimeContext,
    *,
    result: PageFetchResult,
    proxy: str | None,
) -> tuple[PageFetchResult | object | None, bool]:
    result_runtime_policy = resolve_platform_runtime_policy(
        result.final_url or result.url,
        result.html,
        surface=context.surface,
    )
    vendor, should_browser_escalate = await _record_http_block_result(
        context, result=result, proxy=proxy, runtime_policy=result_runtime_policy
    )
    browser_escalation_allowed = (
        should_browser_escalate
        and _browser_escalation_allowed(
            context=context,
            runtime_policy=result_runtime_policy,
        )
    )
    if browser_escalation_allowed:
        if context.browser_first_failed and not (vendor or bool(result.blocked)):
            _attach_browser_attempt_diagnostics(
                result,
                diagnostics=context.last_browser_attempt_diagnostics,
            )
            return result, bool(vendor)
        browser_result = await _escalate_http_result_to_browser(
            context, result=result, proxy=proxy, vendor=vendor
        )
        return browser_result, bool(vendor)
    if is_non_retryable_http_status(result.status_code):
        logger.info(
            "Returning non-retryable HTTP status %s for %s without browser fallback",
            result.status_code,
            context.url,
        )
        await _update_host_result_memory(
            context,
            result=result,
        )
        return result, bool(vendor)
    _attach_browser_attempt_diagnostics(
        result,
        diagnostics=context.last_browser_attempt_diagnostics,
    )
    await _update_host_result_memory(
        context,
        result=result,
    )
    return result, bool(vendor)


async def _record_http_block_result(
    context: FetchRuntimeContext,
    *,
    result: PageFetchResult,
    proxy: str | None,
    runtime_policy: dict[str, object],
) -> tuple[str | None, bool]:
    vendor = _vendor_confirmed_block(result)
    blocked = vendor or bool(result.blocked)
    if blocked:
        await apply_protected_host_backoff(
            result.final_url or result.url or context.url,
            ttl_seconds=context.host_memory_ttl_seconds,
        )
    should_escalate = bool(vendor) or await _should_escalate_to_browser_async(
        result, surface=context.surface, runtime_policy=runtime_policy
    )
    if not should_escalate or not blocked:
        return vendor, should_escalate
    await note_host_hard_block(
        result.final_url or result.url or context.url,
        method=result.method,
        vendor=vendor,
        status_code=result.status_code,
        proxy_used=proxy is not None,
        ttl_seconds=context.host_memory_ttl_seconds,
    )
    context.host_policy = await load_host_protection_policy(
        result.final_url or result.url or context.url,
        ttl_seconds=context.host_memory_ttl_seconds,
    )
    return vendor, should_escalate


async def _escalate_http_result_to_browser(
    context: FetchRuntimeContext,
    *,
    result: PageFetchResult,
    proxy: str | None,
    vendor: str | None,
) -> PageFetchResult:
    reason = context.browser_reason or (
        f"vendor-block:{vendor}" if vendor else "http-escalation"
    )
    await _emit_fetch_event(
        context.on_event,
        "info",
        "Escalating to browser after HTTP result "
        f"(status={result.status_code}, method={result.method}, reason={reason})",
    )
    try:
        browser_result = await run_browser_attempts(
            context,
            reason=reason,
            requested_fields=context.requested_fields,
            listing_recovery_mode=context.listing_recovery_mode,
            capture_screenshot=context.capture_screenshot,
            proxies=_browser_escalation_proxies(
                context=context,
                current_proxy=proxy,
                vendor_blocked=bool(vendor),
            ),
        )
    except Exception as exc:
        await _handle_browser_failure_with_http_fallback(
            context,
            reason=reason,
            exc=exc,
            retain_http_result=True,
        )
        _attach_browser_attempt_diagnostics(
            result,
            diagnostics=context.last_browser_attempt_diagnostics,
        )
        if vendor or bool(result.blocked):
            raise
        await _update_host_result_memory(context, result=result)
        return result
    await _update_host_result_memory(context, result=browser_result)
    return browser_result


async def _update_host_result_memory(
    context: FetchRuntimeContext,
    *,
    result: PageFetchResult,
) -> None:
    await record_fetch_result(
        context,
        result=result,
        note_usable=note_host_usable_fetch,
        note_block=note_host_hard_block,
        apply_backoff=apply_protected_host_backoff,
    )


__all__ = [
    "FetchPageCall",
    "FetchRuntimeContext",
    "PageFetchResult",
    "SharedBrowserRuntime",
    "browser_runtime_snapshot",
    "close_shared_http_client",
    "expand_all_interactive_elements",
    "fetch_page",
    "is_blocked_html",
    "reset_fetch_runtime_state",
    "run_browser_attempts",
    "shutdown_browser_runtime",
    "try_browser_http_handoff",
]

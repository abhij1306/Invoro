from app.services.acquisition.host_protection_memory import (
    note_host_hard_block,
    note_host_usable_fetch,
)
from app.services.acquisition.pacing import apply_protected_host_backoff
from app.services.acquisition.runtime import PageFetchResult
from app.services.fetch.browser_policy import vendor_confirmed_block
from app.services.fetch.types import FetchRuntimeContext


async def record_fetch_result(
    context: FetchRuntimeContext,
    *,
    result: PageFetchResult,
    note_usable=note_host_usable_fetch,
    note_block=note_host_hard_block,
    apply_backoff=apply_protected_host_backoff,
) -> None:
    target_url = result.final_url or result.url or context.url
    diagnostics = dict(result.browser_diagnostics or {})
    browser_engine = str(diagnostics.get("browser_engine") or "").strip().lower()
    method_label = str(result.method or "").strip().lower()
    if method_label == "browser" and browser_engine:
        method_label = f"browser:{browser_engine}"
    proxy_used = bool(diagnostics.get("proxy_scheme"))
    if not bool(result.blocked):
        await note_usable(
            target_url,
            method=method_label or result.method,
            proxy_used=proxy_used,
            ttl_seconds=context.host_memory_ttl_seconds,
        )
        return
    if str(diagnostics.get("browser_outcome") or "").strip().lower() == "location_required":
        return
    ttl_seconds = context.host_memory_ttl_seconds
    await apply_backoff(target_url, ttl_seconds=ttl_seconds)
    await note_block(
        target_url,
        method=method_label or result.method,
        vendor=vendor_confirmed_block(result),
        status_code=result.status_code,
        proxy_used=proxy_used,
        ttl_seconds=ttl_seconds,
    )

from __future__ import annotations

import asyncio
import time
from collections.abc import Callable
from typing import Any

from app.services.acquisition.runtime import PageFetchResult
from app.services.fetch import fetch_context
from app.services.fetch.types import FetchRuntimeContext


def default_fetch_context(
    url: str = "https://example.com/products/widget",
    surface: str = "ecommerce_detail",
    **overrides: Any,
) -> FetchRuntimeContext:
    return FetchRuntimeContext(
        url=url,
        resolved_timeout=5.0,
        deadline_monotonic=time.perf_counter() + 5.0,
        run_id=None,
        surface=surface,
        traversal_mode=None,
        max_pages=1,
        max_scrolls=1,
        max_records=None,
        on_event=None,
        browser_reason=None,
        requested_fields=[],
        listing_recovery_mode=None,
        proxies=[None],
        proxy_profile={},
        traversal_required=False,
        fetch_mode="browser_only",
        runtime_policy={},
        host_memory_ttl_seconds=fetch_context.crawler_runtime_settings.coerce_host_memory_ttl_seconds(
            None
        ),
        **overrides,
    )


def page_fetch_result(
    html: str,
    *,
    url: str = "https://example.com/products/widget",
    final_url: str | None = None,
    method: str = "browser",
    status_code: int = 200,
    **overrides: Any,
) -> PageFetchResult:
    return PageFetchResult(
        url=url,
        final_url=final_url or url,
        html=html,
        status_code=status_code,
        method=method,
        **overrides,
    )


def as_async(fn: Callable[..., Any]) -> Callable[..., Any]:
    async def _wrapped(*args: Any, **kwargs: Any) -> Any:
        await asyncio.sleep(0)
        return fn(*args, **kwargs)

    return _wrapped

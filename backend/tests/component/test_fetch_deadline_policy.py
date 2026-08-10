from __future__ import annotations

import time

import pytest

from app.services.acquisition.runtime import PageFetchResult
from app.services.acquisition.host_protection_memory import HostProtectionPolicy
from app.services.fetch import browser_policy, fetch_context
from tests.fixtures.fetch_runtime import default_fetch_context, page_fetch_result


@pytest.mark.asyncio
@pytest.mark.component
async def test_http_fetch_recalculates_timeout_after_host_slot_wait(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = default_fetch_context()
    seen_timeouts: list[float] = []

    async def wait_for_slot(*_args, **_kwargs) -> None:
        context.deadline_monotonic = time.perf_counter() + 0.25

    async def fetcher(request_url: str, timeout: float) -> PageFetchResult:
        seen_timeouts.append(timeout)
        return page_fetch_result("<html><body>Widget</body></html>", url=request_url)

    monkeypatch.setattr(fetch_context, "wait_for_host_slot", wait_for_slot)
    await fetch_context._attempt_http_fetch(context, fetcher=fetcher, proxy=None)

    assert len(seen_timeouts) == 1
    assert 0 < seen_timeouts[0] <= 0.25


@pytest.mark.component
def test_rate_limited_http_escalation_reserves_budget_for_real_chrome(
    patch_settings,
) -> None:
    patch_settings(browser_vendor_block_probe_timeout_seconds=12.0)
    context = default_fetch_context()
    context.deadline_monotonic = time.perf_counter() + 90.0

    timeout = browser_policy.browser_attempt_timeout_seconds(
        context,
        reason="http-escalation",
        browser_engine="patchright",
        engine_attempts=["patchright", "real_chrome"],
        host_policy=HostProtectionPolicy(
            host="example.com",
            prefer_browser=True,
            request_blocked=True,
            last_block_method="curl_cffi",
        ),
    )

    assert timeout == pytest.approx(12.0, abs=0.05)

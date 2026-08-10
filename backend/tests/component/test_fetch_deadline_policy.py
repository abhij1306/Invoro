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


@pytest.mark.asyncio
@pytest.mark.component
async def test_http_fetch_aborts_when_host_slot_exhausts_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = default_fetch_context()
    fetch_called = False

    async def wait_for_slot(*_args, **_kwargs) -> None:
        context.deadline_monotonic = time.perf_counter() - 1.0

    async def fetcher(_request_url: str, _timeout: float) -> PageFetchResult:
        nonlocal fetch_called
        fetch_called = True
        return page_fetch_result("<html></html>")

    monkeypatch.setattr(fetch_context, "wait_for_host_slot", wait_for_slot)

    result = await fetch_context._attempt_http_fetch(
        context,
        fetcher=fetcher,
        proxy=None,
    )

    assert result is fetch_context._http_attempt_failed
    assert fetch_called is False


@pytest.mark.asyncio
@pytest.mark.component
async def test_http_fetch_rechecks_deadline_after_event_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = default_fetch_context()
    fetch_called = False

    async def wait_for_slot(*_args, **_kwargs) -> None:
        return None

    async def expire_deadline(*_args, **_kwargs) -> None:
        context.deadline_monotonic = time.perf_counter() - 1.0

    async def fetcher(_request_url: str, _timeout: float) -> PageFetchResult:
        nonlocal fetch_called
        fetch_called = True
        return page_fetch_result("<html></html>")

    context.on_event = expire_deadline
    monkeypatch.setattr(fetch_context, "wait_for_host_slot", wait_for_slot)

    result = await fetch_context._attempt_http_fetch(
        context,
        fetcher=fetcher,
        proxy=None,
    )

    assert result is fetch_context._http_attempt_failed
    assert fetch_called is False


@pytest.mark.asyncio
@pytest.mark.component
async def test_http_handoff_aborts_when_cookie_export_exhausts_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    context = default_fetch_context()
    context.fetch_mode = "auto"
    context.prefer_curl_handoff = True
    context.host_policy = HostProtectionPolicy(
        host="example.com",
        prefer_browser=True,
    )
    curl_called = False

    async def export_cookie(*_args, **_kwargs) -> str:
        context.deadline_monotonic = time.perf_counter() - 1.0
        return "session=ready"

    async def curl_fetch(*_args, **_kwargs) -> PageFetchResult:
        nonlocal curl_called
        curl_called = True
        return page_fetch_result("<html></html>")

    monkeypatch.setattr(
        fetch_context, "handoff_cookie_engines", lambda **_kwargs: ("patchright",)
    )
    monkeypatch.setattr(fetch_context, "export_cookie_header_for_domain", export_cookie)
    monkeypatch.setattr(fetch_context, "_curl_fetch", curl_fetch)

    result = await fetch_context._try_browser_http_handoff(context)

    assert result is None
    assert curl_called is False


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


@pytest.mark.component
def test_invalid_nonpositive_http_timeout_uses_remaining_budget(patch_settings) -> None:
    patch_settings(http_timeout_seconds=0)
    context = default_fetch_context()
    context.deadline_monotonic = time.perf_counter() + 5.0

    timeout = browser_policy.resolve_http_timeout(context)

    assert timeout == pytest.approx(5.0, abs=0.05)

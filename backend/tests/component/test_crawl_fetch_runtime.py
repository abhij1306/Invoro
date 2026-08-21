from __future__ import annotations

import asyncio

import sys

import time

from types import SimpleNamespace

from unittest.mock import AsyncMock

import httpx

import pytest

from patchright.async_api import Error as PlaywrightError

from app.services.fetch import fetch_context as crawl_fetch_runtime

from app.services.fetch import browser_policy

from app.services.fetch.types import FetchRuntimeContext

from app.services.acquisition import (
    browser_capture,
    runtime as acquisition_runtime,
)

from app.services.acquisition.host_protection_memory import HostProtectionPolicy

from app.services.acquisition.browser_runtime import (
    classify_network_endpoint,
    read_network_payload_body,
    should_capture_network_payload,
)

from app.services.acquisition.runtime import (
    PageFetchResult,
    http_fetch,
    should_escalate_to_browser_async,
)

from tests.fixtures.fetch_runtime import (
    as_async as _as_async,
    default_fetch_context as _default_fetch_context,
    page_fetch_result as _page_fetch_result,
)

from tests.fixtures.http_mocks import FakeBodyResponse


@pytest.fixture(autouse=True)
async def _reset_fetch_runtime_state_between_tests(
    monkeypatch: pytest.MonkeyPatch,
):
    await crawl_fetch_runtime.reset_fetch_runtime_state()

    @_as_async
    def _default_load_policy(url: str, *, session=None, ttl_seconds=None):
        del url, session, ttl_seconds
        return HostProtectionPolicy(host="")

    monkeypatch.setattr(
        crawl_fetch_runtime,
        "load_host_protection_policy",
        _default_load_policy,
    )
    try:
        yield
    finally:
        await crawl_fetch_runtime.reset_fetch_runtime_state()


__all__ = tuple(name for name in globals() if not name.startswith("__"))

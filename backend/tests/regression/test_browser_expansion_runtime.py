from __future__ import annotations

import asyncio

import time

from contextlib import asynccontextmanager

from dataclasses import dataclass

from pathlib import Path

from types import SimpleNamespace

from typing import Any

import httpx

import pytest

from app.services.dom.html_parser import BeautifulSoup

from patchright.async_api import Error as PlaywrightError

from patchright.async_api import TimeoutError as PlaywrightTimeoutError

from app.services.acquisition import browser_capture, browser_detail, browser_recovery, cookie_store, dom_runtime  # fmt: skip

from app.services.acquisition.browser_capture import BrowserNetworkCapture

from app.services.acquisition import browser_origin_warmup, browser_page_flow, browser_page_helpers, browser_pool, browser_readiness, browser_result_builder, browser_runtime  # fmt: skip

from app.services.acquisition.browser_fetch_support import build_browser_fetch_result

from app.services.acquisition.traversal import TraversalResult

from app.services.acquisition.runtime import BlockPageClassification

from app.services.config.runtime_settings import crawler_runtime_settings

from app.services.config.selectors import CARD_SELECTORS

from app.services.pipeline.extract_records import extract_records


@pytest.fixture(autouse=True)
def _reset_origin_warmup_state(monkeypatch: pytest.MonkeyPatch):
    async def _no_saved_domain_state(*_args, **_kwargs):
        await _async_checkpoint()
        return None

    monkeypatch.setattr(
        cookie_store,
        "load_storage_state_for_domain",
        _no_saved_domain_state,
    )
    browser_origin_warmup.ORIGIN_WARMUP_IN_FLIGHT.clear()
    browser_origin_warmup.ORIGIN_WARMUP_RECENT.clear()
    yield
    browser_origin_warmup.ORIGIN_WARMUP_IN_FLIGHT.clear()
    browser_origin_warmup.ORIGIN_WARMUP_RECENT.clear()


async def _async_checkpoint() -> None:
    await asyncio.sleep(0)


def _network_capture_summary() -> SimpleNamespace:
    return SimpleNamespace(
        network_payload_count=0,
        malformed_network_payloads=0,
        network_payload_read_failures=0,
        network_payload_read_timeouts=0,
        closed_network_payloads=0,
        skipped_oversized_network_payloads=0,
        dropped_payload_events=0,
        payloads=[],
    )


class _StaticPayloadCapture:
    async def close(self, _page):
        await _async_checkpoint()
        return _network_capture_summary()


async def _emit_browser_event_noop(*_args, **_kwargs):
    await _async_checkpoint()
    return None


async def _classify_browser_page_ok(_html: str, _status_code: int):
    await _async_checkpoint()
    return BlockPageClassification(
        blocked=False,
        evidence=[],
        outcome="ok",
    )


@pytest.fixture
def browser_finalize_support() -> SimpleNamespace:
    visual_calls: list[str | None] = []

    async def _capture_fragments(*_args, **_kwargs):
        await _async_checkpoint()
        return []

    async def _capture_visuals(*_args, **_kwargs):
        await _async_checkpoint()
        visual_calls.append(_kwargs.get("surface"))
        return []

    def _make_payload(**overrides: Any) -> browser_result_builder.BrowserFinalizeInput:
        html = str(
            overrides.get(
                "html",
                "<html><body><h1>Widget Prime</h1><div>Description</div></body></html>",
            )
        )
        defaults = {
            "page": SimpleNamespace(url="https://example.com/products/widget"),
            "url": "https://example.com/products/widget",
            "surface": "ecommerce_detail",
            "browser_reason": "http-escalation",
            "on_event": None,
            "response": SimpleNamespace(status=200, headers={}),
            "navigation_strategy": "domcontentloaded",
            "readiness_probes": [],
            "networkidle_timed_out": False,
            "networkidle_skip_reason": None,
            "readiness_policy": {},
            "readiness_diagnostics": {},
            "expansion_diagnostics": {},
            "listing_recovery_diagnostics": {},
            "payload_capture": _StaticPayloadCapture(),
            "html": html,
            "traversal_result": None,
            "rendered_html": html,
            "phase_timings_ms": {},
            "started_at": 0.0,
        }
        return browser_result_builder.BrowserFinalizeInput(**{**defaults, **overrides})

    return SimpleNamespace(
        make_payload=_make_payload,
        classify_blocked_page_async=_classify_browser_page_ok,
        emit_browser_event=_emit_browser_event_noop,
        capture_fragments=_capture_fragments,
        capture_visuals=_capture_visuals,
        visual_calls=visual_calls,
    )


@dataclass
class _FakeHandle:
    label: str
    page: "_FakeExpansionPage"
    attributes: dict[str, str]
    element_identity: str = "node-1"
    tag_name: str = "button"
    actionable: bool = True
    inside_main: bool = False
    inside_header: bool = False
    inside_nav: bool = False
    inside_footer: bool = False
    inside_aside: bool = False

    async def evaluate(self, script: str) -> str | dict[str, bool] | None:
        await _async_checkpoint()
        if "pieces" in script:
            return self.label
        if "insideMain" in script:
            return {
                "elementIdentity": self.element_identity,
                "insideMain": self.inside_main,
                "insideHeader": self.inside_header,
                "insideNav": self.inside_nav,
                "insideFooter": self.inside_footer,
                "insideAside": self.inside_aside,
            }
        if "tagName" in script:
            return self.tag_name
        if "getBoundingClientRect" in script:
            return {"actionable": self.actionable}
        self.page.expanded = True
        return None

    async def inner_text(self) -> str:
        await _async_checkpoint()
        return self.label

    async def get_attribute(self, name: str) -> str | None:
        await _async_checkpoint()
        return self.attributes.get(name)

    async def is_visible(self) -> bool:
        await _async_checkpoint()
        return self.actionable

    async def scroll_into_view_if_needed(self) -> None:
        await _async_checkpoint()
        return None

    async def click(self, **_kwargs) -> None:
        await _async_checkpoint()
        self.page.expanded = True


class _FakeLocator:
    def __init__(self, page: "_FakeExpansionPage", selector: str) -> None:
        self._page = page
        self._selector = selector

    @property
    def first(self) -> "_FakeLocator":
        return self

    async def element_handles(self) -> list[_FakeHandle]:
        await _async_checkpoint()
        handles: list[_FakeHandle] = []
        for index, row in enumerate(self._page.labels):
            attributes = {
                str(key): str(value)
                for key, value in dict(row.get("attributes", {})).items()
            }
            tag_name = str(row.get("tag_name", "button"))
            if not self._matches_selector(tag_name, attributes):
                continue
            handles.append(
                _FakeHandle(
                    row["label"],
                    self._page,
                    attributes=attributes,
                    element_identity=str(
                        row.get("element_identity") or f"node-{index + 1}"
                    ),
                    tag_name=tag_name,
                    actionable=bool(row.get("actionable", True)),
                    inside_main=bool(row.get("inside_main", False)),
                    inside_header=bool(row.get("inside_header", False)),
                    inside_nav=bool(row.get("inside_nav", False)),
                    inside_footer=bool(row.get("inside_footer", False)),
                    inside_aside=bool(row.get("inside_aside", False)),
                )
            )
        return handles

    def _matches_selector(
        self,
        tag_name: str,
        attributes: dict[str, str],
    ) -> bool:
        selector = self._selector
        role = str(attributes.get("role") or "").lower()
        aria_controls = str(attributes.get("aria-controls") or "")
        aria_expanded = str(attributes.get("aria-expanded") or "").lower()
        lowered_tag = tag_name.lower()
        tag_selectors = {
            "summary": "summary",
            "details > summary": "summary",
            "button": "button",
            "a": "a",
        }
        if selector in tag_selectors:
            return lowered_tag == tag_selectors[selector]
        if selector == "[role='button']":
            return role == "button"
        controlled_selectors = {
            "button[aria-controls]": lowered_tag == "button",
            "[role='button'][aria-controls]": role == "button",
            "[role='tab'][aria-controls]": role == "tab",
        }
        if selector in controlled_selectors:
            return controlled_selectors[selector] and bool(aria_controls)
        if selector == "a[href^='#']":
            return lowered_tag == "a" and str(attributes.get("href") or "").startswith(
                "#"
            )
        if selector == "[aria-expanded='false']":
            return aria_expanded == "false"
        return False

    async def count(self) -> int:
        await _async_checkpoint()
        if self._selector in self._page.selector_counts:
            return int(self._page.selector_counts[self._selector])
        if self._selector in self._page.card_selectors:
            return int(self._page.card_count)
        return 0

    async def is_visible(self, **_kwargs) -> bool:
        return await self.count() > 0

    async def is_disabled(self) -> bool:
        await _async_checkpoint()
        return False

    async def click(self, **_kwargs) -> None:
        await _async_checkpoint()
        self._page.expanded = True


class _FakeRoleLocator:
    def __init__(self, page: "_FakeExpansionPage", role: str, name: object) -> None:
        self._page = page
        self._role = role
        self._name = str(name or "").lower()
        self._name_pattern = name if hasattr(name, "search") else None

    @property
    def first(self) -> "_FakeRoleLocator":
        return self

    def nth(self, index: int) -> "_FakeRoleLocator":
        del index
        return self

    async def count(self) -> int:
        await _async_checkpoint()
        return sum(
            1
            for role, name in self._page.role_targets
            if role == self._role and self._matches_name(name)
        )

    async def is_visible(self, **_kwargs) -> bool:
        return await self.count() > 0

    async def is_disabled(self) -> bool:
        await _async_checkpoint()
        return False

    async def click(self, **_kwargs) -> None:
        if await self.count():
            self._page.expanded = True

    def _matches_name(self, name: str) -> bool:
        if self._name_pattern is not None:
            return bool(self._name_pattern.search(name))
        return name == self._name


class _NoTimeoutRoleLocator(_FakeRoleLocator):
    async def is_visible(self, **_kwargs) -> bool:
        return await self.count() > 0


class _WaitingRoleLocator(_FakeRoleLocator):
    def __init__(self, page: "_FakeExpansionPage", role: str, name: str) -> None:
        super().__init__(page, role, name)
        self.wait_for_calls: list[tuple[str | None, int | None]] = []

    async def wait_for(
        self,
        *,
        state: str | None = None,
        **kwargs,
    ) -> None:
        self.wait_for_calls.append((state, kwargs.get("timeout")))
        if await self.count() == 0:
            raise PlaywrightTimeoutError("not visible")


class _FakePageContext:
    def __init__(self, page: "_FakeExpansionPage") -> None:
        self._page = page

    async def cookies(self, *_args, **_kwargs) -> list[dict[str, object]]:
        return await self._page._cookies(*_args, **_kwargs)

    async def close(self) -> None:
        await self._page._close_context()

    async def new_page(self) -> "_FakeExpansionPage":
        await _async_checkpoint()
        warm_page = _FakeExpansionPage(base_html=self._page.base_html)
        self._page.spawned_pages.append(warm_page)
        return warm_page

    def on(self, event_name: str, callback: Any) -> None:
        self._page.listeners.setdefault(f"context:{event_name}", []).append(callback)

    def remove_listener(self, event_name: str, callback: Any) -> None:
        key = f"context:{event_name}"
        listeners = self._page.listeners.get(key)
        if not listeners:
            return
        self._page.listeners[key] = [
            listener for listener in listeners if listener is not callback
        ]


class _FakeExpansionPage:
    def __init__(
        self,
        *,
        base_html: str,
        **options: Any,
    ) -> None:
        expanded_html = options.get("expanded_html")
        labels = options.get("labels")
        selector_counts = options.get("selector_counts")
        accessibility_snapshot = options.get("accessibility_snapshot")
        role_targets = options.get("role_targets")
        goto_failures = options.get("goto_failures")
        response_events = options.get("response_events")
        rendered_listing_fragments = options.get("rendered_listing_fragments")
        wait_html_sequence = options.get("wait_html_sequence")
        cookie_snapshots = options.get("cookie_snapshots")
        content_blocker = options.get("content_blocker")
        content_entered = options.get("content_entered")

        self.base_html = base_html
        self.expanded_html = str(expanded_html or base_html)
        self.shadow_html = options.get("shadow_html")
        self.labels = [*labels] if labels else []
        self.selector_counts = dict(selector_counts or {})
        self.card_count = int(options.get("card_count", 0))
        self.expanded = False
        self.url = "https://example.com/products/widget"
        self.wait_timeout_calls: list[int] = []
        self.wait_function_calls: list[int] = []
        self.load_state_calls: list[str] = []
        self.card_selectors = set()
        self.role_targets = set(role_targets or set())
        self.goto_calls: list[str] = []
        self.goto_timeout_calls: list[int | None] = []
        self.goto_failures = dict(goto_failures or {})
        self.goto_status = int(options.get("goto_status", 200))
        self.response_events = [*response_events] if response_events else []
        self.wait_for_selector_error = options.get("wait_for_selector_error")
        self.wait_for_selector_calls: list[tuple[str, str | None, int | None]] = []
        self.listeners: dict[str, list[Any]] = {}
        self.rendered_listing_fragments = (
            [*rendered_listing_fragments] if rendered_listing_fragments else []
        )
        self.wait_html_sequence = [*wait_html_sequence] if wait_html_sequence else []
        self.cookie_snapshots = [*cookie_snapshots] if cookie_snapshots else [[]]
        self.content_blocker = content_blocker
        self.content_block_after_calls = max(
            0, int(options.get("content_block_after_calls", 0))
        )
        self.ignore_content_cancellation = bool(
            options.get("ignore_content_cancellation", False)
        )
        self.content_entered = content_entered
        self.content_calls = 0
        self.context_close_calls = 0
        self.page_close_calls = 0
        self.spawned_pages: list[_FakeExpansionPage] = []
        self.accessibility = SimpleNamespace(
            snapshot=self._snapshot if accessibility_snapshot is not None else None
        )
        self._accessibility_snapshot = accessibility_snapshot
        self.shadow_flattened = False
        self.context = _FakePageContext(self)

    async def _snapshot(self) -> dict[str, object] | None:
        await _async_checkpoint()
        return self._accessibility_snapshot

    def on(self, event_name: str, callback: Any) -> None:
        self.listeners.setdefault(event_name, []).append(callback)

    def remove_listener(self, event_name: str, callback: Any) -> None:
        listeners = self.listeners.get(event_name)
        if not listeners:
            return
        self.listeners[event_name] = [
            listener for listener in listeners if listener is not callback
        ]

    async def goto(
        self,
        url: str,
        wait_until: str | None = None,
        **kwargs,
    ) -> Any:
        await _async_checkpoint()
        self.url = url
        strategy = str(wait_until or "")
        self.goto_calls.append(strategy)
        timeout = kwargs.get("timeout")
        self.goto_timeout_calls.append(timeout)
        if strategy in self.goto_failures:
            raise self.goto_failures[strategy]
        for callback in tuple(self.listeners.get("response", [])):
            for response in self.response_events:
                callback(response)
        return SimpleNamespace(
            status=self.goto_status,
            headers={"content-type": "text/html"},
        )

    async def _cookies(self, *_args, **_kwargs) -> list[dict[str, object]]:
        await _async_checkpoint()
        return [*(self.cookie_snapshots[0] if self.cookie_snapshots else [])]

    async def _close_context(self) -> None:
        await _async_checkpoint()
        self.context_close_calls += 1
        if self.content_blocker is not None:
            self.content_blocker.set()

    async def close(self) -> None:
        await _async_checkpoint()
        self.page_close_calls += 1
        if self.content_blocker is not None:
            self.content_blocker.set()

    async def evaluate(self, script: str, arg: Any | None = None) -> Any:
        await _async_checkpoint()
        if "document.querySelectorAll('*')" in script and self.shadow_html is not None:
            self.shadow_flattened = True
            return 1
        if "const selectors = Array.isArray(args?.selectors)" in script:
            return [*self.rendered_listing_fragments]
        if "querySelectorAll(selector).length" in script:
            selectors = [*(arg or [])]
            return max(
                (int(self.selector_counts.get(selector, 0)) for selector in selectors),
                default=0,
            )
        if "MutationObserver" in script:
            return {"observed": True}
        return None

    async def wait_for_timeout(self, timeout_ms: int) -> None:
        await _async_checkpoint()
        self.wait_timeout_calls.append(timeout_ms)
        if self.wait_html_sequence:
            next_html = self.wait_html_sequence.pop(0)
            self.base_html = next_html
            self.expanded_html = next_html
        if len(self.cookie_snapshots) > 1:
            self.cookie_snapshots.pop(0)

    async def wait_for_function(self, _script: str, **kwargs) -> None:
        await _async_checkpoint()
        arg = kwargs.get("arg")
        del arg
        timeout = kwargs.get("timeout")
        self.wait_function_calls.append(int(timeout or 0))
        if self.wait_html_sequence:
            next_html = self.wait_html_sequence.pop(0)
            self.base_html = next_html
            self.expanded_html = next_html
        if len(self.cookie_snapshots) > 1:
            self.cookie_snapshots.pop(0)

    async def wait_for_load_state(self, state: str, **_kwargs) -> None:
        await _async_checkpoint()
        self.load_state_calls.append(state)

    async def wait_for_selector(
        self,
        selector: str,
        *,
        state: str | None = None,
        **kwargs,
    ) -> None:
        await _async_checkpoint()
        timeout = kwargs.get("timeout")
        self.wait_for_selector_calls.append((selector, state, timeout))
        if self.wait_for_selector_error is not None:
            raise self.wait_for_selector_error

    def locator(self, selector: str) -> _FakeLocator:
        return _FakeLocator(self, selector)

    def get_by_role(
        self, role: str, *, name: str, exact: bool = True
    ) -> _FakeRoleLocator:
        del exact
        return _FakeRoleLocator(self, role, name)

    async def content(self) -> str:
        self.content_calls += 1
        if self.content_entered is not None:
            self.content_entered.set()
        if (
            self.content_blocker is not None
            and self.content_calls > self.content_block_after_calls
            and not self.content_blocker.is_set()
        ):
            while not self.content_blocker.is_set():
                try:
                    await self.content_blocker.wait()
                except asyncio.CancelledError:
                    if not self.ignore_content_cancellation:
                        raise
        html = self.expanded_html if self.expanded else self.base_html
        if self.shadow_flattened and self.shadow_html is not None:
            return self.shadow_html
        return html

    async def screenshot(self, *, path: str | Path | None = None, **kwargs) -> bytes:
        await _async_checkpoint()
        del kwargs
        payload = b"fake-png"
        if path is not None:
            Path(path).write_bytes(payload)
        return payload


class _FakeRuntime:
    def __init__(self, page: _FakeExpansionPage) -> None:
        self._page = page

    @asynccontextmanager
    async def page(self, **_kwargs):
        await _async_checkpoint()
        yield self._page


__all__ = ['Any', 'BeautifulSoup', 'BlockPageClassification', 'BrowserNetworkCapture', 'CARD_SELECTORS', 'Path', 'PlaywrightError', 'PlaywrightTimeoutError', 'SimpleNamespace', 'TraversalResult', '_FakeExpansionPage', '_FakeHandle', '_FakeLocator', '_FakePageContext', '_FakeRoleLocator', '_FakeRuntime', '_NoTimeoutRoleLocator', '_StaticPayloadCapture', '_WaitingRoleLocator', '_async_checkpoint', '_classify_browser_page_ok', '_emit_browser_event_noop', '_network_capture_summary', '_reset_origin_warmup_state', 'annotations', 'asynccontextmanager', 'asyncio', 'browser_capture', 'browser_detail', 'browser_finalize_support', 'browser_page_flow', 'browser_page_helpers', 'browser_pool', 'browser_readiness', 'browser_recovery', 'browser_result_builder', 'browser_runtime', 'build_browser_fetch_result', 'cookie_store', 'crawler_runtime_settings', 'dataclass', 'dom_runtime', 'extract_records', 'httpx', 'pytest', 'time']  # fmt: skip

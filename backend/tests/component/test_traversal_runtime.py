from __future__ import annotations

from dataclasses import dataclass

from typing import Any

import pytest

import app.services.acquisition.traversal as traversal_module

import app.services.acquisition.traversal_helpers as traversal_helpers

from app.services.config.selectors import CARD_SELECTORS, PAGINATION_SELECTORS

from app.services.extract.listing_card_fragments import (
    listing_node_html,
    listing_selector_is_weak,
)

TraversalResult = traversal_module.TraversalResult

click_with_retry = traversal_module.click_with_retry

locator_still_resolves = traversal_module.locator_still_resolves

wait_for_load_more_card_gain = traversal_module.wait_for_load_more_card_gain

count_listing_cards = traversal_module.count_listing_cards

dismiss_overlays_if_needed = traversal_module.dismiss_overlays_if_needed

execute_listing_traversal = traversal_module.execute_listing_traversal

@dataclass
class _State:
    html: str
    card_count: int
    scroll_height: int
    client_height: int = 600
    overflow_containers: int = 0
    controls: set[str] | None = None
    role_controls: list[dict[str, Any]] | None = None
    next_href: str | None = None
    next_control_state: dict[str, Any] | None = None

class _FakeLocator:
    def __init__(self, page: "_FakePage", selector: str) -> None:
        self._page = page
        self._selector = selector

    @property
    def first(self) -> "_FakeLocator":
        return self

    async def count(self) -> int:
        if self._selector in _card_selectors(self._page.surface):
            return int(self._page.state.card_count)
        return int(
            _selector_group(self._selector) in (self._page.state.controls or set())
        )

    async def is_visible(self, timeout: int | None = None) -> bool:
        return await self.count() > 0

    async def is_disabled(self) -> bool:
        return False

    async def scroll_into_view_if_needed(self, timeout: int | None = None) -> None:
        return None

    async def click(self, timeout: int | None = None, force: bool = False) -> None:
        del timeout, force
        group = _selector_group(self._selector)
        if group == "load_more":
            self._page.load_more_clicks += 1
            self._page.state = self._page.load_more_states[
                min(self._page.load_more_clicks, len(self._page.load_more_states) - 1)
            ]
            return
        if group == "next_page":
            next_href = str(self._page.state.next_href or "").strip().lower()
            if next_href and not next_href.startswith(("#", "javascript:")):
                await self._page.goto(self._page.state.next_href or self._page.url)
                return
            self._page.page_index = min(
                self._page.page_index + 1, len(self._page.paginated_states) - 1
            )
            self._page.state = self._page.paginated_states[self._page.page_index]

    async def get_attribute(self, name: str) -> str | None:
        if name == "href" and _selector_group(self._selector) == "next_page":
            return self._page.state.next_href
        return None

    async def evaluate(self, script: str) -> Any:
        del script
        if _selector_group(self._selector) == "next_page":
            return dict(self._page.state.next_control_state or {})
        return {}

class _EmptyRoleLocator:
    async def count(self) -> int:
        return 0

    def nth(self, index: int) -> "_EmptyRoleLocator":
        del index
        return self

    async def is_visible(self, timeout: int | None = None) -> bool:
        return False

    async def is_disabled(self) -> bool:
        return False

class _RoleLocator:
    def __init__(self, page: "_FakePage", matches: list[dict[str, Any]]) -> None:
        self._page = page
        self._matches = matches

    async def count(self) -> int:
        return len(self._matches)

    def nth(self, index: int) -> "_RoleLocator":
        if index >= len(self._matches):
            return _RoleLocator(self._page, [])
        return _RoleLocator(self._page, [self._matches[index]])

    async def is_visible(self, timeout: int | None = None) -> bool:
        if not self._matches:
            return False
        return bool(self._matches[0].get("visible", True))

    async def is_disabled(self) -> bool:
        if not self._matches:
            return True
        return bool(self._matches[0].get("disabled", False))

    async def scroll_into_view_if_needed(self, timeout: int | None = None) -> None:
        return None

    async def evaluate(self, script: str) -> Any:
        del script
        return None

    async def click(self, timeout: int | None = None, force: bool = False) -> None:
        del timeout, force
        if not self._matches:
            return
        self._page.role_clicks.append(str(self._matches[0].get("name") or ""))

class _FakePage:
    def __init__(
        self,
        *,
        surface: str,
        initial_state: _State,
        paginated_states: list[_State] | None = None,
        load_more_states: list[_State] | None = None,
        scroll_states: list[_State] | None = None,
    ) -> None:
        self.surface = surface
        self.state = initial_state
        self.paginated_states = list(paginated_states or [initial_state])
        self.load_more_states = list(load_more_states or [initial_state])
        self.scroll_states = list(scroll_states or [initial_state])
        self.url = "https://example.com/listing"
        self.page_index = 0
        self.scroll_index = 0
        self.load_more_clicks = 0
        self.goto_calls: list[str] = []
        self.load_state_calls: list[str] = []
        self.wait_timeout_calls: list[int] = []
        self.mutation_settle_calls = 0
        self.role_clicks: list[str] = []

    def locator(self, selector: str) -> _FakeLocator:
        return _FakeLocator(self, selector)

    def get_by_role(
        self, role: str, name: object = None
    ) -> _EmptyRoleLocator | _RoleLocator:
        matches: list[dict[str, Any]] = []
        for control in list(self.state.role_controls or []):
            if str(control.get("role") or "") != role:
                continue
            candidate_name = str(control.get("name") or "")
            if hasattr(name, "search"):
                if not name.search(candidate_name):
                    continue
            elif name is not None and candidate_name != name:
                continue
            matches.append(control)
        if not matches:
            return _EmptyRoleLocator()
        return _RoleLocator(self, matches)

    async def evaluate(self, script: str, arg: Any | None = None) -> Any:
        if "scrollTo({" in script:
            self.scroll_index = min(self.scroll_index + 1, len(self.scroll_states) - 1)
            self.state = self.scroll_states[self.scroll_index]
            return None
        if "querySelectorAll(selector).length" in script:
            selectors = list(arg or [])
            highest = 0
            for selector in selectors:
                if selector in _card_selectors(self.surface):
                    highest = max(highest, int(self.state.card_count))
            return highest
        if "MutationObserver" in script:
            self.mutation_settle_calls += 1
            return {"observed": True}
        return {
            "scroll_height": self.state.scroll_height,
            "client_height": self.state.client_height,
            "overflow_containers": self.state.overflow_containers,
        }

    async def wait_for_timeout(self, timeout_ms: int) -> None:
        self.wait_timeout_calls.append(timeout_ms)

    async def wait_for_load_state(self, state: str, timeout: int | None = None) -> None:
        del timeout
        self.load_state_calls.append(state)

    async def content(self) -> str:
        return self.state.html

    async def goto(
        self, url: str, wait_until: str | None = None, timeout: int | None = None
    ) -> None:
        del wait_until, timeout
        self.goto_calls.append(url)
        self.url = url
        self.page_index = min(self.page_index + 1, len(self.paginated_states) - 1)
        self.state = self.paginated_states[self.page_index]

class _OverlayTestLocator:
    def __init__(self) -> None:
        self.evaluate_calls: list[str] = []

    async def evaluate(self, script: str) -> int:
        self.evaluate_calls.append(script)
        return 1

class _OverlayTestPage:
    def locator(self, selector: str) -> "_OverlayCookieLocator":
        del selector
        return _OverlayCookieLocator()

    async def wait_for_timeout(self, timeout_ms: int) -> None:
        return None

class _OverlayCookieLocator:
    @property
    def first(self) -> "_OverlayCookieLocator":
        return self

    async def count(self) -> int:
        return 0

    async def is_visible(self, timeout: int | None = None) -> bool:
        return False

def _selector_group(selector: str) -> str:
    for group, selectors in PAGINATION_SELECTORS.items():
        if selector in selectors:
            return str(group)
    return ""

def _card_selectors(surface: str) -> list[str]:
    group = "jobs" if surface.startswith("job_") else "ecommerce"
    return list(CARD_SELECTORS.get(group) or [])


__all__ = ['Any', 'CARD_SELECTORS', 'PAGINATION_SELECTORS', 'TraversalResult', '_EmptyRoleLocator', '_FakeLocator', '_FakePage', '_OverlayCookieLocator', '_OverlayTestLocator', '_OverlayTestPage', '_RoleLocator', '_State', '_card_selectors', '_selector_group', 'annotations', 'click_with_retry', 'count_listing_cards', 'dataclass', 'dismiss_overlays_if_needed', 'execute_listing_traversal', 'listing_node_html', 'listing_selector_is_weak', 'locator_still_resolves', 'pytest', 'traversal_helpers', 'traversal_module', 'wait_for_load_more_card_gain']  # fmt: skip

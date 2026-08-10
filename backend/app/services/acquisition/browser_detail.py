from __future__ import annotations

import asyncio
import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any
from patchright.async_api import TimeoutError as PlaywrightTimeoutError

from app.services.config.extraction_rules import (
    BROWSER_DETAIL_CHROME_TOKENS,
    BROWSER_DETAIL_EXPANDABLE_SELECTOR_SET,
    BROWSER_DETAIL_EXPAND_KEYWORDS,
    BROWSER_DETAIL_SIZE_TOGGLE_TOKENS,
    DETAIL_AOM_EXPAND_ROLES,
    BROWSER_REQUESTED_DETAIL_GENERIC_TOGGLE_LABELS,
    BROWSER_REQUESTED_DETAIL_SELECTOR_PRIORITY,
    DETAIL_BLOCKED_TOKENS,
    DETAIL_EXPANSION_STATUS_ATTEMPTED,
    DETAIL_EXPANSION_STATUS_EXPANDED,
    DETAIL_EXPANSION_STATUS_INTERACTION_FAILED,
    DETAIL_EXPANSION_STATUS_INTERACTION_LIMIT_REACHED,
    DETAIL_EXPANSION_STATUS_SELECTOR_LIMIT_REACHED,
    DETAIL_EXPANSION_STATUS_NO_MATCHES,
    DETAIL_EXPANSION_STATUS_SKIPPED,
    DETAIL_EXPANSION_STATUS_TIME_BUDGET_REACHED,
    DETAIL_EXPAND_KEYWORD_EXTENSIONS,
    DETAIL_EXPAND_SELECTORS,
)
from app.services.config.runtime_settings import crawler_runtime_settings
from app.services.field_policy import (
    exact_requested_field_key,
    NORMALIZED_REQUESTED_FIELD_ALIASES,
    normalize_requested_field,
)
from app.services.shared.field_coerce import coerce_int as _coerce_int
from app.services.shared.coerce_primitives import string_list

_DETAIL_EXPAND_KEYWORDS: dict[str, tuple[str, ...]] = {
    str(key): tuple(str(item) for item in value or [])
    for key, value in dict(BROWSER_DETAIL_EXPAND_KEYWORDS or {}).items()
}


def _accessibility_snapshot_timeout_seconds() -> float:
    try:
        timeout = float(
            crawler_runtime_settings.browser_accessibility_snapshot_timeout_seconds
        )
    except (TypeError, ValueError):
        timeout = float(
            crawler_runtime_settings.__class__.model_fields[
                "browser_accessibility_snapshot_timeout_seconds"
            ].default
        )
    return max(0.0, timeout)


def detail_expansion_skip(reason: str) -> dict[str, object]:
    return {
        "status": DETAIL_EXPANSION_STATUS_SKIPPED,
        "reason": reason,
        "clicked_count": 0,
        "expanded_elements": [],
        "interaction_failures": [],
        "dom": {},
        "aom": {},
    }


def _ordered_detail_expand_selectors(
    selectors: list[str],
    *,
    requested_keywords: tuple[str, ...],
) -> list[str]:
    if not requested_keywords:
        return selectors
    priority_order: dict[str, int] = {}
    for keyword in requested_keywords:
        normalized_keyword = str(keyword or "").strip().lower()
        if not normalized_keyword:
            continue
        for selector in selectors:
            if normalized_keyword in selector.lower():
                priority_order.setdefault(selector, len(priority_order))
    for selector in BROWSER_REQUESTED_DETAIL_SELECTOR_PRIORITY:
        priority_order.setdefault(selector, len(priority_order))
    return sorted(
        selectors,
        key=lambda selector: priority_order.get(selector, len(priority_order)),
    )


def _requested_match_priority(
    snapshot: dict[str, object],
    *,
    requested_keywords: tuple[str, ...],
) -> tuple[int, str]:
    label = str(snapshot.get("label") or "").strip().lower()
    aria_controls = str(snapshot.get("aria_controls") or "").strip().lower()
    data_qa_action = str(snapshot.get("data_qa_action") or "").strip().lower()
    href = str(snapshot.get("href") or "").strip().lower()
    requested_keyword_probe = " ".join(
        part for part in (label, aria_controls, data_qa_action, href) if part
    ).strip()
    matches_requested_keywords = bool(
        requested_keywords
        and any(keyword in requested_keyword_probe for keyword in requested_keywords)
    )
    return (0 if matches_requested_keywords else 1, label)


async def expand_detail_content_if_needed_impl(
    page: Any,
    *,
    surface: str,
    readiness_probe: dict[str, object],
    requested_fields: list[str] | None,
    expand_all_interactive_elements,
    probe_browser_readiness,
    expand_interactive_elements_via_accessibility,
) -> dict[str, object]:
    current_probe = dict(readiness_probe or {})
    if "detail" not in str(surface or "").lower():
        return detail_expansion_skip("non_detail_surface")
    if readiness_probe and not current_probe.get("detail_like"):
        return detail_expansion_skip("not_detail_like")
    dom = await expand_all_interactive_elements(
        page,
        surface=surface,
        requested_fields=requested_fields,
        max_elapsed_ms=int(crawler_runtime_settings.detail_expand_max_elapsed_ms),
    )
    if dom.get("clicked_count", 0):
        current_probe = await probe_browser_readiness(
            page,
            url=str(getattr(page, "url", "") or ""),
            surface=surface,
        )
    aom = {
        "status": DETAIL_EXPANSION_STATUS_SKIPPED,
        "reason": "not_needed",
        "clicked_count": 0,
        "expanded_elements": [],
        "interaction_failures": [],
        "limit": int(crawler_runtime_settings.detail_aom_expand_max_interactions),
        "max_elapsed_ms": int(
            crawler_runtime_settings.detail_aom_expand_max_elapsed_ms
        ),
        "attempted": False,
    }
    if not current_probe.get("is_ready"):
        aom = await expand_interactive_elements_via_accessibility(
            page,
            surface=surface,
            requested_fields=requested_fields,
            max_elapsed_ms=int(
                crawler_runtime_settings.detail_aom_expand_max_elapsed_ms
            ),
        )
    return {
        "status": DETAIL_EXPANSION_STATUS_EXPANDED
        if dom.get("clicked_count", 0) or aom.get("clicked_count", 0)
        else DETAIL_EXPANSION_STATUS_ATTEMPTED,
        "reason": "missing_detail_content",
        "clicked_count": _coerce_int(dom.get("clicked_count"), default=0)
        + _coerce_int(aom.get("clicked_count"), default=0),
        "expanded_elements": [
            *string_list(dom.get("expanded_elements"), accept_iterable=True),
            *string_list(aom.get("expanded_elements"), accept_iterable=True),
        ],
        "interaction_failures": [
            *string_list(dom.get("interaction_failures"), accept_iterable=True),
            *string_list(aom.get("interaction_failures"), accept_iterable=True),
        ],
        "dom": dom,
        "aom": aom,
    }


def _finish_expansion_diagnostics(
    diagnostics: dict[str, object],
    *,
    clicked_count: int,
    expanded_elements: list[str],
    interaction_failures: list[str],
    started_at: float,
    elapsed_ms: Callable[[float], int],
) -> dict[str, object]:
    if diagnostics.get("status") == DETAIL_EXPANSION_STATUS_ATTEMPTED:
        if clicked_count > 0:
            diagnostics["status"] = DETAIL_EXPANSION_STATUS_EXPANDED
        elif interaction_failures:
            diagnostics["status"] = DETAIL_EXPANSION_STATUS_INTERACTION_FAILED
        else:
            diagnostics["status"] = DETAIL_EXPANSION_STATUS_NO_MATCHES
    diagnostics["clicked_count"] = clicked_count
    diagnostics["expanded_elements"] = expanded_elements
    diagnostics["interaction_failures"] = interaction_failures
    diagnostics["elapsed_ms"] = elapsed_ms(started_at)
    return diagnostics


@dataclass(slots=True)
class _DomExpansionState:
    started_at: float
    max_interactions: int
    max_per_selector: int
    max_elapsed_ms: int | None
    elapsed_ms: Callable[[float], int]
    diagnostics: dict[str, object]
    clicked_count: int = 0
    expanded_elements: list[str] = field(default_factory=list)
    interaction_failures: list[str] = field(default_factory=list)
    seen_candidates: set[tuple[str, str, str]] = field(default_factory=set)

    def time_budget_reached(self) -> bool:
        return bool(
            self.max_elapsed_ms is not None
            and self.elapsed_ms(self.started_at) >= int(self.max_elapsed_ms)
        )

    def stop_status(self, *, selector_clicks: int | None = None) -> str | None:
        if self.clicked_count >= self.max_interactions:
            return DETAIL_EXPANSION_STATUS_INTERACTION_LIMIT_REACHED
        if self.time_budget_reached():
            return DETAIL_EXPANSION_STATUS_TIME_BUDGET_REACHED
        if selector_clicks is not None and selector_clicks >= self.max_per_selector:
            return DETAIL_EXPANSION_STATUS_SELECTOR_LIMIT_REACHED
        return None


@dataclass(frozen=True, slots=True)
class _ExpansionCandidate:
    label: str
    probe: str
    aria_expanded: str
    href: str
    aria_controls: str
    data_qa_action: str
    class_name: str
    tag_name: str
    inside_main: bool
    inside_header: bool
    inside_nav: bool
    inside_footer: bool
    inside_aside: bool
    visible: bool
    actionable: bool

    @property
    def key(self) -> tuple[str, str, str]:
        return self.label or self.probe, self.aria_controls, self.tag_name


@dataclass(frozen=True, slots=True)
class _ExpansionMatches:
    requested: bool
    fallback_requested: bool
    generic: bool
    generic_requested_toggle: bool
    size_toggle: bool


def _new_dom_expansion_state(
    *,
    started_at: float,
    max_elapsed_ms: int | None,
    elapsed_ms: Callable[[float], int],
) -> _DomExpansionState:
    max_interactions = max(
        0,
        min(
            int(crawler_runtime_settings.detail_expand_max_interactions),
            int(crawler_runtime_settings.accordion_expand_max),
        ),
    )
    return _DomExpansionState(
        started_at=started_at,
        max_interactions=max_interactions,
        max_per_selector=max(
            1, int(crawler_runtime_settings.detail_expand_max_per_selector)
        ),
        max_elapsed_ms=max_elapsed_ms,
        elapsed_ms=elapsed_ms,
        diagnostics={
            "status": DETAIL_EXPANSION_STATUS_ATTEMPTED,
            "buttons_found": 0,
            "clicked_count": 0,
            "expanded_elements": [],
            "interaction_failures": [],
            "limit": int(crawler_runtime_settings.detail_expand_max_interactions),
            "max_elapsed_ms": max_elapsed_ms,
        },
    )


async def _selector_candidate_rows(
    page: Any,
    selector: str,
    *,
    requested_keywords: tuple[str, ...],
    interactive_candidate_snapshot,
    state: _DomExpansionState,
) -> list[tuple[Any, dict[str, object] | None]]:
    try:
        candidates = await page.locator(selector).element_handles()
    except Exception as exc:
        state.interaction_failures.append(f"locator_failed:{selector}:{exc}")
        return []
    state.diagnostics["buttons_found"] = _coerce_int(
        state.diagnostics["buttons_found"]
    ) + len(candidates)
    if not requested_keywords:
        return [(handle, None) for handle in candidates]
    prioritized_rows: list[tuple[tuple[int, str], Any, dict[str, object]]] = []
    for handle in candidates:
        if state.time_budget_reached():
            state.diagnostics["status"] = DETAIL_EXPANSION_STATUS_TIME_BUDGET_REACHED
            break
        try:
            snapshot = await interactive_candidate_snapshot(handle)
        except Exception as exc:
            state.interaction_failures.append(str(exc))
            continue
        prioritized_rows.append(
            (
                _requested_match_priority(
                    snapshot,
                    requested_keywords=requested_keywords,
                ),
                handle,
                snapshot,
            )
        )
    return [
        (handle, snapshot)
        for _priority, handle, snapshot in sorted(
            prioritized_rows,
            key=lambda row: row[0],
        )
    ]


def _candidate_action_label(
    snapshot: dict[str, object],
    *,
    selector: str,
    requested_fields: list[str] | None,
    requested_keywords: tuple[str, ...],
    keywords: tuple[str, ...],
    seen_candidates: set[tuple[str, str, str]],
) -> tuple[bool, str]:
    candidate = _normalized_expansion_candidate(snapshot)
    if not candidate.visible or not candidate.actionable:
        return False, ""
    if candidate.key in seen_candidates:
        return False, ""
    seen_candidates.add(candidate.key)
    matches = _expansion_candidate_matches(
        candidate,
        requested_fields=requested_fields,
        requested_keywords=requested_keywords,
        keywords=keywords,
    )
    if _expansion_candidate_is_blocked(candidate, size_toggle=matches.size_toggle):
        return False, ""
    if requested_fields and not (
        matches.requested
        or matches.fallback_requested
        or matches.generic_requested_toggle
        or matches.size_toggle
    ):
        return False, ""
    if not _expansion_candidate_is_expandable(candidate, selector, matches):
        return False, ""
    if not _expansion_candidate_is_in_safe_context(candidate, matches):
        return False, ""
    return True, candidate.label or candidate.probe


def _normalized_expansion_candidate(
    snapshot: dict[str, object],
) -> _ExpansionCandidate:
    def normalized(key: str) -> str:
        return str(snapshot.get(key) or "").strip().lower()

    return _ExpansionCandidate(
        label=normalized("label"),
        probe=normalized("probe"),
        aria_expanded=normalized("aria_expanded"),
        href=normalized("href"),
        aria_controls=normalized("aria_controls"),
        data_qa_action=normalized("data_qa_action"),
        class_name=normalized("class_name"),
        tag_name=normalized("tag_name"),
        inside_main=bool(snapshot.get("inside_main")),
        inside_header=bool(snapshot.get("inside_header")),
        inside_nav=bool(snapshot.get("inside_nav")),
        inside_footer=bool(snapshot.get("inside_footer")),
        inside_aside=bool(snapshot.get("inside_aside")),
        visible=bool(snapshot.get("visible")),
        actionable=bool(snapshot.get("actionable")),
    )


def _expansion_candidate_matches(
    candidate: _ExpansionCandidate,
    *,
    requested_fields: list[str] | None,
    requested_keywords: tuple[str, ...],
    keywords: tuple[str, ...],
) -> _ExpansionMatches:
    requested_probe = " ".join(
        part
        for part in (
            candidate.label,
            candidate.aria_controls,
            candidate.data_qa_action,
        )
        if part
    ).strip()
    generic_probe = " ".join(
        part
        for part in (
            candidate.label,
            candidate.probe,
            candidate.data_qa_action,
            candidate.class_name,
        )
        if part
    ).strip()
    size_toggle = any(
        token in f"{candidate.data_qa_action} {candidate.class_name}"
        for token in BROWSER_DETAIL_SIZE_TOGGLE_TOKENS
    )
    return _ExpansionMatches(
        requested=bool(
            requested_keywords
            and any(keyword in requested_probe for keyword in requested_keywords)
        ),
        fallback_requested=any(keyword in requested_probe for keyword in keywords),
        generic=any(keyword in generic_probe for keyword in keywords),
        generic_requested_toggle=bool(
            requested_fields
            and candidate.aria_controls
            and candidate.label in BROWSER_REQUESTED_DETAIL_GENERIC_TOGGLE_LABELS
        ),
        size_toggle=size_toggle,
    )


def _expansion_candidate_is_blocked(
    candidate: _ExpansionCandidate,
    *,
    size_toggle: bool,
) -> bool:
    keyword_probe = " ".join(
        part
        for part in (
            candidate.label,
            candidate.probe,
            candidate.data_qa_action,
            candidate.class_name,
        )
        if part
    ).strip()
    navigational_anchor = bool(
        candidate.tag_name == "a"
        and candidate.href
        and not candidate.href.startswith(("#", "javascript:", "mailto:", "tel:"))
        and not candidate.aria_controls
        and not size_toggle
    )
    chrome_token = any(
        token in keyword_probe for token in BROWSER_DETAIL_CHROME_TOKENS
    )
    blocked_token = any(token in keyword_probe for token in DETAIL_BLOCKED_TOKENS)
    return navigational_anchor or chrome_token or (blocked_token and not size_toggle)


def _expansion_candidate_is_expandable(
    candidate: _ExpansionCandidate,
    selector: str,
    matches: _ExpansionMatches,
) -> bool:
    return bool(
        selector in BROWSER_DETAIL_EXPANDABLE_SELECTOR_SET
        or candidate.aria_expanded == "false"
        or candidate.aria_controls
        or candidate.tag_name == "summary"
        or matches.requested
        or matches.generic
    )


def _expansion_candidate_is_in_safe_context(
    candidate: _ExpansionCandidate,
    matches: _ExpansionMatches,
) -> bool:
    outside_main_chrome = bool(
        not candidate.inside_main
        and (candidate.inside_header or candidate.inside_nav or candidate.inside_footer)
    )
    if outside_main_chrome and not (matches.requested or matches.size_toggle):
        return False
    if not candidate.inside_aside:
        return True
    return bool(
        candidate.aria_controls
        or candidate.aria_expanded == "false"
        or matches.requested
        or matches.fallback_requested
        or matches.generic
        or matches.size_toggle
    )


async def _execute_expansion_action(
    page: Any,
    handle: Any,
    *,
    click_timeout_ms: int,
) -> None:
    await handle.scroll_into_view_if_needed()
    try:
        await handle.click(timeout=click_timeout_ms)
    except Exception:
        await handle.evaluate("(node) => node instanceof HTMLElement && node.click()")
    wait_ms = int(crawler_runtime_settings.accordion_expand_wait_ms)
    if wait_ms > 0:
        await page.wait_for_timeout(wait_ms)


async def _expand_selector_candidates(
    page: Any,
    selector: str,
    *,
    requested_fields: list[str] | None,
    requested_keywords: tuple[str, ...],
    keywords: tuple[str, ...],
    interactive_candidate_snapshot,
    click_timeout_ms: int,
    state: _DomExpansionState,
) -> None:
    candidate_rows = await _selector_candidate_rows(
        page,
        selector,
        requested_keywords=requested_keywords,
        interactive_candidate_snapshot=interactive_candidate_snapshot,
        state=state,
    )
    selector_clicks = 0
    for handle, prefetched_snapshot in candidate_rows:
        stop_status = state.stop_status(selector_clicks=selector_clicks)
        if stop_status:
            if stop_status != DETAIL_EXPANSION_STATUS_SELECTOR_LIMIT_REACHED:
                state.diagnostics["status"] = stop_status
            break
        try:
            snapshot = (
                prefetched_snapshot
                if prefetched_snapshot is not None
                else await interactive_candidate_snapshot(handle)
            )
            should_click, expanded_label = _candidate_action_label(
                snapshot,
                selector=selector,
                requested_fields=requested_fields,
                requested_keywords=requested_keywords,
                keywords=keywords,
                seen_candidates=state.seen_candidates,
            )
            if not should_click:
                continue
            if state.time_budget_reached():
                state.diagnostics["status"] = (
                    DETAIL_EXPANSION_STATUS_TIME_BUDGET_REACHED
                )
                break
            await _execute_expansion_action(
                page,
                handle,
                click_timeout_ms=click_timeout_ms,
            )
            state.clicked_count += 1
            selector_clicks += 1
            if expanded_label:
                state.expanded_elements.append(expanded_label)
            if state.time_budget_reached():
                state.diagnostics["status"] = (
                    DETAIL_EXPANSION_STATUS_TIME_BUDGET_REACHED
                )
                break
        except Exception as exc:
            state.interaction_failures.append(str(exc))


async def expand_all_interactive_elements_impl(
    page: Any,
    *,
    surface: str,
    requested_fields: list[str] | None,
    detail_expand_selectors: tuple[str, ...] | list[str],
    detail_expansion_keywords,
    interactive_candidate_snapshot,
    elapsed_ms,
    max_elapsed_ms: int | None = None,
) -> dict[str, object]:
    started_at = time.perf_counter()
    click_timeout_ms = int(crawler_runtime_settings.detail_expand_click_timeout_ms)
    state = _new_dom_expansion_state(
        started_at=started_at,
        max_elapsed_ms=max_elapsed_ms,
        elapsed_ms=elapsed_ms,
    )
    keywords = detail_expansion_keywords(surface, requested_fields=requested_fields)
    requested_keywords = requested_field_tokens(requested_fields)
    selectors = [
        str(selector).strip()
        for selector in detail_expand_selectors or []
        if str(selector).strip()
    ]
    selectors = _ordered_detail_expand_selectors(
        selectors,
        requested_keywords=requested_keywords,
    )
    for selector in selectors:
        stop_status = state.stop_status()
        if stop_status:
            state.diagnostics["status"] = stop_status
            break
        await _expand_selector_candidates(
            page,
            selector,
            requested_fields=requested_fields,
            requested_keywords=requested_keywords,
            keywords=keywords,
            interactive_candidate_snapshot=interactive_candidate_snapshot,
            click_timeout_ms=click_timeout_ms,
            state=state,
        )
    return _finish_expansion_diagnostics(
        state.diagnostics,
        clicked_count=state.clicked_count,
        expanded_elements=state.expanded_elements,
        interaction_failures=state.interaction_failures,
        started_at=started_at,
        elapsed_ms=elapsed_ms,
    )


async def expand_interactive_elements_via_accessibility_impl(
    page: Any,
    *,
    surface: str,
    requested_fields: list[str] | None,
    accessibility_expand_candidates,
    detail_expansion_keywords,
    elapsed_ms,
    max_elapsed_ms: int | None = None,
) -> dict[str, object]:
    started_at = time.perf_counter()
    click_timeout_ms = int(crawler_runtime_settings.detail_expand_click_timeout_ms)
    visibility_timeout_ms = int(
        crawler_runtime_settings.detail_expand_visibility_timeout_ms
    )
    diagnostics: dict[str, object] = {
        "status": DETAIL_EXPANSION_STATUS_ATTEMPTED,
        "attempted": False,
        "limit": int(crawler_runtime_settings.detail_aom_expand_max_interactions),
        "max_elapsed_ms": max_elapsed_ms,
        "buttons_found": 0,
        "clicked_count": 0,
        "expanded_elements": [],
        "interaction_failures": [],
    }
    clicked_count = 0
    expanded_elements: list[str] = []
    interaction_failures: list[str] = []
    accessibility = getattr(page, "accessibility", None)
    snapshot_fn = getattr(accessibility, "snapshot", None)
    if snapshot_fn is None:
        diagnostics["status"] = DETAIL_EXPANSION_STATUS_SKIPPED
        diagnostics["reason"] = "accessibility_unavailable"
        diagnostics["elapsed_ms"] = elapsed_ms(started_at)
        return diagnostics
    diagnostics["attempted"] = True
    try:
        async with asyncio.timeout(_accessibility_snapshot_timeout_seconds()):
            snapshot = await snapshot_fn()
    except (asyncio.TimeoutError, PlaywrightTimeoutError):
        diagnostics["status"] = "snapshot_timeout"
        diagnostics["elapsed_ms"] = elapsed_ms(started_at)
        return diagnostics
    except Exception as exc:
        diagnostics["status"] = "snapshot_failed"
        diagnostics["interaction_failures"] = [f"snapshot_failed:{exc}"]
        diagnostics["elapsed_ms"] = elapsed_ms(started_at)
        return diagnostics
    candidates = accessibility_expand_candidates(
        snapshot,
        surface=surface,
        requested_fields=requested_fields,
    )
    diagnostics["buttons_found"] = len(candidates)
    max_interactions = max(
        0, int(crawler_runtime_settings.detail_aom_expand_max_interactions)
    )
    if len(candidates) > max_interactions:
        keywords = detail_expansion_keywords(surface, requested_fields=requested_fields)
        if keywords:
            prioritized = [
                item
                for item in candidates
                if any(keyword in item[1] for keyword in keywords)
            ]
            prioritized_set = set(prioritized)
            candidates = prioritized + [
                item for item in candidates if item not in prioritized_set
            ]
        diagnostics["skipped_count"] = len(candidates) - max_interactions
    for role, name in candidates[:max_interactions]:
        if max_elapsed_ms is not None and elapsed_ms(started_at) >= int(max_elapsed_ms):
            diagnostics["status"] = DETAIL_EXPANSION_STATUS_TIME_BUDGET_REACHED
            break
        try:
            locator_factory = getattr(page, "get_by_role", None)
            if locator_factory is None:
                interaction_failures.append("get_by_role_unavailable")
                diagnostics["status"] = "locator_unavailable"
                break
            locator = locator_factory(role, name=name, exact=True)
            locator = getattr(locator, "first", locator)
            if hasattr(locator, "count") and await locator.count() == 0:
                continue
            wait_for = getattr(locator, "wait_for", None)
            if callable(wait_for):
                try:
                    await wait_for(state="visible", timeout=visibility_timeout_ms)
                except Exception:
                    visible = False
                else:
                    visible = True
                if not visible:
                    continue
            elif hasattr(locator, "is_visible") and not await locator.is_visible():
                continue
            if hasattr(locator, "is_disabled") and await locator.is_disabled():
                continue
            await locator.click(timeout=click_timeout_ms)
            if int(crawler_runtime_settings.accordion_expand_wait_ms) > 0:
                await page.wait_for_timeout(
                    int(crawler_runtime_settings.accordion_expand_wait_ms)
                )
            clicked_count += 1
            expanded_elements.append(name)
        except Exception as exc:
            interaction_failures.append(str(exc))
    return _finish_expansion_diagnostics(
        diagnostics,
        clicked_count=clicked_count,
        expanded_elements=expanded_elements,
        interaction_failures=interaction_failures,
        started_at=started_at,
        elapsed_ms=elapsed_ms,
    )


def accessibility_expand_candidates_impl(
    snapshot: dict[str, object] | None,
    *,
    surface: str,
    requested_fields: list[str] | None,
    aom_expand_roles: set[str],
    detail_expansion_keywords,
) -> list[tuple[str, str]]:
    requested_keywords = requested_field_tokens(requested_fields)
    keywords = (
        requested_keywords
        if requested_keywords
        else detail_expansion_keywords(surface, requested_fields=requested_fields)
    )
    if not snapshot:
        return []
    results: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def _walk(node: dict[str, object]) -> None:
        role = str(node.get("role") or "").strip().lower()
        name = " ".join(str(node.get("name") or "").split()).strip().lower()
        candidate = (role, name)
        if (
            role in aom_expand_roles
            and name
            and not any(token in name for token in DETAIL_BLOCKED_TOKENS)
            and (not keywords or any(keyword in name for keyword in keywords))
            and candidate not in seen
        ):
            seen.add(candidate)
            results.append(candidate)
        children = node.get("children")
        for child in children if isinstance(children, list) else []:
            if isinstance(child, dict):
                _walk(child)

    _walk(snapshot)
    return results


def requested_field_tokens(requested_fields: list[str] | None) -> tuple[str, ...]:
    tokens: list[str] = []
    seen: set[str] = set()
    for field_name in requested_fields or []:
        exact_key = exact_requested_field_key(str(field_name or ""))
        for token in re.split(r"[_\W]+", exact_key):
            cleaned = str(token or "").strip().lower()
            if len(cleaned) < 3 or cleaned in seen:
                continue
            seen.add(cleaned)
            tokens.append(cleaned)
        normalized = normalize_requested_field(str(field_name or ""))
        if not normalized:
            continue
        aliases = NORMALIZED_REQUESTED_FIELD_ALIASES.get(normalized, [normalized])
        for alias in aliases:
            for token in re.split(r"[_\W]+", str(alias or "")):
                cleaned = str(token or "").strip().lower()
                if len(cleaned) < 3 or cleaned in seen:
                    continue
                seen.add(cleaned)
                tokens.append(cleaned)
    return tuple(tokens)


def detail_expansion_keywords(
    surface: str,
    *,
    requested_fields: list[str] | None = None,
) -> tuple[str, ...]:
    lowered = str(surface or "").strip().lower()
    if "ecommerce" in lowered:
        base_keywords = _DETAIL_EXPAND_KEYWORDS.get("ecommerce", ())
        extended_keywords = DETAIL_EXPAND_KEYWORD_EXTENSIONS.get("ecommerce", ())
    elif "job" in lowered:
        base_keywords = _DETAIL_EXPAND_KEYWORDS.get("job", ())
        extended_keywords = DETAIL_EXPAND_KEYWORD_EXTENSIONS.get("job", ())
    else:
        base_keywords = ()
        extended_keywords = ()
    dynamic_keywords = requested_field_tokens(requested_fields)
    keywords = [*base_keywords]
    if extended_keywords:
        keywords.extend(extended_keywords)
    if dynamic_keywords:
        keywords.extend(dynamic_keywords)
    return tuple(dict.fromkeys(keywords))


def accessibility_expand_candidates(
    snapshot: dict[str, object] | None,
    *,
    surface: str,
    requested_fields: list[str] | None = None,
) -> list[tuple[str, str]]:
    return accessibility_expand_candidates_impl(
        snapshot,
        surface=surface,
        requested_fields=requested_fields,
        aom_expand_roles=set(DETAIL_AOM_EXPAND_ROLES),
        detail_expansion_keywords=detail_expansion_keywords,
    )


async def interactive_label(handle: Any) -> str:
    value = await handle.evaluate(
        """(node) => {
            const pieces = [
                node.innerText,
                node.textContent,
                node.getAttribute('aria-label'),
                node.getAttribute('title'),
                node.getAttribute('data-testid'),
            ];
            return pieces.find((item) => item && item.trim()) || '';
        }"""
    )
    return " ".join(str(value or "").split()).strip().lower()


async def is_actionable_interactive_handle(handle: Any) -> bool:
    state = await handle.evaluate(
        """(node) => {
            if (!(node instanceof HTMLElement) || !node.isConnected) {
                return { actionable: false };
            }
            const style = window.getComputedStyle(node);
            const rect = node.getBoundingClientRect();
            const disabled = Boolean(
                node.hasAttribute('disabled') ||
                node.getAttribute('aria-disabled') === 'true' ||
                node.inert
            );
            const hidden = Boolean(
                node.hidden ||
                node.getAttribute('aria-hidden') === 'true' ||
                style.display === 'none' ||
                style.visibility === 'hidden' ||
                style.pointerEvents === 'none'
            );
            const collapsed = rect.width <= 0 || rect.height <= 0;
            return { actionable: !(disabled || hidden || collapsed) };
        }"""
    )
    if not isinstance(state, dict):
        return False
    return bool(state.get("actionable"))


async def _interactive_handle_attr(handle: Any, attr_name: str) -> str:
    getter = getattr(handle, "get_attribute", None)
    if getter is None:
        return ""
    try:
        value = await getter(attr_name)
    except Exception:
        return ""
    return " ".join(str(value or "").split()).strip().lower()


async def _interactive_handle_tag_name(handle: Any) -> str:
    try:
        value = await handle.evaluate(
            "(node) => node instanceof Element ? node.tagName.toLowerCase() : ''"
        )
    except Exception:
        return ""
    return " ".join(str(value or "").split()).strip().lower()


async def _interactive_handle_is_visible(handle: Any) -> bool:
    checker = getattr(handle, "is_visible", None)
    if checker is None:
        return True
    try:
        return bool(await checker())
    except Exception:
        return False


async def _interactive_handle_context_flags(handle: Any) -> dict[str, bool]:
    try:
        value = await handle.evaluate(
            """(node) => {
                const flags = {
                    insideMain: false,
                    insideHeader: false,
                    insideNav: false,
                    insideFooter: false,
                    insideAside: false,
                };
                let current = node instanceof Element ? node : null;
                while (current) {
                    const tag = (current.tagName || '').toLowerCase();
                    const role = (current.getAttribute('role') || '').toLowerCase();
                    if (tag === 'main' || role === 'main') flags.insideMain = true;
                    if (tag === 'header' || role === 'banner') flags.insideHeader = true;
                    if (tag === 'nav' || role === 'navigation') flags.insideNav = true;
                    if (tag === 'footer' || role === 'contentinfo') flags.insideFooter = true;
                    if (tag === 'aside' || role === 'complementary') flags.insideAside = true;
                    current = current.parentElement;
                }
                return flags;
            }"""
        )
    except Exception:
        return {}
    if not isinstance(value, dict):
        return {}
    return {
        "inside_main": bool(value.get("insideMain")),
        "inside_header": bool(value.get("insideHeader")),
        "inside_nav": bool(value.get("insideNav")),
        "inside_footer": bool(value.get("insideFooter")),
        "inside_aside": bool(value.get("insideAside")),
    }


async def interactive_candidate_snapshot(handle: Any) -> dict[str, object]:
    label = await interactive_label(handle)
    visible = await _interactive_handle_is_visible(handle)
    aria_label = await _interactive_handle_attr(handle, "aria-label")
    title = await _interactive_handle_attr(handle, "title")
    href = await _interactive_handle_attr(handle, "href")
    aria_controls = await _interactive_handle_attr(handle, "aria-controls")
    aria_expanded = await _interactive_handle_attr(handle, "aria-expanded")
    data_qa_action = await _interactive_handle_attr(handle, "data-qa-action")
    data_testid = await _interactive_handle_attr(handle, "data-testid")
    class_name = await _interactive_handle_attr(handle, "class")
    tag_name = await _interactive_handle_tag_name(handle)
    context_flags = await _interactive_handle_context_flags(handle)
    probe = (
        " ".join(
            part
            for part in (label, aria_label, title, data_qa_action, data_testid)
            if str(part or "").strip()
        )
        .strip()
        .lower()
    )
    return {
        "label": label,
        "probe": probe,
        "aria_label": aria_label,
        "title": title,
        "href": href,
        "aria_controls": aria_controls,
        "aria_expanded": aria_expanded,
        "data_qa_action": data_qa_action,
        "data_testid": data_testid,
        "class_name": class_name,
        "tag_name": tag_name,
        **context_flags,
        "visible": visible,
        "actionable": await is_actionable_interactive_handle(handle),
    }


def _elapsed_ms(started_at: float) -> int:
    return max(0, int((time.perf_counter() - started_at) * 1000))


async def expand_all_interactive_elements(
    page: Any,
    *,
    surface: str = "",
    requested_fields: list[str] | None = None,
    checkpoint: Any = None,
    max_elapsed_ms: int | None = None,
) -> dict[str, object]:
    # checkpoint is deprecated API compatibility only; callers should use max_elapsed_ms.
    del checkpoint
    return await expand_all_interactive_elements_impl(
        page,
        surface=surface,
        requested_fields=requested_fields,
        detail_expand_selectors=DETAIL_EXPAND_SELECTORS,
        detail_expansion_keywords=detail_expansion_keywords,
        interactive_candidate_snapshot=interactive_candidate_snapshot,
        elapsed_ms=_elapsed_ms,
        max_elapsed_ms=max_elapsed_ms,
    )


async def expand_interactive_elements_via_accessibility(
    page: Any,
    *,
    surface: str = "",
    requested_fields: list[str] | None = None,
    max_elapsed_ms: int | None = None,
) -> dict[str, object]:
    return await expand_interactive_elements_via_accessibility_impl(
        page,
        surface=surface,
        requested_fields=requested_fields,
        accessibility_expand_candidates=accessibility_expand_candidates,
        detail_expansion_keywords=detail_expansion_keywords,
        elapsed_ms=_elapsed_ms,
        max_elapsed_ms=max_elapsed_ms,
    )


async def expand_detail_content_if_needed(
    page: Any,
    *,
    surface: str,
    readiness_probe: dict[str, object],
    requested_fields: list[str] | None = None,
) -> dict[str, object]:
    from app.services.acquisition.browser_readiness import probe_browser_readiness

    return await expand_detail_content_if_needed_impl(
        page,
        surface=surface,
        readiness_probe=readiness_probe,
        requested_fields=requested_fields,
        expand_all_interactive_elements=expand_all_interactive_elements,
        probe_browser_readiness=probe_browser_readiness,
        expand_interactive_elements_via_accessibility=expand_interactive_elements_via_accessibility,
    )

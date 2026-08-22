import asyncio
import time
from collections.abc import Callable
from typing import Any

from patchright.async_api import TimeoutError as PlaywrightTimeoutError

from app.services.config.extraction_rules import (
    DETAIL_BLOCKED_TOKENS,
    DETAIL_EXPANSION_STATUS_ATTEMPTED,
    DETAIL_EXPANSION_STATUS_EXPANDED,
    DETAIL_EXPANSION_STATUS_INTERACTION_FAILED,
    DETAIL_EXPANSION_STATUS_NO_MATCHES,
    DETAIL_EXPANSION_STATUS_SKIPPED,
    DETAIL_EXPANSION_STATUS_TIME_BUDGET_REACHED,
)
from app.services.config.runtime_settings import crawler_runtime_settings


def accessibility_snapshot_timeout_seconds() -> float:
    try:
        timeout = float(crawler_runtime_settings.browser_accessibility_snapshot_timeout_seconds)
    except (TypeError, ValueError):
        timeout = float(
            crawler_runtime_settings.__class__.model_fields["browser_accessibility_snapshot_timeout_seconds"].default
        )
    return max(0.0, timeout)


def finish_expansion_diagnostics(
    diagnostics: dict[str, object],
    *,
    clicked_count: int,
    expanded_elements: list[str],
    interaction_failures: list[str],
    started_at: float,
    elapsed_ms: Callable[[float], int],
) -> dict[str, object]:
    if diagnostics.get("status") == DETAIL_EXPANSION_STATUS_ATTEMPTED:
        diagnostics["status"] = _completed_expansion_status(clicked_count, interaction_failures)
    diagnostics.update(
        clicked_count=clicked_count,
        expanded_elements=expanded_elements,
        interaction_failures=interaction_failures,
        elapsed_ms=elapsed_ms(started_at),
    )
    return diagnostics


def _completed_expansion_status(clicked_count: int, interaction_failures: list[str]) -> str:
    if clicked_count > 0:
        return DETAIL_EXPANSION_STATUS_EXPANDED
    if interaction_failures:
        return DETAIL_EXPANSION_STATUS_INTERACTION_FAILED
    return DETAIL_EXPANSION_STATUS_NO_MATCHES


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
    diagnostics = _new_accessibility_diagnostics(max_elapsed_ms)
    (
        snapshot,
        failure_status,
        failure_reason,
        failures,
    ) = await _capture_accessibility_snapshot(page)
    diagnostics["attempted"] = failure_reason != "accessibility_unavailable"
    if failure_status:
        diagnostics["status"] = failure_status
        if failure_reason:
            diagnostics["reason"] = failure_reason
        diagnostics["interaction_failures"] = failures
        diagnostics["elapsed_ms"] = elapsed_ms(started_at)
        return diagnostics
    candidates = accessibility_expand_candidates(
        snapshot,
        surface=surface,
        requested_fields=requested_fields,
    )
    diagnostics["buttons_found"] = len(candidates)
    max_interactions = max(0, int(crawler_runtime_settings.detail_aom_expand_max_interactions))
    candidates = _prioritize_candidates(
        candidates,
        max_interactions=max_interactions,
        keywords=detail_expansion_keywords(surface, requested_fields=requested_fields),
        diagnostics=diagnostics,
    )
    clicked_count, expanded_elements, failures = await _expand_candidates(
        page,
        candidates=candidates,
        max_interactions=max_interactions,
        max_elapsed_ms=max_elapsed_ms,
        started_at=started_at,
        elapsed_ms=elapsed_ms,
        diagnostics=diagnostics,
    )
    return finish_expansion_diagnostics(
        diagnostics,
        clicked_count=clicked_count,
        expanded_elements=expanded_elements,
        interaction_failures=failures,
        started_at=started_at,
        elapsed_ms=elapsed_ms,
    )


def _new_accessibility_diagnostics(max_elapsed_ms: int | None) -> dict[str, object]:
    return {
        "status": DETAIL_EXPANSION_STATUS_ATTEMPTED,
        "attempted": False,
        "limit": int(crawler_runtime_settings.detail_aom_expand_max_interactions),
        "max_elapsed_ms": max_elapsed_ms,
        "buttons_found": 0,
        "clicked_count": 0,
        "expanded_elements": [],
        "interaction_failures": [],
    }


async def _capture_accessibility_snapshot(
    page: Any,
) -> tuple[object | None, str | None, str | None, list[str]]:
    snapshot_fn = getattr(getattr(page, "accessibility", None), "snapshot", None)
    if snapshot_fn is None:
        return None, DETAIL_EXPANSION_STATUS_SKIPPED, "accessibility_unavailable", []
    try:
        async with asyncio.timeout(accessibility_snapshot_timeout_seconds()):
            return await snapshot_fn(), None, None, []
    except (asyncio.TimeoutError, PlaywrightTimeoutError):
        return None, "snapshot_timeout", None, []
    except Exception as exc:
        return None, "snapshot_failed", None, [f"snapshot_failed:{exc}"]


def _prioritize_candidates(
    candidates: list[tuple[str, str]],
    *,
    max_interactions: int,
    keywords: tuple[str, ...],
    diagnostics: dict[str, object],
) -> list[tuple[str, str]]:
    if len(candidates) <= max_interactions:
        return candidates
    if keywords:
        prioritized = [item for item in candidates if any(keyword in item[1] for keyword in keywords)]
        prioritized_set = set(prioritized)
        candidates = prioritized + [item for item in candidates if item not in prioritized_set]
    diagnostics["skipped_count"] = len(candidates) - max_interactions
    return candidates


async def _expand_candidates(
    page: Any,
    *,
    candidates: list[tuple[str, str]],
    max_interactions: int,
    max_elapsed_ms: int | None,
    started_at: float,
    elapsed_ms,
    diagnostics: dict[str, object],
) -> tuple[int, list[str], list[str]]:
    clicked_count = 0
    expanded_elements: list[str] = []
    failures: list[str] = []
    for role, name in candidates[:max_interactions]:
        if _time_budget_reached(max_elapsed_ms, elapsed_ms(started_at)):
            diagnostics["status"] = DETAIL_EXPANSION_STATUS_TIME_BUDGET_REACHED
            break
        outcome = await _expand_accessibility_candidate(page, role=role, name=name)
        if outcome == "clicked":
            clicked_count += 1
            expanded_elements.append(name)
        elif outcome == "locator_unavailable":
            failures.append("get_by_role_unavailable")
            diagnostics["status"] = outcome
            break
        elif outcome.startswith("failed:"):
            failures.append(outcome.removeprefix("failed:"))
    return clicked_count, expanded_elements, failures


def _time_budget_reached(max_elapsed_ms: int | None, elapsed_ms: int) -> bool:
    return max_elapsed_ms is not None and elapsed_ms >= int(max_elapsed_ms)


async def _expand_accessibility_candidate(page: Any, *, role: str, name: str) -> str:
    locator_factory = getattr(page, "get_by_role", None)
    if locator_factory is None:
        return "locator_unavailable"
    try:
        locator = locator_factory(role, name=name, exact=True)
        locator = getattr(locator, "first", locator)
        if hasattr(locator, "count") and await locator.count() == 0:
            return "skipped"
        if not await _locator_is_visible(locator):
            return "skipped"
        if hasattr(locator, "is_disabled") and await locator.is_disabled():
            return "skipped"
        await locator.click(timeout=int(crawler_runtime_settings.detail_expand_click_timeout_ms))
        wait_ms = int(crawler_runtime_settings.accordion_expand_wait_ms)
        if wait_ms > 0:
            await page.wait_for_timeout(wait_ms)
        return "clicked"
    except Exception as exc:
        return f"failed:{exc}"


async def _locator_is_visible(locator: Any) -> bool:
    wait_for = getattr(locator, "wait_for", None)
    if callable(wait_for):
        try:
            await wait_for(
                state="visible",
                timeout=int(crawler_runtime_settings.detail_expand_visibility_timeout_ms),
            )
        except Exception:
            return False
        return True
    if hasattr(locator, "is_visible"):
        return bool(await locator.is_visible())
    return True


def accessibility_expand_candidates_impl(
    snapshot: dict[str, object] | None,
    *,
    surface: str,
    requested_fields: list[str] | None,
    aom_expand_roles: set[str],
    detail_expansion_keywords,
    requested_field_tokens,
) -> list[tuple[str, str]]:
    requested_keywords = requested_field_tokens(requested_fields)
    keywords = requested_keywords or detail_expansion_keywords(surface, requested_fields=requested_fields)
    if not snapshot:
        return []
    results: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def walk(node: dict[str, object]) -> None:
        role = str(node.get("role") or "").strip().lower()
        name = " ".join(str(node.get("name") or "").split()).strip().lower()
        candidate = (role, name)
        if _is_accessibility_expand_candidate(
            candidate,
            roles=aom_expand_roles,
            keywords=keywords,
            seen=seen,
        ):
            seen.add(candidate)
            results.append(candidate)
        children = node.get("children")
        for child in children if isinstance(children, list) else []:
            if isinstance(child, dict):
                walk(child)

    walk(snapshot)
    return results


def _is_accessibility_expand_candidate(
    candidate: tuple[str, str],
    *,
    roles: set[str],
    keywords: tuple[str, ...],
    seen: set[tuple[str, str]],
) -> bool:
    role, name = candidate
    return (
        role in roles
        and bool(name)
        and not any(token in name for token in DETAIL_BLOCKED_TOKENS)
        and (not keywords or any(keyword in name for keyword in keywords))
        and candidate not in seen
    )


async def interactive_candidate_snapshot(handle: Any) -> dict[str, object]:
    label = await interactive_label(handle)
    attributes = {
        name: await _interactive_handle_attr(handle, html_name)
        for name, html_name in (
            ("aria_label", "aria-label"),
            ("title", "title"),
            ("href", "href"),
            ("aria_controls", "aria-controls"),
            ("aria_expanded", "aria-expanded"),
            ("data_qa_action", "data-qa-action"),
            ("data_testid", "data-testid"),
            ("class_name", "class"),
        )
    }
    probe = " ".join(
        part
        for part in (
            label,
            attributes["aria_label"],
            attributes["title"],
            attributes["data_qa_action"],
            attributes["data_testid"],
        )
        if part
    ).lower()
    return {
        "label": label,
        "probe": probe,
        **attributes,
        "tag_name": await _interactive_handle_tag_name(handle),
        **(await _interactive_handle_context_flags(handle)),
        "visible": await _interactive_handle_is_visible(handle),
        "actionable": await is_actionable_interactive_handle(handle),
    }


async def interactive_label(handle: Any) -> str:
    value = await handle.evaluate(
        """(node) => {
            const pieces = [node.innerText, node.textContent, node.getAttribute('aria-label'),
                node.getAttribute('title'), node.getAttribute('data-testid')];
            return pieces.find((item) => item && item.trim()) || '';
        }"""
    )
    return " ".join(str(value or "").split()).strip().lower()


async def is_actionable_interactive_handle(handle: Any) -> bool:
    state = await handle.evaluate(
        """(node) => {
            if (!(node instanceof HTMLElement) || !node.isConnected) return { actionable: false };
            const style = window.getComputedStyle(node);
            const rect = node.getBoundingClientRect();
            const disabled = Boolean(node.hasAttribute('disabled') ||
                node.getAttribute('aria-disabled') === 'true' || node.inert);
            const hidden = Boolean(node.hidden || node.getAttribute('aria-hidden') === 'true' ||
                style.display === 'none' || style.visibility === 'hidden' ||
                style.pointerEvents === 'none');
            return { actionable: !(disabled || hidden || rect.width <= 0 || rect.height <= 0) };
        }"""
    )
    return isinstance(state, dict) and bool(state.get("actionable"))


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
        value = await handle.evaluate("(node) => node instanceof Element ? node.tagName.toLowerCase() : ''")
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


async def _interactive_handle_context_flags(handle: Any) -> dict[str, object]:
    try:
        value = await handle.evaluate(
            """(node) => {
                const flags = {elementIdentity: '', insideMain: false, insideHeader: false,
                    insideNav: false, insideFooter: false, insideAside: false};
                const store = globalThis.__invoroDetailExpansionCandidates ??=
                    {nodes: new WeakMap(), nextId: 1};
                let identity = store.nodes.get(node);
                if (!identity) { identity = `node-${store.nextId++}`; store.nodes.set(node, identity); }
                flags.elementIdentity = identity;
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
        "element_identity": str(value.get("elementIdentity") or ""),
        "inside_main": bool(value.get("insideMain")),
        "inside_header": bool(value.get("insideHeader")),
        "inside_nav": bool(value.get("insideNav")),
        "inside_footer": bool(value.get("insideFooter")),
        "inside_aside": bool(value.get("insideAside")),
    }

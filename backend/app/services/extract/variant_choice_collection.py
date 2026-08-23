from __future__ import annotations

__all__ = (
    "iter_variant_choice_groups",
    "iter_variant_select_groups",
    "variant_dom_cues_present",
    "variant_choice_container_for_input",
)

import re
from typing import Any

from app.services.config.extraction_rules import (
    VARIANT_CHOICE_GROUP_MAX,
    VARIANT_CHOICE_INPUT_SCAN_LIMIT,
    VARIANT_CHOICE_GROUP_SELECTOR,
    VARIANT_CHOICE_CONTAINER_OPTION_LIMIT,
    VARIANT_MATCHING_INPUT_LIMIT,
    VARIANT_NARROW_BUTTON_SCAN_LIMIT,
    VARIANT_QUANTITY_ATTR_TOKENS,
    VARIANT_SELECT_GROUP_MAX,
    VARIANT_SELECT_GROUP_SELECTOR,
    VARIANT_SWATCH_BUTTON_LIMIT,
    VARIANT_SWATCH_BUTTON_SELECTOR,
    VARIANT_SWATCH_PARENT_DEPTH,
)
from app.services.config.surface_hints import detail_path_hints
from app.services.extract.variant_axis import (
    normalized_variant_axis_key,
    variant_axis_allowed_single_tokens,
)
from app.services.extract.variant_choice_traversal import (
    anchor_node_has_variant_signal,
    choice_option_texts,
    descendant_variant_choice_inputs,
    infer_variant_group_name_from_values,
    node_supports_value_only_axis_inference,
    resolve_variant_group_name,
    variant_choice_container_is_overbroad,
)
from app.services.extract.variant_dom_cues import (
    select_variant_nodes,
    variant_node_in_noise_context,
)
from app.services.extract.variant_option_value import select_option_values_are_noise

_ALNUM_SPLIT_PATTERN = r"[^a-z0-9]+"
_variant_quantity_attr_tokens = frozenset(
    str(token).strip().lower()
    for token in tuple(VARIANT_QUANTITY_ATTR_TOKENS or ())
    if str(token).strip()
)
_variant_anchor_href_markers = tuple(
    str(marker or "").strip().casefold()
    for marker in (
        *detail_path_hints("ecommerce_detail"),
        "?piid=",
        "&piid=",
        "variant=",
    )
    if str(marker or "").strip()
)
_VARIANT_CHOICE_CACHE_ATTR = "_crawler_variant_choice_cache"


def _variant_choice_cache(soup: Any) -> dict[object, object]:
    cache = getattr(soup, _VARIANT_CHOICE_CACHE_ATTR, None)
    if isinstance(cache, dict):
        return cache
    cache = {}
    try:
        setattr(soup, _VARIANT_CHOICE_CACHE_ATTR, cache)
    except Exception:
        return {}
    return cache


def variant_dom_cues_present(soup: Any) -> bool:
    cache = _variant_choice_cache(soup)
    cache_key = "variant_dom_cues_present"
    if cache_key not in cache:
        cache[cache_key] = bool(
            iter_variant_select_groups(soup) or iter_variant_choice_groups(soup)
        )
    return bool(cache[cache_key])


def _variant_group_has_multiple_options(node: Any) -> bool:
    if not hasattr(node, "select"):
        return False
    tag_name = str(getattr(node, "name", "") or "").strip().lower()
    if tag_name in {"button", "a", "img", "input", "option"}:
        return False
    option_nodes = node.select(
        "button, a[href], [role='radio'], [role='option'], input[type='radio'], "
        "input[type='checkbox'], [data-value], [data-option-value], "
        "[data-selected], [aria-selected], [data-state], [data-testid='swatch' i], "
        "[data-testid*='swatch-option' i], [role='button'][aria-label], option, "
        "a[class*='swatch' i][title], a[class*='swatch' i][aria-label]"
    )
    return len(option_nodes) >= 2


def _node_identity(node: Any) -> object:
    """Return stable DOM identity even when the parser recreates wrappers."""
    return getattr(node, "node", node)


def _select_is_quantity_node(node: Any) -> bool:
    """Return True when the <select> element is a quantity picker."""
    if not hasattr(node, "get"):
        return False
    for attr_name in ("name", "id", "aria-label", "data-testid"):
        value = str(node.get(attr_name) or "").strip().lower()
        if not value:
            continue
        tokens = re.split(_ALNUM_SPLIT_PATTERN, value)
        if any(t in _variant_quantity_attr_tokens for t in tokens):
            return True
    return False


def iter_variant_select_groups(soup: Any) -> list[Any]:
    cache = _variant_choice_cache(soup)
    cache_key = "variant_select_groups"
    cached = cache.get(cache_key)
    if isinstance(cached, tuple):
        return list(cached)
    groups: list[Any] = []
    seen_nodes: set[object] = set()
    for select in select_variant_nodes(soup, VARIANT_SELECT_GROUP_SELECTOR):
        if _select_is_quantity_node(select):
            continue
        if select_option_values_are_noise(select):
            continue
        if resolve_variant_group_name(select):
            groups.append(select)
            seen_nodes.add(_node_identity(select))
        if len(groups) >= int(VARIANT_SELECT_GROUP_MAX):
            break
    if len(groups) >= int(VARIANT_SELECT_GROUP_MAX):
        cache[cache_key] = tuple(groups)
        return groups
    for select in select_variant_nodes(soup, "select"):
        if _node_identity(select) in seen_nodes:
            continue
        if _select_is_quantity_node(select):
            continue
        if select_option_values_are_noise(select):
            continue
        if resolve_variant_group_name(select):
            groups.append(select)
            seen_nodes.add(_node_identity(select))
        if len(groups) >= int(VARIANT_SELECT_GROUP_MAX):
            break
    cache[cache_key] = tuple(groups)
    return groups


def _append_choice_group(groups: list[Any], seen: set[object], node: Any) -> bool:
    node_identity = _node_identity(node)
    if node_identity in seen:
        return False
    groups.append(node)
    seen.add(node_identity)
    return len(groups) >= int(VARIANT_CHOICE_GROUP_MAX)


def _add_labeled_role_groups(soup: Any, groups: list[Any], seen: set[object]) -> bool:
    for container in soup.select("[role='group'][aria-label]"):
        name = resolve_variant_group_name(container)
        axis = normalized_variant_axis_key(name)
        if variant_node_in_noise_context(container) and axis not in {"color", "size"}:
            continue
        if name and _variant_group_has_multiple_options(container):
            if _append_choice_group(groups, seen, container):
                return True
    return False


def _add_configured_choice_groups(
    soup: Any, groups: list[Any], seen: set[object]
) -> bool:
    for container in select_variant_nodes(soup, VARIANT_CHOICE_GROUP_SELECTOR):
        if _node_identity(container) in seen or variant_choice_container_is_overbroad(
            container
        ):
            continue
        name = resolve_variant_group_name(container)
        inferred = (
            infer_variant_group_name_from_values(choice_option_texts(container))
            if node_supports_value_only_axis_inference(container)
            else ""
        )
        if _variant_group_has_multiple_options(container) and (name or inferred):
            if _append_choice_group(groups, seen, container):
                return True
    return False


def _add_input_choice_groups(soup: Any, groups: list[Any], seen: set[object]) -> bool:
    nodes = soup.select("input[type='radio'], input[type='checkbox']")
    for node in nodes[: int(VARIANT_CHOICE_INPUT_SCAN_LIMIT)]:
        if variant_node_in_noise_context(node):
            continue
        candidate = variant_choice_container_for_input(node)
        if candidate is None or variant_node_in_noise_context(candidate):
            continue
        if _append_choice_group(groups, seen, candidate):
            return True
    return False


def _add_button_choice_groups(soup: Any, groups: list[Any], seen: set[object]) -> bool:
    selector = "button[data-variant], button.variant-option, button.size-option, button.color-option"
    nodes = soup.select(selector)[: int(VARIANT_NARROW_BUTTON_SCAN_LIMIT)]
    parent_counts = _narrow_button_parent_counts(nodes)
    for node in nodes:
        if variant_node_in_noise_context(node):
            continue
        container = _narrow_button_container(node, seen, parent_counts)
        if container is not None and _append_choice_group(groups, seen, container):
            return True
    return False


def _narrow_button_parent_counts(nodes: list[Any]) -> dict[object, int]:
    counts: dict[object, int] = {}
    for node in nodes:
        parent = getattr(node, "parent", None)
        depth = 0
        while parent is not None and depth < int(VARIANT_SWATCH_PARENT_DEPTH):
            identity = _node_identity(parent)
            counts[identity] = counts.get(identity, 0) + 1
            parent = getattr(parent, "parent", None)
            depth += 1
    return counts


def _narrow_button_container(
    button: Any,
    seen: set[object],
    parent_counts: dict[object, int],
) -> Any | None:
    parent = getattr(button, "parent", None)
    depth = 0
    while parent is not None and depth < int(VARIANT_SWATCH_PARENT_DEPTH):
        parent_identity = _node_identity(parent)
        if parent_identity in seen:
            return None
        if parent_counts.get(
            parent_identity, 0
        ) >= 2 and not variant_node_in_noise_context(parent):
            tag, role, classes = _swatch_parent_metadata(parent)
            if _swatch_parent_can_contain_group(
                tag, role, classes
            ) and _swatch_parent_has_axis(tag, role, classes, parent):
                return parent
        parent = getattr(parent, "parent", None)
        depth += 1
    return None


def _ordered_swatch_buttons(soup: Any) -> list[Any]:
    priority = soup.select(
        "[data-testid='swatch' i], [data-testid*='swatch-option' i], [role='button'][aria-label]"
    )
    priority_nodes = {_node_identity(node) for node in priority}
    buttons = [
        *priority,
        *(
            node
            for node in soup.select(VARIANT_SWATCH_BUTTON_SELECTOR)
            if _node_identity(node) not in priority_nodes
        ),
    ]
    return buttons[: int(VARIANT_SWATCH_BUTTON_LIMIT)]


def _swatch_parent_metadata(parent: Any) -> tuple[str, str, str]:
    tag = str(getattr(parent, "name", "") or "").lower()
    role = str(parent.get("role") or "").lower() if hasattr(parent, "get") else ""
    classes = parent.get("class") if hasattr(parent, "get") else None
    class_probe = (
        " ".join(str(value) for value in classes)
        if isinstance(classes, list)
        else str(classes or "")
    ).lower()
    return tag, role, class_probe


def _swatch_parent_can_contain_group(tag: str, role: str, classes: str) -> bool:
    container_tags = {"div", "section", "fieldset", "ul", "ol", "nav", "form", "li"}
    hints = ("swatch", "variant", "color", "size", "option")
    return (
        tag in container_tags
        or role == "radiogroup"
        or any(hint in classes for hint in hints)
    )


def _swatch_parent_has_axis(tag: str, role: str, classes: str, parent: Any) -> bool:
    hints = (
        "color",
        "size",
        "swatch",
        "variant",
        "option",
        *variant_axis_allowed_single_tokens,
    )
    return (
        role == "radiogroup"
        or tag in {"fieldset", "ul", "ol"}
        or any(hint in classes for hint in hints)
        or bool(resolve_variant_group_name(parent))
    )


def _swatch_container_for_button(
    button: Any, seen: set[object], cache: dict[object, list[Any]]
) -> Any | None:
    if str(
        getattr(button, "name", "") or ""
    ).strip().lower() == "a" and not anchor_node_has_variant_signal(button):
        return None
    parent = getattr(button, "parent", None)
    depth = 0
    while parent is not None and depth < int(VARIANT_SWATCH_PARENT_DEPTH):
        if not hasattr(parent, "select") or variant_node_in_noise_context(parent):
            parent = getattr(parent, "parent", None)
            depth += 1
            continue
        parent_identity = _node_identity(parent)
        if parent_identity in seen:
            return None
        tag, role, classes = _swatch_parent_metadata(parent)
        if not _swatch_parent_can_contain_group(tag, role, classes):
            parent = getattr(parent, "parent", None)
            depth += 1
            continue
        siblings = cache.setdefault(
            parent_identity, parent.select(VARIANT_SWATCH_BUTTON_SELECTOR)
        )
        if len(siblings) >= 2:
            if _swatch_parent_has_axis(
                tag, role, classes, parent
            ) and _variant_group_has_multiple_options(parent):
                return parent
            return None
        parent = getattr(parent, "parent", None)
        depth += 1
    return None


def _add_swatch_choice_groups(soup: Any, groups: list[Any], seen: set[object]) -> None:
    cache: dict[object, list[Any]] = {}
    for button in _ordered_swatch_buttons(soup):
        candidate = _swatch_container_for_button(button, seen, cache)
        if candidate is not None and _append_choice_group(groups, seen, candidate):
            return


def iter_variant_choice_groups(soup: Any) -> list[Any]:
    """Find variant groups in deterministic discovery order."""
    cache = _variant_choice_cache(soup)
    cache_key = "variant_choice_groups"
    cached = cache.get(cache_key)
    if isinstance(cached, tuple):
        return list(cached)
    groups: list[Any] = []
    seen: set[object] = set()
    stages = (
        _add_labeled_role_groups,
        _add_configured_choice_groups,
        _add_input_choice_groups,
        _add_button_choice_groups,
    )
    for stage in stages:
        if stage(soup, groups, seen):
            break
    else:
        _add_swatch_choice_groups(soup, groups, seen)
    cache[cache_key] = tuple(groups)
    return groups


def variant_choice_container_for_input(
    node: Any, *, axis_name: str | None = None
) -> Any | None:
    if axis_name is None:
        axis_name = resolve_variant_group_name(node)
    input_type = (
        str(node.get("type") or "").strip().lower() if hasattr(node, "get") else ""
    )
    parent = getattr(node, "parent", None)
    depth = 0
    while parent is not None and depth < int(VARIANT_SWATCH_PARENT_DEPTH):
        if not _input_parent_is_eligible(parent):
            parent = getattr(parent, "parent", None)
            depth += 1
            continue
        if _input_parent_is_choice_container(parent, axis_name, input_type):
            return parent
        parent = getattr(parent, "parent", None)
        depth += 1
    return None


def _input_parent_is_eligible(parent: Any) -> bool:
    return (
        hasattr(parent, "find_all")
        and not variant_node_in_noise_context(parent)
        and not variant_choice_container_is_overbroad(parent)
    )


def _input_parent_axis_metadata(parent: Any) -> tuple[str, bool, str]:
    class_attr = parent.get("class") if hasattr(parent, "get") else None
    class_probe = (
        " ".join(str(value) for value in class_attr)
        if isinstance(class_attr, list)
        else str(class_attr or "")
    ).lower()
    tag_name = str(getattr(parent, "name", "") or "").lower()
    role = str(parent.get("role") or "").lower() if hasattr(parent, "get") else ""
    has_hint = (
        role == "radiogroup"
        or tag_name in {"fieldset", "ul", "ol"}
        or any(
            hint in class_probe
            for hint in (
                "color",
                "size",
                "swatch",
                "variant",
                *variant_axis_allowed_single_tokens,
            )
        )
    )
    return tag_name, has_hint, "" if has_hint else resolve_variant_group_name(parent)


def _input_parent_is_choice_container(
    parent: Any, axis_name: str | None, input_type: str
) -> bool:
    matching = _matching_parent_inputs(parent, axis_name)
    tag_name, has_hint, group_name = _input_parent_axis_metadata(parent)
    allowed_single_axes = {"color", *variant_axis_allowed_single_tokens}
    if len(matching) == 1 and axis_name in allowed_single_axes and has_hint:
        return True
    if len(matching) < 2:
        return False
    if input_type == "checkbox" and not any((axis_name, has_hint, group_name)):
        return False
    inferred = _input_parent_inferred_axis(parent, input_type)
    if any((has_hint, group_name, inferred)):
        return True
    return bool(
        axis_name
        and len(matching) <= int(VARIANT_MATCHING_INPUT_LIMIT)
        and tag_name in {"div", "section"}
    )


def _matching_parent_inputs(parent: Any, axis_name: str | None) -> list[Any]:
    inputs = descendant_variant_choice_inputs(
        parent,
        limit=max(
            int(VARIANT_CHOICE_CONTAINER_OPTION_LIMIT),
            int(VARIANT_MATCHING_INPUT_LIMIT),
        ),
    )
    return [
        item
        for item in inputs
        if not axis_name or resolve_variant_group_name(item) == axis_name
    ]


def _input_parent_inferred_axis(parent: Any, input_type: str) -> str:
    if input_type != "checkbox" and node_supports_value_only_axis_inference(parent):
        return infer_variant_group_name_from_values(choice_option_texts(parent))
    return ""

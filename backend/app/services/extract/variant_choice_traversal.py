from __future__ import annotations

__all__ = (
    "infer_variant_group_name",
    "variant_dom_cues_present",
    "variant_input_label",
    "resolve_variant_group_name",
    "infer_variant_group_name_from_values",
    "iter_variant_select_groups",
    "iter_variant_choice_groups",
)

import re
from collections.abc import Sequence
from typing import Any

from app.services.config.extraction_rules import (
    VARIANT_AXIS_EXCLUDED_SINGLE_TOKENS,
    VARIANT_CHOICE_GROUP_MAX,
    VARIANT_CHOICE_GROUP_SELECTOR,
    VARIANT_CHOICE_CONTAINER_GROUP_LIMIT,
    VARIANT_CHOICE_CONTAINER_MIN_DISTINCT_NAMES,
    VARIANT_CHOICE_CONTAINER_OPTION_LIMIT,
    VARIANT_CHOICE_CONTAINER_SELECT_LIMIT,
    VARIANT_CHOICE_OPTION_LIMIT,
    VARIANT_CHOICE_OPTION_SELECTOR,
    VARIANT_COMPONENT_TYPE_ATTRIBUTES,
    VARIANT_COMPONENT_TYPE_AXIS_NAME,
    VARIANT_COLOR_AXIS_TOKENS,
    VARIANT_DESCENDANT_SCAN_LIMIT,
    VARIANT_GROUP_ATTR_NOISE_PATTERNS,
    VARIANT_GROUP_ATTR_NOISE_TOKENS,
    VARIANT_MATCHING_INPUT_LIMIT,
    VARIANT_QUANTITY_ATTR_TOKENS,
    VARIANT_SELECT_GROUP_MAX,
    VARIANT_SIZE_AXIS_TOKENS,
    VARIANT_SIZE_VALUE_PATTERNS,
    VARIANT_SELECT_GROUP_SELECTOR,
    VARIANT_SIBLING_SEARCH_DEPTH,
    VARIANT_SWATCH_BUTTON_LIMIT,
    VARIANT_SWATCH_BUTTON_SELECTOR,
    VARIANT_SWATCH_PARENT_DEPTH,
)
from app.services.config.surface_hints import detail_path_hints
from app.services.extract.variant_dom_cues import (
    select_variant_nodes as _select_variant_nodes,
    variant_context_noise_tokens as _variant_context_noise_tokens,
    variant_node_in_noise_context,
)
from app.services.extract.variant_axis import (
    normalized_variant_axis_key,
    resolve_machine_variant_group_name as _resolve_machine_variant_group_name,
    resolve_visible_variant_group_name as _resolve_visible_variant_group_name,
    semantic_group_label_from_text as _semantic_group_label_from_text,
    variant_axis_allowed_single_tokens as _variant_axis_allowed_single_tokens,
)
from app.services.extract.variant_option_value import (
    is_sequential_integer_run as _is_sequential_integer_run,
    select_option_texts_from_node as _select_option_texts,
    select_option_values_are_noise as _select_option_values_are_noise,
    value_looks_like_color as _value_looks_like_color,
)
from app.services.dom.query import safe_find
from app.services.shared.field_coerce import clean_text, text_or_none
from app.services.shared.regex_patterns import compile_regex_patterns

_ALNUM_SPLIT_PATTERN = r"[^a-z0-9]+"

_variant_group_attr_noise_tokens = frozenset(str(token).strip().lower() for token in tuple(VARIANT_GROUP_ATTR_NOISE_TOKENS or ()) if str(token).strip())
_variant_group_attr_noise_patterns = compile_regex_patterns(VARIANT_GROUP_ATTR_NOISE_PATTERNS or ())
_variant_size_value_patterns = compile_regex_patterns(VARIANT_SIZE_VALUE_PATTERNS or ())
_variant_quantity_attr_tokens = frozenset(str(token).strip().lower() for token in tuple(VARIANT_QUANTITY_ATTR_TOKENS or ()) if str(token).strip())
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

def infer_variant_group_name(node: Any) -> str:
    if not hasattr(node, "get"):
        return ""
    parts: list[str] = []
    for attr_name in (
        "data-option-name",
        "data-testid",
        "data-qa-action",
        "id",
        "name",
        "class",
    ):
        value = node.get(attr_name)
        if isinstance(value, list):
            parts.extend(str(item) for item in value if item)
        elif value not in (None, "", [], {}):
            parts.append(str(value))
    probe = " ".join(parts).replace("_", " ").replace("-", " ").lower()
    probe_tokens = frozenset(token for token in re.split(_ALNUM_SPLIT_PATTERN, probe) if token)
    if VARIANT_COLOR_AXIS_TOKENS & probe_tokens:
        return "color"
    if VARIANT_SIZE_AXIS_TOKENS & probe_tokens:
        return "size"
    for token in probe_tokens:
        if token in _variant_axis_allowed_single_tokens and token not in VARIANT_AXIS_EXCLUDED_SINGLE_TOKENS:
            return token
    return ""
def variant_dom_cues_present(soup: Any) -> bool:
    cache = _variant_choice_cache(soup)
    cache_key = "variant_dom_cues_present"
    if cache_key in cache:
        return bool(cache[cache_key])
    result = bool(iter_variant_select_groups(soup) or iter_variant_choice_groups(soup))
    cache[cache_key] = result
    return result

def _choice_option_text(node: Any, *, parent: Any | None = None) -> str:
    if node is None or not hasattr(node, "get"):
        return ""
    label_text = ""
    if str(getattr(node, "name", "") or "").strip().lower() in {"input", "button"}:
        label = variant_input_label(parent or node, node)
        if label is not None:
            label_text = clean_text(label.get_text(" ", strip=True))
    node_text = clean_text(node.get_text(" ", strip=True)) if hasattr(node, "get_text") else ""
    attribute_value = next(
        (
            node.get(attr)
            for attr in (
                "data-attr-displayvalue",
                "data-displayvalue",
                "data-display-value",
                "data-swatch-sr",
            )
            if node.get(attr) not in (None, "", [], {})
        ),
        None,
    )
    fallback_value = next(
        (node.get(attr) for attr in ("data-value", "data-option-value", "aria-label", "value") if node.get(attr) not in (None, "", [], {})),
        None,
    )
    return clean_text(attribute_value or label_text or fallback_value or node_text)

def variant_input_label(container: Any, input_node: Any) -> Any | None:
    input_id = text_or_none(input_node.get("id")) if hasattr(input_node, "get") else None
    if input_id:
        label = safe_find(container, "label", attrs={"for": input_id})
        if label is not None:
            return label
    if hasattr(input_node, "find_parent"):
        label = input_node.find_parent("label")
        if label is not None:
            return label
    sibling = getattr(input_node, "next_sibling", None)
    while sibling is not None:
        if getattr(sibling, "name", None) == "label":
            return sibling
        sibling = getattr(sibling, "next_sibling", None)
    return None

def _choice_option_texts(node: Any) -> list[str]:
    if not hasattr(node, "select"):
        return []
    values: list[str] = []
    for option in node.select(VARIANT_CHOICE_OPTION_SELECTOR)[: int(VARIANT_CHOICE_OPTION_LIMIT)]:
        value = _choice_option_text(option, parent=node)
        if value:
            values.append(value)
    return values

def _descendant_variant_group_name(node: Any) -> str:
    if not hasattr(node, "select"):
        return ""
    return _direct_descendant_group_name(node) or _label_descendant_group_name(node) or _machine_descendant_group_name(node)

def _direct_descendant_group_name(node: Any) -> str:
    children = node.find_all(
        ["legend", "label", "h1", "h2", "h3", "h4", "h5", "h6", "div", "span"],
        limit=int(VARIANT_DESCENDANT_SCAN_LIMIT),
        recursive=False,
    )
    for child in children:
        if _descendant_group_label_is_control(child):
            continue
        raw_value = clean_text(child.get_text(" ", strip=True))
        if raw_value and len(raw_value.split()) <= 4:
            if resolved := _resolve_visible_variant_group_name(raw_value):
                return resolved
    return ""

def _descendant_group_label_is_control(child: Any) -> bool:
    tag = str(getattr(child, "name", "") or "").strip().lower()
    if tag in {"a", "button", "input", "option"}:
        return True
    if hasattr(child, "get"):
        role = str(child.get("role") or "").strip().lower()
        selected = any(child.get(attr) not in (None, "", [], {}) for attr in ("data-selected", "aria-selected"))
        if role in {"radio", "option"} or selected:
            return True
    return bool(
        hasattr(child, "select")
        and child.select("a[href], button, input[type='radio'], input[type='checkbox'], [role='radio'], [role='option'], [data-selected], [aria-selected]")
    )

def _label_descendant_group_name(node: Any) -> str:
    for child in node.select("label")[: int(VARIANT_DESCENDANT_SCAN_LIMIT)]:
        sr_only = child.select_one(".sr-only, .visually-hidden")
        raw_value = sr_only.get_text(" ", strip=True) if sr_only is not None else child.get_text(" ", strip=True)
        if resolved := _resolve_visible_variant_group_name(raw_value):
            return resolved
    return ""

def _machine_descendant_group_name(node: Any) -> str:
    children = node.select("[data-option-name], input[type='radio'], input[type='checkbox'], button")
    for child in children[: int(VARIANT_DESCENDANT_SCAN_LIMIT)]:
        for attr in ("data-option-name", "name", "id", "data-testid", "data-qa-action"):
            value = child.get(attr)
            if value not in (None, "", [], {}):
                if resolved := _resolve_machine_variant_group_name(value):
                    return resolved
    return ""

def _node_supports_value_only_axis_inference(node: Any) -> bool:
    if not hasattr(node, "find"):
        return False
    if node.find("select") is not None:
        return True
    if node.find(attrs={"data-option-name": True}) is not None:
        return True
    if node.find("a", href=True) is not None:
        return True
    for input_type in ("radio", "checkbox"):
        if node.find("input", attrs={"type": input_type}) is not None:
            return True
    return False

def _descendant_variant_choice_inputs(node: Any, *, limit: int) -> list[Any]:
    if not hasattr(node, "find_all"):
        return []
    normalized_limit = max(1, int(limit))
    inputs: list[Any] = []
    for child in node.find_all(["input", "button"], limit=normalized_limit):
        tag_name = str(getattr(child, "name", "") or "").strip().lower()
        if tag_name == "button":
            inputs.append(child)
            continue
        input_type = str(child.get("type") or "").strip().lower() if hasattr(child, "get") else ""
        if input_type in {"radio", "checkbox"}:
            inputs.append(child)
    remaining = normalized_limit - len(inputs)
    if remaining <= 0:
        return inputs
    for child in node.find_all("a", attrs={"href": True}, limit=remaining):
        if _anchor_node_has_variant_signal(child):
            inputs.append(child)
    return inputs

def _anchor_node_has_variant_signal(node: Any) -> bool:
    href = text_or_none(node.get("href")) if hasattr(node, "get") else None
    if not href:
        return False
    href_lower = href.casefold()
    if any(marker in href_lower for marker in _variant_anchor_href_markers):
        return True
    if any(node.get(attr) not in (None, "", [], {}) for attr in ("data-selected", "aria-current", "aria-pressed")):
        return True
    probe_parts: list[str] = []
    for attr_name in ("class", "id", "data-testid"):
        value = node.get(attr_name) if hasattr(node, "get") else None
        if isinstance(value, list):
            probe_parts.extend(str(item) for item in value if item)
        elif value not in (None, "", [], {}):
            probe_parts.append(str(value))
    probe = clean_text(" ".join(probe_parts)).lower()
    return any(token in probe for token in ("selected", "current", "checked", "variant", "swatch", "option"))

def _descendant_group_label_nodes(node: Any, *, limit: int) -> list[Any]:
    if not hasattr(node, "find_all"):
        return []
    normalized_limit = max(1, int(limit))
    groups: list[Any] = []
    seen_ids: set[int] = set()
    for child in node.find_all(attrs={"role": "radiogroup"}, limit=normalized_limit):
        groups.append(child)
        seen_ids.add(id(child))
    if len(groups) >= normalized_limit:
        return groups
    remaining = normalized_limit - len(groups)
    if remaining <= 0:
        return groups
    for child in node.find_all(attrs={"aria-label": True}, limit=remaining):
        child_id = id(child)
        if child_id in seen_ids:
            continue
        groups.append(child)
        seen_ids.add(child_id)
        if len(groups) >= normalized_limit:
            break
    return groups

def _normalized_group_name(value: object) -> str:
    text = text_or_none(value)
    return normalized_variant_axis_key(text) or clean_text(text).casefold() if text else ""

def _input_group_names(node: Any) -> set[str]:
    names: set[str] = set()
    inputs = _descendant_variant_choice_inputs(node, limit=int(VARIANT_CHOICE_CONTAINER_OPTION_LIMIT))
    for child in inputs:
        raw = child.get("name") or child.get("data-option-name") or child.get("data-testid")
        if name := _normalized_group_name(raw):
            names.add(name)
    return names

def _select_group_names(node: Any) -> set[str]:
    names: set[str] = set()
    for select in node.find_all("select", limit=int(VARIANT_CHOICE_CONTAINER_SELECT_LIMIT)):
        raw = select.get("name") or select.get("aria-label") or select.get("data-option-name")
        if name := _normalized_group_name(raw):
            names.add(name)
    return names

def _aria_group_names(node: Any) -> set[str]:
    names: set[str] = set()
    excluded = {"button", "a", "img", "input", "option"}
    for group in _descendant_group_label_nodes(node, limit=int(VARIANT_CHOICE_CONTAINER_GROUP_LIMIT)):
        if str(getattr(group, "name", "") or "").strip().lower() in excluded:
            continue
        if name := _normalized_group_name(group.get("aria-label")):
            names.add(name)
    return names

def _variant_choice_container_is_overbroad(node: Any) -> bool:
    if not hasattr(node, "find_all"):
        return False
    if str(getattr(node, "name", "") or "").strip().lower() == "fieldset":
        return False
    if len(node.find_all("fieldset", limit=2)) >= 2:
        return True
    names = _input_group_names(node) | _select_group_names(node) | _aria_group_names(node)
    return len(names) >= int(VARIANT_CHOICE_CONTAINER_MIN_DISTINCT_NAMES)

def resolve_variant_group_name(node: Any) -> str:
    if not hasattr(node, "get"):
        return ""
    if _variant_group_node_attrs_are_noise(node):
        return ""
    if component_name := _component_variant_group_name_from_attrs(node):
        return component_name
    inferred_name = infer_variant_group_name(node)
    tag_name = str(getattr(node, "name", "") or "").strip().lower()
    visible_candidates = _visible_variant_group_candidates(node, tag_name)
    for raw_name in [*visible_candidates, inferred_name]:
        if resolved_name := _resolve_visible_variant_group_name(raw_name):
            return resolved_name
    if descendant_name := _descendant_variant_group_name(node):
        return descendant_name
    for raw_name in _machine_variant_group_candidates(node):
        resolved_name = _resolve_machine_variant_group_name(raw_name)
        if resolved_name:
            return resolved_name
    if inferred_from_values := _variant_group_name_from_values(node, tag_name):
        return inferred_from_values
    if nearby := _nearby_variant_group_name(node):
        return nearby
    if hasattr(node, "select"):
        for child in node.select("[data-option-name], [aria-label], [data-testid], [data-qa-action], [role='radio'], input, button")[
            : int(VARIANT_DESCENDANT_SCAN_LIMIT)
        ]:
            inferred_child = infer_variant_group_name(child)
            if inferred_child:
                return inferred_child
    return clean_text(inferred_name)

def _visible_variant_group_candidates(node: Any, tag_name: str) -> list[object]:
    candidates: list[object] = []
    node_id = text_or_none(node.get("id"))
    accepts_label = tag_name not in {"input", "button", "option"}
    if node_id and accepts_label:
        root = node
        while getattr(root, "parent", None) is not None:
            root = root.parent
        external = root.find("label", attrs={"for": node_id}) if hasattr(root, "find") else None
        if external is not None:
            candidates.append(external.get_text(" ", strip=True))
    label = node.find_parent("label") if hasattr(node, "find_parent") else None
    if label is not None and accepts_label:
        candidates.append(label.get_text(" ", strip=True))
    fieldset = node if tag_name == "fieldset" else (node.find_parent("fieldset") if hasattr(node, "find_parent") else None)
    legend = fieldset.find("legend") if fieldset is not None else None
    if legend is not None:
        candidates.append(legend.get_text(" ", strip=True))
    if _node_attr_can_hold_group_label(node) and node.get("aria-label") not in (
        None,
        "",
        [],
        {},
    ):
        candidates.append(node.get("aria-label"))
    return candidates

def _machine_variant_group_candidates(node: Any) -> list[object]:
    return [node.get(attr) for attr in ("data-option-name", "name", "id", "data-testid", "data-qa-action") if node.get(attr) not in (None, "", [], {})]

def _variant_group_name_from_values(node: Any, tag_name: str) -> str:
    if tag_name == "select":
        inferred = infer_variant_group_name_from_values(_select_option_texts(node))
        return inferred if inferred == "size" else ""
    if not _node_supports_value_only_axis_inference(node):
        return ""
    return infer_variant_group_name_from_values(_choice_option_texts(node))

def infer_variant_group_name_from_values(values: Sequence[object]) -> str:
    cleaned_values = [clean_text(value) for value in values or [] if clean_text(value)]
    if len(cleaned_values) < 2:
        return ""
    # Sequential integer runs are quantity selectors, not variant axes.
    if _is_sequential_integer_run(cleaned_values):
        return ""
    size_hits = sum(1 for value in cleaned_values if any(pattern.fullmatch(value) for pattern in _variant_size_value_patterns))
    if size_hits >= 2 and size_hits / len(cleaned_values) >= 0.5:
        return "size"
    color_hits = sum(1 for value in cleaned_values if _value_looks_like_color(value))
    if color_hits >= 2 and color_hits / len(cleaned_values) >= 0.5:
        return "color"
    return ""

def _component_variant_group_name_from_attrs(node: Any) -> str:
    for attr_name in tuple(VARIANT_COMPONENT_TYPE_ATTRIBUTES or ()):
        raw_value = text_or_none(node.get(attr_name))
        if raw_value:
            return clean_text(f"{raw_value} {VARIANT_COMPONENT_TYPE_AXIS_NAME}")
    return ""

def _variant_group_node_attrs_are_noise(node: Any) -> bool:
    if not hasattr(node, "get"):
        return False
    parts: list[str] = []
    for attr_name in (
        "aria-label",
        "data-option-name",
        "data-testid",
        "data-qa-action",
        "id",
        "name",
        "class",
    ):
        value = node.get(attr_name)
        if isinstance(value, list):
            parts.extend(str(item) for item in value if item)
        elif value not in (None, "", [], {}):
            parts.append(str(value))
    probe = clean_text(" ".join(parts)).lower()
    if not probe:
        return False
    if any(token in probe for token in _variant_group_attr_noise_tokens):
        return True
    if any(token in probe for token in _variant_context_noise_tokens):
        return True
    return any(pattern.search(probe) for pattern in _variant_group_attr_noise_patterns)

def _node_attr_can_hold_group_label(node: Any) -> bool:
    tag_name = str(getattr(node, "name", "") or "").strip().lower()
    role = str(node.get("role") or "").strip().lower()
    if role == "radiogroup":
        return True
    if tag_name in {"select", "fieldset"}:
        return True
    if tag_name in {"input", "button", "option", "img", "a"}:
        return False
    if not hasattr(node, "select"):
        return True
    input_count = len(node.select("input[type='radio'], input[type='checkbox']"))
    return input_count >= 2 or tag_name in {"div", "section", "ul", "ol", "form"}

def _nearby_variant_group_name(node: Any) -> str:
    current = node
    for _ in range(int(VARIANT_SIBLING_SEARCH_DEPTH)):
        sibling = getattr(current, "previous_sibling", None)
        while sibling is not None:
            if hasattr(sibling, "select") and sibling.select("a[href], button, input[type='radio'], input[type='checkbox'], [role='radio'], [role='option']"):
                sibling = getattr(sibling, "previous_sibling", None)
                continue
            if hasattr(sibling, "get_text"):
                sibling_text = sibling.get_text(" ", strip=True)
                extracted = _resolve_visible_variant_group_name(sibling_text) or _semantic_group_label_from_text(sibling_text)
                if extracted:
                    return extracted
            sibling = getattr(sibling, "previous_sibling", None)
        parent = getattr(current, "parent", None)
        if parent is None:
            break
        current = parent
    return ""

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
    groups: list[Any] = []
    seen_ids: set[Any] = set()
    for select in _select_variant_nodes(soup, VARIANT_SELECT_GROUP_SELECTOR):
        if _select_is_quantity_node(select):
            continue
        if _select_option_values_are_noise(select):
            continue
        if resolve_variant_group_name(select):
            groups.append(select)
            seen_ids.add(select)
        if len(groups) >= int(VARIANT_SELECT_GROUP_MAX):
            break
    if len(groups) >= int(VARIANT_SELECT_GROUP_MAX):
        return groups
    for select in _select_variant_nodes(soup, "select"):
        if select in seen_ids:
            continue
        if _select_is_quantity_node(select):
            continue
        if _select_option_values_are_noise(select):
            continue
        if resolve_variant_group_name(select):
            groups.append(select)
            seen_ids.add(select)
        if len(groups) >= int(VARIANT_SELECT_GROUP_MAX):
            break
    return groups

def _append_choice_group(groups: list[Any], seen: set[Any], node: Any) -> bool:
    if node in seen:
        return False
    groups.append(node)
    seen.add(node)
    return len(groups) >= int(VARIANT_CHOICE_GROUP_MAX)

def _add_labeled_role_groups(soup: Any, groups: list[Any], seen: set[Any]) -> bool:
    for container in soup.select("[role='group'][aria-label]"):
        name = resolve_variant_group_name(container)
        axis = normalized_variant_axis_key(name)
        if variant_node_in_noise_context(container) and axis not in {"color", "size"}:
            continue
        if name and _variant_group_has_multiple_options(container):
            if _append_choice_group(groups, seen, container):
                return True
    return False

def _add_configured_choice_groups(soup: Any, groups: list[Any], seen: set[Any]) -> bool:
    for container in _select_variant_nodes(soup, VARIANT_CHOICE_GROUP_SELECTOR):
        if container in seen or _variant_choice_container_is_overbroad(container):
            continue
        name = resolve_variant_group_name(container)
        inferred = infer_variant_group_name_from_values(_choice_option_texts(container)) if _node_supports_value_only_axis_inference(container) else ""
        if _variant_group_has_multiple_options(container) and (name or inferred):
            if _append_choice_group(groups, seen, container):
                return True
    return False

def _add_input_choice_groups(soup: Any, groups: list[Any], seen: set[Any]) -> bool:
    for node in soup.select("input[type='radio'], input[type='checkbox']"):
        if variant_node_in_noise_context(node):
            continue
        candidate = _variant_choice_container_for_input(node)
        if candidate is None or variant_node_in_noise_context(candidate):
            continue
        if _append_choice_group(groups, seen, candidate):
            return True
    return False

def _add_button_choice_groups(soup: Any, groups: list[Any], seen: set[Any]) -> bool:
    selector = "button[data-variant], button.variant-option, button.size-option, button.color-option"
    for node in soup.select(selector):
        if variant_node_in_noise_context(node):
            continue
        if _append_choice_group(groups, seen, node):
            return True
    return False

def _ordered_swatch_buttons(soup: Any) -> list[Any]:
    priority = soup.select("[data-testid='swatch' i], [data-testid*='swatch-option' i], [role='button'][aria-label]")
    priority_ids = {id(node) for node in priority}
    buttons = [
        *priority,
        *(node for node in soup.select(VARIANT_SWATCH_BUTTON_SELECTOR) if id(node) not in priority_ids),
    ]
    return buttons[: int(VARIANT_SWATCH_BUTTON_LIMIT)]

def _swatch_parent_metadata(parent: Any) -> tuple[str, str, str]:
    tag = str(getattr(parent, "name", "") or "").lower()
    role = str(parent.get("role") or "").lower() if hasattr(parent, "get") else ""
    classes = parent.get("class") if hasattr(parent, "get") else None
    class_probe = (" ".join(str(value) for value in classes) if isinstance(classes, list) else str(classes or "")).lower()
    return tag, role, class_probe

def _swatch_parent_can_contain_group(tag: str, role: str, classes: str) -> bool:
    container_tags = {"div", "section", "fieldset", "ul", "ol", "nav", "form", "li"}
    hints = ("swatch", "variant", "color", "size", "option")
    return tag in container_tags or role == "radiogroup" or any(hint in classes for hint in hints)

def _swatch_parent_has_axis(tag: str, role: str, classes: str, parent: Any) -> bool:
    hints = (
        "color",
        "size",
        "swatch",
        "variant",
        "option",
        *_variant_axis_allowed_single_tokens,
    )
    return role == "radiogroup" or tag in {"fieldset", "ul", "ol"} or any(hint in classes for hint in hints) or bool(resolve_variant_group_name(parent))

def _swatch_container_for_button(button: Any, seen: set[Any], cache: dict[int, list[Any]]) -> Any | None:
    if str(getattr(button, "name", "") or "").strip().lower() == "a" and not _anchor_node_has_variant_signal(button):
        return None
    parent = getattr(button, "parent", None)
    depth = 0
    while parent is not None and depth < int(VARIANT_SWATCH_PARENT_DEPTH):
        if not hasattr(parent, "select") or variant_node_in_noise_context(parent):
            parent = getattr(parent, "parent", None)
            depth += 1
            continue
        if parent in seen:
            return None
        tag, role, classes = _swatch_parent_metadata(parent)
        if not _swatch_parent_can_contain_group(tag, role, classes):
            parent = getattr(parent, "parent", None)
            depth += 1
            continue
        siblings = cache.setdefault(id(parent), parent.select(VARIANT_SWATCH_BUTTON_SELECTOR))
        if len(siblings) >= 2:
            if _swatch_parent_has_axis(tag, role, classes, parent) and _variant_group_has_multiple_options(parent):
                return parent
            return None
        parent = getattr(parent, "parent", None)
        depth += 1
    return None

def _add_swatch_choice_groups(soup: Any, groups: list[Any], seen: set[Any]) -> None:
    cache: dict[int, list[Any]] = {}
    for button in _ordered_swatch_buttons(soup):
        candidate = _swatch_container_for_button(button, seen, cache)
        if candidate is not None and _append_choice_group(groups, seen, candidate):
            return

def iter_variant_choice_groups(soup: Any) -> list[Any]:
    """Find variant groups in deterministic discovery order."""
    groups: list[Any] = []
    seen: set[Any] = set()
    stages = (
        _add_labeled_role_groups,
        _add_configured_choice_groups,
        _add_input_choice_groups,
        _add_button_choice_groups,
    )
    for stage in stages:
        if stage(soup, groups, seen):
            return groups
    _add_swatch_choice_groups(soup, groups, seen)
    return groups

def _variant_choice_container_for_input(node: Any, *, axis_name: str | None = None) -> Any | None:
    if axis_name is None:
        axis_name = resolve_variant_group_name(node)
    input_type = str(node.get("type") or "").strip().lower() if hasattr(node, "get") else ""
    parent = getattr(node, "parent", None)
    while parent is not None:
        if not _input_parent_is_eligible(parent):
            parent = getattr(parent, "parent", None)
            continue
        if _input_parent_is_choice_container(parent, axis_name, input_type):
            return parent
        parent = getattr(parent, "parent", None)
    return None

def _input_parent_is_eligible(parent: Any) -> bool:
    return hasattr(parent, "find_all") and not variant_node_in_noise_context(parent) and not _variant_choice_container_is_overbroad(parent)

def _input_parent_axis_metadata(parent: Any) -> tuple[str, bool, str]:
    class_attr = parent.get("class") if hasattr(parent, "get") else None
    class_probe = (" ".join(str(value) for value in class_attr) if isinstance(class_attr, list) else str(class_attr or "")).lower()
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
                *_variant_axis_allowed_single_tokens,
            )
        )
    )
    return tag_name, has_hint, "" if has_hint else resolve_variant_group_name(parent)

def _input_parent_is_choice_container(parent: Any, axis_name: str | None, input_type: str) -> bool:
    matching = _matching_parent_inputs(parent, axis_name)
    tag_name, has_hint, group_name = _input_parent_axis_metadata(parent)
    allowed_single_axes = {"color", *_variant_axis_allowed_single_tokens}
    if len(matching) == 1 and axis_name in allowed_single_axes and has_hint:
        return True
    if len(matching) < 2:
        return False
    if input_type == "checkbox" and not any((axis_name, has_hint, group_name)):
        return False
    inferred = _input_parent_inferred_axis(parent, input_type)
    if any((has_hint, group_name, inferred)):
        return True
    return bool(axis_name and len(matching) <= int(VARIANT_MATCHING_INPUT_LIMIT) and tag_name in {"div", "section"})

def _matching_parent_inputs(parent: Any, axis_name: str | None) -> list[Any]:
    inputs = _descendant_variant_choice_inputs(
        parent,
        limit=max(
            int(VARIANT_CHOICE_CONTAINER_OPTION_LIMIT),
            int(VARIANT_MATCHING_INPUT_LIMIT),
        ),
    )
    return [item for item in inputs if not axis_name or resolve_variant_group_name(item) == axis_name]

def _input_parent_inferred_axis(parent: Any, input_type: str) -> str:
    if input_type != "checkbox" and _node_supports_value_only_axis_inference(parent):
        return infer_variant_group_name_from_values(_choice_option_texts(parent))
    return ""

# ruff: noqa: E402, F401, F821, F822
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

from . import variant_choice_groups as _split_owner
globals().update({
    name: value
    for name, value in vars(_split_owner).items()
    if not name.startswith("__") and name != "_owner"
})

# ruff: noqa: F401
from __future__ import annotations

__all__ = ("existing_variant_cluster_has_transport_signal", "primary_dom_context", "record_has_rich_existing_variants")

import logging
from copy import deepcopy
from itertools import product
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from app.services.dom.html_parser import BeautifulSoup

from app.services.config.extraction_rules import (
    DOM_VARIANT_CARTESIAN_COMBO_LIMIT,
    DOM_VARIANT_GROUP_LIMIT,
    VARIANT_CHOICE_OPTION_LIMIT,
    VARIANT_OPTION_CONTROL_SCAN_LIMIT,
)
from app.services.config.variant_migration_rules import (
    VARIANT_STRONG_OPTION_SELECTOR,
    VARIANT_WEAK_OPTION_SELECTOR,
)
from app.services.extract.variant_normalization.contract import (
    flatten_variants_for_public_output,
)
from app.services.shared.field_coerce import (
    clean_text,
    object_dict as _object_dict,
    object_list as _object_list,
    text_or_none,
)
from app.services.shared.url_utils import (
    clean_color_tokens,
    suffix_after_prefix,
    terminal_tokens,
    title_tokens,
)
from app.services.extract.detail.variants.state_targets import (
    state_variant_targets as _state_variant_targets,
)
from app.services.extract.detail.variants.dom_options import (
    merge_variant_option_state,
    node_attr_is_truthy,
    variant_option_availability,
    variant_option_url,
)
from app.services.extract.detail.variants.dom_merge import (
    dom_variants_add_missing_existing_axis as _dom_variants_add_missing_existing_axis,
    expand_existing_variants_with_dom_axes as _expand_existing_variants_with_dom_axes,
)
from app.services.extract.variant_group_validator import (
    VariantGroupValidator,
)
from app.services.extract.variant_dom_provenance import (
    build_variant_candidate_group,
    variant_option_node_types,
    weak_variant_option_node_allowed,
)
from app.services.js_state.helpers import select_variant
from app.services.extract.variant_choice_traversal import (
    infer_variant_group_name_from_values,
    iter_variant_choice_groups,
    iter_variant_select_groups,
    resolve_variant_group_name,
    variant_input_label,
    variant_dom_cues_present,
)
from app.services.extract.variant_identity_merge import (
    merge_variant_pair,
    resolve_variants,
    split_variant_axes,
)
from app.services.extract.variant_axis import (
    normalized_variant_axis_key,
    option_scalar_fields,
    public_variant_axis_fields,
)
from app.services.extract.variant_option_value import (
    variant_option_value_is_noise,
)
from app.services.extract.detail.assembly import (
    dom_section_targets as _detail_dom_section_targets,
)
from app.services.extract.detail.variants import dom_coercion as _variant_coercion

existing_variant_cluster_has_transport_signal = _detail_dom_section_targets.existing_variant_cluster_has_transport_signal
primary_dom_context = _detail_dom_section_targets.primary_dom_context
record_has_rich_existing_variants = _detail_dom_section_targets.record_has_rich_existing_variants

logger = logging.getLogger(__name__)

_DOM_OPTION_AVAILABILITY_PRIORITY = (
    "out_of_stock",
    "limited_stock",
    "in_stock",
)
_DOM_VARIANT_CACHE_ATTR = "_crawler_dom_variant_extraction_cache"

def _safe_int_config(value: object, default: int, name: str) -> int:
    try:
        if not isinstance(value, (int, float, str)):
            raise TypeError
        return max(1, int(value))
    except (TypeError, ValueError) as exc:
        logger.warning(
            f"Invalid {name}; using {default}",
            extra={"value": value},
            exc_info=exc,
        )
        return default

_coerce_variant_option_value = _variant_coercion._coerce_variant_option_value
_color_option_value_candidates = _variant_coercion._color_option_value_candidates
_component_size_style_from_group_name = _variant_coercion._component_size_style_from_group_name
_dom_variant_axis_allowed = _variant_coercion._dom_variant_axis_allowed
_dom_variant_group_name_allowed = _variant_coercion._dom_variant_group_name_allowed
_expand_compound_option_group = _variant_coercion._expand_compound_option_group
_prefer_axis_inferred_from_values = _variant_coercion._prefer_axis_inferred_from_values
_resolve_dom_variant_group_name = _variant_coercion._resolve_dom_variant_group_name
_strip_variant_option_value_suffix_noise = _variant_coercion._strip_variant_option_value_suffix_noise

def _visible_node_text(
    node: Any | None,
    *,
    cache: dict[Any, str] | None = None,
) -> str:
    if node is None or not hasattr(node, "get_text"):
        return ""
    cache_key = node
    if cache is not None:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached
    parsed = BeautifulSoup(str(node), "html.parser")
    for hidden in parsed.select(".sr-only, .visually-hidden, [aria-hidden='true'], svg, title, use"):
        hidden.decompose()
    visible_text = clean_text(parsed.get_text(" ", strip=True))
    if cache is not None:
        cache[cache_key] = visible_text
    return visible_text

def _collect_variant_choice_entries(container: Any, *, page_url: str, title_hint: str = "") -> list[dict[str, object]]:
    raw_group_name = _resolve_dom_variant_group_name(container)
    axis_name = normalized_variant_axis_key(raw_group_name)
    coercion_axis = axis_name if axis_name in option_scalar_fields or axis_name in public_variant_axis_fields else "style"
    entries_by_value: dict[str, dict[str, object]] = {}
    visible_text_cache: dict[Any, str] = {}
    option_limit = _safe_int_config(
        VARIANT_CHOICE_OPTION_LIMIT,
        50,
        "VARIANT_CHOICE_OPTION_LIMIT",
    )

    def candidate_rows(selector: str) -> list[tuple[Any, str]]:
        rows: list[tuple[Any, str]] = []
        scan_limit = _safe_int_config(
            VARIANT_OPTION_CONTROL_SCAN_LIMIT,
            300,
            "VARIANT_OPTION_CONTROL_SCAN_LIMIT",
        )
        for node in container.select(selector)[:scan_limit]:
            if not weak_variant_option_node_allowed(
                node,
                container=container,
                page_url=page_url,
            ):
                continue
            raw_value = _variant_choice_entry_value(
                container,
                node,
                axis_name=coercion_axis,
                visible_text_cache=visible_text_cache,
            )
            cleaned = _resolved_variant_option_value(
                coercion_axis,
                raw_value,
                page_url=page_url,
            )
            if not clean_text(cleaned) and coercion_axis == "color":
                option_url = variant_option_url(
                    container=container,
                    node=node,
                    label_node=None,
                    page_url=page_url,
                )
                cleaned = _color_value_from_option_url(
                    option_url,
                    page_url=page_url,
                    title_hint=title_hint,
                )
                _log_url_color_fallback(
                    cleaned,
                    page_url=page_url,
                    option_url=str(option_url or ""),
                    title_hint=title_hint,
                )
            cleaned = _strip_variant_option_value_suffix_noise(cleaned)
            if not variant_option_value_is_noise(cleaned):
                rows.append((node, cleaned))
                if len(rows) >= option_limit:
                    break
        return rows

    option_rows = candidate_rows(str(VARIANT_STRONG_OPTION_SELECTOR))
    if len(option_rows) < 2:
        option_rows = candidate_rows(str(VARIANT_WEAK_OPTION_SELECTOR))
    for node, cleaned in option_rows[:option_limit]:
        entry = entries_by_value.setdefault(cleaned, {"value": cleaned})
        merge_variant_option_state(
            entry,
            container=container,
            node=node,
            page_url=page_url,
        )
        variant_id = text_or_none(node.get("data-sku") or node.get("data-variant-id") or node.get("data-product-id"))
        if variant_id and entry.get("variant_id") in (None, "", [], {}):
            entry["variant_id"] = variant_id
    for input_node in container.select("input[type='radio'], input[type='checkbox']")[:option_limit]:
        label_node = variant_input_label(container, input_node)
        raw_value = _variant_choice_entry_value(
            container,
            input_node,
            axis_name=coercion_axis,
            label_node=label_node,
            visible_text_cache=visible_text_cache,
        )
        cleaned = _resolved_variant_option_value(
            coercion_axis,
            raw_value,
            page_url=page_url,
        )
        if not clean_text(cleaned) and coercion_axis == "color":
            option_url = variant_option_url(
                container=container,
                node=input_node,
                label_node=label_node,
                page_url=page_url,
            )
            cleaned = _color_value_from_option_url(
                option_url,
                page_url=page_url,
                title_hint=title_hint,
            )
            _log_url_color_fallback(
                cleaned,
                page_url=page_url,
                option_url=str(option_url or ""),
                title_hint=title_hint,
            )
        cleaned = _strip_variant_option_value_suffix_noise(cleaned)
        if variant_option_value_is_noise(cleaned):
            continue
        entry = entries_by_value.setdefault(cleaned, {"value": cleaned})
        merge_variant_option_state(
            entry,
            container=container,
            node=input_node,
            page_url=page_url,
            label_node=label_node,
        )
    return list(entries_by_value.values())

def _variant_choice_entry_value(
    container: Any,
    node: Any,
    *,
    axis_name: str,
    label_node: Any | None = None,
    visible_text_cache: dict[Any, str] | None = None,
) -> str:
    resolved_label = label_node or variant_input_label(container, node)
    label_text = _visible_node_text(resolved_label, cache=visible_text_cache)
    node_text = _visible_node_text(node, cache=visible_text_cache)
    aria_label = node.get("aria-label") if hasattr(node, "get") else None
    if axis_name == "color":
        color = _choice_color_value(node, resolved_label, label_text, node_text, aria_label)
        if color:
            return color
    return _choice_default_value(node, label_text, node_text, aria_label)

def _choice_color_value(node: Any, resolved_label: Any, label_text: str, node_text: str, aria_label: object) -> str:
    raw_values = (
        node.get("data-swatch-sr") if hasattr(node, "get") else None,
        aria_label,
        label_text,
        _descendant_image_alt_text(resolved_label),
        _descendant_image_alt_text(node),
        _descendant_aria_label_text(resolved_label),
        _descendant_aria_label_text(node),
        node_text,
    )
    for raw_value in raw_values:
        candidates = _color_option_value_candidates(clean_text(raw_value))
        if candidates and candidates[0]:
            return candidates[0]
    return ""

def _choice_default_value(node: Any, label_text: str, node_text: str, aria_label: object) -> str:
    return clean_text(
        node.get("data-attr-displayvalue")
        or node.get("data-displayvalue")
        or node.get("data-display-value")
        or node.get("data-swatch-sr")
        or node.get("data-size")
        or label_text
        or node.get("data-value")
        or node.get("data-option-value")
        or aria_label
        or node.get("value")
        or node_text
    )

def _variant_option_value_is_url_like(value: object) -> bool:
    text = text_or_none(value)
    if not text:
        return False
    lowered = text.strip().lower()
    return lowered.startswith(("http://", "https://", "/")) or "product-variation?" in lowered

def _variant_axis_value_from_option_url(
    axis_name: str,
    value: object,
) -> str:
    if axis_name not in {"size", "length"}:
        return ""
    text = text_or_none(value)
    if not text:
        return ""
    parsed = urlsplit(text)
    for key, raw_value in parse_qsl(parsed.query, keep_blank_values=False):
        normalized_key = clean_text(key).casefold()
        candidate = clean_text(raw_value)
        if not normalized_key or not candidate:
            continue
        if axis_name == "size" and _option_url_key_matches_size(normalized_key):
            return candidate
        if axis_name == "length" and _option_url_key_matches_length(normalized_key):
            return candidate
    return ""

def _option_url_key_matches_size(key: str) -> bool:
    return key in {"size", "size1", "waist"} or key.endswith(("_size", "_size1", "_waist"))

def _option_url_key_matches_length(key: str) -> bool:
    return key in {"length", "size2", "inseam"} or key.endswith(("_length", "_size2", "_inseam"))

def _resolved_variant_option_value(
    axis_name: str,
    raw_value: object,
    *,
    page_url: str,
) -> str:
    cleaned = _coerce_variant_option_value(axis_name, raw_value, page_url=page_url)
    if _variant_option_value_is_url_like(cleaned or raw_value):
        derived = _variant_axis_value_from_option_url(
            axis_name,
            cleaned or raw_value,
        )
        if derived:
            return _coerce_variant_option_value(axis_name, derived, page_url=page_url)
        if axis_name in {"size", "length"}:
            return ""
    return cleaned

def _descendant_image_alt_text(node: Any) -> str:
    if not hasattr(node, "find"):
        return ""
    image = node.find("img")
    if image is None or not hasattr(image, "get"):
        return ""
    return clean_text(image.get("alt"))

def _descendant_aria_label_text(node: Any) -> str:
    if not hasattr(node, "find"):
        return ""
    child = node.find(attrs={"aria-label": True})
    if child is None or not hasattr(child, "get"):
        return ""
    return clean_text(child.get("aria-label"))

def _color_value_from_option_url(
    value: object,
    *,
    page_url: str,
    title_hint: str = "",
) -> str:
    option_tokens = terminal_tokens(value)
    page_tokens = terminal_tokens(page_url)
    if len(option_tokens) < 2:
        return ""
    suffix_tokens = suffix_after_prefix(option_tokens, title_tokens(title_hint))
    if not suffix_tokens:
        suffix_tokens = suffix_after_prefix(option_tokens, page_tokens)
    if not suffix_tokens or len(suffix_tokens) > 4:
        return ""
    suffix_tokens = clean_color_tokens(suffix_tokens)
    if not suffix_tokens or len(suffix_tokens) > 4:
        return ""
    return " ".join(token.capitalize() for token in suffix_tokens)

def _log_url_color_fallback(
    color: str,
    *,
    page_url: str,
    option_url: str,
    title_hint: str,
) -> None:
    if not color:
        return
    logger.debug(
        "Extracted DOM variant color from option URL",
        extra={"color_length": len(color), "color_extracted": bool(color)},
    )

def _selected_option_metadata(
    axis_option_metadata: dict[str, dict[str, dict[str, object]]],
    option_values: dict[str, str],
) -> list[dict[str, object]]:
    selected_metadata: list[dict[str, object]] = []
    for axis_name, value in option_values.items():
        metadata = axis_option_metadata.get(axis_name, {}).get(clean_text(value), {})
        if isinstance(metadata, dict) and metadata:
            selected_metadata.append(metadata)
    return selected_metadata

def _availability_from_selected_options(
    selected_metadata: list[dict[str, object]],
) -> str:
    values = {text_or_none(metadata.get("availability")) for metadata in selected_metadata if isinstance(metadata, dict)}
    values.discard(None)
    for candidate in _DOM_OPTION_AVAILABILITY_PRIORITY:
        if candidate in values:
            return candidate
    return ""

def _stock_quantity_from_selected_options(
    selected_metadata: list[dict[str, object]],
) -> int | None:
    quantities: list[int] = []
    for metadata in selected_metadata:
        if not isinstance(metadata, dict):
            continue
        raw_quantity = metadata.get("stock_quantity")
        if raw_quantity in (None, "", [], {}):
            continue
        try:
            quantities.append(int(str(raw_quantity).strip()))
        except (TypeError, ValueError):
            continue
    if not quantities:
        return None
    if any(quantity <= 0 for quantity in quantities):
        return 0
    if len(set(quantities)) == 1:
        return quantities[0]
    return None

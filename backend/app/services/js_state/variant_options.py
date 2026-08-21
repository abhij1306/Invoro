from __future__ import annotations

from typing import Any

from app.services.config.js_state_field_specs import VARIANT_AXIS_KEYS
from app.services.extract.variant_axis import (
    normalized_variant_axis_key,
    variant_axis_name_is_semantic,
)
from app.services.shared.field_coerce import (
    coerce_field_value,
    text_or_none,
)


def variant_axis_value(
    axis_name: str,
    value: object,
    *,
    page_url: str,
) -> str | None:
    axis_key = normalized_variant_axis_key(axis_name) or str(axis_name or "")
    coerced = coerce_field_value(axis_key, value, page_url)
    return text_or_none(coerced)


def variant_selection_values(
    variant: dict[str, Any],
    *,
    option_names: list[str],
) -> dict[str, str]:
    selection_values: dict[str, str] = {}
    named_axis = _name_value_axis(variant)
    if named_axis:
        return named_axis
    selection_values = _selected_option_values(variant, None)
    if selection_values:
        return selection_values
    selection_values = _selection_variation_values(variant)
    return selection_values or _selection_indexed_values(variant, option_names)


def _selection_variation_values(variant: dict[str, Any]) -> dict[str, str]:
    selection_values: dict[str, str] = {}
    variation_values = variant.get("variationValues")
    if not isinstance(variation_values, dict):
        variation_values = variant.get("variation_values")
    if isinstance(variation_values, dict):
        for axis_name, raw_value in variation_values.items():
            axis_key = normalized_variant_axis_key(axis_name)
            cleaned = variant_axis_value(axis_key, raw_value, page_url="")
            if axis_key and cleaned and variant_axis_name_is_semantic(axis_name):
                selection_values[axis_key] = cleaned
    return selection_values


def _selection_indexed_values(
    variant: dict[str, Any], option_names: list[str]
) -> dict[str, str]:
    selection_values: dict[str, str] = {}
    raw_options = _as_list(variant.get("options"))
    for index in range(1, 4):
        axis_name = (
            option_names[index - 1]
            if index - 1 < len(option_names)
            else f"option_{index}"
        )
        axis_key = normalized_variant_axis_key(axis_name)
        if not axis_key or not variant_axis_name_is_semantic(axis_name):
            continue
        value = variant.get(f"option{index}")
        if value in (None, "", [], {}) and index - 1 < len(raw_options):
            value = raw_options[index - 1]
        cleaned = variant_axis_value(axis_key, value, page_url="")
        if cleaned:
            selection_values[axis_key] = cleaned
    return selection_values


def variant_option_values(
    variant: dict[str, Any],
    *,
    option_names: list[str],
    option_value_labels: dict[str, dict[str, str]] | None = None,
) -> dict[str, str]:
    named_axis = _name_value_axis(variant, option_value_labels=option_value_labels)
    if named_axis:
        return named_axis
    option_values = _selected_option_values(variant, option_value_labels)
    if option_values:
        return option_values
    option_values = _variation_option_values(variant, option_value_labels)
    if option_values:
        return option_values
    for field_name in ("attributes", "traits"):
        values = variant.get(field_name)
        if isinstance(values, dict):
            _add_option_values_from_mapping(
                values, option_values, option_value_labels=option_value_labels
            )
        if option_values:
            return option_values
    option_values = _size_chart_option_values(variant, option_value_labels)
    if option_values:
        return option_values
    option_values = _indexed_option_values(variant, option_names, option_value_labels)
    return option_values or _direct_axis_option_values(variant, option_value_labels)


def _selected_option_values(
    variant: dict[str, Any], labels: dict[str, dict[str, str]] | None
) -> dict[str, str]:
    option_values: dict[str, str] = {}
    selected_options = (
        variant.get("selectedOptions")
        if isinstance(variant.get("selectedOptions"), list)
        else variant.get("selected_options")
    )
    if isinstance(selected_options, list):
        for item in selected_options:
            if not isinstance(item, dict):
                continue
            axis_name = text_or_none(item.get("name") or item.get("label"))
            axis_value = variant_axis_value(
                normalized_variant_axis_key(axis_name or ""),
                item.get("value") or item.get("title") or item.get("label"),
                page_url="",
            )
            if (
                not axis_name
                or not axis_value
                or not variant_axis_name_is_semantic(axis_name)
            ):
                continue
            axis_key = normalized_variant_axis_key(axis_name)
            if axis_key:
                option_values[axis_key] = _display_option_value(
                    axis_key,
                    axis_value,
                    option_value_labels=labels,
                )
    return option_values


def _variation_option_values(
    variant: dict[str, Any], labels: dict[str, dict[str, str]] | None
) -> dict[str, str]:
    option_values: dict[str, str] = {}
    variation_values = variant.get("variationValues")
    if not isinstance(variation_values, dict):
        variation_values = variant.get("variation_values")
    if isinstance(variation_values, dict):
        direct_axis_keys = {
            normalized_variant_axis_key(axis_name)
            for axis_name in variation_values
            if normalized_variant_axis_key(axis_name)
            == str(axis_name or "").strip().lower().replace("-", "_")
        }
        for axis_name, raw_value in variation_values.items():
            axis_key = normalized_variant_axis_key(axis_name)
            cleaned = variant_axis_value(axis_key, raw_value, page_url="")
            if (
                not axis_key
                or not cleaned
                or not variant_axis_name_is_semantic(axis_name)
            ):
                continue
            if (
                axis_key in direct_axis_keys
                and axis_key != str(axis_name).strip().lower()
            ):
                continue
            if axis_key in option_values:
                continue
            option_values[axis_key] = _display_option_value(
                axis_key,
                cleaned,
                option_value_labels=labels,
            )
    return option_values


def _size_chart_option_values(
    variant: dict[str, Any], labels: dict[str, dict[str, str]] | None
) -> dict[str, str]:
    size_chart = variant.get("sizeChart")
    if isinstance(size_chart, dict):
        cleaned = variant_axis_value("size", size_chart.get("baseSize"), page_url="")
        if cleaned:
            return {
                "size": _display_option_value(
                    "size", cleaned, option_value_labels=labels
                )
            }
    return {}


def _indexed_option_values(
    variant: dict[str, Any],
    option_names: list[str],
    labels: dict[str, dict[str, str]] | None,
) -> dict[str, str]:
    option_values: dict[str, str] = {}
    raw_options = _as_list(variant.get("options"))
    for index in range(1, 4):
        axis_name = (
            option_names[index - 1]
            if index - 1 < len(option_names)
            else f"option_{index}"
        )
        axis_key = normalized_variant_axis_key(axis_name) or f"option_{index}"
        if not variant_axis_name_is_semantic(axis_name):
            continue
        value = variant.get(f"option{index}")
        if value in (None, "", [], {}) and index - 1 < len(raw_options):
            value = raw_options[index - 1]
        cleaned = variant_axis_value(axis_key, value, page_url="")
        if cleaned:
            option_values[axis_key] = _display_option_value(
                axis_key,
                cleaned,
                option_value_labels=labels,
            )
    return option_values


def _direct_axis_option_values(
    variant: dict[str, Any], labels: dict[str, dict[str, str]] | None
) -> dict[str, str]:
    option_values: dict[str, str] = {}
    for axis in VARIANT_AXIS_KEYS:
        cleaned = variant_axis_value(axis, variant.get(axis), page_url="")
        if cleaned:
            option_values[axis] = _display_option_value(
                axis, cleaned, option_value_labels=labels
            )
    return option_values


def option_value_labels(product: dict[str, Any]) -> dict[str, dict[str, str]]:
    labels: dict[str, dict[str, str]] = {}
    raw_attributes = product.get("variationAttributes")
    if not isinstance(raw_attributes, list):
        raw_attributes = product.get("variation_attributes")
    if not isinstance(raw_attributes, list):
        raw_attributes = product.get("attributes")
    if not isinstance(raw_attributes, list):
        return labels
    direct_axis_keys = _direct_attribute_axis_keys(raw_attributes)
    for attribute in raw_attributes:
        _add_attribute_value_labels(attribute, labels, direct_axis_keys)
    return labels


def _direct_attribute_axis_keys(attributes: list[object]) -> set[str]:
    direct: set[str] = set()
    for attribute in attributes:
        if not isinstance(attribute, dict):
            continue
        raw_id = text_or_none(attribute.get("id")) or ""
        axis_name = (
            text_or_none(
                attribute.get("id") or attribute.get("name") or attribute.get("label")
            )
            or ""
        )
        axis_key = normalized_variant_axis_key(axis_name)
        if axis_key == raw_id.strip().lower().replace("-", "_"):
            direct.add(axis_key)
    return direct


def _first_mapping_text(
    mapping: dict[str, object], keys: tuple[str, ...]
) -> str | None:
    return next(
        (text for key in keys if (text := text_or_none(mapping.get(key)))), None
    )


def _add_attribute_label_rows(
    values: list[object], labels: dict[str, dict[str, str]], axis_key: str
) -> None:
    for item in values:
        if not isinstance(item, dict):
            continue
        raw_value = _first_mapping_text(item, ("value", "id", "slug"))
        display = _first_mapping_text(
            item, ("name", "displayValue", "display_value", "label")
        )
        if not raw_value or not display:
            continue
        labels.setdefault(axis_key, {})[raw_value] = display
        item_id = _first_mapping_text(item, ("id", "slug"))
        if item_id:
            labels[axis_key][item_id] = display


def _add_attribute_value_labels(
    attribute: object,
    labels: dict[str, dict[str, str]],
    direct_axis_keys: set[str],
) -> None:
    if not isinstance(attribute, dict):
        return
    axis_name = _first_mapping_text(attribute, ("id", "name", "label", "type"))
    axis_key = normalized_variant_axis_key(axis_name or "")
    if not axis_key or (
        axis_key in direct_axis_keys
        and axis_key != str(axis_name or "").strip().lower()
    ):
        return
    values = attribute.get("values")
    if not isinstance(values, list):
        values = attribute.get("options")
    if not isinstance(values, list):
        return
    _add_attribute_label_rows(values, labels, axis_key)


def _name_value_axis(
    variant: dict[str, Any],
    *,
    option_value_labels: dict[str, dict[str, str]] | None = None,
) -> dict[str, str]:
    axis_name = text_or_none(variant.get("name") or variant.get("label"))
    axis_key = normalized_variant_axis_key(axis_name or "")
    cleaned = variant_axis_value(axis_key, variant.get("value"), page_url="")
    if not axis_key or not cleaned or not variant_axis_name_is_semantic(axis_name):
        return {}
    return {
        axis_key: _display_option_value(
            axis_key,
            cleaned,
            option_value_labels=option_value_labels,
        )
    }


def _add_option_values_from_mapping(
    values: dict[object, object],
    option_values: dict[str, str],
    *,
    option_value_labels: dict[str, dict[str, str]] | None,
) -> None:
    for axis_name, raw_value in values.items():
        axis_key = normalized_variant_axis_key(axis_name)
        cleaned = variant_axis_value(axis_key, raw_value, page_url="")
        if not axis_key or not cleaned or not variant_axis_name_is_semantic(axis_name):
            continue
        option_values[axis_key] = _display_option_value(
            axis_key,
            cleaned,
            option_value_labels=option_value_labels,
        )


def _display_option_value(
    axis_key: str,
    value: str,
    *,
    option_value_labels: dict[str, dict[str, str]] | None,
) -> str:
    cleaned = text_or_none(value)
    if not cleaned:
        return ""
    return (option_value_labels or {}).get(axis_key, {}).get(cleaned, cleaned)


def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []

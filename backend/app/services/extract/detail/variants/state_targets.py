from __future__ import annotations

__all__ = (
    "state_variant_targets",
    "variant_query_url",
    "iter_variant_mapping_payloads",
)

from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from app.services.extract.variant_axis import normalized_variant_axis_key
from app.services.extract.variant_option_value import variant_option_value_is_noise
from app.services.shared.field_coerce import absolute_url, object_dict, text_or_none


def _first_text(mapping: dict[str, object], keys: tuple[str, ...]) -> str | None:
    return next(
        (text for key in keys if (text := text_or_none(mapping.get(key)))), None
    )


def _state_option_definition(option: object) -> dict[str, object] | None:
    if not isinstance(option, dict):
        return None
    axis_field = _first_text(option, ("id", "key", "name"))
    axis_key = normalized_variant_axis_key(option.get("label") or axis_field)
    option_list = option.get("optionList")
    if not axis_field or not axis_key or not isinstance(option_list, list):
        return None
    values: dict[str, str] = {}
    for item in option_list:
        if not isinstance(item, dict):
            continue
        option_id = _first_text(item, ("id", "value"))
        option_value = _first_text(item, ("title", "label", "value"))
        if (
            option_id
            and option_value
            and not variant_option_value_is_noise(option_value)
        ):
            values[option_id] = option_value
    return (
        {"axis_field": axis_field, "axis_key": axis_key, "value_by_id": values}
        if values
        else None
    )


def _state_option_values(
    row: dict[str, object], definitions: list[dict[str, object]]
) -> dict[str, str]:
    values: dict[str, str] = {}
    for definition in definitions:
        axis_field = str(definition["axis_field"])
        option_id = text_or_none(row.get(axis_field))
        mapped = object_dict(definition.get("value_by_id")).get(option_id or "")
        if mapped:
            values[str(definition["axis_key"])] = str(mapped)
    return values


def _state_row_metadata(row: dict[str, object], page_url: str) -> dict[str, object]:
    metadata: dict[str, object] = {}
    url_keys = ("url", "href", "productUrl", "product_url", "targetUrl", "target_url")
    explicit_url = next(
        (text_or_none(row.get(key)) for key in url_keys if text_or_none(row.get(key))),
        None,
    )
    if explicit_url:
        metadata["url"] = absolute_url(page_url, explicit_url)
    for key in ("productId", "product_id", "variantId", "variant_id", "sku", "id"):
        raw_value = text_or_none(row.get(key))
        if not raw_value:
            continue
        metadata.setdefault("variant_id", raw_value)
        inferred_url = variant_query_url(page_url, query_key=key, query_value=raw_value)
        if "url" not in metadata and inferred_url:
            metadata["url"] = inferred_url
        break
    return metadata


def _add_state_target(
    option_values: dict[str, str],
    metadata: dict[str, object],
    axis_targets: dict[str, dict[str, dict[str, object]]],
    combo_targets: dict[tuple[tuple[str, str], ...], dict[str, object]],
) -> None:
    if len(option_values) == 1:
        axis_key, option_value = next(iter(option_values.items()))
        axis_targets.setdefault(axis_key, {}).setdefault(option_value, {}).update(
            metadata
        )
    combo_targets[tuple(sorted(option_values.items()))] = metadata


def _variant_mapping_lists(payload: dict[str, Any]) -> list[list[dict[str, object]]]:
    return [
        rows
        for item in payload.values()
        if isinstance(item, list)
        and item
        and all(isinstance(row, dict) for row in item)
        for rows in [[row for row in item if isinstance(row, dict)]]
    ]


def state_variant_targets(
    js_state_objects: dict[str, Any] | None,
    *,
    page_url: str,
) -> tuple[
    dict[str, dict[str, dict[str, object]]],
    dict[tuple[tuple[str, str], ...], dict[str, object]],
]:
    axis_targets: dict[str, dict[str, dict[str, object]]] = {}
    combo_targets: dict[tuple[tuple[str, str], ...], dict[str, object]] = {}
    if not isinstance(js_state_objects, dict):
        return axis_targets, combo_targets
    for payload in iter_variant_mapping_payloads(js_state_objects):
        raw_options = payload.get("options")
        if not isinstance(raw_options, list):
            continue
        option_definitions = [
            definition
            for option in raw_options
            if (definition := _state_option_definition(option))
        ]
        if not option_definitions:
            continue
        mapping_lists = _variant_mapping_lists(payload)
        for mapping_rows in mapping_lists:
            for mapping_row in mapping_rows:
                option_values = _state_option_values(mapping_row, option_definitions)
                if not option_values:
                    continue
                row_metadata = _state_row_metadata(mapping_row, page_url)
                if not row_metadata:
                    continue
                _add_state_target(
                    option_values, row_metadata, axis_targets, combo_targets
                )
    return axis_targets, combo_targets


def variant_query_url(page_url: str, *, query_key: str, query_value: str) -> str | None:
    normalized_key = text_or_none(query_key)
    normalized_value = text_or_none(query_value)
    if not normalized_key or not normalized_value:
        return None
    parsed = urlsplit(str(page_url or "").strip())
    query_pairs = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key != normalized_key
    ]
    query_pairs.append((normalized_key, normalized_value))
    return urlunsplit(parsed._replace(query=urlencode(query_pairs, doseq=True)))


def iter_variant_mapping_payloads(
    value: Any, *, depth: int = 0, limit: int = 8
) -> list[dict[str, Any]]:
    if depth > limit:
        return []
    matches: list[dict[str, Any]] = []
    if isinstance(value, dict):
        if isinstance(value.get("options"), list):
            matches.append(value)
        for item in value.values():
            matches.extend(
                iter_variant_mapping_payloads(item, depth=depth + 1, limit=limit)
            )
    elif isinstance(value, list):
        for item in value[:25]:
            matches.extend(
                iter_variant_mapping_payloads(item, depth=depth + 1, limit=limit)
            )
    return matches

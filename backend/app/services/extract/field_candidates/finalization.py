from __future__ import annotations

from app.services.extract.variant_identity_merge import merge_variant_rows
from app.services.shared.field_coerce import (
    LONG_TEXT_FIELDS,
    STRUCTURED_MULTI_FIELDS,
    STRUCTURED_OBJECT_FIELDS,
    STRUCTURED_OBJECT_LIST_FIELDS,
    coerce_text,
    text_or_none,
)
from app.services.shared.coerce_primitives import is_blank

from .collection import candidate_fingerprint

_FieldNames = list[str] | tuple[str, ...] | set[str] | frozenset[str]


def finalize_candidate_value(field_name: str, values: list[object]) -> object | None:
    if not values:
        return None
    if field_name in STRUCTURED_OBJECT_FIELDS:
        return _merge_structured_objects(values)
    if field_name in STRUCTURED_OBJECT_LIST_FIELDS:
        return _merge_structured_rows(field_name, values)
    if field_name in STRUCTURED_MULTI_FIELDS:
        rows = _unique_text_rows(values)
        if field_name in {"additional_images", "features", "tags"}:
            return rows or None
        return "\n".join(rows) if rows else None
    if field_name in LONG_TEXT_FIELDS:
        text_rows = _unique_long_text_rows(values)
        return "\n\n".join(text_rows) if text_rows else None
    return values[0]


def _merge_structured_objects(values: list[object]) -> dict[str, object] | None:
    merged: dict[str, object] = {}
    for value in values:
        if isinstance(value, dict):
            merged = _deep_merge_structured_dict(merged, value)
    return merged or None


def _merge_structured_rows(
    field_name: str, values: list[object]
) -> list[dict[str, object]] | None:
    merged_rows: list[dict[str, object]] = []
    seen_rows: set[str] = set()
    for row in (
        row
        for value in values
        if isinstance(value, list)
        for row in value
        if isinstance(row, dict)
    ):
        fingerprint = candidate_fingerprint(row)
        if fingerprint not in seen_rows:
            seen_rows.add(fingerprint)
            merged_rows.append(row)
    if field_name == "variants":
        merged_rows = merge_variant_rows(merged_rows)
    return merged_rows or None


def _unique_text_rows(values: list[object]) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for value in values:
        for item in value if isinstance(value, list) else [value]:
            text = text_or_none(item)
            if text and text.lower() not in seen:
                seen.add(text.lower())
                rows.append(text)
    return rows


def _unique_long_text_rows(values: list[object]) -> list[str]:
    rows: list[str] = []
    lowered_rows: list[str] = []
    for value in values:
        text = coerce_text(value)
        lowered = text.lower() if text else ""
        if not text or lowered in lowered_rows:
            continue
        if any(
            _long_text_differs_only_by_short_suffix(lowered, kept)
            for kept in lowered_rows
        ):
            continue
        lowered_rows.append(lowered)
        rows.append(text)
    return rows


def finalize_candidate_fields(
    candidates: dict[str, list[object]],
    field_names: _FieldNames | None,
    *,
    require_structured_multi_list: bool = False,
) -> dict[str, object]:
    result: dict[str, object] = {}
    iterable_fields = (
        field_names if isinstance(field_names, (list, tuple, set, frozenset)) else ()
    )
    for field_name in iterable_fields:
        if not isinstance(field_name, str):
            continue
        finalized = finalize_candidate_value(field_name, candidates.get(field_name, []))
        if is_blank(finalized):
            continue
        if (
            require_structured_multi_list
            and field_name in STRUCTURED_MULTI_FIELDS
            and not isinstance(finalized, list)
        ):
            continue
        result[field_name] = finalized
    return result


def _long_text_differs_only_by_short_suffix(left: str, right: str) -> bool:
    if len(left) < 200 or len(right) < 200:
        return False
    shared = 0
    limit = min(len(left), len(right))
    while shared < limit and left[shared] == right[shared]:
        shared += 1
    if shared < 200:
        return False
    left_tail = left[shared:].strip()
    right_tail = right[shared:].strip()
    return max(len(left_tail), len(right_tail)) <= 160


def _deep_merge_structured_dict(
    base: dict[str, object],
    incoming: dict[str, object],
) -> dict[str, object]:
    merged = dict(base)
    incoming_option_values = incoming.get("option_values")
    incoming_option_keys = _option_value_keys(incoming_option_values)
    for key, value in incoming.items():
        normalized_key = str(key)
        existing = merged.get(normalized_key)
        if _preserve_existing_option_value(
            normalized_key, existing, value, merged, incoming_option_keys
        ):
            continue
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[normalized_key] = _deep_merge_structured_dict(existing, value)
            continue
        if isinstance(existing, list) and isinstance(value, list):
            combined: list[object] = []
            seen: set[str] = set()
            for item in [*existing, *value]:
                fingerprint = candidate_fingerprint(item)
                if fingerprint in seen:
                    continue
                seen.add(fingerprint)
                combined.append(item)
            merged[normalized_key] = combined
            continue
        if is_blank(existing) and not is_blank(value):
            merged[normalized_key] = value
            continue
        if normalized_key not in merged:
            merged[normalized_key] = value
    return merged


def _option_value_keys(value: object) -> set[str]:
    return {str(key) for key in value} if isinstance(value, dict) else set()


def _preserve_existing_option_value(
    key: str,
    existing: object,
    incoming: object,
    merged: dict[str, object],
    incoming_option_keys: set[str],
) -> bool:
    if key == "option_values":
        return bool(
            isinstance(existing, dict) and existing and isinstance(incoming, dict)
        )
    option_values = merged.get("option_values")
    return bool(
        incoming_option_keys
        and isinstance(option_values, dict)
        and option_values
        and key in incoming_option_keys
        and is_blank(existing)
    )

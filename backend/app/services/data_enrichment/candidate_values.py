from __future__ import annotations

from collections.abc import Collection

from app.services.config.data_enrichment import data_enrichment_settings


def candidate_values(data: dict[str, object], *keys: str) -> list[object]:
    values: list[object] = []
    for key in keys:
        value = data.get(key)
        if value in (None, "", [], {}):
            continue
        if isinstance(value, dict):
            values.extend(flatten_dict_values(value))
        elif isinstance(value, list):
            values.extend(flatten_list_values(value))
        else:
            values.append(value)
    return values


def targeted_candidate_values(
    data: dict[str, object], target_keys: Collection[str], *keys: str
) -> list[object]:
    normalized_targets = {str(key).casefold() for key in target_keys}
    values: list[object] = []
    for key in keys:
        value = data.get(key)
        if value in (None, "", [], {}):
            continue
        if isinstance(value, dict):
            values.extend(flatten_targeted_dict_values(value, normalized_targets))
        elif isinstance(value, list):
            values.extend(flatten_targeted_list_values(value, normalized_targets))
        else:
            values.append(value)
    return values


def flatten_dict_values(
    value: dict[str, object], max_depth: int | None = None
) -> list[object]:
    depth = (
        data_enrichment_settings.candidate_flatten_max_depth
        if max_depth is None
        else max_depth
    )
    if depth <= 0:
        return []
    values: list[object] = []
    for item in value.values():
        if isinstance(item, dict):
            values.extend(flatten_dict_values(item, depth - 1))
        elif isinstance(item, list):
            values.extend(flatten_list_values(item, depth - 1))
        else:
            values.append(item)
    return values


def flatten_list_values(
    value: list[object], max_depth: int | None = None
) -> list[object]:
    depth = (
        data_enrichment_settings.candidate_flatten_max_depth
        if max_depth is None
        else max_depth
    )
    if depth <= 0:
        return []
    values: list[object] = []
    for item in value:
        if isinstance(item, dict):
            values.extend(flatten_dict_values(item, depth - 1))
        elif isinstance(item, list):
            values.extend(flatten_list_values(item, depth - 1))
        else:
            values.append(item)
    return values


def flatten_targeted_dict_values(
    value: dict[str, object], target_keys: set[str], max_depth: int | None = None
) -> list[object]:
    depth = (
        data_enrichment_settings.candidate_flatten_max_depth
        if max_depth is None
        else max_depth
    )
    if depth <= 0:
        return []
    values: list[object] = []
    for key, item in value.items():
        if str(key).casefold() in target_keys and item not in (None, "", [], {}):
            values.extend(_flatten_matched_value(item, depth))
        elif isinstance(item, dict):
            values.extend(flatten_targeted_dict_values(item, target_keys, depth - 1))
        elif isinstance(item, list):
            values.extend(flatten_targeted_list_values(item, target_keys, depth - 1))
    return values


def flatten_targeted_list_values(
    value: list[object], target_keys: set[str], max_depth: int | None = None
) -> list[object]:
    depth = (
        data_enrichment_settings.candidate_flatten_max_depth
        if max_depth is None
        else max_depth
    )
    if depth <= 0:
        return []
    values: list[object] = []
    for item in value:
        if isinstance(item, dict):
            values.extend(flatten_targeted_dict_values(item, target_keys, depth - 1))
        elif isinstance(item, list):
            values.extend(flatten_targeted_list_values(item, target_keys, depth - 1))
    return values


def _flatten_matched_value(value: object, depth: int) -> list[object]:
    if isinstance(value, dict):
        return flatten_dict_values(value, depth - 1)
    if isinstance(value, list):
        return flatten_list_values(value, depth - 1)
    return [value]

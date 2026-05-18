from __future__ import annotations

from app.services.extract.variant_normalization.common import *
from app.services.extract.variant_normalization import backfill
from app.services.extract.variant_normalization import deduplication
from app.services.extract.variant_normalization import size_color_extraction

__all__ = (
    "_remap_generic_variant_axes",
    "_sanitize_variant_axes",
    "_flatten_variant_rows",
    "_variant_title_tokens",
    "_clean_variant_rows",
    "_enforce_variant_axis_contract",
    "_should_restore_original_variant_url",
    "_drop_polluted_parent_scalar_axes",
    "_value_is_axis_header_noise",
    "_promote_misfiled_color_size",
    "_drop_shade_code_size_duplicate",
    "_normalize_separate_dimension_size_rows",
    "_separate_dimension_style_label",
    "_variant_axis_value_is_header",
)

_REMAP_ELIGIBLE_AXES = frozenset({"state", "type", "style", "configuration"})
_CORE_AXES = frozenset({"size", "color"})


def _remap_generic_variant_axes(record: dict[str, Any]) -> None:
    """Remap generic/non-semantic axes to size or color when values match."""
    variants = record.get("variants")
    if not isinstance(variants, list) or not variants:
        return
    # Collect axes that appear across all variant rows (excluding core axes).
    generic_axis_values: dict[str, list[str]] = {}
    for variant in variants:
        if not isinstance(variant, dict):
            continue
        for axis in _REMAP_ELIGIBLE_AXES:
            value = clean_text(variant.get(axis))
            if value:
                generic_axis_values.setdefault(axis, []).append(value)
    if not generic_axis_values:
        return
    for axis, values in generic_axis_values.items():
        if len(values) < 2:
            continue
        # Only remap if no variant already has the target axis populated.
        inferred = infer_variant_group_name_from_values(values)
        if not inferred or inferred not in _CORE_AXES:
            continue
        # Check that no variant already has the target axis set.
        if any(
            clean_text(variant.get(inferred))
            for variant in variants
            if isinstance(variant, dict)
        ):
            continue
        # Check that the parent record does not already have the target axis
        # populated — remapping would create conflicting parent/variant state.
        if clean_text(record.get(inferred)):
            continue
        # Remap: move values from generic axis to the inferred axis.
        for variant in variants:
            if not isinstance(variant, dict):
                continue
            value = variant.pop(axis, None)
            if value not in (None, "", [], {}):
                variant[inferred] = value


def _sanitize_variant_axes(record: dict[str, Any]) -> None:
    _remap_generic_variant_axes(record)
    drop_cross_product_variant_rows(
        record,
        color_extractor=size_color_extraction._extract_color_value,
    )
    _flatten_variant_rows(record)
    _clean_variant_rows(record)
    _normalize_separate_dimension_size_rows(record)
    deduplication._prune_unrecognized_size_rows_when_real_sizes_exist(record)
    deduplication._prune_child_size_rows_from_adult_products(record)
    drop_parent_shared_variant_axes(record)
    _enforce_variant_axis_contract(record)
    backfill._enforce_variant_currency_context(record)


def _flatten_variant_rows(record: dict[str, Any]) -> None:
    variants = flatten_variants_for_public_output(record.get("variants"))
    if variants:
        record["variants"] = variants
        record["variant_count"] = len(variants)
        return
    record.pop("variants", None)
    record.pop("variant_count", None)


def _variant_title_tokens(value: object) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", clean_text(value).casefold())
        if len(token) >= 3 and token not in _VARIANT_TITLE_STOPWORDS
    }


def _clean_variant_rows(record: dict[str, Any]) -> None:
    variants = record.get("variants")
    if not isinstance(variants, list) or not variants:
        return
    cleaned_variants: list[dict[str, Any]] = []
    for variant in variants:
        if not isinstance(variant, dict):
            continue
        cleaned_variant = dict(variant)
        drop_row = False
        for field_name in _PUBLIC_VARIANT_AXIS_FIELDS:
            raw_axis_value = cleaned_variant.get(field_name)
            if size_color_extraction._variant_size_axis_value_is_quantity_control(
                field_name,
                raw_axis_value,
            ):
                drop_row = True
                break
            cleaned_value = size_color_extraction._normalize_variant_axis_value(
                field_name,
                raw_axis_value,
            )
            if cleaned_value:
                cleaned_variant[field_name] = cleaned_value
            else:
                cleaned_variant.pop(field_name, None)
        if drop_row:
            continue
        _promote_misfiled_color_size(cleaned_variant)
        _drop_shade_code_size_duplicate(cleaned_variant)
        drop_invalid_variant_urls(cleaned_variant)
        if _should_restore_original_variant_url(
            original_variant=variant,
            cleaned_variant=cleaned_variant,
        ):
            cleaned_variant["url"] = variant.get("url")
        if any(
            cleaned_variant.get(field_name) not in (None, "", [], {})
            for field_name in (*FLAT_VARIANT_KEYS, *_PUBLIC_VARIANT_AXIS_FIELDS)
        ):
            cleaned_variants.append(cleaned_variant)
    if cleaned_variants:
        record["variants"] = cleaned_variants
        record["variant_count"] = len(cleaned_variants)
        return
    record.pop("variants", None)
    record.pop("variant_count", None)


def _enforce_variant_axis_contract(record: dict[str, Any]) -> None:
    variants = record.get("variants")
    if not isinstance(variants, list) or not variants:
        return
    axisful_variants = [
        variant
        for variant in variants
        if isinstance(variant, dict) and _variant_has_axis_value(variant)
    ]
    if axisful_variants:
        record["variants"] = axisful_variants
        record["variant_count"] = len(axisful_variants)
        return
    record.pop("variants", None)
    record.pop("variant_count", None)


def _should_restore_original_variant_url(
    *,
    original_variant: dict[str, Any],
    cleaned_variant: dict[str, Any],
) -> bool:
    original_url = clean_text(original_variant.get("url"))
    if not original_url or clean_text(cleaned_variant.get("url")):
        return False
    remaining_transport_fields = [
        field_name
        for field_name in FLAT_VARIANT_KEYS
        if (
            field_name != "url"
            and field_name not in _PUBLIC_VARIANT_AXIS_FIELDS
            and cleaned_variant.get(field_name) not in (None, "", [], {})
        )
    ]
    return not remaining_transport_fields


def _drop_polluted_parent_scalar_axes(record: dict[str, Any]) -> None:
    variants = record.get("variants")
    if not isinstance(variants, list) or not any(
        isinstance(variant, dict) for variant in variants
    ):
        return
    max_tokens = _SCALAR_FIELD_MAX_OPTION_TOKENS
    for field_name in ("color", "size"):
        value = clean_text(record.get(field_name))
        if not value:
            continue
        lowered = value.casefold()
        tokens = [token for token in re.split(r"[\s,|/]+", lowered) if token]
        numeric_tokens = sum(1 for token in tokens if re.search(r"\d", token))
        if lowered in _SCALAR_FIELD_POLLUTION_VALUES or (
            field_name == "size"
            and len(tokens) > max_tokens + 2
            and numeric_tokens >= 2
        ):
            record.pop(field_name, None)


def _promote_misfiled_color_size(variant: dict[str, Any]) -> None:
    if clean_text(variant.get("color")):
        return
    size_value = clean_text(variant.get("size"))
    if not size_value:
        return
    if size_color_extraction._extract_size_value(size_value):
        return
    color_value = size_color_extraction._extract_color_value(size_value)
    if not color_value:
        return
    variant["color"] = color_value
    variant.pop("size", None)


def _drop_shade_code_size_duplicate(variant: dict[str, Any]) -> None:
    size_value = clean_text(variant.get("size"))
    color_value = clean_text(variant.get("color"))
    if not size_value or not color_value:
        return
    option_values = variant.get("option_values")
    if isinstance(option_values, dict) and clean_text(option_values.get("size")):
        return
    if not size_value.isdigit():
        return
    color_tokens = color_value.split()
    if len(color_tokens) < _SHADE_CODE_COLOR_MIN_TOKENS:
        return
    if color_tokens[0].casefold() != size_value:
        return
    variant.pop("size", None)


def _normalize_separate_dimension_size_rows(record: dict[str, Any]) -> None:
    variants = record.get("variants")
    if not isinstance(variants, list) or len(variants) < 2:
        return
    rows = [variant for variant in variants if isinstance(variant, dict)]
    if not rows or any(clean_text(row.get("color")) for row in rows):
        return
    size_values = [clean_text(row.get("size")) for row in rows if clean_text(row.get("size"))]
    if len(size_values) < 2:
        return
    separate_family_hits = [
        sum(1 for value in size_values if pattern.fullmatch(value))
        for pattern, _label in _VARIANT_SEPARATE_DIMENSION_SIZE_RULES
    ]
    if sum(1 for count in separate_family_hits if count >= 2) < 2:
        return
    relabeled_rows: list[dict[str, Any]] = []
    for row in rows:
        relabeled = dict(row)
        size_value = clean_text(relabeled.get("size"))
        style_label = _separate_dimension_style_label(size_value)
        if style_label and size_value:
            option_values = relabeled.get("option_values")
            relabeled["option_values"] = (
                dict(option_values) if isinstance(option_values, dict) else {}
            )
            relabeled["option_values"]["style"] = style_label
            relabeled["option_values"]["size"] = size_value
        relabeled_rows.append(relabeled)
    record["variants"] = relabeled_rows
    record["variant_count"] = len(relabeled_rows)


def _separate_dimension_style_label(size_value: str) -> str:
    for pattern, label in _VARIANT_SEPARATE_DIMENSION_SIZE_RULES:
        if pattern.fullmatch(size_value):
            return label
    return ""

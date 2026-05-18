from __future__ import annotations

from app.services.extract.variant_normalization.common import (
    Any,
    clean_text,
    gender_possessive_re as _GENDER_POSSESSIVE_RE,
    standard_size_values as _STANDARD_SIZE_VALUES,
    text_or_none,
    unquote,
    urlparse,
    variant_sku_size_suffix_patterns as _VARIANT_SKU_SIZE_SUFFIX_PATTERNS,
)
from app.services.extract.variant_normalization import size_color_extraction

__all__ = (
    "_hydrate_variant_axes",
    "_infer_variant_sizes_from_titles",
    "_infer_variant_sizes_from_skus",
    "_infer_single_variant_axes",
    "_variant_size_from_title_or_url",
    "_variant_size_from_sku",
    "_url_terminal_text",
)


def _hydrate_variant_axes(record: dict[str, Any]) -> None:
    _infer_variant_sizes_from_titles(record)
    _infer_variant_sizes_from_skus(record)
    _infer_single_variant_axes(record)


def _infer_variant_sizes_from_titles(record: dict[str, Any]) -> None:
    variants = record.get("variants")
    if not isinstance(variants, list) or len(variants) < 2:
        return
    inferred_by_index: dict[int, str] = {}
    for index, variant in enumerate(variants):
        if not isinstance(variant, dict) or clean_text(variant.get("size")):
            continue
        size_value = _variant_size_from_title_or_url(variant, record=record)
        if size_value:
            inferred_by_index[index] = size_value
    unique_values: list[str] = []
    seen: set[str] = set()
    for value in inferred_by_index.values():
        lowered = value.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        unique_values.append(value)
    if len(unique_values) < 2:
        return
    for index, size_value in inferred_by_index.items():
        variant = variants[index]
        if isinstance(variant, dict) and variant.get("size") in (None, "", [], {}):
            variant["size"] = size_value


def _infer_variant_sizes_from_skus(record: dict[str, Any]) -> None:
    variants = record.get("variants")
    if not isinstance(variants, list) or len(variants) < 2:
        return
    inferred_by_index: dict[int, str] = {}
    for index, variant in enumerate(variants):
        if not isinstance(variant, dict) or clean_text(variant.get("size")):
            continue
        size_value = _variant_size_from_sku(variant.get("sku"))
        if size_value:
            inferred_by_index[index] = size_value
    unique_values = {
        value.casefold() for value in inferred_by_index.values() if clean_text(value)
    }
    if len(unique_values) < 2:
        return
    for index, size_value in inferred_by_index.items():
        variant = variants[index]
        if isinstance(variant, dict) and variant.get("size") in (None, "", [], {}):
            variant["size"] = size_value


def _infer_single_variant_axes(record: dict[str, Any]) -> None:
    variants = record.get("variants")
    if not isinstance(variants, list) or len(variants) != 1:
        return
    variant = variants[0]
    if not isinstance(variant, dict):
        return
    if not clean_text(variant.get("size")):
        size_value = _variant_size_from_title_or_url(variant, record=record)
        if size_value:
            variant["size"] = size_value
    if not clean_text(variant.get("color")):
        color_value = size_color_extraction._variant_color_from_title_or_url(
            variant,
            record=record,
        )
        if color_value:
            variant["color"] = color_value


def _variant_size_from_title_or_url(
    variant: dict[str, Any],
    *,
    record: dict[str, Any],
) -> str:
    candidates = [
        (variant.get("title"), False),
        (variant.get("name"), False),
        (record.get("title"), True),
        (_url_terminal_text(variant.get("url")), False),
        (_url_terminal_text(record.get("url")), False),
    ]
    record_title = clean_text(record.get("title")).casefold()
    for candidate, allow_record_title in candidates:
        text = clean_text(candidate)
        if not text:
            continue
        if not allow_record_title and record_title and text.casefold() == record_title:
            continue
        extracted = size_color_extraction._extract_size_value(text)
        if (
            extracted
            and extracted.lower() in _STANDARD_SIZE_VALUES
            and _GENDER_POSSESSIVE_RE is not None
            and _GENDER_POSSESSIVE_RE.search(text)
        ):
            continue
        if extracted:
            return extracted
    return ""


def _variant_size_from_sku(value: object) -> str:
    sku = clean_text(value)
    if not sku:
        return ""
    for pattern in _VARIANT_SKU_SIZE_SUFFIX_PATTERNS:
        match = pattern.search(sku)
        if match is None:
            continue
        size_value = clean_text(match.groupdict().get("size") or match.group(0))
        if size_value:
            return size_value.upper()
    return ""


def _url_terminal_text(value: object) -> str:
    text = text_or_none(value)
    if not text:
        return ""
    parsed = urlparse(text)
    parts = [part for part in str(parsed.path or "").split("/") if part]
    if not parts:
        return ""
    return clean_text(unquote(parts[-1]).replace("-", " ").replace("_", " "))

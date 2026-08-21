# ruff: noqa: E402, F401, F821, F822
from __future__ import annotations

__all__ = (
    "document_link_label_patterns",
    "fulfillment_only_long_text_phrases",
    "fulfillment_long_text_patterns",
    "guide_glossary_text_patterns",
    "guide_glossary_heading_tokens",
    "long_text_disclaimer_patterns",
    "low_signal_title_values",
    "low_signal_long_text_values",
    "materials_pollution_tokens",
    "low_signal_product_type_values",
    "detail_artifact_product_type_patterns",
    "cross_product_text_type_tokens",
    "cross_product_text_generic_tokens",
    "title_dimension_size_re",
    "tracking_token_re",
    "cookie_disclosure_text_patterns",
    "low_signal_numeric_size_max",
    "artifact_price_values",
    "feature_row_noise_patterns",
    "detail_title_value_is_low_signal",
    "detail_product_type_is_low_signal",
    "detail_scalar_size_is_low_signal",
    "detail_candidate_is_valid",
    "sanitize_detail_long_text_fields",
    "sanitize_detail_long_text",
    "sanitize_detail_features",
    "detail_long_text_chunk_looks_truncated",
    "detail_long_text_chunk_is_variant_size_sequence",
    "detail_long_text_is_numeric_sequence",
    "detail_long_text_is_fulfillment_only",
    "detail_long_text_is_guide_or_glossary_dump",
    "detail_long_text_is_cookie_disclosure_dump",
    "detail_long_text_chunk_is_legal_tail",
    "detail_long_text_chunk_is_document_label",
    "detail_long_text_is_document_label_cluster",
    "detail_long_text_chunk_is_variant_title",
    "detail_long_text_chunk_is_other_product",
    "detail_product_text_tokens",
    "detail_long_text_chunk_has_product_name_shape",
)

import ast
import json
import re
from collections.abc import Iterable
from typing import Any

from app.services.config.extraction_rules import (
    DETAIL_ARTIFACT_IDENTIFIER_VALUES,
    DETAIL_ARTIFACT_PRICE_VALUES,
    DETAIL_ARTIFACT_PRODUCT_TYPE_PATTERNS,
    DETAIL_ARTIFACT_PRODUCT_TYPE_VALUES,
    DETAIL_ARTIFACT_SKU_PREFIXES,
    DETAIL_BRACKET_PROSE_MIN_WORDS,
    DETAIL_CATEGORY_UI_TOKENS,
    DETAIL_COOKIE_DISCLOSURE_TEXT_PATTERNS,
    DETAIL_CROSS_PRODUCT_TEXT_GENERIC_TOKENS,
    DETAIL_CROSS_PRODUCT_TEXT_TYPE_TOKENS,
    DETAIL_DOCUMENT_LINK_LABEL_PATTERNS,
    DETAIL_FULFILLMENT_ONLY_LONG_TEXT_PHRASES,
    DETAIL_FULFILLMENT_LONG_TEXT_PATTERNS,
    DETAIL_GUIDE_GLOSSARY_HEADING_MIN_HITS,
    DETAIL_GUIDE_GLOSSARY_HEADING_TOKENS,
    DETAIL_GUIDE_GLOSSARY_TEXT_PATTERNS,
    DETAIL_LOW_SIGNAL_LONG_TEXT_VALUES,
    DETAIL_LOW_SIGNAL_NUMERIC_SIZE_MAX,
    DETAIL_LOW_SIGNAL_PRODUCT_TYPE_VALUES,
    DETAIL_LOW_SIGNAL_TITLE_VALUES,
    DETAIL_LEGAL_TAIL_PATTERNS,
    DETAIL_LONG_TEXT_DISCLAIMER_PATTERNS,
    DETAIL_LONG_TEXT_LEADING_ATTRIBUTE_BLOB_PATTERN,
    DETAIL_LONG_TEXT_REPEATED_PROMPTS,
    DETAIL_LONG_TEXT_SUBSTRING_REMOVE_PATTERNS,
    DETAIL_LONG_TEXT_TRUNCATED_TAIL_TOKENS,
    DETAIL_LONG_TEXT_UI_TAIL_MIN_PRODUCT_WORDS,
    DETAIL_LONG_TEXT_UI_TAIL_PHRASES,
    DETAIL_MATERIALS_COMPOSITION_PATTERN,
    DETAIL_MATERIALS_EDITORIAL_HEAD_THRESHOLD,
    DETAIL_MATERIALS_EDITORIAL_LENGTH_THRESHOLD,
    DETAIL_MATERIALS_POLLUTION_TOKENS,
    DETAIL_MATERIALS_ZERO_PERCENT_PATTERN,
    DETAIL_NOISE_PREFIXES,
    DETAIL_TITLE_DIMENSION_SIZE_PATTERN,
    DETAIL_TRACKING_TOKEN_PATTERN,
    DETAIL_VARIANT_ARTIFACT_VALUE_TOKENS,
    DETAIL_VARIANT_SIZE_SEQUENCE_MIN_COUNT,
    FEATURE_ROW_NOISE_PATTERNS,
    LONG_TEXT_MAX_WORDS,
    LONG_TEXT_MIN_WORDS,
    LONG_TEXT_PREFIXES,
    TOKEN_MIN_LEN_CHUNK,
    TOKEN_MIN_LEN_DISTINCTIVE,
)
from app.services.config.detail_extraction_constants import MAX_STRUCTURED_TEXT_LENGTH
from app.services.shared.field_coerce import LONG_TEXT_FIELDS, clean_text, text_or_none
from app.services.shared.regex_patterns import compile_regex_patterns

document_link_label_patterns = compile_regex_patterns(DETAIL_DOCUMENT_LINK_LABEL_PATTERNS or ())
fulfillment_only_long_text_phrases = frozenset(
    clean_text(phrase).lower() for phrase in tuple(DETAIL_FULFILLMENT_ONLY_LONG_TEXT_PHRASES or ()) if clean_text(phrase)
)
fulfillment_long_text_patterns = compile_regex_patterns(DETAIL_FULFILLMENT_LONG_TEXT_PATTERNS or ())
guide_glossary_text_patterns = compile_regex_patterns(DETAIL_GUIDE_GLOSSARY_TEXT_PATTERNS or ())
guide_glossary_heading_tokens = frozenset(clean_text(value).lower() for value in tuple(DETAIL_GUIDE_GLOSSARY_HEADING_TOKENS or ()) if clean_text(value))
long_text_disclaimer_patterns = compile_regex_patterns(DETAIL_LONG_TEXT_DISCLAIMER_PATTERNS or ())
long_text_substring_remove_patterns = compile_regex_patterns(DETAIL_LONG_TEXT_SUBSTRING_REMOVE_PATTERNS or ())
long_text_repeated_prompts = tuple(clean_text(prompt) for prompt in tuple(DETAIL_LONG_TEXT_REPEATED_PROMPTS or ()) if clean_text(prompt))
low_signal_title_values = frozenset(clean_text(value).lower() for value in tuple(DETAIL_LOW_SIGNAL_TITLE_VALUES or ()) if clean_text(value))
low_signal_long_text_values = frozenset(clean_text(value).lower() for value in tuple(DETAIL_LOW_SIGNAL_LONG_TEXT_VALUES or ()) if clean_text(value))
materials_pollution_tokens = frozenset(clean_text(token).casefold() for token in tuple(DETAIL_MATERIALS_POLLUTION_TOKENS or ()) if clean_text(token))
_MATERIALS_ZERO_PERCENT_PATTERN = re.compile(str(DETAIL_MATERIALS_ZERO_PERCENT_PATTERN), re.I)
low_signal_product_type_values = frozenset(clean_text(value).lower() for value in tuple(DETAIL_LOW_SIGNAL_PRODUCT_TYPE_VALUES or ()) if clean_text(value))
detail_artifact_product_type_patterns = compile_regex_patterns(DETAIL_ARTIFACT_PRODUCT_TYPE_PATTERNS or ())
cross_product_text_type_tokens = frozenset(clean_text(value).lower() for value in tuple(DETAIL_CROSS_PRODUCT_TEXT_TYPE_TOKENS or ()) if clean_text(value))
cross_product_text_generic_tokens = frozenset(clean_text(value).lower() for value in tuple(DETAIL_CROSS_PRODUCT_TEXT_GENERIC_TOKENS or ()) if clean_text(value))
title_dimension_size_re = re.compile(str(DETAIL_TITLE_DIMENSION_SIZE_PATTERN), re.I)
tracking_token_re = re.compile(str(DETAIL_TRACKING_TOKEN_PATTERN), re.I)
cookie_disclosure_text_patterns = compile_regex_patterns(DETAIL_COOKIE_DISCLOSURE_TEXT_PATTERNS or ())
low_signal_numeric_size_max = int(DETAIL_LOW_SIGNAL_NUMERIC_SIZE_MAX)
_detail_noise_prefixes = tuple(clean_text(prefix).lower() for prefix in tuple(DETAIL_NOISE_PREFIXES or ()) if clean_text(prefix))
_DESCRIPTION_REPAIRED_FROM_PRODUCT_DETAILS = "_description_repaired_from_product_details"
_long_text_ui_tail_phrases = tuple(clean_text(phrase).lower() for phrase in tuple(DETAIL_LONG_TEXT_UI_TAIL_PHRASES or ()) if clean_text(phrase))
_long_text_ui_tail_min_product_words = int(DETAIL_LONG_TEXT_UI_TAIL_MIN_PRODUCT_WORDS)
_guide_glossary_heading_min_hits = int(DETAIL_GUIDE_GLOSSARY_HEADING_MIN_HITS)
_bracket_prose_min_words = int(DETAIL_BRACKET_PROSE_MIN_WORDS)
_long_text_min_words = int(LONG_TEXT_MIN_WORDS)
_long_text_max_words = int(LONG_TEXT_MAX_WORDS)
_token_min_len_distinctive = int(TOKEN_MIN_LEN_DISTINCTIVE)
_token_min_len_chunk = int(TOKEN_MIN_LEN_CHUNK)
_long_text_prefixes = tuple(clean_text(prefix).lower() for prefix in tuple(LONG_TEXT_PREFIXES or ()) if clean_text(prefix))
_legal_tail_patterns = DETAIL_LEGAL_TAIL_PATTERNS or {}
_legal_tail_contains = tuple(str(value) for value in _legal_tail_patterns.get("contains", ()))
_legal_tail_digit_contains = tuple(str(value) for value in _legal_tail_patterns.get("digit_contains", ()))
_legal_tail_exact = frozenset(str(value) for value in _legal_tail_patterns.get("exact", ()))

def _normalize_legal_tail_all_contains(value: object) -> tuple[tuple[str, ...], ...]:
    if isinstance(value, str):
        return ((value,),)
    if not isinstance(value, Iterable):
        return ()
    groups: list[tuple[str, ...]] = []
    for group in tuple(value):
        if isinstance(group, str):
            items = (group,)
        elif isinstance(group, Iterable):
            try:
                items = tuple(group)
            except TypeError as exc:
                raise ValueError("DETAIL_LEGAL_TAIL_PATTERNS all_contains must be strings") from exc
        else:
            raise ValueError("DETAIL_LEGAL_TAIL_PATTERNS all_contains must be strings")
        if not all(isinstance(item, str) for item in items):
            raise ValueError("DETAIL_LEGAL_TAIL_PATTERNS all_contains must be strings")
        groups.append(items)
    return tuple(groups)

_legal_tail_all_contains = _normalize_legal_tail_all_contains(_legal_tail_patterns.get("all_contains", ()))
artifact_price_values = frozenset(clean_text(v).lower() for v in tuple(DETAIL_ARTIFACT_PRICE_VALUES or ()) if clean_text(v))
feature_row_noise_patterns = compile_regex_patterns(FEATURE_ROW_NOISE_PATTERNS or ())

def detail_title_value_is_low_signal(value: object) -> bool:
    text = clean_text(value)
    return bool(text and text.lower() in low_signal_title_values)

def detail_product_type_is_low_signal(value: object) -> bool:
    text = clean_text(value)
    lowered = text.lower()
    return bool(
        lowered
        and (
            lowered in low_signal_product_type_values
            or lowered in DETAIL_ARTIFACT_PRODUCT_TYPE_VALUES
            or any(pattern.fullmatch(lowered) for pattern in detail_artifact_product_type_patterns)
        )
    )

def detail_scalar_size_is_low_signal(value: str, *, title: object) -> bool:
    if not value or not value.isdigit():
        return False
    try:
        numeric_value = int(value)
    except ValueError:
        return False
    return numeric_value <= low_signal_numeric_size_max and bool(title_dimension_size_re.search(clean_text(title)))

def detail_candidate_is_valid(
    field_name: str,
    value: object,
    *,
    source: str | None = None,
) -> bool:
    return not (
        _long_text_candidate_is_noise(field_name, value, source=source)
        or _title_candidate_is_artifact(field_name, value)
        or _category_candidate_is_noise(field_name, value)
        or _sku_candidate_is_artifact(field_name, value)
        or _identifier_candidate_is_artifact(field_name, value)
        or _product_type_candidate_is_artifact(field_name, value)
        or _price_candidate_is_artifact(field_name, value)
        or _variant_candidate_is_artifact(field_name, value)
    )

def _title_candidate_is_artifact(field_name: str, value: object) -> bool:
    return field_name == "title" and bool(tracking_token_re.fullmatch(clean_text(value)))

def _category_candidate_is_noise(field_name: str, value: object) -> bool:
    if field_name != "category":
        return False
    cleaned = clean_text(value)
    if not cleaned:
        return True
    parts = [clean_text(part).lower() for part in re.split(r">\s*|/+", cleaned) if clean_text(part)]
    if not parts or any(part in DETAIL_CATEGORY_UI_TOKENS for part in parts):
        return True
    lowered = f" {cleaned.lower()} "
    return any(
        f" {token} " in lowered
        for token in DETAIL_CATEGORY_UI_TOKENS
        if token != "..."  # nosec B105
    )

def _sku_candidate_is_artifact(field_name: str, value: object) -> bool:
    if field_name not in {"sku", "part_number", "product_id"}:
        return False
    cleaned = clean_text(value).lower()
    return bool(cleaned and any(cleaned.startswith(prefix) for prefix in DETAIL_ARTIFACT_SKU_PREFIXES))

def _identifier_candidate_is_artifact(field_name: str, value: object) -> bool:
    if field_name not in {"product_id", "part_number"}:
        return False
    cleaned = clean_text(value).lower()
    return bool(cleaned and cleaned in DETAIL_ARTIFACT_IDENTIFIER_VALUES)

def _product_type_candidate_is_artifact(field_name: str, value: object) -> bool:
    if field_name != "product_type":
        return False
    cleaned = clean_text(value).lower()
    return bool(
        cleaned and (cleaned in DETAIL_ARTIFACT_PRODUCT_TYPE_VALUES or any(pattern.fullmatch(cleaned) for pattern in detail_artifact_product_type_patterns))
    )

def _price_candidate_is_artifact(field_name: str, value: object) -> bool:
    if field_name not in {"price", "sale_price", "original_price"}:
        return False
    cleaned = clean_text(value).lower()
    if cleaned in artifact_price_values:
        return True
    if re.search(r"(^|[^\d])-\s*\d", cleaned):
        return True
    normalized = re.sub(r"[^0-9.]+", "", cleaned)
    if not normalized:
        return True
    try:
        return float(normalized) < 0
    except ValueError:
        return True

def _variant_candidate_is_artifact(field_name: str, value: object) -> bool:
    if field_name not in {"variants", "selected_variant", "variant_axes"}:
        return False
    return any(_variant_artifact_token_seen(item) for item in _walk_variant_values(value))

def _walk_variant_values(value: object) -> list[object]:
    if isinstance(value, dict):
        values: list[object] = list(value.keys())
        for item in value.values():
            values.extend(_walk_variant_values(item))
        return values
    if isinstance(value, list):
        return [nested for item in value for nested in _walk_variant_values(item)]
    return [value]

def _variant_artifact_token_seen(value: object) -> bool:
    text = clean_text(value).lower()
    return bool(text and (text in DETAIL_VARIANT_ARTIFACT_VALUE_TOKENS or re.fullmatch(r"\d+\s*%", text)))

def _long_text_candidate_is_noise(
    field_name: str,
    value: object,
    *,
    source: str | None = None,
) -> bool:
    if field_name not in LONG_TEXT_FIELDS:
        return False
    cleaned = clean_text(value)
    lowered = cleaned.lower()
    if not lowered or lowered in low_signal_long_text_values:
        return True
    if field_name in {"description", "specifications"} and lowered.startswith(_detail_noise_prefixes):
        return True
    tail_stripped = _strip_long_text_ui_tail(cleaned)
    if tail_stripped != cleaned:
        return len(tail_stripped.split()) < _long_text_ui_tail_min_product_words
    if (
        source == "dom_sections"
        and field_name in {"description", "specifications", "product_details"}
        and len(cleaned.split()) <= 4
        and not any(token in cleaned for token in ".:;!?\n")
    ):
        return True
    if any(pattern.search(cleaned) for pattern in guide_glossary_text_patterns):
        return True
    if detail_long_text_is_cookie_disclosure_dump(cleaned):
        return True
    return len(cleaned.split()) < 2

def sanitize_detail_long_text_fields(
    record: dict[str, Any],
    *,
    title_hint: str | None = None,
) -> None:
    record_title = clean_text(" ".join(value for value in (clean_text(record.get("title")), clean_text(title_hint)) if value))
    title_tokens = set(detail_product_text_tokens(clean_text(record.get("title"))))
    protected_identity_tokens = {
        token for token in detail_product_text_tokens(clean_text(title_hint)) if len(token) >= _token_min_len_chunk and token not in title_tokens
    }
    for field_name in LONG_TEXT_FIELDS:
        text = text_or_none(record.get(field_name))
        if not text:
            continue
        cleaned = sanitize_detail_long_text(
            text,
            title=record_title,
            protected_identity_tokens=protected_identity_tokens,
        )
        if cleaned:
            record[field_name] = cleaned
        else:
            record.pop(field_name, None)
    _trim_description_to_identity_hint(
        record,
        protected_identity_tokens=protected_identity_tokens,
    )
    description = clean_text(record.get("description")).casefold()
    specifications = clean_text(record.get("specifications")).casefold()
    if description and specifications and description == specifications:
        record.pop("specifications", None)
    materials = _clean_materials_pollution(record.get("materials"))
    if materials:
        record["materials"] = materials
    else:
        record.pop("materials", None)
    features = sanitize_detail_features(record.get("features"), title=record_title)
    if features:
        record["features"] = features
    else:
        record.pop("features", None)
    _repair_description_feature_duplicate(record)
    _drop_redundant_product_details(record)
    _promote_product_details_description(record)

def _repair_description_feature_duplicate(record: dict[str, Any]) -> None:
    description = clean_text(record.get("description"))
    raw_features_value = record.get("features")
    raw_features: list[Any] = raw_features_value if isinstance(raw_features_value, list) else []
    features = []
    for row in raw_features:
        cleaned = clean_text(row)
        if cleaned:
            features.append(cleaned)
    if not description or not features:
        return
    feature_text = clean_text(" ".join(features))
    if description.casefold() != feature_text.casefold():
        return
    product_details = sanitize_detail_long_text(
        clean_text(record.get("product_details")),
        title=clean_text(record.get("title")),
    )
    if product_details and product_details.casefold() != description.casefold():
        record["description"] = product_details
        record[_DESCRIPTION_REPAIRED_FROM_PRODUCT_DETAILS] = True
        return
    record.pop("description", None)

def _trim_description_to_identity_hint(
    record: dict[str, Any],
    *,
    protected_identity_tokens: set[str],
) -> None:
    description = clean_text(record.get("description"))
    if not description or not protected_identity_tokens:
        return
    chunks = [clean_text(chunk) for chunk in re.split(r"(?<=[.!?])\s+|\s+:\s+|\n+", description) if clean_text(chunk)]
    if not chunks:
        return
    kept: list[str] = []
    seen_identity = False
    for chunk in chunks:
        chunk_tokens = detail_product_text_tokens(chunk)
        has_identity = bool(protected_identity_tokens & chunk_tokens)
        if has_identity:
            seen_identity = True
            kept.append(chunk)
            continue
        if not seen_identity:
            continue
        if detail_long_text_chunk_has_product_name_shape(chunk) and _chunk_has_named_product_signal(chunk):
            break
        kept.append(chunk)
    if kept and len(kept) < len(chunks):
        record["description"] = " ".join(kept)

def _chunk_has_named_product_signal(chunk: str) -> bool:
    words = re.findall(r"[A-Za-z][A-Za-z'’-]*", str(chunk or ""))
    capitalized = [word for word in words[1:] if len(word) > 1 and word[:1].isupper() and word.casefold() not in {"this"}]
    return len(capitalized) >= 2

def _promote_product_details_description(record: dict[str, Any]) -> None:
    description = clean_text(record.get("description"))
    product_details = sanitize_detail_long_text(
        clean_text(record.get("product_details")),
        title=clean_text(record.get("title")),
    )
    if not product_details:
        return
    if not description:
        record["description"] = product_details
        return
    if product_details.casefold() == description.casefold():
        return
    product_word_count = len(product_details.split())
    description_word_count = len(description.split())
    if product_word_count <= description_word_count:
        return
    if description_word_count >= _long_text_min_words:
        return
    record["description"] = product_details

def _drop_redundant_product_details(record: dict[str, Any]) -> None:
    description = clean_text(record.get("description"))
    product_details = sanitize_detail_long_text(
        clean_text(record.get("product_details")),
        title=clean_text(record.get("title")),
    )
    if not description or not product_details:
        return
    if record.get(_DESCRIPTION_REPAIRED_FROM_PRODUCT_DETAILS) is True:
        return
    if description.casefold() != product_details.casefold():
        return
    record.pop("product_details", None)
    field_sources = record.get("_field_sources")
    if isinstance(field_sources, dict):
        field_sources.pop("product_details", None)

# skipcq: PY-R1000

from . import long_text_sanitization as _split_owner
globals().update({
    name: value
    for name, value in vars(_split_owner).items()
    if not name.startswith("__") and name != "_owner"
})

from __future__ import annotations

import logging
import re
from typing import Any
from urllib.parse import unquote, urlparse

from app.services.config.extraction_rules import (
    ADULT_SIZE_CONTEXT_TOKENS,
    COMMON_WORD_SIZE_VALUES,
    CURRENCY_CODES,
    GENDER_ARTIFACT_PATTERN,
    GENDER_KEYWORD_TOKENS,
    GENDER_POSSESSIVE_PATTERN,
    VARIANT_CHILD_SIZE_PATTERNS,
    VARIANT_COLOR_HINT_WORDS,
    VARIANT_CONDITION_HEADER_PREFIXES,
    VARIANT_OPTION_LABEL_MAX_WORDS,
    VARIANT_OPTION_VALUE_SUFFIX_NOISE_PATTERNS,
    VARIANT_PLACEHOLDER_PREFIXES,
    VARIANT_PLACEHOLDER_VALUES,
    SCALAR_FIELD_MAX_OPTION_TOKENS,
    SHADE_CODE_COLOR_MIN_TOKENS,
    SCALAR_FIELD_POLLUTION_VALUES,
    VARIANT_SEPARATE_DIMENSION_SIZE_RULES,
    VARIANT_SKU_SIZE_SUFFIX_PATTERNS,
    VARIANT_SIZE_QUANTITY_CONTROL_VALUES,
    VARIANT_SIZE_VALUE_PATTERNS,
    VARIANT_SIZE_VALUE_EXTRACT_PATTERNS,
    STANDARD_SIZE_VALUES,
    VARIANT_TITLE_STOPWORDS,
)
from app.services.config.variant_policy import (
    FLAT_VARIANT_KEYS,
    PUBLIC_VARIANT_AXIS_FIELDS,
)
from app.services.shared.field_coerce import (
    clean_text,
    enforce_flat_variant_public_contract,
    extract_currency_code,
    flatten_variants_for_public_output,
    text_or_none,
)
from app.services.extract.variant_identity_merge import (
    collapse_duplicate_size_aliases,
    merge_variant_pair,
    variant_identity,
    variant_row_richness,
    variant_semantic_identity,
)
from app.services.extract.variant_choice_traversal import (
    infer_variant_group_name_from_values,
)
from app.services.extract.variant_axis import normalized_variant_axis_key
from app.services.extract.variant_option_value import variant_option_value_is_noise
from app.services.extract.variant_structural_pruning import (
    drop_color_only_rows_when_size_rows_exist,
    drop_cross_product_variant_rows,
    drop_parent_shared_variant_axes,
    drop_parent_sku_alias_variant_rows,
    drop_subset_variants_when_richer_alternative_exists,
    prune_axisless_rows_when_axisful_rows_exist,
    prune_low_signal_numeric_only_variants,
)
from app.services.extract.variant_value_guards import (
    drop_invalid_variant_urls,
    variant_axis_value_exceeds_word_limit,
)

logger = logging.getLogger(__name__)

try:
    _SCALAR_FIELD_MAX_OPTION_TOKENS = max(1, int(SCALAR_FIELD_MAX_OPTION_TOKENS))
except (TypeError, ValueError):
    _SCALAR_FIELD_MAX_OPTION_TOKENS = 6

try:
    _SHADE_CODE_COLOR_MIN_TOKENS = max(2, int(SHADE_CODE_COLOR_MIN_TOKENS))
except (TypeError, ValueError):
    _SHADE_CODE_COLOR_MIN_TOKENS = 2

_VARIANT_SIZE_VALUE_EXTRACT_PATTERNS = tuple(
    re.compile(str(pattern), re.I)
    for pattern in tuple(VARIANT_SIZE_VALUE_EXTRACT_PATTERNS or ())
    if str(pattern).strip()
)
_VARIANT_SIZE_VALUE_PATTERNS = tuple(
    re.compile(str(pattern), re.I)
    for pattern in tuple(VARIANT_SIZE_VALUE_PATTERNS or ())
    if str(pattern).strip()
)
_VARIANT_COLOR_HINT_WORDS = frozenset(
    clean_text(value).lower()
    for value in tuple(VARIANT_COLOR_HINT_WORDS or ())
    if clean_text(value)
)
_CURRENCY_CODES_UPPER = frozenset(
    str(code).upper() for code in tuple(CURRENCY_CODES or ()) if str(code).strip()
)
_VARIANT_OPTION_VALUE_SUFFIX_NOISE_PATTERNS = tuple(
    re.compile(str(pattern), re.I)
    for pattern in tuple(VARIANT_OPTION_VALUE_SUFFIX_NOISE_PATTERNS or ())
    if str(pattern).strip()
)
_VARIANT_PLACEHOLDER_VALUES_SET = frozenset(
    clean_text(value).lower()
    for value in tuple(VARIANT_PLACEHOLDER_VALUES or ())
    if clean_text(value)
)
_VARIANT_PLACEHOLDER_PREFIXES_LOWER = tuple(
    clean_text(prefix).lower()
    for prefix in tuple(VARIANT_PLACEHOLDER_PREFIXES or ())
    if clean_text(prefix)
)
_VARIANT_SIZE_QUANTITY_CONTROL_VALUES = frozenset(
    clean_text(value).lower()
    for value in tuple(VARIANT_SIZE_QUANTITY_CONTROL_VALUES or ())
    if clean_text(value)
)
try:
    _VARIANT_OPTION_LABEL_MAX_WORDS = max(1, int(VARIANT_OPTION_LABEL_MAX_WORDS))
except (TypeError, ValueError):
    _VARIANT_OPTION_LABEL_MAX_WORDS = 6
_OPTION_FIELD_PATTERN = re.compile(r"option\d+_(?:name|values?)")
_GENDER_ARTIFACT_PATTERN = str(GENDER_ARTIFACT_PATTERN or "")
_GENDER_ARTIFACT_RE = (
    re.compile(
        _GENDER_ARTIFACT_PATTERN.format(candidate=r"[a-z0-9.]+"),
        re.I,
    )
    if _GENDER_ARTIFACT_PATTERN
    else None
)
_GENDER_POSSESSIVE_RE = (
    re.compile(str(GENDER_POSSESSIVE_PATTERN), re.I)
    if GENDER_POSSESSIVE_PATTERN
    else None
)
_STANDARD_SIZE_VALUES = frozenset(
    str(value).lower() for value in tuple(STANDARD_SIZE_VALUES or ())
)
_COMMON_WORD_SIZE_VALUES = frozenset(
    clean_text(value).lower()
    for value in tuple(COMMON_WORD_SIZE_VALUES or ())
    if clean_text(value)
)
_VARIANT_TITLE_STOPWORDS = frozenset(
    clean_text(token).lower()
    for token in tuple(VARIANT_TITLE_STOPWORDS or ())
    if clean_text(token)
)
_GENDER_KEYWORD_TOKENS_SET = frozenset(
    clean_text(token).lower()
    for token in tuple(GENDER_KEYWORD_TOKENS or ())
    if clean_text(token)
)
_ADULT_SIZE_CONTEXT_TOKENS = frozenset(
    clean_text(token).lower()
    for token in tuple(ADULT_SIZE_CONTEXT_TOKENS or ())
    if clean_text(token)
)
_VARIANT_CHILD_SIZE_PATTERNS = tuple(
    re.compile(str(pattern), re.I)
    for pattern in tuple(VARIANT_CHILD_SIZE_PATTERNS or ())
    if str(pattern).strip()
)
_VARIANT_SKU_SIZE_SUFFIX_PATTERNS = tuple(
    re.compile(str(pattern), re.I)
    for pattern in tuple(VARIANT_SKU_SIZE_SUFFIX_PATTERNS or ())
    if str(pattern).strip()
)
_VARIANT_CONDITION_HEADER_PREFIXES = frozenset(
    clean_text(token).lower()
    for token in tuple(VARIANT_CONDITION_HEADER_PREFIXES or ())
    if clean_text(token)
)
_VARIANT_SEPARATE_DIMENSION_SIZE_RULES = tuple(
    (re.compile(str(rule.get("pattern")), re.I), clean_text(rule.get("style")))
    for rule in tuple(VARIANT_SEPARATE_DIMENSION_SIZE_RULES or ())
    if isinstance(rule, dict)
    and str(rule.get("pattern") or "").strip()
    and clean_text(rule.get("style"))
)
_LEGACY_VARIANT_KEYS = ("selected_variant", "variant_axes", "available_sizes")
_PUBLIC_VARIANT_AXIS_FIELDS = tuple(
    str(field_name).strip().lower()
    for field_name in tuple(PUBLIC_VARIANT_AXIS_FIELDS or ())
    if str(field_name).strip()
)
_SCALAR_FIELD_POLLUTION_VALUES = frozenset(
    clean_text(value).casefold()
    for value in tuple(SCALAR_FIELD_POLLUTION_VALUES or ())
    if clean_text(value)
)

scalar_field_max_option_tokens = _SCALAR_FIELD_MAX_OPTION_TOKENS
shade_code_color_min_tokens = _SHADE_CODE_COLOR_MIN_TOKENS
variant_size_value_extract_patterns = _VARIANT_SIZE_VALUE_EXTRACT_PATTERNS
variant_size_value_patterns = _VARIANT_SIZE_VALUE_PATTERNS
variant_color_hint_words = _VARIANT_COLOR_HINT_WORDS
currency_codes_upper = _CURRENCY_CODES_UPPER
variant_option_value_suffix_noise_patterns_normalized = (
    _VARIANT_OPTION_VALUE_SUFFIX_NOISE_PATTERNS
)
variant_placeholder_values_set = _VARIANT_PLACEHOLDER_VALUES_SET
variant_placeholder_prefixes_lower = _VARIANT_PLACEHOLDER_PREFIXES_LOWER
variant_size_quantity_control_values = _VARIANT_SIZE_QUANTITY_CONTROL_VALUES
variant_option_label_max_words = _VARIANT_OPTION_LABEL_MAX_WORDS
gender_artifact_pattern = _GENDER_ARTIFACT_PATTERN
gender_artifact_re = _GENDER_ARTIFACT_RE
gender_possessive_re = _GENDER_POSSESSIVE_RE
standard_size_values = _STANDARD_SIZE_VALUES
common_word_size_values = _COMMON_WORD_SIZE_VALUES
variant_title_stopwords = _VARIANT_TITLE_STOPWORDS
gender_keyword_tokens_set = _GENDER_KEYWORD_TOKENS_SET
adult_size_context_tokens = _ADULT_SIZE_CONTEXT_TOKENS
variant_child_size_patterns = _VARIANT_CHILD_SIZE_PATTERNS
variant_sku_size_suffix_patterns = _VARIANT_SKU_SIZE_SUFFIX_PATTERNS
variant_condition_header_prefixes = _VARIANT_CONDITION_HEADER_PREFIXES
variant_separate_dimension_size_rules = _VARIANT_SEPARATE_DIMENSION_SIZE_RULES
legacy_variant_keys = _LEGACY_VARIANT_KEYS
option_field_pattern = _OPTION_FIELD_PATTERN
public_variant_axis_fields_normalized = _PUBLIC_VARIANT_AXIS_FIELDS
scalar_field_pollution_values = _SCALAR_FIELD_POLLUTION_VALUES

__all__ = (
    "annotations",
    "logging",
    "re",
    "Any",
    "unquote",
    "urlparse",
    "ADULT_SIZE_CONTEXT_TOKENS",
    "COMMON_WORD_SIZE_VALUES",
    "CURRENCY_CODES",
    "GENDER_ARTIFACT_PATTERN",
    "GENDER_KEYWORD_TOKENS",
    "GENDER_POSSESSIVE_PATTERN",
    "VARIANT_CHILD_SIZE_PATTERNS",
    "VARIANT_COLOR_HINT_WORDS",
    "VARIANT_CONDITION_HEADER_PREFIXES",
    "VARIANT_OPTION_LABEL_MAX_WORDS",
    "VARIANT_OPTION_VALUE_SUFFIX_NOISE_PATTERNS",
    "VARIANT_PLACEHOLDER_PREFIXES",
    "VARIANT_PLACEHOLDER_VALUES",
    "SCALAR_FIELD_MAX_OPTION_TOKENS",
    "SHADE_CODE_COLOR_MIN_TOKENS",
    "SCALAR_FIELD_POLLUTION_VALUES",
    "VARIANT_SEPARATE_DIMENSION_SIZE_RULES",
    "VARIANT_SKU_SIZE_SUFFIX_PATTERNS",
    "VARIANT_SIZE_QUANTITY_CONTROL_VALUES",
    "VARIANT_SIZE_VALUE_PATTERNS",
    "VARIANT_SIZE_VALUE_EXTRACT_PATTERNS",
    "STANDARD_SIZE_VALUES",
    "VARIANT_TITLE_STOPWORDS",
    "FLAT_VARIANT_KEYS",
    "PUBLIC_VARIANT_AXIS_FIELDS",
    "clean_text",
    "enforce_flat_variant_public_contract",
    "extract_currency_code",
    "flatten_variants_for_public_output",
    "text_or_none",
    "collapse_duplicate_size_aliases",
    "merge_variant_pair",
    "variant_identity",
    "variant_row_richness",
    "variant_semantic_identity",
    "infer_variant_group_name_from_values",
    "normalized_variant_axis_key",
    "variant_option_value_is_noise",
    "drop_color_only_rows_when_size_rows_exist",
    "drop_cross_product_variant_rows",
    "drop_parent_shared_variant_axes",
    "drop_parent_sku_alias_variant_rows",
    "drop_subset_variants_when_richer_alternative_exists",
    "prune_axisless_rows_when_axisful_rows_exist",
    "prune_low_signal_numeric_only_variants",
    "drop_invalid_variant_urls",
    "variant_axis_value_exceeds_word_limit",
    "logger",
    "scalar_field_max_option_tokens",
    "shade_code_color_min_tokens",
    "variant_size_value_extract_patterns",
    "variant_size_value_patterns",
    "variant_color_hint_words",
    "currency_codes_upper",
    "variant_option_value_suffix_noise_patterns_normalized",
    "variant_placeholder_values_set",
    "variant_placeholder_prefixes_lower",
    "variant_size_quantity_control_values",
    "variant_option_label_max_words",
    "gender_artifact_pattern",
    "gender_artifact_re",
    "gender_possessive_re",
    "standard_size_values",
    "common_word_size_values",
    "variant_title_stopwords",
    "gender_keyword_tokens_set",
    "adult_size_context_tokens",
    "variant_child_size_patterns",
    "variant_sku_size_suffix_patterns",
    "variant_condition_header_prefixes",
    "variant_separate_dimension_size_rules",
    "legacy_variant_keys",
    "option_field_pattern",
    "public_variant_axis_fields_normalized",
    "scalar_field_pollution_values",
    "variant_has_axis_value",
    "variant_title_tokens",
    "url_terminal_text",
)


def _variant_has_axis_value(variant: dict[str, Any]) -> bool:
    return any(clean_text(variant.get(axis)) for axis in _PUBLIC_VARIANT_AXIS_FIELDS)


def _variant_title_tokens(value: object) -> set[str]:
    text = clean_text(value).lower()
    if not text:
        return set()
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text)
        if token not in _VARIANT_TITLE_STOPWORDS
    }


def _url_terminal_text(value: object) -> str:
    text = clean_text(value)
    if not text:
        return ""
    parsed = urlparse(text)
    path = parsed.path if parsed.scheme or parsed.netloc else text
    terminal = path.rstrip("/").rsplit("/", 1)[-1]
    return clean_text(unquote(terminal).replace("-", " ").replace("_", " "))


variant_has_axis_value = _variant_has_axis_value
variant_title_tokens = _variant_title_tokens
url_terminal_text = _url_terminal_text

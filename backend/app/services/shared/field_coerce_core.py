"""Shared field coercion primitives exported to the coercion owners."""

from __future__ import annotations

import ast
import json
import re
from typing import Any
from app.services.extraction_html_helpers import html_to_text
from app.services.config.extraction_rules import (
    AVAILABILITY_URL_MAP,
    COLOR_KEYWORD_PATTERN,
    IMAGE_FIELDS as IMAGE_FIELDS,
    INTEGER_VALUE_FIELDS,
    LISTING_UTILITY_TITLE_PATTERNS,
    NOISY_PRODUCT_ATTRIBUTE_KEYS,
    OPTION_VALUE_NOISE_WORDS,
    PRICE_VALUE_FIELDS,
    REVIEW_COUNT_RE as _REVIEW_COUNT_RE,
    SIZE_REJECT_TOKENS,
    SMALL_NUMERIC_PATTERN,
    STRUCTURED_MULTI_FIELDS,
    STRUCTURED_OBJECT_FIELDS,
    STRUCTURED_OBJECT_LIST_FIELDS,
    TRACKING_PIXEL_PATTERN,
    URL_FIELDS as URL_FIELDS,
    VARIANT_COLOR_CODELIKE_TOKEN_PATTERN,
    VARIANT_OPTION_VALUE_SUFFIX_NOISE_PATTERNS,
)
from app.services.config.field_mappings import (
    CANONICAL_SCHEMAS,
    ADDITIONAL_IMAGES_FIELD,
    FIELD_ALIASES,
    URL_FIELD,
)
from app.services.config.design_system import (
    DESIGN_SYSTEM_PUBLIC_FIELDS,
    DESIGN_SYSTEM_SURFACE,
)
from app.services.config.public_record_policy import (
    PUBLIC_RECORD_ECOMMERCE_DROPPED_FIELDS,
    PUBLIC_RECORD_LEGACY_VARIANT_FIELDS,
    PUBLIC_RECORD_PRODUCT_TYPE_NOISE_TOKENS,
)
from app.services.config.surface_hints import detail_path_hints
from app.services.field_policy import (
    exact_requested_field_key,
    expand_requested_fields,
    get_surface_field_aliases,
    normalize_field_key,
)
from app.services.shared.coerce_primitives import (
    coerce_int as _coerce_int,
    is_blank,
    object_dict as _object_dict,
    object_list as _object_list,
    safe_int as _safe_int,
)
from app.services.shared.text_coerce import (
    clean_text,
    coerce_literal_text_list,
    coerce_text,
    is_title_noise as is_title_noise,
    strip_html_tags as strip_html_tags,
)
from app.services.shared.field_coerce_price import (
    CURRENCY_CODE_PATTERN,
    CURRENCY_SYMBOL_PATTERN,
    PRICE_RE as PRICE_RE,
    decimal_for_shared_price,
    extract_price_text as extract_price_text,
)
from app.services.shared.field_coerce_text import (
    infer_brand_from_product_url as infer_brand_from_product_url,
    infer_brand_from_title_marker as infer_brand_from_title_marker,
)
from app.services.shared.field_coerce_url import (
    absolute_url as absolute_url,
    extract_urls as extract_urls,
    same_host as same_host,
    strip_tracking_query_params as strip_tracking_query_params,
)
from app.services.shared.regex_patterns import compile_regex_patterns

REVIEW_COUNT_RE = _REVIEW_COUNT_RE
_decimal_for_shared_price = decimal_for_shared_price

__all__ = (
    "IMAGE_FIELDS",
    "URL_FIELDS",
    "PRICE_RE",
    "absolute_url",
    "clean_text",
    "extract_price_text",
    "extract_urls",
    "infer_brand_from_product_url",
    "infer_brand_from_title_marker",
    "is_title_noise",
    "same_host",
    "strip_html_tags",
    "strip_tracking_query_params",
)

PRODUCT_URL_HINTS = detail_path_hints("ecommerce_detail")
JOB_URL_HINTS = detail_path_hints("job_detail")
_FIELD_ALIASES = FIELD_ALIASES
_OPTION_VALUE_SUFFIX_NOISE_RE = compile_regex_patterns(VARIANT_OPTION_VALUE_SUFFIX_NOISE_PATTERNS or ())
_OPTION_VALUE_NOISE_WORD_PATTERN = "|".join(re.escape(str(word)) for word in tuple(OPTION_VALUE_NOISE_WORDS or ()) if str(word).strip())
ALL_CANONICAL_FIELDS = sorted({field_name for fields in CANONICAL_SCHEMAS.values() for field_name in fields or [] if field_name})
_PRICE_FIELD_NAMES = PRICE_VALUE_FIELDS
_INTEGER_FIELD_NAMES = INTEGER_VALUE_FIELDS
_NOISY_PRODUCT_ATTRIBUTE_KEYS = frozenset(normalize_field_key(str(key or "")) for key in tuple(NOISY_PRODUCT_ATTRIBUTE_KEYS or ()) if str(key or "").strip())
_SMALL_NUMERIC_RE = re.compile(str(SMALL_NUMERIC_PATTERN), re.I)
_TRACKING_PIXEL_RE = re.compile(str(TRACKING_PIXEL_PATTERN), re.I)
_COLOR_KEYWORD_RE = re.compile(str(COLOR_KEYWORD_PATTERN), re.I)
_variant_color_codelike_token_re = re.compile(str(VARIANT_COLOR_CODELIKE_TOKEN_PATTERN), re.I)
size_reject_tokens_normalized: frozenset[str] = frozenset(str(token).strip().lower() for token in tuple(SIZE_REJECT_TOKENS or ()) if str(token).strip())

object_list = _object_list
object_dict = _object_dict
safe_int = _safe_int
coerce_int = _coerce_int

LISTING_UTILITY_TITLE_REGEXES = tuple(re.compile(pattern, re.I) for pattern in LISTING_UTILITY_TITLE_PATTERNS)
_AVAILABILITY_CANONICAL_ENUM = frozenset(str(v) for v in dict(AVAILABILITY_URL_MAP or {}).values() if v)
_HTML_ENTITY_RE = re.compile(r"&(?:#\d+|#x[0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]+);")
_product_type_noise_tokens = frozenset(str(token).casefold() for token in tuple(PUBLIC_RECORD_PRODUCT_TYPE_NOISE_TOKENS or ()))

def clean_record(record: dict[str, Any]) -> dict[str, Any]:
    return {str(key): value for key, value in record.items() if not is_blank(value)}

def _surface_field_type_error(
    *,
    field_name: str,
    normalized_field: str,
    value: object,
    scalar_list_fields: set[str],
) -> str | None:
    if normalized_field in STRUCTURED_OBJECT_LIST_FIELDS and not isinstance(value, list):
        return f"{field_name} expected list"
    if normalized_field in STRUCTURED_OBJECT_FIELDS and not isinstance(value, dict):
        return f"{field_name} expected object"
    if (
        normalized_field not in STRUCTURED_OBJECT_FIELDS
        and normalized_field not in STRUCTURED_OBJECT_LIST_FIELDS
        and not (normalized_field in scalar_list_fields and isinstance(value, list))
        and isinstance(value, (dict, list, set, frozenset))
    ):
        return f"{field_name} expected scalar"
    return None

def validate_record_for_surface(
    record: dict[str, Any],
    surface: str,
    *,
    requested_fields: list[str] | None = None,
    strict_types: bool = False,
) -> tuple[dict[str, Any], list[str]]:
    if str(surface or "").strip().lower() == DESIGN_SYSTEM_SURFACE:
        allowed = set(DESIGN_SYSTEM_PUBLIC_FIELDS)
        return {key: value for key, value in dict(record or {}).items() if str(key).startswith("_") or (key in allowed and not is_blank(value))}, []
    logical_fields, internal_fields = _partition_record_fields(record)
    allowed_fields = {
        normalize_field_key(field_name)
        for field_name in surface_fields(
            surface,
            requested_fields,
            allow_noncanonical_requested=False,
        )
    }
    validated_fields, validation_errors = _validated_surface_fields(logical_fields, allowed_fields=allowed_fields, strict_types=strict_types)
    if str(surface or "").strip().lower().startswith("ecommerce_"):
        for field_name in (
            *tuple(PUBLIC_RECORD_ECOMMERCE_DROPPED_FIELDS or ()),
            *tuple(PUBLIC_RECORD_LEGACY_VARIANT_FIELDS or ()),
        ):
            validated_fields.pop(str(field_name), None)
    return {
        **clean_record(validated_fields),
        **internal_fields,
    }, validation_errors

def _partition_record_fields(
    record: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    logical: dict[str, Any] = {}
    internal: dict[str, Any] = {}
    for key, value in dict(record).items():
        (internal if str(key).startswith("_") else logical)[key] = value
    return logical, internal

def _validated_surface_fields(
    logical_fields: dict[str, Any],
    *,
    allowed_fields: set[str],
    strict_types: bool,
) -> tuple[dict[str, Any], list[str]]:
    errors: list[str] = []
    validated: dict[str, Any] = {}
    scalar_list_fields = set(STRUCTURED_MULTI_FIELDS) | {ADDITIONAL_IMAGES_FIELD}
    for field_name, value in logical_fields.items():
        normalized = normalize_field_key(field_name)
        if normalized not in allowed_fields:
            continue
        type_error = (
            _surface_field_type_error(
                field_name=field_name,
                normalized_field=normalized,
                value=value,
                scalar_list_fields=scalar_list_fields,
            )
            if strict_types
            else None
        )
        if type_error:
            errors.append(type_error)
        else:
            validated[field_name] = value
    return validated, errors

def surface_fields(
    surface: str,
    requested_fields: list[str] | None,
    *,
    allow_noncanonical_requested: bool = True,
) -> list[str]:
    normalized_surface = str(surface or "").strip().lower()
    fields = list(CANONICAL_SCHEMAS.get(normalized_surface, ALL_CANONICAL_FIELDS))
    allowed_fields = set(ALL_CANONICAL_FIELDS)
    if URL_FIELD not in fields:
        fields.append(URL_FIELD)
    for field_name in requested_fields or []:
        exact_field = exact_requested_field_key(field_name)
        if exact_field and (allow_noncanonical_requested or exact_field in allowed_fields) and exact_field not in fields:
            fields.append(exact_field)
    for field_name in expand_requested_fields(requested_fields or []):
        if field_name and (allow_noncanonical_requested or field_name in allowed_fields) and field_name not in fields:
            fields.append(field_name)
    return fields

def surface_alias_lookup(
    surface: str,
    requested_fields: list[str] | None,
) -> dict[str, str]:
    """Build aliases with exact canonical field keys taking precedence."""
    fields = surface_fields(surface, requested_fields)
    aliases = get_surface_field_aliases(surface)
    lookup: dict[str, str] = {}
    for requested in requested_fields or []:
        normalized_requested = normalize_field_key(requested)
        exact_field = exact_requested_field_key(requested)
        if normalized_requested:
            lookup[normalized_requested] = exact_field or normalized_requested
        if exact_field:
            lookup[exact_field] = exact_field
        if normalized_requested and exact_field:
            lookup[normalized_requested] = exact_field
    for canonical in fields:
        normalized_canonical = normalize_field_key(canonical)
        if normalized_canonical:
            lookup[normalized_canonical] = canonical
        canonical_aliases = list(aliases.get(canonical, []))
        if not canonical_aliases:
            canonical_aliases = list(_FIELD_ALIASES.get(canonical, []))
        for alias in canonical_aliases:
            normalized_alias = normalize_field_key(alias)
            if normalized_alias:
                lookup.setdefault(normalized_alias, canonical)
    return lookup

def _split_multivalue_text_rows(value: str) -> list[str]:
    rows = [clean_text(part) for part in re.split(r"(?:\r?\n|[•]+)", str(value or "")) if clean_text(part)]
    return rows

def _iter_structured_multi_values(value: object) -> list[object]:
    if isinstance(value, dict):
        return list(value.values())
    if isinstance(value, (list, tuple, set)):
        return list(value)
    return []

def _coerce_structured_multi_rows(field_name: str, value: object) -> list[str]:
    if value in (None, "", [], {}):
        return []
    if isinstance(value, bool):
        return []
    iterable_values = _iter_structured_multi_values(value)
    if iterable_values:
        rows = []
        for item in iterable_values:
            rows.extend(_coerce_structured_multi_rows(field_name, item))
        return rows
    if isinstance(value, str):
        literal_rows = coerce_literal_text_list(value)
        if literal_rows:
            return literal_rows
        text = html_to_text(value, preserve_block_breaks=True) if ("<" in value or _HTML_ENTITY_RE.search(value)) else str(value)
        rows = _split_multivalue_text_rows(text)
        if rows:
            return rows
    coerced_text = coerce_text(value)
    return [coerced_text] if coerced_text is not None else []

def coerce_structured_scalar(
    value: object,
    *,
    keys: tuple[str, ...],
) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped.startswith("{") and stripped.endswith("}"):
            try:
                parsed = json.loads(stripped)
            except (json.JSONDecodeError, TypeError, ValueError):
                try:
                    parsed = ast.literal_eval(stripped)
                except (SyntaxError, ValueError, TypeError):
                    return _coerce_simple_string_dict_scalar(stripped, keys=keys)
                if isinstance(parsed, (dict, list)):
                    return coerce_structured_scalar(parsed, keys=keys)
                return _coerce_simple_string_dict_scalar(stripped, keys=keys)
            if isinstance(parsed, (dict, list)):
                return coerce_structured_scalar(parsed, keys=keys)
            return None
    if isinstance(value, dict):
        for key in keys:
            candidate = value.get(key)
            if candidate in (None, "", [], {}):
                continue
            text = coerce_structured_scalar(candidate, keys=keys)
            if text:
                return text
        return None
    if isinstance(value, list):
        for item in value:
            text = coerce_structured_scalar(item, keys=keys)
            if text:
                return text
        return None
    return coerce_text(value)

def _coerce_simple_string_dict_scalar(
    value: str,
    *,
    keys: tuple[str, ...],
) -> str | None:
    """Parse simple {'key': 'value'} scalars, returning None if malformed.

    This fallback naively splits on commas, so embedded comma values such as
    {'name': 'Foo, Inc'} are unsupported; prefer JSON when commas are possible.
    """
    body = value[1:-1].strip()
    if not body:
        return None
    for part in body.split(","):
        raw_key, separator, raw_value = part.partition(":")
        if not separator:
            return None
        key = _unquote_simple_string_dict_token(raw_key.strip())
        candidate = _unquote_simple_string_dict_token(raw_value.strip())
        if key in keys and candidate:
            return candidate
    return None

def _unquote_simple_string_dict_token(value: str) -> str | None:
    if len(value) < 2 or value[0] != value[-1] or value[0] not in {"'", '"'}:
        return None
    inner = value[1:-1].strip()
    if not inner or any(token in inner for token in "{}[]\r\n"):
        return None
    return inner

def _join_text_parts(parts: list[str | None], *, separator: str) -> str | None:
    cleaned_parts = [part for part in parts if part]
    return separator.join(cleaned_parts) if cleaned_parts else None

def _color_value_is_opaque_code(value: str) -> bool:
    """Reject internal swatch/style codes that masquerade as colors.

    Real color values render as human-readable text. Some sources (e.g.
    Patagonia structured payload ``"color":["SMDB","FGE","OLGG",...]``)
    expose internal short codes for swatches. The full color names exist
    elsewhere on the page; the codes pollute the canonical color when
    the candidate scoring picks the first list element.

    Signature: short (2-5 chars), all upper-case, no separators, AND not a
    recognized short color word. Lowercase short values can be real DOM color
    text ("mint", "ecru", "aqua") and must not be dropped here.
    """
    text = value.strip()
    if not text or " " in text or any(sep in text for sep in ("-", "_", "/", ".")):
        return False
    if not re.fullmatch(r"[A-Za-z]{2,5}", text):
        return False
    if not text.isupper():
        return False
    if text.casefold() in _SHORT_COLOR_ALLOWLIST:
        return False
    return True

def _strip_color_value_code_pollution(value: str) -> str:
    if not value or not any(char.isdigit() for char in value):
        return value
    tokens = re.findall(r"[A-Za-z0-9]+", value)
    if len(tokens) < 2:
        return value
    color_indexes = [index for index, token in enumerate(tokens) if _COLOR_KEYWORD_RE.fullmatch(token)]
    if not color_indexes:
        return value
    tail = tokens[color_indexes[-1] + 1 :]
    if not tail:
        return value
    if not all(token.isdigit() or _variant_color_codelike_token_re.fullmatch(token) for token in tail):
        return value
    color_prefix = [token for token in tokens[: color_indexes[0]] if not _color_prefix_token_is_code_like(token)]
    color_tokens = tokens[color_indexes[0] : color_indexes[-1] + 1]
    return clean_text(" ".join([*color_prefix, *color_tokens]))

def _color_prefix_token_is_code_like(token: str) -> bool:
    text = token.strip()
    return 1 < len(text) <= 3 and not text.islower() and text.casefold() not in _SHORT_COLOR_ALLOWLIST and _COLOR_KEYWORD_RE.fullmatch(text) is None

_SHORT_COLOR_ALLOWLIST = frozenset(
    {
        # short, real color words. Lower-case only is fine; real PDPs use
        # mixed-case rendering. Keep this list narrow — it only protects
        # genuinely human-readable short forms.
        "red",
        "tan",
        "navy",
        "blue",
        "pink",
        "gold",
        "lime",
        "teal",
        "gray",
        "grey",
        "black",
        "white",
        "green",
        "ivory",
        "khaki",
        "olive",
        "rose",
        "wine",
        "rust",
        "sand",
        "snow",
        "cyan",
        "plum",
        "ruby",
        "lilac",
        "coral",
        "azure",
        "beige",
        "amber",
        "denim",
        "ochre",
        "mocha",
        "mauve",
        "stone",
        "stoun",
    }
)

def _strip_option_suffix_noise(value: str) -> str:
    cleaned = value
    for pattern in _OPTION_VALUE_SUFFIX_NOISE_RE:
        cleaned = clean_text(pattern.sub("", cleaned))
    cleaned = re.sub(rf"\s+(?:{CURRENCY_SYMBOL_PATTERN})\s*\d[\d.,]*.*$", "", cleaned)
    cleaned = re.sub(rf"\s+\d[\d.,]*\s*(?:{CURRENCY_CODE_PATTERN})\b.*$", "", cleaned, flags=re.I)
    if _OPTION_VALUE_NOISE_WORD_PATTERN:
        cleaned = re.sub(
            rf"\s+\b(?:{_OPTION_VALUE_NOISE_WORD_PATTERN})\b.*$",
            "",
            cleaned,
            flags=re.I,
        )
    return clean_text(cleaned)

from __future__ import annotations

import re
from typing import Any

from app.services.config.field_mappings import (
    BRAND_LIKE_FIELDS,
    TITLE_FIELD,
    TITLE_STRUCTURED_VALUE_KEYS,
    WEIGHT_FIELD,
)
from app.services.config.extraction_rules import (
    CANDIDATE_AVAILABILITY_NOISE_PHRASES,
    LONG_TEXT_FIELDS,
    RATING_RE,
)
from app.services.config.variant_policy import OPTION_SCALAR_FIELDS
from app.services.normalizers import normalize_record_fields
from app.services.shared.field_coerce_price import (
    coerce_price_from_dict,
    extract_currency_code,
    price_text_is_negative,
)
from app.services.shared.field_coerce_text import (
    category_value_is_url_path,
    coerce_barcode,
    coerce_brand_text,
    coerce_gender,
    coerce_identity_token_or_none,
    coerce_sku,
    identity_internal_tokens,
)
from app.services.shared.field_coerce_url import (
    coerce_url_field_value,
    is_url_field,
    strip_record_tracking_params,
)
from app.services.shared.text_coerce import coerce_long_text, is_null_text, text_or_none

from . import field_coerce_core as core

def _sanitize_color_scalar(value: str) -> str | None:
    if any(predicate(value) for predicate in (core._SMALL_NUMERIC_RE.fullmatch, core._TRACKING_PIXEL_RE.fullmatch)) or core._color_value_is_opaque_code(value):
        return None
    match = re.fullmatch(r"select\s+(.+?)\s+color", value, flags=re.I)
    cleaned = core.clean_text(match.group(1)) if match else value
    cleaned = re.split(r"\bstyle\s*:", cleaned, maxsplit=1, flags=re.I)[0]
    if ":" in cleaned:
        _prefix, suffix = cleaned.rsplit(":", 1)
        if len(core.clean_text(suffix).split()) <= 4 and core._COLOR_KEYWORD_RE.search(suffix):
            cleaned = suffix
    cleaned = re.sub(r"^color\s*:\s*", "", cleaned, flags=re.I)
    cleaned = re.sub(r"\bcolor\s+details\b.*$", "", cleaned, flags=re.I).strip()
    cleaned = re.split(r"\bview as list\b", cleaned, maxsplit=1, flags=re.I)[0]
    cleaned = re.split(r"\bsize(?:\s*\([^)]*\))?\b", cleaned, maxsplit=1, flags=re.I)[0]
    cleaned = core.clean_text(core._strip_color_value_code_pollution(cleaned))
    return None if not cleaned or re.search(r"\d+\s*x\s*\d+", cleaned) else cleaned

def _sanitize_size_scalar(value: str) -> str | None:
    cleaned = re.sub(r"^size\s*:\s*", "", value, flags=re.I)
    cleaned = re.split(r"\bview as list\b", cleaned, maxsplit=1, flags=re.I)[0]
    cleaned = re.sub(r"\s*\(size[\s_-]*chart\)", "", cleaned, flags=re.I)
    cleaned = core.clean_text(cleaned)
    if re.search(r"\b(?:please\s+)?select(?:\s+size)?\b", cleaned, flags=re.I):
        return None
    return None if cleaned.strip().lower() in core.size_reject_tokens_normalized else cleaned

def _sanitize_option_scalar(field_name: str, value: object) -> str | None:
    text = core.coerce_text(value)
    if not text or text.lstrip().startswith(("{", "[")):
        return None
    cleaned = core._strip_option_suffix_noise(text) if field_name in OPTION_SCALAR_FIELDS else text
    normalized: str | None = cleaned
    if field_name == "color":
        normalized = _sanitize_color_scalar(cleaned)
    elif field_name == "size":
        normalized = _sanitize_size_scalar(cleaned)
    elif field_name == WEIGHT_FIELD and re.fullmatch(r"\d+(?:\.\d+)?", cleaned):
        return None
    return None if not normalized or is_null_text(normalized) else normalized

def coerce_location(value: object) -> str | None:
    if isinstance(value, dict):
        address = value.get("address")
        if isinstance(address, str):
            address_text = text_or_none(address)
            if address_text:
                return address_text
        if isinstance(address, dict):
            joined_address = core._join_text_parts(
                [
                    text_or_none(address.get("streetAddress")),
                    text_or_none(address.get("addressLocality")),
                    text_or_none(address.get("addressRegion")),
                    text_or_none(address.get("postalCode")),
                    text_or_none(address.get("addressCountry")),
                ],
                separator=", ",
            )
            if joined_address:
                return joined_address
        return core._join_text_parts(
            [
                text_or_none(value.get("name")),
                text_or_none(value.get("addressLocality")),
                text_or_none(value.get("addressRegion")),
                text_or_none(value.get("addressCountry")),
            ],
            separator=", ",
        )
    if isinstance(value, list):
        return core._join_text_parts(
            [coerce_location(item) for item in value],
            separator=" | ",
        )
    return core.coerce_text(value)

def _salary_from_nested_value(
    nested: dict[str, object],
    *,
    currency: str | None,
) -> str | None:
    minimum = text_or_none(nested.get("minValue"))
    maximum = text_or_none(nested.get("maxValue"))
    amount = text_or_none(nested.get("value"))
    unit = text_or_none(nested.get("unitText"))
    numbers = " - ".join(part for part in (minimum, maximum) if part)
    if not numbers:
        numbers = amount or ""
    if not numbers:
        return None
    return " ".join(piece for piece in (currency, numbers, unit) if piece)

def salary_from_json(value: object) -> str | None:
    if isinstance(value, dict):
        currency = text_or_none(value.get("currency") or value.get("salaryCurrency") or value.get("currencyCode"))
        nested = value.get("value")
        if isinstance(nested, dict):
            nested_salary = _salary_from_nested_value(nested, currency=currency)
            if nested_salary:
                return nested_salary
        text = core.coerce_text(value.get("value"))
        if text:
            return f"{currency} {text}".strip() if currency else text
    return core.coerce_text(value)

def coerce_product_attributes(value: object) -> dict[str, object] | None:
    if not isinstance(value, dict):
        return None
    cleaned = _clean_product_attribute_dict(value)
    return cleaned or None

def _product_attribute_key_is_noise(value: object) -> bool:
    normalized = core.normalize_field_key(str(value or ""))
    return bool(normalized and normalized in core._NOISY_PRODUCT_ATTRIBUTE_KEYS)

def _product_attribute_row_is_noise(value: dict[str, object]) -> bool:
    row_id = value.get("Id") or value.get("id") or value.get("name") or value.get("label")
    return _product_attribute_key_is_noise(row_id)

def _clean_product_attribute_value(value: object) -> object | None:
    if value in (None, "", [], {}):
        return None
    if isinstance(value, dict):
        if _product_attribute_row_is_noise(value):
            return None
        return _clean_product_attribute_dict(value)
    if isinstance(value, list):
        rows = [cleaned for item in value if (cleaned := _clean_product_attribute_value(item)) not in (None, "", [], {})]
        return rows or None
    return value

def _clean_product_attribute_dict(value: dict[str, object]) -> dict[str, object]:
    cleaned: dict[str, object] = {}
    for key, item in value.items():
        if _product_attribute_key_is_noise(key):
            continue
        cleaned_value = _clean_product_attribute_value(item)
        if cleaned_value not in (None, "", [], {}):
            cleaned[str(key)] = cleaned_value
    return cleaned

def coerce_availability_dict(value: object) -> str | None:
    if not isinstance(value, dict):
        return None
    explicit_keys = ("availability", "availabilityStatus", "status")
    for key in explicit_keys:
        candidate = value.get(key)
        if candidate not in (None, "", [], {}):
            return coerce_availability_value(candidate)
    if len(value) == 1:
        for key in ("name", "value"):
            candidate = value.get(key)
            if candidate not in (None, "", [], {}):
                return coerce_availability_value(candidate)
    return None

def coerce_availability_value(value: object) -> str | None:
    if isinstance(value, bool):
        return "in_stock" if value else "out_of_stock"
    text = core.coerce_text(value)
    if text:
        for phrase in tuple(CANDIDATE_AVAILABILITY_NOISE_PHRASES or ()):
            if phrase.lower() in text.lower():
                text = re.sub(re.escape(phrase), "", text, flags=re.I).strip()
                if not text:
                    return None
    if not text:
        return None
    lowered = text.strip().lower().rstrip("/")
    mapped = dict(core.AVAILABILITY_URL_MAP or {}).get(lowered)
    if mapped:
        return str(mapped)
    # Drop non-canonical residual text so noisy values cannot leak through.
    normalized_enum = lowered.replace("-", "_").replace(" ", "_")
    if normalized_enum in core._AVAILABILITY_CANONICAL_ENUM:
        return normalized_enum
    return None

def coerce_rating_value(value: object) -> float | None:
    text = core.coerce_text(value)
    if not text:
        return None
    match = RATING_RE.search(text)
    candidate = match.group(0) if match else text
    try:
        return float(candidate)
    except (TypeError, ValueError):
        return None

def _coerce_named_field(field_name: str, value: object) -> tuple[bool, object | None]:
    coercers = {
        "product_attributes": coerce_product_attributes,
        "location": coerce_location,
        "salary": salary_from_json,
        "product_type": _coerce_product_type_clean,
        "product_id": coerce_identity_token_or_none,
        TITLE_FIELD: _coerce_title_text,
        "barcode": coerce_barcode,
        "sku": coerce_sku,
        "gender": coerce_gender,
    }
    coercer = coercers.get(field_name)
    return (False, None) if coercer is None else (True, coercer(value))

def _coerce_structured_container(field_name: str, value: object) -> tuple[bool, object | None]:
    if field_name in core.STRUCTURED_OBJECT_FIELDS and isinstance(value, dict):
        return True, value
    if field_name not in core.STRUCTURED_OBJECT_LIST_FIELDS or not isinstance(value, list):
        return False, None
    rows = [item for item in value if isinstance(item, dict)]
    return True, rows or None

def _coerce_currency_text(value: str) -> str | None:
    currency_code = extract_currency_code(value)
    if currency_code:
        return currency_code
    text = core.coerce_text(value)
    return text.upper() if text and re.fullmatch(r"[A-Za-z]{3}", text) else text

def _coerce_brand_value(value: object) -> str | None:
    if not isinstance(value, dict):
        return coerce_brand_text(value)
    explicit_value = value.get("name") or value.get("title") or value.get("value")
    numeric_keys = {str(index) for index in range(len(value))}
    if explicit_value in (None, "", [], {}) and set(value) <= numeric_keys:
        explicit_value = next(iter(value.values()), None)
    return coerce_brand_text(explicit_value)

def _coerce_category_value(value: object) -> str | None:
    if isinstance(value, dict):
        value = next(
            (value.get(key) for key in ("name", "title", "slug", "value", "en") if value.get(key)),
            None,
        )
    elif isinstance(value, str) and value.strip().startswith(("{", "[")):
        value = core.coerce_structured_scalar(value, keys=("name", "title", "label", "value", "text", "en"))
    text = core.coerce_text(value)
    return None if text and category_value_is_url_path(text) else text

def _coerce_option_value(field_name: str, value: object) -> str | None:
    scalar_input = value
    if field_name == "color" and isinstance(value, list):
        readable = [item for item in value if not (isinstance(item, str) and core._color_value_is_opaque_code(item))]
        scalar_input = readable or value
    scalar = core.coerce_structured_scalar(scalar_input, keys=(field_name, "name", "title", "label", "value", "text"))
    return _sanitize_option_scalar(field_name, scalar)

def _coerce_predefined_field(field_name: str, value: object) -> tuple[bool, object | None]:
    for handler in (_coerce_named_field, _coerce_structured_container):
        handled, coerced = handler(field_name, value)
        if handled:
            return True, coerced
    if field_name in {"currency", "salary_currency"} and isinstance(value, str):
        return True, _coerce_currency_text(value)
    if field_name in BRAND_LIKE_FIELDS:
        return True, _coerce_brand_value(value)
    if field_name == "category":
        return True, _coerce_category_value(value)
    if field_name in OPTION_SCALAR_FIELDS:
        return True, _coerce_option_value(field_name, value)
    return False, None

def _coerce_scalar_number(field_name: str, value: object) -> tuple[bool, object | None]:
    if field_name in core._PRICE_FIELD_NAMES and isinstance(value, str):
        text = core.coerce_text(value)
        valid = not (text and not re.search(r"\d", text)) and not price_text_is_negative(text)
        return True, text or None if valid else None
    if field_name not in core._INTEGER_FIELD_NAMES:
        return False, None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return True, int(value)
    if not isinstance(value, str):
        return False, None
    normalized = (core.coerce_text(value) or "").replace(",", "").strip()
    if not re.fullmatch(r"[-+]?\d+", normalized):
        return True, None
    try:
        return True, int(normalized)
    except (TypeError, ValueError):
        return True, None

def _first_mapping_value(value: dict[object, object], keys: tuple[str, ...]) -> object | None:
    return next(
        (value.get(key) for key in keys if value.get(key) not in (None, "", [], {})),
        None,
    )

def _coerce_mapping_field(field_name: str, value: object) -> tuple[bool, object | None]:
    if not isinstance(value, dict):
        return False, None
    if field_name in {"price", "sale_price", "original_price", "discount_amount"}:
        return True, coerce_price_from_dict(value)
    key_sets = {
        "currency": ("currency", "currencyCode", "priceCurrency", "salaryCurrency"),
        "salary_currency": (
            "currency",
            "currencyCode",
            "priceCurrency",
            "salaryCurrency",
        ),
        "rating": ("ratingValue", "value", "rating", "score"),
        "review_count": (
            "reviewCount",
            "ratingCount",
            "count",
            "totalCount",
            "numberOfReviews",
        ),
    }
    keys = key_sets.get(field_name)
    if keys is None:
        return False, None
    item = _first_mapping_value(value, keys)
    coerced = coerce_rating_value(item) if field_name == "rating" else core.coerce_text(item)
    return True, coerced

def _coerce_availability(field_name: str, value: object) -> tuple[bool, object | None]:
    if field_name != "availability":
        return False, None
    if isinstance(value, bool):
        return True, "in_stock" if value else "out_of_stock"
    if isinstance(value, dict):
        return True, coerce_availability_dict(value)
    return True, coerce_availability_value(value)

def _dedupe_structured_rows(field_name: str, value: object) -> list[str] | None:
    rows = core._coerce_structured_multi_rows(field_name, value)
    deduped: list[str] = []
    seen: set[str] = set()
    for row in rows:
        key = row.casefold()
        if key not in seen:
            seen.add(key)
            deduped.append(row)
    return deduped or None

def _coerce_list_value(field_name: str, value: list[object], page_url: str) -> list[object] | None:
    rows: list[object] = []
    for item in value:
        normalized = coerce_field_value(field_name, item, page_url)
        if normalized in (None, "", [], {}):
            continue
        rows.extend(normalized if isinstance(normalized, list) else [normalized])
    return rows or None

def coerce_field_value(field_name: str, value: object, page_url: str) -> object | None:
    if value in (None, "", [], {}):
        return None
    handled, coerced = _coerce_predefined_field(field_name, value)
    if handled:
        return coerced
    for handler in (_coerce_scalar_number, _coerce_mapping_field, _coerce_availability):
        handled, coerced = handler(field_name, value)
        if handled:
            return coerced
    if is_url_field(field_name):
        return coerce_url_field_value(field_name, value, page_url)
    if field_name in core.STRUCTURED_MULTI_FIELDS:
        return _dedupe_structured_rows(field_name, value)
    if isinstance(value, list):
        return _coerce_list_value(field_name, value, page_url)
    if isinstance(value, (dict, set, frozenset)):
        return None
    if field_name in LONG_TEXT_FIELDS:
        return coerce_long_text(value)
    return coerce_rating_value(value) if field_name == "rating" else core.coerce_text(value)

def _coerce_title_text(value: object) -> str | None:
    is_structured_input = isinstance(value, dict) or (isinstance(value, str) and value.strip().startswith("{") and value.strip().endswith("}"))
    if is_structured_input:
        structured = core.coerce_structured_scalar(
            value,
            keys=TITLE_STRUCTURED_VALUE_KEYS,
        )
        if structured:
            value = structured
        else:
            return None
    return coerce_identity_token_or_none(value)

def _coerce_product_type_clean(value: object) -> str | None:
    if isinstance(value, dict):
        value = core.coerce_structured_scalar(value, keys=("name", "title", "label", "value", "text", "type"))
    text = core.coerce_text(value)
    if not text:
        return None
    if text.lstrip().startswith(("{", "[")):
        return None
    folded = text.strip().lower()
    if folded in identity_internal_tokens():
        return None
    if any(token in folded for token in core._product_type_noise_tokens):
        return None
    return text

def finalize_record(
    record: dict[str, Any],
    *,
    normalize_fields: bool = True,
    surface: str | None = None,
) -> dict[str, Any]:
    cleaned = core.clean_record(record)
    cleaned = strip_record_tracking_params(cleaned, surface=surface)
    return normalize_record_fields(cleaned) if normalize_fields else cleaned

def direct_record_to_surface_fields(
    record: dict[str, Any],
    *,
    surface: str,
    page_url: str,
    requested_fields: list[str] | None = None,
    base_fields: dict[str, Any] | None = None,
) -> dict[str, Any]:
    shaped = dict(base_fields or {})
    source_fields = core.surface_fields(
        surface,
        requested_fields,
        allow_noncanonical_requested=False,
    )
    for field_name in source_fields:
        value = coerce_field_value(field_name, dict(record or {}).get(field_name), page_url)
        if value not in (None, "", [], {}):
            shaped[field_name] = value
    return finalize_record(shaped, surface=surface)

decimal_for_shared_price = core._decimal_for_shared_price

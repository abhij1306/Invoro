from __future__ import annotations

from collections.abc import Mapping
from typing import Any
from urllib.parse import urlparse

from app.services.config.field_mappings import (
    ADDITIONAL_IMAGES_FIELD,
    BARCODE_FIELD,
    CANONICAL_SCHEMAS,
    NAVIGATION_URL_FIELDS,
    OPEN_FIELD_SURFACES,
    ROUTE_BARCODE_TO_SKU,
    SKU_FIELD,
    URL_FIELD,
    VARIANTS_FIELD,
)
from app.services.config.public_record_policy import (
    PUBLIC_RECORD_DEFAULT_EXCLUDED_FIELDS,
    PUBLIC_RECORD_ECOMMERCE_DROPPED_FIELDS,
    PUBLIC_RECORD_LEGACY_VARIANT_FIELDS,
    PUBLIC_RECORD_PRESENTATION_FIELDS,
    PUBLIC_RECORD_URL_BLOCKED_PATH_MARKERS,
    PUBLIC_RECORD_URL_MAX_LENGTH,
)
from app.services.extract.variant_normalization.contract import (
    enforce_flat_variant_public_contract,
    flatten_variants_for_public_output,
)
from app.services.field_policy import canonical_requested_fields, normalize_field_key
from app.services.shared.field_coerce import (
    IMAGE_FIELDS,
    LONG_TEXT_FIELDS,
    STRUCTURED_MULTI_FIELDS,
    STRUCTURED_OBJECT_FIELDS,
    STRUCTURED_OBJECT_LIST_FIELDS,
    URL_FIELDS,
    coerce_field_value,
    finalize_record,
    text_or_none,
)
from app.services.field_url_normalization import (
    canonical_public_record_url,
    is_concatenated_url,
)


def public_record_data_for_surface(
    record: dict[str, Any],
    *,
    surface: str,
    page_url: str,
    requested_fields: list[str] | None = None,
) -> tuple[dict[str, Any], dict[str, str]]:
    (
        normalized_surface,
        allowed_fields,
        open_field_passthrough,
        explicit_fields,
        default_excluded,
        ecommerce_contract_excluded,
    ) = _public_record_policy(
        record, surface=surface, requested_fields=requested_fields
    )
    data: dict[str, Any] = {}
    rejected: dict[str, str] = {}
    for raw_field_name, raw_value in dict(record or {}).items():
        result = _process_public_field(
            raw_field_name,
            raw_value,
            data=data,
            record=record,
            page_url=page_url,
            normalized_surface=normalized_surface,
            ecommerce_contract_excluded=ecommerce_contract_excluded,
            default_excluded=default_excluded,
            explicit_fields=explicit_fields,
            allowed_fields=allowed_fields,
            open_field_passthrough=open_field_passthrough,
        )
        if result is None:
            continue
        field_name, coerced, reason = result
        if reason:
            rejected[str(raw_field_name)] = reason
            continue
        data[field_name] = coerced
    if normalized_surface.startswith("ecommerce_") and VARIANTS_FIELD in data:
        enforce_flat_variant_public_contract(data, page_url=page_url)
    return finalize_record(data, surface=surface), rejected


def _public_record_policy(
    record: dict[str, Any], *, surface: str, requested_fields: list[str] | None
) -> tuple[str, set[str], bool, set[str], set[str], set[str]]:
    normalized_surface = str(surface or "").strip().lower()
    allowed_fields = {
        str(field).strip()
        for field in CANONICAL_SCHEMAS.get(normalized_surface, [])
        if str(field).strip()
    }
    allowed_fields.add(URL_FIELD)
    open_surfaces = {
        normalize_field_key(value) for value in tuple(OPEN_FIELD_SURFACES or ())
    }
    open_field_passthrough = (
        normalized_surface in open_surfaces
        and normalize_field_key(record.get("_extraction_mode")) == "table_rows"
    )
    explicit_fields = {
        normalized
        for field in canonical_requested_fields(requested_fields or [])
        if (normalized := normalize_field_key(field))
    }
    allowed_fields.update(explicit_fields)
    ecommerce_excluded = {
        normalized
        for value in (
            *tuple(PUBLIC_RECORD_ECOMMERCE_DROPPED_FIELDS or ()),
            *tuple(PUBLIC_RECORD_LEGACY_VARIANT_FIELDS or ()),
        )
        if (normalized := normalize_field_key(value))
    }
    return (
        normalized_surface,
        allowed_fields,
        open_field_passthrough,
        explicit_fields,
        _default_excluded_fields_for_surface(normalized_surface),
        ecommerce_excluded,
    )


def _process_public_field(
    raw_field_name: object,
    raw_value: object,
    *,
    data: dict[str, Any],
    record: dict[str, Any],
    page_url: str,
    normalized_surface: str,
    ecommerce_contract_excluded: set[str],
    default_excluded: set[str],
    explicit_fields: set[str],
    allowed_fields: set[str],
    open_field_passthrough: bool,
) -> tuple[str, object, str] | None:
    field_name = normalize_field_key(str(raw_field_name or ""))
    reason = _field_admission_rejection(
        raw_field_name,
        raw_value,
        field_name=field_name,
        normalized_surface=normalized_surface,
        ecommerce_contract_excluded=ecommerce_contract_excluded,
        default_excluded=default_excluded,
        explicit_fields=explicit_fields,
        allowed_fields=allowed_fields,
        open_field_passthrough=open_field_passthrough,
    )
    if reason == "skip":
        return None
    if reason:
        return field_name, None, reason
    coerced = coerce_field_value(field_name, raw_value, page_url)
    if field_name == VARIANTS_FIELD:
        coerced = flatten_variants_for_public_output(coerced, page_url=page_url)
    if coerced in (None, "", [], {}):
        routed = _route_barcode_to_sku(
            data,
            record=record,
            field_name=field_name,
            raw_value=raw_value,
            page_url=page_url,
            allowed_fields=allowed_fields,
        )
        return field_name, None, "routed_to_sku" if routed else "empty_after_coercion"
    coerced, reason = _validate_public_field_value(
        field_name, coerced, normalized_surface=normalized_surface
    )
    return field_name, coerced, reason


def _field_admission_rejection(
    raw_field_name: object,
    raw_value: object,
    *,
    field_name: str,
    normalized_surface: str,
    ecommerce_contract_excluded: set[str],
    default_excluded: set[str],
    explicit_fields: set[str],
    allowed_fields: set[str],
    open_field_passthrough: bool,
) -> str:
    if (
        not field_name
        or str(raw_field_name).startswith("_")
        or raw_value in (None, "", [], {})
    ):
        return "skip"
    if field_name in PUBLIC_RECORD_PRESENTATION_FIELDS:
        return "presentation_field_excluded"
    if (
        normalized_surface.startswith("ecommerce_")
        and field_name in ecommerce_contract_excluded
    ):
        return "public_contract_excluded"
    if field_name in default_excluded and field_name not in explicit_fields:
        return "default_public_field_excluded"
    if field_name not in allowed_fields and not open_field_passthrough:
        return "field_not_allowed_for_surface"
    return ""


def _route_barcode_to_sku(
    data: dict[str, Any],
    *,
    record: dict[str, Any],
    field_name: str,
    raw_value: object,
    page_url: str,
    allowed_fields: set[str],
) -> bool:
    if field_name != BARCODE_FIELD or not ROUTE_BARCODE_TO_SKU:
        return False
    routed_sku = coerce_field_value(SKU_FIELD, raw_value, page_url)
    if (
        routed_sku in (None, "", [], {})
        or SKU_FIELD not in allowed_fields
        or record.get(SKU_FIELD) not in (None, "", [], {})
        or not _public_record_field_shape_valid(SKU_FIELD, routed_sku)
    ):
        return False
    data[SKU_FIELD] = routed_sku
    return True


def _validate_public_field_value(
    field_name: str, value: object, *, normalized_surface: str
) -> tuple[object, str]:
    if not _public_record_field_shape_valid(field_name, value):
        return value, "invalid_field_shape"
    if (
        field_name in URL_FIELDS
        and isinstance(value, str)
        and is_concatenated_url(value)
    ):
        return value, "concatenated_url"
    if field_name in NAVIGATION_URL_FIELDS and not public_navigation_url_safe(value):
        return value, "unsafe_navigation_url"
    if field_name not in NAVIGATION_URL_FIELDS:
        return value, ""
    canonical = canonical_public_record_url(
        value, surface=normalized_surface, field_name=field_name
    )
    reason = "empty_after_canonical_url" if canonical in (None, "", [], {}) else ""
    return canonical, reason


def _default_excluded_fields_for_surface(normalized_surface: str) -> set[str]:
    if not isinstance(PUBLIC_RECORD_DEFAULT_EXCLUDED_FIELDS, Mapping):
        raise TypeError(
            "PUBLIC_RECORD_DEFAULT_EXCLUDED_FIELDS must be a mapping; "
            f"got {type(PUBLIC_RECORD_DEFAULT_EXCLUDED_FIELDS).__name__} "
            f"for surface {normalized_surface!r}"
        )
    return {
        normalize_field_key(field_name)
        for field_name in PUBLIC_RECORD_DEFAULT_EXCLUDED_FIELDS.get(
            normalized_surface,
            [],
        )
        if normalize_field_key(field_name)
    }


def _public_record_field_shape_valid(field_name: str, value: object) -> bool:
    if field_name in STRUCTURED_OBJECT_FIELDS:
        return isinstance(value, dict)
    if field_name in STRUCTURED_OBJECT_LIST_FIELDS:
        return isinstance(value, list) and all(isinstance(item, dict) for item in value)
    if field_name in STRUCTURED_MULTI_FIELDS or field_name == ADDITIONAL_IMAGES_FIELD:
        return isinstance(value, list) and all(
            not isinstance(item, (dict, list, tuple, set)) for item in value
        )
    if field_name in URL_FIELDS | IMAGE_FIELDS | LONG_TEXT_FIELDS:
        return isinstance(value, str)
    return not isinstance(value, (dict, list, tuple, set))


def public_navigation_url_safe(value: object) -> bool:
    text = text_or_none(value)
    if not text:
        return False
    if len(text) > int(PUBLIC_RECORD_URL_MAX_LENGTH):
        return False
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"}:
        return False
    lowered_path = str(parsed.path or "").lower()
    if any(
        marker in lowered_path
        for marker in tuple(PUBLIC_RECORD_URL_BLOCKED_PATH_MARKERS or ())
    ):
        return False
    return True

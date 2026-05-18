from __future__ import annotations

from app.services.extract.variant_normalization.common import *
from app.services.extract.variant_normalization import deduplication

__all__ = (
    "finalize",
    "enforce_payload_limits",
    "_enforce_flat_variant_contract",
)

def finalize(record: dict[str, Any], *, max_rows: int) -> None:
    enforce_payload_limits(record, max_rows=max_rows)
    _enforce_flat_variant_contract(record)


def enforce_payload_limits(record: dict[str, Any], *, max_rows: int) -> None:
    variants = record.get("variants")
    if not isinstance(variants, list) or not variants:
        return
    try:
        max_rows = int(max_rows) if max_rows is not None else 0
    except (TypeError, ValueError):
        max_rows = 0
    if max_rows <= 0:
        return
    if len(variants) <= max_rows:
        return
    kept = [
        variant
        for variant in variants
        if isinstance(variant, dict)
        and (
            deduplication._variant_primary_key(variant)
            or _variant_has_axis_value(variant)
        )
    ]
    truncated = kept[:max_rows] if kept else list(variants[:max_rows])
    if truncated:
        record["variants"] = truncated
        record["variant_count"] = len(truncated)
        return
    record.pop("variants", None)
    record.pop("variant_count", None)


def _enforce_flat_variant_contract(record: dict[str, Any]) -> None:
    enforce_flat_variant_public_contract(record)
    for field_name in _LEGACY_VARIANT_KEYS:
        record.pop(field_name, None)
    for field_name in list(record):
        if _OPTION_FIELD_PATTERN.fullmatch(str(field_name)):
            record.pop(field_name, None)

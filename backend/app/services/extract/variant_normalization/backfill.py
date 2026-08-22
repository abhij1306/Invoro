from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

import logging

from app.services.config.extraction_rules import CURRENCY_CODES
from app.services.extract.variant_structural_pruning import (
    drop_parent_sku_alias_variant_rows,
    prune_low_signal_numeric_only_variants,
)
from app.services.shared.field_coerce import (
    clean_text,
    extract_currency_code,
    text_or_none,
)

logger = logging.getLogger(__name__)
currency_codes_upper = frozenset(
    str(code).upper() for code in tuple(CURRENCY_CODES or ()) if str(code).strip()
)

__all__ = (
    "backfill_parent_scalar_axes_from_variants",
    "backfill_variant_context",
    "enforce_variant_currency_context",
    "_backfill_variant_context",
    "_backfill_parent_scalar_axes_from_variants",
    "_enforce_variant_currency_context",
)


def _backfill_variant_context(record: dict[str, Any]) -> None:
    _backfill_variant_prices_from_record(record)
    _enforce_variant_currency_context(record)
    _backfill_variant_shared_fields_from_record(record)
    prune_low_signal_numeric_only_variants(record)
    drop_parent_sku_alias_variant_rows(record)


def _backfill_parent_scalar_axes_from_variants(record: dict[str, Any]) -> None:
    variants = record.get("variants")
    if not isinstance(variants, list) or len(variants) < 2:
        return
    variant_rows = [variant for variant in variants if isinstance(variant, dict)]
    if len(variant_rows) < 2:
        return
    for field_name in ("color",):
        if clean_text(record.get(field_name)):
            continue
        values = [
            clean_text(variant.get(field_name))
            for variant in variant_rows
            if clean_text(variant.get(field_name))
        ]
        if len(values) != len(variant_rows):
            continue
        first_value = values[0]
        if all(value.casefold() == first_value.casefold() for value in values[1:]):
            record[field_name] = first_value


def _enforce_variant_currency_context(record: dict[str, Any]) -> None:
    variants = record.get("variants")
    if not isinstance(variants, list) or not variants:
        return
    parent_currency = _currency_code(record.get("currency"))
    if not parent_currency:
        return
    variant_currencies = {
        currency
        for variant in variants
        if isinstance(variant, dict)
        if (currency := _currency_code(variant.get("currency")))
    }
    if len(variant_currencies) == 1:
        only_variant_currency = next(iter(variant_currencies))
        if only_variant_currency != parent_currency:
            record["currency"] = only_variant_currency
            parent_currency = only_variant_currency
    kept, mismatched = _partition_variants_by_currency(variants, parent_currency)
    _store_currency_partition(record, kept=kept, mismatched=mismatched)


def _partition_variants_by_currency(
    variants: list[object], parent_currency: str
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    kept: list[dict[str, Any]] = []
    mismatched: list[dict[str, Any]] = []
    for variant in variants:
        if not isinstance(variant, dict):
            continue
        variant_currency = _currency_code(variant.get("currency"))
        if variant_currency and variant_currency != parent_currency:
            logger.warning("Dropping variant with mismatched currency")
            mismatched.append(
                {
                    **variant,
                    "currency_mismatch": True,
                    "parent_currency": parent_currency,
                    "variant_currency": variant_currency,
                }
            )
            continue
        variant["currency"] = parent_currency
        kept.append(variant)
    return kept, mismatched


def _store_currency_partition(
    record: dict[str, Any],
    *,
    kept: list[dict[str, Any]],
    mismatched: list[dict[str, Any]],
) -> None:
    if mismatched:
        record["variants_currency_mismatch"] = mismatched
    output = kept or [_strip_currency_mismatch(row) for row in mismatched]
    if output:
        record["variants"] = output
        record["variant_count"] = len(output)
    else:
        record.pop("variants", None)
        record.pop("variant_count", None)


def _strip_currency_mismatch(variant: dict[str, Any]) -> dict[str, Any]:
    metadata = {"currency_mismatch", "parent_currency", "variant_currency"}
    return {key: value for key, value in variant.items() if key not in metadata}


def _currency_code(value: object) -> str:
    extracted = extract_currency_code(value)
    if extracted:
        return extracted
    text = text_or_none(value)
    if text:
        upper = text.upper()
        if upper in currency_codes_upper:
            return upper
    return ""


def _backfill_variant_prices_from_record(record: dict[str, Any]) -> None:
    variants = record.get("variants")
    if not isinstance(variants, list) or not variants:
        return
    fallback_fields = {
        field_name: record.get(field_name)
        for field_name in ("price", "currency")
        if record.get(field_name) not in (None, "", [], {})
    }
    if not fallback_fields:
        return

    def _value_present(value: object) -> bool:
        return value not in (None, "", [], {})

    def _comparable_scalar(value: object) -> object:
        if isinstance(value, bool):
            return text_or_none(value)
        if isinstance(value, (int, float)):
            try:
                parsed = Decimal(str(value))
            except InvalidOperation:
                return text_or_none(value)
            return parsed if parsed.is_finite() else text_or_none(value)
        text = text_or_none(value)
        if text is None:
            return None
        try:
            parsed = Decimal(text)
        except InvalidOperation:
            return text
        return parsed if parsed.is_finite() else text

    def _has_distinct_variant_value(field_name: str) -> bool:
        """Distinct means a non-empty variant value differs from the parent fallback."""
        fallback_value = _comparable_scalar(fallback_fields.get(field_name))
        if fallback_value is None:
            return False
        return any(
            isinstance(variant, dict)
            and _value_present(variant.get(field_name))
            and _comparable_scalar(variant.get(field_name)) != fallback_value
            for variant in variants
        )

    distinct_price = _has_distinct_variant_value("price")
    for variant in variants:
        if not isinstance(variant, dict):
            continue
        if not distinct_price and variant.get("price") in (None, "", [], {}):
            variant["price"] = fallback_fields.get("price")
        if variant.get("currency") in (None, "", [], {}) and fallback_fields.get(
            "currency"
        ) not in (
            None,
            "",
            [],
            {},
        ):
            variant["currency"] = fallback_fields.get("currency")


def _backfill_variant_shared_fields_from_record(record: dict[str, Any]) -> None:
    variants = record.get("variants")
    if not isinstance(variants, list) or not variants:
        return
    fallback_image = record.get("image_url")
    record_color = clean_text(record.get("color"))
    fallback_image_key = _image_url_normalize_key(fallback_image)
    for variant in variants:
        if not isinstance(variant, dict):
            continue
        _backfill_variant_image(
            variant,
            fallback_image=fallback_image,
            fallback_image_key=fallback_image_key,
            record_color=record_color,
        )


def _backfill_variant_image(
    variant: dict[str, Any],
    *,
    fallback_image: object,
    fallback_image_key: str,
    record_color: str,
) -> None:
    variant_color = clean_text(variant.get("color"))
    different_color = bool(
        record_color
        and variant_color
        and variant_color.casefold() != record_color.casefold()
    )
    existing = variant.get("image_url")
    if (
        existing
        and fallback_image_key
        and _image_url_normalize_key(existing) == fallback_image_key
        and different_color
    ):
        variant.pop("image_url", None)
        existing = None
    if (
        fallback_image not in (None, "", [], {})
        and existing in (None, "", [], {})
        and not different_color
    ):
        variant["image_url"] = fallback_image


def _image_url_normalize_key(url: object) -> str:
    """Strip query string and fragment so two image URLs that differ only by
    CDN resize params (``&width=...``, ``&crop=...``) compare equal."""
    text = clean_text(url)
    if not text:
        return ""
    base = text.split("?", 1)[0].split("#", 1)[0]
    return base.casefold()


backfill_parent_scalar_axes_from_variants = _backfill_parent_scalar_axes_from_variants
backfill_variant_context = _backfill_variant_context
enforce_variant_currency_context = _enforce_variant_currency_context

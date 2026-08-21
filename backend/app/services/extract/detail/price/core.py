# ruff: noqa: F401
from __future__ import annotations

__all__ = (
    "backfill_detail_price_from_html", "drop_low_signal_zero_detail_price",
    "reconcile_detail_currency_with_url", "reconcile_detail_price_magnitudes",
    "reconcile_parent_price_against_variant_range", "record_field_sources",
    "append_record_field_source", "normalize_mismatched_host_currency_price",
)

from decimal import Decimal
from dataclasses import dataclass
import re
from typing import Any

from app.services.dom.html_parser import BeautifulSoup

from app.services.config.extraction_rules import (
    AVAILABILITY_OUT_OF_STOCK,
    DETAIL_CENT_BASED_PRICE_CURRENCY_SET,
    DETAIL_AUTHORITATIVE_PRICE_SOURCE_SET,
    DETAIL_CURRENT_PRICE_SELECTORS,
    DETAIL_LOW_SIGNAL_PRICE_VISIBLE_MIN_DELTA,
    DETAIL_LOW_SIGNAL_PRICE_VISIBLE_RATIO,
    DETAIL_LOW_SIGNAL_ZERO_PRICE_SOURCE_SET,
    DETAIL_PARENT_VARIANT_PRICE_RATIO_MAX_DECIMAL,
    DETAIL_STRICT_PARENT_PRICE_SOURCE_SET,
)
from app.services.config.extraction_price_rules import (
    FIELD_SOURCE_DOM_TEXT,
    FIELD_SOURCE_JSON_LD,
)
from app.services.extract.detail.price.parsing import (
    decimal_is_cent_magnitude_copy,
    detail_currency_from_html,
    detail_current_price_currency_from_html,
    detail_jsonld_price_bundle,
    detail_original_price_from_html,
    detail_price_decimal,
    detail_price_from_html,
    detail_price_from_selector_text,
    detail_price_is_visible_magnitude_copy,
    detail_price_is_cent_magnitude_copy,
    format_detail_price_decimal,
    format_price_decimal,
    single_decimal_value,
)
from app.services.shared.field_coerce import (
    extract_currency_code,
    text_or_none,
)
from app.services.shared.currency_hints import (
    currency_hint_from_page_url,
    detail_currency_hint_is_host_level,
)
from app.services.normalizers import normalize_decimal_price

@dataclass(slots=True)
class _DetailPriceEvidence:
    soup: BeautifulSoup
    record_price_is_low_signal: bool
    jsonld_price_bundle: tuple[str | None, str | None, str | None]
    html_currency: str | None
    record_url: str
    expected_currency: str | None
    visible_price: object
    visible_price_currency: str | None
    currency: str | None = None
    html_currency_conflicts_with_host: bool = False
    visible_currency_conflicts_with_html: bool = False

@dataclass(frozen=True, slots=True)
class _DetailPriceSelection:
    price: object = None
    source: str = ""
    localized_override_applied: bool = False
    blocked: bool = False

def backfill_detail_price_from_html(
    record: dict[str, Any],
    *,
    html: str,
    soup: BeautifulSoup | None = None,
) -> None:
    if soup is None and not str(html or "").strip():
        return
    prepared_soup = soup if soup is not None else BeautifulSoup(str(html or ""), "html.parser")
    evidence = _collect_detail_price_evidence(record, prepared_soup)
    _reconcile_detail_price_currency(record, evidence)
    selection = _select_detail_price(record, evidence)
    _apply_selected_detail_price(record, evidence, selection)
    _split_owner._apply_detail_original_price(record, evidence, selection)
    _split_owner._drop_unavailable_dom_backfilled_detail_price(record)

def _collect_detail_price_evidence(
    record: dict[str, Any],
    soup: BeautifulSoup,
) -> _DetailPriceEvidence:
    jsonld_price_bundle = detail_jsonld_price_bundle(soup, currency=None)
    html_currency = detail_currency_from_html(
        soup,
        jsonld_price_bundle=jsonld_price_bundle,
    )
    record_url = text_or_none(record.get("url")) or ""
    expected_currency = text_or_none(currency_hint_from_page_url(record_url))
    preliminary_currency = text_or_none(record.get("currency")) or expected_currency or html_currency
    visible_price = detail_price_from_selector_text(
        soup,
        selectors=DETAIL_CURRENT_PRICE_SELECTORS,
        currency=preliminary_currency,
    )
    return _DetailPriceEvidence(
        soup=soup,
        record_price_is_low_signal=_split_owner._detail_price_value_is_low_signal(record.get("price")),
        jsonld_price_bundle=jsonld_price_bundle,
        html_currency=html_currency,
        record_url=record_url,
        expected_currency=expected_currency,
        visible_price=visible_price,
        visible_price_currency=(detail_current_price_currency_from_html(soup) if visible_price else None),
    )

def _reconcile_detail_price_currency(
    record: dict[str, Any],
    evidence: _DetailPriceEvidence,
) -> None:
    _apply_visible_price_currency(record, evidence)
    _prefer_visible_price_currency(evidence)
    evidence.html_currency_conflicts_with_host = _split_owner._html_currency_conflicts_with_strong_host_hint(
        html_currency=evidence.html_currency,
        expected_currency=evidence.expected_currency,
        page_url=evidence.record_url,
    )
    _drop_unverified_localized_price_evidence(record, evidence)
    evidence.visible_currency_conflicts_with_html = bool(
        evidence.visible_price and evidence.html_currency and evidence.expected_currency and evidence.html_currency != evidence.expected_currency
    )
    _drop_host_conflicting_currency_evidence(evidence)
    evidence.currency = (
        text_or_none(record.get("currency"))
        or (evidence.expected_currency if evidence.html_currency_conflicts_with_host and evidence.visible_price else None)
        or evidence.html_currency
    )
    if evidence.currency and record.get("currency") in (None, "", [], {}):
        record["currency"] = evidence.currency
        _split_owner.append_record_field_source(record, "currency", FIELD_SOURCE_DOM_TEXT)
    if not evidence.html_currency_conflicts_with_host and evidence.currency != evidence.jsonld_price_bundle[2]:
        evidence.jsonld_price_bundle = detail_jsonld_price_bundle(
            evidence.soup,
            currency=evidence.currency,
        )

def _prefer_visible_price_currency(evidence: _DetailPriceEvidence) -> None:
    if not evidence.visible_price_currency or not evidence.html_currency:
        return
    if evidence.visible_price_currency == evidence.html_currency:
        return
    evidence.html_currency = evidence.visible_price_currency
    evidence.jsonld_price_bundle = (None, None, None)

def _drop_host_conflicting_currency_evidence(evidence: _DetailPriceEvidence) -> None:
    if not evidence.html_currency_conflicts_with_host:
        return
    if _split_owner._detail_price_value_is_low_signal(evidence.visible_price):
        evidence.visible_price = None
    evidence.html_currency = None
    evidence.jsonld_price_bundle = (None, None, None)

def _apply_visible_price_currency(
    record: dict[str, Any],
    evidence: _DetailPriceEvidence,
) -> None:
    visible_currency = evidence.visible_price_currency
    if not visible_currency or text_or_none(record.get("currency")) in (
        None,
        visible_currency,
    ):
        return
    current_price = record.get("price")
    should_update = bool(
        current_price in (None, "", [], {})
        or detail_price_decimal(current_price) == detail_price_decimal(evidence.visible_price)
        or _split_owner._should_override_record_price_from_dom(
            record=record,
            dom_price=evidence.visible_price,
            record_price_is_low_signal=evidence.record_price_is_low_signal,
        )
    )
    if should_update:
        record["currency"] = visible_currency
        _split_owner.append_record_field_source(record, "currency", FIELD_SOURCE_DOM_TEXT)

def _drop_unverified_localized_price_evidence(
    record: dict[str, Any],
    evidence: _DetailPriceEvidence,
) -> None:
    conflict = bool(
        not evidence.visible_price
        and evidence.html_currency
        and evidence.expected_currency
        and evidence.html_currency != evidence.expected_currency
        and text_or_none(record.get("currency")) in (None, evidence.expected_currency)
    )
    if not conflict:
        return
    if not _split_owner._should_preserve_existing_localized_money(
        record,
        expected_currency=evidence.expected_currency,
        jsonld_price=evidence.jsonld_price_bundle[0],
    ):
        _split_owner._drop_unverified_localized_money(record)
    evidence.html_currency = None
    evidence.jsonld_price_bundle = (None, None, None)

def _select_detail_price(
    record: dict[str, Any],
    evidence: _DetailPriceEvidence,
) -> _DetailPriceSelection:
    jsonld_price, _jsonld_original_price, jsonld_currency = evidence.jsonld_price_bundle
    if _split_owner._unavailable_record_blocks_dom_price_backfill(
        record,
        jsonld_price=jsonld_price,
        visible_price=evidence.visible_price,
    ):
        return _DetailPriceSelection(blocked=True)
    localized_override, localized_source = _split_owner._localized_visible_or_structured_price_override(
        record=record,
        visible_price=evidence.visible_price,
        jsonld_price=jsonld_price,
        jsonld_currency=jsonld_currency,
        expected_currency=evidence.expected_currency,
    )
    price, source = _base_detail_price(record, evidence, jsonld_price)
    localized_applied = False
    if localized_override:
        price = localized_override
        source = localized_source
        localized_applied = True
    if evidence.visible_price and (
        detail_price_is_visible_magnitude_copy(price, evidence.visible_price)
        or _split_owner._should_override_record_price_from_dom(
            record=record,
            dom_price=evidence.visible_price,
            record_price_is_low_signal=evidence.record_price_is_low_signal,
        )
    ):
        price = evidence.visible_price
        source = FIELD_SOURCE_DOM_TEXT
    return _DetailPriceSelection(
        price=None if price in (None, "", [], {}) else price,
        source=source,
        localized_override_applied=localized_applied,
    )

def _base_detail_price(
    record: dict[str, Any],
    evidence: _DetailPriceEvidence,
    jsonld_price: object,
) -> tuple[object, str]:
    if evidence.html_currency_conflicts_with_host:
        return (
            evidence.visible_price or text_or_none(record.get("price")),
            FIELD_SOURCE_DOM_TEXT,
        )
    price = jsonld_price or detail_price_from_html(
        evidence.soup,
        currency=evidence.currency,
        jsonld_price_bundle=evidence.jsonld_price_bundle,
    )
    if price in (None, "", [], {}):
        price = text_or_none(record.get("price"))
    return price, FIELD_SOURCE_JSON_LD if jsonld_price else FIELD_SOURCE_DOM_TEXT

def _apply_selected_detail_price(
    record: dict[str, Any],
    evidence: _DetailPriceEvidence,
    selection: _DetailPriceSelection,
) -> None:
    if selection.blocked:
        _split_owner._drop_unavailable_dom_backfilled_detail_price(record)
        return
    if selection.price in (None, "", [], {}):
        return
    jsonld_price, _jsonld_original_price, jsonld_currency = evidence.jsonld_price_bundle
    if selection.source == FIELD_SOURCE_JSON_LD and jsonld_currency and text_or_none(record.get("currency")) != jsonld_currency:
        record["currency"] = jsonld_currency
        evidence.currency = jsonld_currency
        _split_owner.append_record_field_source(record, "currency", FIELD_SOURCE_JSON_LD)
    _apply_detail_record_price(
        record,
        selection,
        jsonld_price=jsonld_price,
        record_price_is_low_signal=evidence.record_price_is_low_signal,
    )
    selected_variant = record.get("selected_variant")
    if isinstance(selected_variant, dict):
        _backfill_variant_price(
            selected_variant,
            price=selection.price,
            currency=evidence.currency,
        )
    _backfill_detail_variant_prices(
        record,
        price=selection.price,
        currency=evidence.currency,
        source=selection.source,
        jsonld_currency=jsonld_currency,
    )
    if selection.localized_override_applied:
        _split_owner._drop_unverified_variant_money(record)

def _apply_detail_record_price(
    record: dict[str, Any],
    selection: _DetailPriceSelection,
    *,
    jsonld_price: object,
    record_price_is_low_signal: bool,
) -> None:
    if (
        selection.source == FIELD_SOURCE_JSON_LD
        and selection.price == jsonld_price
        and not (_split_owner.record_field_sources(record, "price") & DETAIL_AUTHORITATIVE_PRICE_SOURCE_SET)
    ):
        record["price"] = selection.price
        _split_owner.append_record_field_source(record, "price", FIELD_SOURCE_JSON_LD)
    if (
        _split_owner._should_override_record_price_from_dom(
            record=record,
            dom_price=selection.price,
            record_price_is_low_signal=record_price_is_low_signal,
        )
        or selection.localized_override_applied
    ):
        record["price"] = selection.price
        _split_owner.append_record_field_source(record, "price", selection.source)

def _backfill_variant_price(
    variant: dict[str, Any],
    *,
    price: object,
    currency: str | None,
) -> None:
    if (
        variant.get("price") not in (None, "", [], {})
        and not _split_owner._detail_price_value_is_low_signal(variant.get("price"))
        and not detail_price_is_cent_magnitude_copy(variant.get("price"), price)
    ):
        return
    variant["price"] = price
    if currency and variant.get("currency") in (None, "", [], {}):
        variant["currency"] = currency

def _backfill_detail_variant_prices(
    record: dict[str, Any],
    *,
    price: object,
    currency: str | None,
    source: str,
    jsonld_currency: str | None,
) -> None:
    variants = record.get("variants")
    if not isinstance(variants, list):
        return
    authoritative_variants = bool(_split_owner.record_field_sources(record, "variants") & DETAIL_AUTHORITATIVE_PRICE_SOURCE_SET)
    for variant in variants:
        if not isinstance(variant, dict):
            continue
        if source == FIELD_SOURCE_JSON_LD and jsonld_currency and _split_owner._detail_price_is_visible_outlier(variant.get("price"), price) and not authoritative_variants:
            variant["price"] = price
            variant["currency"] = jsonld_currency
            continue
        _backfill_variant_price(variant, price=price, currency=currency)

from . import reconciliation as _split_owner  # noqa: E402
from .reconciliation import (  # noqa: E402
    append_record_field_source, drop_low_signal_zero_detail_price, normalize_mismatched_host_currency_price, reconcile_detail_price_magnitudes,
    reconcile_detail_currency_with_url, reconcile_parent_price_against_variant_range, record_field_sources,
)

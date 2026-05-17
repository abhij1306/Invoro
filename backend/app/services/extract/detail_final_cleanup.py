from __future__ import annotations

from typing import Any

from bs4 import BeautifulSoup

from app.services.config.extraction_rules import (
    AVAILABILITY_IN_STOCK,
    AVAILABILITY_OUT_OF_STOCK,
    AVAILABILITY_UNKNOWN,
)
from app.services.shared.field_coerce import (
    clean_text,
    enforce_flat_variant_public_contract,
    text_or_none,
)
from app.services.extract import detail_image_cleanup as _image_cleanup
from app.services.extract import detail_money_repair as _money_repair
from app.services.extract import detail_record_sanitization as _record_sanitization
from app.services.extract import detail_variant_pruning as _variant_pruning
from app.services.extract.detail_dom_variant_extraction import (
    backfill_variants_from_dom_if_missing,
)
from app.services.extract.detail_numbered_options import (
    hydrate_numbered_variant_options_from_dom,
)
from app.services.extract.detail_price_core import (
    backfill_detail_price_from_html,
    reconcile_detail_currency_with_url,
    reconcile_detail_price_magnitudes,
    reconcile_parent_price_against_variant_range,
)
from app.services.extract.detail_text_sanitizer import sanitize_detail_long_text_fields
from app.services.extract.variant_record_normalization import normalize_variant_record

detail_image_matches_primary_family = _image_cleanup.detail_image_matches_primary_family
detail_title_looks_like_placeholder = (
    _record_sanitization.detail_title_looks_like_placeholder
)
sanitize_variant_row = _variant_pruning.sanitize_variant_row


def repair_ecommerce_detail_record_quality(
    record: dict[str, Any],
    *,
    html: str,
    page_url: str,
    requested_page_url: str | None = None,
    soup: Any | None = None,
    js_state_objects: object | None = None,
) -> None:
    _sanitize_ecommerce_detail_record(
        record,
        page_url=page_url,
        requested_page_url=requested_page_url,
        soup=soup,
        js_state_objects=js_state_objects,
    )
    if soup is None and not text_or_none(record.get("image_url")) and str(html or "").strip():
        parsed_soup = BeautifulSoup(str(html), "html.parser")
        _image_cleanup._backfill_detail_image_from_html(
            record,
            soup=parsed_soup,
            identity_url=text_or_none(requested_page_url) or page_url,
        )
        _image_cleanup._sanitize_detail_images(
            record,
            identity_url=text_or_none(requested_page_url) or page_url,
        )
    normalize_variant_record(record, finalize_contract=False)
    backfill_detail_price_from_html(record, html=html)
    reconcile_detail_currency_with_url(record, page_url=page_url)
    reconcile_detail_price_magnitudes(record)
    reconcile_parent_price_against_variant_range(record)
    _money_repair._normalize_detail_money_precision(record)
    _money_repair._repair_invalid_original_prices(record)
    _money_repair._drop_invalid_detail_discounts(record)
    _money_repair._repair_detail_variant_prices_and_identity(record)
    _default_unknown_availability_for_real_product(record)
    enforce_flat_variant_public_contract(record, page_url=page_url)


def _sanitize_ecommerce_detail_record(
    record: dict[str, Any],
    *,
    page_url: str,
    requested_page_url: str | None,
    soup: Any | None = None,
    js_state_objects: object | None = None,
) -> None:
    identity_url = text_or_none(requested_page_url) or page_url
    _record_sanitization._sanitize_detail_placeholder_scalars(
        record,
        identity_url=identity_url,
    )
    _record_sanitization._sanitize_detail_identity_scalars(
        record,
        identity_url=identity_url,
    )
    hydrate_numbered_variant_options_from_dom(record, soup=soup)
    if soup is not None:
        backfill_variants_from_dom_if_missing(
            record,
            soup=soup,
            page_url=page_url,
            js_state_objects=js_state_objects if isinstance(js_state_objects, dict) else None,
        )
        _image_cleanup._backfill_detail_image_from_html(
            record,
            soup=soup,
            identity_url=identity_url,
        )
    _variant_pruning._sanitize_detail_variant_payload(
        record,
        identity_url=identity_url,
    )
    sanitize_detail_long_text_fields(
        record,
        title_hint=_record_sanitization._detail_title_from_url(identity_url),
    )
    _image_cleanup._sanitize_detail_images(record, identity_url=identity_url)
    _image_cleanup._backfill_parent_image_from_variants(record)
    _reconcile_detail_availability_from_variants(record)


def _default_unknown_availability_for_real_product(record: dict[str, Any]) -> None:
    if record.get("availability") not in (None, "", [], {}):
        return
    if not any(
        record.get(field_name) not in (None, "", [], {})
        for field_name in (
            "price",
            "original_price",
            "image_url",
            "variants",
        )
    ):
        return
    if detail_title_looks_like_placeholder(clean_text(record.get("title"))):
        return
    record["availability"] = AVAILABILITY_UNKNOWN


def _reconcile_detail_availability_from_variants(record: dict[str, Any]) -> None:
    variants = [row for row in record.get("variants") or [] if isinstance(row, dict)]
    if not variants or record.get("availability") not in (None, "", [], {}):
        return
    values = {text_or_none(row.get("availability")) for row in variants}
    values.discard(None)
    if values and values <= {AVAILABILITY_OUT_OF_STOCK, AVAILABILITY_UNKNOWN}:
        record["availability"] = AVAILABILITY_OUT_OF_STOCK
    elif AVAILABILITY_IN_STOCK in values:
        record["availability"] = AVAILABILITY_IN_STOCK

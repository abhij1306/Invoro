from __future__ import annotations

import json
import logging
import re
from decimal import Decimal
from functools import lru_cache
from typing import Any
from urllib.parse import unquote, urlparse

from bs4 import BeautifulSoup

from app.services.config.extraction_rules import (
    AVAILABILITY_IN_STOCK,
    AVAILABILITY_OUT_OF_STOCK,
    AVAILABILITY_UNKNOWN,
    CANDIDATE_PLACEHOLDER_VALUES,
    CATEGORY_PLACEHOLDER_VALUES,
    DETAIL_CATEGORY_BRANCH_STOP_TOKENS,
    DETAIL_CATEGORY_LABEL_PREFIXES,
    DETAIL_CATEGORY_UI_TOKENS,
    DETAIL_BREADCRUMB_SEPARATOR_LABELS,
    DETAIL_BREADCRUMB_TITLE_DUPLICATE_RATIO,
    IMAGE_FAMILY_NOISE_TOKENS,
    IMAGE_PATH_TOKENS,
    MATERIAL_KEYWORDS,
    ORG_SUFFIXES,
    DETAIL_LOW_SIGNAL_PARENT_MIN,
    DETAIL_LOW_SIGNAL_PRICE_MAX,
    DETAIL_NON_PRODUCT_IMAGE_URL_HINTS,
    DETAIL_PRICE_COMPARISON_TOLERANCE,
    PLACEHOLDER_IMAGE_URL_PATTERNS,
    VARIANT_OPTION_LABEL_MAX_WORDS,
    WAF_QUEUE_PATTERNS,
)
from app.services.config.variant_policy import (
    DETAIL_VARIANT_SIZE_MIN_FOR_NUMERIC_PARENT_DROP,
)
from app.services.shared.field_coerce import (
    absolute_url,
    clean_text,
    enforce_flat_variant_public_contract,
    extract_urls,
    text_or_none,
)
from app.services.field_url_normalization import same_site
from app.services.dom.selector_engine import dedupe_image_urls, upgrade_low_resolution_image_url
from app.services.extract.variant_axis import (
    normalized_variant_axis_key,
    variant_axis_allowed_single_tokens,
    variant_axis_name_is_semantic,
)
from app.services.extract.variant_option_value import (
    variant_option_value_matches_noise_token,
    variant_option_value_is_noise as _variant_option_value_is_noise,
)
from app.services.extract.detail_identity_core import (
    detail_identity_codes_match,
    detail_identity_codes_from_record_fields as _detail_identity_codes_from_record_fields,
    detail_identity_codes_from_url as _detail_identity_codes_from_url,
    detail_identity_tokens as _detail_identity_tokens,
    detail_title_from_url as _detail_title_from_url,
    detail_url_looks_like_product as _detail_url_looks_like_product,
    detail_url_matches_requested_identity as _detail_url_matches_requested_identity,
    record_matches_requested_detail_identity as _record_matches_requested_detail_identity,
    semantic_detail_identity_tokens as _semantic_detail_identity_tokens,
)
from app.services.extract.detail_dom_variant_extraction import (
    backfill_variants_from_dom_if_missing,
)
from app.services.extract.detail_numbered_options import (
    hydrate_numbered_variant_options_from_dom,
)
from app.services.extract.detail_raw_signals import detail_breadcrumb_is_root_label
from app.services.extract.detail_price_core import (
    backfill_detail_price_from_html,
    detail_price_decimal,
    format_detail_price_decimal,
    reconcile_detail_currency_with_url,
    reconcile_detail_price_magnitudes,
    reconcile_parent_price_against_variant_range,
)
from app.services.extract.variant_record_normalization import normalize_variant_record
from app.services.extract.detail_text_sanitizer import (
    detail_product_type_is_low_signal,
    detail_scalar_size_is_low_signal,
    detail_title_value_is_low_signal,
    sanitize_detail_long_text_fields,
)

logger = logging.getLogger(__name__)

_UUID_LIKE_PATTERN = re.compile(r"(?i)^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$")
_MERCH_CODE_PATTERN = re.compile(r"\b[A-Z0-9]{2,}(?:-[A-Z0-9]{2,})+\b", re.I)
_PLACEHOLDER_IMAGE_URL_PATTERNS_LOWER = tuple(
    str(pattern).lower()
    for pattern in tuple(PLACEHOLDER_IMAGE_URL_PATTERNS or ())
    if str(pattern).strip()
)
_NON_PRODUCT_IMAGE_HINTS_LOWER = tuple(
    str(pattern).lower()
    for pattern in tuple(DETAIL_NON_PRODUCT_IMAGE_URL_HINTS or ())
    if str(pattern).strip()
)
_DETAIL_BASE_PLACEHOLDER_TITLE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"^404$"),
    re.compile(r"^(?:error\s*)?404\b", re.I),
    re.compile(r"^error\s+page$", re.I),
    re.compile(r"^your\s+ai-generated\s+outfit$", re.I),
    re.compile(r"^oops,?\s+something\s+went\s+wrong\.?$", re.I),
    re.compile(
        r"^oops!? the page you(?:'|’)re looking for can(?:'|’)t be found\.?$", re.I
    ),
    re.compile(r"^page not found$", re.I),
    re.compile(r"^not found$", re.I),
    re.compile(r"^access denied$", re.I),
    re.compile(r"^adding\s+to\s+cart\.{0,3}$", re.I),
)
def _compile_detail_waf_queue_title_patterns() -> tuple[re.Pattern[str], ...]:
    patterns: list[re.Pattern[str]] = []
    for pattern in tuple(WAF_QUEUE_PATTERNS or ()):
        if not str(pattern).strip():
            continue
        try:
            patterns.append(re.compile(str(pattern), re.I))
        except re.error:
            logger.warning("Skipping invalid WAF queue title pattern: %r", pattern)
    return tuple(patterns)


_DETAIL_WAF_QUEUE_TITLE_PATTERNS = _compile_detail_waf_queue_title_patterns()
_material_keyword_tokens = frozenset(
    str(token).strip().lower()
    for token in tuple(MATERIAL_KEYWORDS or ())
    if str(token).strip()
)
_DETAIL_PLACEHOLDER_TITLE_PATTERNS: tuple[re.Pattern[str], ...] = (
    *_DETAIL_BASE_PLACEHOLDER_TITLE_PATTERNS,
    *_DETAIL_WAF_QUEUE_TITLE_PATTERNS,
)
_ORG_SUFFIX_PATTERN = (
    re.compile(
        r"\b(?:"
        + "|".join(re.escape(token) for token in sorted(ORG_SUFFIXES))
        + r")\b",
        re.I,
    )
    if ORG_SUFFIXES
    else None
)


from app.services.extract import detail_record_sanitization as _record_sanitization
from app.services.extract import detail_variant_pruning as _variant_pruning

_looks_like_uuid = _record_sanitization._looks_like_uuid
_variant_title_is_low_signal = _variant_pruning._variant_title_is_low_signal
_variant_title_from_parent = _variant_pruning._variant_title_from_parent

def _repair_detail_variant_prices_and_identity(record: dict[str, Any]) -> None:
    parent_price = text_or_none(record.get("price"))
    parent_availability = text_or_none(record.get("availability"))
    parent_sku = text_or_none(record.get("sku"))
    parent_title = clean_text(record.get("title"))
    rows = [row for row in list(record.get("variants") or []) if isinstance(row, dict)]
    for row in rows:
        if parent_price:
            row_price = text_or_none(row.get("price"))
            if (
                not row_price
                or _price_is_cents_copy(row_price, parent_price)
                or _price_is_low_signal_copy(row_price, parent_price)
            ):
                row["price"] = parent_price
        if (
            parent_availability
            and row.get("availability") in (None, "", [], {})
            and any(
                row.get(field_name) not in (None, "", [], {})
                for field_name in (
                    "sku",
                    "variant_id",
                    "barcode",
                    "image_url",
                    "title",
                    "size",
                    "color",
                    "url",
                )
            )
        ):
            row["availability"] = parent_availability
        row_sku = text_or_none(row.get("sku"))
        if row_sku and _looks_like_uuid(row_sku):
            row.pop("sku", None)
        barcode = text_or_none(row.get("barcode"))
        if (
            barcode
            and row.get("sku") == barcode
            and len(re.sub(r"\D+", "", barcode)) <= 8
        ):
            row.pop("barcode", None)
        title = clean_text(row.get("title"))
        if title and _variant_title_is_low_signal(title):
            replacement = _variant_title_from_parent(parent_title, row)
            if replacement:
                row["title"] = replacement
            else:
                row.pop("title", None)
    variant_rows = [
        row for row in list(record.get("variants") or []) if isinstance(row, dict)
    ]
    if (
        parent_availability == AVAILABILITY_IN_STOCK
        and variant_rows
        and all(
            text_or_none(row.get("availability")) == parent_availability
            for row in variant_rows
        )
    ):
        for row in variant_rows:
            row.pop("availability", None)
    if parent_sku and _looks_like_uuid(parent_sku):
        record.pop("sku", None)


def _price_is_cents_copy(value: str, parent_price: str) -> bool:
    value_number = detail_price_decimal(value)
    parent_number = detail_price_decimal(parent_price)
    if value_number is None or parent_number is None or parent_number <= 0:
        return False
    return abs(value_number - (parent_number * 100)) < Decimal(
        str(DETAIL_PRICE_COMPARISON_TOLERANCE)
    )


def _price_is_low_signal_copy(value: str, parent_price: str) -> bool:
    value_number = detail_price_decimal(value)
    parent_number = detail_price_decimal(parent_price)
    if value_number is None or parent_number is None:
        return False
    return Decimal("0") < value_number <= Decimal(
        str(DETAIL_LOW_SIGNAL_PRICE_MAX)
    ) and parent_number >= Decimal(str(DETAIL_LOW_SIGNAL_PARENT_MIN))


def _normalize_detail_money_precision(record: dict[str, Any]) -> None:
    for container in _detail_money_containers(record):
        if not isinstance(container, dict):
            continue
        if not text_or_none(container.get("currency")):
            continue
        for field_name in ("price", "original_price"):
            normalized = _money_two_decimals(container.get(field_name))
            if normalized is not None:
                container[field_name] = normalized


def _detail_money_containers(record: dict[str, Any]) -> list[dict[str, Any]]:
    containers = [record]
    variants = record.get("variants")
    if isinstance(variants, list):
        containers.extend(row for row in variants if isinstance(row, dict))
    return containers


def _money_two_decimals(value: object) -> str | None:
    text = text_or_none(value)
    if not text or not re.fullmatch(r"\d+(?:\.\d+)?", text):
        return None
    return format_detail_price_decimal(text)


def _drop_invalid_detail_discounts(record: dict[str, Any]) -> None:
    price = detail_price_decimal(record.get("price"))
    original_price = detail_price_decimal(record.get("original_price"))
    discount_amount = detail_price_decimal(record.get("discount_amount"))
    discount_percentage = detail_price_decimal(record.get("discount_percentage"))
    if discount_percentage is not None and not (0 < discount_percentage <= 100):
        record.pop("discount_percentage", None)
    if discount_amount is None:
        return
    if discount_amount <= 0:
        record.pop("discount_amount", None)
        return
    if price is not None and discount_amount > price:
        record.pop("discount_amount", None)
        return
    if original_price is not None and discount_amount > original_price:
        record.pop("discount_amount", None)


def _repair_invalid_original_prices(record: dict[str, Any]) -> None:
    for container in _detail_money_containers(record):
        if not isinstance(container, dict):
            continue
        price = detail_price_decimal(container.get("price"))
        original_price = detail_price_decimal(container.get("original_price"))
        if price is None or original_price is None or original_price >= price:
            continue
        normalized_price = _money_two_decimals(container.get("price"))
        if normalized_price is not None:
            container["original_price"] = normalized_price

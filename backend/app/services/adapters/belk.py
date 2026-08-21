# ruff: noqa: F401
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from selectolax.lexbor import LexborHTMLParser

from app.services.adapters.base import AdapterResult, BaseAdapter
from app.services.config.adapter_runtime_settings import adapter_runtime_settings
from app.services.config.extraction_rules import (
    BELK_BRAND_SELECTORS,
    BELK_CARD_TITLE_ATTRS,
    BELK_COLOR_MAP_KEY,
    BELK_COLOR_NAME_KEYS,
    BELK_IMAGE_SELECTORS,
    BELK_PRODUCT_BARCODE_KEYS,
    BELK_PRICE_SELECTORS,
    BELK_PRODUCT_BRAND_KEYS,
    BELK_PRODUCT_CARD_SELECTORS,
    BELK_PRODUCT_ID_KEYS,
    BELK_PRODUCT_IMAGE_KEYS,
    BELK_PRODUCT_ORIGINAL_PRICE_KEYS,
    BELK_PRODUCT_PRICE_KEYS,
    BELK_PRODUCT_TITLE_KEYS,
    BELK_PRODUCT_URL_KEYS,
    BELK_SKU_ARRAY_ID_KEY,
    BELK_SKU_ARRAY_IMAGE_KEY,
    BELK_SKU_ARRAY_INVENTORY_KEY,
    BELK_SKU_ARRAY_ORIGINAL_PRICE_KEY,
    BELK_SKU_ARRAY_OUT_OF_STOCK_KEY,
    BELK_SKU_ARRAY_PRICE_KEY,
    BELK_SKU_ARRAY_UPC_KEY,
    BELK_TITLE_MAX_CHARS,
    BELK_TITLE_MIN_CHARS,
    BELK_TITLE_SELECTORS,
    BELK_VARIANT_ID_KEYS,
    LISTING_BRAND_MAX_WORDS,
)
from app.services.extract.listing_candidate_ranking import looks_like_utility_title
from app.services.extract.variant_axis import normalized_variant_axis_key
from app.services.extract.variant_normalization.contract import (
    flatten_variants_for_public_output,
)
from app.services.shared.field_coerce import (
    absolute_url,
    clean_text,
    coerce_field_value,
    extract_price_text,
    finalize_record,
    infer_brand_from_product_url,
    infer_brand_from_title_marker,
)
from app.services.js_state.helpers import compact_dict, normalize_price
from app.services.structured_sources import harvest_js_state_objects

_BELK_PRODUCT_TITLE_KEY_SET = frozenset(BELK_PRODUCT_TITLE_KEYS)
_BELK_PRODUCT_URL_KEY_SET = frozenset(BELK_PRODUCT_URL_KEYS)
_BELK_PRODUCT_SIGNAL_KEY_SET = frozenset((*BELK_PRODUCT_BRAND_KEYS, *BELK_PRODUCT_PRICE_KEYS, *BELK_PRODUCT_IMAGE_KEYS))
_BELK_VARIANT_ID_KEY_SET = frozenset(BELK_VARIANT_ID_KEYS)

class BelkAdapter(BaseAdapter):
    name = "belk"
    platform_family = "belk"

    async def can_handle(self, url: str, html: str) -> bool:
        host = (urlparse(str(url or "")).hostname or "").lower()
        return host == "belk.com" or host.endswith(".belk.com")

    async def extract(self, url: str, html: str, surface: str, proxy: str | None = None) -> AdapterResult:
        normalized_surface = str(surface or "").strip().lower()
        records: list[dict[str, Any]] = []
        if normalized_surface == "ecommerce_listing":
            records.extend(_extract_listing_records(url, html))
        elif normalized_surface == "ecommerce_detail":
            record = _extract_detail_record(url, html)
            if record:
                records.append(record)
        return self._result(records)

def _extract_listing_records(page_url: str, html: str) -> list[dict[str, Any]]:
    product_limit = max(0, int(adapter_runtime_settings.belk_max_products))
    if product_limit <= 0:
        return []
    state_index = _state_product_index(page_url, html)
    records: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    state_by_identity = {identity: record for record in state_index.values() if (identity := _split_owner._belk_record_identity(record))}
    for record in _split_owner._dom_listing_records(page_url, html):
        merged = _merge_belk_state_record(record, state_index, state_by_identity)
        _append_belk_listing_record(records, merged, seen_urls=seen_urls)
        if len(records) >= product_limit:
            return records
    for url, record in state_index.items():
        if url in seen_urls:
            continue
        _append_belk_listing_record(records, record, seen_urls=seen_urls)
        if len(records) >= product_limit:
            break
    return records[:product_limit]

def _merge_belk_state_record(
    record: dict[str, Any],
    state_index: dict[str, dict[str, Any]],
    state_by_identity: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    url = str(record.get("url") or "")
    state_record = state_index.get(url)
    if state_record is None and (identity := _split_owner._belk_record_identity(record)):
        state_record = state_by_identity.get(identity)
    if not state_record:
        return record
    return {
        **state_record,
        **{key: value for key, value in record.items() if value not in (None, "", [], {})},
    }

def _append_belk_listing_record(records: list[dict[str, Any]], record: dict[str, Any], *, seen_urls: set[str]) -> None:
    url = str(record.get("url") or "")
    if not url or url in seen_urls:
        return
    finalized = _split_owner._finalize_adapter_record(record, surface="ecommerce_listing")
    final_url = str(finalized.get("url") or "")
    if not final_url or final_url in seen_urls:
        return
    seen_urls.add(final_url)
    records.append(finalized)

def _extract_detail_record(page_url: str, html: str) -> dict[str, Any] | None:
    page_path = (urlparse(page_url).path or "").rstrip("/").lower()
    for record in _state_product_records(page_url, html, target_path=page_path):
        record_url = str(record.get("url") or "")
        if (urlparse(record_url).path or "").rstrip("/").lower() == page_path:
            return _split_owner._finalize_adapter_record(record, surface="ecommerce_detail")
    dom_records = _split_owner._dom_listing_records(page_url, html)
    if len(dom_records) == 1:
        return _split_owner._finalize_adapter_record(dom_records[0], surface="ecommerce_detail")
    return None

def _state_product_index(page_url: str, html: str) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for record in _state_product_records(page_url, html):
        url = str(record.get("url") or "")
        if url:
            index[url] = record
        if len(index) >= adapter_runtime_settings.belk_max_products:
            return index
    return index

def _state_product_records(
    page_url: str,
    html: str,
    *,
    target_path: str | None = None,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for root in _belk_state_roots(html):
        parts = _collect_state_payload_parts(root)
        variant_objects_by_id = _split_owner._variant_objects_by_id(parts.variant_objects)
        for product in parts.products:
            record = _record_from_payload(
                product,
                page_url=page_url,
                variant_objects_by_id=variant_objects_by_id,
                color_name_by_code=parts.color_name_by_code,
            )
            if target_path and _record_path(record) == target_path:
                return [record]
            records.append(record)
            if len(records) >= adapter_runtime_settings.belk_max_products:
                return records
    return records

def _record_path(record: dict[str, Any]) -> str:
    return (urlparse(str(record.get("url") or "")).path or "").rstrip("/").lower()

def _belk_state_roots(html: str) -> list[Any]:
    raw = str(html or "").strip()
    roots: list[Any] = []
    if raw and raw[0] in "[{":
        try:
            roots.append(json.loads(raw))
        except json.JSONDecodeError:
            # Not a raw JSON document; fall back to JS-state harvesting below.
            pass
    roots.extend(harvest_js_state_objects(None, html).values())
    return roots

@dataclass(slots=True)
class _BelkStatePayloadParts:
    products: list[dict[str, Any]]
    variant_objects: list[dict[str, Any]]
    color_name_by_code: dict[str, str]

def _collect_state_payload_parts(root: object) -> _BelkStatePayloadParts:
    products: list[dict[str, Any]] = []
    variant_objects: list[dict[str, Any]] = []
    color_name_by_code: dict[str, str] = {}
    product_limit = adapter_runtime_settings.belk_max_products

    def visit(node: object, depth: int) -> None:
        if depth > 60:
            return
        if isinstance(node, dict):
            color_map = node.get(BELK_COLOR_MAP_KEY)
            if isinstance(color_map, dict):
                for code, value in color_map.items():
                    code_text = clean_text(code)
                    if not code_text or code_text in color_name_by_code:
                        continue
                    name = _color_name_from_entry(value)
                    if name:
                        color_name_by_code[code_text] = name

            keys = {str(k) for k in node.keys()}
            if len(variant_objects) < product_limit and (keys & _BELK_VARIANT_ID_KEY_SET) and "size" in keys:
                variant_objects.append(node)
            if len(products) < product_limit and _looks_like_product_payload(node):
                products.append(node)

            for child in node.values():
                if isinstance(child, (dict, list)):
                    visit(child, depth + 1)
            return
        if isinstance(node, list):
            for child in node:
                if isinstance(child, (dict, list)):
                    visit(child, depth + 1)

    visit(root, 0)
    return _BelkStatePayloadParts(
        products=products,
        variant_objects=variant_objects,
        color_name_by_code=color_name_by_code,
    )

def _color_name_from_entry(value: object) -> str | None:
    if not isinstance(value, dict):
        return None
    for key in BELK_COLOR_NAME_KEYS:
        name = clean_text(value.get(key))
        if name:
            return name
    return None

def _looks_like_product_payload(payload: dict[str, Any]) -> bool:
    keys = set(payload)
    if not (keys & _BELK_PRODUCT_TITLE_KEY_SET and keys & _BELK_PRODUCT_URL_KEY_SET and keys & _BELK_PRODUCT_SIGNAL_KEY_SET):
        return False
    return bool(
        _split_owner._first_payload_field(payload, field_name="title", page_url="", keys=BELK_PRODUCT_TITLE_KEYS)
        and _split_owner._first_payload_field(payload, field_name="url", page_url="", keys=BELK_PRODUCT_URL_KEYS)
        and (
            _split_owner._first_payload_field(payload, field_name="brand", page_url="", keys=BELK_PRODUCT_BRAND_KEYS)
            or _split_owner._first_payload_field(payload, field_name="price", page_url="", keys=BELK_PRODUCT_PRICE_KEYS)
            or _split_owner._first_payload_field(
                payload,
                field_name="image_url",
                page_url="",
                keys=BELK_PRODUCT_IMAGE_KEYS,
            )
        )
    )

def _record_from_payload(
    product: dict[str, Any],
    *,
    page_url: str,
    variant_objects: list[dict[str, Any]] | None = None,
    variant_objects_by_id: dict[str, dict[str, Any]] | None = None,
    color_name_by_code: dict[str, str] | None = None,
) -> dict[str, Any]:
    title = _split_owner._first_payload_field(product, field_name="title", page_url=page_url, keys=BELK_PRODUCT_TITLE_KEYS)
    brand = _split_owner._first_payload_field(product, field_name="brand", page_url=page_url, keys=BELK_PRODUCT_BRAND_KEYS)
    price_value = _split_owner._first_payload_field(product, field_name="price", page_url=page_url, keys=BELK_PRODUCT_PRICE_KEYS)
    original_price_value = _split_owner._first_payload_field(
        product,
        field_name="original_price",
        page_url=page_url,
        keys=BELK_PRODUCT_ORIGINAL_PRICE_KEYS,
    )
    image = _split_owner._first_payload_field(product, field_name="image_url", page_url=page_url, keys=BELK_PRODUCT_IMAGE_KEYS)
    url = _split_owner._first_payload_field(product, field_name="url", page_url=page_url, keys=BELK_PRODUCT_URL_KEYS)
    # Belk's React PDP `utag_data` exposes per-SKU parallel arrays (sku_id[i] <-> sku_upc[i] <-> ...).
    # Build variant rows from those arrays joined to the variant objects, and take the
    # product-level barcode from the selected/first in-stock variant UPC.
    sku_variants = _split_owner._variants_from_sku_arrays(
        product,
        page_url=page_url,
        variant_objects=variant_objects or [],
        variant_objects_by_id=variant_objects_by_id,
        color_name_by_code=color_name_by_code or {},
    )
    if sku_variants:
        barcode = _split_owner._primary_variant_barcode(sku_variants)
    else:
        barcode = _split_owner._first_nested_payload_field(
            product,
            field_name="barcode",
            page_url=page_url,
            keys=BELK_PRODUCT_BARCODE_KEYS,
        )
    if brand in (None, "", [], {}):
        brand = _split_owner._infer_belk_brand_from_url(url=str(url or ""), title=title)
    currency = coerce_field_value("currency", product, page_url)
    if currency in (None, "", [], {}):
        for key in (*BELK_PRODUCT_PRICE_KEYS, *BELK_PRODUCT_ORIGINAL_PRICE_KEYS):
            nested_value = product.get(key)
            if not isinstance(nested_value, dict):
                continue
            currency = coerce_field_value("currency", nested_value, page_url)
            if currency not in (None, "", [], {}):
                break
    variants = sku_variants or _variants_from_payload(
        product,
        page_url=page_url,
        product_url=str(url or page_url or ""),
        currency=currency,
    )
    return compact_dict(
        {
            "title": title,
            "brand": brand,
            "price": normalize_price(price_value, interpret_integral_as_cents=False),
            "original_price": normalize_price(original_price_value, interpret_integral_as_cents=False),
            "currency": currency,
            "image_url": image,
            "sku_upc": barcode,
            "barcode": barcode,
            "product_id": _split_owner._first_payload_field(
                product,
                field_name="product_id",
                page_url=page_url,
                keys=BELK_PRODUCT_ID_KEYS,
            ),
            "url": url,
            "variants": variants,
            "variant_count": len(variants or []) or None,
        }
    )

def _variants_from_payload(
    product: dict[str, Any],
    *,
    page_url: str,
    product_url: str,
    currency: object,
) -> list[dict[str, object]] | None:
    raw_variants = product.get("variants")
    if not isinstance(raw_variants, list):
        return None
    option_names = _option_names(product.get("options"))
    variants: list[dict[str, object]] = []
    for raw_variant in raw_variants:
        if not isinstance(raw_variant, dict):
            continue
        variant = _variant_from_payload(
            raw_variant,
            option_names=option_names,
            page_url=page_url,
            currency=currency,
        )
        if variant:
            variants.append(variant)
    return flatten_variants_for_public_output(variants, page_url=product_url or page_url)

def _option_names(raw_options: object) -> list[str]:
    names: list[str] = []
    if not isinstance(raw_options, list):
        return names
    for option in raw_options:
        label: object
        if isinstance(option, str):
            label = option
        elif isinstance(option, dict):
            label = option.get("name") or option.get("title") or option.get("label")
        else:
            label = None
        cleaned = clean_text(label)
        if cleaned:
            names.append(cleaned)
    return names

def _variant_from_payload(
    variant: dict[str, Any],
    *,
    option_names: list[str],
    page_url: str,
    currency: object,
) -> dict[str, object] | None:
    row: dict[str, object] = {}
    sku = _first_clean_value(variant, ("sku", "skuId", "sku_id", "id", "variantId", "variant_id"))
    if sku:
        row["sku"] = sku
    _apply_belk_variant_fields(row, variant, page_url=page_url, currency=currency)
    option_values = _variant_option_values(variant, option_names=option_names)
    if option_values:
        row["option_values"] = option_values
        for axis_key in ("color", "size"):
            if option_values.get(axis_key):
                row[axis_key] = option_values[axis_key]
    if not any(row.get(axis_key) for axis_key in ("color", "size")):
        _apply_direct_belk_axes(row, variant)
    return row or None

def _first_clean_value(payload: dict[str, Any], keys: tuple[str, ...]) -> str:
    return next((value for key in keys if (value := clean_text(payload.get(key)))), "")

def _apply_belk_variant_fields(row: dict[str, object], variant: dict[str, Any], *, page_url: str, currency: object) -> None:
    raw_price = next(
        (variant.get(key) for key in ("price", "salePrice", "sellingPrice") if variant.get(key)),
        None,
    )
    if (price := normalize_price(raw_price, interpret_integral_as_cents=False)) is not None:
        row["price"] = price
    if variant_currency := coerce_field_value("currency", variant, page_url) or currency:
        row["currency"] = str(variant_currency)
    for field, value in (
        ("availability", _variant_availability(variant)),
        ("stock_quantity", _variant_stock_quantity(variant)),
        ("image_url", _variant_image_url(variant, page_url=page_url)),
    ):
        if value not in (None, "", [], {}):
            row[field] = value

def _apply_direct_belk_axes(row: dict[str, object], variant: dict[str, Any]) -> None:
    for axis_key in ("color", "size"):
        if value := clean_text(variant.get(axis_key)):
            row[axis_key] = value

def _variant_option_values(
    variant: dict[str, Any],
    *,
    option_names: list[str],
) -> dict[str, str]:
    option_values: dict[str, str] = {}
    raw_options = variant.get("options")
    variant_options = raw_options if isinstance(raw_options, list) else []
    max_options = max(len(option_names), len(variant_options), 3)
    for index in range(1, max_options + 1):
        axis_name = option_names[index - 1] if index - 1 < len(option_names) else f"option_{index}"
        axis_key = normalized_variant_axis_key(axis_name)
        if not axis_key:
            continue
        value = variant.get(f"option{index}")
        if value in (None, "", [], {}) and index - 1 < len(variant_options):
            value = variant_options[index - 1]
        cleaned = clean_text(value)
        if cleaned:
            option_values[axis_key] = cleaned
    return option_values

def _variant_availability(variant: dict[str, Any]) -> str | None:
    value = variant.get("availability")
    coerced = coerce_field_value("availability", value, "")
    if coerced:
        return str(coerced)
    available = variant.get("available")
    if isinstance(available, bool):
        return "in_stock" if available else "out_of_stock"
    if isinstance(available, (int, float)):
        return "in_stock" if available else "out_of_stock"
    if isinstance(available, str):
        lowered = available.strip().lower()
        if lowered in {"true", "1", "yes", "available", "in stock", "instock"}:
            return "in_stock"
        if lowered in {"false", "0", "no", "sold out", "out of stock", "outofstock"}:
            return "out_of_stock"
    return None

def _variant_stock_quantity(variant: dict[str, Any]) -> int | None:
    for key in (
        "stock_quantity",
        "stockQuantity",
        "inventory_quantity",
        "inventoryQuantity",
    ):
        value = variant.get(key)
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            continue
    return None

def _variant_image_url(variant: dict[str, Any], *, page_url: str) -> str | None:
    image = variant.get("image") or variant.get("featured_image") or variant.get("featuredImage")
    if isinstance(image, dict):
        image = image.get("url") or image.get("src")
    cleaned = clean_text(image)
    return absolute_url(page_url, cleaned) if cleaned else None

from . import belk_dom as _split_owner  # noqa: E402

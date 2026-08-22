from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from selectolax.lexbor import LexborHTMLParser

from app.services.config.adapter_runtime_settings import adapter_runtime_settings
from app.services.config.extraction_rules import (
    BELK_BRAND_SELECTORS, BELK_CARD_TITLE_ATTRS, BELK_IMAGE_SELECTORS, BELK_PRICE_SELECTORS, BELK_PRODUCT_CARD_SELECTORS,
    BELK_SKU_ARRAY_ID_KEY, BELK_SKU_ARRAY_IMAGE_KEY, BELK_SKU_ARRAY_INVENTORY_KEY, BELK_SKU_ARRAY_ORIGINAL_PRICE_KEY,
    BELK_SKU_ARRAY_OUT_OF_STOCK_KEY, BELK_SKU_ARRAY_PRICE_KEY, BELK_SKU_ARRAY_UPC_KEY, BELK_TITLE_MAX_CHARS,
    BELK_TITLE_MIN_CHARS, BELK_TITLE_SELECTORS, BELK_VARIANT_ID_KEYS, LISTING_BRAND_MAX_WORDS,
)
from app.services.extract.listing_candidate_ranking import looks_like_utility_title
from app.services.extract.variant_normalization.contract import flatten_variants_for_public_output
from app.services.js_state.helpers import compact_dict, normalize_price
from app.services.shared.field_coerce import (
    absolute_url, clean_text, coerce_field_value, extract_price_text, finalize_record, infer_brand_from_product_url, infer_brand_from_title_marker,
)


def _dom_listing_records(page_url: str, html: str) -> list[dict[str, Any]]:
    parser = LexborHTMLParser(html)
    records: list[dict[str, Any]] = []
    seen_urls: set[str] = set()
    for node in _product_card_nodes(parser):
        record = _record_from_card(node, page_url=page_url)
        url = str(record.get("url") or "")
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        records.append(record)
        if len(records) >= adapter_runtime_settings.belk_max_products:
            break
    return records

def _product_card_nodes(parser: LexborHTMLParser) -> list[Any]:
    nodes: list[Any] = []
    seen: set[str] = set()
    for selector in BELK_PRODUCT_CARD_SELECTORS:
        try:
            matches = parser.css(str(selector))
        except Exception:
            matches = []
        for node in matches:
            key = str(getattr(node, "html", "") or "")
            if not key or key in seen:
                continue
            seen.add(key)
            nodes.append(node)
    return nodes

def _record_from_card(node: Any, *, page_url: str) -> dict[str, Any]:
    anchor = node.css_first("a[href]")
    href = _attr(anchor, "href") if anchor is not None else ""
    image = _first_selector_attr(node, BELK_IMAGE_SELECTORS, ("src", "data-src", "srcset"))
    image_title = _first_selector_attr(
        node,
        BELK_IMAGE_SELECTORS,
        ("alt", "title", "aria-label"),
    )
    title = _first_belk_title(node) or _first_node_attr(node, BELK_CARD_TITLE_ATTRS) or image_title
    url = absolute_url(page_url, href)
    brand = _first_selector_text(node, BELK_BRAND_SELECTORS) or infer_brand_from_title_marker(title) or _infer_belk_brand_from_url(url=url, title=title)
    return compact_dict(
        {
            "title": title,
            "brand": brand,
            "price": normalize_price(
                _first_selector_text(node, BELK_PRICE_SELECTORS) or extract_price_text(node.text(separator=" ", strip=True), prefer_last=False),
                interpret_integral_as_cents=False,
            ),
            "image_url": absolute_url(page_url, _srcset_first(image)) if image else None,
            "product_id": _attr(node, "data-cnstrc-item-id") or _attr(node, "data-tile-pid"),
            "url": url,
        }
    )

def _finalize_adapter_record(record: dict[str, Any], *, surface: str) -> dict[str, Any]:
    shaped = dict(record)
    shaped["_source"] = "belk_adapter"
    return finalize_record(shaped, surface=surface)

def _unwrap_single_element(value: Any) -> Any:
    """Unwrap single-element-list values used by Belk's `utag_data` analytics payload.

    Belk PDPs expose product fields (including the UPC under `sku_upc`) inside a
    Tealium `utag_data` object where every scalar is wrapped in a one-item list,
    e.g. ``"sku_upc": ["0655772019097"]``. Coercion does not unwrap these, so the
    UPC was dropped and titles leaked as ``"['...']"``. Unwrap only the exact
    single-scalar-list shape; leave dicts and multi-element lists untouched.
    """
    if isinstance(value, list) and len(value) == 1 and not isinstance(value[0], (dict, list)):
        return value[0]
    return value

def _first_payload_field(
    payload: dict[str, Any],
    *,
    field_name: str,
    page_url: str,
    keys: tuple[str, ...],
) -> str | None:
    for key in keys:
        value = coerce_field_value(field_name, _unwrap_single_element(payload.get(key)), page_url)
        if value:
            return str(value)
    return None
_BARCODE_SEARCH_MAX_DEPTH = 5

def _looks_like_barcode(value: str) -> bool:
    """Validate a coerced value looks like a barcode (8-14 digits)."""
    normalized = str(value or "").strip()
    return normalized.isdigit() and 8 <= len(normalized) <= 14

def _first_nested_payload_field(
    payload: dict[str, Any],
    *,
    field_name: str,
    page_url: str,
    keys: tuple[str, ...],
) -> str | None:
    direct = _first_payload_field(payload, field_name=field_name, page_url=page_url, keys=keys)
    if direct:
        return direct
    normalized_keys = {str(key).casefold() for key in keys}
    stack: list[tuple[object, int]] = [(payload, 0)]
    while stack:
        node, depth = stack.pop()
        if depth > _BARCODE_SEARCH_MAX_DEPTH:
            continue
        if isinstance(node, dict):
            for key, value in node.items():
                if str(key).casefold() in normalized_keys:
                    coerced = coerce_field_value(field_name, _unwrap_single_element(value), page_url)
                    if coerced and _looks_like_barcode(str(coerced)):
                        return str(coerced)
                if isinstance(value, (dict, list)):
                    stack.append((value, depth + 1))
            continue
        if isinstance(node, list):
            for item in node:
                if isinstance(item, (dict, list)):
                    stack.append((item, depth + 1))
    return None
def _infer_belk_brand_from_url(*, url: str, title: object) -> str | None:
    return infer_brand_from_product_url(url=url, title=title) or _infer_belk_brand_from_slug_prefix(
        url=url,
        title=title,
    )

def _infer_belk_brand_from_slug_prefix(*, url: str, title: object) -> str | None:
    title_tokens = _belk_slug_tokens(title)
    if len(title_tokens) < 2:
        return None
    path_parts = [part.split(".", 1)[0] for part in (urlparse(str(url or "")).path or "").split("/") if part]
    slug = _belk_product_slug(path_parts)
    path_tokens = _belk_slug_tokens(slug)
    if len(path_tokens) < 2:
        return None
    min_match = min(3, len(title_tokens))
    for start in range(1, len(path_tokens)):
        if path_tokens[start] != title_tokens[0]:
            continue
        matched = _matching_token_count(path_tokens[start:], title_tokens)
        if matched < min_match:
            continue
        brand_tokens = path_tokens[:start]
        if not brand_tokens or len(brand_tokens) > LISTING_BRAND_MAX_WORDS:
            continue
        return " ".join(token.capitalize() for token in brand_tokens)
    return None

def _belk_product_slug(path_parts: list[str]) -> str:
    for index, part in enumerate(path_parts[:-1]):
        if part.lower() == "p":
            return path_parts[index + 1]
    return path_parts[-1] if path_parts else ""

def _matching_token_count(left: list[str], right: list[str]) -> int:
    return next((index for index, pair in enumerate(zip(left, right)) if pair[0] != pair[1]), min(len(left), len(right)))

def _belk_slug_tokens(value: object) -> list[str]:
    return [token for token in re.split(r"[^a-z0-9]+", str(value or "").casefold()) if token]

def _belk_record_identity(record: dict[str, Any]) -> str:
    product_id = clean_text(record.get("product_id") or record.get("productId") or record.get("sku"))
    if product_id:
        return product_id.lower()
    return _belk_identity_from_url(str(record.get("url") or ""))

def _belk_identity_from_url(url: str) -> str:
    path = urlparse(str(url or "")).path
    match = re.search(r"/([^/?#]+)/?$", path)
    segment = str(match.group(1) if match is not None else "").strip().lower()
    if not segment:
        return ""
    return re.sub(r"\.(?:html?|php|aspx?)$", "", segment)

def _first_node_attr(node: Any, attrs: tuple[str, ...]) -> str | None:
    for attr in attrs:
        value = clean_text(_attr(node, str(attr)))
        if _valid_belk_title(value):
            return value
    return None

def _first_selector_text(node: Any, selectors: tuple[str, ...]) -> str | None:
    for selector in selectors:
        try:
            match = node.css_first(str(selector))
        except Exception:
            match = None
        if match is None:
            continue
        value = clean_text(match.text(strip=True)) or _attr(match, "title") or _attr(match, "aria-label")
        if value:
            return value
    return None

def _first_belk_title(node: Any) -> str | None:
    for selector in BELK_TITLE_SELECTORS:
        try:
            match = node.css_first(str(selector))
        except Exception:
            match = None
        if match is None:
            continue
        value = clean_text(match.text(strip=True)) or _attr(match, "title") or _attr(match, "aria-label")
        if _valid_belk_title(value):
            return value
    return None

def _valid_belk_title(value: object) -> bool:
    text = clean_text(str(value or ""))
    if len(text) < BELK_TITLE_MIN_CHARS or len(text) > BELK_TITLE_MAX_CHARS:
        return False
    return not looks_like_utility_title(text)

def _first_selector_attr(node: Any, selectors: tuple[str, ...], attrs: tuple[str, ...]) -> str | None:
    for selector in selectors:
        try:
            matches = node.css(str(selector))
        except Exception:
            matches = []
        for match in matches:
            for attr in attrs:
                value = _attr(match, attr)
                if value:
                    return value
    return None

def _attr(node: Any, name: str) -> str:
    attrs = getattr(node, "attributes", {}) or {}
    return str(attrs.get(name) or "").strip()

def _srcset_first(value: object) -> str:
    return str(value or "").split(",", 1)[0].strip().split(" ", 1)[0].strip()

def _sku_array(product: dict[str, Any], key: str) -> list[Any]:
    value = product.get(key)
    return value if isinstance(value, list) else []

def _variant_objects_by_id(
    variant_objects: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for obj in variant_objects:
        if not isinstance(obj, dict):
            continue
        for key in BELK_VARIANT_ID_KEYS:
            vid = clean_text(obj.get(key))
            if vid:
                index.setdefault(vid, obj)
                break
    return index

def _variant_size_label(obj: dict[str, Any]) -> str | None:
    size = obj.get("size")
    if isinstance(size, dict):
        label = clean_text(size.get("sizeName") or size.get("label") or size.get("name"))
        if label:
            return label
    return clean_text(obj.get("size")) if not isinstance(obj.get("size"), dict) else None

def _variant_color_label(
    obj: dict[str, Any],
    color_name_by_code: dict[str, str],
) -> str | None:
    """Resolve a variant object's color to its display name.

    The variant object's ``color`` is Belk's numeric color code; the human name
    lives in the RSC ``colors`` map. Fall back to a non-numeric ``color`` value
    if one is already a label, but never leak a raw numeric code.
    """
    raw_color = obj.get("color")
    if isinstance(raw_color, dict):
        label = clean_text(raw_color.get("name") or raw_color.get("label") or raw_color.get("colorName"))
        return label or None
    code = clean_text(raw_color)
    if not code:
        return None
    mapped = clean_text(color_name_by_code.get(code))
    if mapped:
        return mapped
    # A bare numeric code with no map entry is not a usable colorway label.
    return None if code.isdigit() else code

def _variants_from_sku_arrays(
    product: dict[str, Any],
    *,
    page_url: str,
    variant_objects: list[dict[str, Any]],
    variant_objects_by_id: dict[str, dict[str, Any]] | None = None,
    color_name_by_code: dict[str, str] | None = None,
) -> list[dict[str, object]] | None:
    """Build variant rows from Belk's per-SKU parallel `utag_data` arrays.

    Each array index is one sellable SKU; arrays are positionally aligned. Each
    variant row gets its own UPC (`barcode`), price, availability, and image. Size
    and color labels are joined from the variant objects via `variantId == sku_id`.
    Each variant object carries a numeric color code that resolves to a display
    name via `color_name_by_code` (the RSC `colors` map), so multi-colorway PDPs
    keep each variant's own colorway.
    """
    sku_ids = _sku_array(product, BELK_SKU_ARRAY_ID_KEY)
    sku_upcs = _sku_array(product, BELK_SKU_ARRAY_UPC_KEY)
    if not sku_ids or not sku_upcs:
        return None
    prices = _sku_array(product, BELK_SKU_ARRAY_PRICE_KEY)
    original_prices = _sku_array(product, BELK_SKU_ARRAY_ORIGINAL_PRICE_KEY)
    inventories = _sku_array(product, BELK_SKU_ARRAY_INVENTORY_KEY)
    out_of_stock = _sku_array(product, BELK_SKU_ARRAY_OUT_OF_STOCK_KEY)
    images = _sku_array(product, BELK_SKU_ARRAY_IMAGE_KEY)
    objects_by_id = variant_objects_by_id or _variant_objects_by_id(variant_objects)

    rows: list[dict[str, object]] = []
    for index, sku_id in enumerate(sku_ids):
        row = _sku_array_variant_row(
            index,
            sku_id,
            sku_upcs=sku_upcs,
            prices=prices,
            original_prices=original_prices,
            inventories=inventories,
            out_of_stock=out_of_stock,
            images=images,
            objects_by_id=objects_by_id,
            color_name_by_code=color_name_by_code or {},
            page_url=page_url,
        )
        if row:
            rows.append(row)
    if not rows:
        return None
    return flatten_variants_for_public_output(rows, page_url=page_url)

def _array_value(values: list[Any], index: int) -> Any:
    return values[index] if index < len(values) else None

def _sku_array_variant_row(
    index: int,
    sku_id: object,
    *,
    sku_upcs: list[Any],
    prices: list[Any],
    original_prices: list[Any],
    inventories: list[Any],
    out_of_stock: list[Any],
    images: list[Any],
    objects_by_id: dict[str, dict[str, Any]],
    color_name_by_code: dict[str, str],
    page_url: str,
) -> dict[str, object] | None:
    sku = clean_text(sku_id)
    upc = clean_text(_array_value(sku_upcs, index))
    if not upc or not _looks_like_barcode(upc):
        return None
    row: dict[str, object] = {"barcode": upc}
    if sku:
        row["sku"] = sku
    for field, values in (("price", prices), ("original_price", original_prices)):
        value = normalize_price(_array_value(values, index), interpret_integral_as_cents=False)
        if value is not None:
            row[field] = value
    _apply_sku_inventory(row, _array_value(out_of_stock, index), _array_value(inventories, index))
    if image := clean_text(_array_value(images, index)):
        row["image_url"] = absolute_url(page_url, image)
    if variant := objects_by_id.get(sku):
        if size := _variant_size_label(variant):
            row["size"] = size
        if color := _variant_color_label(variant, color_name_by_code):
            row["color"] = color
    return row

def _apply_sku_inventory(row: dict[str, object], out_of_stock: object, inventory: object) -> None:
    if isinstance(out_of_stock, bool):
        row["availability"] = "out_of_stock" if out_of_stock else "in_stock"
    try:
        quantity = int(str(inventory).strip())
    except (TypeError, ValueError):
        return
    row["stock_quantity"] = quantity
    row.setdefault("availability", "in_stock" if quantity > 0 else "out_of_stock")

def _primary_variant_barcode(variants: list[dict[str, object]]) -> str | None:
    """Pick the product-level UPC: first in-stock variant, else first variant."""
    for variant in variants:
        if str(variant.get("availability") or "").strip() == "in_stock":
            barcode = clean_text(variant.get("barcode"))
            if barcode:
                return barcode
    for variant in variants:
        barcode = clean_text(variant.get("barcode"))
        if barcode:
            return barcode
    return None

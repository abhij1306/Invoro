from __future__ import annotations
# ruff: noqa: F401,F403,F405

import logging
from decimal import Decimal, InvalidOperation
from typing import Any

import jmespath
from app.services.dom.html_parser import BeautifulSoup
from glom import GlomError, glom  # type: ignore[import-untyped]

from ._common import *
from ._variant_rows import _product_variant_rows
from ._variant_mapping import (
    _connection_nodes,
    _name_or_value,
    _normalize_variant,
    _option_names,
)
from app.services.config.variant_policy import (
    GEOGRAPHIC_STATE_VARIANT_VALUE_SET,
    variant_state_values_are_geographic,
)

logger = logging.getLogger(__name__)


def _map_product_payload(
    product: dict[str, Any],
    *,
    page_url: str,
    category_fallback_from_type: bool,
    field_jmespaths: dict[str, str | list[str]] | None = None,
) -> dict[str, Any]:
    base = _product_base_fields(product, field_jmespaths=field_jmespaths)
    images = _extract_product_images(product, page_url=page_url)
    description_fields = _extract_ecommerce_description_fields(base.get("description"))
    shopify_like = _looks_like_shopify_product(product)
    option_names = _option_names(product.get("options"))
    normalized_variants = _normalized_product_variants(
        product, option_names, page_url, shopify_like
    )
    axes = variant_axes(normalized_variants)
    variants = (
        resolve_variants(axes, normalized_variants) if axes else normalized_variants
    )
    active_variant = select_variant(variants, page_url=page_url)
    price = _product_price(product, base, active_variant, shopify_like)
    original_price = _product_original_price(
        product, base, active_variant, shopify_like
    )
    currency = variant_attribute(active_variant, "currency") or text_or_none(
        base.get("currency")
    )
    availability = availability_value(active_variant) or availability_value(product)
    product_stock = _product_stock_quantity(active_variant, product)
    color, size = _product_variant_axes(
        product, active_variant, option_names, normalized_variants, page_url
    )
    brand = _product_party_value(base.get("brand"))
    vendor = _product_party_value(base.get("vendor"))
    category = base.get("category") or (
        base.get("product_type") if category_fallback_from_type else None
    )
    primary_image = variant_attribute(active_variant, "image_url")
    if not primary_image and images:
        primary_image = images[0]
    record = compact_dict(
        {
            "title": base.get("title"),
            "brand": brand,
            "vendor": vendor,
            "url": base.get("url"),
            "handle": base.get("handle"),
            "description": description_fields.get("description"),
            "product_id": base.get("product_id"),
            "category": category,
            "product_type": base.get("product_type"),
            "price": price,
            "original_price": original_price,
            "currency": currency,
            "availability": availability,
            "stock_quantity": product_stock,
            "sku": variant_attribute(active_variant, "sku") or base.get("sku"),
            "barcode": variant_attribute(active_variant, "barcode")
            or base.get("barcode"),
            "color": color,
            "size": size,
            "image_url": primary_image,
            "additional_images": images[1:] if len(images) > 1 else None,
            "image_count": len(images) or None,
            "features": description_fields.get("features"),
            "variants": variants or None,
            "variant_count": len(variants) if variants else None,
            "tags": base.get("tags") if isinstance(base.get("tags"), list) else None,
            "created_at": base.get("created_at"),
            "updated_at": base.get("updated_at"),
            "published_at": base.get("published_at"),
        }
    )
    return record


def _normalized_product_variants(
    product: dict[str, Any],
    option_names: list[str],
    page_url: str,
    shopify_like: bool,
) -> list[dict[str, Any]]:
    labels = option_value_labels(product)
    variants = [
        normalized
        for variant in _product_variant_rows(product)
        if isinstance(variant, dict)
        if (
            normalized := _normalize_variant(
                variant,
                option_names=option_names,
                option_value_labels=labels,
                page_url=page_url,
                interpret_integral_as_cents=shopify_like,
            )
        )
    ]
    return _drop_geographic_state_variant_rows(variants)


def _product_stock_quantity(
    active_variant: dict[str, Any] | None, product: dict[str, Any]
) -> int | None:
    quantity = stock_quantity(active_variant)
    return quantity if quantity is not None else stock_quantity(product)


def _product_price(
    product: dict[str, Any],
    base: dict[str, Any],
    active_variant: dict[str, Any] | None,
    shopify_like: bool,
) -> object:
    price = variant_attribute(active_variant, "price")
    if price not in (None, "", [], {}):
        return price
    price = _raw_current_price_value(product, interpret_integral_as_cents=shopify_like)
    if price is None:
        price = normalize_price(
            base.get("price"), interpret_integral_as_cents=shopify_like
        )
    return (
        price
        if price not in (None, "", [], {})
        else _discounted_percentage_price(product)
    )


def _product_original_price(
    product: dict[str, Any],
    base: dict[str, Any],
    active_variant: dict[str, Any] | None,
    shopify_like: bool,
) -> object:
    price = variant_attribute(active_variant, "original_price")
    if price not in (None, "", [], {}):
        return price
    price = _raw_original_price_value(product, interpret_integral_as_cents=shopify_like)
    if price is not None:
        return price
    return normalize_price(
        base.get("original_price"), interpret_integral_as_cents=shopify_like
    )


def _product_variant_axes(
    product: dict[str, Any],
    active_variant: dict[str, Any] | None,
    option_names: list[str],
    normalized_variants: list[dict[str, Any]],
    page_url: str,
) -> tuple[object, object]:
    color = variant_attribute(active_variant, "color")
    if color in (None, "", [], {}):
        color = variant_axis_value(
            "color", product.get("color") or product.get("colour"), page_url=page_url
        )
    size = variant_attribute(active_variant, "size")
    raw_size = product.get("size") or product.get("sz")
    if size in (None, "", [], {}) and _product_scalar_size_is_public(
        raw_size,
        option_names=option_names,
        normalized_variants=normalized_variants,
    ):
        size = variant_axis_value("size", raw_size, page_url=page_url)
    return color, size


def _product_party_value(value: object) -> object:
    return _name_or_value(value) if isinstance(value, dict) else value


def _drop_geographic_state_variant_rows(
    variants: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    state_values = [
        state_value
        for variant in variants
        if (state_value := _variant_state_axis_value(variant))
    ]
    if variant_state_values_are_geographic(state_values):
        return [
            variant
            for variant in variants
            if (_variant_state_axis_value(variant) or "").strip().casefold()
            not in GEOGRAPHIC_STATE_VARIANT_VALUE_SET
        ]
    return variants


def _variant_state_axis_value(variant: dict[str, Any]) -> str | None:
    option_values = variant.get("option_values")
    value = (
        option_values.get("state")
        if isinstance(option_values, dict)
        else variant.get("state")
    )
    return text_or_none(value)


def _product_scalar_size_is_public(
    raw_value: object,
    *,
    option_names: list[str],
    normalized_variants: list[dict[str, Any]],
) -> bool:
    value = clean_text(raw_value)
    if not value:
        return False
    if any(normalized_variant_axis_key(name) == "size" for name in option_names):
        return True
    return True


def _extract_ecommerce_description_fields(value: object) -> dict[str, object]:
    description_html = str(value or "").strip()
    if not description_html:
        return {}
    if "<" not in description_html and "&" not in description_html:
        text = text_or_none(description_html)
        return {"description": text} if text else {}

    return _description_fields_from_html(description_html)


def _description_fields_from_html(description_html: str) -> dict[str, object]:
    soup = BeautifulSoup(description_html, "html.parser")
    for node in soup.select("script, style, iframe, svg, img, picture, source, video"):
        node.decompose()

    features = extract_feature_rows(soup)
    blocks: list[tuple[str, str]] = []
    alias_lookup = surface_alias_lookup("ecommerce_detail", None)
    for node in soup.find_all(
        ["h1", "h2", "h3", "h4", "h5", "h6", "p"],
        limit=ECOMMERCE_DESCRIPTION_BLOCK_LIMIT,
    ):
        text = text_or_none(node.get_text(" ", strip=True))
        if text:
            blocks.append((str(node.name).lower(), text))

    lead_parts = _lead_description_parts(blocks, alias_lookup)
    lead_description = clean_text(" ".join(lead_parts))
    description = text_or_none(lead_description) or text_or_none(
        html_to_text(description_html)
    )
    return compact_dict({"description": description, "features": features})


def _lead_description_parts(
    blocks: list[tuple[str, str]], alias_lookup: dict[str, str]
) -> list[str]:
    lead_parts: list[str] = []
    seen: set[str] = set()
    for _tag_name, text in blocks:
        normalized_text = normalize_field_key(text)
        canonical = alias_lookup.get(normalized_text)
        if lead_parts and canonical and canonical != "description":
            break
        lowered = text.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        lead_parts.append(text)
    return lead_parts


def _raw_current_price_value(
    product: dict[str, Any],
    *,
    interpret_integral_as_cents: bool,
) -> str | None:
    return _contextual_numeric_value(
        product,
        (
            ("prices", "currentPrice"),
            ("currentPrice",),
            ("pricing_information", "currentPrice"),
            ("pricing_information", "standard_price"),
        ),
        interpret_integral_as_cents=interpret_integral_as_cents,
    )


def _raw_original_price_value(
    product: dict[str, Any],
    *,
    interpret_integral_as_cents: bool,
) -> str | None:
    return _contextual_numeric_value(
        product,
        (
            ("prices", "initialPrice"),
            ("fullPrice",),
            ("pricing_information", "listPrice"),
            ("mrp",),
        ),
        interpret_integral_as_cents=interpret_integral_as_cents,
    )


def _discounted_percentage_price(product: dict[str, Any]) -> str | None:
    list_price = _raw_numeric_value(product, (("mrp",),))
    discount_percent = _raw_numeric_value(product, (("Dis",),))
    if list_price is None or discount_percent is None:
        return None
    try:
        discounted = float(list_price) * (100.0 - float(discount_percent)) / 100.0
    except (TypeError, ValueError):
        return None
    if discounted <= 0:
        return None
    return f"{discounted:.2f}".rstrip("0").rstrip(".") or None


def _contextual_numeric_value(
    product: dict[str, Any],
    paths: tuple[tuple[str, ...], ...],
    *,
    interpret_integral_as_cents: bool,
) -> str | None:
    currency = _raw_currency_value(product)
    if not currency:
        return None
    value = _raw_numeric_value(product, paths)
    if value is None:
        return None
    normalized = normalize_price(
        value,
        interpret_integral_as_cents=interpret_integral_as_cents,
    )
    if normalized is None:
        return None
    if interpret_integral_as_cents:
        try:
            normalized = format(Decimal(normalized).quantize(Decimal("0.01")), "f")
        except (InvalidOperation, ValueError):
            return None
    if normalized.startswith(f"{currency} "):
        return normalized
    return f"{currency} {normalized}"


def _raw_numeric_value(
    product: dict[str, Any],
    paths: tuple[tuple[str, ...], ...],
) -> int | float | None:
    for path in paths:
        current: Any = product
        for key in path:
            if not isinstance(current, dict):
                current = None
                break
            current = current.get(key)
        if isinstance(current, (int, float)) and not isinstance(current, bool):
            return current
    return None


def _raw_currency_value(product: dict[str, Any]) -> str | None:
    for path in (
        ("prices", "currency"),
        ("pricing_information", "currency"),
        ("currency",),
        ("currencyCode",),
        ("priceCurrency",),
    ):
        current: Any = product
        for key in path:
            if not isinstance(current, dict):
                current = None
                break
            current = current.get(key)
        if isinstance(current, str) and current.strip():
            return current.strip()
    return None


def _product_base_fields(
    product: dict[str, Any],
    *,
    field_jmespaths: dict[str, str | list[str]] | None,
) -> dict[str, Any]:
    base = _glom_product_base_fields(product)
    mapped = _map_jmespath_fields(product, field_jmespaths=field_jmespaths)
    if not mapped:
        return base
    merged = dict(mapped)
    for field_name, value in base.items():
        if field_name not in merged or merged[field_name] in (None, "", [], {}):
            merged[field_name] = value
    return compact_dict(merged)


def _glom_product_base_fields(product: dict[str, Any]) -> dict[str, Any]:
    try:
        base = glom(product, JS_STATE_PRODUCT_FIELD_SPEC, default=None)
    except (GlomError, RuntimeError, TypeError):
        logger.debug("Failed to glom JS-state product payload", exc_info=True)
        base = {}
    if not isinstance(base, dict):
        return {}
    return compact_dict(base)


def _map_jmespath_fields(
    product: dict[str, Any],
    *,
    field_jmespaths: dict[str, str | list[str]] | None,
) -> dict[str, Any]:
    if not isinstance(field_jmespaths, dict) or not field_jmespaths:
        return {}
    mapped: dict[str, Any] = {}
    for field_name, expressions in field_jmespaths.items():
        if not isinstance(field_name, str) or not field_name.strip():
            continue
        value = _first_non_empty_jmespath(product, expressions)
        if value not in (None, "", [], {}):
            mapped[field_name] = value
    return compact_dict(mapped)


def _first_non_empty_jmespath(
    payload: dict[str, Any],
    expressions: str | list[str],
) -> Any:
    candidates = [expressions] if isinstance(expressions, str) else expressions
    if not isinstance(candidates, list):
        return None
    for expression in candidates:
        if not isinstance(expression, str) or not expression.strip():
            continue
        value = jmespath.search(expression, payload)
        if value not in (None, "", [], {}):
            return value
    return None


def _extract_product_images(product: dict[str, Any], *, page_url: str) -> list[str]:
    values = extract_urls(product.get("images"), page_url)
    values.extend(extract_urls(_connection_nodes(product.get("images")), page_url))
    values.extend(_extract_nested_image_urls(product.get("images"), page_url=page_url))
    values.extend(extract_urls(product.get("image"), page_url))
    values.extend(extract_urls(product.get("featuredImage"), page_url))
    values.extend(extract_urls(product.get("featured_image"), page_url))
    values.extend(extract_urls(_connection_nodes(product.get("media")), page_url))
    return dedupe_image_urls(values)


def _extract_nested_image_urls(
    value: Any, *, page_url: str, depth: int = 0
) -> list[str]:
    if depth > 6:
        return []
    urls = extract_urls(value, page_url)
    if urls:
        return urls
    nested: list[str] = []
    if isinstance(value, dict):
        for item in value.values():
            nested.extend(
                _extract_nested_image_urls(item, page_url=page_url, depth=depth + 1)
            )
    elif isinstance(value, list):
        for item in value[: int(JS_STATE_LIST_ITERATION_LIMIT)]:
            nested.extend(
                _extract_nested_image_urls(item, page_url=page_url, depth=depth + 1)
            )
    return dedupe_image_urls(nested)


def _looks_like_shopify_product(product: dict[str, Any]) -> bool:
    raw_variants = _product_variant_rows(product)
    return any(
        key in product
        for key in (
            "handle",
            "compare_at_price",
            "product_type",
            "body_html",
        )
    ) or any(
        isinstance(variant, dict)
        and any(
            field in variant
            for field in ("option1", "compare_at_price", "inventory_quantity")
        )
        for variant in raw_variants
    )


__all__: list[str] = []

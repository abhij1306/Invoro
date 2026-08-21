from __future__ import annotations
# ruff: noqa: F401,F403,F405

import logging
from typing import Any

from glom import GlomError, glom  # type: ignore[import-untyped]
from app.services.shared.url_utils import variant_url_with_param

from ._common import *

logger = logging.getLogger(__name__)


def _option_names(raw_options: object) -> list[str]:
    names: list[str] = []
    if isinstance(raw_options, list):
        for option in raw_options:
            if isinstance(option, str):
                names.append(option)
            elif isinstance(option, dict):
                label = option.get("name") or option.get("title") or option.get("label")
                if label:
                    names.append(str(label))
    return names


def _normalize_variant(
    variant: dict[str, Any],
    *,
    option_names: list[str],
    option_value_labels: dict[str, dict[str, str]] | None = None,
    page_url: str,
    interpret_integral_as_cents: bool,
) -> dict[str, Any] | None:
    row: dict[str, Any] = {}
    variant_id = _variant_id(variant)
    if variant_id:
        row["variant_id"] = variant_id
    base = _variant_base_fields(variant)
    explicit_url = text_or_none(base.get("url"))
    if explicit_url:
        row["url"] = explicit_url
    elif variant_id:
        row["url"] = _variant_url(page_url, variant_id)
    _add_variant_scalar_fields(row, variant, base, interpret_integral_as_cents)
    _add_variant_image(row, variant, page_url)
    selection_values = variant_selection_values(
        variant,
        option_names=option_names,
    )
    if selection_values:
        row["_selection_values"] = selection_values
    option_values = variant_option_values(
        variant,
        option_names=option_names,
        option_value_labels=option_value_labels,
    )
    if option_values:
        row["option_values"] = option_values
        if option_values.get("color"):
            row["color"] = option_values["color"]
        if option_values.get("size"):
            row["size"] = option_values["size"]
    for field_name in ("title", "name", "color", "size"):
        raw_value = _variant_axis_raw_value(variant, field_name)
        value = (
            variant_axis_value(field_name, raw_value, page_url=page_url)
            if field_name in {"color", "size"}
            else text_or_none(raw_value)
        )
        if value and field_name not in row:
            row["title" if field_name == "name" else field_name] = value
    return row or None


def _variant_id(variant: dict[str, Any]) -> str | None:
    return text_or_none(
        variant.get("id")
        or variant.get("variantId")
        or variant.get("variant_id")
        or variant.get("simple_id")
        or variant.get("simpleId")
        or variant.get("npin")
    )


def _variant_base_fields(variant: dict[str, Any]) -> dict[str, Any]:
    try:
        base = glom(variant, JS_STATE_VARIANT_FIELD_SPEC, default=None)
    except (GlomError, RuntimeError, TypeError):
        logger.debug("Failed to glom JS-state variant payload", exc_info=True)
        return {}
    return base if isinstance(base, dict) else {}


def _add_variant_scalar_fields(
    row: dict[str, Any],
    variant: dict[str, Any],
    base: dict[str, Any],
    interpret_integral_as_cents: bool,
) -> None:
    for field_name in ("sku", "barcode", "currency"):
        if value := text_or_none(base.get(field_name)):
            row[field_name] = value
    for field_name, nested_key in (
        ("price", "sellingRetail"),
        ("original_price", "baseRetail"),
    ):
        raw_value = _nested_variant_price(variant, nested_key)
        if raw_value in (None, "", [], {}):
            raw_value = base.get(field_name)
        value = normalize_price(
            raw_value, interpret_integral_as_cents=interpret_integral_as_cents
        )
        if value is not None:
            row[field_name] = value
    if availability := _nested_variant_availability(variant) or availability_value(
        variant
    ):
        row["availability"] = availability
    variant_stock = stock_quantity(variant)
    if variant_stock is None:
        variant_stock = _nested_variant_stock_quantity(variant)
    if variant_stock is not None:
        row["stock_quantity"] = variant_stock


def _add_variant_image(
    row: dict[str, Any], variant: dict[str, Any], page_url: str
) -> None:
    raw_image = (
        variant.get("featured_image")
        or variant.get("featuredImage")
        or variant.get("image")
    )
    image_url = next(iter(extract_urls(raw_image, page_url)), None)
    if image_url:
        row["image_url"] = image_url


def _variant_axis_raw_value(variant: dict[str, Any], field_name: str) -> Any:
    if field_name != "size":
        return variant.get(field_name)
    return (
        _dict_label(variant.get("size"))
        or variant.get("size")
        or variant.get("concatenatedDisplaySize")
        or _dict_label(variant.get("sizeDimension1"))
    )


def _nested_variant_availability(variant: dict[str, Any]) -> str | None:
    for proposition in _nested_variant_propositions(variant):
        nested_availability = proposition.get("availability")
        if isinstance(nested_availability, dict):
            availability = availability_value(nested_availability)
            if availability:
                return availability
        else:
            availability = availability_value(proposition)
            if availability:
                return availability
        salability = proposition.get("salability")
        if isinstance(salability, dict):
            status = text_or_none(salability.get("status"))
            if status and status.strip().upper() in {"SELLABLE", "PREVIEWABLE"}:
                return "in_stock"
            if status and status.strip().upper() in {"SOLD_OUT", "UNSELLABLE"}:
                return "out_of_stock"
    return None


def _nested_variant_stock_quantity(variant: dict[str, Any]) -> int | None:
    for proposition in _nested_variant_propositions(variant):
        availability = proposition.get("availability")
        if not isinstance(availability, dict):
            continue
        quantities = [
            availability.get("shipQuantity"),
            availability.get("marketPickQuantity"),
            availability.get("pickQuantity"),
        ]
        numeric_quantities: list[int] = []
        for raw_quantity in quantities:
            try:
                numeric_quantities.append(int(str(raw_quantity).strip()))
            except (TypeError, ValueError):
                continue
        if numeric_quantities:
            return max(numeric_quantities)
    return None


def _nested_variant_price(variant: dict[str, Any], price_key: str) -> Any:
    for proposition in _nested_variant_propositions(variant):
        for pricing in as_list(proposition.get("pricings")):
            if not isinstance(pricing, dict):
                continue
            price = pricing.get(price_key)
            if isinstance(price, dict) and price.get("price") not in (None, "", [], {}):
                return price.get("price")
    return None


def _nested_variant_propositions(variant: dict[str, Any]) -> list[dict[str, Any]]:
    sku = variant.get("sku")
    if not isinstance(sku, dict):
        return []
    return [
        proposition
        for proposition in as_list(sku.get("propositions"))
        if isinstance(proposition, dict)
    ]


def _dict_label(value: Any) -> str | None:
    if not isinstance(value, dict):
        return None
    return text_or_none(value.get("label")) or text_or_none(value.get("name"))


def _variant_url(page_url: str, variant_id: str) -> str:
    return variant_url_with_param(page_url, variant_id)


def _connection_nodes(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        nodes = value.get("nodes")
        if isinstance(nodes, list):
            return [node for node in nodes if isinstance(node, dict)]
        edges = value.get("edges")
        if isinstance(edges, list):
            return [
                node
                for edge in edges
                if isinstance(edge, dict)
                for node in [edge.get("node")]
                if isinstance(node, dict)
            ]
    return []


def _name_or_value(value: Any) -> Any:
    if isinstance(value, dict):
        return value.get("name") or value.get("title") or value.get("value")
    return value


__all__: list[str] = []

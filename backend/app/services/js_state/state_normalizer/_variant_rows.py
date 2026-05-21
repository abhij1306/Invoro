from __future__ import annotations
# ruff: noqa: F401,F403,F405

from typing import Any

from ._common import *
from ._variant_mapping import _option_names, _variant_axis_raw_value

def _product_variant_rows(product: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for key in JS_STATE_PRODUCT_VARIANT_LIST_KEYS:
        raw_rows = as_list(product.get(key))
        if not raw_rows:
            continue
        for item in raw_rows:
            if not isinstance(item, dict):
                continue
            row = dict(item)
            # `variants` rows are authoritative single-axis data, so use
            # _backfill_single_axis_variant_context to avoid inflating transport
            # fields. Richer sources use _backfill_nested_variant_context.
            if key != "variants":
                _backfill_nested_variant_context(row, product)
            else:
                _backfill_single_axis_variant_context(
                    row,
                    product,
                    variant_count=len(raw_rows),
                )
            rows.append(row)
    rows.extend(_nested_choice_item_variant_rows(product))
    if not rows:
        rows.extend(_mapped_size_variant_rows(product))
    if not rows:
        rows.extend(_option_group_variant_rows(product))
    return rows

def _mapped_size_variant_rows(product: dict[str, Any]) -> list[dict[str, Any]]:
    raw_sizes = product.get("sizes")
    if not isinstance(raw_sizes, dict):
        return []
    rows: list[dict[str, Any]] = []
    for size_key, item in raw_sizes.items():
        if not isinstance(item, dict):
            continue
        row = dict(item)
        if row.get("size") in (None, "", [], {}):
            row["size"] = (
                text_or_none(item.get("title"))
                or text_or_none(item.get("displayName"))
                or text_or_none(item.get("name"))
                or text_or_none(size_key)
            )
        _backfill_single_axis_variant_context(row, product)
        rows.append(row)
    return rows

def _option_group_variant_rows(product: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for group_key in JS_STATE_PRODUCT_OPTION_GROUP_KEYS:
        for group in as_list(product.get(group_key)):
            if not isinstance(group, dict):
                continue
            axis_name = text_or_none(
                group.get("name")
                or group.get("title")
                or group.get("label")
                or group.get("attribute_code")
                or group.get("id")
            )
            if not axis_name:
                continue
            for value_key in JS_STATE_OPTION_GROUP_VALUE_KEYS:
                values = as_list(group.get(value_key))
                if values:
                    break
            else:
                values = []
            for item in values:
                if not isinstance(item, dict):
                    continue
                axis_value = (
                    text_or_none(item.get("label"))
                    or text_or_none(item.get("name"))
                    or text_or_none(item.get("displayValue"))
                    or text_or_none(item.get("value"))
                    or text_or_none(item.get("index"))
                )
                if not axis_value:
                    continue
                row = dict(item)
                row["name"] = axis_name
                row["value"] = axis_value
                simple_id = text_or_none(
                    item.get("simple_id") or item.get("simpleId") or item.get("variantId")
                )
                if simple_id and row.get("id") in (None, "", [], {}):
                    row["id"] = simple_id
                rows.append(row)
    return rows

def _nested_choice_item_variant_rows(product: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for core_product in as_list(product.get("coreProducts")):
        if not isinstance(core_product, dict):
            continue
        for choice in as_list(core_product.get("coreChoices")):
            if not isinstance(choice, dict):
                continue
            color_family = choice.get("colorFamily")
            color = (
                text_or_none(choice.get("displayColorDescription"))
                or (
                    text_or_none(color_family.get("label"))
                    if isinstance(color_family, dict)
                    else None
                )
            )
            image_url = _choice_primary_image(choice)
            for item in as_list(choice.get("items")):
                if not isinstance(item, dict):
                    continue
                row = dict(item)
                if color and row.get("color") in (None, "", [], {}):
                    row["color"] = color
                size = _variant_axis_raw_value(row, "size")
                if size and row.get("size") in (None, "", [], {}):
                    row["size"] = size
                if image_url and row.get("image") in (None, "", [], {}):
                    row["image"] = image_url
                rows.append(row)
    return rows

def _choice_primary_image(choice: dict[str, Any]) -> str | None:
    for shot in as_list(choice.get("orderedShots")):
        if not isinstance(shot, dict):
            continue
        image_url = text_or_none(shot.get("imageUrl"))
        if image_url:
            return image_url
    return None

def _backfill_nested_variant_context(
    variant: dict[str, Any],
    product: dict[str, Any],
) -> None:
    for target_key, product_keys in {
        "color": ("color", "colour"),
        "currencyCode": ("currencyCode", "currency", "priceCurrency"),
        "compareAtPrice": ("compareAtPrice", "compare_at_price"),
        "featuredImage": ("featuredMedia", "featured_image", "image"),
        "url": (
            "url",
            "href",
            "onlineStoreUrl",
            "online_store_url",
            "productUrl",
            "product_url",
            "canonicalUrl",
            "canonical_url",
        ),
    }.items():
        if variant.get(target_key) not in (None, "", [], {}):
            continue
        for product_key in product_keys:
            value = product.get(product_key)
            if value not in (None, "", [], {}):
                variant[target_key] = value
                break

def _backfill_single_axis_variant_context(
    variant: dict[str, Any],
    product: dict[str, Any],
    *,
    variant_count: int | None = None,
) -> None:
    if variant.get("color") not in (None, "", [], {}):
        return
    option_names = {
        normalized_variant_axis_key(name)
        for name in _option_names(product.get("options"))
    }
    if "color" in option_names:
        return
    if (
        "size" not in option_names
        and _variant_axis_raw_value(variant, "size") in (None, "", [], {})
        and (variant_count or 1) <= 1
    ):
        return
    color = text_or_none(product.get("color") or product.get("colour"))
    if color:
        variant["color"] = color

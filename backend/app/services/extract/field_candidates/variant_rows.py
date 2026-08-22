from __future__ import annotations

import re

from app.services.extract.variant_axis import (
    is_public_variant_axis,
    normalized_variant_axis_key,
)
from app.services.shared.field_coerce import (
    coerce_field_value,
    coerce_text,
    text_or_none,
)
from app.services.shared.url_utils import variant_url_with_param

from .structured_values import _coerce_structured_candidate_value

_OFFER_TITLE_SIZE_RE = re.compile(
    r"(?:^|[,\s])(\d+(?:\.\d+)?\s*-?\s*(?:lb|lbs|oz|kg|g|ml|l|ct|count|pack|pk|bag|bags))\b",
    re.I,
)


def _variant_url_from_id(page_url: str, variant_id: str) -> str:
    return variant_url_with_param(page_url, variant_id)


def _additional_property_options(item: dict[str, object]) -> dict[str, object]:
    values: dict[str, object] = {}
    properties = item.get("additionalProperty")
    for prop in properties if isinstance(properties, list) else []:
        if not isinstance(prop, dict) or not prop.get("name") or not prop.get("value"):
            continue
        if axis := normalized_variant_axis_key(prop["name"]):
            values[axis] = str(prop["value"]).strip()
    return values


def _structured_variant_row(
    item: dict[str, object], page_url: str
) -> dict[str, object]:
    offer = item.get("offers")
    offer = offer[0] if isinstance(offer, list) and offer else offer
    availability_source = offer if isinstance(offer, dict) else item.get("availability")
    row: dict[str, object] = {}
    values = {
        "sku": coerce_text(item.get("sku")),
        "barcode": coerce_text(
            item.get("gtin13") or item.get("gtin") or item.get("gtin14")
        ),
        "title": coerce_text(item.get("name")),
        "color": coerce_field_value("color", item.get("color"), page_url),
        "size": coerce_field_value("size", item.get("size"), page_url),
        "price": coerce_field_value("price", offer or item, page_url),
        "availability": coerce_field_value(
            "availability", availability_source, page_url
        ),
        "image_url": coerce_field_value("image_url", item.get("image"), page_url),
        "url": coerce_field_value("url", offer or item, page_url),
    }
    row.update(
        {key: value for key, value in values.items() if value not in (None, "", [], {})}
    )
    options = _additional_property_options(item)
    for axis in ("color", "size"):
        if row.get(axis):
            options[axis] = row[axis]
    if options:
        row["option_values"] = options
    return row


def _structured_variant_rows(
    variants: object, page_url: str
) -> list[dict[str, object]]:
    items = variants if isinstance(variants, list) else []
    return [
        row
        for item in items
        if isinstance(item, dict)
        if (row := _structured_variant_row(item, page_url))
    ]


def _structured_offer_variant_row(
    item: dict[str, object], page_url: str
) -> dict[str, object] | None:
    offered = item.get("itemOffered")
    offered = offered if isinstance(offered, dict) else {}
    title = coerce_text(item.get("name") or offered.get("name"))
    row: dict[str, object] = {}
    if title:
        row["title"] = title
        if size := _offer_title_size(title):
            row["size"] = size
        if scent := _offer_title_scent(title, item, page_url):
            row["scent"] = scent
    values = {
        "sku": coerce_text(item.get("sku") or offered.get("sku")),
        "price": coerce_field_value("price", item, page_url),
        "currency": coerce_field_value("currency", item, page_url),
        "availability": coerce_field_value("availability", item, page_url),
        "image_url": coerce_field_value(
            "image_url", item.get("image") or offered.get("image"), page_url
        ),
        "url": coerce_field_value("url", item, page_url),
    }
    row.update(
        {key: value for key, value in values.items() if value not in (None, "", [], {})}
    )
    options = {axis: row[axis] for axis in ("size", "scent") if row.get(axis)}
    if options:
        row["option_values"] = options
    return row if row.get("url") or row.get("price") else None


def _structured_offer_variant_rows(
    offers: object, page_url: str
) -> list[dict[str, object]]:
    items = offers if isinstance(offers, list) and len(offers) >= 2 else []
    return [
        row
        for item in items
        if isinstance(item, dict)
        if (row := _structured_offer_variant_row(item, page_url))
    ]


def _offer_title_size(title: str) -> str:
    match = _OFFER_TITLE_SIZE_RE.search(title)
    if not match:
        return ""
    return re.sub(r"\s+", "", match.group(1)).lower()


def _offer_title_scent(
    title: str,
    offer: dict[str, object],
    page_url: str,
) -> str:
    probe = " ".join(
        text
        for text in (
            title,
            text_or_none(offer.get("url")),
            page_url,
        )
        if text
    ).casefold()
    if not any(
        token in probe for token in ("scent", "fragrance", "body mist", "body-mist")
    ):
        return ""
    parts = re.split(r"\s[-–—]\s", title, maxsplit=1)
    if len(parts) != 2:
        return ""
    value = text_or_none(parts[1])
    return value or ""


def _variant_axes_from_rows(variants: list[dict[str, object]]) -> dict[str, list[str]]:
    axes: dict[str, list[str]] = {}
    for row in variants:
        if not isinstance(row, dict):
            continue
        option_values = row.get("option_values")
        if isinstance(option_values, dict):
            for axis_name, axis_value in option_values.items():
                cleaned = text_or_none(axis_value)
                if not cleaned:
                    continue
                axes.setdefault(str(axis_name), [])
                if cleaned not in axes[str(axis_name)]:
                    axes[str(axis_name)].append(cleaned)
        for axis_name in ("color", "size", "style", "material", "scent", "flavor"):
            cleaned = text_or_none(row.get(axis_name))
            if not cleaned:
                continue
            axes.setdefault(axis_name, [])
            if cleaned not in axes[axis_name]:
                axes[axis_name].append(cleaned)
    return axes


def _variation_attribute_labels(
    payload: dict[str, object],
) -> dict[str, dict[str, str]]:
    labels: dict[str, dict[str, str]] = {}
    raw_attributes = payload.get("variationAttributes")
    if not isinstance(raw_attributes, list):
        raw_attributes = payload.get("variation_attributes")
    for attribute in raw_attributes if isinstance(raw_attributes, list) else []:
        if isinstance(attribute, dict):
            _add_variation_attribute_labels(labels, attribute)
    return labels


def _add_variation_attribute_labels(
    labels: dict[str, dict[str, str]], attribute: dict[str, object]
) -> None:
    axis_source = _first_nonblank(attribute, ("id", "name", "label"))
    axis_key = normalized_variant_axis_key(axis_source)
    values = attribute.get("values")
    if not axis_key or not isinstance(values, list):
        return
    for item in values:
        if not isinstance(item, dict):
            continue
        raw_value = text_or_none(item.get("value") or item.get("id"))
        display_source = _first_nonblank(
            item, ("name", "displayValue", "display_value", "label")
        )
        display = text_or_none(display_source)
        if raw_value and display:
            labels.setdefault(axis_key, {})[raw_value] = display


def _public_variant_axis_key(value: object) -> str:
    axis_key = normalized_variant_axis_key(value)
    return axis_key if is_public_variant_axis(axis_key) else ""


def _structured_product_option_names(payload: dict[str, object]) -> list[str]:
    raw_options = payload.get("options")
    if not isinstance(raw_options, list):
        return []
    names: list[str] = []
    for item in raw_options:
        if isinstance(item, dict):
            name = text_or_none(
                item.get("name") or item.get("title") or item.get("label")
            )
        else:
            name = text_or_none(item)
        if name:
            names.append(name)
    return names


def _structured_selected_option_values(
    item: dict[str, object],
    *,
    labels: dict[str, dict[str, str]],
) -> dict[str, str]:
    raw_selected = item.get("selectedOptions")
    if not isinstance(raw_selected, list):
        raw_selected = item.get("selected_options")
    if not isinstance(raw_selected, list):
        return {}
    option_values: dict[str, str] = {}
    for selected in raw_selected:
        if not isinstance(selected, dict):
            continue
        axis_key = _public_variant_axis_key(
            selected.get("name") or selected.get("option") or selected.get("label")
        )
        cleaned = text_or_none(
            selected.get("value")
            or selected.get("displayValue")
            or selected.get("label")
        )
        if not axis_key or not cleaned:
            continue
        option_values[axis_key] = labels.get(axis_key, {}).get(cleaned, cleaned)
    return option_values


def _structured_option_index_values(
    item: dict[str, object],
    *,
    option_names: list[str],
) -> dict[str, str]:
    if not option_names:
        return {}
    option_values: dict[str, str] = {}
    for index, option_name in enumerate(option_names, start=1):
        axis_key = _public_variant_axis_key(option_name)
        cleaned = text_or_none(item.get(f"option{index}"))
        if not axis_key or not cleaned:
            continue
        option_values[axis_key] = cleaned
    return option_values


def _structured_variant_option_values(
    item: dict[str, object],
    *,
    payload: dict[str, object],
    labels: dict[str, dict[str, str]],
) -> dict[str, str]:
    variation_values = item.get("variationValues")
    if not isinstance(variation_values, dict):
        variation_values = item.get("variation_values")
    if isinstance(variation_values, dict):
        option_values: dict[str, str] = {}
        for axis_name, raw_value in variation_values.items():
            axis_key = _public_variant_axis_key(axis_name)
            cleaned = text_or_none(raw_value)
            if not axis_key or not cleaned:
                continue
            option_values[axis_key] = labels.get(axis_key, {}).get(cleaned, cleaned)
        if option_values:
            return option_values
    if option_values := _structured_selected_option_values(item, labels=labels):
        return option_values
    return _structured_option_index_values(
        item,
        option_names=_structured_product_option_names(payload),
    )


def _first_nonblank(mapping: dict[str, object], keys: tuple[str, ...]) -> object:
    return next(
        (
            mapping.get(key)
            for key in keys
            if mapping.get(key) not in (None, "", [], {})
        ),
        None,
    )


def _raw_product_variants(payload: dict[str, object]) -> list[object]:
    variants = payload.get("variants")
    if not isinstance(variants, list):
        size_options = payload.get("sizeOptions")
        variants = (
            size_options.get("options") if isinstance(size_options, dict) else None
        )
    if (
        not isinstance(variants, list) or not variants
    ) and _payload_is_single_size_variant(payload):
        return [payload]
    return variants if isinstance(variants, list) else []


def _structured_product_variant_identity(
    item: dict[str, object], option_values: dict[str, str]
) -> dict[str, object]:
    row: dict[str, object] = {"option_values": option_values}
    sku = text_or_none(
        item.get("sku") or item.get("productId") or item.get("product_id")
    )
    variant_id = text_or_none(
        item.get("id") or item.get("productId") or item.get("product_id")
    )
    if sku:
        row["sku"] = sku
    if variant_id:
        row["variant_id"] = variant_id
    return row


def _add_structured_variant_money(
    row: dict[str, object],
    item: dict[str, object],
    payload: dict[str, object],
    page_url: str,
) -> None:
    raw_price = _first_nonblank(item, ("discountedPrice", "discounted_price", "price"))
    price = _coerce_structured_candidate_value(
        "price", raw_price, page_url=page_url, payload=payload, source_key="price"
    )
    if price not in (None, "", [], {}):
        row["price"] = price
    raw_availability = _first_nonblank(
        item, ("availability", "available", "availableForSale")
    )
    availability = coerce_field_value("availability", raw_availability, page_url)
    if availability in (None, "", [], {}):
        out_of_stock = _coerce_boolean_flag(item.get("isOutOfStock"))
        if out_of_stock is not None:
            availability = "out_of_stock" if out_of_stock else "in_stock"
    if availability not in (None, "", [], {}):
        row["availability"] = availability


def _add_structured_variant_media(
    row: dict[str, object], item: dict[str, object], page_url: str
) -> None:
    image = _first_nonblank(
        item, ("image", "imageUrl", "featured_image", "featuredImage")
    )
    image_url = coerce_field_value("image_url", image, page_url)
    if image_url not in (None, "", [], {}):
        row["image_url"] = image_url
    raw_url = _first_nonblank(item, ("url", "action_url", "productUrl"))
    variant_url = coerce_field_value("url", raw_url, page_url)
    variant_id = text_or_none(row.get("variant_id"))
    if variant_url in (None, "", [], {}) and variant_id:
        variant_url = _variant_url_from_id(page_url, variant_id)
    if variant_url not in (None, "", [], {}):
        row["url"] = variant_url


def _add_structured_variant_axes(
    row: dict[str, object],
    item: dict[str, object],
    option_values: dict[str, str],
    page_url: str,
) -> None:
    for axis, value in option_values.items():
        if is_public_variant_axis(axis):
            row[axis] = value
    color = coerce_field_value(
        "color", item.get("product_detail_color") or item.get("color"), page_url
    )
    if color not in (None, "", [], {}) and "color" not in row:
        row["color"] = color


def _structured_product_variant_row(
    item: dict[str, object],
    payload: dict[str, object],
    labels: dict[str, dict[str, str]],
    page_url: str,
) -> dict[str, object] | None:
    options = _structured_variant_option_values(item, payload=payload, labels=labels)
    if not options:
        size_name = text_or_none(
            item.get("sizeName")
            or item.get("size_name")
            or item.get("name")
            or item.get("title")
        )
        options = {"size": size_name} if size_name else {}
    if not options:
        return None
    row = _structured_product_variant_identity(item, options)
    _add_structured_variant_money(row, item, payload, page_url)
    _add_structured_variant_media(row, item, page_url)
    _add_structured_variant_axes(row, item, options, page_url)
    return row


def _structured_variants_from_product_payload(
    payload: dict[str, object], page_url: str
) -> list[dict[str, object]]:
    labels = _variation_attribute_labels(payload)
    rows: list[dict[str, object]] = []
    for item in _raw_product_variants(payload):
        if isinstance(item, dict):
            row = _structured_product_variant_row(item, payload, labels, page_url)
            if row:
                rows.append(row)
    return rows


def _payload_is_single_size_variant(payload: dict[str, object]) -> bool:
    size_value = (
        payload.get("sizeName")
        or payload.get("size_name")
        or payload.get("size")
        or payload.get("displaySize")
        or payload.get("display_size")
    )
    is_one_size = payload.get("isOneSize") is True or payload.get("is_one_size") is True
    if is_one_size and text_or_none(size_value):
        return True
    return (
        bool(text_or_none(size_value))
        and str(payload.get("type") or "").casefold() == "simple"
    )


def _coerce_boolean_flag(value: object) -> bool | None:
    if isinstance(value, bool):
        return value
    if isinstance(value, int) and value in {0, 1}:
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().casefold()
        if normalized in {"true", "1", "yes"}:
            return True
        if normalized in {"false", "0", "no"}:
            return False
    return None

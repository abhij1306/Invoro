from __future__ import annotations

import html as html_lib
import logging
from typing import Any
from urllib.parse import urlparse

from app.services.dom.html_parser import BeautifulSoup

from app.services.config.extraction_rules import (
    DETAIL_BREADCRUMB_ROOT_LABELS,
    DETAIL_BREADCRUMB_SEPARATOR_LABELS,
    DETAIL_GENDER_TERMS,
    STRUCTURED_CANDIDATE_LIST_SLICE,
    STRUCTURED_CANDIDATE_TRAVERSAL_LIMIT,
)
from app.services.extract.variant_identity_merge import resolve_variants
from app.services.field_policy import normalize_field_key, normalize_requested_field
from app.services.shared.field_coerce import (
    STRUCTURED_MULTI_FIELDS,
    absolute_url,
    clean_text,
    coerce_field_value,
    coerce_text,
    extract_urls,
    is_blank,
    text_or_none,
)

from .collection import add_candidate
from .structured_values import (
    _coerce_structured_candidate_value,
    _structured_alias_allowed,
    _structured_alias_value_allowed,
)
from .variant_rows import (
    _structured_offer_variant_rows,
    _structured_variant_rows,
    _structured_variants_from_product_payload,
    _variant_axes_from_rows,
)

logger = logging.getLogger(__name__)
_structured_candidate_list_slice = int(STRUCTURED_CANDIDATE_LIST_SLICE)
_structured_candidate_traversal_limit = int(STRUCTURED_CANDIDATE_TRAVERSAL_LIMIT)


def _normalized_text_token(value: object) -> str:
    return " ".join(str(value or "").replace("&", " ").split()).strip().lower()


def _gender_from_text(value: object) -> str | None:
    text = _normalized_text_token(value)
    if not text:
        return None
    padded = f" {text.replace('-', ' ')} "
    matches: list[str] = []
    for canonical, terms in DETAIL_GENDER_TERMS.items():
        if any(f" {str(term).lower().replace('-', ' ')} " in padded for term in terms):
            matches.append(str(canonical))
    # DETAIL_GENDER_TERMS may match duplicate terms for one canonical gender.
    # Multiple distinct canonicals are ambiguous and intentionally return None.
    return matches[0] if len(set(matches)) == 1 else None


def _breadcrumb_item_name(item: object) -> str | None:
    if isinstance(item, str):
        return _clean_structured_markup_text(item)
    if not isinstance(item, dict):
        return None
    source = item.get("item")
    if isinstance(source, dict):
        name = source.get("name") or source.get("title")
        if not is_blank(name):
            return _clean_structured_markup_text(name)
    name = item.get("name") or item.get("title")
    if is_blank(name):
        return None
    return _clean_structured_markup_text(name)


def _clean_structured_markup_text(value: object) -> str | None:
    text = text_or_none(value)
    if not text:
        return None
    unescaped = html_lib.unescape(text)
    if "<" in unescaped and ">" in unescaped:
        unescaped = BeautifulSoup(unescaped, "html.parser").get_text("", strip=True)
    cleaned = clean_text(unescaped)
    return cleaned or None


def _breadcrumb_names(payload: dict[str, object], page_url: str = "") -> list[str]:
    raw_items = payload.get("itemListElement")
    if not isinstance(raw_items, list):
        return []

    def _get_position(item: Any) -> float:
        if not isinstance(item, dict):
            return 0.0
        try:
            return float(item.get("position", 0))
        except (ValueError, TypeError):
            return 0.0

    raw_items = _sort_breadcrumb_items(raw_items, _get_position)

    names: list[str] = []
    strip_chars = " \t\n\r" + "".join(DETAIL_BREADCRUMB_SEPARATOR_LABELS)
    for item in raw_items:
        name = _breadcrumb_item_name(item)
        if name:
            clean_name = name.strip(strip_chars)
            if clean_name and clean_name not in DETAIL_BREADCRUMB_SEPARATOR_LABELS:
                names.append(clean_name)
    if not names:
        return []

    def _is_root_label(text: str) -> bool:
        lowered = text.strip().lower()
        if lowered in DETAIL_BREADCRUMB_ROOT_LABELS:
            return True
        if page_url:
            host = urlparse(page_url).netloc.lower()
            if host.startswith("www."):
                host = host[4:]
            host_parts = [part for part in host.split(".") if part]
            second_level_domain = host_parts[-2] if len(host_parts) >= 2 else host
            if host and (lowered == host or lowered == second_level_domain):
                return True
        return False

    if len(names) > 1 and _is_root_label(names[-1]) and not _is_root_label(names[0]):
        names.reverse()

    if _is_root_label(names[0]):
        names = names[1:]
    return [name for name in names if name]


def _sort_breadcrumb_items(items: list[object], position: Any) -> list[object]:
    try:
        return (
            sorted(items, key=position)
            if all(isinstance(item, dict) and position(item) > 0 for item in items)
            else items
        )
    except Exception:
        logger.exception("Failed to sort breadcrumb itemListElement by position")
        return items


def _breadcrumb_category_path(
    payload: dict[str, object], page_url: str = ""
) -> str | None:
    names = _breadcrumb_names(payload, page_url)
    return " > ".join(names) if names else None


def structured_feature_rows(payload: dict[str, object], page_url: str) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()

    def _add(value: object) -> None:
        coerced = coerce_field_value("features", value, page_url)
        values = coerced if isinstance(coerced, list) else [coerced]
        for item in values:
            text = text_or_none(item)
            if not text:
                continue
            lowered = text.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            rows.append(text)

    for key in ("feature", "features"):
        raw_value = payload.get(key)
        if not is_blank(raw_value):
            _add(raw_value)

    additional_properties = payload.get("additionalProperty")
    if isinstance(additional_properties, list):
        for item in additional_properties[:_structured_candidate_list_slice]:
            if not isinstance(item, dict):
                continue
            name = _structured_property_label(item.get("name") or item.get("label"))
            value = _structured_property_value(
                item.get("value") or item.get("description")
            )
            if name and value:
                _add(f"{name}: {value}")
            elif value:
                _add(value)
    return rows


def _structured_property_label(value: object) -> str | None:
    label = _clean_structured_markup_text(value)
    if not label:
        return None
    parts = label.split("_")
    if len(parts) > 1 and all(len(part) == 1 and part.isalnum() for part in parts):
        label = "".join(parts)
    return label


def _structured_property_value(value: object) -> str | None:
    if isinstance(value, (list, tuple, set)):
        values = [
            cleaned
            for item in value
            if (cleaned := _clean_structured_markup_text(item))
        ]
        if not values:
            return None
        return "; ".join(values)
    return _clean_structured_markup_text(value)


def _collect_additional_property_candidates(
    payload: dict[str, object],
    alias_lookup: dict[str, str],
    page_url: str,
    candidates: dict[str, list[object]],
) -> None:
    properties = payload.get("additionalProperty")
    if not isinstance(properties, list):
        return
    for item in properties[:_structured_candidate_list_slice]:
        if not isinstance(item, dict):
            continue
        label = normalize_requested_field(item.get("name")) or normalize_field_key(
            item.get("name")
        )
        canonical = alias_lookup.get(label)
        if canonical:
            add_candidate(
                candidates,
                canonical,
                coerce_field_value(canonical, item.get("value"), page_url),
            )


def _field_envelope_value(payload: dict[str, object]) -> object:
    return next(
        (
            payload.get(key)
            for key in (
                "FieldValues",
                "fieldValues",
                "field_values",
                "FieldValue",
                "fieldValue",
                "field_value",
            )
            if payload.get(key) not in (None, "", [], {})
        ),
        None,
    )


def _collect_field_envelope_candidate(
    payload: dict[str, object],
    alias_lookup: dict[str, str],
    page_url: str,
    candidates: dict[str, list[object]],
) -> None:
    normalized_keys = {normalize_field_key(str(key or "")) for key in payload}
    if not normalized_keys & {"field_name", "field_value", "field_values"}:
        return
    raw_name = (
        payload.get("FieldName")
        or payload.get("fieldName")
        or payload.get("field_name")
    )
    label_text = str(raw_name or "")
    label = normalize_requested_field(label_text) or normalize_field_key(label_text)
    canonical = alias_lookup.get(label)
    if not canonical:
        return
    raw_value = _field_envelope_value(payload)
    if isinstance(raw_value, list) and canonical not in STRUCTURED_MULTI_FIELDS:
        raw_value = " ".join(text for item in raw_value if (text := text_or_none(item)))
    add_candidate(
        candidates,
        canonical,
        coerce_field_value(canonical, raw_value, page_url),
    )


def _structured_key_is_skipped(
    normalized_key: str,
    *,
    breadcrumb_list: bool,
    list_item_wrapper: bool,
    normalized_type: str,
) -> bool:
    breadcrumb_keys = {"item_list_element", "item", "name", "title", "position"}
    list_item_keys = {"item", "name", "title", "position"}
    if breadcrumb_list and normalized_key in breadcrumb_keys:
        return True
    if list_item_wrapper and normalized_key in list_item_keys:
        return True
    return "productgroup" in normalized_type and normalized_key in {
        "has_variant",
        "hasvariant",
    }


def _collect_structured_payload_items(
    payload: dict[str, object],
    alias_lookup: dict[str, str],
    page_url: str,
    candidates: dict[str, list[object]],
    *,
    depth: int,
    limit: int,
    in_variant_context: bool,
    normalized_type: str,
    breadcrumb_list: bool,
    list_item_wrapper: bool,
    review_like: bool,
) -> None:
    for key, value in payload.items():
        if str(key).startswith("@"):
            collect_structured_candidates(
                value,
                alias_lookup,
                page_url,
                candidates,
                depth=depth + 1,
                limit=limit,
                in_variant_context=in_variant_context,
            )
            continue
        normalized_key = normalize_field_key(key)
        if _structured_key_is_skipped(
            normalized_key,
            breadcrumb_list=breadcrumb_list,
            list_item_wrapper=list_item_wrapper,
            normalized_type=normalized_type,
        ):
            continue
        child_variant_context = in_variant_context or normalized_key in {
            "has_variant",
            "hasvariant",
            "variants",
        }
        canonical = alias_lookup.get(normalized_key)
        review_field_blocked = review_like and canonical in {
            "title",
            "description",
            "image_url",
            "additional_images",
        }
        if (
            canonical
            and not in_variant_context
            and not review_field_blocked
            and _structured_alias_allowed(
                canonical=canonical, normalized_key=normalized_key, payload=payload
            )
            and _structured_alias_value_allowed(
                canonical=canonical,
                normalized_key=normalized_key,
                payload=payload,
                value=value,
            )
        ):
            add_candidate(
                candidates,
                canonical,
                _coerce_structured_candidate_value(
                    canonical,
                    value,
                    page_url=page_url,
                    payload=payload,
                    source_key=normalized_key,
                ),
            )
        collect_structured_candidates(
            value,
            alias_lookup,
            page_url,
            candidates,
            depth=depth + 1,
            limit=limit,
            in_variant_context=child_variant_context,
        )


def _structured_product_variants(
    payload: dict[str, object], page_url: str
) -> list[dict[str, object]]:
    variants = _structured_variant_rows(payload.get("hasVariant"), page_url)
    variants.extend(_structured_offer_variant_rows(payload.get("offers"), page_url))
    variants.extend(_structured_variants_from_product_payload(payload, page_url))
    if variants and (axes := _variant_axes_from_rows(variants)):
        return resolve_variants(axes, variants)
    return variants


def _valid_structured_id(value: object) -> object | None:
    if not isinstance(value, str) or not value or value.startswith("_:"):
        return None
    return value if "/" in value or ":" in value else None


def _product_identity_values(
    payload: dict[str, object], page_url: str
) -> dict[str, object | None]:
    fallback = _valid_structured_id(payload.get("@id"))
    return {
        "title": coerce_text(payload.get("name") or payload.get("title")),
        "url": absolute_url(page_url, payload.get("url") or fallback or page_url),
        "description": coerce_text(payload.get("description")),
        "brand": coerce_field_value("brand", payload.get("brand"), page_url),
        "sku": coerce_text(payload.get("sku")),
        "part_number": coerce_text(payload.get("mpn")),
        "barcode": coerce_text(
            payload.get("gtin13") or payload.get("gtin") or payload.get("gtin14")
        ),
        "category": coerce_text(payload.get("category")),
        "materials": coerce_text(payload.get("material")),
    }


def _product_commerce_values(
    payload: dict[str, object], page_url: str
) -> dict[str, object | None]:
    offer = payload.get("offers")
    offer = offer[0] if isinstance(offer, list) and offer else offer
    aggregate = payload.get("aggregateRating")
    return {
        "price": coerce_field_value("price", offer or payload, page_url),
        "currency": coerce_field_value("currency", offer or payload, page_url),
        "availability": coerce_field_value("availability", offer or payload, page_url),
        "rating": coerce_field_value("rating", aggregate, page_url),
        "review_count": coerce_field_value("review_count", aggregate, page_url),
        "gender": coerce_field_value("gender", payload.get("gender"), page_url),
        "color": coerce_field_value("color", payload.get("color"), page_url),
        "size": coerce_field_value("size", payload.get("size"), page_url),
    }


def _collect_product_payload_candidates(
    payload: dict[str, object],
    page_url: str,
    candidates: dict[str, list[object]],
) -> None:
    values = _product_identity_values(payload, page_url)
    values.update(_product_commerce_values(payload, page_url))
    for field_name, value in values.items():
        add_candidate(candidates, field_name, value)
    if features := structured_feature_rows(payload, page_url):
        add_candidate(candidates, "features", features)
    if images := extract_urls(payload.get("image"), page_url):
        add_candidate(candidates, "image_url", images[0])
        add_candidate(candidates, "additional_images", images[1:])
    if variants := _structured_product_variants(payload, page_url):
        add_candidate(candidates, "variants", variants)
        add_candidate(candidates, "variant_count", len(variants))


def _collect_embedded_variant_candidates(
    payload: dict[str, object],
    page_url: str,
    candidates: dict[str, list[object]],
) -> None:
    if candidates.get("variants") or not _embedded_payload_has_variant_options(payload):
        return
    variants = _structured_variants_from_product_payload(payload, page_url)
    if not variants:
        return
    if axes := _variant_axes_from_rows(variants):
        variants = resolve_variants(axes, variants)
    add_candidate(candidates, "variants", variants)
    add_candidate(candidates, "variant_count", len(variants))


def _collect_job_payload_candidates(
    payload: dict[str, object],
    page_url: str,
    candidates: dict[str, list[object]],
) -> None:
    organization = payload.get("hiringOrganization")
    values = {
        "title": coerce_text(payload.get("title") or payload.get("name")),
        "url": absolute_url(page_url, payload.get("url") or page_url),
        "apply_url": absolute_url(page_url, payload.get("url") or page_url),
        "company": coerce_field_value("company", organization, page_url),
        "location": coerce_field_value(
            "location", payload.get("jobLocation"), page_url
        ),
        "posted_date": coerce_text(payload.get("datePosted")),
        "job_type": coerce_text(payload.get("employmentType")),
        "salary": coerce_field_value("salary", payload.get("baseSalary"), page_url),
        "description": coerce_text(payload.get("description")),
        "remote": coerce_text(payload.get("jobLocationType")),
    }
    for field_name, value in values.items():
        add_candidate(candidates, field_name, value)


def collect_structured_candidates(
    payload: object,
    alias_lookup: dict[str, str],
    page_url: str,
    candidates: dict[str, list[object]],
    *,
    depth: int = 0,
    limit: int = _structured_candidate_traversal_limit,
    in_variant_context: bool = False,
) -> None:
    if depth > limit:
        return
    if isinstance(payload, dict):
        _collect_structured_dict(
            payload,
            alias_lookup,
            page_url,
            candidates,
            depth=depth,
            limit=limit,
            in_variant_context=in_variant_context,
        )
    elif isinstance(payload, list):
        for item in payload[:_structured_candidate_list_slice]:
            collect_structured_candidates(
                item,
                alias_lookup,
                page_url,
                candidates,
                depth=depth + 1,
                limit=limit,
                in_variant_context=in_variant_context,
            )


def _collect_structured_dict(
    payload: dict[str, object],
    alias_lookup: dict[str, str],
    page_url: str,
    candidates: dict[str, list[object]],
    *,
    depth: int,
    limit: int,
    in_variant_context: bool,
) -> None:
    raw_type = payload.get("@type")
    normalized_type = (
        " ".join(raw_type) if isinstance(raw_type, list) else str(raw_type or "")
    ).lower()
    breadcrumb_list = "breadcrumblist" in normalized_type
    list_item_wrapper = "listitem" in normalized_type and any(
        key in payload for key in ("position", "item")
    )
    _collect_additional_property_candidates(payload, alias_lookup, page_url, candidates)
    if breadcrumb_list and (category := _breadcrumb_category_path(payload, page_url)):
        add_candidate(candidates, "category", category)
        if gender := _gender_from_text(category):
            add_candidate(candidates, "gender", gender)
    _collect_field_envelope_candidate(payload, alias_lookup, page_url, candidates)
    _collect_structured_payload_items(
        payload,
        alias_lookup,
        page_url,
        candidates,
        depth=depth,
        limit=limit,
        in_variant_context=in_variant_context,
        normalized_type=normalized_type,
        breadcrumb_list=breadcrumb_list,
        list_item_wrapper=list_item_wrapper,
        review_like=any(
            token in normalized_type for token in ("review", "reviewrating")
        ),
    )
    if not in_variant_context and any(
        token in normalized_type for token in ("product", "productgroup")
    ):
        _collect_product_payload_candidates(payload, page_url, candidates)
    if not in_variant_context:
        _collect_embedded_variant_candidates(payload, page_url, candidates)
    if "jobposting" in normalized_type:
        _collect_job_payload_candidates(payload, page_url, candidates)


def _embedded_payload_has_variant_options(payload: dict[str, object]) -> bool:
    size_options = payload.get("sizeOptions")
    has_size_options = False
    if isinstance(size_options, dict):
        options = size_options.get("options")
        has_size_options = isinstance(options, list) and any(
            isinstance(item, dict) for item in options
        )
    size_value = payload.get("sizeName") or payload.get("size_name")
    has_one_size = payload.get("isOneSize") is True and size_value not in (
        None,
        "",
        [],
        {},
    )
    raw_variants = payload.get("variants")
    variant_row_signal_fields = {
        "sku",
        "productId",
        "product_id",
        "price",
        "discountedPrice",
        "discounted_price",
        "availability",
        "available",
        "availableForSale",
        "isOutOfStock",
        "sizeName",
        "size",
        "color",
        "selectedOptions",
        "variationValues",
        "option1",
        "url",
        "action_url",
    }
    has_variant_rows = isinstance(raw_variants, list) and any(
        isinstance(item, dict) and bool(set(item) & variant_row_signal_fields)
        for item in raw_variants
    )
    if not has_size_options and not has_one_size and not has_variant_rows:
        return False
    return any(
        not is_blank(payload.get(field_name))
        for field_name in ("id", "sku", "title", "subTitle", "price", "discountedPrice")
    )

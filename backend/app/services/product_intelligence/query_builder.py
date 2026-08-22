from __future__ import annotations

import re

from app.services.config.product_intelligence import (
    BRAND_DOMAIN_MAP,
    SEARCH_PHRASE_BUY,
    SEARCH_SITE_PREFIX,
    product_intelligence_settings,
)
from app.services.product_intelligence.matching import (
    manufacturer_style_code,
    normalize_brand,
)
from app.services.shared.field_coerce import clean_text


def build_search_queries(
    product: dict[str, object], *, source_domain_value: str = ""
) -> list[str]:
    del source_domain_value
    brand = normalize_brand(product.get("brand"))
    title = _title_without_brand(product.get("title"), product.get("brand"), brand)
    queries: list[str] = []
    gtin = _identity_field(product, "gtin")
    mpn = _query_identifier_value(product)
    query_identifier = gtin or mpn
    brand_domain = BRAND_DOMAIN_MAP.get(brand)
    brand_site = f"{SEARCH_SITE_PREFIX}{brand_domain}" if brand_domain else ""
    if gtin:
        queries.append(_quoted(gtin))
    if brand and title and brand_site:
        if query_identifier:
            queries.append(_join_query_parts(brand_site, _quoted(query_identifier)))
        queries.append(_join_query_parts(brand_site, brand, title))
    if brand and title:
        if query_identifier:
            queries.append(_join_query_parts(brand, title, _quoted(query_identifier)))
        queries.append(_join_query_parts(brand, title))
    if title and not brand:
        if query_identifier:
            queries.append(_join_query_parts(_quoted(title), _quoted(query_identifier)))
        queries.append(_join_query_parts(_quoted(title), SEARCH_PHRASE_BUY))
    return _dedupe_keep_order(queries)


def _title_without_brand(title: object, *brand_variants: object) -> str:
    normalized_title = clean_text(title).strip()
    if not normalized_title:
        return ""
    for brand_variant in brand_variants:
        trimmed = _strip_query_prefix(
            normalized_title, clean_text(brand_variant).strip()
        )
        if trimmed != normalized_title:
            return _limit_query_tokens(trimmed)
    return _limit_query_tokens(normalized_title)


def _strip_query_prefix(text: str, prefix: str) -> str:
    normalized_text = str(text or "").strip()
    normalized_prefix = str(prefix or "").strip()
    if not normalized_text or not normalized_prefix:
        return normalized_text
    if not normalized_text.casefold().startswith(normalized_prefix.casefold()):
        return normalized_text
    trimmed = normalized_text[len(normalized_prefix) :].lstrip(" -\u2013\u2014:/|,")
    return trimmed or normalized_text


def _limit_query_tokens(text: str) -> str:
    tokens = str(text or "").split()
    return " ".join(tokens[: product_intelligence_settings.title_token_limit])


def _query_identifier_value(product: dict[str, object]) -> str:
    if mpn := _identity_field(product, "mpn"):
        return mpn
    style_core = manufacturer_style_code(
        product.get("style_code"),
        product.get("sku"),
        product.get("style"),
        product.get("product_id"),
        gtin_value=product.get("gtin"),
    )
    if style_core:
        return style_core.split()[0]
    return next(
        (
            value
            for key in ("style", "product_id")
            if (value := _identity_field(product, key))
            and _looks_like_manufacturer_identifier(value)
        ),
        "",
    )


def _identity_field(product: dict[str, object], key: str) -> str:
    return str(product.get(key) or "").strip()


def _looks_like_manufacturer_identifier(value: object) -> bool:
    compact = re.sub(r"[^a-z0-9]+", "", str(value or "").strip().casefold())
    return bool(
        compact
        and any(char.isalpha() for char in compact)
        and any(char.isdigit() for char in compact)
    )


def _quoted(value: object) -> str:
    text = " ".join(str(value or "").strip().replace('"', '\\"').split())
    return f'"{text}"' if text else ""


def _join_query_parts(*parts: str) -> str:
    return " ".join(part for part in parts if part)


def _dedupe_keep_order(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))

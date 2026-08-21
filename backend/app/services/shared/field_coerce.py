"""Shared field coercion, normalization, and public-record shaping helpers."""

from __future__ import annotations

from .field_coerce_core import (IMAGE_FIELDS, LISTING_UTILITY_TITLE_REGEXES, LONG_TEXT_FIELDS, PRICE_RE, PRODUCT_URL_HINTS, RATING_RE,
    REVIEW_COUNT_RE, STRUCTURED_MULTI_FIELDS, STRUCTURED_OBJECT_FIELDS, STRUCTURED_OBJECT_LIST_FIELDS, URL_FIELDS, absolute_url, clean_text,
    coerce_brand_text, coerce_int, coerce_structured_scalar, coerce_text, decimal_for_shared_price, direct_record_to_surface_fields,
    extract_currency_code, extract_price_text, extract_urls, infer_brand_from_product_url, infer_brand_from_title_marker, is_blank, is_title_noise,
    object_dict, object_list, safe_int, same_host, strip_html_tags, strip_tracking_query_params, surface_alias_lookup, surface_fields, text_or_none,
    validate_record_for_surface,)
from .field_coerce_values import coerce_availability_value, coerce_field_value, finalize_record

__all__ = ("IMAGE_FIELDS", "LISTING_UTILITY_TITLE_REGEXES", "LONG_TEXT_FIELDS", "PRICE_RE", "PRODUCT_URL_HINTS", "RATING_RE", "REVIEW_COUNT_RE",
    "STRUCTURED_MULTI_FIELDS", "STRUCTURED_OBJECT_FIELDS", "STRUCTURED_OBJECT_LIST_FIELDS", "URL_FIELDS", "absolute_url", "clean_text",
    "coerce_availability_value", "coerce_brand_text", "coerce_int", "coerce_structured_scalar", "coerce_text", "decimal_for_shared_price",
    "coerce_field_value", "direct_record_to_surface_fields", "extract_currency_code", "extract_price_text", "extract_urls", "finalize_record",
    "infer_brand_from_product_url", "infer_brand_from_title_marker", "is_blank", "is_title_noise", "object_dict", "object_list", "safe_int",
    "same_host", "strip_html_tags", "strip_tracking_query_params", "surface_alias_lookup", "surface_fields", "text_or_none",
    "validate_record_for_surface",)

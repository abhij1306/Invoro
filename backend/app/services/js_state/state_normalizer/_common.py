from __future__ import annotations
# ruff: noqa: F401,F403,F405

import logging
import re
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from typing import Any

import jmespath
from bs4 import BeautifulSoup
from glom import GlomError, glom  # type: ignore[import-untyped]

from app.services.config.js_state_field_specs import (
    JS_STATE_PRODUCT_PAYLOAD_LIMIT,
    JS_STATE_LIST_ITERATION_LIMIT,
    JS_STATE_OPTION_GROUP_VALUE_KEYS,
    JS_STATE_PRODUCT_FIELD_SPEC,
    JS_STATE_PRODUCT_OPTION_GROUP_KEYS,
    JS_STATE_PRODUCT_VARIANT_LIST_KEYS,
    JS_STATE_VARIANT_FIELD_SPEC,
    VARIANT_AXIS_KEYS,
)
from app.services.config.extraction_rules import (
    DETAIL_ARTIFACT_PRODUCT_TYPE_PATTERNS,
    DETAIL_ARTIFACT_PRODUCT_TYPE_VALUES,
    DETAIL_LOW_SIGNAL_PRODUCT_TYPE_VALUES,
    ECOMMERCE_DESCRIPTION_BLOCK_LIMIT,
)
from app.services.extraction_html_helpers import html_to_text
from app.services.field_policy import normalize_field_key
from app.services.dom.selector_engine import dedupe_image_urls, extract_feature_rows
from app.services.extract.variant_identity_merge import (
    merge_variant_rows,
    resolve_variants,
)
from app.services.extract.variant_axis import normalized_variant_axis_key
from app.services.shared.field_coerce import (
    clean_text,
    extract_urls,
    surface_alias_lookup,
    text_or_none,
)
from app.services.js_state.marketplace_choice_mapper import (
    extract_marketplace_choice_products,
)
from app.services.js_state.variant_options import (
    option_value_labels,
    variant_axis_value,
    variant_option_values,
    variant_selection_values,
)
from app.services.js_state.helpers import (
    availability_value,
    compact_dict,
    normalize_price,
    select_variant,
    stock_quantity,
    variant_attribute,
    variant_axes,
)
from app.services.js_state import job_mapper as _job_mapper
from app.services.platform_policy import JSStateExtractorConfig, platform_js_state_extractors

logger = logging.getLogger(__name__)
PRODUCT_FIELD_SPEC = JS_STATE_PRODUCT_FIELD_SPEC
_VARIANT_FIELD_SPEC = JS_STATE_VARIANT_FIELD_SPEC
map_configured_state_payload = _job_mapper.map_configured_state_payload

def _as_list(value: object) -> list[Any]:
    return value if isinstance(value, list) else []

__all__ = [
    "Any", "BeautifulSoup", "Decimal", "DETAIL_ARTIFACT_PRODUCT_TYPE_PATTERNS",
    "DETAIL_ARTIFACT_PRODUCT_TYPE_VALUES", "DETAIL_LOW_SIGNAL_PRODUCT_TYPE_VALUES",
    "ECOMMERCE_DESCRIPTION_BLOCK_LIMIT", "GlomError", "InvalidOperation", "JSStateExtractorConfig",
    "JS_STATE_LIST_ITERATION_LIMIT", "JS_STATE_OPTION_GROUP_VALUE_KEYS", "JS_STATE_PRODUCT_FIELD_SPEC",
    "JS_STATE_PRODUCT_OPTION_GROUP_KEYS", "JS_STATE_PRODUCT_PAYLOAD_LIMIT",
    "JS_STATE_PRODUCT_VARIANT_LIST_KEYS", "JS_STATE_VARIANT_FIELD_SPEC", "PRODUCT_FIELD_SPEC",
    "VARIANT_AXIS_KEYS", "_VARIANT_FIELD_SPEC", "_as_list", "_job_mapper", "availability_value",
    "clean_text", "compact_dict", "dedupe_image_urls", "extract_feature_rows",
    "extract_marketplace_choice_products", "extract_urls", "glom", "html_to_text", "jmespath",
    "logger", "map_configured_state_payload", "merge_variant_rows", "normalize_field_key",
    "normalize_price", "normalized_variant_axis_key", "option_value_labels", "parse_qsl",
    "platform_js_state_extractors", "re", "resolve_variants", "select_variant", "stock_quantity",
    "surface_alias_lookup", "text_or_none", "urlencode", "urlsplit", "urlunsplit",
    "variant_attribute", "variant_axes", "variant_axis_value", "variant_option_values",
    "variant_selection_values",
]

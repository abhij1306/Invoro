from __future__ import annotations

import json

import pytest

from app.services.dom.html_parser import BeautifulSoup

from app.services.adapters.shopify import ShopifyAdapter

from app.services.adapters.myntra import MyntraAdapter

from app.services.extract.detail.assembly.record_assembly import (
    build_detail_record,
    extract_detail_records,
)

from app.services.extract.field_candidates.variant_rows import (
    _structured_variants_from_product_payload,
)

from app.services.extract.field_candidates.structured_payloads import (
    structured_feature_rows,
)

from app.services.extract.detail.variants.dom_options import variant_option_availability

from app.services.extract.detail.variants.dom_availability import (
    reconcile_variant_availability_from_dom,
)

from app.services.extract.detail.price.core import (
    backfill_detail_price_from_html,
    reconcile_parent_price_against_variant_range,
    reconcile_detail_currency_with_url,
)
from app.services.shared.currency_hints import detail_currency_hint_is_host_level

from app.services.extract.detail.images.cleanup import (
    detail_image_matches_primary_family,
)

from app.services.extract.detail.assembly.final_cleanup import (
    repair_ecommerce_detail_record_quality,
)

from app.services.extract.detail.assembly.record_sanitization import (
    sanitize_detail_placeholder_scalars,
)

from app.services.extract.detail.variants.pruning import (
    sanitize_variant_row,
)

from app.services.extract.detail.assembly import raw_signals as detail_raw_signals

from app.services.extract.detail.assembly import dom_completion as detail_dom_completion

from app.services.extract.detail.assembly.title_scorer import title_needs_promotion

from app.services.extract.detail.identity.core import (
    detail_title_fallback_looks_like_code,
    detail_redirect_identity_is_mismatched,
    detail_slug_title_fallback_from_url,
)

from app.services.extract.detail.text.sanitizer import detail_product_type_is_low_signal

from app.services.extract.variant_normalization import normalize_variant_record

from app.services.pipeline.extract_records import extract_records

from app.services.structured_sources import harvest_js_state_objects

from tests.fixtures.loader import read_optional_artifact_text


__all__ = ['BeautifulSoup', 'MyntraAdapter', 'ShopifyAdapter', '_structured_variants_from_product_payload', 'annotations', 'backfill_detail_price_from_html', 'build_detail_record', 'detail_currency_hint_is_host_level', 'detail_dom_completion', 'detail_image_matches_primary_family', 'detail_product_type_is_low_signal', 'detail_raw_signals', 'detail_redirect_identity_is_mismatched', 'detail_slug_title_fallback_from_url', 'detail_title_fallback_looks_like_code', 'extract_detail_records', 'extract_records', 'harvest_js_state_objects', 'json', 'normalize_variant_record', 'pytest', 'read_optional_artifact_text', 'reconcile_detail_currency_with_url', 'reconcile_parent_price_against_variant_range', 'reconcile_variant_availability_from_dom', 'repair_ecommerce_detail_record_quality', 'sanitize_detail_placeholder_scalars', 'sanitize_variant_row', 'structured_feature_rows', 'title_needs_promotion', 'variant_option_availability']  # fmt: skip

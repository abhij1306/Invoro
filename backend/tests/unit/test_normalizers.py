from __future__ import annotations

import pytest

from app.services.dom.html_parser import BeautifulSoup

from app.services.extract.detail.assembly.final_cleanup import (
    _reconcile_variant_derived_parent_fields,
    repair_ecommerce_detail_record_quality,
    sanitize_variant_row,
)

from app.services.extract.detail.price.core import backfill_detail_price_from_html

from app.services.extract.variant_normalization import normalize_variant_record

from app.services.extract.variant_normalization import backfill, hydration, sanitization

from app.services.extract.variant_normalization.contract import enforce_payload_limits

from app.services.shared.field_coerce import coerce_field_value

from app.services.dom.selector_engine import extract_node_value

from app.services.normalizers import normalize_decimal_price, normalize_value


__all__ = tuple(name for name in globals() if not name.startswith("__"))

"""Detail price extraction facade.

Notes:
    Currency reconciliation and price magnitude repair live in detail_price_core.py.
"""

from __future__ import annotations

from app.services.extract import detail_price_core as _detail_price_core
from app.services.extract.detail_price_core import (
    append_record_field_source,
    backfill_detail_price_from_html,
    currency_hint_from_page_url,
    detail_currency_hint_is_host_level,
    detail_price_decimal,
    drop_low_signal_zero_detail_price,
    format_detail_price_decimal,
    normalize_mismatched_host_currency_price,
    reconcile_detail_currency_with_url,
    reconcile_detail_price_magnitudes,
    reconcile_parent_price_against_variant_range,
    record_field_sources,
)

__all__ = list(_detail_price_core.__all__)

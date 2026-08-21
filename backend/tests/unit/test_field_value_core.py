from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.shared.field_coerce import (
    decimal_for_shared_price,
    absolute_url,
    clean_text,
    coerce_field_value,
    direct_record_to_surface_fields,
    extract_currency_code,
    extract_urls,
    infer_brand_from_product_url,
    infer_brand_from_title_marker,
    is_title_noise,
    strip_tracking_query_params,
    surface_alias_lookup,
    validate_record_for_surface,
)

from app.services.extract.variant_identity_merge import merge_variant_rows

from app.services.field_url_normalization import registrable_host, same_site

from app.services.public_record_firewall import public_record_data_for_surface


__all__ = tuple(name for name in globals() if not name.startswith("__"))

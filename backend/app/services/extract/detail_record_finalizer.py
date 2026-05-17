"""Detail record finalization facade.

Notes:
    Cleanup, image family checks, and variant repair live in
    detail_final_cleanup.py. Keep this import surface only until callers move.
"""

from __future__ import annotations

from app.services.extract.detail_final_cleanup import (
    detail_image_matches_primary_family,
    detail_title_looks_like_placeholder,
    repair_ecommerce_detail_record_quality,
    sanitize_variant_row,
)

__all__ = [
    "detail_image_matches_primary_family",
    "detail_title_looks_like_placeholder",
    "repair_ecommerce_detail_record_quality",
    "sanitize_variant_row",
]

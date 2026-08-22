from __future__ import annotations

from .dom_extraction import (
    backfill_variants_from_dom_if_missing,
    extract_variants_from_dom,
)

__all__ = ("extract_variants_from_dom", "backfill_variants_from_dom_if_missing")

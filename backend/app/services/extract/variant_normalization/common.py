from __future__ import annotations

from app.services.extract.variant_normalization.backfill import (
    backfill_parent_scalar_axes_from_variants as _backfill_parent_scalar_axes_from_variants,
    backfill_variant_context as _backfill_variant_context,
    enforce_variant_currency_context as _enforce_variant_currency_context,
)
from app.services.extract.variant_normalization.contract import (
    enforce_flat_variant_public_contract,
    enforce_payload_limits,
    flatten_variants_for_public_output,
)
from app.services.extract.variant_normalization.deduplication import (
    dedupe_and_prune_variant_rows as _dedupe_and_prune_variant_rows,
    prune_child_size_rows_from_adult_products as _prune_child_size_rows_from_adult_products,
    prune_unrecognized_size_rows_when_real_sizes_exist as _prune_unrecognized_size_rows_when_real_sizes_exist,
)
from app.services.extract.variant_normalization.hydration import (
    hydrate_variant_axes as _hydrate_variant_axes,
)
from app.services.extract.variant_normalization.sanitization import (
    drop_polluted_parent_scalar_axes as _drop_polluted_parent_scalar_axes,
    sanitize_variant_axes as _sanitize_variant_axes,
)

__all__ = (
    "_backfill_parent_scalar_axes_from_variants",
    "_backfill_variant_context",
    "_dedupe_and_prune_variant_rows",
    "_drop_polluted_parent_scalar_axes",
    "_enforce_variant_currency_context",
    "_hydrate_variant_axes",
    "_prune_child_size_rows_from_adult_products",
    "_prune_unrecognized_size_rows_when_real_sizes_exist",
    "_sanitize_variant_axes",
    "enforce_flat_variant_public_contract",
    "enforce_payload_limits",
    "flatten_variants_for_public_output",
)

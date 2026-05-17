"""Detail DOM extraction facade.

Notes:
    Keep this facade small; primary DOM context, fallback fields, and DOM variant
    recovery live in focused owners. Delete after callers move to those owners.
"""

from __future__ import annotations

from app.services.config.extraction_rules import (
    DOM_VARIANT_CARTESIAN_COMBO_LIMIT,
    DOM_VARIANT_GROUP_LIMIT,
)
from app.services.extract import detail_dom_context as _impl

primary_dom_context = _impl.primary_dom_context
record_has_rich_existing_variants = _impl.record_has_rich_existing_variants
variant_option_availability = _impl.variant_option_availability
existing_variant_cluster_has_transport_signal = (
    _impl.existing_variant_cluster_has_transport_signal
)
extract_heading_sections = _impl.extract_heading_sections

# Bind config-driven runtime limits onto the implementation module once at
# import time. Tests use ``monkeypatch.setattr(detail_dom_extractor, "DOM_*", ...)``
# to override these for a single case; ``monkeypatch`` restores the facade
# attribute on teardown. Re-syncing on every call would mutate the shared
# implementation module from inside test bodies (a race risk under pytest-xdist),
# and would also clobber any direct ``_impl.DOM_*`` patch installed by another
# test. The facade values are the source of truth; mirror them onto ``_impl``
# at load time so the implementation sees the same defaults.
_impl.DOM_VARIANT_GROUP_LIMIT = DOM_VARIANT_GROUP_LIMIT
_impl.DOM_VARIANT_CARTESIAN_COMBO_LIMIT = DOM_VARIANT_CARTESIAN_COMBO_LIMIT
_DEFAULT_DOM_VARIANT_GROUP_LIMIT = DOM_VARIANT_GROUP_LIMIT
_DEFAULT_DOM_VARIANT_CARTESIAN_COMBO_LIMIT = DOM_VARIANT_CARTESIAN_COMBO_LIMIT


def _sync_limit_patchpoints() -> None:
    if DOM_VARIANT_GROUP_LIMIT != _DEFAULT_DOM_VARIANT_GROUP_LIMIT:
        _impl.DOM_VARIANT_GROUP_LIMIT = DOM_VARIANT_GROUP_LIMIT
    if DOM_VARIANT_CARTESIAN_COMBO_LIMIT != _DEFAULT_DOM_VARIANT_CARTESIAN_COMBO_LIMIT:
        _impl.DOM_VARIANT_CARTESIAN_COMBO_LIMIT = DOM_VARIANT_CARTESIAN_COMBO_LIMIT


def apply_dom_fallbacks(*args, **kwargs):
    _sync_limit_patchpoints()
    return _impl.apply_dom_fallbacks(*args, **kwargs)


def extract_variants_from_dom(*args, **kwargs):
    _sync_limit_patchpoints()
    return _impl.extract_variants_from_dom(*args, **kwargs)


def backfill_variants_from_dom_if_missing(*args, **kwargs):
    _sync_limit_patchpoints()
    return _impl.backfill_variants_from_dom_if_missing(*args, **kwargs)


__all__ = [
    "DOM_VARIANT_CARTESIAN_COMBO_LIMIT",
    "DOM_VARIANT_GROUP_LIMIT",
    "apply_dom_fallbacks",
    "backfill_variants_from_dom_if_missing",
    "existing_variant_cluster_has_transport_signal",
    "extract_heading_sections",
    "extract_variants_from_dom",
    "primary_dom_context",
    "record_has_rich_existing_variants",
    "variant_option_availability",
]

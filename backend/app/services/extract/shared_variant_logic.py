"""Temporary public re-export shim for legacy variant imports.

Notes:
    Delete after 2026-06-30 once callers import focused variant owners directly.
"""

from __future__ import annotations

from app.services.extract import variant_grouping as _variant_grouping
from app.services.extract.variant_grouping import (
    collapse_duplicate_size_aliases,
    infer_variant_group_name,
    infer_variant_group_name_from_values,
    iter_variant_choice_groups,
    iter_variant_select_groups,
    merge_variant_pair,
    merge_variant_rows,
    normalized_variant_axis_display_name,
    normalized_variant_axis_key,
    option_scalar_fields,
    public_variant_axis_fields,
    resolve_variant_group_name,
    resolve_variants,
    split_variant_axes,
    variant_axis_allowed_single_tokens,
    variant_axis_name_is_semantic,
    variant_dom_cues_present,
    variant_identity,
    variant_option_value_is_noise,
    variant_option_value_matches_noise_token,
    variant_option_value_matches_ui_noise,
    variant_option_value_suffix_noise_patterns,
    variant_row_richness,
    variant_semantic_identity,
    variant_size_value_patterns,
)

_variant_choice_container_for_input = (
    _variant_grouping._variant_choice_container_for_input
)
_variant_choice_container_is_overbroad = (
    _variant_grouping._variant_choice_container_is_overbroad
)
variant_choice_container_for_input = _variant_choice_container_for_input
variant_choice_container_is_overbroad = _variant_choice_container_is_overbroad

__all__ = [
    "collapse_duplicate_size_aliases",
    "infer_variant_group_name",
    "infer_variant_group_name_from_values",
    "iter_variant_choice_groups",
    "iter_variant_select_groups",
    "merge_variant_pair",
    "merge_variant_rows",
    "normalized_variant_axis_display_name",
    "normalized_variant_axis_key",
    "option_scalar_fields",
    "public_variant_axis_fields",
    "resolve_variant_group_name",
    "resolve_variants",
    "split_variant_axes",
    "variant_axis_allowed_single_tokens",
    "variant_axis_name_is_semantic",
    "variant_dom_cues_present",
    "variant_identity",
    "variant_option_value_is_noise",
    "variant_option_value_matches_noise_token",
    "variant_option_value_matches_ui_noise",
    "variant_option_value_suffix_noise_patterns",
    "variant_row_richness",
    "variant_semantic_identity",
    "variant_size_value_patterns",
    "_variant_choice_container_for_input",
    "_variant_choice_container_is_overbroad",
    "variant_choice_container_for_input",
    "variant_choice_container_is_overbroad",
]

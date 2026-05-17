"""Detail identity facade.

Notes:
    URL shape, redirect identity, and detail/listing URL checks live in
    detail_identity_core.py. Imports here are explicit so this facade's
    public API is reviewable and stable across refactors of the core module.
"""

from __future__ import annotations

from app.services.extract.detail_identity_core import (
    detail_identity_codes_from_record_fields,
    detail_identity_codes_from_url,
    detail_identity_codes_match,
    detail_identity_tokens,
    detail_query_identity_codes_from_url,
    detail_redirect_identity_is_mismatched,
    detail_title_from_url,
    detail_url_candidate_is_low_signal,
    detail_url_is_collection_like,
    detail_url_is_utility,
    detail_url_looks_like_product,
    detail_url_matches_requested_identity,
    listing_detail_like_path,
    listing_url_is_structural,
    preferred_detail_identity_url,
    prune_irrelevant_detail_dom_nodes,
    record_matches_requested_detail_identity,
    semantic_detail_identity_tokens,
)

__all__ = [
    "detail_identity_codes_from_record_fields",
    "detail_identity_codes_from_url",
    "detail_identity_codes_match",
    "detail_identity_tokens",
    "detail_query_identity_codes_from_url",
    "detail_redirect_identity_is_mismatched",
    "detail_title_from_url",
    "detail_url_candidate_is_low_signal",
    "detail_url_is_collection_like",
    "detail_url_is_utility",
    "detail_url_looks_like_product",
    "detail_url_matches_requested_identity",
    "listing_detail_like_path",
    "listing_url_is_structural",
    "preferred_detail_identity_url",
    "prune_irrelevant_detail_dom_nodes",
    "record_matches_requested_detail_identity",
    "semantic_detail_identity_tokens",
]

"""Detail identity facade.

Notes:
    URL shape, redirect identity, and detail/listing URL checks live in
    detail_identity_core.py. Imports here are explicit so this facade's
    public API is reviewable and stable across refactors of the core module.
"""

from __future__ import annotations

from app.services.extract import detail_identity_core as _core
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

_detail_identity_codes_from_record_fields = _core._detail_identity_codes_from_record_fields
_detail_identity_codes_from_url = _core._detail_identity_codes_from_url
_detail_identity_tokens = _core._detail_identity_tokens
_detail_marker_matches = _core._detail_marker_matches
_detail_query_identity_codes_from_url = _core._detail_query_identity_codes_from_url
_detail_redirect_identity_is_mismatched = _core._detail_redirect_identity_is_mismatched
_detail_segment_code = _core._detail_segment_code
_detail_segment_looks_like_identity_code = _core._detail_segment_looks_like_identity_code
_detail_title_from_url = _core._detail_title_from_url
_detail_url_candidate_is_low_signal = _core._detail_url_candidate_is_low_signal
_detail_url_is_collection_like = _core._detail_url_is_collection_like
_detail_url_is_utility = _core._detail_url_is_utility
_detail_url_looks_like_product = _core._detail_url_looks_like_product
_detail_url_matches_requested_identity = _core._detail_url_matches_requested_identity
_detail_url_path_segments = _core._detail_url_path_segments
_detail_url_path_tokens = _core._detail_url_path_tokens
_job_detail_like_path = _core._job_detail_like_path
_listing_url_has_category_path_segment = _core._listing_url_has_category_path_segment
_listing_url_has_product_detail_identity = _core._listing_url_has_product_detail_identity
_normalized_detail_identity_code = _core._normalized_detail_identity_code
_path_segment_tokens = _core._path_segment_tokens
_preferred_detail_identity_url = _core._preferred_detail_identity_url
_record_matches_requested_detail_identity = _core._record_matches_requested_detail_identity
_semantic_detail_identity_tokens = _core._semantic_detail_identity_tokens


def __getattr__(name: str):
    return getattr(_core, name)

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
    "_detail_identity_codes_from_record_fields",
    "_detail_identity_codes_from_url",
    "_detail_identity_tokens",
    "_detail_marker_matches",
    "_detail_query_identity_codes_from_url",
    "_detail_redirect_identity_is_mismatched",
    "_detail_segment_code",
    "_detail_segment_looks_like_identity_code",
    "_detail_title_from_url",
    "_detail_url_candidate_is_low_signal",
    "_detail_url_is_collection_like",
    "_detail_url_is_utility",
    "_detail_url_looks_like_product",
    "_detail_url_matches_requested_identity",
    "_detail_url_path_segments",
    "_detail_url_path_tokens",
    "_job_detail_like_path",
    "_listing_url_has_category_path_segment",
    "_listing_url_has_product_detail_identity",
    "_normalized_detail_identity_code",
    "_path_segment_tokens",
    "_preferred_detail_identity_url",
    "_record_matches_requested_detail_identity",
    "_semantic_detail_identity_tokens",
]

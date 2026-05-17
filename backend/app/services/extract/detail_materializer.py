"""Detail materialization facade.

Notes:
    Candidate collection and DOM-completion internals moved to
    detail_candidate_collection.py. Delete this facade after callers import
    focused owners directly.
"""

from __future__ import annotations

from app.services.extract import detail_candidate_collection as _impl

detail_record_rejection_reason = _impl.detail_record_rejection_reason
infer_detail_failure_reason = _impl.infer_detail_failure_reason
repair_ecommerce_detail_record_quality = _impl.repair_ecommerce_detail_record_quality

_detail_title_from_url = _impl._detail_title_from_url
_detail_identity_tokens = _impl._detail_identity_tokens
_detail_identity_codes_from_url = _impl._detail_identity_codes_from_url


def _sync_test_patchpoints() -> None:
    _impl._detail_title_from_url = _detail_title_from_url
    _impl._detail_identity_tokens = _detail_identity_tokens
    _impl._detail_identity_codes_from_url = _detail_identity_codes_from_url


def _prune_irrelevant_detail_structured_payload(*args, **kwargs):
    _sync_test_patchpoints()
    return _impl._prune_irrelevant_detail_structured_payload(*args, **kwargs)


def build_detail_record(*args, **kwargs):
    _sync_test_patchpoints()
    return _impl.build_detail_record(*args, **kwargs)


def extract_detail_records(*args, **kwargs):
    _sync_test_patchpoints()
    return _impl.extract_detail_records(*args, **kwargs)


def _materialize_image_fields(*args, **kwargs):
    return _impl._materialize_image_fields(*args, **kwargs)


def _requires_dom_completion(*args, **kwargs):
    return _impl._requires_dom_completion(*args, **kwargs)


def _should_collect_dom_variants(*args, **kwargs):
    return _impl._should_collect_dom_variants(*args, **kwargs)


prune_irrelevant_detail_structured_payload = (
    _prune_irrelevant_detail_structured_payload
)
materialize_image_fields = _materialize_image_fields
requires_dom_completion = _requires_dom_completion


__all__ = [
    "build_detail_record",
    "detail_record_rejection_reason",
    "extract_detail_records",
    "infer_detail_failure_reason",
    "repair_ecommerce_detail_record_quality",
    "_materialize_image_fields",
    "_prune_irrelevant_detail_structured_payload",
    "_requires_dom_completion",
    "_should_collect_dom_variants",
]

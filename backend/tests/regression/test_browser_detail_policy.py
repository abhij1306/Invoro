from __future__ import annotations

import pytest

from app.services.acquisition import browser_detail, browser_page_helpers
from app.services.config.runtime_settings import crawler_runtime_settings


@pytest.mark.regression
def test_detail_expansion_distinguishes_duplicate_labels_by_element_identity() -> None:
    seen_candidates: set[tuple[str, str, str]] = set()

    def candidate(identity: str) -> dict[str, object]:
        return {
            "element_identity": identity,
            "label": "details",
            "probe": "details",
            "tag_name": "button",
            "inside_main": True,
            "visible": True,
            "actionable": True,
        }

    results = [
        browser_detail._candidate_action_label(
            candidate(identity),
            selector="button",
            requested_fields=None,
            requested_keywords=(),
            keywords=("details",),
            seen_candidates=seen_candidates,
        )[0]
        for identity in ("node-1", "node-2", "node-1")
    ]

    assert results == [True, True, False]


@pytest.mark.regression
def test_rejected_candidate_remains_available_to_later_selector() -> None:
    seen_candidates: set[tuple[str, str, str]] = set()
    snapshot = {
        "element_identity": "node-1",
        "label": "mystery",
        "probe": "mystery",
        "tag_name": "button",
        "inside_main": True,
        "visible": True,
        "actionable": True,
    }

    rejected = browser_detail._candidate_action_label(
        snapshot,
        selector="div",
        requested_fields=None,
        requested_keywords=(),
        keywords=("details",),
        seen_candidates=seen_candidates,
    )[0]
    accepted = browser_detail._candidate_action_label(
        snapshot,
        selector="button[aria-controls]",
        requested_fields=None,
        requested_keywords=(),
        keywords=("details",),
        seen_candidates=seen_candidates,
    )[0]

    assert rejected is False
    assert accepted is True


@pytest.mark.regression
def test_dom_expansion_diagnostics_report_effective_interaction_limit(
    patch_settings,
) -> None:
    patch_settings(
        detail_expand_max_interactions=5,
        accordion_expand_max=2,
    )

    state = browser_detail._new_dom_expansion_state(
        started_at=0.0,
        max_elapsed_ms=None,
        elapsed_ms=lambda _started_at: 0,
    )

    assert state.max_interactions == 2
    assert state.diagnostics["limit"] == 2


@pytest.mark.regression
def test_detail_expansion_skip_requires_extractable_ecommerce_content() -> None:
    can_skip, reason = browser_page_helpers.detail_expansion_can_skip(
        {"verified": False, "matched_requested_fields": []},
        surface="ecommerce_detail",
        requested_fields=None,
        readiness_probe={"is_ready": True},
    )

    assert can_skip is False
    assert reason is None


@pytest.mark.regression
def test_detail_expansion_skip_does_not_trust_sparse_structured_data_alone() -> None:
    readiness_probe = {
        "is_ready": True,
        "structured_data_present": True,
        "visible_text_length": 1,
        "detail_hint_count": 0,
        "h1_present": False,
    }

    unverified = browser_page_helpers.detail_expansion_can_skip(
        {"verified": False, "matched_requested_fields": []},
        surface="ecommerce_detail",
        requested_fields=None,
        readiness_probe=readiness_probe,
    )
    verified = browser_page_helpers.detail_expansion_can_skip(
        {"verified": True, "matched_requested_fields": []},
        surface="ecommerce_detail",
        requested_fields=None,
        readiness_probe=readiness_probe,
    )

    assert unverified == (False, None)
    assert verified == (True, "canonical_detail_already_ready")


@pytest.mark.regression
def test_detail_expansion_skip_does_not_trust_sparse_detail_hints_alone() -> None:
    can_skip, reason = browser_page_helpers.detail_expansion_can_skip(
        {"verified": False, "matched_requested_fields": []},
        surface="ecommerce_detail",
        requested_fields=None,
        readiness_probe={
            "is_ready": True,
            "structured_data_present": False,
            "visible_text_length": 1,
            "detail_hint_count": int(
                crawler_runtime_settings.detail_field_signal_min_count
            ),
            "h1_present": False,
        },
    )

    assert can_skip is False
    assert reason is None

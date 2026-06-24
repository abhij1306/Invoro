from __future__ import annotations

import pytest

from app.services.config import aid_score as config
from app.services.ucp_audit.repair_roadmap import build_repair_roadmap
from app.services.ucp_audit.types import UCPFinding


@pytest.mark.unit
def test_repair_roadmap_preserves_evidence_and_dependency_order() -> None:
    findings = [
        UCPFinding(
            code=config.FINDING_AID3_OFFER_MISSING,
            dimension_id=config.D_AID3_ID,
            severity=config.AID_FINDING_BLOCKING,
            evidence=[{"url": "https://example.com/product"}],
        ),
        UCPFinding(
            code=config.FINDING_AID1_SCHEMA_INVALID,
            dimension_id=config.D_AID1_ID,
            severity=config.AID_FINDING_WARNING,
            evidence=[{"errors": ["invalid JSON-LD"]}],
        ),
    ]

    roadmap = build_repair_roadmap(findings, domain="example.com")

    assert [item.sub_skill for item in roadmap] == ["structured markup", "commerce signals"]
    assert roadmap[0].evidence == findings[1].evidence
    assert roadmap[0].effort == "2 hours"
    assert roadmap[1].depends_on == ["structured markup", "catalog completeness"]


@pytest.mark.unit
def test_no_shopify_advisory_for_aid_score() -> None:
    roadmap = build_repair_roadmap([], domain="store.myshopify.com")

    assert roadmap == []


@pytest.mark.unit
def test_repair_roadmap_action_surfaces_schema_errors() -> None:
    roadmap = build_repair_roadmap(
        [
            UCPFinding(
                code=config.FINDING_AID1_SCHEMA_INVALID,
                dimension_id=config.D_AID1_ID,
                severity=config.AID_FINDING_WARNING,
                evidence=[{"errors": ["Unexpected token"]}],
            )
        ],
        domain="example.com",
    )

    assert "Unexpected token" in roadmap[0].action


@pytest.mark.unit
def test_repair_roadmap_ignores_non_mapping_evidence_for_action_details() -> None:
    roadmap = build_repair_roadmap(
        [
            UCPFinding(
                code=config.FINDING_AID1_SCHEMA_INVALID,
                dimension_id=config.D_AID1_ID,
                severity=config.AID_FINDING_WARNING,
                evidence=["invalid json"],
            )
        ],
        domain="example.com",
    )

    assert roadmap[0].sub_skill == "structured markup"

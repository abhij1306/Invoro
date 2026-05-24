from __future__ import annotations

from app.services.config import ucp_audit as config
from app.services.ucp_audit.repair_roadmap import build_repair_roadmap
from app.services.ucp_audit.types import UCPFinding


def test_repair_roadmap_preserves_evidence_and_dependency_order() -> None:
    findings = [
        UCPFinding(
            code=config.FINDING_TRANSPORT_UNREACHABLE,
            dimension_id=config.D_UCP3_ID,
            severity=config.UCP_FINDING_BLOCKING,
            evidence=[{"endpoint": "https://example.com/ucp"}],
        ),
        UCPFinding(
            code=config.FINDING_MANIFEST_INVALID,
            dimension_id=config.D_UCP1_ID,
            severity=config.UCP_FINDING_BLOCKING,
            evidence=[{"errors": ["Missing required array: signing_keys"]}],
        ),
    ]

    roadmap = build_repair_roadmap(findings, domain="example.com")

    assert [item.sub_skill for item in roadmap] == ["discovery", "transport"]
    assert roadmap[0].evidence == findings[1].evidence
    assert roadmap[0].effort == "2 hours"
    assert roadmap[1].depends_on == ["discovery", "capabilities"]


def test_shopify_advisory_is_conditional() -> None:
    no_findings = build_repair_roadmap([], domain="example.com")
    shopify = build_repair_roadmap([], domain="store.myshopify.com")
    cart_gap = build_repair_roadmap(
        [
            UCPFinding(
                code=config.FINDING_CART_CHECKOUT_CONTRACT_MISSING,
                dimension_id=config.D_UCP5_ID,
                severity=config.UCP_FINDING_WARNING,
            )
        ],
        domain="example.com",
    )

    assert no_findings == []
    assert shopify[-1].sub_skill == "shop-skill advisory"
    assert cart_gap[-1].sub_skill == "shop-skill advisory"

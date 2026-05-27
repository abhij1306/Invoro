from __future__ import annotations

import pytest

from app.services.config import aid_score as config
from app.services.ucp_audit.reporting import build_markdown_report
from app.services.ucp_audit.types import (
    UCPComplianceReport,
    UCPDimensionScore,
    UCPFinding,
    UCPRepairRoadmapItem,
)


@pytest.mark.unit
def test_markdown_report_includes_aid_gate_max_score() -> None:
    report = UCPComplianceReport(
        domain="example.com",
        audit_id="audit-1",
        overall_score=30,
        dimension_scores=[
            UCPDimensionScore(
                dimension_id=config.D_AID2_ID,
                score=80,
                status="warning",
                findings=[],
                weight=0.25,
            )
        ],
        all_findings=[
            UCPFinding(
                code=config.FINDING_AID2_PRICE_MISSING,
                dimension_id=config.D_AID2_ID,
                severity=config.AID_FINDING_BLOCKING,
                message="Product price is missing on sampled pages.",
                affected_count=1,
                affected_urls=["https://example.com/p/1"],
                evidence=[{"field": "price"}],
            )
        ],
        d_ucp1_gate_applied=True,
        d_ucp3_gate_applied=False,
        ucp_contract={
            "catalog": {
                "pages_crawled": 2,
                "sampled_urls": ["https://example.com", "https://example.com/p/1"],
            },
            "structured_markup": {
                "product_jsonld_count": 1,
                "jsonld_parse_errors": [],
            },
            "discovery": {"sitemap_found": True},
            "product_records": [
                {
                    "source_url": "https://example.com/p/1",
                    "title": "Widget",
                    "price": "100",
                    "variant_count": 2,
                    "rating": 4.8,
                }
            ],
        },
        repair_roadmap=[
            UCPRepairRoadmapItem(
                sub_skill="catalog completeness",
                priority="high",
                finding_codes=[config.FINDING_AID2_PRICE_MISSING],
                action="Expose current product prices.",
                source="AI Discoverability Score guidance",
                evidence=[{"field": "price"}],
                effort="2 hours",
            )
        ],
    )

    markdown = build_markdown_report(report)

    assert "# AI Discoverability Audit Report: example\\.com" in markdown
    assert f"D-AID1 gate max score: {config.D_AID1_GATE_MAX_SCORE}" in markdown
    assert "D-UCP3 gate max score" not in markdown
    assert "Reliability rule: uncertain or insufficient-evidence signals are excluded" in markdown
    assert "| D-AID2 | 80 | warning | 0 |" in markdown
    assert "https://example\\.com/p/1" in markdown
    assert "Expose current product prices" in markdown

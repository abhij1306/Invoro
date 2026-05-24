from __future__ import annotations

from app.services.config import ucp_audit as config
from app.services.ucp_audit.reporting import build_markdown_report
from app.services.ucp_audit.types import UCPComplianceReport


def test_markdown_report_includes_transport_gate_max_score() -> None:
    report = UCPComplianceReport(
        domain="example.com",
        audit_id="audit-1",
        overall_score=45,
        dimension_scores=[],
        all_findings=[],
        d_ucp1_gate_applied=False,
        d_ucp3_gate_applied=True,
        ucp_contract={},
        repair_roadmap=[],
    )

    markdown = build_markdown_report(report)

    assert f"D-UCP3 gate max score: {config.D_UCP3_GATE_MAX_SCORE}" in markdown

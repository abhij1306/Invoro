from __future__ import annotations

from app.services.config import ucp_audit as config
from app.services.ucp_audit.repair_roadmap import build_repair_roadmap
from app.services.ucp_audit.types import UCPComplianceReport, UCPDimensionScore


def build_compliance_report(
    *,
    domain: str,
    audit_id: str,
    dimension_scores: list[UCPDimensionScore],
    ucp_contract: dict,
) -> UCPComplianceReport:
    weighted = sum(item.score * item.weight for item in dimension_scores)
    overall = int(weighted)
    d_ucp1_gate_applied = False
    d_ucp3_gate_applied = False
    discovery = next(
        (item for item in dimension_scores if item.dimension_id == config.D_UCP1_ID),
        None,
    )
    if discovery is None:
        raise ValueError(f"Missing required dimension score: {config.D_UCP1_ID}")
    if discovery.score == 0:
        overall = min(overall, config.D_UCP1_GATE_MAX_SCORE)
        d_ucp1_gate_applied = True
    transport = next(
        (item for item in dimension_scores if item.dimension_id == config.D_UCP3_ID),
        None,
    )
    if transport is not None and transport.score == 0:
        overall = min(overall, config.D_UCP3_GATE_MAX_SCORE)
        d_ucp3_gate_applied = True
    findings = [
        finding
        for dimension in dimension_scores
        for finding in dimension.findings or []
    ]
    return UCPComplianceReport(
        domain=domain,
        audit_id=audit_id,
        overall_score=overall,
        dimension_scores=dimension_scores,
        all_findings=findings,
        d_ucp1_gate_applied=d_ucp1_gate_applied,
        d_ucp3_gate_applied=d_ucp3_gate_applied,
        ucp_contract=ucp_contract,
        repair_roadmap=build_repair_roadmap(findings, domain=domain),
    )

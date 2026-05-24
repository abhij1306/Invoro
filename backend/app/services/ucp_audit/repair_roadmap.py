from __future__ import annotations

from app.services.config import ucp_audit as config
from app.services.ucp_audit.types import UCPFinding, UCPRepairRoadmapItem

_SUB_SKILL_BY_DIMENSION = {
    config.D_UCP1_ID: "discovery",
    config.D_UCP2_ID: "capabilities",
    config.D_UCP3_ID: "transport",
    config.D_UCP4_ID: "catalog",
    config.D_UCP5_ID: "cart/checkout",
    config.D_UCP6_ID: "order/fulfillment",
}

_ACTION_BY_CODE = {
    config.FINDING_MANIFEST_MISSING: "Publish /.well-known/ucp with a UCP shopping profile.",
    config.FINDING_MANIFEST_INVALID: "Fix the UCP profile shape and declare dev.ucp.shopping.",
    config.FINDING_SERVICE_MISSING: "Declare dev.ucp.shopping in the UCP services map.",
    config.FINDING_CAPABILITY_MISSING: "Declare all required shopping capabilities.",
    config.FINDING_TRANSPORT_MISSING: "Expose a REST, MCP, or embedded UCP transport.",
    config.FINDING_TRANSPORT_NEGOTIATION_INCOMPLETE: (
        "Complete MCP/REST negotiation or publish the required agent profile contract."
    ),
    config.FINDING_SCHEMA_MISSING: "Attach schema URLs for UCP payload contracts.",
    config.FINDING_SCHEMA_UNREACHABLE: "Make declared schema URLs reachable as JSON.",
    config.FINDING_CATALOG_CONTRACT_MISSING: (
        "Expose catalog search and lookup schemas or tools with product and variant payloads."
    ),
    config.FINDING_CART_CHECKOUT_CONTRACT_MISSING: (
        "Expose cart and checkout schemas or tools without relying on rendered storefront UI."
    ),
    config.FINDING_ORDER_POLICY_CONTRACT_MISSING: (
        "Expose order, fulfillment, discount, return, and policy payload schemas."
    ),
    config.FINDING_PAYMENT_HANDLER_MISSING: "Declare at least one UCP payment handler.",
}


def build_repair_roadmap(findings: list[UCPFinding]) -> list[UCPRepairRoadmapItem]:
    items = [
        UCPRepairRoadmapItem(
            sub_skill=_SUB_SKILL_BY_DIMENSION.get(finding.dimension_id, "ucp"),
            priority=_priority(finding),
            finding_codes=[finding.code],
            action=_ACTION_BY_CODE.get(finding.code, finding.message or finding.code),
            source="UCP Overview and UCP Schema Reference",
        )
        for finding in findings
    ]
    items.append(
        UCPRepairRoadmapItem(
            sub_skill="shop-skill advisory",
            priority="low",
            finding_codes=[],
            action=(
                "Use https://shop.app/SKILL.md as Shopify repair guidance for catalog "
                "search and checkout affordances; do not count it as UCP compliance."
            ),
            source="https://shop.app/SKILL.md",
        )
    )
    return items


def _priority(finding: UCPFinding) -> str:
    if finding.severity == config.UCP_FINDING_BLOCKING:
        return "critical"
    if finding.dimension_id in {config.D_UCP2_ID, config.D_UCP3_ID}:
        return "high"
    return "medium"

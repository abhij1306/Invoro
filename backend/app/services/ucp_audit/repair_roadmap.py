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
    config.FINDING_MANIFEST_CONTENT_TYPE_INVALID: "Serve the UCP profile with a JSON content type.",
    config.FINDING_MANIFEST_REDIRECTED: "Serve the canonical well-known UCP path without redirects.",
    config.FINDING_SIGNING_KEYS_MISSING: (
        "Add a signing_keys array at the top level of /.well-known/ucp with at least one "
        "EC or RSA JWK public key. Required fields per JWK spec: kty, kid, alg, use='sig'. "
        "Used for webhook signature verification per RFC 7797."
    ),
    config.FINDING_CACHE_CONTROL_MISSING: (
        "Add 'Cache-Control: public, max-age=300' (or higher) to the /.well-known/ucp "
        "response. The UCP spec requires at least 60 seconds to allow platforms to cache the profile."
    ),
    config.FINDING_SERVICE_MISSING: "Declare dev.ucp.shopping in the UCP services map.",
    config.FINDING_SERVICE_INVALID: "Fix malformed UCP service entries and declare valid versions.",
    config.FINDING_CAPABILITY_MISSING: "Declare all required shopping capabilities.",
    config.FINDING_CAPABILITY_INVALID: "Fix malformed UCP capability entries and declare valid versions.",
    config.FINDING_CAPABILITY_VERSION_MISMATCH: (
        "Align capability versions with the declared dev.ucp.shopping service version."
    ),
    config.FINDING_TRANSPORT_MISSING: "Expose a REST, MCP, or embedded UCP transport.",
    config.FINDING_TRANSPORT_UNREACHABLE: "Make at least one declared UCP transport reachable.",
    config.FINDING_TRANSPORT_NEGOTIATION_INCOMPLETE: (
        "Complete MCP/REST negotiation or publish the required agent profile contract."
    ),
    config.FINDING_SCHEMA_MISSING: "Attach schema URLs for UCP payload contracts.",
    config.FINDING_SCHEMA_UNREACHABLE: "Make declared schema URLs reachable as JSON.",
    config.FINDING_SCHEMA_FIELD_MISSING: "Add required UCP fields to declared JSON schemas.",
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

_EFFORT_BY_CODE = {
    config.FINDING_MANIFEST_MISSING: "1 hour",
    config.FINDING_MANIFEST_INVALID: "2 hours",
    config.FINDING_MANIFEST_CONTENT_TYPE_INVALID: "1 hour",
    config.FINDING_MANIFEST_REDIRECTED: "1 hour",
    config.FINDING_SIGNING_KEYS_MISSING: "2-4 hours",
    config.FINDING_CACHE_CONTROL_MISSING: "1 hour",
    config.FINDING_SERVICE_MISSING: "1 hour",
    config.FINDING_SERVICE_INVALID: "2 hours",
    config.FINDING_CAPABILITY_MISSING: "2-4 hours",
    config.FINDING_CAPABILITY_INVALID: "2 hours",
    config.FINDING_CAPABILITY_VERSION_MISMATCH: "2 hours",
    config.FINDING_TRANSPORT_MISSING: "1 sprint",
    config.FINDING_TRANSPORT_UNREACHABLE: "1 sprint",
    config.FINDING_TRANSPORT_NEGOTIATION_INCOMPLETE: "1 sprint",
    config.FINDING_SCHEMA_MISSING: "2 hours",
    config.FINDING_SCHEMA_UNREACHABLE: "2 hours",
    config.FINDING_SCHEMA_FIELD_MISSING: "1 sprint",
    config.FINDING_CATALOG_CONTRACT_MISSING: "1 sprint",
    config.FINDING_CART_CHECKOUT_CONTRACT_MISSING: "1 sprint",
    config.FINDING_ORDER_POLICY_CONTRACT_MISSING: "1 sprint",
    config.FINDING_PAYMENT_HANDLER_MISSING: "2-4 hours",
}

_DIMENSION_ORDER = {
    config.D_UCP1_ID: 0,
    config.D_UCP2_ID: 1,
    config.D_UCP3_ID: 2,
    config.D_UCP4_ID: 3,
    config.D_UCP5_ID: 4,
    config.D_UCP6_ID: 5,
}

_DEPENDS_ON_BY_DIMENSION = {
    config.D_UCP2_ID: ["discovery"],
    config.D_UCP3_ID: ["discovery", "capabilities"],
    config.D_UCP4_ID: ["discovery", "capabilities", "transport"],
    config.D_UCP5_ID: ["discovery", "capabilities", "transport"],
    config.D_UCP6_ID: ["discovery", "capabilities", "transport"],
}

def build_repair_roadmap(
    findings: list[UCPFinding],
    *,
    domain: str = "",
) -> list[UCPRepairRoadmapItem]:
    sorted_findings = sorted(
        findings,
        key=lambda item: (
            _DIMENSION_ORDER.get(item.dimension_id, 99),
            _priority_order(_priority(item)),
            item.code,
        ),
    )
    items = [
        UCPRepairRoadmapItem(
            sub_skill=_SUB_SKILL_BY_DIMENSION.get(finding.dimension_id, "ucp"),
            priority=_priority(finding),
            finding_codes=[finding.code],
            action=_action_for(finding),
            source="UCP Overview and UCP Schema Reference",
            evidence=finding.evidence,
            effort=_EFFORT_BY_CODE.get(finding.code, "review"),
            depends_on=_DEPENDS_ON_BY_DIMENSION.get(finding.dimension_id, []),
        )
        for finding in sorted_findings
    ]
    if _should_include_shopify_advisory(domain, findings):
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
                effort="review",
                depends_on=["cart/checkout"],
            )
        )
    return items


def _action_for(finding: UCPFinding) -> str:
    base = _ACTION_BY_CODE.get(finding.code, finding.message or finding.code)
    if finding.evidence:
        first = finding.evidence[0]
        errors = first.get("errors") if isinstance(first, dict) else []
        if errors and finding.code in {
            config.FINDING_MANIFEST_INVALID,
            config.FINDING_SIGNING_KEYS_MISSING,
            config.FINDING_SERVICE_INVALID,
            config.FINDING_CAPABILITY_INVALID,
        }:
            detail = "; ".join(str(error) for error in errors[:3])
            return f"{base} Errors: {detail}"
    return base


def _priority(finding: UCPFinding) -> str:
    if finding.severity == config.UCP_FINDING_BLOCKING:
        return "critical"
    if finding.dimension_id in {config.D_UCP2_ID, config.D_UCP3_ID}:
        return "high"
    return "medium"


def _priority_order(priority: str) -> int:
    return {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(priority, 9)


def _should_include_shopify_advisory(domain: str, findings: list[UCPFinding]) -> bool:
    normalized = str(domain or "").lower()
    if "shopify" in normalized or "myshopify" in normalized:
        return True
    return any(finding.dimension_id == config.D_UCP5_ID for finding in findings)

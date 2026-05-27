from __future__ import annotations

from app.services.config import aid_score as config
from app.services.ucp_audit.types import UCPFinding, UCPRepairRoadmapItem

_SUB_SKILL_BY_DIMENSION = {
    config.D_AID1_ID: "structured markup",
    config.D_AID2_ID: "catalog completeness",
    config.D_AID3_ID: "commerce signals",
    config.D_AID4_ID: "freshness availability",
    config.D_AID5_ID: "trust proof",
    config.D_AID6_ID: "local discovery",
}

_ACTION_BY_CODE = {
    config.FINDING_AID1_JSONLD_MISSING: "Add Product JSON-LD to sampled product pages.",
    config.FINDING_AID1_PRODUCT_TYPE_MISSING: "Declare schema.org Product in JSON-LD.",
    config.FINDING_AID1_OPEN_GRAPH_MISSING: "Add Open Graph product metadata.",
    config.FINDING_AID1_SCHEMA_INVALID: "Fix malformed JSON-LD blocks.",
    config.FINDING_AID2_TITLE_MISSING: "Populate product titles in structured and visible page data.",
    config.FINDING_AID2_PRICE_MISSING: "Expose current product price in structured data and visible page data.",
    config.FINDING_AID2_DESCRIPTION_SHORT: "Add useful product descriptions of at least 100 characters.",
    config.FINDING_AID2_IMAGES_MISSING: "Expose primary product images in markup and extraction output.",
    config.FINDING_AID2_VARIANTS_MISSING: "Expose available size, color, or variant options.",
    config.FINDING_AID2_IDENTIFIERS_MISSING: "Add SKU, GTIN, MPN, or stable product identifiers.",
    config.FINDING_AID3_OFFER_MISSING: "Add schema.org Offer blocks with price and currency.",
    config.FINDING_AID3_PAYMENT_METHODS_MISSING: "Expose payment method signals on product or policy pages.",
    config.FINDING_AID3_EMI_SIGNAL_MISSING: "Expose EMI or installment payment information when supported.",
    config.FINDING_AID3_DELIVERY_ETA_MISSING: "Add delivery or shipping ETA signals.",
    config.FINDING_AID3_RETURN_POLICY_MISSING: "Add return and refund policy signals.",
    config.FINDING_AID4_AVAILABILITY_MISSING: "Add schema.org availability to offers.",
    config.FINDING_AID4_PRICE_STALE: "Keep structured prices aligned with visible DOM prices.",
    config.FINDING_AID4_OUT_OF_STOCK_RATE_HIGH: "Add alternative recommendations or improve stock exposure for unavailable products.",
    config.FINDING_AID5_RATING_MISSING: "Add aggregateRating structured data where review data exists.",
    config.FINDING_AID5_REVIEW_COUNT_ZERO: "Ensure aggregateRating includes a non-zero review count when ratings are shown.",
    config.FINDING_AID5_REVIEW_SCHEMA_INVALID: "Fix malformed review markup.",
    config.FINDING_AID6_LOCAL_BUSINESS_MISSING: "Add LocalBusiness markup when the merchant has stores or service areas.",
    config.FINDING_AID6_ROBOTS_BLOCKING_AI: "Review robots.txt rules that block AI crawlers.",
    config.FINDING_AID6_SITEMAP_MISSING: "Publish sitemap.xml or expose a sitemap index.",
}

_EFFORT_ONE_HOUR = "1 hour"
_EFFORT_TWO_HOURS = "2 hours"
_EFFORT_TWO_TO_FOUR_HOURS = "2-4 hours"
_EFFORT_ONE_SPRINT = "1 sprint"

_EFFORT_BY_CODE = {
    config.FINDING_AID1_JSONLD_MISSING: _EFFORT_TWO_HOURS,
    config.FINDING_AID1_PRODUCT_TYPE_MISSING: _EFFORT_ONE_HOUR,
    config.FINDING_AID1_OPEN_GRAPH_MISSING: _EFFORT_ONE_HOUR,
    config.FINDING_AID1_SCHEMA_INVALID: _EFFORT_TWO_HOURS,
    config.FINDING_AID2_TITLE_MISSING: _EFFORT_ONE_HOUR,
    config.FINDING_AID2_PRICE_MISSING: _EFFORT_TWO_HOURS,
    config.FINDING_AID2_DESCRIPTION_SHORT: _EFFORT_TWO_TO_FOUR_HOURS,
    config.FINDING_AID2_IMAGES_MISSING: _EFFORT_TWO_HOURS,
    config.FINDING_AID2_VARIANTS_MISSING: _EFFORT_ONE_SPRINT,
    config.FINDING_AID2_IDENTIFIERS_MISSING: _EFFORT_TWO_TO_FOUR_HOURS,
    config.FINDING_AID3_OFFER_MISSING: _EFFORT_TWO_HOURS,
    config.FINDING_AID3_PAYMENT_METHODS_MISSING: _EFFORT_TWO_TO_FOUR_HOURS,
    config.FINDING_AID3_EMI_SIGNAL_MISSING: _EFFORT_TWO_TO_FOUR_HOURS,
    config.FINDING_AID3_DELIVERY_ETA_MISSING: _EFFORT_TWO_HOURS,
    config.FINDING_AID3_RETURN_POLICY_MISSING: _EFFORT_TWO_HOURS,
    config.FINDING_AID4_AVAILABILITY_MISSING: _EFFORT_TWO_HOURS,
    config.FINDING_AID4_PRICE_STALE: _EFFORT_TWO_HOURS,
    config.FINDING_AID4_OUT_OF_STOCK_RATE_HIGH: _EFFORT_ONE_SPRINT,
    config.FINDING_AID5_RATING_MISSING: _EFFORT_TWO_TO_FOUR_HOURS,
    config.FINDING_AID5_REVIEW_COUNT_ZERO: _EFFORT_ONE_HOUR,
    config.FINDING_AID5_REVIEW_SCHEMA_INVALID: _EFFORT_TWO_HOURS,
    config.FINDING_AID6_LOCAL_BUSINESS_MISSING: _EFFORT_TWO_HOURS,
    config.FINDING_AID6_ROBOTS_BLOCKING_AI: _EFFORT_ONE_HOUR,
    config.FINDING_AID6_SITEMAP_MISSING: _EFFORT_ONE_HOUR,
}

_DIMENSION_ORDER = {
    config.D_AID1_ID: 0,
    config.D_AID2_ID: 1,
    config.D_AID3_ID: 2,
    config.D_AID4_ID: 3,
    config.D_AID5_ID: 4,
    config.D_AID6_ID: 5,
}

_DEPENDS_ON_BY_DIMENSION = {
    config.D_AID2_ID: ["structured markup"],
    config.D_AID3_ID: ["structured markup", "catalog completeness"],
    config.D_AID4_ID: ["structured markup", "catalog completeness"],
    config.D_AID5_ID: ["structured markup"],
    config.D_AID6_ID: [],
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
            source="AI Discoverability Score guidance",
            evidence=finding.evidence,
            effort=_EFFORT_BY_CODE.get(finding.code, "review"),
            depends_on=_DEPENDS_ON_BY_DIMENSION.get(finding.dimension_id, []),
        )
        for finding in sorted_findings
    ]
    return items


def _action_for(finding: UCPFinding) -> str:
    base = _ACTION_BY_CODE.get(finding.code, finding.message or finding.code)
    if finding.evidence:
        first = finding.evidence[0]
        errors = first.get("errors") if isinstance(first, dict) else []
        if errors and finding.code in {config.FINDING_AID1_SCHEMA_INVALID}:
            detail = "; ".join(str(error) for error in errors[:3])
            return f"{base} Errors: {detail}"
    return base


def _priority(finding: UCPFinding) -> str:
    if finding.severity == config.AID_FINDING_BLOCKING:
        return "critical"
    if finding.dimension_id in {config.D_AID2_ID, config.D_AID3_ID, config.D_AID4_ID}:
        return "high"
    return "medium"


def _priority_order(priority: str) -> int:
    return {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(priority, 9)

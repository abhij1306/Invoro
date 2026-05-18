from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class UCPManifestResult:
    manifest_found: bool
    capabilities_declared: list[str]
    missing_required_capabilities: list[str]
    manifest_valid: bool
    raw_manifest: dict | None
    errors: list[str]


@dataclass(slots=True)
class UCPSchemaScore:
    url: str
    product_jsonld_found: bool
    required_fields_present: list[str]
    recommended_fields_present: list[str]
    ucp_fields_present: list[str]
    completeness_score: int
    missing_required: list[str]
    missing_recommended: list[str]
    raw_additional_properties: list[dict]
    raw_product_type: str | None
    raw_offers: list[dict]


@dataclass(slots=True)
class MetafieldCoverageReport:
    total_sampled: int
    coverage_by_attribute: dict[str, float]
    critical_gaps: list[str]
    worst_product_types: list[str]


@dataclass(slots=True)
class TaxonomyConsistencyReport:
    unique_raw_values: list[str]
    duplicate_clusters: list[list[str]]
    shallow_categories: list[str]
    consistency_score: int


@dataclass(slots=True)
class UCPFinding:
    code: str
    dimension_id: str
    severity: str
    message: str = ""
    affected_count: int = 0


@dataclass(slots=True)
class VariantFidelityReport:
    products_with_variants_sampled: int
    collapsed_offers_count: int
    missing_sku_count: int
    missing_availability_count: int
    fidelity_score: int
    findings: list[UCPFinding]


@dataclass(slots=True)
class PolicyReadabilityReport:
    structured_shipping_found: bool
    return_period_machine_readable: bool
    currency_is_iso4217: bool
    policy_page_http_accessible: bool
    readability_score: int
    findings: list[UCPFinding]


@dataclass(slots=True)
class AgentViewDelta:
    url: str
    agent_extracted: dict[str, Any]
    human_visible: dict[str, Any]
    missing_in_agent_view: list[str]
    agent_only_signals: list[str]
    fidelity_score: float


@dataclass(slots=True)
class UCPDimensionScore:
    dimension_id: str
    score: int
    status: str
    findings: list[UCPFinding] = field(default_factory=list)
    weight: float = 0.0


@dataclass(slots=True)
class UCPComplianceReport:
    domain: str
    audit_id: str
    overall_score: int
    dimension_scores: list[UCPDimensionScore]
    all_findings: list[UCPFinding]
    d_ucp1_gate_applied: bool

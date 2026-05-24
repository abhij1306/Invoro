from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class UCPManifestResult:
    manifest_found: bool = False
    manifest_valid: bool = False
    capabilities_declared: list[str] = field(default_factory=list)
    missing_required_capabilities: list[str] = field(default_factory=list)
    services_declared: list[str] = field(default_factory=list)
    missing_required_services: list[str] = field(default_factory=list)
    service_entries: list[dict[str, Any]] = field(default_factory=list)
    capability_entries: list[dict[str, Any]] = field(default_factory=list)
    transport_entries: list[dict[str, Any]] = field(default_factory=list)
    schema_urls: list[str] = field(default_factory=list)
    payment_handlers: list[str] = field(default_factory=list)
    raw_manifest: dict[str, Any] | None = None
    errors: list[str] = field(default_factory=list)


@dataclass(slots=True)
class UCPTransportProbe:
    service: str
    transport: str
    endpoint: str = ""
    reachable: bool = False
    negotiated: bool = False
    profile_required: bool = False
    status_code: int = 0
    error: str = ""
    tool_names: list[str] = field(default_factory=list)
    tool_schemas: list[dict[str, Any]] = field(default_factory=list)
    response_preview: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class UCPSchemaProbe:
    url: str
    reachable: bool = False
    valid_json: bool = False
    title: str = ""
    error: str = ""


@dataclass(slots=True)
class UCPRepairRoadmapItem:
    sub_skill: str
    priority: str
    finding_codes: list[str]
    action: str
    source: str


@dataclass(slots=True)
class UCPFinding:
    code: str
    dimension_id: str
    severity: str
    message: str = ""
    affected_count: int = 0
    count_kind: str = "items"
    affected_urls: list[str] = field(default_factory=list)
    evidence: list[dict[str, Any]] = field(default_factory=list)


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
    ucp_contract: dict[str, Any] = field(default_factory=dict)
    repair_roadmap: list[UCPRepairRoadmapItem] = field(default_factory=list)

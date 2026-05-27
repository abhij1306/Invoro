from __future__ import annotations

from dataclasses import asdict
from typing import Any, Iterable, Literal

from app.services.config import aid_score as config
from app.services.ucp_audit.types import UCPComplianceReport

_MARKDOWN_SPECIAL_CHARS = "\\`*_{}[]()#+-.!"
# Keep `-` safe for bullet text, but still escape `.` so values like `1. foo`
# do not accidentally render as ordered lists; see the selective markdown tests.
_MARKDOWN_SELECTIVE_SAFE_CHARS = frozenset({"-"})


def escape_markdown(
    value: object,
    *,
    mode: Literal["full", "selective"] = "full",
    safe_chars: Iterable[str] | None = None,
) -> str:
    text = str(value)
    safe = set(safe_chars or ())
    if mode == "selective":
        safe.update(_MARKDOWN_SELECTIVE_SAFE_CHARS)
    return "".join(
        f"\\{char}" if char in _MARKDOWN_SPECIAL_CHARS and char not in safe else char
        for char in text
    )


def build_report_payload(report: UCPComplianceReport) -> dict[str, Any]:
    return {
        "domain": report.domain,
        "audit_id": report.audit_id,
        "overall_score": report.overall_score,
        "d_ucp1_gate_applied": report.d_ucp1_gate_applied,
        "d_ucp1_gate_max_score": config.D_AID1_GATE_MAX_SCORE,
        "d_ucp3_gate_applied": report.d_ucp3_gate_applied,
        "d_ucp3_gate_max_score": config.D_AID3_GATE_MAX_SCORE,
        "dimension_scores": [asdict(item) for item in report.dimension_scores],
        "findings": [asdict(item) for item in report.all_findings],
        "ucp_contract": report.ucp_contract,
        "repair_roadmap": [asdict(item) for item in report.repair_roadmap],
    }


def build_markdown_report(report: UCPComplianceReport) -> str:
    contract: dict[str, Any] = report.ucp_contract if isinstance(report.ucp_contract, dict) else {}
    catalog_raw = contract.get("catalog")
    structured_raw = contract.get("structured_markup")
    discovery_raw = contract.get("discovery")
    product_records_raw = contract.get("product_records")
    catalog: dict[str, Any] = catalog_raw if isinstance(catalog_raw, dict) else {}
    structured: dict[str, Any] = structured_raw if isinstance(structured_raw, dict) else {}
    discovery: dict[str, Any] = discovery_raw if isinstance(discovery_raw, dict) else {}
    product_records: list[Any] = product_records_raw if isinstance(product_records_raw, list) else []
    lines = [
        f"# AI Discoverability Audit Report: {escape_markdown(report.domain, mode='selective')}",
        "",
        "## Executive Summary",
        f"- Audit ID: {escape_markdown(report.audit_id, mode='selective')}",
        f"- Overall score: {escape_markdown(report.overall_score)}",
        f"- Pages crawled: {escape_markdown(catalog.get('pages_crawled', 0))}",
        f"- Product samples reviewed: {escape_markdown(len(product_records))}",
        f"- Finding count: {escape_markdown(len(report.all_findings))}",
        "- Reliability rule: uncertain or insufficient-evidence signals are excluded from findings.",
        "",
        "## Scope And Evidence",
        f"- Sampled URLs: {escape_markdown(len(catalog.get('sampled_urls') or []))}",
        f"- Product JSON-LD nodes: {escape_markdown(structured.get('product_jsonld_count', 0))}",
        f"- JSON-LD parse errors: {escape_markdown(len(structured.get('jsonld_parse_errors') or []))}",
        f"- Sitemap found: {escape_markdown(discovery.get('sitemap_found', False))}",
        "",
        "## Dimension Scores",
        "| Dimension | Score | Status | Findings |",
        "| --- | ---: | --- | ---: |",
    ]
    for dimension in report.dimension_scores:
        lines.append(
            "| "
            f"{escape_markdown(dimension.dimension_id, mode='selective')} | "
            f"{escape_markdown(dimension.score)} | "
            f"{escape_markdown(dimension.status)} | "
            f"{escape_markdown(len(dimension.findings or []))} |"
        )
    if report.d_ucp1_gate_applied:
        lines.extend(
            [
                "",
                "## Score Gate",
                f"- D-AID1 gate applied: {escape_markdown(report.d_ucp1_gate_applied)}",
                f"- D-AID1 gate max score: {escape_markdown(config.D_AID1_GATE_MAX_SCORE)}",
            ]
        )
    lines.extend(["", "## Findings"])
    if report.all_findings:
        for finding in report.all_findings:
            lines.extend(_finding_lines(finding))
    else:
        lines.append("- None")
    lines.extend(["", "## Product Sample Summary"])
    if product_records:
        lines.extend(_product_table(product_records))
    else:
        lines.append("- No product records were extracted from the audited sample.")
    lines.extend(["", "## Repair Roadmap"])
    if report.repair_roadmap:
        for index, item in enumerate(report.repair_roadmap, start=1):
            lines.extend(_roadmap_lines(index, item))
    else:
        lines.append("- No repair actions required from observed findings.")
    return "\n".join(lines) + "\n"


def _finding_lines(finding: Any) -> list[str]:
    lines = [
        f"### {escape_markdown(finding.dimension_id, mode='selective')} - {escape_markdown(finding.code, mode='selective')}",
        f"- Severity: {escape_markdown(finding.severity)}",
    ]
    if finding.message:
        lines.append(f"- Finding: {escape_markdown(finding.message, mode='selective')}")
    if finding.affected_count:
        lines.append(f"- Affected samples: {escape_markdown(finding.affected_count)}")
    if finding.affected_urls:
        lines.append("- Affected URLs:")
        lines.extend(f"  - {escape_markdown(url, mode='selective')}" for url in finding.affected_urls[:5])
    evidence = _evidence_lines(finding.evidence)
    if evidence:
        lines.append("- Evidence:")
        lines.extend(f"  - {line}" for line in evidence)
    lines.append("")
    return lines


def _roadmap_lines(index: int, item: Any) -> list[str]:
    lines = [
        f"{index}. {escape_markdown(item.action, mode='selective')}",
        f"   - Priority: {escape_markdown(item.priority)}",
        f"   - Effort: {escape_markdown(item.effort)}",
        f"   - Source: {escape_markdown(item.source, mode='selective')}",
    ]
    if item.finding_codes:
        codes = ", ".join(escape_markdown(code, mode="selective") for code in item.finding_codes)
        lines.append(f"   - Finding codes: {codes}")
    evidence = _evidence_lines(item.evidence)
    if evidence:
        lines.append("   - Evidence:")
        lines.extend(f"     - {line}" for line in evidence)
    return lines


def _product_table(records: list[Any]) -> list[str]:
    lines = [
        "| URL | Title | Price | Variants | Rating |",
        "| --- | --- | ---: | ---: | ---: |",
    ]
    for record in records[:10]:
        if not isinstance(record, dict):
            continue
        url = escape_markdown(_short_text(str(record.get("source_url") or record.get("url") or ""), 80), mode="selective")
        title = escape_markdown(_short_text(str(record.get("title") or record.get("name") or ""), 64), mode="selective")
        price = escape_markdown(str(record.get("price") or ""))
        variants = escape_markdown(str(record.get("variant_count") or len(record.get("variants") or [])))
        rating = escape_markdown(str(record.get("rating") or ""))
        lines.append(f"| {url} | {title} | {price} | {variants} | {rating} |")
    return lines


def _evidence_lines(evidence: list[dict[str, Any]]) -> list[str]:
    lines: list[str] = []
    for item in evidence or []:
        if not isinstance(item, dict):
            continue
        for key, value in item.items():
            if isinstance(value, list):
                value_text = ", ".join(_short_text(str(entry), 140) for entry in value[:5])
            else:
                value_text = _short_text(str(value), 180)
            lines.append(
                f"`{escape_markdown(key, mode='selective')}`: "
                f"{escape_markdown(value_text, mode='selective')}"
            )
    return lines[:12]


def _short_text(value: str, max_length: int) -> str:
    text = " ".join(str(value or "").split())
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3]}..."

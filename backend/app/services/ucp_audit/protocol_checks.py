from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict
from typing import Any

import httpx

from app.services.config import ucp_audit as config
from app.services.network_resolution import build_async_http_client
from app.services.ucp_audit.types import (
    UCPDimensionScore,
    UCPFinding,
    UCPManifestResult,
    UCPSchemaProbe,
    UCPTransportProbe,
)

logger = logging.getLogger(__name__)


async def probe_transports(manifest: UCPManifestResult) -> list[UCPTransportProbe]:
    probes: list[UCPTransportProbe] = []
    for entry in manifest.transport_entries:
        transport = str(entry.get("transport") or "").lower()
        endpoint = str(entry.get("endpoint") or "")
        service = str(entry.get("service") or "")
        if transport == "mcp" and endpoint:
            probes.append(await _probe_mcp(service=service, endpoint=endpoint))
            continue
        probes.append(
            UCPTransportProbe(
                service=service,
                transport=transport,
                endpoint=endpoint,
                reachable=bool(entry.get("schema")),
                negotiated=False,
                error="" if entry.get("schema") else "missing schema or endpoint",
            )
        )
    return probes


async def probe_schemas(schema_urls: list[str]) -> list[UCPSchemaProbe]:
    async def probe(url: str) -> UCPSchemaProbe:
        try:
            async with build_async_http_client(
                follow_redirects=True,
                timeout=config.UCP_SCHEMA_TIMEOUT_SECONDS,
            ) as client:
                response = await client.get(url)
            payload = response.json()
            return UCPSchemaProbe(
                url=url,
                reachable=response.status_code < 400,
                valid_json=isinstance(payload, dict),
                title=str(payload.get("title") or payload.get("$id") or ""),
            )
        except (json.JSONDecodeError, ValueError) as exc:
            return UCPSchemaProbe(url=url, reachable=True, valid_json=False, error=str(exc))
        except (httpx.HTTPError, OSError, TimeoutError, asyncio.TimeoutError) as exc:
            logger.debug("UCP schema probe failed for %s: %s", url, exc, exc_info=True)
            return UCPSchemaProbe(url=url, error=str(exc))

    return await asyncio.gather(*(probe(url) for url in schema_urls))


def build_contract_payload(
    manifest: UCPManifestResult,
    transport_probes: list[UCPTransportProbe],
    schema_probes: list[UCPSchemaProbe],
) -> dict[str, Any]:
    return {
        "manifest": {
            "found": manifest.manifest_found,
            "valid": manifest.manifest_valid,
            "errors": manifest.errors,
            "supported_versions": _supported_versions(manifest.raw_manifest or {}),
        },
        "services": manifest.services_declared,
        "capabilities": manifest.capabilities_declared,
        "missing_required_services": manifest.missing_required_services,
        "missing_required_capabilities": manifest.missing_required_capabilities,
        "transports": [asdict(item) for item in transport_probes],
        "schemas": [asdict(item) for item in schema_probes],
        "schema_urls": manifest.schema_urls,
        "payment_handlers": manifest.payment_handlers,
    }


def build_protocol_dimensions(
    manifest: UCPManifestResult,
    transport_probes: list[UCPTransportProbe],
    schema_probes: list[UCPSchemaProbe],
) -> list[UCPDimensionScore]:
    return [
        _discovery_dimension(manifest),
        _services_dimension(manifest),
        _transport_dimension(manifest, transport_probes),
        _catalog_dimension(manifest, schema_probes),
        _cart_checkout_dimension(manifest, schema_probes),
        _order_policy_dimension(manifest, schema_probes),
    ]


async def _probe_mcp(*, service: str, endpoint: str) -> UCPTransportProbe:
    body = {
        "jsonrpc": "2.0",
        "id": "ucp-audit-tools-list",
        "method": "tools/list",
        "params": {},
    }
    try:
        async with build_async_http_client(
            follow_redirects=True,
            timeout=config.UCP_TRANSPORT_TIMEOUT_SECONDS,
        ) as client:
            response = await client.post(endpoint, json=body)
        payload = _safe_json(response)
        error_text = json.dumps(payload.get("error", payload))[:500].lower()
        profile_required = "profile" in error_text and (
            "missing" in error_text or "invalid" in error_text or "required" in error_text
        )
        tools = _tool_entries(payload)
        return UCPTransportProbe(
            service=service,
            transport="mcp",
            endpoint=endpoint,
            reachable=response.status_code < 500,
            negotiated=response.status_code < 400 and not payload.get("error"),
            profile_required=profile_required,
            status_code=response.status_code,
            error="" if response.status_code < 400 else error_text[:240],
            tool_names=[str(item.get("name") or "") for item in tools if item.get("name")],
            tool_schemas=tools,
            response_preview=_preview(payload),
        )
    except (httpx.HTTPError, OSError, TimeoutError, asyncio.TimeoutError) as exc:
        logger.debug("UCP MCP probe failed for %s: %s", endpoint, exc, exc_info=True)
        return UCPTransportProbe(
            service=service,
            transport="mcp",
            endpoint=endpoint,
            error=str(exc),
        )


def _discovery_dimension(manifest: UCPManifestResult) -> UCPDimensionScore:
    findings: list[UCPFinding] = []
    if not manifest.manifest_found:
        findings.append(
            UCPFinding(
                code=config.FINDING_MANIFEST_MISSING,
                dimension_id=config.D_UCP1_ID,
                severity=config.UCP_FINDING_BLOCKING,
                message="UCP discovery profile was not found at /.well-known/ucp.",
            )
        )
        return _dimension(config.D_UCP1_ID, 0, findings)
    if not manifest.manifest_valid:
        findings.append(
            UCPFinding(
                code=config.FINDING_MANIFEST_INVALID,
                dimension_id=config.D_UCP1_ID,
                severity=config.UCP_FINDING_BLOCKING,
                message="UCP discovery profile exists but does not declare a valid shopping service.",
                evidence=[{"errors": manifest.errors}],
            )
        )
    return _dimension(config.D_UCP1_ID, 60 if findings else 100, findings)


def _services_dimension(manifest: UCPManifestResult) -> UCPDimensionScore:
    service_score = 40 if not manifest.missing_required_services else 0
    capability_score = _coverage_score(
        config.UCP_REQUIRED_CAPABILITIES,
        manifest.capabilities_declared,
        maximum=60,
    )
    findings: list[UCPFinding] = []
    if manifest.missing_required_services:
        findings.append(
            _missing_finding(
                config.FINDING_SERVICE_MISSING,
                config.D_UCP2_ID,
                manifest.missing_required_services,
                "Required UCP shopping service is not declared.",
            )
        )
    if manifest.missing_required_capabilities:
        findings.append(
            _missing_finding(
                config.FINDING_CAPABILITY_MISSING,
                config.D_UCP2_ID,
                manifest.missing_required_capabilities,
                "Required UCP shopping capabilities are not declared.",
            )
        )
    return _dimension(config.D_UCP2_ID, service_score + capability_score, findings)


def _transport_dimension(
    manifest: UCPManifestResult,
    transport_probes: list[UCPTransportProbe],
) -> UCPDimensionScore:
    if not manifest.transport_entries:
        return _dimension(
            config.D_UCP3_ID,
            0,
            [
                UCPFinding(
                    code=config.FINDING_TRANSPORT_MISSING,
                    dimension_id=config.D_UCP3_ID,
                    severity=config.UCP_FINDING_BLOCKING,
                    message="No REST, MCP, or embedded transport was declared.",
                )
            ],
        )
    scores = [_transport_probe_score(item) for item in transport_probes]
    findings = [
        UCPFinding(
            code=config.FINDING_TRANSPORT_NEGOTIATION_INCOMPLETE,
            dimension_id=config.D_UCP3_ID,
            severity=config.UCP_FINDING_WARNING,
            message="At least one transport is reachable but did not complete full negotiation.",
            evidence=[asdict(item) for item in transport_probes if not item.negotiated],
        )
    ] if any(not item.negotiated for item in transport_probes) else []
    return _dimension(config.D_UCP3_ID, _average(scores), findings)


def _catalog_dimension(
    manifest: UCPManifestResult,
    schema_probes: list[UCPSchemaProbe],
) -> UCPDimensionScore:
    caps_score = _coverage_score(
        config.UCP_REQUIRED_CATALOG_CAPABILITIES,
        manifest.capabilities_declared,
        maximum=60,
    )
    schema_score = _schema_keyword_score(schema_probes, "catalog", maximum=40)
    missing = [
        item
        for item in config.UCP_REQUIRED_CATALOG_CAPABILITIES
        if item not in manifest.capabilities_declared
    ]
    findings = [
        _missing_finding(
            config.FINDING_CATALOG_CONTRACT_MISSING,
            config.D_UCP4_ID,
            missing,
            "Catalog search and lookup payload contracts are incomplete.",
        )
    ] if missing or schema_score < 40 else []
    return _dimension(config.D_UCP4_ID, caps_score + schema_score, findings)


def _cart_checkout_dimension(
    manifest: UCPManifestResult,
    schema_probes: list[UCPSchemaProbe],
) -> UCPDimensionScore:
    caps_score = _coverage_score(
        config.UCP_REQUIRED_CART_CHECKOUT_CAPABILITIES,
        manifest.capabilities_declared,
        maximum=60,
    )
    schema_score = _schema_keyword_score(schema_probes, "cart_checkout", maximum=40)
    missing = [
        item
        for item in config.UCP_REQUIRED_CART_CHECKOUT_CAPABILITIES
        if item not in manifest.capabilities_declared
    ]
    findings = [
        _missing_finding(
            config.FINDING_CART_CHECKOUT_CONTRACT_MISSING,
            config.D_UCP5_ID,
            missing,
            "Cart and checkout payload contracts are incomplete.",
        )
    ] if missing or schema_score < 40 else []
    return _dimension(config.D_UCP5_ID, caps_score + schema_score, findings)


def _order_policy_dimension(
    manifest: UCPManifestResult,
    schema_probes: list[UCPSchemaProbe],
) -> UCPDimensionScore:
    caps_score = _coverage_score(
        config.UCP_REQUIRED_ORDER_POLICY_CAPABILITIES,
        manifest.capabilities_declared,
        maximum=60,
    )
    schema_score = _schema_keyword_score(schema_probes, "order_policy", maximum=25)
    payment_score = 15 if manifest.payment_handlers else 0
    missing = [
        item
        for item in config.UCP_REQUIRED_ORDER_POLICY_CAPABILITIES
        if item not in manifest.capabilities_declared
    ]
    findings: list[UCPFinding] = []
    if missing or schema_score < 25:
        findings.append(
            _missing_finding(
                config.FINDING_ORDER_POLICY_CONTRACT_MISSING,
                config.D_UCP6_ID,
                missing,
                "Order, fulfillment, discount, or policy payload contracts are incomplete.",
            )
        )
    if not manifest.payment_handlers:
        findings.append(
            UCPFinding(
                code=config.FINDING_PAYMENT_HANDLER_MISSING,
                dimension_id=config.D_UCP6_ID,
                severity=config.UCP_FINDING_WARNING,
                message="No UCP payment handler is declared.",
            )
        )
    return _dimension(config.D_UCP6_ID, caps_score + schema_score + payment_score, findings)


def _transport_probe_score(probe: UCPTransportProbe) -> int:
    if probe.negotiated:
        return 100
    if probe.transport == "embedded" and probe.reachable:
        return 80
    if probe.profile_required:
        return 70
    if probe.reachable:
        return 50
    return 0


def _coverage_score(required: tuple[str, ...], declared: list[str], *, maximum: int) -> int:
    if not required:
        return maximum
    found = len([item for item in required if item in declared])
    return int(maximum * (found / len(required)))


def _schema_keyword_score(
    probes: list[UCPSchemaProbe],
    group: str,
    *,
    maximum: int,
) -> int:
    keywords = config.UCP_REQUIRED_SCHEMA_KEYWORDS[group]
    if not keywords:
        return maximum
    found = 0
    for keyword in keywords:
        if any(
            probe.reachable
            and probe.valid_json
            and keyword in f"{probe.url} {probe.title}".lower()
            for probe in probes
        ):
            found += 1
    return int(maximum * (found / len(keywords)))


def _missing_finding(
    code: str,
    dimension_id: str,
    missing: list[str] | tuple[str, ...],
    message: str,
) -> UCPFinding:
    return UCPFinding(
        code=code,
        dimension_id=dimension_id,
        severity=config.UCP_FINDING_WARNING,
        message=message,
        affected_count=len(missing),
        count_kind="contracts",
        evidence=[{"missing": list(missing)}],
    )


def _dimension(
    dimension_id: str,
    score: int,
    findings: list[UCPFinding],
) -> UCPDimensionScore:
    normalized = max(0, min(100, int(score)))
    return UCPDimensionScore(
        dimension_id=dimension_id,
        score=normalized,
        status=_status(normalized, findings),
        findings=findings,
        weight=config.DIMENSION_WEIGHTS[dimension_id],
    )


def _status(score: int, findings: list[UCPFinding]) -> str:
    if any(item.severity == config.UCP_FINDING_BLOCKING for item in findings):
        return config.UCP_STATUS_FAIL
    if score >= 80 and not findings:
        return config.UCP_STATUS_PASS
    if score >= 50:
        return config.UCP_STATUS_WARNING
    return config.UCP_STATUS_FAIL


def _average(values: list[int]) -> int:
    if not values:
        return 0
    return int(sum(values) / len(values))


def _safe_json(response: httpx.Response) -> dict:
    try:
        payload = response.json()
    except ValueError:
        return {"raw": response.text[:500]}
    return payload if isinstance(payload, dict) else {"raw": payload}


def _tool_entries(payload: dict) -> list[dict]:
    result = payload.get("result")
    raw_tools = result.get("tools") if isinstance(result, dict) else None
    if not isinstance(raw_tools, list):
        return []
    return [dict(item) for item in raw_tools if isinstance(item, dict)]


def _preview(payload: dict) -> dict:
    if "result" in payload:
        return {"result_keys": sorted(dict(payload.get("result") or {}).keys())}
    if "error" in payload:
        return {"error": payload.get("error")}
    return {"keys": sorted(payload.keys())}


def _supported_versions(payload: dict) -> list[str]:
    root = payload.get("ucp") if isinstance(payload.get("ucp"), dict) else payload
    versions = root.get("supported_versions") if isinstance(root, dict) else None
    if isinstance(versions, dict):
        return sorted(str(item) for item in versions.keys())
    return []

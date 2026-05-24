from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict
from typing import Any

import httpx
from jsonschema.exceptions import SchemaError
from jsonschema.validators import validator_for

from app.services.config import ucp_audit as config
from app.services.network_resolution import build_async_http_client
from app.services.ucp_audit.discovery import (
    check_manifest_cache_headers,
    check_version_alignment,
)
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
        schema_url = str(entry.get("schema") or "")
        if transport == "mcp" and endpoint:
            probes.append(await _probe_mcp(service=service, endpoint=endpoint))
            continue
        if transport == "rest" and endpoint:
            probes.append(await _probe_rest(service=service, endpoint=endpoint))
            continue
        if transport == "a2a" and endpoint:
            probes.append(await _probe_a2a(service=service, endpoint=endpoint))
            continue
        probes.append(
            UCPTransportProbe(
                service=service,
                transport=transport,
                endpoint=endpoint,
                schema_url=schema_url,
                reachable=False,
                negotiated=False,
                error="" if schema_url else "missing schema or endpoint",
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
                response = await client.get(
                    url,
                    headers={"Accept": config.UCP_ACCEPT_HEADER},
                )
            payload = response.json()
            valid_json = isinstance(payload, dict)
            schema_error = _schema_error(payload) if valid_json else "schema is not an object"
            field_results = (
                _schema_field_results(payload) if valid_json and not schema_error else {}
            )
            return UCPSchemaProbe(
                url=url,
                reachable=response.status_code < 400,
                valid_json=valid_json,
                schema_valid=valid_json and not schema_error,
                status_code=response.status_code,
                content_type=response.headers.get("content-type", ""),
                title=str(payload.get("title") or payload.get("$id") or "")
                if isinstance(payload, dict)
                else "",
                error=schema_error,
                groups=_schema_groups(url, payload if isinstance(payload, dict) else {}),
                field_results=field_results,
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
            "target_version": manifest.target_version,
            "selected_version": manifest.selected_version,
            "version_source": manifest.version_source,
            "content_type": manifest.content_type,
            "final_url": manifest.final_url,
            "redirect_chain": manifest.redirect_chain,
            "discovery_source": manifest.discovery_source,
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
        _transport_dimension(manifest, transport_probes, schema_probes),
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
            response = await client.post(
                endpoint,
                json=body,
                headers={
                    "Accept": config.UCP_ACCEPT_HEADER,
                    "UCP-Agent": f'profile="{config.UCP_AUDIT_PLATFORM_PROFILE_URL}"',
                },
            )
        payload = _safe_json(response)
        errors = _mcp_conformance_errors(payload, expected_id=str(body["id"]))
        error_text = json.dumps(payload.get("error", payload))[:500].lower()
        profile_required = _profile_required(payload)
        tools = _tool_entries(payload)
        return UCPTransportProbe(
            service=service,
            transport="mcp",
            endpoint=endpoint,
            reachable=response.status_code < 500,
            negotiated=response.status_code < 400 and not payload.get("error") and not errors,
            profile_required=profile_required,
            status_code=response.status_code,
            error="; ".join(errors)[:240]
            if errors
            else ("" if response.status_code < 400 else error_text[:240]),
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


async def _probe_rest(*, service: str, endpoint: str) -> UCPTransportProbe:
    try:
        async with build_async_http_client(
            follow_redirects=True,
            timeout=config.UCP_TRANSPORT_TIMEOUT_SECONDS,
        ) as client:
            options_resp = await client.options(
                endpoint,
                headers={"Accept": config.UCP_ACCEPT_HEADER},
            )
            get_resp = await client.get(
                endpoint,
                headers={"Accept": config.UCP_ACCEPT_HEADER},
            )
        allow = options_resp.headers.get("allow", "")
        reachable = get_resp.status_code < 500
        get_payload = _safe_json(get_resp)
        ucp_shaped = (
            _non_empty_collection(get_payload.get("capabilities"))
            or _non_empty_collection(get_payload.get("services"))
            or bool(get_resp.headers.get("UCP-Version"))
            or "ucp" in str(get_payload.get("$schema") or "").lower()
        )
        negotiated = reachable and get_resp.status_code < 400 and ucp_shaped
        return UCPTransportProbe(
            service=service,
            transport="rest",
            endpoint=endpoint,
            reachable=reachable,
            negotiated=negotiated,
            status_code=get_resp.status_code,
            error="" if reachable else get_resp.text[:240],
            response_preview={"allow": allow, "get_keys": sorted(get_payload.keys())}
            if allow
            else {},
        )
    except (httpx.HTTPError, OSError, TimeoutError, asyncio.TimeoutError) as exc:
        logger.debug("UCP REST probe failed for %s: %s", endpoint, exc, exc_info=True)
        return UCPTransportProbe(
            service=service,
            transport="rest",
            endpoint=endpoint,
            error=str(exc),
        )


async def _probe_a2a(*, service: str, endpoint: str) -> UCPTransportProbe:
    try:
        async with build_async_http_client(
            follow_redirects=True,
            timeout=config.UCP_TRANSPORT_TIMEOUT_SECONDS,
        ) as client:
            response = await client.get(
                endpoint,
                headers={"Accept": config.UCP_ACCEPT_HEADER},
            )
        payload = _safe_json(response)
        a2a_shaped = (
            isinstance(payload.get("capabilities"), (list, dict))
            or "agent" in payload
            or bool(response.headers.get("A2A-Version"))
        )
        return UCPTransportProbe(
            service=service,
            transport="a2a",
            endpoint=endpoint,
            reachable=response.status_code < 500,
            negotiated=response.status_code < 400 and a2a_shaped,
            status_code=response.status_code,
            error="" if response.status_code < 400 else response.text[:240],
            response_preview=_preview(payload),
        )
    except (httpx.HTTPError, OSError, TimeoutError, asyncio.TimeoutError) as exc:
        logger.debug("UCP A2A probe failed for %s: %s", endpoint, exc, exc_info=True)
        return UCPTransportProbe(
            service=service,
            transport="a2a",
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
                message="UCP discovery profile has structural errors.",
                evidence=[{"errors": [e for e in manifest.errors if "signing_keys" not in e]}],
            )
        )
    if manifest.signing_keys_errors:
        findings.append(
            UCPFinding(
                code=config.FINDING_SIGNING_KEYS_MISSING,
                dimension_id=config.D_UCP1_ID,
                severity=config.UCP_FINDING_WARNING,
                message=(
                    "signing_keys array is missing or empty. "
                    "Webhook signatures cannot be verified per RFC 7797."
                ),
                evidence=[{"errors": list(manifest.signing_keys_errors)}],
            )
        )
    cache_errors = check_manifest_cache_headers(manifest.response_headers)
    if cache_errors:
        findings.append(
            UCPFinding(
                code=config.FINDING_CACHE_CONTROL_MISSING,
                dimension_id=config.D_UCP1_ID,
                severity=config.UCP_FINDING_WARNING,
                message="UCP discovery profile response lacks required cache headers.",
                evidence=[{"errors": cache_errors}],
            )
        )
    if not manifest.final_url.endswith(config.UCP_MANIFEST_PATH) and manifest.final_url:
        findings.append(
            UCPFinding(
                code=config.FINDING_MANIFEST_REDIRECTED,
                dimension_id=config.D_UCP1_ID,
                severity=config.UCP_FINDING_WARNING,
                message="UCP discovery profile did not resolve at the canonical well-known path.",
                evidence=[
                    {
                        "final_url": manifest.final_url,
                        "redirect_chain": manifest.redirect_chain,
                    }
                ],
            )
        )
    if any(finding.code == config.FINDING_MANIFEST_INVALID for finding in findings):
        score = 40
    elif findings:
        score = 80
    else:
        score = 100
    return _dimension(config.D_UCP1_ID, score, findings)


def _services_dimension(manifest: UCPManifestResult) -> UCPDimensionScore:
    service_score = 60 if not manifest.missing_required_services else 0
    capability_score = _coverage_score(
        config.UCP_REQUIRED_CAPABILITIES,
        manifest.capabilities_declared,
        maximum=40,
    )
    findings: list[UCPFinding] = []
    service_errors = _entry_validation_errors(manifest.service_entries)
    capability_errors = _entry_validation_errors(manifest.capability_entries)
    version_mismatches = check_version_alignment(
        manifest.service_entries,
        manifest.capability_entries,
        config.UCP_SHOPPING_SERVICE,
    )
    if manifest.missing_required_services:
        findings.append(
            _missing_finding(
                config.FINDING_SERVICE_MISSING,
                config.D_UCP2_ID,
                manifest.missing_required_services,
                "Required UCP shopping service is not declared.",
            )
        )
    if service_errors:
        findings.append(
            UCPFinding(
                code=config.FINDING_SERVICE_INVALID,
                dimension_id=config.D_UCP2_ID,
                severity=config.UCP_FINDING_WARNING,
                message="One or more UCP service entries are malformed.",
                affected_count=len(service_errors),
                count_kind="services",
                evidence=service_errors,
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
    if capability_errors:
        findings.append(
            UCPFinding(
                code=config.FINDING_CAPABILITY_INVALID,
                dimension_id=config.D_UCP2_ID,
                severity=config.UCP_FINDING_WARNING,
                message="One or more UCP capability entries are malformed.",
                affected_count=len(capability_errors),
                count_kind="capabilities",
                evidence=capability_errors,
            )
        )
    if version_mismatches:
        findings.append(
            UCPFinding(
                code=config.FINDING_CAPABILITY_VERSION_MISMATCH,
                dimension_id=config.D_UCP2_ID,
                severity=config.UCP_FINDING_WARNING,
                message="Capability versions do not align with the shopping service version.",
                evidence=[{"errors": version_mismatches}],
            )
        )
    return _dimension(config.D_UCP2_ID, service_score + capability_score, findings)


def _transport_dimension(
    manifest: UCPManifestResult,
    transport_probes: list[UCPTransportProbe],
    schema_probes: list[UCPSchemaProbe],
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
    scores = [_transport_probe_score(item, schema_probes) for item in transport_probes]
    findings: list[UCPFinding] = []
    if not any(_transport_reachable(item, schema_probes) for item in transport_probes):
        findings.append(
            UCPFinding(
                code=config.FINDING_TRANSPORT_UNREACHABLE,
                dimension_id=config.D_UCP3_ID,
                severity=config.UCP_FINDING_BLOCKING,
                message="No declared UCP transport is reachable.",
                evidence=[asdict(item) for item in transport_probes],
            )
        )
    reachable_incomplete = [
        item
        for item in transport_probes
        if _transport_reachable(item, schema_probes) and not item.negotiated
    ]
    if reachable_incomplete:
        findings.append(
            UCPFinding(
                code=config.FINDING_TRANSPORT_NEGOTIATION_INCOMPLETE,
                dimension_id=config.D_UCP3_ID,
                severity=config.UCP_FINDING_WARNING,
                message="At least one reachable transport did not complete full negotiation.",
                evidence=[asdict(item) for item in reachable_incomplete],
            )
        )
    best = max(scores, default=0)
    bonus = min(10, 5 * max(0, len([s for s in scores if s >= 70]) - 1))
    final_score = min(100, best + bonus)
    return _dimension(config.D_UCP3_ID, final_score, findings)


def _catalog_dimension(
    manifest: UCPManifestResult,
    schema_probes: list[UCPSchemaProbe],
) -> UCPDimensionScore:
    caps_score = _coverage_score(
        config.UCP_REQUIRED_CATALOG_CAPABILITIES,
        manifest.capabilities_declared,
        maximum=60,
    )
    schema_score = _schema_field_score(schema_probes, "catalog", maximum=40)
    missing_fields = _missing_schema_fields(schema_probes, "catalog")
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
    _append_missing_schema_evidence(
        findings,
        config.FINDING_CATALOG_CONTRACT_MISSING,
        config.D_UCP4_ID,
        missing_fields,
        "Catalog search and lookup payload contracts are incomplete.",
    )
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
    schema_score = _schema_field_score(schema_probes, "cart_checkout", maximum=40)
    missing_fields = _missing_schema_fields(schema_probes, "cart_checkout")
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
    _append_missing_schema_evidence(
        findings,
        config.FINDING_CART_CHECKOUT_CONTRACT_MISSING,
        config.D_UCP5_ID,
        missing_fields,
        "Cart and checkout payload contracts are incomplete.",
    )
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
    schema_score = _schema_field_score(schema_probes, "order_policy", maximum=25)
    missing_fields = _missing_schema_fields(schema_probes, "order_policy")
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
        if missing_fields:
            findings[-1].evidence.append({"missing_schema_fields": missing_fields})
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


def _transport_probe_score(
    probe: UCPTransportProbe,
    schema_probes: list[UCPSchemaProbe],
) -> int:
    if probe.negotiated:
        return 100
    if probe.transport == "embedded" and _embedded_schema_valid(probe, schema_probes):
        return 80
    if probe.profile_required:
        return 70
    if probe.reachable:
        return 50
    return 0


def _transport_reachable(
    probe: UCPTransportProbe,
    schema_probes: list[UCPSchemaProbe],
) -> bool:
    if probe.transport == "embedded":
        return _embedded_schema_valid(probe, schema_probes)
    return probe.reachable


def _embedded_schema_valid(
    probe: UCPTransportProbe,
    schema_probes: list[UCPSchemaProbe],
) -> bool:
    schema_url = str(probe.schema_url or "")
    return bool(
        schema_url
        and any(item.url == schema_url and item.reachable and item.schema_valid for item in schema_probes)
    )


def _coverage_score(required: tuple[str, ...], declared: list[str], *, maximum: int) -> int:
    if not required:
        return maximum
    found = len([item for item in required if item in declared])
    return int(maximum * (found / len(required)))


def _schema_field_score(
    probes: list[UCPSchemaProbe],
    group: str,
    *,
    maximum: int,
) -> int:
    required = config.UCP_REQUIRED_SCHEMA_FIELDS[group]
    if not required:
        return maximum
    found = len(required) - len(_missing_schema_fields(probes, group))
    return int(maximum * (found / len(required)))


def _missing_schema_fields(probes: list[UCPSchemaProbe], group: str) -> list[str]:
    missing: list[str] = []
    for field in config.UCP_REQUIRED_SCHEMA_FIELDS[group]:
        if not any(
            probe.reachable
            and probe.schema_valid
            and probe.field_results.get(group, {}).get(field)
            for probe in probes
        ):
            missing.append(field)
    return missing


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


def _append_missing_schema_evidence(
    findings: list[UCPFinding],
    code: str,
    dimension_id: str,
    missing_fields: list[str],
    message: str,
) -> None:
    if not missing_fields:
        return
    if not findings:
        findings.append(
            UCPFinding(
                code=code,
                dimension_id=dimension_id,
                severity=config.UCP_FINDING_WARNING,
                message=message,
                evidence=[],
            )
        )
    findings[0].evidence.append({"missing_schema_fields": missing_fields})


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
    has_warnings = any(item.severity == config.UCP_FINDING_WARNING for item in findings)
    if score >= 80 and not has_warnings:
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


def _mcp_conformance_errors(payload: dict, *, expected_id: str) -> list[str]:
    if payload.get("error"):
        return []
    errors: list[str] = []
    if payload.get("jsonrpc") != "2.0":
        errors.append("MCP response missing jsonrpc=2.0")
    if str(payload.get("id") or "") != expected_id:
        errors.append("MCP response did not echo request id")
    tools = _tool_entries(payload)
    if not tools:
        errors.append("MCP tools/list did not return result.tools")
    for tool in tools:
        if not isinstance(tool.get("inputSchema"), dict):
            errors.append(f"MCP tool {tool.get('name') or '<unknown>'} lacks inputSchema")
    return errors


def _profile_required(payload: dict) -> bool:
    error = payload.get("error")
    if not isinstance(error, dict):
        return False
    try:
        raw_code = error.get("code")
        if raw_code is None:
            return False
        code = int(raw_code)
    except (TypeError, ValueError):
        return False
    raw_data = error.get("data")
    data: dict = raw_data if isinstance(raw_data, dict) else {}
    text = " ".join(
        [
            str(error.get("message") or "").lower(),
            str(data.get("code") or "").lower(),
            str(data.get("content") or "").lower(),
        ]
    )
    return -32099 <= code <= -32000 and "profile" in text and any(
        kw in text for kw in ("missing", "invalid", "required", "uri", "url")
    )


def _schema_error(payload: dict) -> str:
    try:
        validator_cls = validator_for(payload)
        validator_cls.check_schema(payload)
    except SchemaError as exc:
        return str(exc.message)
    return ""


def _schema_field_results(payload: dict) -> dict[str, dict[str, bool]]:
    return {
        group: {
            field: _schema_contains_field(payload, field, root=payload)
            for field in required_fields
        }
        for group, required_fields in config.UCP_REQUIRED_SCHEMA_FIELDS.items()
    }


def _resolve_refs(node: object, root: dict, seen: set[str] | None = None) -> object:
    if not isinstance(node, dict):
        return node
    ref = node.get("$ref")
    if not ref or not isinstance(ref, str) or not ref.startswith("#/"):
        return node
    seen = set() if seen is None else seen
    if ref in seen:
        return node
    seen.add(ref)
    cursor: object = root
    for part in ref.lstrip("#/").split("/"):
        if not isinstance(cursor, dict):
            return node
        cursor = cursor.get(part, {})
    return _resolve_refs(cursor, root, seen) if cursor != {} else node


def _schema_contains_field(value: object, field: str, root: dict | None = None) -> bool:
    if root is None:
        root = value if isinstance(value, dict) else {}
    if isinstance(value, dict):
        value = _resolve_refs(value, root)
        if not isinstance(value, dict):
            return False
        for key, child in value.items():
            if str(key).lower() == field:
                return True
            if key == "required" and isinstance(child, list):
                if any(str(item).lower() == field for item in child):
                    return True
            if key == "properties" and isinstance(child, dict):
                if any(str(item).lower() == field for item in child):
                    return True
            if _schema_contains_field(child, field, root):
                return True
    if isinstance(value, list):
        return any(_schema_contains_field(item, field, root) for item in value)
    return False


def _schema_groups(url: str, payload: dict) -> list[str]:
    text = f"{url} {payload.get('title') or ''} {payload.get('$id') or ''}".lower()
    groups = [
        group
        for group, keywords in config.UCP_REQUIRED_SCHEMA_KEYWORDS.items()
        if any(keyword in text for keyword in keywords)
    ]
    field_results = _schema_field_results(payload)
    for group, results in field_results.items():
        if any(results.values()) and group not in groups:
            groups.append(group)
    return groups


def _entry_validation_errors(entries: list[dict]) -> list[dict[str, Any]]:
    return [
        {"name": str(entry.get("name") or ""), "errors": list(entry.get("_errors") or [])}
        for entry in entries
        if entry.get("_errors")
    ]


def _preview(payload: dict) -> dict:
    if "result" in payload:
        return {"result_keys": sorted(dict(payload.get("result") or {}).keys())}
    if "error" in payload:
        return {"error": payload.get("error")}
    return {"keys": sorted(payload.keys())}


def _non_empty_collection(value: object) -> bool:
    return isinstance(value, (list, dict)) and bool(value)


def _supported_versions(payload: dict) -> list[str]:
    root = payload.get("ucp") if isinstance(payload.get("ucp"), dict) else payload
    versions = root.get("supported_versions") if isinstance(root, dict) else None
    if isinstance(versions, dict):
        return sorted(str(item) for item in versions.keys())
    if isinstance(versions, list):
        normalized = [
            str(item.get("version") if isinstance(item, dict) else item)
            for item in versions
        ]
        return sorted(item for item in normalized if item.strip())
    return []

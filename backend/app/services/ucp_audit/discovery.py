from __future__ import annotations

import asyncio
import json
import logging
import re
from collections.abc import Iterable
from types import SimpleNamespace
from typing import Any
from urllib.parse import urljoin, urlparse, urlunparse

import httpx

from app.services.config import ucp_audit as config
from app.services.network_resolution import build_async_http_client
from app.services.ucp_audit.types import UCPManifestResult

logger = logging.getLogger(__name__)

_VERSION_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


async def discover_ucp_manifest(domain: str) -> UCPManifestResult:
    target_url = manifest_url(domain)
    result = await _fetch_manifest_page(target_url)
    if _should_try_link_fallback(result):
        fallback_url = await _discover_link_manifest_url(domain)
        if fallback_url:
            fallback_result = await _fetch_manifest_page(fallback_url)
            if fallback_result is not None and not _page_error(fallback_result):
                result = fallback_result
                _set_result_attr(result, "discovery_source", "link-header")
    if result is None:
        return UCPManifestResult(
            manifest_found=False,
            target_version=config.UCP_TARGET_VERSION,
            final_url=target_url,
            missing_required_capabilities=list(config.UCP_REQUIRED_CAPABILITIES),
            missing_required_services=list(config.UCP_REQUIRED_SERVICE_NAMES),
            errors=[f"{config.UCP_MANIFEST_PATH} fetch failed"],
        )
    discovery_source = str(getattr(result, "discovery_source", "well-known") or "well-known")
    fetch_error = _page_error(result)
    if fetch_error:
        return UCPManifestResult(
            manifest_found=False,
            target_version=config.UCP_TARGET_VERSION,
            discovery_source=discovery_source,
            content_type=str(getattr(result, "content_type", "") or ""),
            final_url=str(getattr(result, "final_url", target_url) or target_url),
            redirect_chain=list(getattr(result, "redirect_chain", []) or []),
            missing_required_capabilities=list(config.UCP_REQUIRED_CAPABILITIES),
            missing_required_services=list(config.UCP_REQUIRED_SERVICE_NAMES),
            errors=[fetch_error],
        )
    if int(getattr(result, "status_code", 0) or 0) == 404:
        return UCPManifestResult(
            manifest_found=False,
            target_version=config.UCP_TARGET_VERSION,
            discovery_source=discovery_source,
            content_type=str(getattr(result, "content_type", "") or ""),
            final_url=str(getattr(result, "final_url", target_url) or target_url),
            redirect_chain=list(getattr(result, "redirect_chain", []) or []),
            missing_required_capabilities=list(config.UCP_REQUIRED_CAPABILITIES),
            missing_required_services=list(config.UCP_REQUIRED_SERVICE_NAMES),
            errors=[f"{config.UCP_MANIFEST_PATH} returned 404"],
        )
    result, payload, parse_errors = await _selected_manifest_payload(result)
    metadata: dict[str, Any] = {
        "target_version": config.UCP_TARGET_VERSION,
        "discovery_source": discovery_source,
        "content_type": str(getattr(result, "content_type", "") or ""),
        "final_url": str(getattr(result, "final_url", target_url) or target_url),
        "redirect_chain": list(getattr(result, "redirect_chain", []) or []),
    }
    if parse_errors:
        version_source = str(getattr(result, "version_source", "") or "")
        return UCPManifestResult(
            manifest_found=version_source != "unsupported",
            **metadata,
            missing_required_capabilities=list(config.UCP_REQUIRED_CAPABILITIES),
            missing_required_services=list(config.UCP_REQUIRED_SERVICE_NAMES),
            errors=parse_errors,
        )
    assert payload is not None

    root = _profile_root(payload)
    services = _service_entries(payload)
    capabilities = _capability_entries(payload)
    _validate_entry_versions(services, "service")
    _validate_entry_versions(capabilities, "capability")
    service_names = sorted({item["name"] for item in services})
    capability_names = sorted({item["name"] for item in capabilities})
    missing_services = [
        item for item in config.UCP_REQUIRED_SERVICE_NAMES if item not in service_names
    ]
    missing_capabilities = [
        item for item in config.UCP_REQUIRED_CAPABILITIES if item not in capability_names
    ]
    shape_errors = _validate_manifest_shape(payload)
    if not _is_json_content_type(metadata["content_type"]):
        shape_errors.append(
            "Response Content-Type is not application/json or an application/*+json type"
        )
    if metadata["redirect_chain"]:
        shape_errors.append("Discovery endpoint redirected before profile resolution")
    entry_errors = _entry_errors(services, "service") + _entry_errors(
        capabilities, "capability"
    )
    profile_valid = (
        isinstance(root, dict)
        and not missing_services
        and not shape_errors
        and not entry_errors
    )

    return UCPManifestResult(
        manifest_found=True,
        manifest_valid=profile_valid,
        selected_version=str(root.get("version") or ""),
        version_source=str(getattr(result, "version_source", "current") or "current"),
        capabilities_declared=capability_names,
        missing_required_capabilities=missing_capabilities,
        services_declared=service_names,
        missing_required_services=missing_services,
        service_entries=services,
        capability_entries=capabilities,
        transport_entries=_transport_entries(services, metadata["final_url"]),
        schema_urls=_schema_urls(
            metadata["final_url"],
            services,
            capabilities,
            _payment_handler_entries(payload),
        ),
        payment_handlers=sorted({item["name"] for item in _payment_handler_entries(payload)}),
        raw_manifest=payload,
        errors=shape_errors + entry_errors,
        **metadata,
    )


async def _selected_manifest_payload(result: object) -> tuple[object, dict | None, list[str]]:
    raw_body = str(getattr(result, "html", "") or "")
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        return result, None, [str(exc)]
    if not isinstance(payload, dict):
        return result, None, [type(payload).__name__]
    root = _profile_root(payload)
    version = str(root.get("version") or "") if isinstance(root, dict) else ""
    if version == config.UCP_TARGET_VERSION:
        _set_result_attr(result, "version_source", "current")
        return result, payload, []
    supported = root.get("supported_versions") if isinstance(root, dict) else None
    version_url = ""
    if isinstance(supported, dict):
        version_url = str(supported.get(config.UCP_TARGET_VERSION) or "").strip()
    if version_url:
        fetched = await _fetch_manifest_page(version_url)
        if fetched is None or _page_error(fetched):
            return result, payload, [
                f"Unable to fetch supported version profile {config.UCP_TARGET_VERSION}"
            ]
        raw_supported = str(getattr(fetched, "html", "") or "")
        try:
            supported_payload = json.loads(raw_supported)
        except json.JSONDecodeError as exc:
            return fetched, None, [str(exc)]
        if not isinstance(supported_payload, dict):
            return fetched, None, [type(supported_payload).__name__]
        _set_result_attr(fetched, "version_source", "supported_versions")
        return fetched, supported_payload, []
    _set_result_attr(result, "version_source", "unsupported")
    return result, payload, [
        f"UCP target version {config.UCP_TARGET_VERSION} is not declared"
    ]


async def _fetch_manifest_page(url: str):
    try:
        async with build_async_http_client(
            follow_redirects=True,
            timeout=config.UCP_DISCOVERY_TIMEOUT_SECONDS,
        ) as client:
            response = await client.get(
                url,
                headers={"Accept": config.UCP_ACCEPT_HEADER},
            )
        return SimpleNamespace(
            url=url,
            final_url=str(response.url),
            html=response.text,
            status_code=response.status_code,
            content_type=response.headers.get("content-type", ""),
            headers=dict(response.headers),
            redirect_chain=[str(item.url) for item in response.history],
        )
    except (httpx.HTTPError, OSError, TimeoutError, asyncio.TimeoutError) as exc:
        logger.debug("UCP manifest fetch failed for %s", url, exc_info=True)
        return SimpleNamespace(
            url=url,
            final_url=url,
            html="",
            status_code=0,
            content_type="",
            headers={},
            redirect_chain=[],
            error=str(exc),
        )


async def _discover_link_manifest_url(domain: str) -> str:
    try:
        async with build_async_http_client(
            follow_redirects=True,
            timeout=config.UCP_DISCOVERY_TIMEOUT_SECONDS,
        ) as client:
            response = await client.get(
                _root_url(domain),
                headers={"Accept": config.UCP_ACCEPT_HEADER},
            )
    except (httpx.HTTPError, OSError, TimeoutError, asyncio.TimeoutError):
        return ""
    return _link_header_ucp_url(response.headers.get("link", ""), str(response.url))


def manifest_url(value: str) -> str:
    parsed = urlparse(str(value or "").strip())
    if not parsed.scheme:
        parsed = urlparse(f"{config.UCP_DEFAULT_URL_SCHEME}://{value}")
    return urlunparse(
        (parsed.scheme, parsed.netloc, config.UCP_MANIFEST_PATH, "", "", "")
    )


def _profile_root(payload: dict) -> dict:
    nested = payload.get("ucp")
    return nested if isinstance(nested, dict) else payload


def _page_error(result: object) -> str:
    return str(getattr(result, "error", "") or "")


def _should_try_link_fallback(result: object | None) -> bool:
    if result is None:
        return True
    if _page_error(result):
        return True
    return int(getattr(result, "status_code", 0) or 0) in {404, 405}


def _service_entries(payload: dict) -> list[dict]:
    root = _profile_root(payload)
    services = root.get("services")
    if not isinstance(services, dict):
        return []
    return _named_entries(services)


def _capability_entries(payload: dict) -> list[dict]:
    root = _profile_root(payload)
    capabilities = root.get("capabilities")
    if not isinstance(capabilities, dict):
        return []
    return _named_entries(capabilities)


def _payment_handler_entries(payload: dict) -> list[dict]:
    root = _profile_root(payload)
    handlers = root.get("payment_handlers")
    if not isinstance(handlers, dict):
        return []
    return _named_entries(handlers)


def _named_entries(raw_map: dict) -> list[dict]:
    entries: list[dict] = []
    for name, raw in raw_map.items():
        raw_entries: Iterable[object]
        if isinstance(raw, list):
            raw_entries = raw
        else:
            raw_entries = [raw]
        for raw_entry in raw_entries:
            entry = dict(raw_entry) if isinstance(raw_entry, dict) else {}
            entry["name"] = str(name)
            entries.append(entry)
    return entries


def _transport_entries(service_entries: list[dict], base_url: str) -> list[dict]:
    entries: list[dict] = []
    for service in service_entries:
        transport = str(service.get("transport") or "").strip().lower()
        if not transport:
            continue
        endpoint = _absolute_http_url(str(service.get("endpoint") or ""), base_url)
        errors = list(service.get("_errors") or [])
        if str(service.get("endpoint") or "").strip() and not endpoint:
            errors.append("Invalid service endpoint URL")
        entries.append(
            {
                "service": str(service.get("name") or ""),
                "transport": transport,
                "endpoint": endpoint,
                "schema": _absolute_http_url(str(service.get("schema") or ""), base_url),
                "errors": errors,
            }
        )
    return entries


def _schema_urls(base_url: str, *entry_sets: list[dict]) -> list[str]:
    urls: set[str] = set()
    for entries in entry_sets:
        for entry in entries:
            value = _absolute_http_url(str(entry.get("schema") or ""), base_url)
            if value:
                urls.add(value)
    return sorted(urls)


def _validate_manifest_shape(payload: dict) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload.get("ucp"), dict):
        errors.append("Missing required object: ucp")
        return errors
    root = _profile_root(payload)
    version = str(root.get("version") or "")
    if not version:
        errors.append("Missing required field: ucp.version")
    elif not _VERSION_RE.match(version):
        errors.append("ucp.version must be a YYYY-MM-DD date")
    for field in ("services", "capabilities"):
        if not isinstance(root.get(field), dict):
            errors.append(f"Missing required object: ucp.{field}")
    signing_keys = payload.get("signing_keys")
    if not isinstance(signing_keys, list):
        errors.append("Missing required array: signing_keys")
    return errors


def _validate_entry_versions(entries: list[dict], kind: str) -> None:
    for entry in entries:
        version = str(entry.get("version") or "")
        errors = list(entry.get("_errors") or [])
        if not version:
            errors.append(f"Missing {kind} version for {entry.get('name')}")
        elif not _VERSION_RE.match(version):
            errors.append(f"Invalid {kind} version for {entry.get('name')}: {version}")
        if kind == "service" and not str(entry.get("transport") or "").strip():
            errors.append(f"Missing service transport for {entry.get('name')}")
        if errors:
            entry["_errors"] = errors


def _entry_errors(entries: list[dict], kind: str) -> list[str]:
    errors: list[str] = []
    for entry in entries:
        for error in list(entry.get("_errors") or []):
            errors.append(str(error or f"Invalid {kind} entry"))
    return errors


def _is_json_content_type(content_type: str) -> bool:
    media_type = str(content_type or "").split(";", 1)[0].strip().lower()
    return media_type == "application/json" or media_type.endswith("+json")


def _absolute_http_url(value: str, base_url: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    candidate = urljoin(_root_url(base_url), raw)
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", parsed.query, ""))


def _root_url(value: str) -> str:
    parsed = urlparse(str(value or "").strip())
    if not parsed.scheme:
        parsed = urlparse(f"{config.UCP_DEFAULT_URL_SCHEME}://{value}")
    return urlunparse((parsed.scheme, parsed.netloc, "", "", "", ""))


def _link_header_ucp_url(value: str, base_url: str) -> str:
    for part in str(value or "").split(","):
        url_part, *params = part.split(";")
        rel_values = [item for item in params if "rel=" in item.lower()]
        if not rel_values:
            continue
        rel_text = rel_values[0].split("=", 1)[1].strip().strip('"').lower()
        if rel_text not in {"ucp", "ucp-profile", "profile"}:
            continue
        candidate = url_part.strip()
        if candidate.startswith("<") and candidate.endswith(">"):
            candidate = candidate[1:-1]
        absolute = _absolute_http_url(candidate, base_url)
        if _same_origin(absolute, base_url):
            return absolute
    return ""


def _same_origin(candidate: str, base_url: str) -> bool:
    candidate_parsed = urlparse(candidate)
    base_parsed = urlparse(base_url)
    return bool(
        candidate_parsed.scheme in {"http", "https"}
        and candidate_parsed.scheme == base_parsed.scheme
        and candidate_parsed.netloc.lower() == base_parsed.netloc.lower()
    )


def _set_result_attr(result: object, name: str, value: object) -> None:
    try:
        setattr(result, name, value)
    except AttributeError:
        return

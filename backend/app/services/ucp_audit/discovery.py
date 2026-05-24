from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Iterable
from types import SimpleNamespace
from urllib.parse import urlparse, urlunparse

import httpx

from app.services.config import ucp_audit as config
from app.services.network_resolution import build_async_http_client
from app.services.ucp_audit.types import UCPManifestResult

logger = logging.getLogger(__name__)


async def discover_ucp_manifest(domain: str) -> UCPManifestResult:
    target_url = manifest_url(domain)
    result = await _fetch_manifest_page(target_url)
    if result is None:
        return UCPManifestResult(
            manifest_found=False,
            missing_required_capabilities=list(config.UCP_REQUIRED_CAPABILITIES),
            missing_required_services=list(config.UCP_REQUIRED_SERVICE_NAMES),
            errors=[f"{config.UCP_MANIFEST_PATH} fetch failed"],
        )
    fetch_error = _page_error(result)
    if fetch_error:
        return UCPManifestResult(
            manifest_found=False,
            missing_required_capabilities=list(config.UCP_REQUIRED_CAPABILITIES),
            missing_required_services=list(config.UCP_REQUIRED_SERVICE_NAMES),
            errors=[fetch_error],
        )
    if int(getattr(result, "status_code", 0) or 0) == 404:
        return UCPManifestResult(
            manifest_found=False,
            missing_required_capabilities=list(config.UCP_REQUIRED_CAPABILITIES),
            missing_required_services=list(config.UCP_REQUIRED_SERVICE_NAMES),
            errors=[f"{config.UCP_MANIFEST_PATH} returned 404"],
        )
    raw_body = str(getattr(result, "html", "") or "")
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        return UCPManifestResult(
            manifest_found=True,
            missing_required_capabilities=list(config.UCP_REQUIRED_CAPABILITIES),
            missing_required_services=list(config.UCP_REQUIRED_SERVICE_NAMES),
            errors=[str(exc)],
        )
    if not isinstance(payload, dict):
        return UCPManifestResult(
            manifest_found=True,
            missing_required_capabilities=list(config.UCP_REQUIRED_CAPABILITIES),
            missing_required_services=list(config.UCP_REQUIRED_SERVICE_NAMES),
            errors=[type(payload).__name__],
        )

    services = _service_entries(payload)
    capabilities = _capability_entries(payload)
    service_names = sorted({item["name"] for item in services})
    capability_names = sorted({item["name"] for item in capabilities})
    missing_services = [
        item for item in config.UCP_REQUIRED_SERVICE_NAMES if item not in service_names
    ]
    missing_capabilities = [
        item for item in config.UCP_REQUIRED_CAPABILITIES if item not in capability_names
    ]
    profile_valid = bool(_profile_root(payload)) and not missing_services

    return UCPManifestResult(
        manifest_found=True,
        manifest_valid=profile_valid,
        capabilities_declared=capability_names,
        missing_required_capabilities=missing_capabilities,
        services_declared=service_names,
        missing_required_services=missing_services,
        service_entries=services,
        capability_entries=capabilities,
        transport_entries=_transport_entries(services),
        schema_urls=_schema_urls(services, capabilities, _payment_handler_entries(payload)),
        payment_handlers=sorted({item["name"] for item in _payment_handler_entries(payload)}),
        raw_manifest=payload,
        errors=[],
    )


async def _fetch_manifest_page(url: str):
    try:
        async with build_async_http_client(
            follow_redirects=True,
            timeout=config.UCP_DISCOVERY_TIMEOUT_SECONDS,
        ) as client:
            response = await client.get(url)
        return SimpleNamespace(
            url=url,
            final_url=str(response.url),
            html=response.text,
            status_code=response.status_code,
            content_type=response.headers.get("content-type", ""),
        )
    except (httpx.HTTPError, OSError, TimeoutError, asyncio.TimeoutError) as exc:
        logger.debug("UCP manifest fetch failed for %s", url, exc_info=True)
        return SimpleNamespace(
            url=url,
            final_url=url,
            html="",
            status_code=0,
            content_type="",
            error=str(exc),
        )


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


def _transport_entries(service_entries: list[dict]) -> list[dict]:
    entries: list[dict] = []
    for service in service_entries:
        transport = str(service.get("transport") or "").strip().lower()
        if not transport:
            continue
        entries.append(
            {
                "service": str(service.get("name") or ""),
                "transport": transport,
                "endpoint": str(service.get("endpoint") or ""),
                "schema": str(service.get("schema") or ""),
            }
        )
    return entries


def _schema_urls(*entry_sets: list[dict]) -> list[str]:
    urls: set[str] = set()
    for entries in entry_sets:
        for entry in entries:
            value = str(entry.get("schema") or "").strip()
            if value:
                urls.add(value)
    return sorted(urls)

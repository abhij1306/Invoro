from __future__ import annotations

import json
from urllib.parse import urlparse, urlunparse

from app.services.config import ucp_audit as config
from app.services.fetch.fetch_context import fetch_page
from app.services.ucp_audit.types import UCPManifestResult


async def discover_ucp_manifest(domain: str) -> UCPManifestResult:
    target_url = _manifest_url(domain)
    result = await fetch_page(
        target_url,
        timeout_seconds=config.UCP_DISCOVERY_TIMEOUT_SECONDS,
        fetch_mode=config.UCP_HTTP_ONLY_MODE,
        surface=config.UCP_AUDIT_SURFACE,
    )
    if int(getattr(result, "status_code", 0) or 0) == 404:
        return UCPManifestResult(
            manifest_found=False,
            capabilities_declared=[],
            missing_required_capabilities=list(config.UCP_REQUIRED_CAPABILITIES),
            manifest_valid=False,
            raw_manifest=None,
            errors=[],
        )
    raw_body = str(getattr(result, "html", "") or "")
    try:
        payload = json.loads(raw_body)
    except json.JSONDecodeError as exc:
        return UCPManifestResult(
            manifest_found=True,
            capabilities_declared=[],
            missing_required_capabilities=list(config.UCP_REQUIRED_CAPABILITIES),
            manifest_valid=False,
            raw_manifest=None,
            errors=[str(exc)],
        )
    if not isinstance(payload, dict):
        return UCPManifestResult(
            manifest_found=True,
            capabilities_declared=[],
            missing_required_capabilities=list(config.UCP_REQUIRED_CAPABILITIES),
            manifest_valid=False,
            raw_manifest=None,
            errors=[type(payload).__name__],
        )
    declared = _declared_capabilities(payload)
    missing = [
        item for item in config.UCP_REQUIRED_CAPABILITIES if item not in set(declared)
    ]
    return UCPManifestResult(
        manifest_found=True,
        capabilities_declared=declared,
        missing_required_capabilities=missing,
        manifest_valid=not missing,
        raw_manifest=payload,
        errors=[],
    )


def _manifest_url(value: str) -> str:
    parsed = urlparse(str(value or "").strip())
    if not parsed.scheme:
        parsed = urlparse(f"{config.UCP_DEFAULT_URL_SCHEME}://{value}")
    return urlunparse(
        (
            parsed.scheme,
            parsed.netloc,
            config.UCP_MANIFEST_PATH,
            "",
            "",
            "",
        )
    )


def _declared_capabilities(payload: dict) -> list[str]:
    raw = payload.get("capabilities")
    if isinstance(raw, dict):
        values = raw.keys()
    elif isinstance(raw, list):
        values = raw
    else:
        values = []
    return sorted({str(item).strip() for item in values if str(item).strip()})

from __future__ import annotations

from collections.abc import Iterable

from app.models.review import ReviewPromotion
from app.services.domain_utils import normalize_domain
from app.services.field_policy import canonical_requested_fields
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def load_domain_requested_fields(
    session: AsyncSession,
    *,
    url: str,
    surface: str,
) -> list[str]:
    domain = normalize_domain(url)
    if not domain:
        return []
    mapping = await load_domain_field_mapping(session, domain=domain, surface=surface)
    fields: list[str] = []
    seen: set[str] = set()
    for value in mapping.values():
        name = str(value or "").strip().lower()
        if not name or name in seen:
            continue
        seen.add(name)
        fields.append(name)
    return fields


async def load_domain_field_mapping(
    session: AsyncSession,
    *,
    domain: str,
    surface: str,
) -> dict[str, str]:
    result = await session.execute(
        select(ReviewPromotion.field_mapping)
        .where(
            ReviewPromotion.domain == domain,
            ReviewPromotion.surface == surface,
        )
        .order_by(ReviewPromotion.created_at.desc(), ReviewPromotion.id.desc())
        .limit(1)
    )
    mapping = result.scalar_one_or_none()
    return dict(mapping) if isinstance(mapping, dict) else {}


def refresh_record_commit_metadata(
    record,
    *,
    run,
    field_name: str,
    value: object,
    source_label: str = "user_commit",
    preserve_existing_sources: bool = False,
) -> None:
    normalized_field = str(field_name or "").strip().lower()
    if not normalized_field:
        return
    source_trace = dict(record.source_trace or {})
    field_discovery = dict(source_trace.get("field_discovery") or {})
    existing = field_discovery.get(normalized_field)
    sources = _commit_sources(
        existing,
        source_label=source_label,
        preserve_existing_sources=preserve_existing_sources,
    )
    next_payload: dict[str, object] = {
        "status": "found",
        "value": _stringify_value(value),
        "sources": sources,
    }
    if isinstance(existing, dict) and isinstance(existing.get("selector_trace"), dict):
        next_payload["selector_trace"] = dict(existing["selector_trace"])
    field_discovery[normalized_field] = next_payload
    source_trace["field_discovery"] = field_discovery

    requested_fields, found_fields, missing = _field_coverage(
        run.requested_fields, field_discovery
    )
    _set_missing_fields(source_trace, missing)
    record.source_trace = source_trace

    discovered_data = dict(record.discovered_data or {})
    if requested_fields:
        discovered_data["requested_field_coverage"] = {
            "requested": len(requested_fields),
            "found": len([item for item in requested_fields if item in found_fields]),
            "missing": missing,
        }
    record.discovered_data = discovered_data


def _commit_sources(
    existing: object, *, source_label: str, preserve_existing_sources: bool
) -> list[str]:
    if not preserve_existing_sources or not isinstance(existing, dict):
        return [source_label]
    existing_sources = existing.get("sources")
    if not isinstance(existing_sources, list) or not existing_sources:
        return [source_label]
    return [str(item) for item in existing_sources]


def _field_coverage(
    requested: Iterable[str] | None, field_discovery: dict
) -> tuple[list[str], set[str], list[str]]:
    requested_fields = canonical_requested_fields(requested)
    found_fields = {
        key
        for key, payload in field_discovery.items()
        if isinstance(payload, dict) and payload.get("status") == "found"
    }
    missing = [item for item in requested_fields if item and item not in found_fields]
    return requested_fields, found_fields, missing


def _set_missing_fields(source_trace: dict, missing: list[str]) -> None:
    if missing:
        source_trace["field_discovery_missing"] = missing
    else:
        source_trace.pop("field_discovery_missing", None)


def _stringify_value(value: object) -> str:
    if isinstance(value, (dict, list)):
        return str(value)
    if value is None:
        return ""
    return str(value)

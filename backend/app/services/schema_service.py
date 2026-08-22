from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from app.models.review import ReviewPromotion
from app.services.config.runtime_settings import crawler_runtime_settings
from app.services.domain_utils import normalize_domain
from app.services.field_policy import (
    canonical_fields_for_surface,
    field_allowed_for_surface,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

_SCHEMA_MAX_AGE = timedelta(days=crawler_runtime_settings.schema_max_age_days)


@dataclass
class ResolvedSchema:
    surface: str
    domain: str
    baseline_fields: list[str]
    fields: list[str]
    new_fields: list[str]
    deprecated_fields: list[str]
    source: str
    saved_at: str | None
    stale: bool


def _dedupe_fields(values: Iterable[str] | None) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values or []:
        normalized = str(value or "").strip().lower()
        if not normalized or normalized in seen:
            continue
        deduped.append(normalized)
        seen.add(normalized)
    return deduped


def _parse_saved_at(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _snapshot_to_resolved(
    *,
    surface: str,
    domain: str,
    baseline_fields: list[str],
    snapshot: dict | None,
    explicit_fields: list[str],
) -> ResolvedSchema:
    payload = snapshot if isinstance(snapshot, dict) else {}
    explicit_field_set = set(explicit_fields)
    saved_at = str(payload.get("saved_at") or "").strip() or None
    saved_at_dt = _parse_saved_at(saved_at)
    stale = bool(saved_at_dt and datetime.now(UTC) - saved_at_dt > _SCHEMA_MAX_AGE)
    stored_fields = _snapshot_fields(payload, "fields", surface=surface)
    baseline = _snapshot_fields(
        payload, "baseline_fields", surface=surface, fallback=baseline_fields
    )
    new_fields = _snapshot_fields(payload, "new_fields", surface=surface)
    deprecated_fields = _snapshot_fields(payload, "deprecated_fields", surface=surface)
    fields = _dedupe_fields(
        field
        for field in [*baseline, *stored_fields, *explicit_fields]
        if field in explicit_field_set or field_allowed_for_surface(surface, field)
    )
    new_fields = new_fields or _fields_not_in(fields, baseline)
    deprecated_fields = deprecated_fields or (
        _fields_not_in(baseline, stored_fields) if stored_fields else []
    )
    return ResolvedSchema(
        surface=surface,
        domain=domain,
        baseline_fields=baseline,
        fields=fields,
        new_fields=new_fields,
        deprecated_fields=deprecated_fields,
        source=str(payload.get("source") or "static").strip() or "static",
        saved_at=saved_at,
        stale=stale,
    )


def _snapshot_fields(
    payload: dict,
    key: str,
    *,
    surface: str,
    fallback: list[str] | None = None,
) -> list[str]:
    raw = payload.get(key)
    values = raw if isinstance(raw, list) else list(fallback or [])
    return _dedupe_fields(
        field for field in values if field_allowed_for_surface(surface, field)
    )


def _fields_not_in(values: list[str], excluded: list[str]) -> list[str]:
    excluded_set = set(excluded)
    return [field for field in values if field not in excluded_set]


async def load_resolved_schema(
    session: AsyncSession,
    surface: str,
    domain: str,
    *,
    explicit_fields: list[str] | None = None,
) -> ResolvedSchema:
    baseline_fields = _dedupe_fields(
        field
        for field in canonical_fields_for_surface(surface)
        if field_allowed_for_surface(surface, field)
    )
    normalized_domain = normalize_domain(domain)
    normalized_explicit = _dedupe_fields(explicit_fields or [])
    if not normalized_domain:
        fields = _dedupe_fields([*baseline_fields, *normalized_explicit])
        return ResolvedSchema(
            surface=surface,
            domain="",
            baseline_fields=baseline_fields,
            fields=fields,
            new_fields=[field for field in fields if field not in set(baseline_fields)],
            deprecated_fields=[],
            source="static",
            saved_at=None,
            stale=False,
        )
    result = await session.execute(
        select(ReviewPromotion.approved_schema)
        .where(
            ReviewPromotion.domain == normalized_domain,
            ReviewPromotion.surface == surface,
        )
        .order_by(ReviewPromotion.created_at.desc(), ReviewPromotion.id.desc())
        .limit(1)
    )
    snapshot = result.scalar_one_or_none()
    return _snapshot_to_resolved(
        surface=surface,
        domain=normalized_domain,
        baseline_fields=baseline_fields,
        snapshot=snapshot if isinstance(snapshot, dict) else None,
        explicit_fields=normalized_explicit,
    )

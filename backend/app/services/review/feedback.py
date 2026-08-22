from __future__ import annotations

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.domain_memory import DomainCookieMemory, DomainFieldFeedback
from app.services.shared.field_coerce import safe_int


async def list_domain_field_feedback(
    session: AsyncSession,
    *,
    domain: str = "",
    surface: str = "",
    limit: int = 50,
) -> list[dict[str, object]]:
    statement = select(DomainFieldFeedback).order_by(
        desc(DomainFieldFeedback.created_at), desc(DomainFieldFeedback.id)
    )
    if domain:
        statement = statement.where(DomainFieldFeedback.domain == domain)
    if surface:
        statement = statement.where(DomainFieldFeedback.surface == surface)
    rows = list((await session.execute(statement.limit(max(1, limit)))).scalars().all())
    return [serialize_feedback_record(row) for row in rows]


async def domain_cookie_memory_exists(session: AsyncSession, *, domain: str) -> bool:
    result = await session.execute(
        select(DomainCookieMemory.id)
        .where(DomainCookieMemory.domain == domain)
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def latest_field_feedback_index(
    session: AsyncSession, *, domain: str, surface: str
) -> dict[tuple[str, str, str], DomainFieldFeedback]:
    rows = list(
        (
            await session.execute(
                select(DomainFieldFeedback)
                .where(
                    DomainFieldFeedback.domain == domain,
                    DomainFieldFeedback.surface == surface,
                )
                .order_by(
                    desc(DomainFieldFeedback.created_at), desc(DomainFieldFeedback.id)
                )
            )
        )
        .scalars()
        .all()
    )
    index: dict[tuple[str, str, str], DomainFieldFeedback] = {}
    for row in rows:
        payload = row.payload or {}
        key = (
            str(row.field_name or "").strip().lower(),
            str(payload.get("selector_kind") or "").strip(),
            str(row.source_value or "").strip(),
        )
        index.setdefault(key, row)
    return index


def serialize_feedback_row(row: DomainFieldFeedback) -> dict[str, object]:
    return {
        "action": row.action,
        "source_kind": row.source_kind,
        "source_value": row.source_value,
        "source_run_id": row.source_run_id,
        "created_at": row.created_at,
    }


def serialize_feedback_record(row: DomainFieldFeedback) -> dict[str, object]:
    payload = row.payload or {}
    return {
        "id": row.id,
        "domain": row.domain,
        "surface": row.surface,
        "field_name": row.field_name,
        "action": row.action,
        "source_kind": row.source_kind,
        "source_value": row.source_value,
        "source_run_id": row.source_run_id,
        "selector_kind": payload.get("selector_kind"),
        "selector_value": payload.get("selector_value"),
        "source_record_ids": [
            parsed
            for value in payload.get("source_record_ids") or []
            if (parsed := safe_int(value)) is not None
        ],
        "created_at": row.created_at,
    }

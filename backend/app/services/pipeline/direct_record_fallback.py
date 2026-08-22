from __future__ import annotations

import json
from typing import Awaitable, Callable

from app.models.crawl_run import CrawlRun
from app.services.confidence import score_record_confidence
from app.services.config.llm_runtime import llm_runtime_settings
from app.services.config.runtime_settings import crawler_runtime_settings
from app.services.domain_utils import normalize_domain
from app.services.field_policy import (
    field_allowed_for_surface,
    repair_target_fields_for_surface,
)
from app.services.db_utils import mapping_or_empty
from app.services.shared.field_coerce import (
    IMAGE_FIELDS,
    LONG_TEXT_FIELDS,
    STRUCTURED_MULTI_FIELDS,
    STRUCTURED_OBJECT_FIELDS,
    STRUCTURED_OBJECT_LIST_FIELDS,
    URL_FIELDS,
    coerce_field_value,
    finalize_record,
    strip_html_tags,
)
from app.services.llm.runtime import extract_missing_fields
from app.services.shared.coerce_primitives import string_list
from sqlalchemy.ext.asyncio import AsyncSession


ResolveRunConfigFn = Callable[..., Awaitable[dict[str, object] | None]]
ExtractRecordsFn = Callable[
    ..., Awaitable[tuple[list[dict[str, object]] | None, str | None]]
]


def _sanitize_llm_existing_values(record: dict[str, object]) -> dict[str, object]:
    sanitized: dict[str, object] = {}
    max_chars = max(1, int(llm_runtime_settings.existing_values_max_chars or 1))
    for key, value in record.items():
        if str(key).startswith("_"):
            continue
        if isinstance(value, str):
            truncated = value
            if "<" in truncated and ">" in truncated:
                truncated = strip_html_tags(truncated)
            truncated = truncated[:max_chars]
            sanitized[key] = truncated
        elif isinstance(value, (list, dict)):
            serialized = json.dumps(value, default=str)
            if len(serialized) > max_chars:
                serialized = serialized[:max_chars]
            sanitized[key] = serialized
        else:
            sanitized[key] = value
    return sanitized


_STRING_FIELDS = URL_FIELDS | IMAGE_FIELDS | LONG_TEXT_FIELDS
_LIST_FIELDS = STRUCTURED_MULTI_FIELDS | STRUCTURED_OBJECT_LIST_FIELDS
_DICT_FIELDS = STRUCTURED_OBJECT_FIELDS


def _validate_llm_field_type(field_name: str, value: object) -> bool:
    if value in (None, "", [], {}):
        return True
    normalized = str(field_name or "").strip().lower()
    if normalized in _STRING_FIELDS:
        return isinstance(value, str)
    if normalized in _LIST_FIELDS:
        return isinstance(value, list)
    if normalized in _DICT_FIELDS:
        return isinstance(value, dict)
    return True


async def apply_direct_record_llm_fallback(
    session: AsyncSession,
    *,
    run: CrawlRun,
    page_url: str,
    html: str,
    records: list[dict[str, object]],
    resolve_run_config_fn: ResolveRunConfigFn,
    extract_records_fn: ExtractRecordsFn,
) -> list[dict[str, object]]:
    if not records:
        return records
    if "detail" in str(run.surface or ""):
        return records
    domain = normalize_domain(page_url)
    requested_fields = repair_target_fields_for_surface(
        run.surface,
        run.requested_fields or [],
    )
    missing_by_record = [
        _missing_record_fields(record, surface=run.surface, fields=requested_fields)
        for record in records
    ]
    if not any(missing_by_record):
        return records
    config = await resolve_run_config_fn(
        session,
        run_id=run.id,
        task_type="direct_record_extraction",
    )
    if not config:
        return records
    candidates, _error_message = await extract_records_fn(
        session,
        run_id=run.id,
        domain=domain,
        url=page_url,
        surface=run.surface,
        html_text=html,
        requested_fields=requested_fields,
        existing_records=records,
    )
    if not candidates:
        return records

    updated_records: list[dict[str, object]] = []
    for index, record in enumerate(records):
        candidate = candidates[index] if index < len(candidates) else None
        next_record = _overlay_direct_candidate(
            record,
            candidate=candidate,
            missing_fields=missing_by_record[index],
            page_url=page_url,
        )
        updated_records.append(finalize_record(next_record, surface=run.surface))
    return updated_records


def _missing_record_fields(
    record: dict[str, object], *, surface: str, fields: list[str]
) -> list[str]:
    return [
        field_name
        for field_name in fields
        if field_allowed_for_surface(surface, field_name)
        and record.get(field_name) in (None, "", [], {})
    ]


def _overlay_direct_candidate(
    record: dict[str, object],
    *,
    candidate: object,
    missing_fields: list[str],
    page_url: str,
) -> dict[str, object]:
    updated = dict(record)
    if not isinstance(candidate, dict):
        return updated
    for field_name in missing_fields:
        value = candidate.get(field_name)
        if value in (None, "", [], {}) or not _validate_llm_field_type(
            field_name, value
        ):
            continue
        updated[field_name] = coerce_field_value(field_name, value, page_url)
    return updated


async def apply_llm_fallback(
    session: AsyncSession,
    *,
    run: CrawlRun,
    page_url: str,
    html: str,
    records: list[dict[str, object]],
) -> list[dict[str, object]]:
    updated_records: list[dict[str, object]] = []
    domain = normalize_domain(page_url)
    requested_fields = repair_target_fields_for_surface(
        run.surface,
        run.requested_fields or [],
    )
    for record in records:
        updated_records.append(
            await _apply_llm_to_record(
                session,
                run=run,
                domain=domain,
                page_url=page_url,
                html=html,
                record=record,
                requested_fields=requested_fields,
            )
        )
    return updated_records


async def _apply_llm_to_record(
    session: AsyncSession,
    *,
    run: CrawlRun,
    domain: str,
    page_url: str,
    html: str,
    record: dict[str, object],
    requested_fields: list[str],
) -> dict[str, object]:
    updated = dict(record)
    missing_fields = _missing_record_fields(
        updated, surface=run.surface, fields=requested_fields
    )
    if not missing_fields:
        return updated
    payload, error_message = await extract_missing_fields(
        session,
        run_id=run.id,
        domain=domain,
        url=page_url,
        html_text=html,
        missing_fields=missing_fields,
        existing_values=_sanitize_llm_existing_values(updated),
    )
    field_sources = mapping_or_empty(updated.get("_field_sources"))
    applied, rejected = _apply_llm_payload_fields(
        updated,
        payload=payload,
        field_sources=field_sources,
        surface=run.surface,
        page_url=page_url,
    )
    if applied:
        canonical = {
            key: value for key, value in updated.items() if not str(key).startswith("_")
        }
        updated.update(finalize_record(canonical, surface=run.surface))
    updated["_field_sources"] = field_sources
    updated["_confidence"] = score_record_confidence(
        updated, surface=run.surface, requested_fields=requested_fields
    )
    if applied and not str(updated.get("_source") or "").strip():
        updated["_source"] = "llm_missing_field_extraction"
    updated["_self_heal"] = {
        "enabled": True,
        "triggered": True,
        "threshold": crawler_runtime_settings.llm_confidence_threshold,
        "mode": "missing_field_extraction",
        "error": error_message or None,
        "rejected_fields": rejected or None,
    }
    return updated


def _apply_llm_payload_fields(
    record: dict[str, object],
    *,
    payload: object,
    field_sources: dict[str, object],
    surface: str,
    page_url: str,
) -> tuple[list[str], list[str]]:
    applied: list[str] = []
    rejected: list[str] = []
    if not isinstance(payload, dict):
        return applied, rejected
    for field_name, value in payload.items():
        normalized = str(field_name or "").strip().lower()
        if not normalized or not field_allowed_for_surface(surface, normalized):
            continue
        if record.get(normalized) not in (None, "", [], {}):
            continue
        coerced = coerce_field_value(normalized, value, page_url)
        if not _validate_llm_field_type(normalized, coerced):
            rejected.append(normalized)
            continue
        if coerced in (None, "", [], {}):
            continue
        record[normalized] = coerced
        applied.append(normalized)
        sources = string_list(field_sources.get(normalized))
        if "llm_missing_field_extraction" not in sources:
            sources.append("llm_missing_field_extraction")
        field_sources[normalized] = sources
    return applied, rejected

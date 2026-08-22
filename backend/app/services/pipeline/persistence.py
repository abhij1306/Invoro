from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass

from app.models.crawl_run import CrawlRecord, CrawlRun
from app.services.db_utils import mapping_or_empty
from app.services.shared.field_coerce import object_list as _object_list
from app.services.public_record_firewall import public_record_data_for_surface
from app.services.export.schema import build_source_trace
from app.services.artifact_store import (
    persist_html_artifact,
    persist_json_artifact,
    persist_png_artifact,
    persist_png_artifact_from_file,
    shape_browser_artifact,
)
from app.services.publish.metadata import refresh_record_commit_metadata
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


def _merge_browser_diagnostics(
    acquisition_result,
    diagnostics: dict[str, object],
) -> None:
    merged = mapping_or_empty(getattr(acquisition_result, "browser_diagnostics", {}))
    merged.update(dict(diagnostics or {}))
    acquisition_result.browser_diagnostics = merged


def _record_identity_key(source_url: str) -> str | None:
    text = str(source_url or "").strip()
    if not text:
        return None
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _record_content_fingerprint(
    data: dict[str, object],
    *,
    identity_source_url: str,
) -> str | None:
    identity_fields = ("gtin", "barcode", "sku", "mpn", "brand", "title")
    values = {
        field_name: _fingerprint_value(data.get(field_name))
        for field_name in identity_fields
        if _fingerprint_value(data.get(field_name)) not in (None, "", [], {})
    }
    if not values:
        values = {"url": _fingerprint_value(identity_source_url)}
    payload = json.dumps(
        values, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _fingerprint_value(value: object) -> object:
    if isinstance(value, str):
        return " ".join(value.casefold().split())
    if isinstance(value, list):
        return [
            item
            for item in (_fingerprint_value(item) for item in value)
            if item not in (None, "", [], {})
        ]
    if isinstance(value, dict):
        return {
            str(key): item
            for key, raw_item in sorted(value.items())
            if (item := _fingerprint_value(raw_item)) not in (None, "", [], {})
        }
    return value


def _stored_record_matches(
    row: CrawlRecord,
    *,
    source_url: str,
    data: dict[str, object],
    raw_data: dict[str, object],
    source_trace: dict[str, object],
    raw_html_path: str | None,
    content_fingerprint: str | None,
) -> bool:
    return (
        row.source_url == source_url
        and row.data == data
        and row.raw_data == raw_data
        and row.source_trace == source_trace
        and row.raw_html_path == raw_html_path
        and row.content_fingerprint == content_fingerprint
    )


def _update_stored_record(
    row: CrawlRecord,
    *,
    source_url: str,
    data: dict[str, object],
    raw_data: dict[str, object],
    discovered_data: dict[str, object],
    source_trace: dict[str, object],
    raw_html_path: str | None,
    content_fingerprint: str | None,
) -> None:
    row.source_url = source_url
    row.data = data
    row.raw_data = raw_data
    row.discovered_data = discovered_data
    row.source_trace = source_trace
    row.raw_html_path = raw_html_path
    row.content_fingerprint = content_fingerprint


async def persist_acquisition_artifacts(
    *,
    run_id: int,
    acquisition_result,
    browser_attempted: bool,
    screenshot_required: bool,
    surface: str | None = None,
    blocked: bool = False,
) -> str:
    raw_html_path = await asyncio.to_thread(
        persist_html_artifact,
        run_id=run_id,
        source_url=acquisition_result.final_url,
        html=acquisition_result.html,
    )
    if browser_attempted:
        await _persist_browser_artifacts(
            run_id=run_id,
            acquisition_result=acquisition_result,
            screenshot_required=screenshot_required,
            raw_html_path=raw_html_path,
            surface=surface,
            blocked=blocked,
        )
    return raw_html_path


async def _persist_browser_artifacts(
    *,
    run_id: int,
    acquisition_result,
    screenshot_required: bool,
    raw_html_path: str,
    surface: str | None = None,
    blocked: bool = False,
) -> None:
    diagnostics = mapping_or_empty(
        getattr(acquisition_result, "browser_diagnostics", {})
    )
    artifacts = dict(mapping_or_empty(getattr(acquisition_result, "artifacts", {})))
    screenshot_path_source = str(
        artifacts.pop("browser_screenshot_path", "") or ""
    ).strip()
    screenshot_bytes = artifacts.pop("browser_screenshot_png", b"")
    screenshot_path = ""
    if screenshot_required:
        if screenshot_path_source:
            screenshot_path = await asyncio.to_thread(
                persist_png_artifact_from_file,
                run_id=run_id,
                source_url=acquisition_result.final_url,
                suffix="browser",
                file_path=screenshot_path_source,
            )
        elif isinstance(screenshot_bytes, (bytes, bytearray)):
            screenshot_path = await asyncio.to_thread(
                persist_png_artifact,
                run_id=run_id,
                source_url=acquisition_result.final_url,
                suffix="browser",
                content=bytes(screenshot_bytes),
            )

    # Shape only the *saved* artifact (honest + lean). The in-memory diagnostics
    # dict is left untouched for downstream runtime consumers.
    diagnostics_payload = shape_browser_artifact(
        diagnostics,
        surface=surface,
        blocked=blocked,
    )
    diagnostics_payload["artifact_paths"] = {
        "html": raw_html_path or None,
        "screenshot": screenshot_path or None,
    }
    diagnostics_path = await asyncio.to_thread(
        persist_json_artifact,
        run_id=run_id,
        source_url=acquisition_result.final_url,
        suffix="browser",
        payload=diagnostics_payload,
    )
    _merge_browser_diagnostics(
        acquisition_result,
        {
            "artifact_paths": {
                "html": raw_html_path or None,
                "diagnostics": diagnostics_path or None,
                "screenshot": screenshot_path or None,
            }
        },
    )


async def persist_extracted_records(
    session: AsyncSession,
    run: CrawlRun,
    records: list[dict[str, object]],
    *,
    acquisition_result,
    raw_html_path: str | None = None,
) -> int:
    persisted = 0
    prepared_records = [
        (record, prepared)
        for record in records
        if (
            prepared := _prepare_record(
                record, run=run, acquisition_result=acquisition_result
            )
        )
        is not None
    ]
    identity_keys = {
        prepared.identity_key
        for _record, prepared in prepared_records
        if prepared.identity_key is not None
    }
    existing_records_by_identity = await _existing_records_by_identity(
        session, run=run, identity_keys=identity_keys
    )
    for record, prepared in prepared_records:
        existing_record = existing_records_by_identity.get(prepared.identity_key or "")
        if existing_record is not None:
            persisted += await _update_existing_record_if_changed(
                session,
                run=run,
                record=record,
                prepared=prepared,
                existing_record=existing_record,
                raw_html_path=raw_html_path,
            )
            continue
        crawl_record, inserted = await _insert_prepared_record(
            session,
            run=run,
            record=record,
            prepared=prepared,
            raw_html_path=raw_html_path,
        )
        if prepared.identity_key is not None:
            existing_records_by_identity[prepared.identity_key] = crawl_record
        if inserted:
            persisted += 1
        else:
            persisted += await _update_existing_record_if_changed(
                session,
                run=run,
                record=record,
                prepared=prepared,
                existing_record=crawl_record,
                raw_html_path=raw_html_path,
            )
    return persisted


@dataclass(frozen=True, slots=True)
class _PreparedRecord:
    source_url: str
    identity_key: str | None
    content_fingerprint: str | None
    data: dict[str, object]
    raw_data: dict[str, object]
    discovered_data: dict[str, object]
    source_trace: dict[str, object]


async def _existing_records_by_identity(
    session: AsyncSession, *, run: CrawlRun, identity_keys: set[str]
) -> dict[str, CrawlRecord]:
    if not identity_keys:
        return {}
    rows = await session.scalars(
        select(CrawlRecord).where(
            CrawlRecord.run_id == run.id,
            CrawlRecord.url_identity_key.in_(identity_keys),
        )
    )
    return {str(row.url_identity_key): row for row in rows if row.url_identity_key}


async def _insert_prepared_record(
    session: AsyncSession,
    *,
    run: CrawlRun,
    record: dict[str, object],
    prepared: _PreparedRecord,
    raw_html_path: str | None,
) -> tuple[CrawlRecord, bool]:
    crawl_record = CrawlRecord(
        run_id=run.id,
        source_url=prepared.source_url,
        url_identity_key=prepared.identity_key,
        content_fingerprint=prepared.content_fingerprint,
        data=prepared.data,
        raw_data=prepared.raw_data,
        discovered_data=prepared.discovered_data,
        source_trace=prepared.source_trace,
        raw_html_path=raw_html_path,
    )
    _refresh_record_metadata(crawl_record, run=run, record=record, data=prepared.data)
    if prepared.identity_key is None:
        session.add(crawl_record)
        await session.flush()
        return crawl_record, True
    try:
        async with session.begin_nested():
            session.add(crawl_record)
            await session.flush()
    except IntegrityError:
        existing_record = await session.scalar(
            select(CrawlRecord).where(
                CrawlRecord.run_id == run.id,
                CrawlRecord.url_identity_key == prepared.identity_key,
            )
        )
        if existing_record is None:
            raise
        return existing_record, False
    return crawl_record, True


def _prepare_record(
    record: dict[str, object], *, run: CrawlRun, acquisition_result
) -> _PreparedRecord | None:
    raw_record = dict(record)
    preliminary_url = str(raw_record.get("source_url") or acquisition_result.final_url)
    data, rejected_fields = public_record_data_for_surface(
        raw_record,
        surface=run.surface,
        page_url=preliminary_url,
        requested_fields=list(run.requested_fields or []),
    )
    if not data or _listing_record_requires_url(run, raw_record=raw_record, data=data):
        return None
    source_url = str(data.get("source_url") or acquisition_result.final_url)
    identity_source_url = str(data.get("url") or source_url)
    if rejected_fields:
        raw_record["_rejected_public_fields"] = rejected_fields
    discovered_data = _record_discovered_data(record)
    return _PreparedRecord(
        source_url=source_url,
        identity_key=_record_identity_key(identity_source_url),
        content_fingerprint=_record_content_fingerprint(
            data, identity_source_url=identity_source_url
        ),
        data=data,
        raw_data=raw_record,
        discovered_data=discovered_data,
        source_trace=build_source_trace(acquisition_result, raw_record, data=data),
    )


def _listing_record_requires_url(
    run: CrawlRun, *, raw_record: dict[str, object], data: dict[str, object]
) -> bool:
    table_row = (
        str(run.surface or "") == "content_listing"
        and raw_record.get("_extraction_mode") == "table_rows"
    )
    return "listing" in str(run.surface or "") and not data.get("url") and not table_row


def _record_discovered_data(record: dict[str, object]) -> dict[str, object]:
    values = {
        "confidence": mapping_or_empty(record.get("_confidence")),
        "field_repair": mapping_or_empty(record.get("_field_repair")),
        "manifest_trace": mapping_or_empty(record.get("_manifest_trace")),
        "semantic": mapping_or_empty(record.get("_semantic")),
        "review_bucket": _object_list(record.get("_review_bucket")),
    }
    return {
        key: value for key, value in values.items() if value not in (None, "", [], {})
    }


async def _update_existing_record_if_changed(
    session: AsyncSession,
    *,
    run: CrawlRun,
    record: dict[str, object],
    prepared: _PreparedRecord,
    existing_record: CrawlRecord | None,
    raw_html_path: str | None,
) -> int:
    if existing_record is None or _stored_record_matches(
        existing_record,
        source_url=prepared.source_url,
        data=prepared.data,
        raw_data=prepared.raw_data,
        source_trace=prepared.source_trace,
        raw_html_path=raw_html_path,
        content_fingerprint=prepared.content_fingerprint,
    ):
        return 0
    _update_stored_record(
        existing_record,
        source_url=prepared.source_url,
        data=prepared.data,
        raw_data=prepared.raw_data,
        discovered_data=dict(prepared.discovered_data),
        source_trace=prepared.source_trace,
        raw_html_path=raw_html_path,
        content_fingerprint=prepared.content_fingerprint,
    )
    _refresh_record_metadata(
        existing_record, run=run, record=record, data=prepared.data
    )
    await session.flush()
    return 1


def _refresh_record_metadata(
    crawl_record: CrawlRecord,
    *,
    run: CrawlRun,
    record: dict[str, object],
    data: dict[str, object],
) -> None:
    for field_name, value in data.items():
        refresh_record_commit_metadata(
            crawl_record,
            run=run,
            field_name=field_name,
            value=value,
            source_label=str(record.get("_source") or "extraction"),
            preserve_existing_sources=True,
        )

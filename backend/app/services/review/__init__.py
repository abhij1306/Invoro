# Review and promotion service.
from __future__ import annotations

from datetime import UTC, datetime

from app.models.domain_memory import DomainFieldFeedback
from app.models.crawl_run import CrawlRecord, CrawlRun
from app.models.review import ReviewPromotion
from app.services.db_utils import mapping_or_empty
from app.services.crawl.profile import (
    load_domain_run_profile,
    save_domain_run_profile,
)
from app.services.domain_utils import normalize_domain
from app.services.field_policy import normalize_field_key, normalize_review_target
from app.services.shared.field_coerce import (
    object_list as _object_list,
    safe_int as _safe_int,
)
from app.services.normalizers import normalize_value
from app.services.publish import (
    load_domain_field_mapping,
    refresh_record_commit_metadata,
)
from app.services.schema_service import load_resolved_schema
from app.services.review.record_content import (
    discovered_review_fields,
    found_review_fields,
    normalized_review_fields,
    render_review_html,
    review_bucket_rows,
)
from app.services.review.acquisition_evidence import derive_acquisition_info
from app.services.review.feedback import (
    domain_cookie_memory_exists,
    latest_field_feedback_index,
    list_domain_field_feedback as list_domain_field_feedback,
    serialize_feedback_row,
)
from app.services.selectors_runtime import (
    create_selector_record,
    list_selector_records,
    update_selector_record,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def build_review_payload(session: AsyncSession, run_id: int) -> dict | None:
    run = await session.get(CrawlRun, run_id)
    if run is None:
        return None
    records_result = await session.execute(
        select(CrawlRecord).where(CrawlRecord.run_id == run_id)
    )
    records = list(records_result.scalars().all())
    domain = normalize_domain(run.url)
    canonical_fields = (await load_resolved_schema(session, run.surface, domain)).fields
    domain_mapping = await load_domain_field_mapping(
        session,
        domain=domain,
        surface=run.surface,
    )
    normalized_fields = normalized_review_fields(records)
    discovered_fields = discovered_review_fields(records)
    suggested_mapping = {
        field: domain_mapping.get(field, field) for field in discovered_fields
    }
    return {
        "run": run,
        "records": records,
        "normalized_fields": normalized_fields,
        "discovered_fields": discovered_fields,
        "canonical_fields": canonical_fields,
        "domain_mapping": domain_mapping,
        "suggested_mapping": suggested_mapping,
    }


async def load_review_html(session: AsyncSession, run_id: int) -> str:
    run = await session.get(CrawlRun, run_id)
    if run is None:
        return ""
    records_result = await session.execute(
        select(CrawlRecord).where(CrawlRecord.run_id == run_id)
    )
    records = list(records_result.scalars().all())
    return render_review_html(records)


async def save_review(
    session: AsyncSession, run: CrawlRun, selections: list[dict]
) -> dict:
    domain = normalize_domain(run.url)
    mapping = _review_mapping(run.surface, selections)
    resolved_schema = await load_resolved_schema(session, run.surface, domain)
    updated_schema = _updated_review_schema(resolved_schema, run.surface, mapping)
    db_run = await session.get(CrawlRun, run.id)
    if db_run is None:
        raise RuntimeError(f"CrawlRun not found for review save: run_id={run.id}")
    saved_at = datetime.now(UTC).isoformat()
    promotion = ReviewPromotion(
        run_id=db_run.id,
        domain=domain,
        surface=db_run.surface,
        approved_schema={
            "fields": updated_schema.fields,
            "baseline_fields": updated_schema.baseline_fields,
            "new_fields": updated_schema.new_fields,
            "deprecated_fields": updated_schema.deprecated_fields,
            "source": updated_schema.source,
            "saved_at": saved_at,
        },
        field_mapping=mapping,
    )
    session.add(promotion)
    await _promote_review_bucket_fields(session, db_run, mapping)
    await session.commit()
    return {
        "run_id": run.id,
        "domain": domain,
        "surface": run.surface,
        "selected_fields": list(dict.fromkeys(mapping.values())),
        "canonical_fields": updated_schema.fields,
        "field_mapping": mapping,
    }


def _review_mapping(surface: str, selections: list[dict]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for row in selections:
        if not bool(row.get("selected", True)):
            continue
        source = normalize_field_key(row.get("source_field"))
        target = normalize_review_target(surface, row.get("output_field"))
        if source and target:
            mapping[source] = target
    return mapping


def _updated_review_schema(resolved_schema, surface: str, mapping: dict[str, str]):
    next_fields = [*resolved_schema.fields, *mapping.values()]
    normalized_baseline_fields = list(
        dict.fromkeys(
            normalized_field
            for field in resolved_schema.baseline_fields
            if (normalized_field := normalize_review_target(surface, field))
        )
    )
    normalized_new_fields = list(
        dict.fromkeys(
            normalized_field
            for field in resolved_schema.new_fields
            if (normalized_field := normalize_review_target(surface, field))
        )
    )
    normalized_baseline_field_set = set(normalized_baseline_fields)
    return resolved_schema.__class__(
        surface=resolved_schema.surface,
        domain=resolved_schema.domain,
        baseline_fields=normalized_baseline_fields,
        fields=list(dict.fromkeys(field for field in next_fields if field)),
        new_fields=list(
            dict.fromkeys(
                [
                    *normalized_new_fields,
                    *[
                        normalized_value
                        for value in mapping.values()
                        if (normalized_value := normalize_review_target(surface, value))
                        and normalized_value not in normalized_baseline_field_set
                    ],
                ]
            )
        ),
        deprecated_fields=list(resolved_schema.deprecated_fields),
        source="review",
        saved_at=None,
        stale=False,
    )


def _selector_signature(
    *,
    field_name: object,
    selector_kind: object,
    selector_value: object,
) -> tuple[str, str, str]:
    return (
        str(field_name or "").strip().lower(),
        str(selector_kind or "").strip().lower(),
        str(selector_value or "").strip(),
    )


def _saved_selector_signature(row: dict[str, object]) -> tuple[str, str, str]:
    if row.get("css_selector"):
        selector_kind = "css_selector"
        selector_value = row.get("css_selector")
    elif row.get("xpath"):
        selector_kind = "xpath"
        selector_value = row.get("xpath")
    else:
        selector_kind = "regex"
        selector_value = row.get("regex")
    return _selector_signature(
        field_name=row.get("field_name"),
        selector_kind=selector_kind,
        selector_value=selector_value,
    )


async def _promote_review_bucket_fields(
    session: AsyncSession, run: CrawlRun, mapping: dict[str, str]
) -> None:
    normalized_mapping = _normalized_review_mapping(mapping)
    if not normalized_mapping:
        return
    records_result = await session.execute(
        select(CrawlRecord).where(CrawlRecord.run_id == run.id)
    )
    for record in records_result.scalars().all():
        _promote_record_bucket(record, run=run, mapping=normalized_mapping)


def _normalized_review_mapping(mapping: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for source_field, target_field in mapping.items():
        source = normalize_field_key(source_field)
        target = normalize_field_key(target_field)
        if source and target:
            normalized[source] = target
    return normalized


def _promote_record_bucket(
    record: CrawlRecord, *, run: CrawlRun, mapping: dict[str, str]
) -> None:
    review_bucket = review_bucket_rows(record)
    if not review_bucket:
        return
    selected, remaining = _select_review_values(
        review_bucket,
        mapping=mapping,
        record_data=mapping_or_empty(record.data),
    )
    if not selected and len(remaining) == len(review_bucket):
        return
    data = dict(mapping_or_empty(record.data))
    for output_field, row in selected.items():
        data[output_field] = normalize_value(output_field, row.get("value"))
    record.data = data
    discovered = dict(mapping_or_empty(record.discovered_data))
    discovered["review_bucket"] = _remaining_review_rows(
        remaining, mapping=mapping, record_data=mapping_or_empty(record.data)
    )
    record.discovered_data = {
        key: value
        for key, value in discovered.items()
        if value not in (None, "", [], {})
    }
    for output_field in selected:
        refresh_record_commit_metadata(
            record,
            run=run,
            field_name=output_field,
            value=data[output_field],
            source_label="review_promotion",
        )


def _select_review_values(
    review_bucket: list[dict],
    *,
    mapping: dict[str, str],
    record_data: dict[str, object],
) -> tuple[dict[str, dict], list[dict]]:
    selected: dict[str, dict] = {}
    remaining: list[dict] = []
    for row in review_bucket:
        source_field = normalize_field_key(row.get("key"))
        output_field = mapping.get(source_field)
        if not source_field or not output_field:
            remaining.append(row)
        elif record_data.get(output_field) not in (None, "", [], {}):
            remaining.append(row)
        elif output_field not in selected:
            selected[output_field] = row
    return selected, remaining


def _remaining_review_rows(
    rows: list[dict],
    *,
    mapping: dict[str, str],
    record_data: dict[str, object],
) -> list[dict]:
    mapped_sources = set(mapping)
    return [
        row
        for row in rows
        if (key := normalize_field_key(row.get("key"))) not in mapped_sources
        or record_data.get(mapping.get(key, "")) not in (None, "", [], {})
    ]


def _collect_selector_candidates(
    records: list[CrawlRecord],
    *,
    saved_selectors: list[dict[str, object]],
    run: CrawlRun,
    feedback_index: dict[tuple[str, str, str], DomainFieldFeedback],
) -> tuple[dict[str, dict[str, object]], dict[tuple[str, str, str], dict[str, object]]]:
    saved_index = {_saved_selector_signature(row): row for row in saved_selectors}
    candidates: dict[str, dict[str, object]] = {}
    learning: dict[tuple[str, str, str], dict[str, object]] = {}
    for record in records:
        discovery = mapping_or_empty(
            mapping_or_empty(record.source_trace).get("field_discovery")
        )
        for field_name, raw_payload in discovery.items():
            payload = raw_payload if isinstance(raw_payload, dict) else {}
            trace = mapping_or_empty(payload.get("selector_trace"))
            kind = str(trace.get("selector_kind") or "").strip()
            value = str(trace.get("selector_value") or "").strip()
            labels = [
                str(item)
                for item in payload.get("sources") or []
                if str(item or "").strip()
            ]
            _add_field_learning(
                learning,
                feedback_index=feedback_index,
                record=record,
                field_name=field_name,
                payload=payload,
                selector_kind=kind,
                selector_value=value,
                source_labels=labels,
            )
            _add_selector_candidate(
                candidates,
                saved_index=saved_index,
                record=record,
                run=run,
                field_name=field_name,
                payload=payload,
                trace=trace,
                selector_kind=kind,
                selector_value=value,
            )
    if candidates:
        return candidates, learning
    return _fallback_selector_candidates(saved_selectors, run=run), learning


def _add_field_learning(
    learning: dict[tuple[str, str, str], dict[str, object]],
    *,
    feedback_index: dict[tuple[str, str, str], DomainFieldFeedback],
    record: CrawlRecord,
    field_name: object,
    payload: dict[str, object],
    selector_kind: str,
    selector_value: str,
    source_labels: list[str],
) -> None:
    found_xpath = (
        payload.get("status") == "found"
        and payload.get("value") not in (None, "", [], {})
        and selector_kind == "xpath"
        and bool(selector_value)
    )
    if not found_xpath:
        return
    key = (
        str(field_name or "").strip().lower(),
        selector_kind,
        selector_value or (source_labels[-1] if source_labels else ""),
    )
    feedback = feedback_index.get(key)
    entry = learning.setdefault(
        key,
        {
            "field_name": key[0],
            "value": payload.get("value"),
            "source_labels": source_labels,
            "selector_kind": selector_kind or None,
            "selector_value": selector_value or None,
            "source_record_ids": [],
            "feedback": serialize_feedback_row(feedback)
            if feedback is not None
            else None,
        },
    )
    entry["source_record_ids"] = _merged_record_ids(entry, record.id)


def _add_selector_candidate(
    candidates: dict[str, dict[str, object]],
    *,
    saved_index: dict[tuple[str, str, str], dict[str, object]],
    record: CrawlRecord,
    run: CrawlRun,
    field_name: object,
    payload: dict[str, object],
    trace: dict[str, object],
    selector_kind: str,
    selector_value: str,
) -> None:
    if not selector_kind or not selector_value:
        return
    field = str(field_name or "").strip().lower()
    key = f"{field_name}|{selector_kind}|{selector_value}"
    saved = saved_index.get(
        _selector_signature(
            field_name=field_name,
            selector_kind=selector_kind,
            selector_value=selector_value,
        )
    )
    sources = _object_list(payload.get("sources"))
    entry = candidates.setdefault(
        key,
        {
            "candidate_key": key,
            "field_name": field,
            "selector_kind": selector_kind,
            "selector_value": selector_value,
            "selector_source": str(trace.get("selector_source") or ""),
            "sample_value": trace.get("sample_value") or payload.get("value"),
            "source_record_ids": [],
            "source_run_id": trace.get("source_run_id") or run.id,
            "saved_selector_id": saved.get("id") if isinstance(saved, dict) else None,
            "already_saved": isinstance(saved, dict),
            "final_field_source": sources[-1] if sources else None,
        },
    )
    entry["source_record_ids"] = _merged_record_ids(entry, record.id)


def _merged_record_ids(entry: dict[str, object], record_id: object) -> list[int]:
    return sorted(
        {
            parsed
            for value in [*_object_list(entry.get("source_record_ids")), record_id]
            if (parsed := _safe_int(value)) is not None
        }
    )


def _fallback_selector_candidates(
    saved_selectors: list[dict[str, object]], *, run: CrawlRun
) -> dict[str, dict[str, object]]:
    saved_index = {_saved_selector_signature(row): row for row in saved_selectors}
    candidates: dict[str, dict[str, object]] = {}
    for row in [*saved_selectors, *run.settings_view.extraction_contract()]:
        field_name = str(row.get("field_name") or "").strip().lower()
        selector_value = str(row.get("css_selector") or "").strip()
        if not field_name or not selector_value:
            continue
        key = f"{field_name}|css_selector|{selector_value}"
        saved = saved_index.get(
            _selector_signature(
                field_name=field_name,
                selector_kind="css_selector",
                selector_value=selector_value,
            )
        )
        candidates[key] = {
            "candidate_key": key,
            "field_name": field_name,
            "selector_kind": "css_selector",
            "selector_value": selector_value,
            "selector_source": str(row.get("source") or "run_contract"),
            "sample_value": row.get("sample_value"),
            "source_record_ids": [],
            "source_run_id": row.get("source_run_id") or run.id,
            "saved_selector_id": saved.get("id") if isinstance(saved, dict) else None,
            "already_saved": isinstance(saved, dict),
            "final_field_source": None,
        }
    return candidates


async def build_domain_recipe_payload(
    session: AsyncSession,
    *,
    run: CrawlRun,
) -> dict[str, object]:
    records = list(
        (
            await session.execute(
                select(CrawlRecord)
                .where(CrawlRecord.run_id == run.id)
                .order_by(CrawlRecord.id.asc())
            )
        )
        .scalars()
        .all()
    )
    domain = normalize_domain(run.url)
    saved_selectors = await list_selector_records(
        session, domain=domain, surface=run.surface
    )
    requested_fields = [
        str(value) for value in run.requested_fields or [] if str(value or "").strip()
    ]
    found_fields = found_review_fields(records, requested_fields=requested_fields)
    feedback_index = await latest_field_feedback_index(
        session, domain=domain, surface=run.surface
    )
    selector_candidates, field_learning = _collect_selector_candidates(
        records,
        saved_selectors=saved_selectors,
        run=run,
        feedback_index=feedback_index,
    )
    acquisition = derive_acquisition_info(records, run=run)
    saved_profile = await load_domain_run_profile(
        session, domain=domain, surface=run.surface
    )
    cookie_memory_exists = await domain_cookie_memory_exists(session, domain=domain)
    return {
        "run_id": run.id,
        "domain": domain,
        "surface": run.surface,
        "requested_field_coverage": _requested_field_coverage(
            requested_fields, found_fields=found_fields
        ),
        "acquisition_evidence": {
            "actual_fetch_method": acquisition["actual_fetch_method"],
            "browser_used": acquisition["actual_fetch_method"] == "browser",
            "browser_reason": acquisition["browser_reason"],
            "acquisition_summary": acquisition["acquisition_summary"],
            "cookie_memory_available": cookie_memory_exists,
        },
        "field_learning": _sorted_recipe_rows(field_learning.values()),
        "selector_candidates": _sorted_recipe_rows(selector_candidates.values()),
        "affordance_candidates": acquisition["affordance_candidates"],
        "saved_selectors": saved_selectors,
        "saved_run_profile": dict(saved_profile.profile or {})
        if saved_profile
        else None,
    }


def _requested_field_coverage(
    requested_fields: list[str], *, found_fields: list[str]
) -> dict[str, list[str]]:
    found_set = set(found_fields)
    return {
        "requested": requested_fields,
        "found": [field for field in requested_fields if field in found_set],
        "missing": [field for field in requested_fields if field not in found_set],
    }


def _sorted_recipe_rows(rows) -> list[dict[str, object]]:
    return sorted(
        rows,
        key=lambda row: (
            str(row.get("field_name") or ""),
            str(row.get("selector_kind") or ""),
            str(row.get("selector_value") or ""),
        ),
    )


async def promote_domain_recipe_selectors(
    session: AsyncSession,
    *,
    run: CrawlRun,
    selectors: list[dict[str, object]],
    commit: bool = True,
) -> list[dict[str, object]]:
    domain = normalize_domain(run.url)
    existing = await list_selector_records(
        session,
        domain=domain,
        surface=run.surface,
    )
    by_signature = {_saved_selector_signature(row): row for row in existing}
    saved_rows: list[dict[str, object]] = []
    for row in selectors:
        normalized = _normalized_recipe_selector(row, run_id=run.id)
        if normalized is None:
            continue
        signature, payload = normalized
        selector_id = _existing_selector_id(by_signature.get(signature))
        if selector_id is not None:
            updated_row = await update_selector_record(
                session,
                selector_id=selector_id,
                payload=payload,
                commit=commit,
            )
            if updated_row is not None:
                saved_rows.append(updated_row)
            continue
        created_row = await create_selector_record(
            session,
            domain=domain,
            surface=run.surface,
            payload=payload,
            commit=commit,
        )
        if created_row is not None:
            saved_rows.append(created_row)
    return [row for row in saved_rows if isinstance(row, dict)]


def _normalized_recipe_selector(
    row: dict[str, object], *, run_id: int
) -> tuple[tuple[str, str, str], dict[str, object]] | None:
    selector_kind = str(row.get("selector_kind") or "").strip()
    selector_value = str(row.get("selector_value") or "").strip()
    field_name = normalize_field_key(str(row.get("field_name") or ""))
    if not all((field_name, selector_kind, selector_value)):
        return None
    payload = {
        "field_name": field_name,
        "css_selector": selector_value if selector_kind == "css_selector" else None,
        "xpath": selector_value if selector_kind == "xpath" else None,
        "regex": selector_value if selector_kind == "regex" else None,
        "sample_value": row.get("sample_value"),
        "source": "domain_recipe",
        "source_run_id": run_id,
        "status": "validated",
        "is_active": True,
    }
    signature = _selector_signature(
        field_name=field_name,
        selector_kind=selector_kind,
        selector_value=selector_value,
    )
    return signature, payload


def _existing_selector_id(row: object) -> int | None:
    if not isinstance(row, dict):
        return None
    return _safe_int(row.get("id"))


async def save_domain_recipe_run_profile(
    session: AsyncSession,
    *,
    run: CrawlRun,
    profile: dict[str, object],
) -> dict[str, object]:
    return await save_domain_run_profile(
        session,
        domain=normalize_domain(run.url),
        surface=run.surface,
        profile=profile,
        source_run_id=run.id,
        commit=True,
    )


async def apply_domain_recipe_field_action(
    session: AsyncSession,
    *,
    run: CrawlRun,
    action: dict[str, object],
) -> dict[str, object]:
    field_name = normalize_field_key(str(action.get("field_name") or ""))
    action_name = str(action.get("action") or "").strip().lower()
    selector_kind = str(action.get("selector_kind") or "").strip().lower()
    selector_value = str(action.get("selector_value") or "").strip()
    if not field_name or action_name not in {"keep", "reject"}:
        raise ValueError("Invalid domain recipe field action.")
    try:
        await _apply_selector_feedback_action(
            session,
            run=run,
            action_name=action_name,
            field_name=field_name,
            selector_kind=selector_kind,
            selector_value=selector_value,
        )
        feedback = DomainFieldFeedback(
            domain=normalize_domain(run.url),
            surface=run.surface,
            field_name=field_name,
            action=action_name,
            source_kind="selector"
            if selector_kind and selector_value
            else "field_source",
            source_value=selector_value or None,
            source_run_id=run.id,
            payload={
                "selector_kind": selector_kind or None,
                "selector_value": selector_value or None,
                "source_record_ids": _feedback_record_ids(action),
            },
        )
        session.add(feedback)
        await session.commit()
        await session.refresh(feedback)
        return serialize_feedback_row(feedback)
    except Exception:
        await session.rollback()
        raise


async def _apply_selector_feedback_action(
    session: AsyncSession,
    *,
    run: CrawlRun,
    action_name: str,
    field_name: str,
    selector_kind: str,
    selector_value: str,
) -> None:
    if not selector_kind or not selector_value:
        return
    if action_name == "keep":
        await promote_domain_recipe_selectors(
            session,
            run=run,
            selectors=[
                {
                    "field_name": field_name,
                    "selector_kind": selector_kind,
                    "selector_value": selector_value,
                }
            ],
            commit=False,
        )
        return
    await _reject_domain_selector(
        session,
        run=run,
        field_name=field_name,
        selector_kind=selector_kind,
        selector_value=selector_value,
    )


async def _reject_domain_selector(
    session: AsyncSession,
    *,
    run: CrawlRun,
    field_name: str,
    selector_kind: str,
    selector_value: str,
) -> None:
    existing = await list_selector_records(
        session, domain=normalize_domain(run.url), surface=run.surface
    )
    for row in existing:
        if not _selector_row_matches(
            row,
            field_name=field_name,
            selector_kind=selector_kind,
            selector_value=selector_value,
        ):
            continue
        selector_id = _safe_int(row.get("id"))
        if selector_id is not None:
            await update_selector_record(
                session,
                selector_id=selector_id,
                payload={"is_active": False},
                commit=False,
            )
        return


def _selector_row_matches(
    row: dict[str, object],
    *,
    field_name: str,
    selector_kind: str,
    selector_value: str,
) -> bool:
    field_key = {
        "css_selector": "css_selector",
        "xpath": "xpath",
    }.get(selector_kind, "regex")
    return (
        normalize_field_key(str(row.get("field_name") or "")) == field_name
        and str(row.get(field_key) or "").strip() == selector_value
        and row.get("id") is not None
    )


def _feedback_record_ids(action: dict[str, object]) -> list[int]:
    return [
        parsed
        for value in _object_list(action.get("source_record_ids"))
        if (parsed := _safe_int(value)) is not None
    ]

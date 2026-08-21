from __future__ import annotations

from ._support_shared import *  # noqa: F403
from .challenge_classifier import (
    _challenge_summary_from_diagnostics,
    classify_failure_mode,
)
from .harness_user import _ensure_harness_user_id
from .record_signals import (
    _identity_path,
    _looks_like_utility_record,
    _looks_numeric_price,
    _object_dict,
    _object_list,
    _safe_int,
    _summary_value,
    _variant_row_has_axis,
)


def status_for_result(result: dict[str, object]) -> str:
    if "ok" in result:
        return "PASS" if bool(result.get("ok")) else "FAIL"
    return "PASS" if classify_failure_mode(result) == "success" else "FAIL"


async def run_site_harness(*, url: str, surface: str, mode: str) -> dict[str, object]:
    async with SessionLocal() as session:
        run = await create_crawl_run(
            session,
            await _ensure_harness_user_id(session),
            {
                "run_type": "crawl",
                "url": url,
                "surface": surface,
                "settings": {"max_pages": 5, "max_scrolls": 5},
            },
        )
        if mode == HARNESS_MODE_FULL_PIPELINE:
            await process_run(session, run.id)
            await session.refresh(run)
            rows, total_records = await get_run_records(session, run.id, 1, 100)
            return _persisted_run_result(
                run=run,
                rows=rows,
                total_records=total_records,
                requested_url=url,
                run_source="live_run",
            )
        url_result = await process_single_url(
            session=session,
            run=run,
            url=url,
            config=URLProcessingConfig.from_acquisition_plan(
                run.settings_view.acquisition_plan(surface=surface),
                update_run_state=False,
                persist_logs=False,
                prefetch_only=True,
            ),
        )
        metrics = dict(url_result.url_metrics or {})
        challenge_summary = _challenge_summary_from_diagnostics(
            dict(metrics.get("browser_diagnostics") or {})
        )
        return {
            "run_id": run.id,
            "status": run.status,
            "requested_url": url,
            "verdict": str(url_result.verdict or ""),
            "method": str(metrics.get("method") or "").strip() or None,
            "platform_family": str(metrics.get("platform_family") or "").strip()
            or None,
            "status_code": metrics.get("status_code"),
            "blocked": bool(metrics.get("blocked")),
            "browser_diagnostics": dict(metrics.get("browser_diagnostics") or {}),
            "records": int(metrics.get("record_count", 0) or 0),
            "sample_title": "",
            "populated_fields": 0,
            "challenge_summary": challenge_summary,
            "run_source": "live_run",
            "error": str(metrics.get("error") or "").strip() or None,
        }


async def review_saved_run(
    *,
    run_id: int,
    requested_url: str | None = None,
) -> dict[str, object]:
    async with SessionLocal() as session:
        run = (
            await session.execute(
                select(CrawlRun).where(CrawlRun.id == int(run_id)).limit(1)
            )
        ).scalar_one_or_none()
        if run is None:
            raise RuntimeError(f"Saved harness run {run_id} was not found")
        rows, total_records = await get_run_records(session, run.id, 1, 100)
        return _persisted_run_result(
            run=run,
            rows=rows,
            total_records=total_records,
            requested_url=str(requested_url or run.url or "").strip(),
            run_source="artifact_review",
        )


def _populated_field_count(record: dict[str, object]) -> int:
    return sum(
        1
        for key, value in record.items()
        if value not in (None, "", [], {}) and not str(key).startswith("_")
    )


def _sample_records(rows: Sequence[object]) -> list[dict[str, object]]:
    samples: list[dict[str, object]] = []
    for row in (rows or [])[:3]:
        data = dict(getattr(row, "data", {}) or {})
        samples.append(
            {
                "title": str(data.get("title") or "")[:160],
                "url": str(data.get("url") or "")[:240],
                "populated_fields": _populated_field_count(data),
                "price_present": data.get("price") not in (None, "", [], {}),
            }
        )
    return samples


def _sample_record_audit(sample_records: list[dict[str, object]]) -> dict[str, object]:
    coverage_values = [
        _safe_int(row.get("populated_fields"))
        for row in sample_records
        if isinstance(row, dict)
    ]
    utility_hits = [
        index
        for index, row in enumerate(sample_records, start=1)
        if isinstance(row, dict)
        and _looks_like_utility_record(
            title=row.get("title"),
            url=row.get("url"),
        )
    ]
    return {
        "field_coverage": {
            "avg_populated_fields": round(
                sum(coverage_values) / max(1, len(coverage_values)), 2
            ),
            "max_populated_fields": max(coverage_values, default=0),
            "min_populated_fields": min(coverage_values, default=0),
        },
        "utility_noise_hits": utility_hits,
        "looks_like_utility_chrome": bool(utility_hits),
    }


def _persisted_run_result(
    *,
    run: CrawlRun,
    rows: Sequence[object],
    total_records: int,
    requested_url: str,
    run_source: str,
) -> dict[str, object]:
    first = rows[0] if rows else None
    first_data = getattr(first, "data", {}) if first is not None else {}
    first_trace = getattr(first, "source_trace", {}) if first is not None else {}
    data = _object_dict(first_data)
    acquisition = _object_dict(_object_dict(first_trace).get("acquisition"))
    summary = run.summary_dict()
    sample_records = _sample_records(rows)
    sample_audit = _sample_record_audit(sample_records)
    challenge_summary = _challenge_summary_from_diagnostics(
        _object_dict(acquisition.get("browser_diagnostics"))
    )
    return {
        "run_id": run.id,
        "status": run.status,
        "requested_url": requested_url,
        "verdict": str(summary.get("extraction_verdict") or ""),
        "method": _summary_value(summary, "methods"),
        "platform_family": _summary_value(summary, "platform_families"),
        "status_code": acquisition.get("status_code"),
        "blocked": bool(acquisition.get("blocked")),
        "browser_diagnostics": _object_dict(acquisition.get("browser_diagnostics")),
        "records": max(total_records, _safe_int(summary.get("record_count"))),
        "sample_title": str(data.get("title") or "")[:120],
        "sample_url": str(data.get("url") or "")[:240],
        "sample_record_data": data,
        "sample_source_trace": _object_dict(first_trace),
        "sample_records": sample_records,
        "sample_semantics": _sample_semantics(data),
        "listing_contract": _listing_contract(rows),
        "populated_fields": _populated_field_count(data),
        "sample_field_coverage": sample_audit["field_coverage"],
        "sample_utility_noise_hits": sample_audit["utility_noise_hits"],
        "sample_looks_like_utility_chrome": sample_audit["looks_like_utility_chrome"],
        "challenge_summary": challenge_summary,
        "run_source": run_source,
        "error": str(summary.get("error") or "").strip() or None,
    }


def _sample_semantics(record: dict[str, object]) -> dict[str, object]:
    variants = [
        row for row in _object_list(record.get("variants")) if isinstance(row, dict)
    ]
    variant_rows_with_axes = sum(1 for row in variants if _variant_row_has_axis(row))
    variant_rows_with_price = sum(
        1 for row in variants if row.get("price") not in (None, "", [], {})
    )
    return {
        "price_present": record.get("price") not in (None, "", [], {}),
        "currency_present": record.get("currency") not in (None, "", [], {}),
        "variant_count": max(_safe_int(record.get("variant_count")), len(variants)),
        "variants_with_axes_count": variant_rows_with_axes,
        "variants_all_have_axes": bool(variants)
        and variant_rows_with_axes == len(variants),
        "variants_with_price_count": variant_rows_with_price,
        "legacy_variant_keys_present": any(
            record.get(field_name) not in (None, "", [], {})
            for field_name in _PUBLIC_RECORD_LEGACY_VARIANT_FIELDS
        ),
    }


def _listing_contract(rows: Sequence[object]) -> dict[str, object]:
    detail_url_count = 0
    price_present_count = 0
    numeric_price_count = 0
    sampled = 0
    for row in rows or []:
        data = dict(getattr(row, "data", {}) or {})
        sampled += 1
        row_url = str(data.get("url") or "").strip()
        if row_url and not _looks_like_utility_record(
            title=data.get("title"), url=row_url
        ):
            detail_url_count += 1
        if data.get("price") not in (None, "", [], {}):
            price_present_count += 1
            if _looks_numeric_price(data.get("price")):
                numeric_price_count += 1
    return {
        "sampled_records": sampled,
        "detail_url_count": detail_url_count,
        "detail_urls_present": detail_url_count > 0,
        "price_present_count": price_present_count,
        "price_numeric_count": numeric_price_count,
    }


__all__ = tuple(name for name in globals() if not name.startswith("__"))

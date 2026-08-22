from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crawl_run import CrawlRecord, CrawlRun
from app.models.playground import PlaygroundSession
from app.services.config.data_enrichment import DATA_ENRICHMENT_JOB_TERMINAL_STATUSES
from app.services.config.product_intelligence import (
    PRODUCT_INTELLIGENCE_JOB_STATUS_COMPLETE,
    PRODUCT_INTELLIGENCE_JOB_STATUS_FAILED,
)
from app.services.crawl.state import TERMINAL_STATUSES

max_products = 50
pi_terminal_statuses = {
    PRODUCT_INTELLIGENCE_JOB_STATUS_COMPLETE,
    PRODUCT_INTELLIGENCE_JOB_STATUS_FAILED,
}
enrich_terminal_statuses = set(DATA_ENRICHMENT_JOB_TERMINAL_STATUSES)


async def get_results(
    session: AsyncSession, *, playground: PlaygroundSession
) -> dict[str, Any]:
    step_data = dict(playground.step_data or {})
    results: dict[str, Any] = {
        "state": playground.state,
        "input_url": playground.input_url,
        "steps": {},
    }
    discover = step_data.get("discover", {})
    if discover:
        results["steps"]["discover"] = {
            "status": discover.get("status"),
            "total_found": discover.get("total_found", 0),
            "products": discover.get("products", []),
        }
    results["steps"]["selected_urls"] = step_data.get("selected_urls", [])
    extract = step_data.get("extract", {})
    if extract:
        records = await extract_records(session, extract_run_ids(step_data))
        results["steps"]["extract"] = {
            "status": extract.get("status"),
            "run_id": extract.get("run_id"),
            "run_ids": extract_run_ids(step_data),
            "url_count": extract.get("url_count", 0),
            "record_count": len(records),
            "records": records,
        }
    for key in ("enrich", "compare", "monitor"):
        if key in step_data:
            results["steps"][key] = step_data[key]
    return results


async def auto_advance(session: AsyncSession, playground: PlaygroundSession) -> None:
    handlers = {
        "discovering": advance_discovery,
        "extracting": advance_extraction,
        "running_pipeline": advance_pipeline,
    }
    handler = handlers.get(playground.state)
    if handler is not None:
        await handler(session, playground)


async def advance_discovery(
    session: AsyncSession, playground: PlaygroundSession
) -> None:
    step_data = dict(playground.step_data or {})
    run_id = step_data.get("discover", {}).get("run_id")
    if not run_id:
        return
    run = await session.get(CrawlRun, run_id)
    if run is None or run.status not in {status.value for status in TERMINAL_STATUSES}:
        return
    products = await extract_discovered_products(session, run_id)
    products = merge_seed_detail_products(step_data, products)
    step_data["discover"] = {
        **step_data.get("discover", {}),
        "status": "completed",
        "products": products[:max_products],
        "total_found": len(products),
    }
    playground.state = "discovered"
    playground.step_data = step_data


async def advance_extraction(
    session: AsyncSession, playground: PlaygroundSession
) -> None:
    step_data = dict(playground.step_data or {})
    extract_info = step_data.get("extract", {}) or {}
    runs = await resolve_extract_runs(
        session, playground=playground, step_data=step_data
    )
    run_ids = [int(run.id) for run in runs]
    if run_ids:
        step_data["extract"] = {
            **extract_info,
            "run_id": run_ids[0],
            "run_ids": run_ids,
        }
        extract_info = step_data["extract"]
    if len(run_ids) < expected_extract_run_count(step_data):
        return
    terminal = {status.value for status in TERMINAL_STATUSES}
    if not run_ids or not all(str(run.status) in terminal for run in runs):
        return
    step_data["extract"] = {**extract_info, "status": "completed"}
    playground.state = "extracted"
    playground.step_data = step_data


async def advance_pipeline(
    session: AsyncSession, playground: PlaygroundSession
) -> None:
    step_data = dict(playground.step_data or {})
    mutated = False
    for key, refresher in (
        ("enrich", refresh_enrich_status),
        ("compare", refresh_compare_status),
    ):
        info = step_data.get(key)
        if not isinstance(info, dict) or not info:
            continue
        updated = await refresher(session, info)
        if updated is not None and updated != info:
            step_data[key] = updated
            mutated = True
    running = any(
        isinstance(step_data.get(key), dict)
        and step_data[key].get("status") == "running"
        for key in ("enrich", "compare")
    )
    if not running:
        playground.state = "complete"
        mutated = True
    if mutated:
        playground.step_data = step_data


async def refresh_enrich_status(
    session: AsyncSession, info: dict[str, Any]
) -> dict[str, Any] | None:
    job_id = info.get("job_id")
    if not isinstance(job_id, int):
        return None
    from app.models.data_enrichment import DataEnrichmentJob

    job = await session.get(DataEnrichmentJob, job_id)
    status = str(job.status or "").strip().lower() if job is not None else ""
    return {**info, "status": status} if status in enrich_terminal_statuses else None


async def refresh_compare_status(
    session: AsyncSession, info: dict[str, Any]
) -> dict[str, Any] | None:
    job_id = info.get("job_id")
    if not isinstance(job_id, int):
        return None
    from app.models.product_intelligence import ProductIntelligenceJob

    job = await session.get(ProductIntelligenceJob, job_id)
    status = str(job.status or "").strip().lower() if job is not None else ""
    return {**info, "status": status} if status in pi_terminal_statuses else None


async def extract_discovered_products(
    session: AsyncSession, run_id: int
) -> list[dict[str, Any]]:
    rows = await session.scalars(
        select(CrawlRecord).where(CrawlRecord.run_id == run_id).limit(max_products)
    )
    products = []
    for record in rows.all():
        data = record.data or {}
        product_url = next(
            (
                value
                for key in ("url", "product_url", "detail_url", "canonical_url")
                if (value := data.get(key))
            ),
            record.source_url,
        )
        if product_url:
            products.append(
                {
                    "url": str(product_url),
                    "title": str(data.get("title") or ""),
                    "brand": str(data.get("brand") or ""),
                    "price": str(data.get("price") or ""),
                    "image": str(data.get("image") or data.get("image_url") or ""),
                }
            )
    return products


def merge_seed_detail_products(
    step_data: dict[str, Any], discovered_products: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    seeds = (
        {
            "url": str(url or "").strip(),
            "title": "",
            "brand": "",
            "price": "",
            "image": "",
        }
        for url in step_data.get("seed_detail_urls", []) or []
    )
    for product in (*seeds, *discovered_products):
        url = str(product.get("url") or "").strip()
        if url and url not in seen:
            merged.append(product)
            seen.add(url)
    return merged


def extract_run_ids(step_data: dict[str, Any]) -> list[int]:
    extract = step_data.get("extract", {}) or {}
    raw_run_ids = extract.get("run_ids")
    if isinstance(raw_run_ids, list):
        run_ids = [
            value for value in raw_run_ids if isinstance(value, int) and value > 0
        ]
        if run_ids:
            return run_ids
    run_id = extract.get("run_id")
    return [run_id] if isinstance(run_id, int) and run_id > 0 else []


async def extract_record_ids(session: AsyncSession, run_ids: list[int]) -> list[int]:
    if not run_ids:
        return []
    rows = await session.scalars(
        select(CrawlRecord.id)
        .where(CrawlRecord.run_id.in_(run_ids))
        .order_by(CrawlRecord.run_id.asc(), CrawlRecord.id.asc())
    )
    return [int(record_id) for record_id in rows.all() if record_id is not None]


async def extract_records(
    session: AsyncSession, run_ids: list[int]
) -> list[dict[str, Any]]:
    if not run_ids:
        return []
    rows = await session.scalars(
        select(CrawlRecord)
        .where(CrawlRecord.run_id.in_(run_ids))
        .order_by(CrawlRecord.run_id.asc(), CrawlRecord.id.asc())
    )
    return [
        {
            "id": int(record.id),
            "run_id": int(record.run_id),
            "source_url": str(record.source_url),
            "data": dict(record.data or {}),
        }
        for record in rows.all()
    ]


def extract_selected_urls(step_data: dict[str, Any]) -> list[str]:
    values = step_data.get("selected_urls")
    if not isinstance(values, list):
        return []
    return [
        value.strip() for value in values if isinstance(value, str) and value.strip()
    ]


def expected_extract_run_count(step_data: dict[str, Any]) -> int:
    extract = step_data.get("extract", {}) or {}
    url_count = extract.get("url_count")
    expected = max(
        len(extract_selected_urls(step_data)),
        url_count if isinstance(url_count, int) and url_count > 0 else 0,
    )
    return expected or len(extract_run_ids(step_data))


async def resolve_extract_runs(
    session: AsyncSession,
    *,
    playground: PlaygroundSession,
    step_data: dict[str, Any],
) -> list[CrawlRun]:
    resolved = await runs_by_ids(session, extract_run_ids(step_data))
    selected_urls = extract_selected_urls(step_data)
    if selected_urls:
        rows = await session.scalars(
            select(CrawlRun)
            .where(
                CrawlRun.user_id == playground.user_id,
                CrawlRun.run_type == "crawl",
                CrawlRun.url.in_(selected_urls),
                CrawlRun.created_at >= playground.created_at,
            )
            .order_by(CrawlRun.id.asc())
        )
        for run in rows.all():
            settings = run.settings if isinstance(run.settings, dict) else {}
            if settings.get("playground_session_id") == playground.id:
                resolved.setdefault(int(run.id), run)
    return [resolved[run_id] for run_id in sorted(resolved)]


async def runs_by_ids(session: AsyncSession, run_ids: list[int]) -> dict[int, CrawlRun]:
    if not run_ids:
        return {}
    rows = await session.scalars(select(CrawlRun).where(CrawlRun.id.in_(run_ids)))
    by_id = {int(run.id): run for run in rows.all()}
    return {run_id: by_id[run_id] for run_id in run_ids if run_id in by_id}

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.models.product_intelligence import (
    ProductIntelligenceCandidate,
    ProductIntelligenceJob,
    ProductIntelligenceMatch,
    ProductIntelligenceSourceProduct,
)
from app.models.crawl_run import CrawlRun
from app.models.user import User
from app.services.config.product_intelligence import (
    ADMIN_ROLE,
    ECOMMERCE_DETAIL_SURFACE,
    PRIVATE_LABEL_EXCLUDE,
    PRODUCT_INTELLIGENCE_BRAND_INFERENCE_LLM_TASK,
    PRODUCT_INTELLIGENCE_LLM_TASK,
    PRODUCT_INTELLIGENCE_CANDIDATE_STATUS_CRAWL_QUEUED,
    PRODUCT_INTELLIGENCE_CANDIDATE_STATUS_CRAWL_TIMEOUT,
    PRODUCT_INTELLIGENCE_JOB_STATUS_COMPLETE,
    PRODUCT_INTELLIGENCE_JOB_STATUS_FAILED,
    PRODUCT_INTELLIGENCE_JOB_STATUS_QUEUED,
    PRODUCT_INTELLIGENCE_JOB_STATUS_RUNNING,
    PRODUCT_INTELLIGENCE_REVIEW_ACCEPTED,
    PRODUCT_INTELLIGENCE_REVIEW_PENDING,
    PRODUCT_INTELLIGENCE_REVIEW_REJECTED,
    RUN_TYPE_CRAWL,
    product_intelligence_settings,
)
from app.services.crawl.access_service import (
    require_accessible_record,
    require_accessible_run,
)
from app.services.crawl.crud import create_crawl_run, get_run_records
from app.services.crawl.service import dispatch_run
from app.services.domain_utils import normalize_domain
from app.services.llm.runtime import run_prompt_task
from app.services.product_intelligence.discovery import discover_candidates
from app.services.product_intelligence.discovery import shared_query_runner
from app.services.product_intelligence.matching import (
    build_search_result_intelligence,
    extract_product_snapshot,
    is_private_label,
    normalize_brand,
    score_candidate,
    source_domain,
)
from app.services.product_intelligence.options import (
    as_float_or_default as _as_float_or_default,
    as_int as _as_int,
    as_price as _as_price,
    int_list as _int_list,
    meets_confidence_threshold as _meets_confidence_threshold,
    normalized_options as _normalized_options,
    option_int as _option_int,
    string_list as _string_list,
)
from app.services.product_intelligence.records import (
    resolved_source_url as _resolved_source_url,
    row_data_payload as _row_data_payload,
    row_from_record as _row_from_record,
    source_product_payload as _source_product_payload,
)
from app.services.product_intelligence.discovery_persistence import (
    persist_discovery_job,
)
from app.services.product_intelligence.candidate_scoring import (
    score_candidate_if_ready as score_persisted_candidate_if_ready,
)

logger = logging.getLogger(__name__)


async def create_product_intelligence_job(
    session: AsyncSession,
    *,
    user: User,
    payload: dict[str, object],
) -> ProductIntelligenceJob:
    options = _normalized_options(payload.get("options"))
    source_run_id = _as_int(payload.get("source_run_id"))
    source_rows = await _load_source_rows(
        session, user=user, payload=payload, options=options
    )
    if not source_rows:
        raise ValueError("Product Intelligence needs at least one source product")
    if source_run_id is not None:
        await require_accessible_run(session, run_id=source_run_id, user=user)

    job = ProductIntelligenceJob(
        user_id=user.id,
        source_run_id=source_run_id,
        status=PRODUCT_INTELLIGENCE_JOB_STATUS_QUEUED,
        options=options,
        summary={
            "source_count": len(source_rows),
            "candidate_count": 0,
            "match_count": 0,
        },
    )
    session.add(job)
    await session.flush()

    llm_enabled = bool(options.get("llm_enrichment_enabled"))
    for row in source_rows[
        : _option_int(
            options,
            "max_source_products",
            default=product_intelligence_settings.max_source_products,
        )
    ]:
        snapshot = await _resolve_source_snapshot(
            session,
            raw=_row_data_payload(row),
            llm_enabled=llm_enabled,
        )
        source_url = _resolved_source_url(row, snapshot)
        private_label = is_private_label(snapshot.get("brand"))
        session.add(
            ProductIntelligenceSourceProduct(
                job_id=job.id,
                source_run_id=_as_int(row.get("source_run_id")) or source_run_id,
                source_record_id=_as_int(row.get("source_record_id")),
                source_url=source_url,
                brand=str(snapshot.get("brand") or ""),
                normalized_brand=str(snapshot.get("normalized_brand") or ""),
                title=str(snapshot.get("title") or ""),
                sku=str(snapshot.get("sku") or ""),
                mpn=str(snapshot.get("mpn") or ""),
                gtin=str(snapshot.get("gtin") or ""),
                price=_as_price(snapshot.get("price")),
                currency=str(snapshot.get("currency") or ""),
                image_url=str(snapshot.get("image_url") or ""),
                is_private_label=private_label,
                payload=snapshot,
            )
        )
    await session.commit()
    await session.refresh(job)
    return job


async def run_product_intelligence_job(job_id: int) -> None:
    async with SessionLocal() as session:
        job = await session.get(ProductIntelligenceJob, job_id)
        if job is None:
            return
        if job.status != PRODUCT_INTELLIGENCE_JOB_STATUS_QUEUED:
            return
        job.status = PRODUCT_INTELLIGENCE_JOB_STATUS_RUNNING
        job.summary = {
            **dict(job.summary or {}),
            "started_at": datetime.now(UTC).isoformat(),
        }
        await session.commit()
        try:
            await _run_job(session, job)
        except Exception as exc:
            logger.exception("Product Intelligence job failed: %s", job_id)
            await session.refresh(job)
            job.status = PRODUCT_INTELLIGENCE_JOB_STATUS_FAILED
            job.summary = {
                **dict(job.summary or {}),
                "error": f"{type(exc).__name__}: {exc}",
            }
            job.completed_at = datetime.now(UTC)
            await session.commit()


async def refresh_product_intelligence_job(
    session: AsyncSession,
    *,
    job: ProductIntelligenceJob,
) -> ProductIntelligenceJob:
    await _score_completed_candidates(session, job)
    await _update_job_summary(session, job)
    await session.commit()
    await session.refresh(job)
    return job


async def list_product_intelligence_jobs(
    session: AsyncSession,
    *,
    user: User,
    limit: int = 25,
) -> list[ProductIntelligenceJob]:
    statement = (
        select(ProductIntelligenceJob)
        .order_by(ProductIntelligenceJob.id.desc())
        .limit(limit)
    )
    if user.role != ADMIN_ROLE:
        statement = statement.where(ProductIntelligenceJob.user_id == user.id)
    return list((await session.scalars(statement)).all())


async def get_product_intelligence_job(
    session: AsyncSession,
    *,
    user: User,
    job_id: int,
    refresh: bool = False,
) -> ProductIntelligenceJob:
    job = await session.get(ProductIntelligenceJob, job_id)
    if job is None or (user.role != ADMIN_ROLE and job.user_id != user.id):
        raise LookupError("Product Intelligence job not found")
    if refresh:
        return await refresh_product_intelligence_job(session, job=job)
    return job


async def review_product_intelligence_match(
    session: AsyncSession,
    *,
    user: User,
    job_id: int,
    match_id: int,
    action: str,
) -> ProductIntelligenceMatch:
    await get_product_intelligence_job(session, user=user, job_id=job_id)
    match = await session.get(ProductIntelligenceMatch, match_id)
    if match is None or match.job_id != job_id:
        raise LookupError("Product Intelligence match not found")
    if action not in {
        PRODUCT_INTELLIGENCE_REVIEW_ACCEPTED,
        PRODUCT_INTELLIGENCE_REVIEW_REJECTED,
        PRODUCT_INTELLIGENCE_REVIEW_PENDING,
    }:
        raise ValueError("Invalid review action")
    match.review_status = action
    await session.commit()
    await session.refresh(match)
    return match


async def build_job_payload(
    session: AsyncSession,
    *,
    job: ProductIntelligenceJob,
) -> dict[str, object]:
    source_products = list(
        (
            await session.scalars(
                select(ProductIntelligenceSourceProduct)
                .where(ProductIntelligenceSourceProduct.job_id == job.id)
                .order_by(ProductIntelligenceSourceProduct.id)
            )
        ).all()
    )
    candidates = list(
        (
            await session.scalars(
                select(ProductIntelligenceCandidate)
                .where(ProductIntelligenceCandidate.job_id == job.id)
                .order_by(ProductIntelligenceCandidate.id)
            )
        ).all()
    )
    matches = list(
        (
            await session.scalars(
                select(ProductIntelligenceMatch)
                .where(ProductIntelligenceMatch.job_id == job.id)
                .order_by(
                    ProductIntelligenceMatch.score.desc(), ProductIntelligenceMatch.id
                )
            )
        ).all()
    )
    return {
        "job": job,
        "source_products": source_products,
        "candidates": candidates,
        "matches": matches,
    }


async def discover_product_intelligence_candidates(
    session: AsyncSession,
    *,
    user: User,
    payload: dict[str, object],
) -> dict[str, object]:
    options = _normalized_options(payload.get("options"))
    source_run_id = _as_int(payload.get("source_run_id"))
    source_rows = await _load_source_rows(
        session, user=user, payload=payload, options=options
    )
    if not source_rows:
        raise ValueError("Product Intelligence needs at least one source product")
    if source_run_id is not None:
        await require_accessible_run(session, run_id=source_run_id, user=user)

    discovered_payloads: list[dict[str, object]] = []
    max_source_products = _option_int(
        options,
        "max_source_products",
        default=product_intelligence_settings.max_source_products,
    )
    processed_source_count = 0
    resolved_snapshots: dict[int, dict[str, object]] = {}
    llm_enabled = bool(options.get("llm_enrichment_enabled"))
    async with shared_query_runner(str(options["search_provider"])) as run_query:
        for index, row in enumerate(source_rows[:max_source_products]):
            snapshot = await _resolve_source_snapshot(
                session,
                raw=_row_data_payload(row),
                llm_enabled=llm_enabled,
            )
            resolved_snapshots[index] = snapshot
            if (
                is_private_label(snapshot.get("brand"))
                and options["private_label_mode"] == PRIVATE_LABEL_EXCLUDE
            ):
                continue
            processed_source_count += 1
            source_url_value = _resolved_source_url(row, snapshot)
            discovered = await discover_candidates(
                snapshot,
                source_domain_value=normalize_domain(source_url_value),
                provider=str(options["search_provider"]),
                allowed_domains=_string_list(options.get("allowed_domains")),
                excluded_domains=_string_list(options.get("excluded_domains")),
                max_candidates=_option_int(
                    options,
                    "max_candidates_per_product",
                    default=product_intelligence_settings.max_candidates_per_product,
                ),
                run_query=run_query,
            )
            for candidate in discovered:
                intelligence = build_search_result_intelligence(
                    source=snapshot,
                    candidate_payload=dict(candidate.payload or {}),
                    candidate_url=candidate.url,
                    candidate_domain=candidate.domain,
                    source_type=candidate.source_type,
                )
                intelligence = await _backfill_candidate_brand(
                    session,
                    source=snapshot,
                    intelligence=intelligence,
                    source_type=candidate.source_type,
                    llm_enabled=llm_enabled,
                )
                if not _meets_confidence_threshold(
                    _as_float_or_default(intelligence.get("confidence_score"), 0.0),
                    options=options,
                ):
                    continue
                discovered_payloads.append(
                    {
                        "source_record_id": _as_int(row.get("source_record_id")),
                        "source_run_id": _as_int(row.get("source_run_id")),
                        "source_url": source_url_value,
                        "source_title": str(snapshot.get("title") or ""),
                        "source_brand": str(snapshot.get("brand") or ""),
                        "source_price": snapshot.get("price")
                        if isinstance(snapshot.get("price"), float)
                        else None,
                        "source_currency": str(snapshot.get("currency") or ""),
                        "source_index": index,
                        "url": candidate.url,
                        "domain": candidate.domain,
                        "source_type": candidate.source_type,
                        "query_used": candidate.query_used,
                        "search_rank": candidate.search_rank,
                        "payload": dict(candidate.payload or {}),
                        "intelligence": intelligence,
                    }
                )
    job = await _persist_discovery_job(
        session,
        user=user,
        source_run_id=source_run_id,
        source_rows=source_rows,
        processed_source_count=processed_source_count,
        options=options,
        discovered_payloads=discovered_payloads,
        resolved_snapshots=resolved_snapshots,
    )
    return {
        "job_id": job.id,
        "options": options,
        "source_count": min(processed_source_count, max_source_products),
        "candidate_count": len(discovered_payloads),
        "search_provider": str(options.get("search_provider") or ""),
        "candidates": discovered_payloads,
    }


async def _persist_discovery_job(
    session: AsyncSession,
    *,
    user: User,
    source_run_id: int | None,
    source_rows: list[dict[str, object]],
    processed_source_count: int,
    options: dict[str, object],
    discovered_payloads: list[dict[str, object]],
    resolved_snapshots: dict[int, dict[str, object]] | None = None,
) -> ProductIntelligenceJob:
    return await persist_discovery_job(
        session,
        user=user,
        source_run_id=source_run_id,
        source_rows=source_rows,
        processed_source_count=processed_source_count,
        options=options,
        discovered_payloads=discovered_payloads,
        resolved_snapshots=resolved_snapshots,
        resolve_snapshot=_resolve_source_snapshot,
    )


async def _run_job(session: AsyncSession, job: ProductIntelligenceJob) -> None:
    options = _normalized_options(job.options)
    sources = list(
        (
            await session.scalars(
                select(ProductIntelligenceSourceProduct)
                .where(ProductIntelligenceSourceProduct.job_id == job.id)
                .order_by(ProductIntelligenceSourceProduct.id)
            )
        ).all()
    )

    candidates_to_poll = []

    async with shared_query_runner(str(options["search_provider"])) as run_query:
        for source in sources[
            : _option_int(
                options,
                "max_source_products",
                default=product_intelligence_settings.max_source_products,
            )
        ]:
            if (
                source.is_private_label
                and options["private_label_mode"] == PRIVATE_LABEL_EXCLUDE
            ):
                continue
            source_payload = _source_product_payload(source)
            source_domain_value = normalize_domain(source.source_url)
            discovered = await discover_candidates(
                source_payload,
                source_domain_value=source_domain_value,
                provider=str(options["search_provider"]),
                allowed_domains=_string_list(options.get("allowed_domains")),
                excluded_domains=_string_list(options.get("excluded_domains")),
                max_candidates=_option_int(
                    options,
                    "max_candidates_per_product",
                    default=product_intelligence_settings.max_candidates_per_product,
                ),
                run_query=run_query,
            )
            for discovered_candidate in discovered:
                candidate = ProductIntelligenceCandidate(
                    job_id=job.id,
                    source_product_id=source.id,
                    url=discovered_candidate.url,
                    domain=discovered_candidate.domain,
                    source_type=discovered_candidate.source_type,
                    query_used=discovered_candidate.query_used,
                    search_rank=discovered_candidate.search_rank,
                    payload=dict(discovered_candidate.payload or {}),
                )
                session.add(candidate)
                await session.flush()

                # Non-blocking dispatch to queue/background crawler
                await _create_candidate_crawl(session, job, candidate, options=options)
                candidates_to_poll.append(candidate)

    # Commit changes before entering sequential status checking loops
    await session.commit()

    # Poll candidates. Background crawls execute concurrently on workers, so resolution is fast
    for candidate in candidates_to_poll:
        await _poll_candidate_and_score(session, job, candidate)
        await _update_job_summary(session, job)
        await session.commit()

    await _score_completed_candidates(session, job)
    job.status = PRODUCT_INTELLIGENCE_JOB_STATUS_COMPLETE
    job.completed_at = datetime.now(UTC)
    await _update_job_summary(session, job)
    await session.commit()


async def _create_candidate_crawl(
    session: AsyncSession,
    job: ProductIntelligenceJob,
    candidate: ProductIntelligenceCandidate,
    *,
    options: dict[str, object],
) -> CrawlRun:
    settings = {
        "llm_enabled": bool(options.get("llm_enrichment_enabled")),
        "max_records": 1,
        "product_intelligence_job_id": job.id,
        "product_intelligence_candidate_id": candidate.id,
    }
    run = await create_crawl_run(
        session,
        int(job.user_id or 0),
        {
            "run_type": RUN_TYPE_CRAWL,
            "url": candidate.url,
            "surface": ECOMMERCE_DETAIL_SURFACE,
            "settings": settings,
        },
    )
    await dispatch_run(session, run)
    candidate.candidate_crawl_run_id = run.id
    candidate.status = PRODUCT_INTELLIGENCE_CANDIDATE_STATUS_CRAWL_QUEUED
    await session.commit()
    return run


async def _poll_candidate_and_score(
    session: AsyncSession,
    job: ProductIntelligenceJob,
    candidate: ProductIntelligenceCandidate,
) -> None:
    deadline = (
        asyncio.get_running_loop().time()
        + product_intelligence_settings.candidate_poll_seconds
    )
    while asyncio.get_running_loop().time() <= deadline:
        scored = await _score_candidate_if_ready(session, job, candidate)
        if scored:
            return
        await asyncio.sleep(
            product_intelligence_settings.candidate_poll_interval_seconds
        )
    candidate.status = PRODUCT_INTELLIGENCE_CANDIDATE_STATUS_CRAWL_TIMEOUT
    await _update_job_summary(session, job)
    await session.flush()


async def _score_completed_candidates(
    session: AsyncSession,
    job: ProductIntelligenceJob,
) -> None:
    candidates = list(
        (
            await session.scalars(
                select(ProductIntelligenceCandidate)
                .where(ProductIntelligenceCandidate.job_id == job.id)
                .order_by(ProductIntelligenceCandidate.id)
            )
        ).all()
    )
    for candidate in candidates:
        await _score_candidate_if_ready(session, job, candidate)


async def _score_candidate_if_ready(
    session: AsyncSession,
    job: ProductIntelligenceJob,
    candidate: ProductIntelligenceCandidate,
) -> bool:
    return await score_persisted_candidate_if_ready(
        session,
        job,
        candidate,
        build_llm_enrichment=_build_llm_enrichment,
    )


async def _resolve_source_snapshot(
    session: AsyncSession,
    *,
    raw: dict[str, object],
    llm_enabled: bool,
) -> dict[str, object]:
    snapshot = extract_product_snapshot(raw)
    if snapshot.get("brand") or not llm_enabled:
        return snapshot
    brand = await _brand_inference_llm(
        session,
        title=str(snapshot.get("title") or ""),
        url=str(snapshot.get("url") or ""),
        snippet=str(snapshot.get("description") or ""),
    )
    if not brand:
        return snapshot
    return {**snapshot, "brand": brand, "normalized_brand": normalize_brand(brand)}


async def _backfill_candidate_brand(
    session: AsyncSession,
    *,
    source: dict[str, object],
    intelligence: dict[str, object],
    source_type: str,
    llm_enabled: bool,
) -> dict[str, object]:
    if not llm_enabled:
        return intelligence
    canonical = intelligence.get("canonical_record")
    if not isinstance(canonical, dict) or str(canonical.get("brand") or "").strip():
        return intelligence
    brand = await _brand_inference_llm(
        session,
        title=str(canonical.get("title") or ""),
        url=str(canonical.get("url") or ""),
        snippet=str(canonical.get("snippet") or canonical.get("description") or ""),
    )
    if not brand:
        return intelligence
    updated = {**canonical, "brand": brand, "normalized_brand": normalize_brand(brand)}
    rescored = score_candidate(
        source=source, candidate=updated, source_type=source_type
    )
    return {
        **intelligence,
        "canonical_record": updated,
        "confidence_score": rescored["score"],
        "confidence_label": rescored["label"],
        "score_reasons": rescored["reasons"],
    }


async def _brand_inference_llm(
    session: AsyncSession, *, title: str, url: str, snippet: str
) -> str:
    if not title and not url:
        return ""
    domain = source_domain(url)
    result = await run_prompt_task(
        session,
        task_type=PRODUCT_INTELLIGENCE_BRAND_INFERENCE_LLM_TASK,
        run_id=None,
        domain=domain,
        variables={
            "product_title": title,
            "product_url": url,
            "source_domain": domain,
            "product_snippet": snippet,
        },
    )
    if result.error_message or not isinstance(result.payload, dict):
        return ""
    brand = str(result.payload.get("brand") or "").strip()
    if not brand:
        return ""
    try:
        confidence = float(result.payload.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0
    threshold = product_intelligence_settings.brand_inference_confidence_threshold
    return brand if confidence >= threshold else ""


async def _build_llm_enrichment(
    session: AsyncSession,
    *,
    job: ProductIntelligenceJob,
    candidate: ProductIntelligenceCandidate,
    source_snapshot: dict[str, object],
    candidate_snapshot: dict[str, object],
    deterministic_result: dict[str, object],
) -> dict[str, object]:
    requested = bool((job.options or {}).get("llm_enrichment_enabled"))
    base: dict[str, object] = {
        "requested": requested,
        "applied": False,
    }
    if not requested:
        return base
    result = await run_prompt_task(
        session,
        task_type=PRODUCT_INTELLIGENCE_LLM_TASK,
        run_id=candidate.candidate_crawl_run_id,
        domain=candidate.domain,
        variables={
            "source_product_json": source_snapshot,
            "candidate_product_json": candidate_snapshot,
            "serpapi_result_json": dict(candidate.payload or {}),
            "deterministic_match_json": deterministic_result,
        },
    )
    if result.error_message:
        return {
            **base,
            "error": result.error_message,
            "error_category": str(result.error_category or ""),
        }
    return {
        **base,
        "applied": isinstance(result.payload, dict),
        "provider": result.provider or "",
        "model": result.model or "",
        "payload": result.payload if isinstance(result.payload, dict) else {},
    }


async def _update_job_summary(
    session: AsyncSession, job: ProductIntelligenceJob
) -> None:
    source_count = await session.scalar(
        select(func.count())
        .select_from(ProductIntelligenceSourceProduct)
        .where(ProductIntelligenceSourceProduct.job_id == job.id)
    )
    candidate_count = await session.scalar(
        select(func.count())
        .select_from(ProductIntelligenceCandidate)
        .where(ProductIntelligenceCandidate.job_id == job.id)
    )
    match_count = await session.scalar(
        select(func.count())
        .select_from(ProductIntelligenceMatch)
        .where(ProductIntelligenceMatch.job_id == job.id)
    )
    job.summary = {
        **dict(job.summary or {}),
        "source_count": int(source_count or 0),
        "candidate_count": int(candidate_count or 0),
        "search_provider": str((job.options or {}).get("search_provider") or ""),
        "match_count": int(match_count or 0),
        "updated_at": datetime.now(UTC).isoformat(),
    }


async def _load_source_rows(
    session: AsyncSession,
    *,
    user: User,
    payload: dict[str, object],
    options: dict[str, object],
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for record_id in _int_list(payload.get("source_record_ids")):
        record = await require_accessible_record(
            session, record_id=record_id, user=user
        )
        rows.append(_row_from_record(record))
    if rows:
        return rows

    source_run_id = _as_int(payload.get("source_run_id"))
    if source_run_id is not None:
        run = await require_accessible_run(session, run_id=source_run_id, user=user)
        records, _ = await get_run_records(
            session,
            run.id,
            1,
            _option_int(
                options,
                "max_source_products",
                default=product_intelligence_settings.max_source_products,
            ),
        )
        return [_row_from_record(record) for record in records]

    source_records = payload.get("source_records")
    source_record_items = source_records if isinstance(source_records, list) else []
    for index, item in enumerate(source_record_items):
        if not isinstance(item, dict):
            continue
        data = dict(item.get("data") or item)
        rows.append(
            {
                "source_record_id": _as_int(item.get("id")),
                "source_run_id": _as_int(item.get("run_id")),
                "source_url": str(item.get("source_url") or data.get("url") or ""),
                "data": data,
                "index": index,
            }
        )
    return rows


backfill_candidate_brand = _backfill_candidate_brand
poll_candidate_and_score = _poll_candidate_and_score
resolve_source_snapshot = _resolve_source_snapshot

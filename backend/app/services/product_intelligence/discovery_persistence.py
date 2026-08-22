from __future__ import annotations

from datetime import UTC, datetime
from typing import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.product_intelligence import (
    ProductIntelligenceCandidate,
    ProductIntelligenceJob,
    ProductIntelligenceMatch,
    ProductIntelligenceSourceProduct,
)
from app.models.user import User
from app.services.config.product_intelligence import (
    PRODUCT_INTELLIGENCE_CANDIDATE_STATUS_DISCOVERED,
    PRODUCT_INTELLIGENCE_JOB_STATUS_COMPLETE,
    PRODUCT_INTELLIGENCE_REVIEW_PENDING,
    product_intelligence_settings,
)
from app.services.product_intelligence.matching import is_private_label, source_domain
from app.services.product_intelligence.options import (
    as_float_or_default,
    as_int,
    as_nonnegative_int,
    as_price,
    option_int,
)
from app.services.product_intelligence.records import (
    resolved_source_url,
    row_data_payload,
)

SnapshotResolver = Callable[..., Awaitable[dict[str, object]]]


async def persist_discovery_job(
    session: AsyncSession,
    *,
    user: User,
    source_run_id: int | None,
    source_rows: list[dict[str, object]],
    processed_source_count: int,
    options: dict[str, object],
    discovered_payloads: list[dict[str, object]],
    resolved_snapshots: dict[int, dict[str, object]] | None,
    resolve_snapshot: SnapshotResolver,
) -> ProductIntelligenceJob:
    job = _new_discovery_job(
        user=user,
        source_run_id=source_run_id,
        processed_source_count=processed_source_count,
        options=options,
        candidate_count=len(discovered_payloads),
    )
    session.add(job)
    await session.flush()
    source_ids = await _persist_sources(
        session,
        job=job,
        source_run_id=source_run_id,
        source_rows=source_rows,
        options=options,
        resolved_snapshots=resolved_snapshots or {},
        resolve_snapshot=resolve_snapshot,
    )
    for payload in discovered_payloads:
        source_index = _candidate_source_index(payload)
        source_product_id = (
            source_ids.get(source_index) if source_index is not None else None
        )
        if source_product_id is not None:
            await _persist_candidate(
                session, job=job, source_product_id=source_product_id, payload=payload
            )
    await session.commit()
    await session.refresh(job)
    return job


def _new_discovery_job(
    *,
    user: User,
    source_run_id: int | None,
    processed_source_count: int,
    options: dict[str, object],
    candidate_count: int,
) -> ProductIntelligenceJob:
    max_sources = option_int(
        options,
        "max_source_products",
        default=product_intelligence_settings.max_source_products,
    )
    return ProductIntelligenceJob(
        user_id=user.id,
        source_run_id=source_run_id,
        status=PRODUCT_INTELLIGENCE_JOB_STATUS_COMPLETE,
        options=options,
        summary={
            "mode": "discovery",
            "source_count": min(processed_source_count, max_sources),
            "candidate_count": candidate_count,
            "search_provider": str(options.get("search_provider") or ""),
            "match_count": candidate_count,
            "updated_at": datetime.now(UTC).isoformat(),
        },
        completed_at=datetime.now(UTC),
    )


async def _persist_sources(
    session: AsyncSession,
    *,
    job: ProductIntelligenceJob,
    source_run_id: int | None,
    source_rows: list[dict[str, object]],
    options: dict[str, object],
    resolved_snapshots: dict[int, dict[str, object]],
    resolve_snapshot: SnapshotResolver,
) -> dict[int, int]:
    max_sources = option_int(
        options,
        "max_source_products",
        default=product_intelligence_settings.max_source_products,
    )
    sources: dict[int, ProductIntelligenceSourceProduct] = {}
    for index, row in enumerate(source_rows[:max_sources]):
        snapshot = resolved_snapshots.get(index) or await resolve_snapshot(
            session,
            raw=row_data_payload(row),
            llm_enabled=bool(options.get("llm_enrichment_enabled")),
        )
        source = _source_model(
            job=job,
            row=row,
            snapshot=snapshot,
            source_run_id=source_run_id,
        )
        session.add(source)
        sources[index] = source
    await session.flush()
    return {
        index: int(source.id)
        for index, source in sources.items()
        if source.id is not None
    }


def _source_model(
    *,
    job: ProductIntelligenceJob,
    row: dict[str, object],
    snapshot: dict[str, object],
    source_run_id: int | None,
) -> ProductIntelligenceSourceProduct:
    return ProductIntelligenceSourceProduct(
        job_id=job.id,
        source_run_id=as_int(row.get("source_run_id")) or source_run_id,
        source_record_id=as_int(row.get("source_record_id")),
        source_url=resolved_source_url(row, snapshot),
        brand=str(snapshot.get("brand") or ""),
        normalized_brand=str(snapshot.get("normalized_brand") or ""),
        title=str(snapshot.get("title") or ""),
        sku=str(snapshot.get("sku") or ""),
        mpn=str(snapshot.get("mpn") or ""),
        gtin=str(snapshot.get("gtin") or ""),
        price=as_price(snapshot.get("price")),
        currency=str(snapshot.get("currency") or ""),
        image_url=str(snapshot.get("image_url") or ""),
        is_private_label=is_private_label(snapshot.get("brand")),
        payload=snapshot,
    )


def _candidate_source_index(payload: dict[str, object]) -> int | None:
    if "source_index" not in payload or payload.get("source_index") is None:
        return None
    return as_nonnegative_int(payload.get("source_index"))


async def _persist_candidate(
    session: AsyncSession,
    *,
    job: ProductIntelligenceJob,
    source_product_id: int,
    payload: dict[str, object],
) -> None:
    raw_payload = payload.get("payload")
    payload_data = raw_payload if isinstance(raw_payload, dict) else {}
    raw_intelligence = payload.get("intelligence")
    intelligence = raw_intelligence if isinstance(raw_intelligence, dict) else {}
    candidate = ProductIntelligenceCandidate(
        job_id=job.id,
        source_product_id=source_product_id,
        url=str(payload.get("url") or ""),
        domain=str(payload.get("domain") or ""),
        source_type=str(payload.get("source_type") or ""),
        query_used=str(payload.get("query_used") or ""),
        search_rank=as_int(payload.get("search_rank")) or 0,
        payload={**payload_data, "intelligence": intelligence},
        status=PRODUCT_INTELLIGENCE_CANDIDATE_STATUS_DISCOVERED,
    )
    session.add(candidate)
    await session.flush()
    if intelligence:
        session.add(
            _match_model(job, source_product_id, candidate, payload, intelligence)
        )


def _match_model(
    job: ProductIntelligenceJob,
    source_product_id: int,
    candidate: ProductIntelligenceCandidate,
    payload: dict[str, object],
    intelligence: dict[str, object],
) -> ProductIntelligenceMatch:
    canonical = _dict_value(intelligence.get("canonical_record"))
    candidate_url = str(canonical.get("url") or candidate.url)
    return ProductIntelligenceMatch(
        job_id=job.id,
        source_product_id=source_product_id,
        candidate_id=candidate.id,
        candidate_record_id=None,
        score=as_float_or_default(intelligence.get("confidence_score"), 0.0),
        score_label=str(intelligence.get("confidence_label") or ""),
        review_status=PRODUCT_INTELLIGENCE_REVIEW_PENDING,
        source_price=as_price(payload.get("source_price")),
        candidate_price=as_price(canonical.get("price")),
        currency=str(canonical.get("currency") or payload.get("source_currency") or ""),
        availability=str(canonical.get("availability") or ""),
        candidate_url=candidate_url,
        candidate_domain=source_domain(candidate_url),
        score_reasons=_dict_value(intelligence.get("score_reasons")),
        llm_enrichment=_dict_value(intelligence.get("llm_enrichment")),
    )


def _dict_value(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}

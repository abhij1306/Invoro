from __future__ import annotations

from typing import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crawl_run import CrawlRecord, CrawlRun
from app.models.product_intelligence import (
    ProductIntelligenceCandidate,
    ProductIntelligenceJob,
    ProductIntelligenceMatch,
    ProductIntelligenceSourceProduct,
)
from app.services.config.product_intelligence import (
    CRAWL_RUN_FINAL_STATUSES,
    PRODUCT_INTELLIGENCE_CANDIDATE_STATUS_CRAWL_COMPLETE,
    PRODUCT_INTELLIGENCE_CANDIDATE_STATUS_FAILED,
    PRODUCT_INTELLIGENCE_CANDIDATE_STATUS_NO_RECORDS,
    PRODUCT_INTELLIGENCE_REVIEW_PENDING,
)
from app.services.product_intelligence.matching import (
    extract_product_snapshot,
    score_candidate,
    source_domain,
)
from app.services.product_intelligence.options import (
    as_float_or_default,
    as_price,
    meets_confidence_threshold,
)
from app.services.product_intelligence.records import source_product_payload

BuildLlmEnrichment = Callable[..., Awaitable[dict[str, object]]]


async def score_candidate_if_ready(
    session: AsyncSession,
    job: ProductIntelligenceJob,
    candidate: ProductIntelligenceCandidate,
    *,
    build_llm_enrichment: BuildLlmEnrichment,
) -> bool:
    record_state = await _candidate_record_state(session, candidate)
    if isinstance(record_state, bool):
        return record_state
    record = record_state
    source_product = await session.get(
        ProductIntelligenceSourceProduct, candidate.source_product_id
    )
    if source_product is None:
        candidate.status = PRODUCT_INTELLIGENCE_CANDIDATE_STATUS_FAILED
        return True
    source_snapshot = source_product_payload(source_product)
    candidate_snapshot = extract_product_snapshot(
        {**dict(record.data or {}), "source_url": record.source_url}
    )
    result = score_candidate(
        source=source_snapshot,
        candidate=candidate_snapshot,
        source_type=candidate.source_type,
    )
    score = as_float_or_default(result.get("score"), 0.0)
    if not meets_confidence_threshold(score, options=job.options):
        candidate.status = PRODUCT_INTELLIGENCE_CANDIDATE_STATUS_CRAWL_COMPLETE
        return True
    llm_enrichment = await build_llm_enrichment(
        session,
        job=job,
        candidate=candidate,
        source_snapshot=source_snapshot,
        candidate_snapshot=candidate_snapshot,
        deterministic_result=result,
    )
    session.add(
        _match_model(
            job=job,
            candidate=candidate,
            record=record,
            source_product=source_product,
            candidate_snapshot=candidate_snapshot,
            result=result,
            llm_enrichment=llm_enrichment,
        )
    )
    candidate.status = PRODUCT_INTELLIGENCE_CANDIDATE_STATUS_CRAWL_COMPLETE
    return True


async def _candidate_record_state(
    session: AsyncSession, candidate: ProductIntelligenceCandidate
) -> CrawlRecord | bool:
    if candidate.candidate_crawl_run_id is None:
        return False
    existing = await session.scalar(
        select(ProductIntelligenceMatch.id).where(
            ProductIntelligenceMatch.candidate_id == candidate.id
        )
    )
    if existing:
        return True
    candidate_run = await session.get(CrawlRun, candidate.candidate_crawl_run_id)
    if candidate_run is None:
        candidate.status = PRODUCT_INTELLIGENCE_CANDIDATE_STATUS_FAILED
        return True
    if candidate_run.status not in CRAWL_RUN_FINAL_STATUSES:
        return False
    record = await session.scalar(
        select(CrawlRecord)
        .where(CrawlRecord.run_id == candidate_run.id)
        .order_by(CrawlRecord.id)
        .limit(1)
    )
    if record is None:
        candidate.status = PRODUCT_INTELLIGENCE_CANDIDATE_STATUS_NO_RECORDS
        return True
    return record


def _match_model(
    *,
    job: ProductIntelligenceJob,
    candidate: ProductIntelligenceCandidate,
    record: CrawlRecord,
    source_product: ProductIntelligenceSourceProduct,
    candidate_snapshot: dict[str, object],
    result: dict[str, object],
    llm_enrichment: dict[str, object],
) -> ProductIntelligenceMatch:
    candidate_url = str(candidate_snapshot.get("url") or candidate.url)
    reasons = result.get("reasons")
    return ProductIntelligenceMatch(
        job_id=job.id,
        source_product_id=source_product.id,
        candidate_id=candidate.id,
        candidate_record_id=record.id,
        score=as_float_or_default(result.get("score"), 0.0),
        score_label=str(result.get("label") or ""),
        review_status=PRODUCT_INTELLIGENCE_REVIEW_PENDING,
        source_price=source_product.price,
        candidate_price=as_price(candidate_snapshot.get("price")),
        currency=str(
            candidate_snapshot.get("currency") or source_product.currency or ""
        ),
        availability=str(candidate_snapshot.get("availability") or ""),
        candidate_url=candidate_url,
        candidate_domain=source_domain(candidate_url),
        score_reasons=dict(reasons) if isinstance(reasons, dict) else {},
        llm_enrichment=llm_enrichment,
    )

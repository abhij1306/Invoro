from __future__ import annotations

from datetime import UTC, datetime
from typing import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crawl_run import CrawlRecord
from app.models.data_enrichment import DataEnrichmentJob, EnrichedProduct
from app.services.config.data_enrichment import (
    DATA_ENRICHMENT_STATUS_ENRICHED,
    DATA_ENRICHMENT_STATUS_FAILED,
    DATA_ENRICHMENT_STATUS_RUNNING,
)

EnrichProduct = Callable[..., Awaitable[None]]


async def load_product_refs(
    session: AsyncSession, job_id: int
) -> list[tuple[int, int]]:
    rows = (
        await session.execute(
            select(EnrichedProduct.id, EnrichedProduct.source_record_id)
            .where(EnrichedProduct.job_id == job_id)
            .order_by(EnrichedProduct.id)
        )
    ).all()
    return [
        (int(product_id), int(source_record_id))
        for product_id, source_record_id in rows
        if product_id is not None and source_record_id is not None
    ]


async def process_product_ref(
    session: AsyncSession,
    *,
    job: DataEnrichmentJob,
    job_id: int,
    product_id: int,
    source_record_id: int,
    llm_enabled: bool,
    enrich_product: EnrichProduct,
) -> tuple[DataEnrichmentJob, bool]:
    product = await session.get(EnrichedProduct, product_id)
    record = await session.get(CrawlRecord, source_record_id)
    if product is None:
        return job, False
    if record is None:
        product.status = DATA_ENRICHMENT_STATUS_FAILED
        product.diagnostics = {"error": "source_record_missing"}
        await session.commit()
        return job, False
    record_id = int(record.id)
    try:
        product.status = DATA_ENRICHMENT_STATUS_RUNNING
        record.enrichment_status = DATA_ENRICHMENT_STATUS_RUNNING
        await enrich_product(
            session,
            job=job,
            product=product,
            record=record,
            llm_enabled=llm_enabled,
        )
    except Exception as exc:  # pragma: no cover - defensive job isolation
        job, product, record = await _recover_enrichment_error(
            session,
            exc=exc,
            job=job,
            job_id=job_id,
            product=product,
            product_id=product_id,
            record=record,
            record_id=record_id,
        )
        product.status = DATA_ENRICHMENT_STATUS_FAILED
        product.diagnostics = {"error": str(exc)}
        record.enrichment_status = DATA_ENRICHMENT_STATUS_FAILED
        await session.commit()
        return job, False
    product.status = DATA_ENRICHMENT_STATUS_ENRICHED
    record.enrichment_status = DATA_ENRICHMENT_STATUS_ENRICHED
    record.enriched_at = datetime.now(UTC)
    await session.commit()
    return job, True


async def _recover_enrichment_error(
    session: AsyncSession,
    *,
    exc: Exception,
    job: DataEnrichmentJob,
    job_id: int,
    product: EnrichedProduct,
    product_id: int,
    record: CrawlRecord,
    record_id: int,
) -> tuple[DataEnrichmentJob, EnrichedProduct, CrawlRecord]:
    if not isinstance(exc, SQLAlchemyError):
        return job, product, record
    await session.rollback()
    refreshed_job = await session.get(DataEnrichmentJob, job_id)
    refreshed_product = await session.get(EnrichedProduct, product_id)
    refreshed_record = await session.get(CrawlRecord, record_id)
    if refreshed_job is None or refreshed_product is None or refreshed_record is None:
        raise exc
    return refreshed_job, refreshed_product, refreshed_record

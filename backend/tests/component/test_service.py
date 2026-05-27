from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ucp_audit import UCPAuditPageResult, UCPAuditReport
from app.services.config.aid_score import (
    AID_AUDIT_JOB_STATUS_COMPLETE,
    AID_AUDIT_JOB_STATUS_QUEUED,
    AID_CATALOG_MODE,
    D_AID1_ID,
    D_AID2_ID,
    D_AID3_ID,
    D_AID4_ID,
    D_AID5_ID,
    D_AID6_ID,
    DIMENSION_WEIGHTS,
)
from app.services.ucp_audit.catalog_crawl import CatalogCrawlResult
from app.services.ucp_audit.service import (
    build_ucp_audit_job_payload,
    build_ucp_report_for_domain,
    create_ucp_audit_job,
    get_ucp_audit_job,
    list_ucp_audit_jobs,
    run_job,
)
from app.services.ucp_audit.types import UCPComplianceReport, UCPDimensionScore


def _dimension(dimension_id: str, score: int = 100) -> UCPDimensionScore:
    return UCPDimensionScore(
        dimension_id=dimension_id,
        score=score,
        status="pass",
        findings=[],
        weight=DIMENSION_WEIGHTS[dimension_id],
    )


def _sample_report(audit_id: str = "audit-1") -> UCPComplianceReport:
    return UCPComplianceReport(
        domain="example.com",
        audit_id=audit_id,
        overall_score=82,
        dimension_scores=[_dimension(D_AID1_ID, 82)],
        all_findings=[],
        d_ucp1_gate_applied=False,
        ucp_contract={"catalog": {"pages_crawled": 2}},
        repair_roadmap=[],
    )


@pytest.mark.asyncio
@pytest.mark.component
async def test_aid_audit_job_creates_queued_row(
    db_session: AsyncSession,
    test_user,
) -> None:
    job = await create_ucp_audit_job(
        db_session,
        user=test_user,
        payload={
            "domain": "https://example.com",
            "options": {"sample_size": 3},
        },
    )

    assert job.status == AID_AUDIT_JOB_STATUS_QUEUED
    assert job.domain == "example.com"
    assert job.options["sample_size"] == 3
    assert job.summary["page_result_count"] == 0


@pytest.mark.asyncio
@pytest.mark.component
async def test_aid_audit_run_job_persists_report_and_catalog_result(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_report(
        domain: str,
        audit_id: str,
        options: dict[str, object],
        **kwargs,
    ):
        assert domain == "example.com"
        assert options["sample_size"] == 2
        return _sample_report(audit_id=audit_id)

    monkeypatch.setattr(
        "app.services.ucp_audit.service.build_ucp_report_for_domain",
        fake_report,
    )
    job = await create_ucp_audit_job(
        db_session,
        user=test_user,
        payload={"domain": "example.com", "options": {"sample_size": 2}},
    )

    await run_job(db_session, job)

    report = (
        await db_session.scalars(
            select(UCPAuditReport).where(UCPAuditReport.job_id == job.id)
        )
    ).one()
    page_result = (
        await db_session.scalars(
            select(UCPAuditPageResult).where(UCPAuditPageResult.job_id == job.id)
        )
    ).one()

    assert job.status == AID_AUDIT_JOB_STATUS_COMPLETE
    assert job.summary["overall_score"] == 82
    assert report.overall_score == 82
    assert report.report_json["domain"] == "example.com"
    assert report.report_json["ucp_contract"]["catalog"]["pages_crawled"] == 2
    assert page_result.url == "https://example.com/"
    assert page_result.acquisition_mode == AID_CATALOG_MODE


@pytest.mark.asyncio
@pytest.mark.component
async def test_aid_audit_job_payload_serializes(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_report(
        domain: str,
        audit_id: str,
        options: dict[str, object],
        **kwargs,
    ):
        del domain, options, kwargs
        return _sample_report(audit_id=audit_id)

    monkeypatch.setattr(
        "app.services.ucp_audit.service.build_ucp_report_for_domain",
        fake_report,
    )
    job = await create_ucp_audit_job(
        db_session,
        user=test_user,
        payload={"domain": "example.com"},
    )
    await run_job(db_session, job)

    jobs = await list_ucp_audit_jobs(db_session, user=test_user)
    loaded = await get_ucp_audit_job(db_session, user=test_user, job_id=job.id)
    payload = await build_ucp_audit_job_payload(db_session, job=loaded)

    assert [row.id for row in jobs] == [job.id]
    assert payload["job"].id == job.id
    assert payload["report"].overall_score == 82
    assert len(payload["page_results"]) == 1


@pytest.mark.asyncio
@pytest.mark.component
async def test_aid_report_scores_catalog_signals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured_sample_size = 0

    async def fake_crawl(domain: str, *, sample_size: int) -> CatalogCrawlResult:
        nonlocal captured_sample_size
        captured_sample_size = sample_size
        assert domain == "example.com"
        return CatalogCrawlResult(
            domain="example.com",
            pages_crawled=2,
            jsonld_blocks=[
                {
                    "@type": "Product",
                    "offers": {"@type": "Offer", "price": "100", "availability": "InStock"},
                    "aggregateRating": {"ratingValue": "4.8", "reviewCount": "12"},
                },
                {"@type": "LocalBusiness"},
            ],
            og_tags={"@type": "product"},
            product_records=[
                {
                    "title": "Product",
                    "description": "Useful product description. " * 8,
                    "price": "100",
                    "image_url": "https://example.com/image.jpg",
                    "variants": [{"size": "M"}],
                    "sku": "SKU",
                    "brand": "Brand",
                    "_dom_price": "100",
                    "_page_text": "Visa Mastercard EMI delivery return",
                }
            ],
            sitemap_found=True,
        )

    monkeypatch.setattr("app.services.ucp_audit.service.crawl_catalog", fake_crawl)

    report = await build_ucp_report_for_domain("example.com", "audit-1", {"sample_size": 7})
    by_dimension = {item.dimension_id: item for item in report.dimension_scores}

    assert captured_sample_size == 7
    assert set(by_dimension) == {
        D_AID1_ID,
        D_AID2_ID,
        D_AID3_ID,
        D_AID4_ID,
        D_AID5_ID,
        D_AID6_ID,
    }
    assert all(item.score >= 95 for item in by_dimension.values())
    assert report.ucp_contract["catalog"]["pages_crawled"] == 2


@pytest.mark.asyncio
@pytest.mark.component
async def test_aid_report_runs_llm_when_enabled(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_crawl(domain: str, *, sample_size: int) -> CatalogCrawlResult:
        del domain, sample_size
        return CatalogCrawlResult(
            domain="example.com",
            pages_crawled=1,
            jsonld_blocks=[{"@type": "Product", "name": "Product"}],
            product_records=[{"source_url": "https://example.com/p/1", "title": "Product"}],
            sitemap_found=True,
        )

    async def fake_audit(session, *, domain, audit_id, packets):
        assert session is db_session
        assert domain == "example.com"
        assert audit_id == "audit-llm"
        assert packets[0].url == "https://example.com/p/1"
        return []

    monkeypatch.setattr("app.services.ucp_audit.service.crawl_catalog", fake_crawl)
    monkeypatch.setattr("app.services.ucp_audit.service.audit_evidence_packets", fake_audit)

    report = await build_ucp_report_for_domain(
        "example.com",
        "audit-llm",
        {"llm_enabled": True},
        session=db_session,
    )

    assert report.ucp_contract["ai_assessment"]["enabled"] is False

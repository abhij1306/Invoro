from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ucp_audit import UCPAuditPageResult, UCPAuditReport
from app.services.config.ucp_audit import (
    D_UCP1_ID,
    D_UCP2_ID,
    D_UCP3_ID,
    D_UCP4_ID,
    D_UCP5_ID,
    D_UCP6_ID,
    UCP_AUDIT_JOB_STATUS_COMPLETE,
    UCP_AUDIT_JOB_STATUS_QUEUED,
    UCP_MANIFEST_MODE,
)
from app.services.ucp_audit.service import (
    build_ucp_audit_job_payload,
    build_ucp_report_for_domain,
    create_ucp_audit_job,
    get_ucp_audit_job,
    list_ucp_audit_jobs,
    run_job,
)
from app.services.ucp_audit.types import (
    UCPComplianceReport,
    UCPDimensionScore,
    UCPManifestResult,
    UCPSchemaProbe,
    UCPTransportProbe,
)


def _sample_report(audit_id: str = "audit-1") -> UCPComplianceReport:
    return UCPComplianceReport(
        domain="example.com",
        audit_id=audit_id,
        overall_score=82,
        dimension_scores=[
            UCPDimensionScore(
                dimension_id=D_UCP1_ID,
                score=100,
                status="pass",
                findings=[],
                weight=1.0,
            )
        ],
        all_findings=[],
        d_ucp1_gate_applied=False,
        ucp_contract={"services": ["dev.ucp.shopping"]},
        repair_roadmap=[],
    )


@pytest.mark.asyncio
async def test_ucp_audit_job_creates_queued_row(
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

    assert job.status == UCP_AUDIT_JOB_STATUS_QUEUED
    assert job.domain == "example.com"
    assert job.options["sample_size"] == 3
    assert job.summary["page_result_count"] == 0


@pytest.mark.asyncio
async def test_ucp_audit_run_job_persists_report_and_endpoint_result(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_report(domain: str, audit_id: str, options: dict[str, object]):
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

    assert job.status == UCP_AUDIT_JOB_STATUS_COMPLETE
    assert job.summary["overall_score"] == 82
    assert report.overall_score == 82
    assert report.report_json["domain"] == "example.com"
    assert report.report_json["ucp_contract"]["services"] == ["dev.ucp.shopping"]
    assert page_result.url == "https://example.com/.well-known/ucp"
    assert page_result.acquisition_mode == UCP_MANIFEST_MODE


@pytest.mark.asyncio
async def test_ucp_audit_job_payload_serializes(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_report(domain: str, audit_id: str, options: dict[str, object]):
        del domain, options
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
async def test_ucp_report_scores_protocol_contract_not_json_ld(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = UCPManifestResult(
        manifest_found=True,
        manifest_valid=True,
        services_declared=["dev.ucp.shopping"],
        capabilities_declared=[
            "dev.ucp.shopping.catalog.search",
            "dev.ucp.shopping.catalog.lookup",
            "dev.ucp.shopping.cart",
            "dev.ucp.shopping.checkout",
            "dev.ucp.shopping.order",
            "dev.ucp.shopping.fulfillment",
            "dev.ucp.shopping.discount",
        ],
        service_entries=[],
        capability_entries=[],
        transport_entries=[
            {
                "service": "dev.ucp.shopping",
                "transport": "mcp",
                "endpoint": "https://example.com/api/ucp/mcp",
                "schema": "https://ucp.dev/shopping/mcp.openrpc.json",
            }
        ],
        schema_urls=[
            "https://ucp.dev/catalog_search.json",
            "https://ucp.dev/catalog_lookup.json",
            "https://ucp.dev/cart.json",
            "https://ucp.dev/checkout.json",
            "https://ucp.dev/order.json",
            "https://ucp.dev/fulfillment.json",
            "https://ucp.dev/discount.json",
        ],
        payment_handlers=["com.google.pay"],
        raw_manifest={"ucp": {"supported_versions": {"2026-04-08": "https://example.com"}}},
    )

    async def fake_discover(domain: str) -> UCPManifestResult:
        del domain
        return manifest

    async def fake_transport_probe(result: UCPManifestResult) -> list[UCPTransportProbe]:
        assert result is manifest
        return [
            UCPTransportProbe(
                service="dev.ucp.shopping",
                transport="mcp",
                endpoint="https://example.com/api/ucp/mcp",
                reachable=True,
                negotiated=False,
                profile_required=True,
                status_code=422,
            )
        ]

    async def fake_schema_probe(urls: list[str]) -> list[UCPSchemaProbe]:
        return [
            UCPSchemaProbe(url=url, reachable=True, valid_json=True, title=url)
            for url in urls
        ]

    monkeypatch.setattr("app.services.ucp_audit.service.discover_ucp_manifest", fake_discover)
    monkeypatch.setattr("app.services.ucp_audit.service.probe_transports", fake_transport_probe)
    monkeypatch.setattr("app.services.ucp_audit.service.probe_schemas", fake_schema_probe)

    report = await build_ucp_report_for_domain("example.com", "audit-1", {"sample_size": 1})
    by_dimension = {item.dimension_id: item for item in report.dimension_scores}
    finding_codes = {finding.code for finding in report.all_findings}

    assert set(by_dimension) == {
        D_UCP1_ID,
        D_UCP2_ID,
        D_UCP3_ID,
        D_UCP4_ID,
        D_UCP5_ID,
        D_UCP6_ID,
    }
    assert by_dimension[D_UCP1_ID].score == 100
    assert by_dimension[D_UCP2_ID].score == 100
    assert by_dimension[D_UCP3_ID].score == 70
    assert by_dimension[D_UCP4_ID].score == 100
    assert by_dimension[D_UCP5_ID].score == 100
    assert by_dimension[D_UCP6_ID].score == 100
    assert "schema_missing" not in finding_codes
    assert report.ucp_contract["payment_handlers"] == ["com.google.pay"]
    assert report.repair_roadmap[-1].sub_skill == "shop-skill advisory"

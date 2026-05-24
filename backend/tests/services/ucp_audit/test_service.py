from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

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

BACKEND_ROOT = Path(__file__).resolve().parents[3]


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


def test_ucp_schema_analysis_system_prompt_anchors_response_shape() -> None:
    prompt = (
        BACKEND_ROOT
        / "app"
        / "data"
        / "prompts"
        / "ucp_schema_analysis.system.txt"
    ).read_text(encoding="utf-8")

    assert '"summary"' in prompt
    assert '"recommended_changes"' in prompt
    assert '"risk_notes"' in prompt


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
    async def fake_report(
        domain: str,
        audit_id: str,
        options: dict[str, object],
        **kwargs,
    ):
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
        del urls
        return [
            UCPSchemaProbe(
                url="https://ucp.dev/catalog_search.json",
                reachable=True,
                valid_json=True,
                schema_valid=True,
                field_results={
                    "catalog": {
                        "product_id": True,
                        "title": True,
                        "price": True,
                        "currency": True,
                        "availability": True,
                    }
                },
            ),
            UCPSchemaProbe(
                url="https://ucp.dev/cart.json",
                reachable=True,
                valid_json=True,
                schema_valid=True,
                field_results={
                    "cart_checkout": {
                        "cart_id": True,
                        "line_items": True,
                        "total": True,
                        "currency": True,
                    }
                },
            ),
            UCPSchemaProbe(
                url="https://ucp.dev/order.json",
                reachable=True,
                valid_json=True,
                schema_valid=True,
                field_results={
                    "order_policy": {
                        "order_id": True,
                        "status": True,
                        "fulfillment": True,
                    }
                },
            ),
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
    assert all(item.sub_skill != "shop-skill advisory" for item in report.repair_roadmap)


@pytest.mark.asyncio
async def test_ucp_schema_llm_analysis_runs_only_when_enabled(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest = UCPManifestResult(
        manifest_found=True,
        manifest_valid=True,
        services_declared=["dev.ucp.shopping"],
        capabilities_declared=["dev.ucp.shopping.catalog.search"],
        schema_urls=["https://ucp.dev/catalog_search.json"],
        raw_manifest={"ucp": {"version": "2026-04-08"}},
    )
    schema_probe = UCPSchemaProbe(
        url="https://ucp.dev/catalog_search.json",
        reachable=True,
        valid_json=True,
        schema_valid=True,
        groups=["catalog"],
        field_results={
            "catalog": {
                "product_id": True,
                "title": True,
                "price": False,
                "currency": False,
                "availability": False,
            }
        },
    )
    calls = 0

    async def fake_discover(domain: str) -> UCPManifestResult:
        del domain
        return manifest

    async def fake_transport_probe(result: UCPManifestResult) -> list[UCPTransportProbe]:
        del result
        return []

    async def fake_schema_probe(urls: list[str]) -> list[UCPSchemaProbe]:
        del urls
        return [schema_probe]

    async def fake_llm(*args, **kwargs):
        nonlocal calls
        calls += 1
        return SimpleNamespace(
            payload={
                "summary": "Add missing catalog fields.",
                "recommended_changes": ["Add price, currency, availability."],
                "risk_notes": [],
            },
            error_message="",
            error_category="",
            provider="test",
            model="test-model",
        )

    monkeypatch.setattr("app.services.ucp_audit.service.discover_ucp_manifest", fake_discover)
    monkeypatch.setattr("app.services.ucp_audit.service.probe_transports", fake_transport_probe)
    monkeypatch.setattr("app.services.ucp_audit.service.probe_schemas", fake_schema_probe)
    monkeypatch.setattr("app.services.ucp_audit.service.run_prompt_task", fake_llm)

    disabled = await build_ucp_report_for_domain(
        "example.com",
        "audit-1",
        {"llm_enabled": False},
        session=db_session,
    )
    enabled = await build_ucp_report_for_domain(
        "example.com",
        "audit-2",
        {"llm_enabled": True},
        session=db_session,
    )

    assert calls == 1
    assert enabled.ucp_contract["schemas"][0]["llm_analysis"]["summary"]
    assert enabled.overall_score == disabled.overall_score

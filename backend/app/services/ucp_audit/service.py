from __future__ import annotations

import logging
from datetime import UTC, datetime
from urllib.parse import urljoin, urlparse
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.models.ucp_audit import UCPAuditJob, UCPAuditPageResult, UCPAuditReport
from app.models.user import User
from app.services.config import aid_score as config
from app.services.domain_utils import normalize_domain
from app.services.ucp_audit.catalog_checks import (
    build_catalog_contract,
    build_catalog_dimensions,
)
from app.services.ucp_audit.catalog_crawl import crawl_catalog
from app.services.ucp_audit.evidence import build_evidence_packets
from app.services.ucp_audit.llm_rubric import audit_evidence_packets
from app.services.ucp_audit.reporting import build_markdown_report, build_report_payload
from app.services.ucp_audit.scoring import build_compliance_report
from app.services.ucp_audit.types import UCPComplianceReport

logger = logging.getLogger(__name__)


async def create_ucp_audit_job(
    session: AsyncSession,
    *,
    user: User,
    payload: dict[str, object],
) -> UCPAuditJob:
    domain = _normalized_domain(payload.get("domain"))
    options = _normalized_options(payload.get("options"))
    job = UCPAuditJob(
        user_id=user.id,
        domain=domain,
        status=config.AID_AUDIT_JOB_STATUS_QUEUED,
        options=options,
        summary={"page_result_count": 0, "overall_score": None},
    )
    session.add(job)
    await session.commit()
    await session.refresh(job)
    return job


async def run_ucp_audit_job(job_id: int) -> None:
    async with SessionLocal() as session:
        job = await session.scalar(
            select(UCPAuditJob)
            .where(
                UCPAuditJob.id == job_id,
                UCPAuditJob.status == config.AID_AUDIT_JOB_STATUS_QUEUED,
            )
            .with_for_update(skip_locked=True)
        )
        if job is None:
            return
        try:
            await run_job(session, job)
        except Exception as exc:
            logger.exception("AI Discoverability audit job failed: %s", job_id)
            await session.refresh(job)
            job.status = config.AID_AUDIT_JOB_STATUS_FAILED
            job.summary = {
                **dict(job.summary or {}),
                "error": f"{type(exc).__name__}: {exc}",
            }
            job.completed_at = datetime.now(UTC)
            await session.commit()


async def run_job(session: AsyncSession, job: UCPAuditJob) -> None:
    job.status = config.AID_AUDIT_JOB_STATUS_RUNNING
    job.summary = {**dict(job.summary or {}), "started_at": datetime.now(UTC).isoformat()}
    await session.commit()

    audit_id = f"ucp-{job.id}-{uuid4().hex[:8]}"
    report = await build_ucp_report_for_domain(
        job.domain,
        audit_id,
        dict(job.options or {}),
        session=session,
    )
    payload = build_report_payload(report)
    markdown = build_markdown_report(report)

    session.add(
        UCPAuditPageResult(
            job_id=job.id,
            url=_site_url(job.domain, ""),
            acquisition_mode=config.AID_CATALOG_MODE,
            dimension_payloads=payload,
            findings=payload["findings"],
        )
    )
    session.add(
        UCPAuditReport(
            job_id=job.id,
            overall_score=report.overall_score,
            dimension_scores=payload["dimension_scores"],
            findings=payload["findings"],
            report_json=payload,
            markdown_report=markdown,
        )
    )
    await session.flush()
    job.status = config.AID_AUDIT_JOB_STATUS_COMPLETE
    job.summary = {
        **dict(job.summary or {}),
        "overall_score": report.overall_score,
        "page_result_count": 1,
        "finding_count": len(report.all_findings),
    }
    job.completed_at = datetime.now(UTC)
    await session.commit()


async def build_ucp_report_for_domain(
    domain: str,
    audit_id: str,
    options: dict[str, object],
    *,
    session: AsyncSession | None = None,
) -> UCPComplianceReport:
    crawl_result = await crawl_catalog(
        domain,
        sample_size=_bounded_int(
            options.get("sample_size"),
            default=config.AID_AUDIT_DEFAULT_SAMPLE_SIZE,
            upper=config.AID_AUDIT_MAX_SAMPLE_SIZE,
        ),
    )
    evidence_packets = build_evidence_packets(crawl_result)
    llm_results = []
    if bool(options.get("llm_enabled")) and session is not None:
        llm_results = await audit_evidence_packets(
            session,
            domain=domain,
            audit_id=audit_id,
            packets=evidence_packets,
        )
    contract = build_catalog_contract(
        crawl_result,
        evidence_packets=evidence_packets,
        llm_results=llm_results,
    )
    dimensions = build_catalog_dimensions(crawl_result, llm_results=llm_results)
    return build_compliance_report(
        domain=domain,
        audit_id=audit_id,
        dimension_scores=dimensions,
        ucp_contract=contract,
    )


async def list_ucp_audit_jobs(
    session: AsyncSession,
    *,
    user: User,
    limit: int = 25,
) -> list[UCPAuditJob]:
    statement = select(UCPAuditJob).order_by(UCPAuditJob.id.desc()).limit(limit)
    if getattr(user, "role", "") != "admin":
        statement = statement.where(UCPAuditJob.user_id == user.id)
    return list((await session.scalars(statement)).all())


async def get_ucp_audit_job(
    session: AsyncSession,
    *,
    user: User,
    job_id: int,
) -> UCPAuditJob:
    job = await session.get(UCPAuditJob, job_id)
    if job is None or (getattr(user, "role", "") != "admin" and job.user_id != user.id):
        raise LookupError("AI Discoverability audit job not found")
    return job


async def get_ucp_audit_report(
    session: AsyncSession,
    job_id: int,
) -> UCPAuditReport | None:
    return await session.scalar(
        select(UCPAuditReport).where(UCPAuditReport.job_id == job_id)
    )


async def build_ucp_audit_job_payload(
    session: AsyncSession,
    *,
    job: UCPAuditJob,
) -> dict[str, object]:
    page_results = list(
        (
            await session.scalars(
                select(UCPAuditPageResult)
                .where(UCPAuditPageResult.job_id == job.id)
                .order_by(UCPAuditPageResult.id)
            )
        ).all()
    )
    report = await session.scalar(
        select(UCPAuditReport).where(UCPAuditReport.job_id == job.id)
    )
    return {"job": job, "page_results": page_results, "report": report}


def _normalized_domain(value: object) -> str:
    domain = normalize_domain(str(value or "").strip())
    if not domain:
        raise ValueError("AI Discoverability Score needs a domain")
    return domain


def _normalized_options(value: object) -> dict[str, object]:
    raw = dict(value or {}) if isinstance(value, dict) else {}
    sample_size = _bounded_int(
        raw.get("sample_size"),
        default=config.AID_AUDIT_DEFAULT_SAMPLE_SIZE,
        upper=config.AID_AUDIT_MAX_SAMPLE_SIZE,
    )
    formats = raw.get("report_formats")
    return {
        "sample_size": sample_size,
        "llm_enabled": bool(raw.get("llm_enabled", False)),
        "report_formats": _string_list(formats)
        or list(config.AID_AUDIT_DEFAULT_REPORT_FORMATS),
    }


def _bounded_int(value: object, *, default: int, upper: int) -> int:
    try:
        parsed = int(value) if isinstance(value, (int, float)) else int(str(value))
    except (TypeError, ValueError):
        parsed = default
    return max(1, min(parsed, upper))


def _string_list(value: object) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    return [str(item).strip().lower() for item in value if str(item).strip()]


def _root_url(domain: str) -> str:
    parsed = urlparse(str(domain or ""))
    if parsed.scheme:
        return f"{parsed.scheme}://{parsed.netloc}"
    return f"{config.AID_DEFAULT_URL_SCHEME}://{domain}"


def _site_url(domain: str, path: str) -> str:
    return urljoin(f"{_root_url(domain)}/", str(path or "").lstrip("/"))

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
from app.services.config import ucp_audit as config
from app.services.domain_utils import normalize_domain
from app.services.llm.config_service import snapshot_active_configs
from app.services.llm.runtime import run_prompt_task
from app.services.ucp_audit.discovery import discover_ucp_manifest, manifest_url
from app.services.ucp_audit.protocol_checks import (
    build_contract_payload,
    build_protocol_dimensions,
    probe_schemas,
    probe_transports,
)
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
    options["llm_config_snapshot"] = await snapshot_active_configs(
        session,
        task_types=[config.UCP_SCHEMA_ANALYSIS_LLM_TASK],
    )
    job = UCPAuditJob(
        user_id=user.id,
        domain=domain,
        status=config.UCP_AUDIT_JOB_STATUS_QUEUED,
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
                UCPAuditJob.status == config.UCP_AUDIT_JOB_STATUS_QUEUED,
            )
            .with_for_update(skip_locked=True)
        )
        if job is None:
            return
        try:
            await run_job(session, job)
        except Exception as exc:
            logger.exception("UCP audit job failed: %s", job_id)
            await session.refresh(job)
            job.status = config.UCP_AUDIT_JOB_STATUS_FAILED
            job.summary = {
                **dict(job.summary or {}),
                "error": f"{type(exc).__name__}: {exc}",
            }
            job.completed_at = datetime.now(UTC)
            await session.commit()


async def run_job(session: AsyncSession, job: UCPAuditJob) -> None:
    job.status = config.UCP_AUDIT_JOB_STATUS_RUNNING
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
            url=manifest_url(job.domain),
            acquisition_mode=config.UCP_MANIFEST_MODE,
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
    job.status = config.UCP_AUDIT_JOB_STATUS_COMPLETE
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
    manifest = await discover_ucp_manifest(domain)
    transport_probes = await probe_transports(manifest)
    schema_probes = await probe_schemas(manifest.schema_urls)
    if bool(options.get("llm_enabled")) and session is not None:
        await _apply_schema_llm_analysis(
            session,
            domain=domain,
            audit_id=audit_id,
            options=options,
            schema_probes=schema_probes,
        )
    contract = build_contract_payload(manifest, transport_probes, schema_probes)
    dimensions = build_protocol_dimensions(manifest, transport_probes, schema_probes)
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
        raise LookupError("UCP audit job not found")
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
        raise ValueError("UCP audit needs a domain")
    return domain


def _normalized_options(value: object) -> dict[str, object]:
    raw = dict(value or {}) if isinstance(value, dict) else {}
    sample_size = _bounded_int(
        raw.get("sample_size"),
        default=config.UCP_AUDIT_DEFAULT_SAMPLE_SIZE,
        upper=config.UCP_AUDIT_MAX_SAMPLE_SIZE,
    )
    formats = raw.get("report_formats")
    return {
        "sample_size": sample_size,
        "llm_enabled": bool(raw.get("llm_enabled", False)),
        "report_formats": _string_list(formats)
        or list(config.UCP_AUDIT_DEFAULT_REPORT_FORMATS),
    }


async def _apply_schema_llm_analysis(
    session: AsyncSession,
    *,
    domain: str,
    audit_id: str,
    options: dict[str, object],
    schema_probes: list,
) -> None:
    for probe in schema_probes:
        missing = _schema_probe_missing_fields(probe)
        if not missing:
            continue
        result = await run_prompt_task(
            session,
            task_type=config.UCP_SCHEMA_ANALYSIS_LLM_TASK,
            run_id=None,
            domain=domain,
            budget_scope=f"{config.UCP_SCHEMA_ANALYSIS_LLM_TASK}:{audit_id}",
            timeout_seconds=config.UCP_SCHEMA_LLM_TIMEOUT_SECONDS,
            config_snapshot=_llm_config_snapshot(options),
            variables={
                "schema_url": getattr(probe, "url", ""),
                "schema_title": getattr(probe, "title", ""),
                "missing_fields": missing,
                "field_results": getattr(probe, "field_results", {}),
            },
        )
        if result.error_message:
            probe.llm_analysis = {
                "applied": False,
                "error": result.error_message,
                "error_category": str(result.error_category or ""),
            }
            continue
        payload = result.payload if isinstance(result.payload, dict) else {}
        probe.llm_analysis = {
            "applied": bool(payload),
            "provider": result.provider or "",
            "model": result.model or "",
            **payload,
        }


def _schema_probe_missing_fields(probe: object) -> dict[str, list[str]]:
    field_results = getattr(probe, "field_results", {})
    if not isinstance(field_results, dict):
        return {}
    groups = [
        str(item)
        for item in list(getattr(probe, "groups", []) or [])
        if str(item) in field_results
    ] or list(field_results.keys())
    missing: dict[str, list[str]] = {}
    for group in groups:
        results = field_results.get(group)
        if not isinstance(results, dict):
            continue
        group_missing = [
            str(field)
            for field, present in results.items()
            if not bool(present)
        ]
        if group_missing:
            missing[str(group)] = group_missing
    return missing


def _llm_config_snapshot(options: dict[str, object]) -> dict[str, object] | None:
    snapshot = options.get("llm_config_snapshot")
    return snapshot if isinstance(snapshot, dict) else None


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
    return f"{config.UCP_DEFAULT_URL_SCHEME}://{domain}"


def _site_url(domain: str, path: str) -> str:
    return urljoin(f"{_root_url(domain)}/", str(path or "").lstrip("/"))

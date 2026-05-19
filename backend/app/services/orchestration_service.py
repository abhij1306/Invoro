from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from urllib.parse import urldefrag, urljoin, urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crawl_run import CrawlRecord, CrawlRun
from app.models.orchestration import (
    OrchestrationProject,
    OrchestrationStepRun,
    OrchestrationWorkflowRun,
)
from app.models.user import User
from app.services.config.orchestration_templates import (
    COMPETITIVE_PRICING_TEMPLATE_ID,
    ORCHESTRATION_DEFAULT_TRACKED_FIELDS,
    ORCHESTRATION_LISTING_LINK_FIELDS,
    ORCHESTRATION_LISTING_REQUEST_FIELDS,
    ORCHESTRATION_PRICE_VIEW_FIELDS,
    ORCHESTRATION_PRICE_VIEW_TITLE_FIELDS,
    ORCHESTRATION_PRICE_VIEW_WAS_PRICE_FIELDS,
    get_orchestration_template,
    list_orchestration_templates,
)
from app.services.crawl.crud import create_crawl_run
from app.services.crawl.service import dispatch_run
from app.services.domain_utils import normalize_domain
from app.services.field_policy import preserve_requested_fields
from app.services.monitor_service import create_monitor


def utcnow() -> datetime:
    return datetime.now(UTC)


def templates() -> list[dict[str, object]]:
    return list_orchestration_templates()


def template(template_id: str) -> dict[str, object]:
    try:
        return get_orchestration_template(template_id)
    except KeyError as exc:
        raise LookupError("Workflow template not found") from exc


async def create_project(
    session: AsyncSession,
    *,
    user: User,
    payload: dict[str, object],
) -> OrchestrationProject:
    project = OrchestrationProject(
        user_id=user.id,
        name=str(payload.get("name") or "").strip(),
        description=str(payload.get("description") or "").strip(),
        competitors=_text_list(payload.get("competitors")),
        category=str(payload.get("category") or "").strip(),
        tracked_fields=_text_list(payload.get("tracked_fields"))
        or list(ORCHESTRATION_DEFAULT_TRACKED_FIELDS),
        archived=False,
    )
    session.add(project)
    await session.commit()
    await session.refresh(project)
    return project


async def list_projects(session: AsyncSession, *, user: User) -> list[OrchestrationProject]:
    rows = await session.scalars(
        select(OrchestrationProject)
        .where(
            OrchestrationProject.user_id == user.id,
            OrchestrationProject.archived.is_(False),
        )
        .order_by(OrchestrationProject.updated_at.desc())
    )
    return list(rows.all())


async def get_project(
    session: AsyncSession,
    *,
    project_id: int,
    user: User,
) -> OrchestrationProject:
    project = await session.get(OrchestrationProject, project_id)
    if project is None or project.user_id != user.id:
        raise LookupError("Project not found")
    return project


async def create_workflow(
    session: AsyncSession,
    *,
    user: User,
    payload: dict[str, object],
) -> OrchestrationWorkflowRun:
    project = await get_project(
        session,
        project_id=_int_value(payload.get("project_id")),
        user=user,
    )
    workflow_template = template(str(payload["template_id"]))
    if workflow_template["id"] != COMPETITIVE_PRICING_TEMPLATE_ID:
        raise ValueError("Only competitive_pricing_snapshot is available")
    intent_inputs = _dict(payload.get("intent_inputs"))
    advanced_overrides = _dict(payload.get("advanced_overrides"))
    pipeline_config = _resolve_pipeline_config(workflow_template, advanced_overrides)
    fields = _workflow_fields(intent_inputs, project, pipeline_config)
    listing_seeds = _listing_seed_urls(intent_inputs)
    if not listing_seeds:
        raise ValueError("Listing URL is required")

    workflow = OrchestrationWorkflowRun(
        user_id=user.id,
        project_id=project.id,
        template_id=str(workflow_template["id"]),
        template_version=str(workflow_template["version"]),
        label=str(payload.get("label") or project.name).strip(),
        status="queued",
        intent_inputs=intent_inputs,
        advanced_overrides=advanced_overrides,
        pipeline_config=pipeline_config,
        summary={"estimated_completion_minutes": 12},
    )
    session.add(workflow)
    await session.flush()
    session.add_all(
        [
            OrchestrationStepRun(
                workflow_id=workflow.id,
                step_id="listing_run",
                step_type="crawl_run",
                status="queued",
                inputs={
                    "surface": pipeline_config["listing_surface"],
                    "seeds": listing_seeds,
                    "fields": list(ORCHESTRATION_LISTING_REQUEST_FIELDS),
                },
                outputs={},
            ),
            OrchestrationStepRun(
                workflow_id=workflow.id,
                step_id="detail_run",
                step_type="crawl_run",
                status="pending",
                inputs={
                    "surface": pipeline_config["detail_surface"],
                    "fields": fields,
                },
                outputs={},
            ),
            OrchestrationStepRun(
                workflow_id=workflow.id,
                step_id="comparison_view",
                step_type="view_render",
                status="pending",
                inputs={"view_type": "price_comparison_table"},
                outputs={},
            ),
        ]
    )
    await session.commit()
    workflow = await get_workflow(session, workflow_id=workflow.id, user=user, advance=False)
    await _dispatch_listing_step(session, workflow)
    await session.commit()
    return await get_workflow(session, workflow_id=workflow.id, user=user, advance=False)


async def list_workflows(
    session: AsyncSession,
    *,
    project_id: int,
    user: User,
) -> list[OrchestrationWorkflowRun]:
    await get_project(session, project_id=project_id, user=user)
    rows = await session.scalars(
        select(OrchestrationWorkflowRun)
        .where(OrchestrationWorkflowRun.project_id == project_id)
        .order_by(OrchestrationWorkflowRun.created_at.desc())
    )
    return list(rows.all())


async def get_workflow(
    session: AsyncSession,
    *,
    workflow_id: int,
    user: User,
    advance: bool = True,
) -> OrchestrationWorkflowRun:
    workflow = await session.get(OrchestrationWorkflowRun, workflow_id)
    if workflow is None or workflow.user_id != user.id:
        raise LookupError("Workflow not found")
    if advance:
        await advance_workflow(session, workflow)
        await session.commit()
        await session.refresh(workflow)
    return workflow


async def workflow_steps(
    session: AsyncSession,
    workflow_id: int,
) -> list[OrchestrationStepRun]:
    rows = await session.scalars(
        select(OrchestrationStepRun)
        .where(OrchestrationStepRun.workflow_id == workflow_id)
        .order_by(OrchestrationStepRun.id.asc())
    )
    return list(rows.all())


async def advance_workflow(
    session: AsyncSession,
    workflow: OrchestrationWorkflowRun,
) -> None:
    steps = {step.step_id: step for step in await workflow_steps(session, workflow.id)}
    listing_step = steps["listing_run"]
    detail_step = steps["detail_run"]
    comparison_step = steps["comparison_view"]

    if listing_step.status == "running":
        await _sync_crawl_step(session, listing_step)
    if listing_step.status == "completed" and detail_step.status == "pending":
        await _dispatch_detail_step(session, workflow, listing_step, detail_step)
    if detail_step.status == "running":
        await _sync_crawl_step(session, detail_step)
    if detail_step.status == "completed" and comparison_step.status == "pending":
        comparison_step.status = "completed"
        comparison_step.outputs = {"view_type": "price_comparison_table"}

    if any(step.status == "failed" for step in steps.values()):
        workflow.status = "failed"
        workflow.completed_at = workflow.completed_at or utcnow()
        return
    if comparison_step.status == "completed":
        workflow.status = "completed"
        workflow.completed_at = workflow.completed_at or utcnow()
        return
    if any(step.status == "running" for step in steps.values()):
        workflow.status = "running"
    else:
        workflow.status = "queued"


async def promote_workflow_to_monitor(
    session: AsyncSession,
    *,
    workflow_id: int,
    user: User,
    payload: dict[str, object],
) -> tuple[OrchestrationWorkflowRun, int, int, list[str]]:
    workflow = await get_workflow(session, workflow_id=workflow_id, user=user)
    if workflow.status != "completed":
        raise ValueError("Workflow must be completed before promotion")
    detail_step = await _require_step(session, workflow.id, "detail_run")
    urls = await _detail_urls_for_step(session, detail_step)
    if not urls:
        urls = _text_list(detail_step.inputs.get("seeds"))
    if not urls:
        raise ValueError("No detail URLs available for monitor")
    tracked_fields = _workflow_fields(workflow.intent_inputs, None, workflow.pipeline_config)
    monitor = await create_monitor(
        session,
        user=user,
        payload={
            "name": f"{workflow.label} monitor",
            "urls": urls,
            "surface": workflow.pipeline_config.get("detail_surface", "ecommerce_detail"),
            "tracked_fields": tracked_fields,
            "requested_fields": tracked_fields,
            "schedule_interval_hours": payload.get("schedule_interval_hours", 168),
            "retention_days": payload.get("retention_days", 30),
            "priority": payload.get("priority", "background"),
            "settings": _run_settings(workflow, "monitor"),
        },
    )
    workflow.monitor_id = monitor.id
    workflow.summary = {**_dict(workflow.summary), "promoted_monitor_id": monitor.id}
    await session.commit()
    await session.refresh(workflow)
    return workflow, monitor.id, len(urls), tracked_fields


async def price_comparison(
    session: AsyncSession,
    *,
    workflow_id: int,
    user: User,
) -> dict[str, object]:
    workflow = await get_workflow(session, workflow_id=workflow_id, user=user)
    detail_step = await _require_step(session, workflow.id, "detail_run")
    detail_run_id = detail_step.run_id
    rows: list[dict[str, object]] = []
    if detail_run_id is not None:
        records = await session.scalars(
            select(CrawlRecord)
            .where(CrawlRecord.run_id == detail_run_id)
            .order_by(CrawlRecord.created_at.asc(), CrawlRecord.id.asc())
        )
        for record in records.all():
            data = _dict(record.data)
            rows.append(
                {
                    "record_id": record.id,
                    "run_id": record.run_id,
                    "product": str(_first_data_value(data, ORCHESTRATION_PRICE_VIEW_TITLE_FIELDS) or ""),
                    "brand": str(data.get(ORCHESTRATION_PRICE_VIEW_FIELDS["brand"]) or ""),
                    "domain": _domain(record.source_url),
                    "price": data.get(ORCHESTRATION_PRICE_VIEW_FIELDS["price"]),
                    "was_price": _first_data_value(
                        data,
                        ORCHESTRATION_PRICE_VIEW_WAS_PRICE_FIELDS,
                    ),
                    "currency": _optional_text(
                        data.get(ORCHESTRATION_PRICE_VIEW_FIELDS["currency"])
                    ),
                    "availability": _optional_text(
                        data.get(ORCHESTRATION_PRICE_VIEW_FIELDS["availability"])
                    ),
                    "source_url": record.source_url,
                }
            )
    return {
        "workflow_id": workflow.id,
        "project_id": workflow.project_id,
        "detail_run_id": detail_run_id,
        "rows": rows,
        "export_csv_url": f"/api/crawls/{detail_run_id}/export/csv" if detail_run_id else None,
        "export_json_url": f"/api/crawls/{detail_run_id}/export/json" if detail_run_id else None,
        "crawl_studio_url": f"/crawl?run_id={detail_run_id}" if detail_run_id else None,
    }


async def _dispatch_listing_step(
    session: AsyncSession,
    workflow: OrchestrationWorkflowRun,
) -> None:
    step = await _require_step(session, workflow.id, "listing_run")
    if step.run_id is not None:
        return
    seeds = _text_list(step.inputs.get("seeds"))
    fields = _text_list(step.inputs.get("fields"))
    user_id = _workflow_user_id(workflow)
    run = await create_crawl_run(
        session,
        user_id,
        {
            "run_type": "batch" if len(seeds) > 1 else "crawl",
            "url": seeds[0],
            "urls": seeds,
            "surface": workflow.pipeline_config["listing_surface"],
            "settings": _run_settings(workflow, "listing_run"),
            "requested_fields": fields,
            "additional_fields": fields,
        },
    )
    run = await dispatch_run(session, run)
    step.run_id = run.id
    step.status = "running"
    workflow.status = "running"


async def _dispatch_detail_step(
    session: AsyncSession,
    workflow: OrchestrationWorkflowRun,
    listing_step: OrchestrationStepRun,
    detail_step: OrchestrationStepRun,
) -> None:
    urls = await _listing_product_urls(session, listing_step)
    max_items = int(workflow.pipeline_config.get("max_items_detail") or 200)
    urls = urls[:max_items]
    if not urls:
        detail_step.status = "failed"
        detail_step.error = "Listing run produced no product URLs"
        workflow.status = "failed"
        workflow.completed_at = utcnow()
        return
    fields = _text_list(detail_step.inputs.get("fields"))
    detail_step.inputs = {**_dict(detail_step.inputs), "seeds": urls}
    user_id = _workflow_user_id(workflow)
    run = await create_crawl_run(
        session,
        user_id,
        {
            "run_type": "batch" if len(urls) > 1 else "crawl",
            "url": urls[0],
            "urls": urls,
            "surface": workflow.pipeline_config["detail_surface"],
            "settings": _run_settings(workflow, "detail_run"),
            "requested_fields": fields,
            "additional_fields": fields,
        },
    )
    run = await dispatch_run(session, run)
    detail_step.run_id = run.id
    detail_step.status = "running"
    detail_step.outputs = {"url_count": len(urls)}


async def _sync_crawl_step(session: AsyncSession, step: OrchestrationStepRun) -> None:
    if step.run_id is None:
        return
    run = await session.get(CrawlRun, step.run_id)
    if run is None:
        step.status = "failed"
        step.error = "Crawl run missing"
        return
    if not run.is_terminal():
        return
    if run.status == "completed":
        step.status = "completed"
        step.outputs = {**_dict(step.outputs), "run_status": run.status}
        return
    step.status = "failed"
    step.error = f"Crawl run ended as {run.status}"


async def _require_step(
    session: AsyncSession,
    workflow_id: int,
    step_id: str,
) -> OrchestrationStepRun:
    step = await session.scalar(
        select(OrchestrationStepRun).where(
            OrchestrationStepRun.workflow_id == workflow_id,
            OrchestrationStepRun.step_id == step_id,
        )
    )
    if step is None:
        raise LookupError("Workflow step not found")
    return step


async def _listing_product_urls(
    session: AsyncSession,
    listing_step: OrchestrationStepRun,
) -> list[str]:
    if listing_step.run_id is None:
        return []
    seed_domains = _domains_for_urls(_text_list(listing_step.inputs.get("seeds")))
    records = await session.scalars(
        select(CrawlRecord)
        .where(CrawlRecord.run_id == listing_step.run_id)
        .order_by(CrawlRecord.created_at.asc(), CrawlRecord.id.asc())
    )
    urls: list[str] = []
    seen: set[str] = set()
    for record in records.all():
        data = _dict(record.data)
        for key in ORCHESTRATION_LISTING_LINK_FIELDS:
            candidate = _resolve_listing_url(record.source_url, data.get(key))
            if (
                candidate
                and _listing_url_matches_seed_domain(candidate, seed_domains)
                and candidate not in seen
            ):
                urls.append(candidate)
                seen.add(candidate)
                break
    return urls


def _resolve_listing_url(source_url: str, value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    resolved = urljoin(source_url, raw)
    parsed = urlparse(resolved)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return ""
    return urldefrag(resolved).url


def _listing_url_matches_seed_domain(candidate: str, seed_domains: set[str]) -> bool:
    if not seed_domains:
        return True
    candidate_domain = normalize_domain(candidate)
    return candidate_domain in seed_domains


def _domains_for_urls(urls: list[str]) -> set[str]:
    domains: set[str] = set()
    for url in urls:
        domain = normalize_domain(url)
        if domain:
            domains.add(domain)
    return domains


async def _detail_urls_for_step(
    session: AsyncSession,
    detail_step: OrchestrationStepRun,
) -> list[str]:
    if detail_step.run_id is None:
        return []
    records = await session.scalars(
        select(CrawlRecord)
        .where(CrawlRecord.run_id == detail_step.run_id)
        .order_by(CrawlRecord.created_at.asc(), CrawlRecord.id.asc())
    )
    urls: list[str] = []
    seen: set[str] = set()
    for record in records.all():
        if record.source_url and record.source_url not in seen:
            urls.append(record.source_url)
            seen.add(record.source_url)
    return urls


def _resolve_pipeline_config(
    workflow_template: Mapping[str, object],
    advanced_overrides: Mapping[str, object],
) -> dict[str, object]:
    defaults = _dict(workflow_template.get("pipeline_defaults"))
    allowed = set(_text_list(workflow_template.get("advanced_overrides")))
    config = dict(defaults)
    for key, value in advanced_overrides.items():
        if key in allowed:
            config[key] = value
    return config


def _run_settings(
    workflow: OrchestrationWorkflowRun,
    step_id: str,
) -> dict[str, object]:
    config = _dict(workflow.pipeline_config)
    settings: dict[str, object] = {
        "orchestration": {
            "workflow_id": workflow.id,
            "template_id": workflow.template_id,
            "step_id": step_id,
        },
        "llm_enabled": bool(config.get("llm_enabled", False)),
        "fetch_profile": {
            "fetch_mode": str(config.get("fetch_mode") or "auto"),
        },
        "locality_profile": {
            "geo_country": str(config.get("locality") or "auto"),
        },
    }
    if step_id == "listing_run":
        settings["fetch_profile"] = {
            **_dict(settings["fetch_profile"]),
            "max_pages": _int_value(config.get("max_pages_listing"), default=5),
        }
    if config.get("proxy_profile"):
        settings["proxy_profile"] = config["proxy_profile"]
    return settings


def _workflow_fields(
    intent_inputs: Mapping[str, object],
    project: OrchestrationProject | None,
    pipeline_config: Mapping[str, object],
) -> list[str]:
    fields = _text_list(intent_inputs.get("fields"))
    if not fields and project is not None:
        fields = _text_list(project.tracked_fields)
    custom_fields = _text_list(pipeline_config.get("custom_fields"))
    return preserve_requested_fields(
        [*(fields or ORCHESTRATION_DEFAULT_TRACKED_FIELDS), *custom_fields]
    )


def _listing_seed_urls(intent_inputs: Mapping[str, object]) -> list[str]:
    raw = [
        *_text_list(intent_inputs.get("listing_urls")),
        *_text_list(intent_inputs.get("listing_url")),
    ]
    urls: list[str] = []
    seen: set[str] = set()
    for item in raw:
        url = _url_from_input(item)
        if url and url not in seen:
            urls.append(url)
            seen.add(url)
    return urls


def _url_from_input(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if text.startswith(("http://", "https://")):
        return text
    return f"https://{text.lstrip('/')}"


def _workflow_user_id(workflow: OrchestrationWorkflowRun) -> int:
    if workflow.user_id is None:
        raise ValueError("Workflow user is missing")
    return workflow.user_id


def _int_value(value: object, *, default: int = 0) -> int:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        return int(value)
    raise TypeError(f"Unsupported integer value: {value!r}")


def _dict(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text_list(value: object) -> list[str]:
    raw_items = value if isinstance(value, list) else [value] if isinstance(value, str) else []
    items: list[str] = []
    seen: set[str] = set()
    for item in raw_items:
        text = str(item or "").strip()
        if text and text not in seen:
            items.append(text)
            seen.add(text)
    return items


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _first_data_value(data: Mapping[str, object], fields: list[str]) -> object:
    for field in fields:
        value = data.get(field)
        if value not in (None, "", [], {}):
            return value
    return None


def _domain(value: str) -> str:
    try:
        return urlparse(value).netloc
    except ValueError:
        return ""

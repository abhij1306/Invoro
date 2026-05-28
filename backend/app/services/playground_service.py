"""Playground session service.

Coordinates existing crawl, enrichment, product intelligence, alert,
and UCP audit services into a guided pipeline for non-technical users.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crawl_run import CrawlRecord, CrawlRun
from app.models.playground import PlaygroundSession
from app.models.user import User
from app.services.config.aid_score import (
    AID_AUDIT_JOB_STATUS_COMPLETE,
    AID_AUDIT_JOB_STATUS_FAILED,
)
from app.services.config.data_enrichment import (
    DATA_ENRICHMENT_JOB_TERMINAL_STATUSES,
)
from app.services.config.product_intelligence import (
    PRODUCT_INTELLIGENCE_JOB_STATUS_COMPLETE,
    PRODUCT_INTELLIGENCE_JOB_STATUS_FAILED,
)
from app.services.crawl.ingestion_service import create_crawl_run_from_payload
from app.services.crawl.state import TERMINAL_STATUSES

logger = logging.getLogger(__name__)

_AUDIT_TERMINAL_STATUSES = {
    AID_AUDIT_JOB_STATUS_COMPLETE,
    AID_AUDIT_JOB_STATUS_FAILED,
}
_PI_TERMINAL_STATUSES = {
    PRODUCT_INTELLIGENCE_JOB_STATUS_COMPLETE,
    PRODUCT_INTELLIGENCE_JOB_STATUS_FAILED,
}
_ENRICH_TERMINAL_STATUSES = set(DATA_ENRICHMENT_JOB_TERMINAL_STATUSES)

# State machine transitions
VALID_TRANSITIONS = {
    "created": ["discovering"],
    "discovering": ["discovered"],
    "discovered": ["extracting"],
    "extracting": ["extracted"],
    "extracted": ["running_pipeline"],
    "running_pipeline": ["complete"],
}

MAX_PRODUCTS = 50


async def create_session(
    session: AsyncSession,
    *,
    user: User,
    url: str,
) -> PlaygroundSession:
    """Create a new playground session."""
    url = url.strip()
    if not url:
        raise ValueError("URL is required")
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"

    playground = PlaygroundSession(
        user_id=user.id,
        input_url=url,
        state="created",
        step_data={},
    )
    session.add(playground)
    await session.flush()
    await session.refresh(playground)
    return playground


async def get_session(
    session: AsyncSession,
    *,
    session_id: int,
    user: User,
) -> PlaygroundSession:
    """Get a playground session, enforcing ownership. Auto-advances state if crawl completed."""
    playground = await session.get(PlaygroundSession, session_id)
    if playground is None or playground.user_id != user.id:
        raise LookupError("Session not found")
    # Ensure step_data is loaded before auto-advance to avoid lazy reload issues
    _ = playground.step_data
    await _auto_advance(session, playground)
    # Refresh server-computed columns (updated_at) after any flush to avoid MissingGreenlet
    await session.refresh(playground)
    return playground


async def list_sessions(
    session: AsyncSession,
    *,
    user: User,
    limit: int = 20,
) -> list[PlaygroundSession]:
    """List recent playground sessions for a user."""
    rows = await session.scalars(
        select(PlaygroundSession)
        .where(PlaygroundSession.user_id == user.id)
        .order_by(PlaygroundSession.created_at.desc())
        .limit(limit)
    )
    return list(rows.all())


async def start_discover(
    session: AsyncSession,
    *,
    playground: PlaygroundSession,
    user: User,
) -> int:
    """Kick off a listing/category crawl to discover products."""
    _require_state(playground, "created")

    run = await create_crawl_run_from_payload(
        session,
        user.id,
        {
            "run_type": "single",
            "url": playground.input_url,
            "surface": "ecommerce_listing",
            "settings": {"playground_session_id": playground.id},
            "requested_fields": ["url", "title", "brand", "price", "image"],
        },
    )

    playground.state = "discovering"
    playground.step_data = {
        **(playground.step_data or {}),
        "discover": {"run_id": run.id, "status": "running"},
    }
    await session.flush()
    return run.id


async def complete_discover(
    session: AsyncSession,
    *,
    playground: PlaygroundSession,
    products: list[dict[str, Any]],
) -> None:
    """Mark discovery complete with found products (called by crawl completion hook or poll)."""
    _require_state(playground, "discovering")

    playground.state = "discovered"
    step_data = dict(playground.step_data or {})
    step_data["discover"] = {
        **step_data.get("discover", {}),
        "status": "completed",
        "products": products[:MAX_PRODUCTS],
        "total_found": len(products),
    }
    playground.step_data = step_data
    await session.flush()


async def select_products(
    session: AsyncSession,
    *,
    playground: PlaygroundSession,
    urls: list[str],
) -> list[str]:
    """User confirms which products to extract (max 50)."""
    _require_state(playground, "discovered")

    if len(urls) > MAX_PRODUCTS:
        raise ValueError(f"Maximum {MAX_PRODUCTS} products per session")
    if not urls:
        raise ValueError("Select at least one product")

    step_data = dict(playground.step_data or {})
    step_data["selected_urls"] = urls
    playground.step_data = step_data
    await session.flush()
    return urls


async def start_extract(
    session: AsyncSession,
    *,
    playground: PlaygroundSession,
    user: User,
) -> int:
    """Kick off PDP crawl for selected products."""
    _require_state(playground, "discovered")

    urls = (playground.step_data or {}).get("selected_urls", [])
    if not urls:
        raise ValueError("No products selected — call select first")

    run = await create_crawl_run_from_payload(
        session,
        user.id,
        {
            "run_type": "batch",
            "url": urls[0],
            "urls": urls,
            "surface": "ecommerce_detail",
            "settings": {
                "playground_session_id": playground.id,
                "urls": urls,
            },
            "requested_fields": [
                "title", "price", "was_price", "brand",
                "availability", "image", "description",
            ],
        },
    )

    playground.state = "extracting"
    step_data = dict(playground.step_data or {})
    step_data["extract"] = {"run_id": run.id, "status": "running", "url_count": len(urls)}
    playground.step_data = step_data
    await session.flush()
    return run.id


async def start_pipeline(
    session: AsyncSession,
    *,
    playground: PlaygroundSession,
    user: User,
    enrich: bool = False,
    compare: bool = False,
    monitor: bool = False,
    audit: bool = False,
) -> tuple[dict[str, Any], list[tuple[Any, int]]]:
    """Launch selected downstream operations in parallel where possible.

    Returns a tuple of (launched_summary, dispatch_specs). The caller is
    expected to enqueue each ``(runner, job_id)`` spec via FastAPI
    ``BackgroundTasks`` so the underlying service workers actually run.
    """
    # Audit only needs the input URL; allow it from any post-creation state.
    # Other ops require completed extraction.
    needs_extracted = bool(enrich or compare or monitor)
    if needs_extracted:
        _require_state(playground, "extracted")
    elif playground.state == "created":
        raise ValueError("Session not started — call discover first")

    launched: dict[str, Any] = {}
    dispatch_specs: list[tuple[Any, int]] = []
    step_data = dict(playground.step_data or {})
    extract_run_id = step_data.get("extract", {}).get("run_id")

    if enrich:
        if not extract_run_id:
            launched["enrich"] = {
                "job_id": None,
                "status": "failed",
                "error": "No extraction run available",
            }
        else:
            from app.services.data_enrichment.service import (
                create_data_enrichment_job,
                run_data_enrichment_job,
            )
            try:
                job = await create_data_enrichment_job(
                    session,
                    user=user,
                    payload={"source_run_id": extract_run_id},
                )
                launched["enrich"] = {"job_id": job.id, "status": "running"}
                dispatch_specs.append((run_data_enrichment_job, job.id))
            except Exception as exc:
                logger.error("Pipeline enrich failed: %s", exc, exc_info=True)
                launched["enrich"] = {
                    "job_id": None,
                    "status": "failed",
                    "error": str(exc),
                }
        step_data["enrich"] = launched["enrich"]

    if compare:
        if not extract_run_id:
            launched["compare"] = {
                "job_id": None,
                "status": "failed",
                "error": "No extraction run available",
            }
        else:
            from app.services.product_intelligence.service import (
                create_product_intelligence_job,
                run_product_intelligence_job,
            )
            try:
                job = await create_product_intelligence_job(
                    session,
                    user=user,
                    payload={"source_run_id": extract_run_id},
                )
                launched["compare"] = {"job_id": job.id, "status": "running"}
                dispatch_specs.append((run_product_intelligence_job, job.id))
            except Exception as exc:
                logger.error("Pipeline compare failed: %s", exc, exc_info=True)
                launched["compare"] = {
                    "job_id": None,
                    "status": "failed",
                    "error": str(exc),
                }
        step_data["compare"] = launched["compare"]

    if monitor:
        selected_urls = step_data.get("selected_urls", [])
        from app.schemas.alert import AlertCreate
        from app.services.alert_service import create_alert
        try:
            alert_payload = AlertCreate(
                url=selected_urls[0] if selected_urls else playground.input_url,
                target_fields=["price", "availability"],
            )
            monitor_obj, _run_id = await create_alert(
                session, user=user, payload=alert_payload
            )
            launched["monitor"] = {
                "alert_id": monitor_obj.id,
                "status": "created",
            }
        except Exception as exc:
            logger.error("Pipeline monitor failed: %s", exc, exc_info=True)
            launched["monitor"] = {
                "alert_id": None,
                "status": "failed",
                "error": str(exc),
            }
        step_data["monitor"] = launched["monitor"]

    if audit:
        from app.services.ucp_audit.service import (
            create_ucp_audit_job,
            run_ucp_audit_job,
        )
        try:
            job = await create_ucp_audit_job(
                session,
                user=user,
                payload={"domain": playground.input_url},
            )
            launched["audit"] = {"job_id": job.id, "status": "running"}
            dispatch_specs.append((run_ucp_audit_job, job.id))
        except Exception as exc:
            logger.error("Pipeline audit failed: %s", exc, exc_info=True)
            launched["audit"] = {
                "job_id": None,
                "status": "failed",
                "error": str(exc),
            }
        step_data["audit"] = launched["audit"]

    # Only transition to running_pipeline when there is actual extraction work
    # to track. Audit-only sessions stay in their current state but still
    # surface results via step_data.
    if needs_extracted:
        playground.state = "running_pipeline"
    playground.step_data = step_data
    await session.flush()
    return launched, dispatch_specs


async def get_results(
    session: AsyncSession,
    *,
    playground: PlaygroundSession,
) -> dict[str, Any]:
    """Aggregate results from all pipeline steps."""
    step_data = dict(playground.step_data or {})
    results: dict[str, Any] = {
        "state": playground.state,
        "input_url": playground.input_url,
        "steps": {},
    }

    # Discovery results
    discover = step_data.get("discover", {})
    if discover:
        results["steps"]["discover"] = {
            "status": discover.get("status"),
            "total_found": discover.get("total_found", 0),
            "products": discover.get("products", []),
        }

    # Selected URLs
    results["steps"]["selected_urls"] = step_data.get("selected_urls", [])

    # Extraction results — fetch records from the crawl run
    extract = step_data.get("extract", {})
    if extract:
        results["steps"]["extract"] = {
            "status": extract.get("status"),
            "run_id": extract.get("run_id"),
            "url_count": extract.get("url_count", 0),
        }

    # Pipeline results
    for key in ("enrich", "compare", "monitor", "audit"):
        if key in step_data:
            results["steps"][key] = step_data[key]

    return results


async def _auto_advance(
    session: AsyncSession,
    playground: PlaygroundSession,
) -> None:
    """Check if underlying crawl runs / pipeline jobs finished and advance state."""
    step_data = dict(playground.step_data or {})

    if playground.state == "discovering":
        run_id = step_data.get("discover", {}).get("run_id")
        if run_id:
            run = await session.get(CrawlRun, run_id)
            if run and run.status in {s.value for s in TERMINAL_STATUSES}:
                # Pull discovered product URLs from the crawl records
                products = await _extract_discovered_products(session, run_id)
                step_data["discover"] = {
                    **step_data.get("discover", {}),
                    "status": "completed",
                    "products": products[:MAX_PRODUCTS],
                    "total_found": len(products),
                }
                playground.state = "discovered"
                playground.step_data = step_data

    elif playground.state == "extracting":
        run_id = step_data.get("extract", {}).get("run_id")
        if run_id:
            run = await session.get(CrawlRun, run_id)
            if run and run.status in {s.value for s in TERMINAL_STATUSES}:
                step_data["extract"] = {
                    **step_data.get("extract", {}),
                    "status": "completed",
                }
                playground.state = "extracted"
                playground.step_data = step_data

    elif playground.state == "running_pipeline":
        # Refresh the live status of each launched downstream job and decide
        # if the whole pipeline is done.
        mutated = False
        for key, refresher in (
            ("enrich", _refresh_enrich_status),
            ("compare", _refresh_compare_status),
            ("audit", _refresh_audit_status),
        ):
            info = step_data.get(key)
            if not info or not isinstance(info, dict):
                continue
            updated = await refresher(session, info)
            if updated is not None and updated != info:
                step_data[key] = updated
                mutated = True

        # Pipeline is done once no tracked job is still in a non-terminal state.
        all_done = True
        for key in ("enrich", "compare", "audit"):
            info = step_data.get(key, {})
            if isinstance(info, dict) and info.get("status") == "running":
                all_done = False
                break
        if all_done:
            playground.state = "complete"
            mutated = True
        if mutated:
            playground.step_data = step_data

    # Audit can be launched standalone (independent of extraction). Refresh
    # its status whenever it exists, regardless of the session state.
    if playground.state != "running_pipeline":
        audit_info = step_data.get("audit")
        if isinstance(audit_info, dict) and audit_info.get("status") == "running":
            updated = await _refresh_audit_status(session, audit_info)
            if updated is not None and updated != audit_info:
                step_data["audit"] = updated
                playground.step_data = step_data


async def _refresh_enrich_status(
    session: AsyncSession,
    info: dict[str, Any],
) -> dict[str, Any] | None:
    job_id = info.get("job_id")
    if not isinstance(job_id, int):
        return None
    from app.models.data_enrichment import DataEnrichmentJob

    job = await session.get(DataEnrichmentJob, job_id)
    if job is None:
        return None
    status = str(job.status or "").strip().lower()
    if status in _ENRICH_TERMINAL_STATUSES:
        return {**info, "status": status}
    return None


async def _refresh_compare_status(
    session: AsyncSession,
    info: dict[str, Any],
) -> dict[str, Any] | None:
    job_id = info.get("job_id")
    if not isinstance(job_id, int):
        return None
    from app.models.product_intelligence import ProductIntelligenceJob

    job = await session.get(ProductIntelligenceJob, job_id)
    if job is None:
        return None
    status = str(job.status or "").strip().lower()
    if status in _PI_TERMINAL_STATUSES:
        return {**info, "status": status}
    return None


async def _refresh_audit_status(
    session: AsyncSession,
    info: dict[str, Any],
) -> dict[str, Any] | None:
    job_id = info.get("job_id")
    if not isinstance(job_id, int):
        return None
    from app.models.ucp_audit import UCPAuditJob

    job = await session.get(UCPAuditJob, job_id)
    if job is None:
        return None
    status = str(job.status or "").strip().lower()
    if status in _AUDIT_TERMINAL_STATUSES:
        return {**info, "status": status}
    return None


async def _extract_discovered_products(
    session: AsyncSession,
    run_id: int,
) -> list[dict[str, Any]]:
    """Pull product data from crawl records for the discovery run."""
    rows = await session.scalars(
        select(CrawlRecord)
        .where(CrawlRecord.run_id == run_id)
        .limit(MAX_PRODUCTS)
    )
    products = []
    for record in rows.all():
        data = record.data or {}
        product_url = (
            data.get("url")
            or data.get("product_url")
            or data.get("detail_url")
            or data.get("canonical_url")
            or record.source_url
        )
        if product_url:
            products.append({
                "url": str(product_url),
                "title": str(data.get("title") or ""),
                "brand": str(data.get("brand") or ""),
                "price": str(data.get("price") or ""),
                "image": str(data.get("image") or data.get("image_url") or ""),
            })
    return products


def _require_state(playground: PlaygroundSession, expected: str) -> None:
    """Enforce state machine — playground must be in expected state."""
    if playground.state != expected:
        raise ValueError(
            f"Session is in state '{playground.state}', expected '{expected}'"
        )

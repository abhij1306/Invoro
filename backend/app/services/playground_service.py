"""Playground session orchestration service.

Coordinates existing crawl, enrichment, product intelligence, alert,
and UCP audit services into a guided pipeline for non-technical users.
"""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.playground import PlaygroundSession
from app.models.user import User
from app.services.crawl.ingestion_service import create_crawl_run_from_payload

logger = logging.getLogger(__name__)

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
    return playground


async def get_session(
    session: AsyncSession,
    *,
    session_id: int,
    user: User,
) -> PlaygroundSession:
    """Get a playground session, enforcing ownership."""
    playground = await session.get(PlaygroundSession, session_id)
    if playground is None or playground.user_id != user.id:
        raise LookupError("Session not found")
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
        **playground.step_data,
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
    playground.state = "discovered"
    step_data = dict(playground.step_data)
    step_data["discover"] = {
        **step_data.get("discover", {}),
        "status": "completed",
        "products": products[:200],  # cap stored results
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

    step_data = dict(playground.step_data)
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

    urls = playground.step_data.get("selected_urls", [])
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
    step_data = dict(playground.step_data)
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
) -> dict[str, Any]:
    """Launch selected downstream operations in parallel where possible."""
    _require_state(playground, "extracted")

    launched: dict[str, Any] = {}
    step_data = dict(playground.step_data)
    extract_run_id = step_data.get("extract", {}).get("run_id")

    if enrich and extract_run_id:
        from app.services.data_enrichment.service import (
            create_data_enrichment_job,
            run_data_enrichment_job,
        )
        job = await create_data_enrichment_job(
            session,
            user=user,
            payload={"run_id": extract_run_id},
        )
        launched["enrich"] = {"job_id": job.id, "status": "running"}
        # Fire async — background task would be better but keeping it simple
        # In production this would use BackgroundTasks
        step_data["enrich"] = launched["enrich"]

    if compare and extract_run_id:
        from app.services.product_intelligence.service import (
            create_product_intelligence_job,
            run_product_intelligence_job,
        )
        job = await create_product_intelligence_job(
            session,
            user=user,
            payload={"run_id": extract_run_id},
        )
        launched["compare"] = {"job_id": job.id, "status": "running"}
        step_data["compare"] = launched["compare"]

    if monitor:
        selected_urls = step_data.get("selected_urls", [])
        from app.services.alert_service import create_alert
        from app.schemas.alert import AlertCreate
        alert_payload = AlertCreate(
            name=f"Playground Monitor — {playground.input_url}",
            url=selected_urls[0] if selected_urls else playground.input_url,
            urls=selected_urls or [playground.input_url],
            tracked_fields=["price", "availability"],
        )
        monitor_obj, _run_id = await create_alert(
            session, user=user, payload=alert_payload
        )
        launched["monitor"] = {"alert_id": monitor_obj.id, "status": "created"}
        step_data["monitor"] = launched["monitor"]

    if audit:
        from app.services.ucp_audit.service import create_ucp_audit_job
        job = await create_ucp_audit_job(
            session,
            user=user,
            payload={"url": playground.input_url},
        )
        launched["audit"] = {"job_id": job.id, "status": "running"}
        step_data["audit"] = launched["audit"]

    playground.state = "running_pipeline"
    playground.step_data = step_data
    await session.flush()
    return launched


async def get_results(
    session: AsyncSession,
    *,
    playground: PlaygroundSession,
) -> dict[str, Any]:
    """Aggregate results from all pipeline steps."""
    step_data = dict(playground.step_data)
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


def _require_state(playground: PlaygroundSession, expected: str) -> None:
    """Enforce state machine — playground must be in expected state."""
    if playground.state != expected:
        raise ValueError(
            f"Session is in state '{playground.state}', expected '{expected}'"
        )

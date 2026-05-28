"""Playground session service.

Coordinates existing crawl, enrichment, product intelligence, alert,
and UCP audit services into a guided pipeline for non-technical users.
"""
from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

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
    ECOMMERCE_DETAIL_SURFACE,
)
from app.services.config.monitor_settings import MONITOR_PRIORITY_BACKGROUND
from app.services.config.product_intelligence import (
    PRODUCT_INTELLIGENCE_JOB_STATUS_COMPLETE,
    PRODUCT_INTELLIGENCE_JOB_STATUS_FAILED,
)
from app.services.crawl.ingestion_service import create_crawl_run_from_payload
from app.services.crawl.sitemap_resolver import resolve_category_urls_from_sitemap_result
from app.services.crawl.state import TERMINAL_STATUSES
from app.services.surface_resolver import resolve_auto_surface

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
    "created": ["sitemap_listed", "discovering", "extracting"],
    "sitemap_listed": ["discovering"],
    "discovering": ["discovered"],
    "discovered": ["extracting"],
    "extracting": ["extracted"],
    "extracted": ["running_pipeline"],
    "running_pipeline": ["complete"],
}

MAX_PRODUCTS = 50
SITEMAP_DISPLAY_LIMIT = 100


def _classify_input_url(url: str) -> str:
    """Decide which playground entry stage applies for the given URL.

    Returns one of ``"sitemap"`` (homepage / domain root),
    ``"listing"`` (category, search, shop), or ``"detail"`` (PDP, article).
    Pure URL inspection — relies on the existing ``resolve_auto_surface``
    helper for surface classification.
    """
    parsed = urlparse(url)
    path = (parsed.path or "").strip("/")
    # Domain root or trivially shallow path (no slugs) → sitemap stage.
    if not path:
        return "sitemap"
    resolution = resolve_auto_surface(url=url)
    surface = resolution.surface
    # Low-confidence fallback content_detail on a shallow path such as
    # `/en`, `/us`, or `/en-us` is usually a locale-root homepage, not a
    # real detail page. Treat it like sitemap entry so orchestration can
    # expand into categories or products instead of extracting the root URL.
    if (
        surface == "content_detail"
        and resolution.confidence < 0.5
        and path.count("/") == 0
    ):
        return "sitemap"
    if surface.endswith("_detail"):
        return "detail"
    if surface.endswith("_listing"):
        return "listing"
    return "listing"


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
    state_before = playground.state
    step_data_before = playground.step_data
    await _auto_advance(session, playground)
    # Only flush + refresh when auto-advance actually mutated the row.
    # Calling refresh on an unchanged row can trigger an implicit flush in
    # async sessions and surface a MissingGreenlet error during the reload
    # of server-computed columns (updated_at).
    if playground.state != state_before or playground.step_data != step_data_before:
        await session.flush()
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
) -> dict[str, Any]:
    """Route the input URL into the right entry stage.

    Three entry points, all driven by existing services:

    - ``sitemap``: homepage / domain root → fetch the sitemap and surface
      category URLs for the user to pick from. Sets state ``sitemap_listed``.
    - ``listing``: category / search URL → start a standard crawl on it
      (run_type=crawl, surface=auto). Sets state ``discovering``.
    - ``detail``: PDP / article URL → start a standard crawl directly
      against the URL and skip discover/select. Sets state ``extracting``.

    Returns a small payload describing what was started so the API layer
    can return useful info to the client.
    """
    _require_state(playground, "created")

    classification = _classify_input_url(playground.input_url)
    step_data = dict(playground.step_data or {})

    if classification == "sitemap":
        sitemap_source: str
        sitemap_error: str | None = None
        try:
            sitemap_resolution = await resolve_category_urls_from_sitemap_result(
                domain=playground.input_url,
                allow_homepage_fallback=True,
            )
            sitemap_urls = sitemap_resolution.urls
            sitemap_source = sitemap_resolution.source
        except Exception as exc:
            logger.warning(
                "Sitemap fetch failed for %s: %s", playground.input_url, exc
            )
            sitemap_urls = []
            sitemap_source = "failed"
            sitemap_error = type(exc).__name__
        # Limit what we expose to the user; everything else stays in step_data.
        step_data["sitemap"] = {
            "status": "completed",
            "source": sitemap_source,
            "urls": sitemap_urls[:SITEMAP_DISPLAY_LIMIT],
            "total_found": len(sitemap_urls),
        }
        if sitemap_error:
            step_data["sitemap"]["error"] = sitemap_error
        playground.state = "sitemap_listed"
        playground.step_data = step_data
        await session.flush()
        return {"stage": "sitemap", "url_count": len(sitemap_urls)}

    if classification == "detail":
        # Treat the URL as the only product to extract — same crawl call
        # Crawl Studio uses for a single PDP.
        run = await create_crawl_run_from_payload(
            session,
            user.id,
            {
                "run_type": "crawl",
                "url": playground.input_url,
                "surface": "auto",
                "settings": {"playground_session_id": playground.id},
            },
        )
        step_data["selected_urls"] = [playground.input_url]
        step_data["extract"] = {
            "run_id": run.id,
            "run_ids": [run.id],
            "status": "running",
            "url_count": 1,
            "skipped_discover": True,
        }
        playground.state = "extracting"
        playground.step_data = step_data
        await session.flush()
        return {"stage": "detail", "run_id": run.id}

    # Listing / category crawl — standard call shape.
    run = await create_crawl_run_from_payload(
        session,
        user.id,
        {
            "run_type": "crawl",
            "url": playground.input_url,
            "surface": "auto",
            "settings": {"playground_session_id": playground.id},
        },
    )
    step_data["discover"] = {"run_id": run.id, "status": "running"}
    playground.state = "discovering"
    playground.step_data = step_data
    await session.flush()
    return {"stage": "listing", "run_id": run.id}


async def select_category(
    session: AsyncSession,
    *,
    playground: PlaygroundSession,
    user: User,
    urls: list[str],
) -> int:
    """User picked one or more categories from the sitemap. Start crawl.

    Same call shape as the listing branch of ``start_discover``.
    """
    _require_state(playground, "sitemap_listed")
    normalized_urls = [url.strip() for url in urls if url and url.strip()]
    if not normalized_urls:
        raise ValueError("category URL is required")
    if len(normalized_urls) > MAX_PRODUCTS:
        raise ValueError(f"Maximum {MAX_PRODUCTS} category URLs per session")
    unique_urls = list(dict.fromkeys(normalized_urls))
    detail_urls, discover_urls = _partition_playground_urls(unique_urls)
    if detail_urls and not discover_urls:
        run_ids = await _launch_extract_runs(
            session,
            playground=playground,
            user=user,
            urls=detail_urls,
            skipped_discover=True,
        )
        return run_ids[0]

    run_type = "batch" if len(discover_urls) > 1 else "crawl"

    run = await create_crawl_run_from_payload(
        session,
        user.id,
        {
            "run_type": run_type,
            "url": discover_urls[0],
            "urls": discover_urls if len(discover_urls) > 1 else None,
            "surface": "auto",
            "settings": {"playground_session_id": playground.id},
        },
    )
    step_data = dict(playground.step_data or {})
    step_data["selected_category_url"] = discover_urls[0]
    step_data["selected_category_urls"] = discover_urls
    if detail_urls:
        step_data["seed_detail_urls"] = detail_urls
    step_data["discover"] = {"run_id": run.id, "status": "running"}
    playground.state = "discovering"
    playground.step_data = step_data
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
) -> list[int]:
    """Kick off PDP crawls for selected products.

    One standard ``run_type=crawl`` run per URL — same call shape Crawl
    Studio uses for a single product. The orchestrator just dispatches
    them in parallel; nothing else.
    """
    _require_state(playground, "discovered")

    urls = (playground.step_data or {}).get("selected_urls", [])
    if not urls:
        raise ValueError("No products selected — call select first")
    return await _launch_extract_runs(
        session,
        playground=playground,
        user=user,
        urls=urls,
    )


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
    extract_run_ids = _extract_run_ids(step_data)
    source_record_ids = await _extract_record_ids(session, extract_run_ids)

    if enrich:
        if not source_record_ids:
            launched["enrich"] = {
                "job_id": None,
                "status": "failed",
                "error": "No extracted records available",
            }
        else:
            from app.services.data_enrichment.service import (
                create_data_enrichment_job,
                run_data_enrichment_job,
            )
            try:
                enrich_job = await create_data_enrichment_job(
                    session,
                    user=user,
                    payload={"source_record_ids": source_record_ids},
                )
                launched["enrich"] = {"job_id": enrich_job.id, "status": "running"}
                dispatch_specs.append((run_data_enrichment_job, enrich_job.id))
            except Exception as exc:
                logger.error("Pipeline enrich failed: %s", exc, exc_info=True)
                launched["enrich"] = {
                    "job_id": None,
                    "status": "failed",
                    "error": str(exc),
                }
        step_data["enrich"] = launched["enrich"]

    if compare:
        if not source_record_ids:
            launched["compare"] = {
                "job_id": None,
                "status": "failed",
                "error": "No extracted records available",
            }
        else:
            from app.services.product_intelligence.service import (
                create_product_intelligence_job,
                run_product_intelligence_job,
            )
            try:
                compare_job = await create_product_intelligence_job(
                    session,
                    user=user,
                    payload={"source_record_ids": source_record_ids},
                )
                launched["compare"] = {"job_id": compare_job.id, "status": "running"}
                dispatch_specs.append((run_product_intelligence_job, compare_job.id))
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
        from app.services.monitor_service import create_monitor

        if not selected_urls:
            launched["monitor"] = {
                "monitor_id": None,
                "status": "failed",
                "error": "No extracted URLs available",
            }
        else:
            try:
                monitor_obj = await create_monitor(
                    session,
                    user=user,
                    payload={
                        "name": f"Playground monitor for {urlparse(selected_urls[0]).netloc or 'selected products'}",
                        "urls": selected_urls,
                        "surface": ECOMMERCE_DETAIL_SURFACE,
                        "tracked_fields": ["price", "availability"],
                        "requested_fields": ["price", "availability"],
                        "schedule_interval_hours": 24,
                        "priority": MONITOR_PRIORITY_BACKGROUND,
                    },
                )
                launched["monitor"] = {
                    "monitor_id": monitor_obj.id,
                    "status": "created",
                    "url_count": len(selected_urls),
                }
            except Exception as exc:
                logger.error("Pipeline monitor failed: %s", exc, exc_info=True)
                launched["monitor"] = {
                    "monitor_id": None,
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
            audit_job = await create_ucp_audit_job(
                session,
                user=user,
                payload={"domain": playground.input_url},
            )
            launched["audit"] = {"job_id": audit_job.id, "status": "running"}
            dispatch_specs.append((run_ucp_audit_job, audit_job.id))
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
        records = await _extract_records(session, _extract_run_ids(step_data))
        results["steps"]["extract"] = {
            "status": extract.get("status"),
            "run_id": extract.get("run_id"),
            "run_ids": _extract_run_ids(step_data),
            "url_count": extract.get("url_count", 0),
            "record_count": len(records),
            "records": records,
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
                products = _merge_seed_detail_products(step_data, products)
                step_data["discover"] = {
                    **step_data.get("discover", {}),
                    "status": "completed",
                    "products": products[:MAX_PRODUCTS],
                    "total_found": len(products),
                }
                playground.state = "discovered"
                playground.step_data = step_data

    elif playground.state == "extracting":
        extract_info = step_data.get("extract", {}) or {}
        extract_runs = await _resolve_extract_runs(
            session,
            playground=playground,
            step_data=step_data,
        )
        resolved_run_ids = [int(run.id) for run in extract_runs]
        if resolved_run_ids:
            step_data["extract"] = {
                **extract_info,
                "run_id": resolved_run_ids[0],
                "run_ids": resolved_run_ids,
            }
            extract_info = step_data["extract"]
        expected_run_count = _expected_extract_run_count(step_data)
        if resolved_run_ids and len(resolved_run_ids) >= expected_run_count:
            terminal = {s.value for s in TERMINAL_STATUSES}
            statuses = [str(run.status) for run in extract_runs]
            # All resolved session-owned runs must reach a terminal status
            # before we transition.
            if all(status in terminal for status in statuses):
                step_data["extract"] = {
                    **extract_info,
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


async def _launch_extract_runs(
    session: AsyncSession,
    *,
    playground: PlaygroundSession,
    user: User,
    urls: list[str],
    skipped_discover: bool = False,
) -> list[int]:
    run_ids: list[int] = []
    for product_url in urls:
        run = await create_crawl_run_from_payload(
            session,
            user.id,
            {
                "run_type": "crawl",
                "url": product_url,
                "surface": "auto",
                "settings": {"playground_session_id": playground.id},
            },
        )
        run_ids.append(run.id)

    playground.state = "extracting"
    step_data = dict(playground.step_data or {})
    step_data["selected_urls"] = list(urls)
    step_data["extract"] = {
        "run_id": run_ids[0],
        "run_ids": run_ids,
        "status": "running",
        "url_count": len(urls),
        "skipped_discover": skipped_discover,
    }
    playground.step_data = step_data
    await session.flush()
    return run_ids


def _partition_playground_urls(urls: list[str]) -> tuple[list[str], list[str]]:
    detail_urls: list[str] = []
    discover_urls: list[str] = []
    for url in urls:
        if _classify_input_url(url) == "detail":
            detail_urls.append(url)
        else:
            discover_urls.append(url)
    return detail_urls, discover_urls


def _merge_seed_detail_products(
    step_data: dict[str, Any],
    discovered_products: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    seen: set[str] = set()
    for seed_url in step_data.get("seed_detail_urls", []) or []:
        normalized = str(seed_url or "").strip()
        if not normalized or normalized in seen:
            continue
        merged.append({"url": normalized, "title": "", "brand": "", "price": "", "image": ""})
        seen.add(normalized)
    for product in discovered_products:
        normalized = str(product.get("url") or "").strip()
        if not normalized or normalized in seen:
            continue
        merged.append(product)
        seen.add(normalized)
    return merged


def _extract_run_ids(step_data: dict[str, Any]) -> list[int]:
    extract = step_data.get("extract", {}) or {}
    raw_run_ids = extract.get("run_ids")
    if isinstance(raw_run_ids, list):
        run_ids = [
            run_id
            for run_id in raw_run_ids
            if isinstance(run_id, int) and run_id > 0
        ]
        if run_ids:
            return run_ids
    run_id = extract.get("run_id")
    if isinstance(run_id, int) and run_id > 0:
        return [run_id]
    return []


async def _extract_record_ids(
    session: AsyncSession,
    run_ids: list[int],
) -> list[int]:
    if not run_ids:
        return []
    rows = await session.scalars(
        select(CrawlRecord.id)
        .where(CrawlRecord.run_id.in_(run_ids))
        .order_by(CrawlRecord.run_id.asc(), CrawlRecord.id.asc())
    )
    return [int(record_id) for record_id in rows.all() if record_id is not None]


async def _extract_records(
    session: AsyncSession,
    run_ids: list[int],
) -> list[dict[str, Any]]:
    if not run_ids:
        return []
    rows = await session.scalars(
        select(CrawlRecord)
        .where(CrawlRecord.run_id.in_(run_ids))
        .order_by(CrawlRecord.run_id.asc(), CrawlRecord.id.asc())
    )
    records: list[dict[str, Any]] = []
    for record in rows.all():
        records.append(
            {
                "id": int(record.id),
                "run_id": int(record.run_id),
                "source_url": str(record.source_url),
                "data": dict(record.data or {}),
            }
        )
    return records


def _extract_selected_urls(step_data: dict[str, Any]) -> list[str]:
    selected_urls = step_data.get("selected_urls")
    if not isinstance(selected_urls, list):
        return []
    return [
        url.strip()
        for url in selected_urls
        if isinstance(url, str) and url.strip()
    ]


def _expected_extract_run_count(step_data: dict[str, Any]) -> int:
    extract = step_data.get("extract", {}) or {}
    url_count = extract.get("url_count")
    expected = max(
        len(_extract_selected_urls(step_data)),
        url_count if isinstance(url_count, int) and url_count > 0 else 0,
    )
    if expected > 0:
        return expected
    run_ids = _extract_run_ids(step_data)
    return len(run_ids)


async def _resolve_extract_runs(
    session: AsyncSession,
    *,
    playground: PlaygroundSession,
    step_data: dict[str, Any],
) -> list[CrawlRun]:
    resolved: dict[int, CrawlRun] = {}
    for run_id in _extract_run_ids(step_data):
        run = await session.get(CrawlRun, run_id)
        if run is not None:
            resolved[int(run.id)] = run

    selected_urls = _extract_selected_urls(step_data)
    if selected_urls:
        rows = await session.scalars(
            select(CrawlRun)
            .where(
                CrawlRun.user_id == playground.user_id,
                CrawlRun.run_type == "crawl",
                CrawlRun.url.in_(selected_urls),
                CrawlRun.created_at >= playground.created_at,
            )
            .order_by(CrawlRun.id.asc())
        )
        for run in rows.all():
            settings = run.settings if isinstance(run.settings, dict) else {}
            if settings.get("playground_session_id") != playground.id:
                continue
            resolved.setdefault(int(run.id), run)

    return [resolved[run_id] for run_id in sorted(resolved)]


def _require_state(playground: PlaygroundSession, expected: str) -> None:
    """Enforce state machine — playground must be in expected state."""
    if playground.state != expected:
        raise ValueError(
            f"Session is in state '{playground.state}', expected '{expected}'"
        )

from __future__ import annotations

import logging
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.playground import PlaygroundSession
from app.models.user import User
from app.services.config.data_enrichment import (
    DATA_ENRICHMENT_JOB_TERMINAL_STATUSES,
    ECOMMERCE_DETAIL_SURFACE,
    ECOMMERCE_LISTING_SURFACE,
)
from app.services.config.monitor_settings import MONITOR_PRIORITY_BACKGROUND
from app.services.config.product_intelligence import (
    PRODUCT_INTELLIGENCE_JOB_STATUS_COMPLETE,
    PRODUCT_INTELLIGENCE_JOB_STATUS_FAILED,
)
from app.services.config.sitemap import (
    PLAYGROUND_CATEGORY_DEFAULT_LIMIT,
    PLAYGROUND_CATEGORY_MAX_LIMIT,
)
from app.services.crawl.category_discovery import discover_category_urls
from app.services.crawl.ingestion_service import create_crawl_run_from_payload
from app.services.playground_progress import (
    auto_advance as _auto_advance,
    extract_record_ids as _extract_record_ids,
    extract_run_ids as _extract_run_ids,
    get_results as get_results,
    merge_seed_detail_products,
)
from app.services.surface_resolver import resolve_auto_surface

logger = logging.getLogger(__name__)

_PI_TERMINAL_STATUSES = {
    PRODUCT_INTELLIGENCE_JOB_STATUS_COMPLETE,
    PRODUCT_INTELLIGENCE_JOB_STATUS_FAILED,
}
_ENRICH_TERMINAL_STATUSES = set(DATA_ENRICHMENT_JOB_TERMINAL_STATUSES)

MAX_PRODUCTS = 50
_merge_seed_detail_products = merge_seed_detail_products


def _classify_input_url(url: str) -> str:
    parsed = urlparse(url)
    path = (parsed.path or "").strip("/")
    if not path:
        return "sitemap"
    resolution = resolve_auto_surface(url=url)
    surface = resolution.surface
    if (
        surface == "content_detail"
        and resolution.confidence < 0.5
        and path.count("/") == 0
    ):
        return "sitemap"
    if surface.endswith("_detail"):
        return "detail"
    if surface == ECOMMERCE_LISTING_SURFACE or surface.endswith("_listing"):
        return "listing"
    return "listing"


def _detail_surface_for_url(url: str) -> str:
    surface = resolve_auto_surface(url=url).surface
    return surface if surface.endswith("_detail") else ECOMMERCE_DETAIL_SURFACE


async def create_session(
    session: AsyncSession,
    *,
    user: User,
    url: str | None = None,
    urls: list[str] | None = None,
    category_limit: int = PLAYGROUND_CATEGORY_DEFAULT_LIMIT,
) -> PlaygroundSession:
    input_values: list[str] = [
        item for item in [url, *(urls or [])] if item is not None
    ]
    input_urls = _normalize_input_urls(input_values)
    if not input_urls:
        raise ValueError("URL is required")
    if len(input_urls) > MAX_PRODUCTS:
        raise ValueError(f"Maximum {MAX_PRODUCTS} input URLs per session")

    safe_category_limit = _safe_category_limit(category_limit)
    step_data: dict[str, object] = {"category_limit": safe_category_limit}
    if len(input_urls) > 1:
        step_data["input_urls"] = input_urls

    playground = PlaygroundSession(
        user_id=user.id,
        input_url=input_urls[0],
        state="created",
        step_data=step_data,
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
    playground = await session.get(PlaygroundSession, session_id)
    if playground is None or playground.user_id != user.id:
        raise LookupError("Session not found")
    _ = playground.step_data
    state_before = playground.state
    step_data_before = playground.step_data
    await _auto_advance(session, playground)
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
    _require_state(playground, "created")

    classification = _classify_input_url(playground.input_url)
    step_data = dict(playground.step_data or {})
    input_urls = _session_input_urls(playground)
    category_limit = _session_category_limit(playground)

    if len(input_urls) > 1:
        detail_urls, discover_urls = _partition_playground_urls(input_urls)
        if detail_urls and not discover_urls:
            run_ids = await _launch_extract_runs(
                session,
                playground=playground,
                user=user,
                urls=detail_urls,
                skipped_discover=True,
            )
            return {"stage": "detail", "run_id": run_ids[0]}
        if detail_urls:
            step_data["seed_detail_urls"] = detail_urls

        sitemap = await _resolve_category_list_for_inputs(
            discover_urls,
            limit=category_limit,
        )
        step_data["sitemap"] = sitemap
        playground.state = "sitemap_listed"
        playground.step_data = step_data
        await session.flush()
        return {"stage": "sitemap", "url_count": int(sitemap["total_found"])}

    if classification == "sitemap":
        sitemap = await _resolve_category_list_for_inputs(
            [playground.input_url],
            limit=category_limit,
        )
        first_tree = sitemap.get("trees", {}).get(playground.input_url)
        if first_tree:
            sitemap["nav_tree"] = first_tree
        first_error = sitemap.get("errors", {}).get(playground.input_url)
        if first_error:
            sitemap["error"] = first_error
        step_data["sitemap"] = sitemap
        playground.state = "sitemap_listed"
        playground.step_data = step_data
        await session.flush()
        return {"stage": "sitemap", "url_count": int(sitemap["total_found"])}

    if classification == "detail":
        run = await create_crawl_run_from_payload(
            session,
            user.id,
            {
                "run_type": "crawl",
                "url": playground.input_url,
                "surface": _detail_surface_for_url(playground.input_url),
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

    run = await create_crawl_run_from_payload(
        session,
        user.id,
        {
            "run_type": "crawl",
            "url": playground.input_url,
            "surface": ECOMMERCE_LISTING_SURFACE,
            "settings": {"playground_session_id": playground.id},
        },
    )
    step_data["discover"] = {"run_id": run.id, "status": "running"}
    playground.state = "discovering"
    playground.step_data = step_data
    await session.flush()
    return {"stage": "listing", "run_id": run.id}


# skipcq: PY-R1000
async def _resolve_category_list_for_inputs(
    urls: list[str],
    *,
    limit: int,
) -> dict[str, Any]:
    discover_urls, input_listing_urls = _partition_category_inputs(urls)
    discovered: dict[str, Any] = (
        await discover_category_urls(discover_urls, limit=limit)
        if discover_urls
        else _empty_category_discovery(limit)
    )
    input_groups = {url: [url] for url in input_listing_urls}
    input_sources = dict.fromkeys(input_listing_urls, "input")
    flat_urls = list(
        dict.fromkeys(
            [
                url
                for url in [*input_listing_urls, *list(discovered.get("urls") or [])]
                if isinstance(url, str)
            ]
        )
    )
    discovered_total = int(discovered.get("total_found") or 0)
    total_found = max(len(flat_urls), discovered_total + len(input_listing_urls))
    return {
        "status": "completed",
        "source": _category_result_source(
            discovered,
            input_listing_urls=input_listing_urls,
            discover_urls=discover_urls,
        ),
        "sources": {**input_sources, **dict(discovered.get("sources") or {})},
        "urls": flat_urls[:limit],
        "groups": {**input_groups, **dict(discovered.get("groups") or {})},
        "trees": dict(discovered.get("trees") or {}),
        "errors": dict(discovered.get("errors") or {}),
        "diagnostics": dict(discovered.get("diagnostics") or {}),
        "total_found": total_found,
        "limit": limit,
    }


def _partition_category_inputs(urls: list[str]) -> tuple[list[str], list[str]]:
    discover_urls: list[str] = []
    listing_urls: list[str] = []
    for url in urls:
        classification = _classify_input_url(url)
        if classification == "listing":
            listing_urls.append(url)
        elif classification != "detail":
            discover_urls.append(url)
    return discover_urls, listing_urls


def _empty_category_discovery(limit: int) -> dict[str, Any]:
    return {
        "status": "completed",
        "source": "input",
        "sources": {},
        "urls": [],
        "groups": {},
        "trees": {},
        "errors": {},
        "diagnostics": {},
        "total_found": 0,
        "limit": limit,
    }


def _category_result_source(
    discovered: dict[str, Any],
    *,
    input_listing_urls: list[str],
    discover_urls: list[str],
) -> str:
    if input_listing_urls:
        return "multi" if discover_urls else "input"
    return str(discovered.get("source") or "multi")


async def select_category(
    session: AsyncSession,
    *,
    playground: PlaygroundSession,
    user: User,
    urls: list[str],
) -> int:
    _require_state(playground, "sitemap_listed")
    normalized_urls = [url.strip() for url in urls if url and url.strip()]
    if not normalized_urls:
        raise ValueError("category URL is required")
    unique_urls = list(dict.fromkeys(_validate_http_urls(normalized_urls)))
    if len(unique_urls) > MAX_PRODUCTS:
        raise ValueError(f"Maximum {MAX_PRODUCTS} category URLs per session")
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
            "surface": ECOMMERCE_LISTING_SURFACE,
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
) -> tuple[dict[str, Any], list[tuple[Any, int]]]:
    needs_extracted = _validate_pipeline_start(
        playground, enrich=enrich, compare=compare, monitor=monitor
    )

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

    if needs_extracted:
        playground.state = "running_pipeline"
    playground.step_data = step_data
    await session.flush()
    return launched, dispatch_specs


def _validate_pipeline_start(
    playground: PlaygroundSession, *, enrich: bool, compare: bool, monitor: bool
) -> bool:
    needs_extracted = any((enrich, compare, monitor))
    if needs_extracted:
        _require_state(playground, "extracted")
    elif playground.state == "created":
        raise ValueError("Session not started — call discover first")
    return needs_extracted


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
                "surface": _detail_surface_for_url(product_url),
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


def _validate_http_urls(urls: list[str]) -> list[str]:
    valid: list[str] = []
    invalid: list[str] = []
    for url in urls:
        parsed = urlparse(url)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            invalid.append(url)
            continue
        valid.append(url)
    if invalid:
        raise ValueError(f"Invalid URL(s): {', '.join(invalid)}")
    return valid


def _normalize_input_urls(values: list[str]) -> list[str]:
    normalized: list[str] = []
    for raw_value in values:
        for item in str(raw_value or "").splitlines():
            candidate = item.strip()
            if not candidate:
                continue
            if not candidate.startswith(("http://", "https://")):
                candidate = f"https://{candidate}"
            normalized.append(candidate)
    return list(dict.fromkeys(_validate_http_urls(normalized)))


def _session_input_urls(playground: PlaygroundSession) -> list[str]:
    step_data = dict(playground.step_data or {})
    input_urls = step_data.get("input_urls")
    if isinstance(input_urls, list):
        normalized = [
            item.strip()
            for item in input_urls
            if isinstance(item, str) and item.strip()
        ]
        if normalized:
            return normalized
    return [playground.input_url]


def _safe_category_limit(value: object) -> int:
    try:
        candidate = (
            int(value)
            if isinstance(value, (int, float, str))
            else PLAYGROUND_CATEGORY_DEFAULT_LIMIT
        )
    except (TypeError, ValueError):
        candidate = PLAYGROUND_CATEGORY_DEFAULT_LIMIT
    return max(1, min(candidate, PLAYGROUND_CATEGORY_MAX_LIMIT))


def _session_category_limit(playground: PlaygroundSession) -> int:
    return _safe_category_limit(
        dict(playground.step_data or {}).get(
            "category_limit",
            PLAYGROUND_CATEGORY_DEFAULT_LIMIT,
        )
    )


def _require_state(playground: PlaygroundSession, expected: str) -> None:
    if playground.state != expected:
        raise ValueError(
            f"Session is in state '{playground.state}', expected '{expected}'"
        )

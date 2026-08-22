from __future__ import annotations

import asyncio
import logging
from contextlib import suppress
from datetime import UTC, datetime

from app.core.database import SessionLocal
from app.core.config import settings  # noqa: F401 - compatibility test seam
from app.core.logfire_integration import logfire_span, set_logfire_attributes
from app.models.crawl_run import CrawlRun
from app.services.crawl.state import (
    CONTROL_REQUEST_KILL,
    CONTROL_REQUEST_PAUSE,
    TERMINAL_STATUSES,
    CrawlStatus,
    get_control_request,
    set_control_request,
    update_run_status,
)
from app.services.crawl.sitemap_resolver import resolve_category_urls_with_site_links
from app.services.crawl.batch_parallel import (
    parallel_url_concurrency,
    process_urls_in_parallel,
)
from app.services.crawl.utils import normalize_target_url, parse_csv_urls_async
from app.services.config.sitemap import (
    SITEMAP_DEFAULT_FILTER_KEYWORD,
    SITEMAP_DEFAULT_MAX_URLS,
)
from app.services.config.runtime_settings import (
    crawler_runtime_settings,
)
from app.services.config.design_system import DESIGN_SYSTEM_SURFACE
from app.services.design_system import process_design_system_run
from app.services.domain_utils import normalize_domain
from app.services.pipeline.extraction_loop import process_single_url
from app.services.pipeline.run_complete_callbacks import on_run_complete
from app.services.pipeline.run_progress import BatchRunProgressState
from app.services.pipeline.runtime_helpers import (
    STAGE_ACQUIRE,
    STAGE_PERSIST,
    log_event,
    mark_run_failed,
    set_stage,
)
from app.services.pipeline.types import URLProcessingConfig, URLProcessingResult
from app.services.publish import VERDICT_ERROR, aggregate_verdict
from app.services.run_summary import as_int
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


class _URLProcessingDeadlineExceeded(TimeoutError):
    pass


async def _run_url_processing_with_timeout(operation, timeout_seconds: float):
    task = asyncio.create_task(operation)
    try:
        done, _pending = await asyncio.wait(
            {task},
            timeout=max(0.001, float(timeout_seconds)),
            return_when=asyncio.FIRST_COMPLETED,
        )
    except asyncio.CancelledError:
        task.cancel()
        with suppress(asyncio.CancelledError):
            _ = await task
        raise
    if task in done:
        return task.result()
    task.cancel()
    with suppress(asyncio.CancelledError):
        _ = await task
    raise _URLProcessingDeadlineExceeded(f"URL processing exceeded timeout_seconds={timeout_seconds}")


async def resolve_category_urls_from_sitemap(
    domain: str,
    filter_keyword: str,
    max_urls: int,
    allow_homepage_fallback: bool = False,
) -> list[str]:
    result = await resolve_category_urls_with_site_links(
        domain=domain,
        filter_keyword=filter_keyword,
        max_urls=max_urls,
        allow_homepage_fallback=allow_homepage_fallback,
        category_only=True,
    )
    return result.urls


def _require_url_processing_result(url_result: object) -> URLProcessingResult:
    if isinstance(url_result, URLProcessingResult):
        return url_result
    raise TypeError(f"Unexpected URL result type: {type(url_result)!r}")


async def _prewarm_browser_pool() -> None:
    return None


def _safe_sitemap_max_urls(value: object) -> int:
    try:
        candidate = value if value not in (None, "") else SITEMAP_DEFAULT_MAX_URLS
        return int(str(candidate))
    except (TypeError, ValueError):
        return SITEMAP_DEFAULT_MAX_URLS


def _allow_sitemap_homepage_fallback(run: CrawlRun, settings_view) -> bool:
    requested_surface = str(run.surface or "").strip().lower()
    if requested_surface == "auto":
        return True
    resolution = settings_view.get("surface_resolution")
    if not isinstance(resolution, dict):
        return False
    evidence = resolution.get("evidence")
    if not isinstance(evidence, list):
        return False
    return "requested_surface:auto" in {str(item).strip().lower() for item in evidence if item}


async def _resolve_run_urls(run: CrawlRun, settings_view) -> list[str]:
    urls = settings_view.urls()
    if run.run_type == "batch" and urls:
        url_list = urls
    elif run.run_type == "csv" and settings_view.get("csv_content"):
        url_list = await parse_csv_urls_async(settings_view.get("csv_content"))
    elif settings_view.get("sitemap_domain"):
        url_list = await resolve_category_urls_from_sitemap(
            domain=settings_view.get("sitemap_domain"),
            filter_keyword=settings_view.get("sitemap_filter_keyword") or SITEMAP_DEFAULT_FILTER_KEYWORD,
            max_urls=_safe_sitemap_max_urls(settings_view.get("sitemap_max_urls")),
            allow_homepage_fallback=_allow_sitemap_homepage_fallback(run, settings_view),
        )
    elif run.url:
        url_list = [run.url]
    else:
        raise ValueError("No URL provided")
    return [value for value in (normalize_target_url(item) for item in url_list) if value]


def _current_duration_ms(run: CrawlRun) -> int:
    if not isinstance(run.created_at, datetime):
        return 0
    return max(0, int((datetime.now(UTC) - run.created_at).total_seconds() * 1000))


def _touch_run_heartbeat(run: CrawlRun) -> None:
    run.last_heartbeat_at = datetime.now(UTC)


def _url_timeout_seconds(settings_view) -> float:
    configured_timeout = settings_view.get("url_timeout_seconds")
    if configured_timeout not in (None, ""):
        return settings_view.url_timeout_seconds()
    base_timeout = crawler_runtime_settings.default_url_process_timeout_seconds()
    # Extend timeout when traversal is active — pagination/scroll can take
    # significantly longer than a single-page fetch+extract cycle.
    traversal_mode = settings_view.traversal_mode()
    if traversal_mode:
        raw_max_pages = settings_view.max_pages()
        raw_max_scrolls = settings_view.max_scrolls()
        max_pages = int(raw_max_pages) if raw_max_pages is not None else 1
        max_scrolls = int(raw_max_scrolls) if raw_max_scrolls is not None else 1
        traversal_pages = max(max_pages, max_scrolls)
        # Allow ~30s per traversal page on top of the base timeout, capped at max.
        traversal_budget = traversal_pages * 30.0
        extended = base_timeout + traversal_budget
        return min(extended, float(crawler_runtime_settings.max_url_process_timeout_seconds))
    return base_timeout


def _url_failure_metrics(exc: BaseException) -> dict[str, object]:
    metrics: dict[str, object] = {"error": f"{type(exc).__name__}: {exc}"}
    browser_diagnostics = getattr(exc, "browser_diagnostics", None)
    if not isinstance(browser_diagnostics, dict):
        return metrics
    diagnostics = dict(browser_diagnostics)
    metrics["browser_diagnostics"] = diagnostics
    failure_reason = str(diagnostics.get("failure_reason") or "").strip()
    if failure_reason:
        metrics["failure_reason"] = failure_reason
    browser_outcome = str(diagnostics.get("browser_outcome") or "").strip()
    if browser_outcome:
        metrics["browser_outcome"] = browser_outcome
    if diagnostics.get("browser_attempted") is not None:
        metrics["browser_attempted"] = bool(diagnostics.get("browser_attempted"))
    return metrics


async def _rollback_url_session(session: AsyncSession, *, context: str) -> bool:
    try:
        await session.rollback()
        session.expire_all()
        return True
    except Exception:
        logger.debug("Session rollback failed during %s", context, exc_info=True)
        return False


async def _recover_url_failure(
    session: AsyncSession,
    *,
    run: CrawlRun | None = None,
    run_id: int,
    url: str,
    exc: BaseException,
    log_message: str,
) -> tuple[CrawlRun, URLProcessingResult]:
    await _rollback_url_session(session, context="URL failure recovery")
    if run is not None:
        with suppress(Exception):
            session.expire(run)
        with suppress(Exception):
            await session.refresh(run)
    recovery_error: Exception | None = None
    try:
        run = await _persist_url_failure_log(
            session,
            run_id=run_id,
            url=url,
            exc=exc,
            log_message=log_message,
        )
    except Exception as original_session_error:
        recovery_error = original_session_error
        logger.debug(
            "Original session unusable for URL failure recovery; falling back to SessionLocal",
            exc_info=True,
        )
        await _rollback_url_session(session, context="before URL recovery fallback")
        try:
            async with SessionLocal() as recovery:
                await _persist_url_failure_log(
                    recovery,
                    run_id=run_id,
                    url=url,
                    exc=exc,
                    log_message=log_message,
                )
        except Exception as fallback_error:
            recovery_error = fallback_error
            logger.exception(
                "Failed to persist URL failure log for run=%s url=%s",
                run_id,
                url,
            )
        await _rollback_url_session(session, context="after URL recovery fallback")
        try:
            reloaded_run = await session.get(CrawlRun, run_id, populate_existing=True)
        except Exception as reload_error:
            logger.debug(
                "Failed to reload run after URL failure recovery; keeping current instance",
                exc_info=True,
            )
            if run is None:
                raise RuntimeError(
                    f"Original session unusable after URL failure recovery for run {run_id}"
                ) from reload_error
        else:
            if reloaded_run is not None:
                run = reloaded_run
    if run is None:
        raise RuntimeError(f"Run {run_id} disappeared after URL failure") from exc
    metrics = _url_failure_metrics(exc)
    if recovery_error is not None:
        metrics["failure_log_persistence_error"] = f"{type(recovery_error).__name__}: {recovery_error}"
        metrics["failure_log_persisted"] = False
    return run, URLProcessingResult(
        records=[],
        verdict=VERDICT_ERROR,
        url_metrics=metrics,
    )


async def _persist_url_failure_log(
    session: AsyncSession,
    *,
    run_id: int,
    url: str,
    exc: BaseException,
    log_message: str,
) -> CrawlRun:
    run = await session.get(CrawlRun, run_id, populate_existing=True)
    if run is None:
        raise RuntimeError(f"Run {run_id} disappeared after URL failure") from exc
    logger.warning("URL processing failed for run=%s url=%s", run_id, url, exc_info=True)
    event_message = log_message
    if not event_message.startswith("[url:"):
        event_message = f"[url:{url}] {event_message}"
    await log_event(session, run.id, "warning", event_message)
    await session.commit()
    return run


def _url_start_message(*, url: str, idx: int, total_urls: int) -> str:
    if idx == 1:
        return f"Starting crawl run for {url}"
    return f"Starting crawl run for {url} ({idx}/{total_urls})"


async def _process_url_in_parallel(
    *,
    run_id: int,
    idx: int,
    total_urls: int,
    url: str,
    max_records: int,
    url_timeout_seconds: float,
) -> tuple[int, str, URLProcessingResult]:
    async with SessionLocal() as url_session:
        run = await url_session.get(CrawlRun, run_id, populate_existing=True)
        if run is None:
            raise RuntimeError(f"Run {run_id} disappeared before URL processing")
        await log_event(
            url_session,
            run.id,
            "info",
            _url_start_message(url=url, idx=idx, total_urls=total_urls),
        )
        await url_session.commit()
        url_config = URLProcessingConfig.from_acquisition_plan(
            run.settings_view.acquisition_plan(
                surface=run.surface,
                max_records=max(1, max_records),
            ),
            update_run_state=False,
            persist_logs=True,
        )
        try:
            with logfire_span(
                "pipeline.url",
                run_id=run.id,
                url_index=idx,
                url_count=total_urls,
                domain=normalize_domain(url),
                surface=run.surface,
                max_records=max_records,
                timeout_seconds=url_timeout_seconds,
            ) as url_span:
                url_result = _require_url_processing_result(
                    await _run_url_processing_with_timeout(
                        process_single_url(
                            session=url_session,
                            run=run,
                            url=url,
                            config=url_config,
                        ),
                        url_timeout_seconds,
                    )
                )
                set_logfire_attributes(
                    url_span,
                    verdict=url_result.verdict,
                    record_count=_url_metric(
                        url_result,
                        "record_count",
                        len(url_result.records),
                    ),
                    method=_url_metric(url_result, "method"),
                    blocked=_url_metric(url_result, "blocked"),
                )
            await url_session.commit()
        except _URLProcessingDeadlineExceeded as exc:
            logger.warning("URL processing timed out for run=%s url=%s", run.id, url)
            run, url_result = await _recover_url_failure(
                url_session,
                run=run,
                run_id=run.id,
                url=url,
                exc=exc,
                log_message=(f"URL processing timed out for {url} (timeout_seconds={url_timeout_seconds})"),
            )
            url_result.url_metrics["error"] = f"TimeoutError: url exceeded timeout_seconds={url_timeout_seconds}"
        except Exception as exc:
            run, url_result = await _recover_url_failure(
                url_session,
                run=run,
                run_id=run.id,
                url=url,
                exc=exc,
                log_message=f"URL processing failed for {url}: {type(exc).__name__}: {exc}",
            )
        return idx, url, url_result


async def _process_urls_in_parallel(
    session: AsyncSession,
    *,
    run: CrawlRun,
    settings_view,
    url_list: list[str],
    progress_state: BatchRunProgressState,
    max_records: int,
    url_timeout_seconds: float,
) -> tuple[CrawlRun, list[str], int]:
    return await process_urls_in_parallel(
        session,
        run=run,
        settings_view=settings_view,
        url_list=url_list,
        progress_state=progress_state,
        max_records=max_records,
        url_timeout_seconds=url_timeout_seconds,
        process_url=_process_url_in_parallel,
        url_metric=_url_metric,
        touch_heartbeat=_touch_run_heartbeat,
        current_duration_ms=_current_duration_ms,
    )


async def _process_urls_sequential(
    session: AsyncSession,
    *,
    run: CrawlRun,
    url_list: list[str],
    progress_state: BatchRunProgressState,
    max_records: int,
    sleep_ms: int,
    url_timeout_seconds: float,
    run_span,
) -> tuple[list[str], int]:
    verdicts: list[str] = []
    record_count = as_int(run.get_summary("record_count", 0))
    total_urls = len(url_list)
    for idx, url in enumerate(url_list, start=1):
        await session.refresh(run)
        _touch_run_heartbeat(run)
        if await _apply_sequential_control_request(session, run):
            return run, verdicts, record_count
        await _log_sequential_url_start(session, run, url=url, idx=idx, total_urls=total_urls)
        remaining_records = max(max_records - record_count, 1)
        run, result = await _process_sequential_url(
            session,
            run=run,
            url=url,
            idx=idx,
            total_urls=total_urls,
            remaining_records=remaining_records,
            url_timeout_seconds=url_timeout_seconds,
        )
        verdict = str(result.verdict or VERDICT_ERROR)
        verdicts.append(verdict)
        records_count = as_int(_url_metric(result, "record_count", len(result.records)))
        record_count += records_count
        set_logfire_attributes(
            run_span,
            record_count=record_count,
            last_url_verdict=verdict,
        )
        progress_state.record_url_result(
            idx=idx - 1,
            records_count=records_count,
            verdict=verdict,
            url_metrics=result.url_metrics,
        )
        _touch_run_heartbeat(run)
        run.update_summary(
            **progress_state.build_progress_patch(current_url=url, current_url_index=idx),
            duration_ms=_current_duration_ms(run),
        )
        await session.commit()
        if record_count >= max_records:
            await log_event(
                session,
                run.id,
                "info",
                f"Stopped after reaching max_records={max_records}",
            )
            await session.commit()
            break
        if sleep_ms > 0 and idx < total_urls:
            await asyncio.sleep(sleep_ms / 1000)
    return run, verdicts, record_count


async def _apply_sequential_control_request(session: AsyncSession, run: CrawlRun) -> bool:
    control_request = get_control_request(run)
    if control_request not in (CONTROL_REQUEST_PAUSE, CONTROL_REQUEST_KILL):
        return False
    paused = control_request == CONTROL_REQUEST_PAUSE
    update_run_status(run, CrawlStatus.PAUSED if paused else CrawlStatus.KILLED)
    set_control_request(run, None)
    await log_event(
        session,
        run.id,
        "warning",
        f"Run {'paused' if paused else 'killed'} at checkpoint",
    )
    await session.commit()
    return True


async def _log_sequential_url_start(
    session: AsyncSession,
    run: CrawlRun,
    *,
    url: str,
    idx: int,
    total_urls: int,
) -> None:
    await log_event(
        session,
        run.id,
        "info",
        _url_start_message(url=url, idx=idx, total_urls=total_urls),
    )
    if idx == 1:
        await log_event(
            session,
            run.id,
            "info",
            f"Resolved {total_urls} seed URL(s), domain policy: standard",
        )
    await set_stage(
        session,
        run,
        STAGE_ACQUIRE,
        current_url=url,
        current_url_index=idx,
        total_urls=total_urls,
    )
    await session.commit()


async def _process_sequential_url(
    session: AsyncSession,
    *,
    run: CrawlRun,
    url: str,
    idx: int,
    total_urls: int,
    remaining_records: int,
    url_timeout_seconds: float,
) -> tuple[CrawlRun, URLProcessingResult]:
    config = URLProcessingConfig.from_acquisition_plan(
        run.settings_view.acquisition_plan(surface=run.surface, max_records=remaining_records),
        update_run_state=True,
        persist_logs=True,
    )
    try:
        with logfire_span(
            "pipeline.url",
            run_id=run.id,
            url_index=idx,
            url_count=total_urls,
            domain=normalize_domain(url),
            surface=run.surface,
            max_records=remaining_records,
            timeout_seconds=url_timeout_seconds,
        ) as url_span:
            result = _require_url_processing_result(
                await _run_url_processing_with_timeout(
                    process_single_url(
                        session=session,
                        run=run,
                        url=url,
                        config=config,
                    ),
                    url_timeout_seconds,
                )
            )
            set_logfire_attributes(
                url_span,
                verdict=result.verdict,
                record_count=_url_metric(result, "record_count", len(result.records)),
                method=_url_metric(result, "method"),
                blocked=_url_metric(result, "blocked"),
            )
            return run, result
    except _URLProcessingDeadlineExceeded as exc:
        logger.warning("URL processing timed out for run=%s url=%s", run.id, url)
        recovered_run, result = await _recover_url_failure(
            session,
            run=run,
            run_id=run.id,
            url=url,
            exc=exc,
            log_message=(f"URL processing timed out for {url} (timeout_seconds={url_timeout_seconds})"),
        )
        result.url_metrics["error"] = f"TimeoutError: url exceeded timeout_seconds={url_timeout_seconds}"
        return recovered_run, result
    except Exception as exc:
        recovered_run, result = await _recover_url_failure(
            session,
            run=run,
            run_id=run.id,
            url=url,
            exc=exc,
            log_message=f"URL processing failed for {url}: {type(exc).__name__}: {exc}",
        )
        return recovered_run, result


async def process_run(session: AsyncSession, run_id: int) -> None:
    with logfire_span("pipeline.run", run_id=run_id) as run_span:
        await _process_run_with_span(session, run_id, run_span)


async def process_run_async(run_id: int) -> None:
    async with SessionLocal() as session:
        await process_run(session, run_id)


async def _process_run_with_span(
    session: AsyncSession,
    run_id: int,
    run_span,
) -> None:
    try:
        run = await session.get(CrawlRun, run_id, populate_existing=True)
        if run is None or run.status_value in TERMINAL_STATUSES:
            return
        await session.refresh(run)
        set_logfire_attributes(
            run_span,
            surface=run.surface,
            run_type=run.run_type,
            llm_enabled=run.settings_view.llm_enabled(),
        )
        if str(run.surface or "").strip().lower() == DESIGN_SYSTEM_SURFACE:
            await process_design_system_run(session, run)
            return
        if run.status_value == CrawlStatus.PAUSED:
            return
        if run.status_value == CrawlStatus.PENDING:
            update_run_status(run, CrawlStatus.RUNNING)

        _touch_run_heartbeat(run)
        await session.commit()
        settings_view = run.settings_view
        url_list = await _resolve_run_urls(run, settings_view)
        total_urls = len(url_list)
        if total_urls == 0:
            raise ValueError("No URL provided")
        first_url = url_list[0]
        await _prewarm_browser_pool()
        set_logfire_attributes(
            run_span,
            url_count=total_urls,
            domain=normalize_domain(first_url),
        )

        max_records = settings_view.max_records()
        sleep_ms = settings_view.sleep_ms()
        url_timeout_seconds = _url_timeout_seconds(settings_view)

        progress_state = BatchRunProgressState(
            total_urls=total_urls,
            url_domain=normalize_domain(first_url),
            persisted_record_count=as_int(run.get_summary("record_count", 0)),
        )
        run.update_summary(
            **progress_state.build_progress_patch(
                current_url=first_url,
                current_url_index=0,
            ),
            current_stage=STAGE_ACQUIRE,
            resolved_url_list=url_list,
        )
        await session.commit()

        verdicts: list[str] = []
        record_count = as_int(run.get_summary("record_count", 0))

        try:
            if total_urls > 1 and parallel_url_concurrency(total_urls, settings_view) > 1:
                verdicts, record_count = await _process_urls_in_parallel(
                    session,
                    run=run,
                    settings_view=settings_view,
                    url_list=url_list,
                    progress_state=progress_state,
                    max_records=max_records,
                    url_timeout_seconds=url_timeout_seconds,
                )
            else:
                run, verdicts, record_count = await _process_urls_sequential(
                    session,
                    run=run,
                    url_list=url_list,
                    progress_state=progress_state,
                    max_records=max_records,
                    sleep_ms=sleep_ms,
                    url_timeout_seconds=url_timeout_seconds,
                    run_span=run_span,
                )
            await session.refresh(run)
            if run.status_value in TERMINAL_STATUSES:
                return
            aggregate_verdict_value = aggregate_verdict(verdicts)
            set_logfire_attributes(
                run_span,
                verdict=aggregate_verdict_value,
                record_count=record_count,
            )
            update_run_status(run, CrawlStatus.COMPLETED)
            _touch_run_heartbeat(run)
            run.update_summary(
                **progress_state.build_final_patch(aggregate_verdict_value),
                current_stage=STAGE_PERSIST,
                duration_ms=_current_duration_ms(run),
            )
            await log_event(
                session,
                run.id,
                "info",
                f"Pipeline finished. {record_count} records. verdict={aggregate_verdict_value}",
            )
            await session.commit()
            try:
                await on_run_complete(run.id)
            except Exception as exc:
                logger.exception("Run-complete callback failed for run=%s", run.id)
                with suppress(Exception):
                    await log_event(
                        session,
                        run.id,
                        "error",
                        f"on_run_complete failure: {exc}",
                    )
        finally:
            pass
    except (RuntimeError, ValueError, TypeError, SQLAlchemyError) as exc:
        logger.exception("Run-level failure for run=%s", run_id)
        await _rollback_url_session(session, context="run failure marking")
        await mark_run_failed(session, run_id, f"{type(exc).__name__}: {exc}")


def _url_metric(
    url_result: URLProcessingResult,
    key: str,
    default: object | None = None,
) -> object | None:
    metrics = url_result.url_metrics if isinstance(url_result.url_metrics, dict) else {}
    return metrics.get(key, default)

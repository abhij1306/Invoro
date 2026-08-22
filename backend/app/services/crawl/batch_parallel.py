import asyncio
from contextlib import suppress

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.crawl_run import CrawlRun
from app.services.config.runtime_settings import (
    BROWSER_CONCURRENCY_EXEMPT_FETCH_MODES,
    crawler_runtime_settings,
)
from app.services.crawl.state import (
    CONTROL_REQUEST_KILL,
    CONTROL_REQUEST_PAUSE,
    CrawlStatus,
    get_control_request,
    set_control_request,
    update_run_status,
)
from app.services.pipeline.run_progress import BatchRunProgressState
from app.services.pipeline.runtime_helpers import log_event
from app.services.pipeline.types import URLProcessingResult
from app.services.publish import VERDICT_ERROR
from app.services.run_summary import as_int

_DEFAULT_URL_CONCURRENCY = 1


def parallel_url_concurrency(total_urls: int, settings_view) -> int:
    system_limit = _positive_int_or_default(getattr(settings, "system_max_concurrent_urls", _DEFAULT_URL_CONCURRENCY))
    batch_value = getattr(settings_view, "url_batch_concurrency", None)
    raw_batch_limit = batch_value() if callable(batch_value) else batch_value
    batch_limit = _positive_int_or_default(raw_batch_limit)
    limits = [total_urls, system_limit, batch_limit]
    browser_limit = browser_capacity_limit(settings_view)
    if browser_limit is not None:
        limits.append(browser_limit)
    return max(1, min(limits))


def _positive_int_or_default(value: object) -> int:
    try:
        return int(value if value is not None else _DEFAULT_URL_CONCURRENCY)  # type: ignore[call-overload]
    except (AttributeError, TypeError, ValueError):
        return _DEFAULT_URL_CONCURRENCY


def browser_capacity_limit(settings_view) -> int | None:
    if settings_fetch_mode(settings_view) in BROWSER_CONCURRENCY_EXEMPT_FETCH_MODES:
        return None
    return max(
        1,
        _positive_int_or_default(getattr(crawler_runtime_settings, "browser_runtime_context_capacity", 1)),
    )


def settings_fetch_mode(settings_view) -> str:
    try:
        fetch_profile_attr = getattr(settings_view, "fetch_profile", None)
        fetch_profile = fetch_profile_attr() if callable(fetch_profile_attr) else fetch_profile_attr
    except (AttributeError, TypeError, ValueError):
        fetch_profile = None
    if fetch_profile is None:
        getter = getattr(settings_view, "get", None)
        fetch_profile = getter("fetch_profile") if callable(getter) else None
    if not isinstance(fetch_profile, dict):
        return ""
    return str(fetch_profile.get("fetch_mode") or "").strip().lower()


def parallel_worker_record_limit(max_records: int, concurrency: int) -> int:
    total_budget = max(1, int(max_records or 1))
    worker_count = max(1, int(concurrency or 1))
    return max(1, (total_budget + worker_count - 1) // worker_count)


async def cancel_pending_tasks(tasks: list[asyncio.Task]) -> None:
    for task in tasks:
        if not task.done():
            task.cancel()
    with suppress(BaseException):
        await asyncio.gather(*tasks, return_exceptions=True)


async def process_urls_in_parallel(
    session: AsyncSession,
    *,
    run: CrawlRun,
    settings_view,
    url_list: list[str],
    progress_state: BatchRunProgressState,
    max_records: int,
    url_timeout_seconds: float,
    process_url,
    url_metric,
    touch_heartbeat,
    current_duration_ms,
) -> tuple[list[str], int]:
    total_urls = len(url_list)
    concurrency = parallel_url_concurrency(total_urls, settings_view)
    record_limit = parallel_worker_record_limit(max_records, concurrency)
    await log_event(
        session,
        run.id,
        "info",
        f"Processing {total_urls} URL(s) with concurrency={concurrency}",
    )
    await session.commit()
    semaphore = asyncio.Semaphore(concurrency)

    async def guarded(idx: int, url: str) -> tuple[int, str, URLProcessingResult]:
        async with semaphore:
            return await process_url(
                run_id=int(run.id),
                idx=idx,
                total_urls=total_urls,
                url=url,
                max_records=record_limit,
                url_timeout_seconds=url_timeout_seconds,
            )

    tasks = [
        asyncio.create_task(guarded(idx, url), name=f"crawl-run-{run.id}-url-{idx}")
        for idx, url in enumerate(url_list, start=1)
    ]
    verdicts: list[str] = []
    record_count = as_int(run.get_summary("record_count", 0))

    async def record_task(task: asyncio.Task) -> None:
        nonlocal record_count
        idx, url, result = await task
        verdict = str(result.verdict or VERDICT_ERROR)
        verdicts.append(verdict)
        count = as_int(url_metric(result, "record_count", len(result.records)))
        record_count += count
        progress_state.record_url_result(
            idx=idx - 1,
            records_count=count,
            verdict=verdict,
            url_metrics=result.url_metrics,
        )
        touch_heartbeat(run)
        run.update_summary(
            **progress_state.build_progress_patch(current_url=url, current_url_index=idx),
            duration_ms=current_duration_ms(run),
        )
        await session.commit()

    async def drain_completed(pending: set[asyncio.Task]) -> None:
        for task in [item for item in pending if item.done()]:
            pending.remove(task)
            await record_task(task)

    try:
        pending = set(tasks)
        while pending:
            done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                await record_task(task)
            await session.refresh(run)
            control_request = get_control_request(run)
            if control_request in (CONTROL_REQUEST_PAUSE, CONTROL_REQUEST_KILL):
                await drain_completed(pending)
                await cancel_pending_tasks(list(pending))
                await _persist_parallel_control(session, run, control_request)
                return verdicts, record_count
            if record_count >= max_records:
                await drain_completed(pending)
                await cancel_pending_tasks(list(pending))
                await log_event(
                    session,
                    run.id,
                    "info",
                    f"Stopped after reaching max_records={max_records}",
                )
                await session.commit()
                break
    except BaseException:
        await cancel_pending_tasks(tasks)
        raise
    return verdicts, record_count


async def _persist_parallel_control(session: AsyncSession, run: CrawlRun, control_request: str) -> None:
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

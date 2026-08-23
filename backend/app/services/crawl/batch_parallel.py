import asyncio
from dataclasses import dataclass, field
from typing import Any

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
    system_limit = _positive_int_or_default(
        getattr(settings, "system_max_concurrent_urls", _DEFAULT_URL_CONCURRENCY)
    )
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
        _positive_int_or_default(
            getattr(crawler_runtime_settings, "browser_runtime_context_capacity", 1)
        ),
    )


def settings_fetch_mode(settings_view) -> str:
    try:
        fetch_profile_attr = getattr(settings_view, "fetch_profile", None)
        fetch_profile = (
            fetch_profile_attr() if callable(fetch_profile_attr) else fetch_profile_attr
        )
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


class ParallelRecordBudget:
    def __init__(self, *, total: int, per_worker: int) -> None:
        self._available = max(0, int(total))
        self._per_worker = max(1, int(per_worker))
        self._condition = asyncio.Condition()

    async def claim(self) -> int:
        async with self._condition:
            await self._condition.wait_for(lambda: self._available > 0)
            claimed = min(self._available, self._per_worker)
            self._available -= claimed
            return claimed

    async def release(self, amount: int) -> None:
        if amount <= 0:
            return
        async with self._condition:
            self._available += int(amount)
            self._condition.notify_all()


async def cancel_pending_tasks(tasks: list[asyncio.Task]) -> None:
    for task in tasks:
        if not task.done():
            task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


async def _parallel_url_worker(
    *,
    work_queue,
    result_queue,
    record_budget: ParallelRecordBudget,
    process_url,
    session_factory,
    run_id: int,
    total_urls: int,
    url_timeout_seconds: float,
    url_metric,
) -> None:
    while True:
        try:
            idx, url = work_queue.get_nowait()
        except asyncio.QueueEmpty:
            return
        claimed = await record_budget.claim()
        try:
            result_idx, result_url, result = await process_url(
                session_factory=session_factory,
                run_id=run_id,
                idx=idx,
                total_urls=total_urls,
                url=url,
                max_records=claimed,
                url_timeout_seconds=url_timeout_seconds,
            )
            count = as_int(url_metric(result, "record_count", len(result.records)))
            await record_budget.release(max(0, claimed - count))
            await result_queue.put((result_idx, result_url, result, count))
        except asyncio.CancelledError:
            await record_budget.release(claimed)
            raise
        except Exception as exc:
            await record_budget.release(claimed)
            await result_queue.put(exc)
            return
        finally:
            work_queue.task_done()


@dataclass
class _ParallelResultCoordinator:
    session: AsyncSession
    run: CrawlRun
    progress_state: BatchRunProgressState
    max_records: int
    record_count: int
    url_metric: Any
    touch_heartbeat: Any
    current_duration_ms: Any
    verdicts: list[str] = field(default_factory=list, init=False)

    async def record(self, item: tuple[int, str, URLProcessingResult, int]) -> bool:
        idx, url, result, count = item
        verdict = str(result.verdict or VERDICT_ERROR)
        self.verdicts.append(verdict)
        self.record_count += count
        self.progress_state.record_url_result(
            idx=idx - 1,
            records_count=count,
            verdict=verdict,
            url_metrics=result.url_metrics,
        )
        self.touch_heartbeat(self.run)
        self.run.update_summary(
            **self.progress_state.build_progress_patch(
                current_url=url, current_url_index=idx
            ),
            duration_ms=self.current_duration_ms(self.run),
        )
        await self.session.commit()
        return self.record_count >= self.max_records

    async def drain_ready_results(self, result_queue) -> Exception | None:
        first_error: Exception | None = None
        while True:
            try:
                item = result_queue.get_nowait()
            except asyncio.QueueEmpty:
                return first_error
            if isinstance(item, Exception):
                first_error = first_error or item
            else:
                await self.record(item)
            result_queue.task_done()

    async def consume(
        self,
        *,
        result_queue,
        tasks: list[asyncio.Task],
        total_urls: int,
    ) -> bool:
        completed_urls = 0
        while completed_urls < total_urls:
            completed_item = await result_queue.get()
            result_queue.task_done()
            completed_urls += 1
            if isinstance(completed_item, Exception):
                await cancel_pending_tasks(tasks)
                await self.drain_ready_results(result_queue)
                raise completed_item
            record_limit_reached = await self.record(completed_item)
            await self.session.refresh(self.run)
            control_request = get_control_request(self.run)
            if control_request in (CONTROL_REQUEST_PAUSE, CONTROL_REQUEST_KILL):
                await self._stop_for_control(result_queue, tasks, control_request)
                return True
            if record_limit_reached:
                await self._stop_at_record_limit(result_queue, tasks)
                return True
        return False

    async def _stop_for_control(
        self, result_queue, tasks: list[asyncio.Task], control_request: str
    ) -> None:
        queued_error = await self.drain_ready_results(result_queue)
        await cancel_pending_tasks(tasks)
        if queued_error is not None:
            raise queued_error
        await _persist_parallel_control(self.session, self.run, control_request)

    async def _stop_at_record_limit(
        self, result_queue, tasks: list[asyncio.Task]
    ) -> None:
        queued_error = await self.drain_ready_results(result_queue)
        await cancel_pending_tasks(tasks)
        if queued_error is not None:
            raise queued_error
        await log_event(
            self.session,
            self.run.id,
            "info",
            f"Stopped after reaching max_records={self.max_records}",
        )
        await self.session.commit()


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
    session_factory,
    url_metric,
    touch_heartbeat,
    current_duration_ms,
) -> tuple[list[str], int]:
    total_urls = len(url_list)
    run_id = int(run.id)
    concurrency = parallel_url_concurrency(total_urls, settings_view)
    record_count = as_int(run.get_summary("record_count", 0))
    record_limit = parallel_worker_record_limit(max_records, concurrency)
    record_budget = ParallelRecordBudget(
        total=max(0, max_records - record_count),
        per_worker=record_limit,
    )
    await log_event(
        session,
        run.id,
        "info",
        f"Processing {total_urls} URL(s) with concurrency={concurrency}",
    )
    await session.commit()
    if record_count >= max_records:
        return [], record_count
    work_queue: asyncio.Queue[tuple[int, str]] = asyncio.Queue()
    for work_item in enumerate(url_list, start=1):
        work_queue.put_nowait(work_item)
    result_queue: asyncio.Queue[
        tuple[int, str, URLProcessingResult, int] | Exception
    ] = asyncio.Queue(maxsize=concurrency)

    tasks = [
        asyncio.create_task(
            _parallel_url_worker(
                work_queue=work_queue,
                result_queue=result_queue,
                record_budget=record_budget,
                process_url=process_url,
                session_factory=session_factory,
                run_id=run_id,
                total_urls=total_urls,
                url_timeout_seconds=url_timeout_seconds,
                url_metric=url_metric,
            ),
            name=f"crawl-run-{run_id}-worker-{worker_number}",
        )
        for worker_number in range(1, concurrency + 1)
    ]
    coordinator = _ParallelResultCoordinator(
        session=session,
        run=run,
        progress_state=progress_state,
        max_records=max_records,
        record_count=record_count,
        url_metric=url_metric,
        touch_heartbeat=touch_heartbeat,
        current_duration_ms=current_duration_ms,
    )
    try:
        skip_final_gather = await coordinator.consume(
            result_queue=result_queue,
            tasks=tasks,
            total_urls=total_urls,
        )
    except asyncio.CancelledError:
        await cancel_pending_tasks(tasks)
        raise
    except Exception:
        await cancel_pending_tasks(tasks)
        raise
    if not skip_final_gather:
        await asyncio.gather(*tasks)
    return coordinator.verdicts, coordinator.record_count


async def _persist_parallel_control(
    session: AsyncSession, run: CrawlRun, control_request: str
) -> None:
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

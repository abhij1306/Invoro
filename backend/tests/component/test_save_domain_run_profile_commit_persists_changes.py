from __future__ import annotations

from .test_crawl_service import AsyncSession, CONTROL_REQUEST_KILL, CONTROL_REQUEST_PAUSE, CrawlRecord, UTC, _create_running_run, asyncio, celery_dispatch_module, commit_selected_fields, crawl_service, create_crawl_run, database_module, datetime, delete_run, get_control_request, load_domain_run_profile, local_dispatch_module, logging, pytest, save_domain_run_profile, settings, timedelta, update_run_status  # fmt: skip
from app.models.domain_memory import DomainRunProfile
from app.services.crawl.profile import repository as profile_repository
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker


@pytest.mark.asyncio
@pytest.mark.component
async def test_save_domain_run_profile_commit_persists_changes(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commit_calls = 0
    refresh_calls = 0

    original_commit = db_session.commit
    original_refresh = db_session.refresh

    async def _tracked_commit() -> None:
        nonlocal commit_calls
        commit_calls += 1
        await original_commit()

    async def _tracked_refresh(instance, *args, **kwargs) -> None:
        nonlocal refresh_calls
        refresh_calls += 1
        await original_refresh(instance, *args, **kwargs)

    monkeypatch.setattr(db_session, "commit", _tracked_commit)
    monkeypatch.setattr(db_session, "refresh", _tracked_refresh)

    saved = await save_domain_run_profile(
        db_session,
        domain="example.com",
        surface="ecommerce_detail",
        profile={
            "fetch_profile": {
                "fetch_mode": "browser_only",
            }
        },
        source_run_id=91,
        commit=True,
    )

    assert saved["fetch_profile"]["fetch_mode"] == "browser_only"
    assert commit_calls == 1
    assert refresh_calls == 1

    loaded = await load_domain_run_profile(
        db_session,
        domain="example.com",
        surface="ecommerce_detail",
    )
    assert loaded is not None
    assert dict(loaded.profile or {})["fetch_profile"]["fetch_mode"] == "browser_only"


@pytest.mark.asyncio
@pytest.mark.component
async def test_save_domain_run_profile_upserts_concurrent_first_writes(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory = async_sessionmaker(
        bind=db_session.bind,
        expire_on_commit=False,
        class_=AsyncSession,
        autoflush=False,
    )
    load_gate = asyncio.Barrier(2)
    original_load = profile_repository.load_domain_run_profile

    async def _load_then_wait(*args, **kwargs):
        existing = await original_load(*args, **kwargs)
        assert existing is None
        await load_gate.wait()
        return existing

    monkeypatch.setattr(
        profile_repository,
        "load_domain_run_profile",
        _load_then_wait,
    )

    async def _save(source_run_id: int, fetch_mode: str) -> None:
        async with session_factory() as session:
            await save_domain_run_profile(
                session,
                domain="parallel.example.com",
                surface="ecommerce_detail",
                profile={"fetch_profile": {"fetch_mode": fetch_mode}},
                source_run_id=source_run_id,
                commit=True,
            )

    await asyncio.gather(
        _save(101, "http_only"),
        _save(102, "browser_only"),
    )
    await db_session.rollback()
    profiles = list(
        await db_session.scalars(
            select(DomainRunProfile).where(
                DomainRunProfile.domain == "parallel.example.com",
                DomainRunProfile.surface == "ecommerce_detail",
            )
        )
    )

    assert len(profiles) == 1
    loaded = profiles[0]
    assert dict(loaded.profile or {})["fetch_profile"]["fetch_mode"] in {
        "http_only",
        "browser_only",
    }


@pytest.mark.asyncio
@pytest.mark.component
async def test_delete_run_rejects_active_runs(
    db_session: AsyncSession,
    test_user,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/product/widget",
            "surface": "ecommerce_detail",
        },
    )

    with pytest.raises(ValueError, match="Cannot delete run"):
        await delete_run(db_session, run)


@pytest.mark.asyncio
@pytest.mark.component
async def test_commit_selected_fields_updates_requested_field_metadata(
    db_session: AsyncSession,
    test_user,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/product/widget",
            "surface": "ecommerce_detail",
            "additional_fields": ["description", "number_of_keys"],
        },
    )
    record = CrawlRecord(
        run_id=run.id,
        source_url=run.url,
        data={"title": "Widget"},
        raw_data={},
        discovered_data={},
        source_trace={},
    )
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(record)

    updated_records, updated_fields = await commit_selected_fields(
        db_session,
        run=run,
        items=[
            {
                "record_id": record.id,
                "field_name": "description",
                "value": "Clean text",
            },
            {"record_id": record.id, "field_name": "number_of_keys", "value": 61},
        ],
    )

    await db_session.refresh(record)
    assert updated_records == 1
    assert updated_fields == 2
    assert record.data["description"] == "Clean text"
    assert record.data["number_of_keys"] == 61
    assert record.source_trace["field_discovery"]["description"]["status"] == "found"
    assert record.source_trace["field_discovery"]["number_of_keys"]["value"] == "61"
    coverage = record.discovered_data["requested_field_coverage"]
    assert coverage["requested"] >= 1
    assert coverage["found"] >= 1
    assert "description" not in coverage["missing"]


@pytest.mark.asyncio
@pytest.mark.component
async def test_pause_run_preserves_live_local_task_bookkeeping(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "celery_dispatch_enabled", False)
    run = await _create_running_run(db_session, user_id=test_user.id)
    local_task = asyncio.create_task(asyncio.sleep(60))
    local_dispatch_module._local_run_tasks[run.id] = local_task

    paused = await crawl_service.pause_run(db_session, run)
    await db_session.refresh(paused)

    assert paused.status == "running"
    assert get_control_request(paused) == CONTROL_REQUEST_PAUSE
    assert paused.get_summary(crawl_service.CELERY_TASK_ID_KEY) == f"crawl-run-{run.id}"
    assert local_dispatch_module._local_run_tasks[run.id] is local_task

    local_dispatch_module._local_run_tasks.pop(run.id, None)
    local_task.cancel()
    await asyncio.gather(local_task, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.component
async def test_kill_run_clears_local_task_bookkeeping(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "celery_dispatch_enabled", False)
    browser_shutdowns = 0

    async def _fake_shutdown_browser_runtime() -> None:
        nonlocal browser_shutdowns
        browser_shutdowns += 1

    monkeypatch.setattr(
        crawl_service, "shutdown_browser_runtime", _fake_shutdown_browser_runtime
    )
    run = await _create_running_run(db_session, user_id=test_user.id)
    local_task = asyncio.create_task(asyncio.sleep(60))
    local_dispatch_module._local_run_tasks[run.id] = local_task

    killed = await crawl_service.kill_run(db_session, run)
    await asyncio.sleep(0)
    await db_session.refresh(killed)

    assert killed.status == "killed"
    assert get_control_request(killed) == CONTROL_REQUEST_KILL
    assert killed.get_summary(crawl_service.CELERY_TASK_ID_KEY) is None
    assert run.id not in local_dispatch_module._local_run_tasks
    assert local_task.cancelled()
    assert browser_shutdowns == 1


@pytest.mark.asyncio
@pytest.mark.component
async def test_shutdown_browser_runtime_after_kill_skips_concurrent_calls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    browser_shutdowns = 0
    shutdown_started = asyncio.Event()
    release_shutdown = asyncio.Event()

    async def _fake_shutdown_browser_runtime() -> None:
        nonlocal browser_shutdowns
        browser_shutdowns += 1
        shutdown_started.set()
        await release_shutdown.wait()

    monkeypatch.setattr(
        crawl_service, "shutdown_browser_runtime", _fake_shutdown_browser_runtime
    )

    first = asyncio.create_task(crawl_service._shutdown_browser_runtime_after_kill())
    await shutdown_started.wait()
    second = asyncio.create_task(crawl_service._shutdown_browser_runtime_after_kill())
    await asyncio.sleep(0)

    release_shutdown.set()
    await asyncio.gather(first, second)

    assert browser_shutdowns == 1


@pytest.mark.asyncio
@pytest.mark.component
async def test_recover_stale_local_runs_clears_task_entries_and_task_ids(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "celery_dispatch_enabled", False)
    pending_run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/jobs/pending",
            "surface": "job_detail",
        },
    )
    pending_run.update_summary(celery_task_id="pending-task")

    running_run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/jobs/running",
            "surface": "job_detail",
        },
    )
    update_run_status(running_run, "running")
    running_run.update_summary(celery_task_id="running-task")
    stale_time = datetime.now(UTC) - timedelta(
        seconds=crawl_service.crawler_runtime_settings.stalled_run_threshold_seconds
        + 30
    )
    running_run.last_heartbeat_at = stale_time
    running_run.updated_at = stale_time
    await db_session.commit()

    finished_pending = asyncio.create_task(asyncio.sleep(0))
    finished_running = asyncio.create_task(asyncio.sleep(0))
    await asyncio.sleep(0)
    local_dispatch_module._local_run_tasks[pending_run.id] = finished_pending
    local_dispatch_module._local_run_tasks[running_run.id] = finished_running

    recovered = await crawl_service.recover_stale_local_runs(db_session)
    await db_session.refresh(pending_run)
    await db_session.refresh(running_run)

    assert recovered == 2
    assert pending_run.status == "killed"
    assert pending_run.get_summary(crawl_service.CELERY_TASK_ID_KEY) is None
    assert "interrupted before processing began" in str(
        pending_run.get_summary("error") or ""
    )
    assert running_run.status == "failed"
    assert running_run.get_summary(crawl_service.CELERY_TASK_ID_KEY) is None
    assert "interrupted by backend restart" in str(
        running_run.get_summary("error") or ""
    )
    assert pending_run.id not in local_dispatch_module._local_run_tasks
    assert running_run.id not in local_dispatch_module._local_run_tasks


@pytest.mark.asyncio
@pytest.mark.component
async def test_recover_stale_local_runs_skips_fresh_active_runs(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "celery_dispatch_enabled", False)
    pending_run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/jobs/fresh-pending",
            "surface": "job_detail",
        },
    )
    running_run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/jobs/fresh-running",
            "surface": "job_detail",
        },
    )
    update_run_status(running_run, "running")
    running_run.last_heartbeat_at = datetime.now(UTC)
    await db_session.commit()

    recovered = await crawl_service.recover_stale_local_runs(db_session)
    await db_session.refresh(pending_run)
    await db_session.refresh(running_run)

    assert recovered == 0
    assert pending_run.status == "pending"
    assert running_run.status == "running"


@pytest.mark.asyncio
@pytest.mark.component
async def test_dispatch_run_locally_recovers_stale_runs_before_launch(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "celery_dispatch_enabled", False)

    stale_run = await _create_running_run(
        db_session,
        user_id=test_user.id,
        url="https://example.com/jobs/stale-running",
    )
    stale_time = datetime.now(UTC) - timedelta(
        seconds=crawl_service.crawler_runtime_settings.stalled_run_threshold_seconds
        + 30
    )
    stale_run.last_heartbeat_at = stale_time
    stale_run.updated_at = stale_time

    new_run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/jobs/new-run",
            "surface": "job_detail",
        },
    )
    await db_session.commit()

    created_tasks: list[int] = []

    def _fake_track(run_id: int) -> asyncio.Task[None]:
        created_tasks.append(run_id)
        task = asyncio.create_task(asyncio.sleep(0))
        local_dispatch_module._local_run_tasks[run_id] = task
        return task

    monkeypatch.setattr(local_dispatch_module, "track_local_run_task", _fake_track)

    dispatched = await crawl_service.dispatch_run(db_session, new_run)
    await asyncio.sleep(0)
    await db_session.refresh(stale_run)
    await db_session.refresh(dispatched)

    assert stale_run.status == "failed"
    assert created_tasks == [new_run.id]
    assert dispatched.status == "pending"
    assert dispatched.get_summary(crawl_service.CELERY_TASK_ID_KEY) is not None

    local_task = local_dispatch_module._local_run_tasks.pop(new_run.id, None)
    if local_task is not None:
        await asyncio.gather(local_task, return_exceptions=True)


@pytest.mark.asyncio
@pytest.mark.component
async def test_local_dispatch_commits_task_id_before_launching_task(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "celery_dispatch_enabled", False)
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/jobs/local-order",
            "surface": "job_detail",
        },
    )
    events: list[str] = []
    tracked_tasks: list[asyncio.Task[None]] = []
    real_commit = db_session.commit

    async def _commit() -> None:
        events.append("commit")
        await real_commit()

    def _fake_track(run_id: int) -> asyncio.Task[None]:
        events.append("track")
        task = asyncio.create_task(asyncio.sleep(0))
        tracked_tasks.append(task)
        return task

    monkeypatch.setattr(db_session, "commit", _commit)
    monkeypatch.setattr(local_dispatch_module, "track_local_run_task", _fake_track)

    await crawl_service.dispatch_run(db_session, run)
    await asyncio.gather(*tracked_tasks)

    assert events[-2:] == ["commit", "track"]


@pytest.mark.asyncio
@pytest.mark.component
async def test_celery_dispatch_commits_task_id_before_enqueue(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/jobs/celery-order",
            "surface": "job_detail",
        },
    )
    events: list[str] = []
    real_commit = db_session.commit

    async def _commit() -> None:
        events.append("commit")
        await real_commit()

    class _FakeTask:
        def apply_async(self, *args, **kwargs):
            del args, kwargs
            events.append("enqueue")

    monkeypatch.setattr(db_session, "commit", _commit)
    monkeypatch.setattr(celery_dispatch_module, "process_run_task", _FakeTask())

    await celery_dispatch_module.CeleryRunDispatcher().dispatch(db_session, run)

    assert events[-2:] == ["commit", "enqueue"]


@pytest.mark.asyncio
@pytest.mark.component
async def test_run_with_local_session_preserves_original_process_run_error(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    session = object()

    class _FakeSessionLocal:
        async def __aenter__(self):
            return session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    async def _failing_process_run(active_session, run_id: int) -> None:
        assert active_session is session
        assert run_id == 17
        raise RuntimeError("process exploded")

    async def _failing_mark_run_failed(
        active_session, run_id: int, message: str
    ) -> None:
        assert active_session is session
        assert run_id == 17
        assert "RuntimeError: process exploded" in message
        raise ValueError("write failed")

    monkeypatch.setattr(local_dispatch_module, "SessionLocal", _FakeSessionLocal)
    monkeypatch.setattr(
        local_dispatch_module, "_batch_process_run", _failing_process_run
    )
    monkeypatch.setattr(
        local_dispatch_module, "mark_run_failed", _failing_mark_run_failed
    )

    with caplog.at_level(logging.ERROR):
        with pytest.raises(RuntimeError, match="process exploded") as exc_info:
            await local_dispatch_module._run_with_local_session(17)

    assert str(exc_info.value) == "process exploded"
    assert "Local crawl task failed for run 17" in caplog.text
    assert (
        "Failed to persist failed status for run 17 after process_run error"
        in caplog.text
    )


@pytest.mark.asyncio
@pytest.mark.component
async def test_get_session_rolls_back_when_consumer_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeSession:
        def __init__(self) -> None:
            self.rollback_calls = 0

        async def rollback(self) -> None:
            self.rollback_calls += 1

    session = _FakeSession()

    class _FakeSessionLocal:
        async def __aenter__(self):
            return session

        async def __aexit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(database_module, "SessionLocal", _FakeSessionLocal)

    generator = database_module.get_session()
    yielded = await anext(generator)

    assert yielded is session

    with pytest.raises(RuntimeError, match="boom"):
        await generator.athrow(RuntimeError("boom"))

    assert session.rollback_calls == 1

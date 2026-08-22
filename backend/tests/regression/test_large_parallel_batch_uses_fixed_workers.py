from __future__ import annotations

from .test_batch_runtime import AsyncSession, URLProcessingResult, asyncio, batch_runtime_module, create_crawl_run, process_run, pytest  # fmt: skip

pytest_plugins = ["tests.regression.test_batch_runtime"]


@pytest.mark.asyncio
@pytest.mark.regression
async def test_large_parallel_batch_uses_fixed_workers_and_owned_sessions(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
    patch_settings,
) -> None:
    patch_settings(url_batch_concurrency=4, browser_runtime_context_capacity=4)
    monkeypatch.setattr(
        batch_runtime_module.settings,
        "system_max_concurrent_urls",
        4,
        raising=False,
    )
    urls = [f"https://example.com/products/{idx}" for idx in range(80)]
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "batch",
            "surface": "ecommerce_detail",
            "settings": {
                "fetch_profile": {"fetch_mode": "http_only"},
                "url_batch_concurrency": 4,
                "urls": urls,
            },
        },
    )
    run_id = int(run.id)
    active = 0
    max_active = 0
    max_worker_tasks = 0
    owned_sessions: list[AsyncSession] = []

    async def _fake_process_single_url(*args, **kwargs):
        nonlocal active, max_active, max_worker_tasks
        del args
        owned_sessions.append(kwargs["session"])
        active += 1
        max_active = max(max_active, active)
        worker_prefix = f"crawl-run-{run_id}-worker-"
        max_worker_tasks = max(
            max_worker_tasks,
            sum(
                1
                for task in asyncio.all_tasks()
                if task.get_name().startswith(worker_prefix)
            ),
        )
        try:
            await asyncio.sleep(0.001)
        finally:
            active -= 1
        return URLProcessingResult(
            records=[],
            verdict="success",
            url_metrics={"record_count": 0},
        )

    monkeypatch.setattr(
        "app.services.crawl.batch_runtime.process_single_url",
        _fake_process_single_url,
    )

    await process_run(db_session, run_id)
    await db_session.refresh(run)

    assert run.status_value == "completed"
    assert run.result_summary["completed_urls"] == 80
    assert 1 <= max_active <= 4
    assert max_worker_tasks == 4
    assert len(owned_sessions) == 80
    assert len({id(session) for session in owned_sessions}) == 80
    assert all(session is not db_session for session in owned_sessions)

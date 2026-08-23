from __future__ import annotations

import asyncio
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import psutil
import pytest
import pytest_asyncio

from app.services.pipeline import extraction_process
from app.services.pipeline.extraction_process import (
    ExtractionProcessDeadlineExceeded,
    ExtractionProcessRequest,
    run_extraction_process,
    shutdown_extraction_processes,
)


@pytest_asyncio.fixture(autouse=True)
async def _shutdown_process_pool_after_test():  # type: ignore[no-untyped-def]
    yield
    await shutdown_extraction_processes()


@pytest.mark.asyncio
@pytest.mark.component
async def test_extraction_runs_in_worker_process() -> None:
    request = ExtractionProcessRequest(
        html=(
            "<html><body><article><h1>Release notes</h1><p>"
            + ("Useful deterministic content. " * 30)
            + "</p></article></body></html>"
        ),
        page_url="https://example.com/release-notes",
        surface="content_detail",
        max_records=1,
    )

    result = await run_extraction_process(request, timeout_seconds=30)
    worker = extraction_process._extraction_worker()
    first_pid = worker.process.pid  # type: ignore[union-attr]
    second_result = await run_extraction_process(request, timeout_seconds=30)
    second_pid = worker.process.pid  # type: ignore[union-attr]

    assert len(result.records) == 1
    assert len(second_result.records) == 1
    assert first_pid == second_pid
    assert result.elapsed_ms >= 0
    assert result.queue_wait_ms >= 0


@pytest.mark.asyncio
@pytest.mark.component
async def test_extraction_timeout_terminates_worker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_worker_command = extraction_process._worker_command
    request = ExtractionProcessRequest(
        html="<html></html>",
        page_url="https://example.com/slow",
        surface="content_detail",
        max_records=1,
    )
    ready_script = (
        "import pickle, struct, sys, time; "
        "payload=pickle.dumps({'ready': True}); "
        "sys.stdout.buffer.write(struct.pack('!Q', len(payload)) + payload); "
        "sys.stdout.buffer.flush(); time.sleep(60)"
    )
    monkeypatch.setattr(
        extraction_process,
        "_worker_command",
        lambda: (
            sys.executable,
            "-c",
            ready_script,
        ),
    )
    started_at = time.perf_counter()

    with pytest.raises(
        ExtractionProcessDeadlineExceeded,
        match="timeout_seconds=0.05",
    ):
        await run_extraction_process(request, timeout_seconds=0.05)

    assert time.perf_counter() - started_at < 3
    assert extraction_process._extraction_worker().process is None

    monkeypatch.setattr(extraction_process, "_worker_command", real_worker_command)
    recovered = await run_extraction_process(request, timeout_seconds=30)

    assert recovered.elapsed_ms >= 0
    assert extraction_process._extraction_worker().process is not None


@pytest.mark.asyncio
@pytest.mark.component
async def test_extraction_startup_uses_the_exchange_timeout_budget(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = extraction_process._ExtractionWorker()
    request = ExtractionProcessRequest(
        html="<html></html>",
        page_url="https://example.com/product",
        surface="ecommerce_detail",
        max_records=1,
    )
    process = object()
    clock = iter((10.0, 10.75))
    observed_timeout: list[float] = []

    async def _ensure_started():  # type: ignore[no-untyped-def]
        return process

    async def _exchange(active_process, active_request):  # type: ignore[no-untyped-def]
        assert active_process is process
        assert active_request is request
        return {"ok": True, "records": [], "elapsed_ms": 0}

    async def _wait_for(awaitable, *, timeout):  # type: ignore[no-untyped-def]
        observed_timeout.append(timeout)
        return await awaitable

    monkeypatch.setattr(worker, "_ensure_started", _ensure_started)
    monkeypatch.setattr(worker, "_exchange", _exchange)
    monkeypatch.setattr(extraction_process.time, "perf_counter", lambda: next(clock))
    monkeypatch.setattr(extraction_process.asyncio, "wait_for", _wait_for)

    response = await worker._run(request, timeout_seconds=1.0)

    assert response["ok"] is True
    assert observed_timeout == [pytest.approx(0.25)]


@pytest.mark.component
def test_close_sync_kills_reaps_and_closes_process_without_event_loop() -> None:
    worker = extraction_process._ExtractionWorker()
    process_handle = Mock()
    process_transport = Mock()
    process_transport._proc = process_handle
    stdin = Mock()
    stdout_transport = Mock()
    stderr_transport = Mock()
    process = SimpleNamespace(
        returncode=None,
        kill=Mock(),
        stdin=stdin,
        stdout=SimpleNamespace(_transport=stdout_transport),
        stderr=SimpleNamespace(_transport=stderr_transport),
        _transport=process_transport,
    )
    stderr_task = Mock()
    worker.process = process
    worker.stderr_task = stderr_task

    worker.close_sync()

    process.kill.assert_called_once_with()
    process_handle.wait.assert_called_once()
    assert process_handle.wait.call_args.kwargs["timeout"] > 0
    stderr_task.cancel.assert_called_once_with()
    stdin.close.assert_called_once_with()
    stdout_transport.close.assert_called_once_with()
    stderr_transport.close.assert_called_once_with()
    process_transport.close.assert_called_once_with()
    assert worker.process is None
    assert worker.stderr_task is None

    worker.close_sync()


@pytest.mark.asyncio
@pytest.mark.component
async def test_extraction_cancellation_terminates_worker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    pid_path = tmp_path / "worker.pid"
    request = ExtractionProcessRequest(
        html="<html></html>",
        page_url="https://example.com/cancelled",
        surface="content_detail",
        max_records=1,
    )
    script = (
        "import os, pathlib, pickle, struct, sys, time; "
        "pathlib.Path(sys.argv[1]).write_text(str(os.getpid())); "
        "payload=pickle.dumps({'ready': True}); "
        "sys.stdout.buffer.write(struct.pack('!Q', len(payload)) + payload); "
        "sys.stdout.buffer.flush(); "
        "time.sleep(60)"
    )
    monkeypatch.setattr(
        extraction_process,
        "_worker_command",
        lambda: (
            sys.executable,
            "-c",
            script,
            str(pid_path),
        ),
    )
    task = asyncio.create_task(run_extraction_process(request, timeout_seconds=30))
    for _ in range(100):
        if pid_path.is_file():
            break
        await asyncio.sleep(0.01)
    assert pid_path.is_file()
    worker_pid = int(pid_path.read_text())
    assert worker_pid != os.getpid()

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    for _ in range(200):
        if not psutil.pid_exists(worker_pid):
            break
        await asyncio.sleep(0.01)
    assert not psutil.pid_exists(worker_pid)


@pytest.mark.asyncio
@pytest.mark.component
async def test_extraction_concurrency_is_bounded_separately(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    active = 0
    peak = 0

    async def _fake_run(self, request, *, timeout_seconds):  # type: ignore[no-untyped-def]
        nonlocal active, peak
        del self, request, timeout_seconds
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.02)
        active -= 1
        return {"ok": True, "records": [], "elapsed_ms": 1}

    monkeypatch.setattr(extraction_process._ExtractionWorker, "_run", _fake_run)
    request = ExtractionProcessRequest(
        html="<html></html>",
        page_url="https://example.com/product",
        surface="ecommerce_detail",
        max_records=1,
    )

    await asyncio.gather(*(run_extraction_process(request) for _ in range(5)))

    assert peak == 1

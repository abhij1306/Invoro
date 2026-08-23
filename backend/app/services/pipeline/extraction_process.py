from __future__ import annotations

import asyncio
import contextlib
import logging
import pickle
import struct
import subprocess
import sys
import time
import traceback
import weakref
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.services.config.runtime_settings import crawler_runtime_settings

logger = logging.getLogger(__name__)

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
_FRAME_HEADER = struct.Struct("!Q")
_STDERR_TAIL_BYTES = 4000
_WORKER_BOOTSTRAP = (
    "from app.services.pipeline.extraction_process import worker_main; "
    "raise SystemExit(worker_main())"
)
_WORKERS: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, _ExtractionWorker] = (
    weakref.WeakKeyDictionary()
)


class ExtractionProcessError(RuntimeError):
    pass


class ExtractionProcessDeadlineExceeded(TimeoutError):
    pass


@dataclass(frozen=True, slots=True)
class ExtractionProcessRequest:
    html: str
    page_url: str
    surface: str
    max_records: int
    requested_page_url: str | None = None
    requested_fields: list[str] | None = None
    adapter_records: list[dict[str, Any]] | None = None
    network_payloads: list[dict[str, object]] | None = None
    artifacts: dict[str, object] | None = None
    selector_rules: list[dict[str, object]] | None = None
    extraction_runtime_snapshot: dict[str, object] | None = None
    content_type: str | None = None
    browser_diagnostics: dict[str, object] | None = None
    record_dom_observed_selectors: bool = False


@dataclass(frozen=True, slots=True)
class ExtractionProcessResult:
    records: list[dict[str, Any]]
    elapsed_ms: int
    queue_wait_ms: int


def _worker_command() -> tuple[str, ...]:
    return (sys.executable, "-c", _WORKER_BOOTSTRAP)


def _max_payload_bytes() -> int:
    return max(1, int(crawler_runtime_settings.extraction_process_max_payload_bytes))


def _decode_response(payload: bytes) -> dict[str, object]:
    response = pickle.loads(payload)
    if not isinstance(response, dict):
        raise ExtractionProcessError("Extraction worker returned an invalid response")
    return response


class _ExtractionWorker:
    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.process: asyncio.subprocess.Process | None = None
        self.stderr_task: asyncio.Task[None] | None = None
        self.stderr_tail = bytearray()

    async def execute(
        self,
        request: ExtractionProcessRequest,
        *,
        timeout_seconds: float,
    ) -> ExtractionProcessResult:
        queued_at = time.perf_counter()
        async with self.lock:
            queue_wait_ms = max(0, int(round((time.perf_counter() - queued_at) * 1000)))
            response = await self._run(request, timeout_seconds=timeout_seconds)
        if not bool(response.get("ok")):
            error_type = str(response.get("error_type") or "ExtractionError")
            error_message = str(response.get("error_message") or "unknown error")
            raise ExtractionProcessError(f"{error_type}: {error_message}")
        raw_records = response.get("records")
        if not isinstance(raw_records, list):
            raise ExtractionProcessError("Extraction worker returned invalid records")
        elapsed_value = response.get("elapsed_ms")
        elapsed_ms = int(elapsed_value) if isinstance(elapsed_value, int | float) else 0
        return ExtractionProcessResult(
            records=[dict(row) for row in raw_records if isinstance(row, dict)],
            elapsed_ms=max(0, elapsed_ms),
            queue_wait_ms=queue_wait_ms,
        )

    async def _run(
        self,
        request: ExtractionProcessRequest,
        *,
        timeout_seconds: float,
    ) -> dict[str, object]:
        started_at = time.perf_counter()
        try:
            process = await self._ensure_started()
            remaining_seconds = float(timeout_seconds) - (
                time.perf_counter() - started_at
            )
            if remaining_seconds <= 0:
                raise asyncio.TimeoutError
            return await asyncio.wait_for(
                self._exchange(process, request),
                timeout=remaining_seconds,
            )
        except asyncio.TimeoutError as exc:
            await self.close()
            raise ExtractionProcessDeadlineExceeded(
                f"Deterministic extraction exceeded timeout_seconds={timeout_seconds:g}"
            ) from exc
        except asyncio.CancelledError:
            await self.close()
            raise
        except Exception:
            detail = self.stderr_detail()
            await self.close()
            if detail:
                logger.debug("Extraction worker stderr: %s", detail)
            raise

    async def _ensure_started(self) -> asyncio.subprocess.Process:
        if self.process is not None and self.process.returncode is None:
            return self.process
        self.stderr_tail.clear()
        self.process = await asyncio.create_subprocess_exec(
            *_worker_command(),
            cwd=str(_BACKEND_ROOT),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        self.stderr_task = asyncio.create_task(self._drain_stderr(self.process))
        try:
            ready = await asyncio.wait_for(
                self._read_response(self.process),
                timeout=max(
                    0.001,
                    float(
                        crawler_runtime_settings.extraction_process_start_timeout_seconds
                    ),
                ),
            )
        except Exception as exc:
            detail = self.stderr_detail()
            await self.close()
            raise ExtractionProcessError(
                f"Extraction worker failed to start: {detail or type(exc).__name__}"
            ) from exc
        if ready.get("ready") is not True:
            await self.close()
            raise ExtractionProcessError(
                "Extraction worker sent an invalid ready frame"
            )
        return self.process

    async def _exchange(
        self,
        process: asyncio.subprocess.Process,
        request: ExtractionProcessRequest,
    ) -> dict[str, object]:
        if process.stdin is None:
            raise ExtractionProcessError("Extraction worker input pipe is unavailable")
        payload = await asyncio.to_thread(
            pickle.dumps, request, pickle.HIGHEST_PROTOCOL
        )
        if len(payload) > _max_payload_bytes():
            raise ExtractionProcessError(
                f"Extraction request exceeds max_payload_bytes={_max_payload_bytes()}"
            )
        process.stdin.write(_FRAME_HEADER.pack(len(payload)))
        process.stdin.write(payload)
        await process.stdin.drain()
        return await self._read_response(process)

    async def _read_response(
        self, process: asyncio.subprocess.Process
    ) -> dict[str, object]:
        if process.stdout is None:
            raise ExtractionProcessError("Extraction worker output pipe is unavailable")
        header = await process.stdout.readexactly(_FRAME_HEADER.size)
        response_size = _FRAME_HEADER.unpack(header)[0]
        if response_size > _max_payload_bytes():
            raise ExtractionProcessError(
                f"Extraction response exceeds max_payload_bytes={_max_payload_bytes()}"
            )
        payload = await process.stdout.readexactly(response_size)
        return await asyncio.to_thread(_decode_response, payload)

    async def _drain_stderr(self, process: asyncio.subprocess.Process) -> None:
        if process.stderr is None:
            return
        while chunk := await process.stderr.read(1024):
            self.stderr_tail.extend(chunk)
            if len(self.stderr_tail) > _STDERR_TAIL_BYTES:
                del self.stderr_tail[:-_STDERR_TAIL_BYTES]

    def stderr_detail(self) -> str:
        return bytes(self.stderr_tail).decode("utf-8", errors="replace").strip()

    async def close(self) -> None:
        process, self.process = self.process, None
        if process is not None and process.returncode is None:
            process.terminate()
            try:
                await asyncio.wait_for(
                    process.wait(),
                    timeout=max(
                        0.001,
                        float(
                            crawler_runtime_settings.extraction_process_terminate_grace_seconds
                        ),
                    ),
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
        stderr_task, self.stderr_task = self.stderr_task, None
        if stderr_task is not None:
            stderr_task.cancel()
            await asyncio.gather(stderr_task, return_exceptions=True)

    def close_sync(self) -> None:
        process, self.process = self.process, None
        stderr_task, self.stderr_task = self.stderr_task, None
        try:
            if process is not None and process.returncode is None:
                process.kill()
                transport = getattr(process, "_transport", None)
                process_handle = getattr(transport, "_proc", None)
                if process_handle is not None:
                    with contextlib.suppress(subprocess.TimeoutExpired):
                        process_handle.wait(
                            timeout=max(
                                0.001,
                                float(
                                    crawler_runtime_settings.extraction_process_terminate_grace_seconds
                                ),
                            )
                        )
        finally:
            if stderr_task is not None:
                with contextlib.suppress(RuntimeError):
                    stderr_task.cancel()
            if process is not None:
                if process.stdin is not None:
                    with contextlib.suppress(Exception):
                        process.stdin.close()
                for stream in (process.stdout, process.stderr):
                    pipe_transport = getattr(stream, "_transport", None)
                    if pipe_transport is not None:
                        with contextlib.suppress(Exception):
                            pipe_transport.close()
                transport = getattr(process, "_transport", None)
                if transport is not None:
                    with contextlib.suppress(Exception):
                        transport.close()


def _extraction_worker() -> _ExtractionWorker:
    loop = asyncio.get_running_loop()
    worker = _WORKERS.get(loop)
    if worker is None:
        worker = _ExtractionWorker()
        _WORKERS[loop] = worker
    return worker


async def run_extraction_process(
    request: ExtractionProcessRequest,
    *,
    timeout_seconds: float | None = None,
) -> ExtractionProcessResult:
    timeout = (
        float(crawler_runtime_settings.extraction_process_timeout_seconds)
        if timeout_seconds is None
        else float(timeout_seconds)
    )
    return await _extraction_worker().execute(request, timeout_seconds=timeout)


async def shutdown_extraction_processes() -> None:
    workers = list(_WORKERS.values())
    _WORKERS.clear()
    await asyncio.gather(
        *(worker.close() for worker in workers), return_exceptions=True
    )


def shutdown_extraction_processes_sync() -> None:
    for worker in list(_WORKERS.values()):
        worker.close_sync()
    _WORKERS.clear()


def _read_exactly(stream, size: int) -> bytes:  # type: ignore[no-untyped-def]
    chunks: list[bytes] = []
    remaining = size
    while remaining > 0:
        chunk = stream.read(remaining)
        if not chunk:
            raise EOFError("Extraction worker input closed mid-frame")
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def _read_request(stream) -> ExtractionProcessRequest | None:  # type: ignore[no-untyped-def]
    header = stream.read(_FRAME_HEADER.size)
    if not header:
        return None
    if len(header) != _FRAME_HEADER.size:
        raise EOFError("Extraction worker input closed during frame header")
    payload_size = _FRAME_HEADER.unpack(header)[0]
    if payload_size > _max_payload_bytes():
        raise ValueError(
            f"Extraction request exceeds max_payload_bytes={_max_payload_bytes()}"
        )
    request = pickle.loads(_read_exactly(stream, payload_size))
    if not isinstance(request, ExtractionProcessRequest):
        raise TypeError("Extraction worker received an invalid request")
    return request


def _write_response(stream, response: dict[str, object]) -> None:  # type: ignore[no-untyped-def]
    payload = pickle.dumps(response, protocol=pickle.HIGHEST_PROTOCOL)
    stream.write(_FRAME_HEADER.pack(len(payload)))
    stream.write(payload)
    stream.flush()


def _extract_response(request: ExtractionProcessRequest) -> dict[str, object]:
    from app.services.pipeline.extract_records import extract_records

    started_at = time.perf_counter()
    try:
        records = extract_records(
            request.html,
            request.page_url,
            request.surface,
            max_records=request.max_records,
            requested_page_url=request.requested_page_url,
            requested_fields=request.requested_fields,
            adapter_records=request.adapter_records,
            network_payloads=request.network_payloads,
            artifacts=request.artifacts,
            selector_rules=request.selector_rules,
            extraction_runtime_snapshot=request.extraction_runtime_snapshot,
            content_type=request.content_type,
            browser_diagnostics=request.browser_diagnostics,
            record_dom_observed_selectors=request.record_dom_observed_selectors,
        )
        return {
            "ok": True,
            "records": records,
            "elapsed_ms": max(0, int(round((time.perf_counter() - started_at) * 1000))),
        }
    except Exception as exc:
        traceback.print_exc(file=sys.stderr)
        return {
            "ok": False,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        }


def worker_main() -> int:
    protocol_input = sys.stdin.buffer
    protocol_output = sys.stdout.buffer
    _write_response(protocol_output, {"ready": True})
    while request := _read_request(protocol_input):
        with contextlib.redirect_stdout(sys.stderr):
            response = _extract_response(request)
        _write_response(protocol_output, response)
    return 0

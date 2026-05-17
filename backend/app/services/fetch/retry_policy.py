"""HTTP fetch retry status and delay policy."""

from __future__ import annotations

import asyncio
import logging
import secrets

from app.services.config.runtime_settings import crawler_runtime_settings

logger = logging.getLogger(__name__)


def retryable_status_for_http_fetch(status_code: int) -> bool:
    code = int(status_code or 0)
    retryable_codes: set[int] = set()
    for value in list(crawler_runtime_settings.http_retry_status_codes or []):
        try:
            retryable_codes.add(int(value))
        except (TypeError, ValueError):
            logger.warning("Ignoring invalid http retry status code: %r", value)
    return code in retryable_codes


def http_max_attempts() -> int:
    try:
        retries = int(crawler_runtime_settings.http_max_retries or 0)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid http_max_retries=%r; using no retries",
            crawler_runtime_settings.http_max_retries,
        )
        retries = 0
    return max(1, retries + 1)


def retry_delay_ms(attempt: int) -> int:
    try:
        raw_base_ms = int(crawler_runtime_settings.http_retry_backoff_base_ms or 0)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid http_retry_backoff_base_ms %r, defaulting to 0",
            crawler_runtime_settings.http_retry_backoff_base_ms,
        )
        raw_base_ms = 0
    try:
        raw_max_ms = int(crawler_runtime_settings.http_retry_backoff_max_ms or 0)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid http_retry_backoff_max_ms %r, defaulting to 0",
            crawler_runtime_settings.http_retry_backoff_max_ms,
        )
        raw_max_ms = 0
    base_ms = max(0, raw_base_ms)
    max_ms = max(base_ms, raw_max_ms)
    delay_ms = min(max_ms, base_ms * (2 ** max(0, attempt - 1)))
    if delay_ms <= 0:
        return 0
    jitter_ms = secrets.randbelow(max(1, delay_ms // 4) + 1)
    return delay_ms + jitter_ms


async def sleep_retry_delay(*, delay_ms: int) -> None:
    if delay_ms <= 0:
        return
    await asyncio.sleep(delay_ms / 1000)

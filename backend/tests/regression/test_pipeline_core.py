from __future__ import annotations

import asyncio

import json

import copy

from pathlib import Path

import pytest

from app.services.acquisition_plan import AcquisitionPlan

from app.services.acquisition.acquirer import (
    AcquisitionRequest,
    AcquisitionResult,
    acquire,
)

from app.services.adapters.base import AdapterResult

from app.services.crawl.crud import create_crawl_run, get_run_logs, get_run_records

from app.services.pipeline.extraction_loop import (
    URLProcessingContext,
    best_adapter_result,
    empty_extraction_browser_retry_decision,
    resolved_url_processing_config,
    apply_llm_fallback,
    process_single_url,
)

from app.services.pipeline.direct_record_fallback import (
    apply_direct_record_llm_fallback,
)

from app.services.pipeline.extraction_retry_decision import (
    low_quality_extraction_browser_retry_decision,
    records_missing_repair_fields,
)

from app.services.pipeline.persistence import persist_acquisition_artifacts

from app.services.pipeline.types import URLProcessingConfig

from app.services.robots_policy import RobotsPolicyResult

from sqlalchemy.ext.asyncio import AsyncSession


def _as_async(fn):
    async def _wrapped(*args, **kwargs):
        await asyncio.sleep(0)
        return fn(*args, **kwargs)

    return _wrapped


def _detail_html() -> str:
    return "<html><body><h1>Widget Prime</h1></body></html>"


def _listing_html() -> str:
    return "<html><body><h1>Empty category</h1></body></html>"


def _fake_acquire_result(
    request: AcquisitionRequest,
    *,
    html: str | None = None,
    method: str = "test",
    status_code: int = 200,
    final_url: str | None = None,
    **overrides,
) -> AcquisitionResult:
    return AcquisitionResult(
        request=request,
        final_url=final_url or request.url,
        html=_detail_html() if html is None else html,
        method=method,
        status_code=status_code,
        **overrides,
    )


@_as_async
def _no_adapter(*_args, **_kwargs):
    return None


__all__ = tuple(name for name in globals() if not name.startswith("__"))

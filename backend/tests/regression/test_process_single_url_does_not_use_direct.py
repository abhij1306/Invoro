from __future__ import annotations

from ._pipeline_core_support import _as_async, _no_adapter  # fmt: skip
import pytest
from app.services.acquisition.acquirer import AcquisitionResult  # fmt: skip
from app.services.crawl.crud import create_crawl_run, get_run_logs, get_run_records  # fmt: skip
from app.services.pipeline.extraction_loop import process_single_url  # fmt: skip
from pathlib import Path  # fmt: skip
from sqlalchemy.ext.asyncio import AsyncSession  # fmt: skip


@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_does_not_use_direct_llm_as_primary_listing_extractor(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/category/widgets",
            "surface": "ecommerce_listing",
            "settings": {"respect_robots_txt": False, "llm_enabled": True},
        },
    )

    @_as_async
    def _fake_acquire(request):
        return AcquisitionResult(
            request=request,
            final_url=request.url,
            html="<html><body><main>Category shell</main></body></html>",
            method="browser",
            status_code=200,
            browser_diagnostics={
                "browser_attempted": True,
                "browser_reason": "http-escalation",
                "browser_outcome": "usable_content",
            },
        )

    @_as_async
    def _no_selector_rules(*args, **kwargs):
        del args, kwargs
        return []

    @_as_async
    def _unexpected_resolve_run_config(*args, **kwargs):
        del args, kwargs
        raise AssertionError("empty listing must not ask LLM to invent records")

    @_as_async
    def _persist_artifacts(**kwargs):
        del kwargs
        return "artifacts/widgets.html"

    monkeypatch.setattr("app.services.pipeline.extraction_loop.acquire", _fake_acquire)
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.run_adapter", _no_adapter
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.load_domain_selector_rules",
        _no_selector_rules,
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.extract_records",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.resolve_run_config",
        _unexpected_resolve_run_config,
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.persist_acquisition_artifacts",
        _persist_artifacts,
    )

    result = await process_single_url(db_session, run, run.url)
    rows, total = await get_run_records(db_session, run.id, 1, 20)

    assert result.records == []
    assert result.verdict == "listing_detection_failed"
    assert total == 0
    assert rows == []


@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_ignores_extracted_placeholder_records_from_low_content_browser_page(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/for-sale/mixer-truck",
            "surface": "ecommerce_detail",
            "settings": {"respect_robots_txt": False},
        },
    )

    @_as_async
    def _fake_acquire(request):
        return AcquisitionResult(
            request=request,
            final_url=request.url,
            html="<html><head><title>JavaScript is disabled</title></head><body><h1>JavaScript is disabled</h1></body></html>",
            method="browser",
            status_code=200,
            browser_diagnostics={
                "browser_attempted": True,
                "browser_reason": "http-escalation",
                "browser_outcome": "low_content_shell",
            },
        )

    @_as_async
    def _no_selector_rules(*args, **kwargs):
        del args, kwargs
        return []

    monkeypatch.setattr("app.services.pipeline.extraction_loop.acquire", _fake_acquire)
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.run_adapter", _no_adapter
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.load_domain_selector_rules",
        _no_selector_rules,
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.extract_records",
        lambda *args, **kwargs: [
            {"title": "JavaScript is disabled", "_source": "extraction"}
        ],
    )

    @_as_async
    def _persist_artifacts(**kwargs):
        del kwargs
        return "artifacts/mixer-truck.html"

    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.persist_acquisition_artifacts",
        _persist_artifacts,
    )

    result = await process_single_url(db_session, run, run.url)
    rows, total = await get_run_records(db_session, run.id, 1, 20)

    assert result.records == []
    assert result.verdict == "blocked"
    assert result.url_metrics["browser_outcome"] == "low_content_shell"
    assert result.url_metrics["failure_reason"] == "challenge_shell"
    assert total == 0
    assert rows == []


@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_does_not_retry_browser_after_prior_challenge_attempt(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/category/widgets",
            "surface": "ecommerce_listing",
            "settings": {"respect_robots_txt": False},
        },
    )
    acquire_calls: list[dict[str, object]] = []

    @_as_async
    def _fake_acquire(request):
        acquire_calls.append(dict(request.acquisition_profile))
        return AcquisitionResult(
            request=request,
            final_url=request.url,
            html="<html><body>http</body></html>",
            method="curl_cffi",
            status_code=200,
            browser_diagnostics={
                "browser_attempted": True,
                "browser_reason": "http-escalation",
                "browser_outcome": "challenge_page",
            },
        )

    @_as_async
    def _no_selector_rules(*args, **kwargs):
        del args, kwargs
        return []

    monkeypatch.setattr("app.services.pipeline.extraction_loop.acquire", _fake_acquire)
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.run_adapter", _no_adapter
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.load_domain_selector_rules",
        _no_selector_rules,
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.extract_records",
        lambda *args, **kwargs: [],
    )

    @_as_async
    def _persist_artifacts(**kwargs):
        del kwargs
        return "artifacts/widgets.html"

    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.persist_acquisition_artifacts",
        _persist_artifacts,
    )

    result = await process_single_url(db_session, run, run.url)

    assert len(acquire_calls) == 1
    assert result.url_metrics["method"] == "curl_cffi"
    assert result.url_metrics["blocked"] is True
    assert result.url_metrics["browser_attempted"] is True
    assert result.url_metrics["browser_outcome"] == "challenge_page"
    assert result.verdict == "blocked"


@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_marks_low_content_listing_with_challenge_signals_as_blocked(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/category/widgets",
            "surface": "ecommerce_listing",
            "settings": {"respect_robots_txt": False},
        },
    )

    @_as_async
    def _fake_acquire(request):
        return AcquisitionResult(
            request=request,
            final_url=request.url,
            html="<html><body>challenge shell</body></html>",
            method="browser",
            status_code=200,
            blocked=False,
            browser_diagnostics={
                "browser_attempted": True,
                "browser_reason": "http-escalation",
                "browser_outcome": "low_content_shell",
                "challenge_provider_hits": ["datadome"],
                "challenge_evidence": ["provider:datadome"],
            },
        )

    @_as_async
    def _no_selector_rules(*args, **kwargs):
        del args, kwargs
        return []

    monkeypatch.setattr("app.services.pipeline.extraction_loop.acquire", _fake_acquire)
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.run_adapter", _no_adapter
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.load_domain_selector_rules",
        _no_selector_rules,
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.extract_records",
        lambda *args, **kwargs: [],
    )

    @_as_async
    def _persist_artifacts(**kwargs):
        del kwargs
        return "artifacts/widgets.html"

    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.persist_acquisition_artifacts",
        _persist_artifacts,
    )

    result = await process_single_url(db_session, run, run.url)

    assert result.records == []
    assert result.url_metrics["blocked"] is True
    assert result.url_metrics["browser_outcome"] == "low_content_shell"
    assert result.verdict == "blocked"


@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_rejects_detail_non_detail_seed_with_failure_reason(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/search?q=widget",
            "surface": "ecommerce_detail",
            "settings": {"respect_robots_txt": False},
        },
    )

    @_as_async
    def _fake_acquire(request):
        return AcquisitionResult(
            request=request,
            final_url=request.url,
            html="<html><body>search</body></html>",
            method="browser",
            status_code=200,
            blocked=False,
            browser_diagnostics={
                "browser_attempted": True,
                "browser_outcome": "usable_content",
                "readiness_probes": [{"is_ready": True}],
            },
        )

    @_as_async
    def _no_selector_rules(*args, **kwargs):
        del args, kwargs
        return []

    monkeypatch.setattr("app.services.pipeline.extraction_loop.acquire", _fake_acquire)
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.run_adapter", _no_adapter
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.load_domain_selector_rules",
        _no_selector_rules,
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.extract_records",
        lambda *args, **kwargs: [
            {"title": "Search Results", "url": "https://example.com/search?q=widget"}
        ],
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.detail_record_rejection_reason",
        lambda *args, **kwargs: "non_detail_seed",
    )

    @_as_async
    def _persist_artifacts(**kwargs):
        del kwargs
        return "artifacts/widgets.html"

    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.persist_acquisition_artifacts",
        _persist_artifacts,
    )

    result = await process_single_url(db_session, run, run.url)

    assert result.records == []
    assert result.verdict == "empty"
    assert result.url_metrics["failure_reason"] == "non_detail_seed"
    assert result.url_metrics["record_count"] == 0


@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_rejects_detail_challenge_shell_and_marks_blocked(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/products/widget-prime",
            "surface": "ecommerce_detail",
            "settings": {"respect_robots_txt": False},
        },
    )

    @_as_async
    def _fake_acquire(request):
        return AcquisitionResult(
            request=request,
            final_url=request.url,
            html="<html><body>challenge</body></html>",
            method="browser",
            status_code=200,
            blocked=False,
            browser_diagnostics={
                "browser_attempted": True,
                "browser_reason": "vendor-block:datadome",
                "browser_outcome": "usable_content",
                "challenge_evidence": ["strong:captcha", "provider:datadome"],
                "challenge_provider_hits": ["datadome"],
                "readiness_probes": [{"is_ready": False}],
            },
        )

    @_as_async
    def _no_selector_rules(*args, **kwargs):
        del args, kwargs
        return []

    monkeypatch.setattr("app.services.pipeline.extraction_loop.acquire", _fake_acquire)
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.run_adapter", _no_adapter
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.load_domain_selector_rules",
        _no_selector_rules,
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.extract_records",
        lambda *args, **kwargs: [
            {
                "title": "Sorry, you have been blocked",
                "url": "https://example.com/products/widget-prime",
            }
        ],
    )

    @_as_async
    def _persist_artifacts(**kwargs):
        del kwargs
        return "artifacts/widgets.html"

    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.persist_acquisition_artifacts",
        _persist_artifacts,
    )

    result = await process_single_url(db_session, run, run.url)
    logs = await get_run_logs(db_session, run.id)

    assert result.records == []
    assert result.verdict == "blocked"
    assert result.url_metrics["failure_reason"] == "challenge_shell"
    assert result.url_metrics["blocked"] is True
    assert [log.message for log in logs] == [
        "Extraction yielded 0 records (generic extraction path)",
        "Rejected detail extraction for https://example.com/products/widget-prime: challenge_shell",
    ]


@pytest.mark.asyncio
@pytest.mark.regression
async def test_challenge_shell_budget_skip_logs_once(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/products/widget-prime",
            "surface": "ecommerce_detail",
            "settings": {"respect_robots_txt": False},
        },
    )

    @_as_async
    def _fake_acquire(request):
        return AcquisitionResult(
            request=request,
            final_url=request.url,
            html="<html><body>challenge</body></html>",
            method="browser",
            status_code=200,
            blocked=False,
            browser_diagnostics={
                "browser_attempted": True,
                "browser_engine": "patchright",
                "browser_reason": "vendor-block:akamai",
                "browser_outcome": "low_content_shell",
                "readiness_probes": [{"is_ready": False}],
            },
        )

    @_as_async
    def _no_selector_rules(*args, **kwargs):
        del args, kwargs
        return []

    monkeypatch.setattr("app.services.pipeline.extraction_loop.acquire", _fake_acquire)
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.run_adapter", _no_adapter
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.load_domain_selector_rules",
        _no_selector_rules,
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.extract_records",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.real_chrome_browser_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop._remaining_url_budget_seconds",
        lambda context: 1.0,
    )

    result = await process_single_url(db_session, run, run.url)
    logs = await get_run_logs(db_session, run.id)
    skip_logs = [
        log.message
        for log in logs
        if "Skipping challenge_shell Chrome escalation" in log.message
    ]

    assert result.url_metrics["failure_reason"] == "challenge_shell"
    assert len(skip_logs) == 1


@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_keeps_prior_observation_when_browser_retry_fails(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/category/widgets",
            "surface": "ecommerce_listing",
            "settings": {"respect_robots_txt": False},
        },
    )
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setattr(
        "app.services.artifact_store.settings.artifacts_dir", artifacts_dir
    )
    acquire_calls: list[dict[str, object]] = []

    @_as_async
    def _fake_acquire(request):
        acquire_calls.append(dict(request.acquisition_profile))
        if request.acquisition_profile.get("prefer_browser"):
            raise TimeoutError("browser retry timed out")
        return AcquisitionResult(
            request=request,
            final_url=request.url,
            html="<html><body>http</body></html>",
            method="curl_cffi",
            status_code=200,
        )

    @_as_async
    def _no_selector_rules(*args, **kwargs):
        del args, kwargs
        return []

    monkeypatch.setattr("app.services.pipeline.extraction_loop.acquire", _fake_acquire)
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.run_adapter", _no_adapter
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.load_domain_selector_rules",
        _no_selector_rules,
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.extract_records",
        lambda *args, **kwargs: [],
    )

    result = await process_single_url(db_session, run, run.url)

    logs = await get_run_logs(db_session, run.id)
    artifact_dir = artifacts_dir / "runs" / str(run.id) / "pages"
    diagnostics_files = list(artifact_dir.glob("*.browser.json"))

    assert result.verdict == "listing_detection_failed"
    assert result.url_metrics["failure_reason"] == "timeout"
    assert len(acquire_calls) == 2
    assert [log.message for log in logs] == [
        "Acquired payload via curl_cffi (status=200)",
        "No records via curl_cffi; retrying browser render for https://example.com/category/widgets",
        "Browser retry failed for https://example.com/category/widgets: TimeoutError: browser retry timed out",
        "Extraction yielded 0 records (generic extraction path)",
        "Normalized 0 record(s) for persistence",
        "Persisted 0 record(s) for https://example.com/category/widgets",
    ]
    assert len(diagnostics_files) == 1


@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_persists_live_acquisition_events(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/category/widgets",
            "surface": "ecommerce_listing",
            "settings": {"respect_robots_txt": False},
        },
    )

    async def _fake_acquire(request):
        assert request.on_event is not None
        await request.on_event("info", "Detected listing layout, pagination: scroll")
        await request.on_event("info", "Scroll 1/3 - 24 -> 48 records")
        return AcquisitionResult(
            request=request,
            final_url=request.url,
            html="<html><body>browser</body></html>",
            method="browser",
            status_code=200,
            browser_diagnostics={"browser_attempted": True},
        )

    @_as_async
    def _no_selector_rules(*args, **kwargs):
        del args, kwargs
        return []

    monkeypatch.setattr("app.services.pipeline.extraction_loop.acquire", _fake_acquire)
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.run_adapter", _no_adapter
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.load_domain_selector_rules",
        _no_selector_rules,
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.extract_records",
        lambda *args, **kwargs: [
            {
                "title": "Widget Prime",
                "url": "https://example.com/products/widget-prime",
            }
        ],
    )

    @_as_async
    def _persist_artifacts(**kwargs):
        del kwargs
        return "artifacts/widgets.html"

    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.persist_acquisition_artifacts",
        _persist_artifacts,
    )

    await process_single_url(db_session, run, run.url)
    logs = await get_run_logs(db_session, run.id)

    assert [log.message for log in logs] == [
        "Detected listing layout, pagination: scroll",
        "Scroll 1/3 - 24 -> 48 records",
        "Extracted 1 records using generic extraction path",
        "Normalized 1 record(s) for persistence",
        "Persisted 1 record(s) for https://example.com/category/widgets",
    ]

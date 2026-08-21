from __future__ import annotations

from ._pipeline_core_support import _as_async, _detail_html, _no_adapter  # fmt: skip
import copy
import json
import pytest
from app.services.acquisition.acquirer import AcquisitionRequest, AcquisitionResult  # fmt: skip
from app.services.acquisition_plan import AcquisitionPlan  # fmt: skip
from app.services.crawl.crud import create_crawl_run, get_run_logs, get_run_records  # fmt: skip
from app.services.pipeline.extraction_loop import apply_llm_fallback, process_single_url  # fmt: skip
from app.services.pipeline.persistence import persist_acquisition_artifacts  # fmt: skip
from pathlib import Path  # fmt: skip
from sqlalchemy.ext.asyncio import AsyncSession  # fmt: skip

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_keeps_platform_family_separate_from_adapter_provenance(
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
            html=_detail_html(),
            method="test",
            status_code=200,
        )

    @_as_async
    def _no_selector_rules(*args, **kwargs):
        del args, kwargs
        return []

    @_as_async
    def _persist_artifacts(**kwargs):
        del kwargs
        return "artifacts/widget-prime.html"

    monkeypatch.setattr("app.services.pipeline.extraction_loop.acquire", _fake_acquire)
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.detect_platform_family",
        lambda *args, **kwargs: "shopify",
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.run_adapter", _no_adapter
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.load_domain_selector_rules",
        _no_selector_rules,
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.extract_records",
        lambda *args, **kwargs: [{"title": "Widget Prime", "_source": "extraction"}],
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.persist_acquisition_artifacts",
        _persist_artifacts,
    )

    result = await process_single_url(db_session, run, run.url)

    assert result.url_metrics["adapter_name"] is None
    assert result.url_metrics["platform_family"] == "shopify"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_apply_llm_fallback_re_normalizes_llm_values_before_return(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/products/widget-prime?utm_source=mail",
            "surface": "ecommerce_detail",
            "settings": {"llm_enabled": True},
            "additional_fields": ["review_count", "availability"],
        },
    )

    @_as_async
    def _fake_extract_missing_fields(*args, **kwargs):
        del args, kwargs
        return (
            {
                "review_count": "1,234 reviews",
                "availability": "In Stock",
                "url": "https://example.com/products/widget-prime?utm_source=mail",
            },
            None,
        )

    monkeypatch.setattr(
        "app.services.pipeline.direct_record_fallback.extract_missing_fields",
        _fake_extract_missing_fields,
    )

    rows = await apply_llm_fallback(
        db_session,
        run=run,
        page_url="https://example.com/products/widget-prime?utm_source=mail",
        html=_detail_html(),
        records=[
            {
                "title": "Widget Prime",
                "source_url": "https://example.com/products/widget-prime?utm_source=mail",
                "url": "https://example.com/products/widget-prime?utm_source=mail",
                "_source": "json_ld",
                "_field_sources": {"title": ["json_ld"]},
                "_confidence": {"score": 0.1},
                "_self_heal": {"enabled": False, "triggered": False},
            }
        ],
    )

    assert rows[0]["review_count"] == 1234
    assert rows[0]["availability"] == "in_stock"
    assert rows[0]["url"] == "https://example.com/products/widget-prime"
    assert rows[0]["source_url"] == "https://example.com/products/widget-prime"
    assert rows[0]["_field_sources"]["review_count"] == ["llm_missing_field_extraction"]
    assert rows[0]["_self_heal"]["mode"] == "missing_field_extraction"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_apply_llm_fallback_skips_when_contract_fields_complete(
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
            "settings": {"llm_enabled": True},
        },
    )

    @_as_async
    def _unexpected_extract_missing_fields(*args, **kwargs):
        del args, kwargs
        raise AssertionError("LLM should not run when contract fields are complete")

    monkeypatch.setattr(
        "app.services.pipeline.direct_record_fallback.extract_missing_fields",
        _unexpected_extract_missing_fields,
    )

    rows = await apply_llm_fallback(
        db_session,
        run=run,
        page_url="https://example.com/products/widget-prime",
        html=_detail_html(),
        records=[
            {
                "title": "Widget Prime",
                "price": "19.99",
                "currency": "USD",
                "brand": "Acme",
                "image_url": "https://example.com/widget.jpg",
                "_confidence": {"score": 0.1},
            }
        ],
    )

    assert rows[0]["title"] == "Widget Prime"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_applies_llm_fallback_when_confidence_score_is_non_numeric(
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
            "settings": {"llm_enabled": True},
            "additional_fields": ["price"],
        },
    )

    @_as_async
    def _fake_acquire(request):
        return AcquisitionResult(
            request=request,
            final_url=request.url,
            html=_detail_html(),
            method="test",
            status_code=200,
        )

    @_as_async
    def _fake_extract_missing_fields(*args, **kwargs):
        del args, kwargs
        return {"price": "19.99"}, None

    @_as_async
    def _no_selector_rules(*args, **kwargs):
        del args, kwargs
        return []

    monkeypatch.setattr("app.services.pipeline.extraction_loop.acquire", _fake_acquire)
    monkeypatch.setattr(
        "app.services.pipeline.direct_record_fallback.extract_missing_fields",
        _fake_extract_missing_fields,
    )
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
                "_confidence": {"score": "not-a-number"},
                "_self_heal": {},
            }
        ],
    )

    @_as_async
    def _persist_artifacts(**kwargs):
        del kwargs
        return "artifacts/widget-prime.html"

    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.persist_acquisition_artifacts",
        _persist_artifacts,
    )

    result = await process_single_url(db_session, run, run.url)
    rows, total = await get_run_records(db_session, run.id, 1, 20)

    assert result.records[0]["price"] == "19.99"
    assert total == 1
    assert rows[0].data["price"] == "19.99"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_strips_schema_type_mismatches_during_normalization(
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
            html=_detail_html(),
            method="test",
            status_code=200,
        )

    @_as_async
    def _no_selector_rules(*args, **kwargs):
        del args, kwargs
        return []

    @_as_async
    def _persist_artifacts(**kwargs):
        del kwargs
        return "artifacts/widget-prime.html"

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
                "price": {"amount": "19.99"},
                "variants": "not-a-list",
                "_source": "adapter",
            }
        ],
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.persist_acquisition_artifacts",
        _persist_artifacts,
    )

    result = await process_single_url(db_session, run, run.url)
    rows, total = await get_run_records(db_session, run.id, 1, 20)
    logs = await get_run_logs(db_session, run.id)

    assert result.records == [{"title": "Widget Prime", "_source": "adapter"}]
    assert total == 1
    assert rows[0].data == {"title": "Widget Prime"}
    assert any("Schema validation cleaned record 1" in log.message for log in logs)

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_persists_browser_diagnostics_and_screenshot_artifacts(
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
            "url": "https://example.com/products/widget-prime",
            "surface": "ecommerce_detail",
            "settings": {"respect_robots_txt": False},
        },
    )
    artifacts_dir = tmp_path / "artifacts"
    staged_screenshot = tmp_path / "browser-screenshot.png"
    staged_screenshot.write_bytes(b"fake-png")
    monkeypatch.setattr(
        "app.services.artifact_store.settings.artifacts_dir", artifacts_dir
    )

    @_as_async
    def _fake_acquire(request):
        return AcquisitionResult(
            request=request,
            final_url=request.url,
            html="<html><head><title>Access denied</title></head><body>captcha datadome</body></html>",
            method="browser",
            status_code=403,
            blocked=True,
            browser_diagnostics={
                "browser_attempted": True,
                "browser_reason": "http-escalation",
                "browser_outcome": "challenge_page",
                "html_bytes": 82,
                "phase_timings_ms": {"navigation": 1200},
                "challenge_evidence": ["captcha", "datadome"],
            },
            artifacts={"browser_screenshot_path": str(staged_screenshot)},
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

    await process_single_url(db_session, run, run.url)

    artifact_dir = artifacts_dir / "runs" / str(run.id) / "pages"
    diagnostics_files = list(artifact_dir.glob("*.browser.json"))
    screenshot_files = list(artifact_dir.glob("*.browser.png"))

    assert len(diagnostics_files) == 1
    assert len(screenshot_files) == 1
    assert not staged_screenshot.exists()

    diagnostics_payload = json.loads(diagnostics_files[0].read_text(encoding="utf-8"))
    assert diagnostics_payload["browser_outcome"] == "challenge_page"
    assert diagnostics_payload["browser_reason"] == "http-escalation"
    assert diagnostics_payload["artifact_paths"]["html"].endswith(".html")
    assert diagnostics_payload["artifact_paths"]["screenshot"].endswith(".png")

@pytest.mark.asyncio
@pytest.mark.regression
async def test_persist_acquisition_artifacts_treats_none_artifacts_as_empty_mapping(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setattr(
        "app.services.artifact_store.settings.artifacts_dir", artifacts_dir
    )

    acquisition_result = AcquisitionResult(
        request=AcquisitionRequest(
            run_id=7,
            url="https://example.com/products/widget-prime",
            plan=AcquisitionPlan(surface="ecommerce_detail"),
        ),
        final_url="https://example.com/products/widget-prime",
        html="<html><body>Widget Prime</body></html>",
        method="browser",
        status_code=200,
        browser_diagnostics={"browser_attempted": True},
        artifacts=None,
    )

    raw_html_path = await persist_acquisition_artifacts(
        run_id=7,
        acquisition_result=acquisition_result,
        browser_attempted=True,
        screenshot_required=True,
    )

    assert raw_html_path.endswith(".html")
    assert (
        acquisition_result.browser_diagnostics["artifact_paths"]["screenshot"] is None
    )

@pytest.mark.asyncio
@pytest.mark.regression
async def test_persist_acquisition_artifacts_does_not_mutate_source_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    artifacts_dir = tmp_path / "artifacts"
    monkeypatch.setattr(
        "app.services.artifact_store.settings.artifacts_dir", artifacts_dir
    )

    artifacts = {
        "browser_screenshot_path": "",
        "browser_screenshot_png": b"png",
        "keep": "value",
    }
    expected_artifacts = copy.deepcopy(artifacts)
    acquisition_result = AcquisitionResult(
        request=AcquisitionRequest(
            run_id=7,
            url="https://example.com/products/widget-prime",
            plan=AcquisitionPlan(surface="ecommerce_detail"),
        ),
        final_url="https://example.com/products/widget-prime",
        html="<html><body>Widget Prime</body></html>",
        method="browser",
        status_code=200,
        browser_diagnostics={"browser_attempted": True},
        artifacts=artifacts,
    )

    await persist_acquisition_artifacts(
        run_id=7,
        acquisition_result=acquisition_result,
        browser_attempted=True,
        screenshot_required=True,
    )

    assert acquisition_result.artifacts == expected_artifacts
    assert artifacts == expected_artifacts

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_does_not_retry_browser_after_empty_browser_acquisition(
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
            html="<html><body>browser</body></html>",
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
    assert result.url_metrics["browser_attempted"] is True
    assert result.url_metrics["browser_outcome"] == "low_content_shell"
    assert result.verdict == "listing_detection_failed"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_skips_llm_on_low_content_browser_listing(
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
            html="<html><head><title>Belk Spa</title></head><body>Be Right Back!</body></html>",
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

    @_as_async
    def _unexpected_direct_llm(*args, **kwargs):
        del args, kwargs
        raise AssertionError(
            "low-content browser result must not run direct LLM fallback"
        )

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
        "app.services.pipeline.extraction_loop.apply_direct_record_llm_fallback_impl",
        _unexpected_direct_llm,
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

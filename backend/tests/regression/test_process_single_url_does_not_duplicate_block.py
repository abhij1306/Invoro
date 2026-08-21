from __future__ import annotations

from ._pipeline_core_support import _as_async, _detail_html, _no_adapter  # fmt: skip
import pytest
from app.services.acquisition.acquirer import AcquisitionResult  # fmt: skip
from app.services.crawl.crud import create_crawl_run, get_run_logs, get_run_records  # fmt: skip
from app.services.pipeline.extraction_loop import process_single_url  # fmt: skip
from sqlalchemy.ext.asyncio import AsyncSession  # fmt: skip

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_does_not_duplicate_block_warning_after_browser_event(
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
        await request.on_event(
            "warning",
            f"Acquisition detected rate limiting or bot protection for {request.url}",
        )
        return AcquisitionResult(
            request=request,
            final_url=request.url,
            html="<html><body>challenge shell</body></html>",
            method="browser",
            status_code=200,
            blocked=False,
            browser_diagnostics={
                "browser_attempted": True,
                "browser_outcome": "challenge_page",
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

    await process_single_url(db_session, run, run.url)
    logs = await get_run_logs(db_session, run.id)
    warning_messages = [
        log.message
        for log in logs
        if log.level == "warning"
        and "Acquisition detected rate limiting or bot protection" in log.message
    ]

    assert warning_messages == [
        "Acquisition detected rate limiting or bot protection for https://example.com/category/widgets"
    ]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_persists_detail_records_after_self_heal_and_llm_fallback(
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
            "settings": {"respect_robots_txt": False, "llm_enabled": True},
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
    def _fake_self_heal(session, **kwargs):
        del session
        record = dict(kwargs["records"][0])
        record["title"] = "Widget Prime (self-healed)"
        record["_self_heal"] = {"mode": "selector_synthesis", "triggered": True}
        return [record], list(kwargs["selector_rules"])

    @_as_async
    def _fake_llm(session, *, records, **kwargs):
        del session, kwargs
        record = dict(records[0])
        record["price"] = "19.99"
        return [record]

    monkeypatch.setattr("app.services.pipeline.extraction_loop.acquire", _fake_acquire)

    @_as_async
    def _no_selector_rules(*args, **kwargs):
        del args, kwargs
        return []

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
        "app.services.pipeline.extraction_loop.apply_selector_self_heal",
        _fake_self_heal,
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.apply_llm_fallback", _fake_llm
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
    await db_session.refresh(run)
    rows, total = await get_run_records(db_session, run.id, 1, 20)

    assert result.verdict == "success"
    assert result.records == [
        {
            "title": "Widget Prime (self-healed)",
            "_source": "extraction",
            "_self_heal": {"mode": "selector_synthesis", "triggered": True},
            "price": "19.99",
        }
    ]
    assert run.summary_dict()["current_stage"] == "PERSIST"
    assert total == 1
    assert rows[0].data == {"title": "Widget Prime (self-healed)", "price": "19.99"}
    assert rows[0].raw_html_path == "artifacts/widget-prime.html"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_retries_with_browser_after_empty_non_browser_extraction(
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
        if request.acquisition_profile.get("prefer_browser"):
            return AcquisitionResult(
                request=request,
                final_url=request.url,
                html="<html><body>browser</body></html>",
                method="browser",
                status_code=200,
            )
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

    def _extract_records(html, *args, **kwargs):
        del args, kwargs
        if "browser" in html:
            return [
                {
                    "title": "Widget Prime",
                    "url": "https://example.com/products/widget-prime",
                }
            ]
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
        "app.services.pipeline.extraction_loop.extract_records", _extract_records
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
    rows, total = await get_run_records(db_session, run.id, 1, 20)

    assert len(acquire_calls) == 2
    assert acquire_calls[1]["prefer_browser"] is True
    assert result.verdict == "success"
    assert result.url_metrics["method"] == "browser"
    assert total == 1
    assert rows[0].data["title"] == "Widget Prime"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_does_not_auto_scroll_after_empty_browser_listing(
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
    acquire_calls: list[tuple[dict[str, object], str | None]] = []

    @_as_async
    def _fake_acquire(request):
        acquire_calls.append(
            (dict(request.acquisition_profile), request.plan.traversal_mode)
        )
        if request.acquisition_profile.get("prefer_browser"):
            return AcquisitionResult(
                request=request,
                final_url=request.url,
                html="<html><body>browser</body></html>",
                method="browser",
                status_code=200,
                browser_diagnostics={"browser_outcome": "usable_content"},
            )
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

    @_as_async
    def _persist_artifacts(**kwargs):
        del kwargs
        return "artifacts/widgets.html"

    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.persist_acquisition_artifacts",
        _persist_artifacts,
    )

    result = await process_single_url(db_session, run, run.url)

    assert len(acquire_calls) == 2
    assert acquire_calls[1][0]["prefer_browser"] is True
    assert acquire_calls[1][1] is None
    assert result.verdict == "listing_detection_failed"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_persists_listing_page_source_separately_from_record_url(
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
            html="<html><body>listing</body></html>",
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
                "source_url": "https://example.com/category/widgets",
                "url": "https://example.com/products/widget-prime",
                "_source": "dom_listing",
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
    rows, total = await get_run_records(db_session, run.id, 1, 20)

    assert result.verdict == "success"
    assert total == 1
    assert rows[0].source_url == "https://example.com/category/widgets"
    assert rows[0].data["url"] == "https://example.com/products/widget-prime"
    assert "page_markdown" not in (rows[0].raw_data or {})

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_log_uses_generic_extraction_label_when_no_adapter_matches(
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
            html="<html><body>listing</body></html>",
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
                "source_url": "https://example.com/category/widgets",
                "url": "https://example.com/products/widget-prime",
                "_source": "dom_listing",
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

    assert any(
        log.message == "Extracted 1 records using generic extraction path"
        for log in logs
    )

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_upserts_duplicate_run_identity_records(
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
            html="<html><body><h1>Widget Prime</h1></body></html>",
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
    extracted_prices = iter(["19.99", "24.99"])

    def _extract_records(*args, **kwargs):
        del args, kwargs
        try:
            price = extracted_prices.__next__()
        except StopIteration as exc:
            raise AssertionError("Expected another extracted price") from exc
        return [
            {
                "title": "Widget Prime",
                "price": price,
                "source_url": "https://example.com/products/widget-prime",
                "url": "https://example.com/products/widget-prime",
                "_source": "json_ld",
            }
        ]

    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.extract_records", _extract_records
    )

    @_as_async
    def _persist_artifacts(**kwargs):
        del kwargs
        return "artifacts/widget-prime.html"

    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.persist_acquisition_artifacts",
        _persist_artifacts,
    )

    first = await process_single_url(db_session, run, run.url)
    second = await process_single_url(db_session, run, run.url)
    rows, total = await get_run_records(db_session, run.id, 1, 20)

    assert first.records[0]["price"] == "19.99"
    assert second.records[0]["price"] == "24.99"
    assert total == 1
    assert rows[0].content_fingerprint
    assert rows[0].data["price"] == "24.99"
    assert rows[0].data["url"] == "https://example.com/products/widget-prime"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_offloads_extract_records_to_thread(
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
    to_thread_calls: list[str] = []

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
    def _fake_to_thread(func, *args, **kwargs):
        to_thread_calls.append(getattr(func, "__name__", type(func).__name__))
        return func(*args, **kwargs)

    monkeypatch.setattr("app.services.pipeline.extraction_loop.acquire", _fake_acquire)
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.run_adapter", _no_adapter
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.load_domain_selector_rules",
        _no_selector_rules,
    )
    monkeypatch.setattr(
        "app.services.pipeline.record_extraction_stage.asyncio.to_thread",
        _fake_to_thread,
    )

    result = await process_single_url(db_session, run, run.url)

    assert result.verdict in {"success", "empty"}
    assert "extract_records" in to_thread_calls

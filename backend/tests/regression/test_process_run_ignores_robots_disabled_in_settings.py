from __future__ import annotations

from .test_batch_runtime import *  # noqa: F403


@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_run_ignores_robots_when_disabled_in_settings(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/private/widget-prime",
            "surface": "ecommerce_detail",
            "settings": {"respect_robots_txt": False},
        },
    )
    acquire_calls: list[str] = []

    async def _disallow(url: str, *, user_agent: str = "*") -> RobotsPolicyResult:
        del user_agent
        return RobotsPolicyResult(
            allowed=False,
            outcome="disallowed",
            robots_url="https://example.com/robots.txt",
        )

    async def _fake_acquire(request):
        acquire_calls.append(request.url)
        return AcquisitionResult(
            request=request,
            final_url=request.url,
            html=_detail_html(),
            method="test",
            status_code=200,
        )

    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.check_url_crawlability", _disallow
    )
    monkeypatch.setattr("app.services.pipeline.extraction_loop.acquire", _fake_acquire)

    await process_run(db_session, run.id)
    await db_session.refresh(run)
    rows, total = await get_run_records(db_session, run.id, 1, 20)

    assert acquire_calls == ["https://example.com/private/widget-prime"]
    assert run.status == "completed"
    assert run.result_summary["extraction_verdict"] == "success"
    assert total == 1
    assert rows[0].data["title"] == "Widget Prime"

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "robots_outcome", [ROBOTS_ALLOWED, ROBOTS_MISSING, ROBOTS_FETCH_FAILURE]
)
@pytest.mark.regression
async def test_process_run_continues_when_robots_allows_or_fails_open(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
    robots_outcome: str,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/products/widget-prime",
            "surface": "ecommerce_detail",
        },
    )
    acquire_calls: list[str] = []

    async def _allow(url: str, *, user_agent: str = "*") -> RobotsPolicyResult:
        del user_agent
        return RobotsPolicyResult(
            allowed=True,
            outcome=robots_outcome,
            robots_url="https://example.com/robots.txt",
            error="timeout" if robots_outcome == ROBOTS_FETCH_FAILURE else None,
        )

    async def _fake_acquire(request):
        acquire_calls.append(request.url)
        return AcquisitionResult(
            request=request,
            final_url=request.url,
            html=_detail_html(),
            method="test",
            status_code=200,
        )

    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.check_url_crawlability", _allow
    )
    monkeypatch.setattr("app.services.pipeline.extraction_loop.acquire", _fake_acquire)

    await process_run(db_session, run.id)
    await db_session.refresh(run)
    rows, total = await get_run_records(db_session, run.id, 1, 20)

    assert acquire_calls == ["https://example.com/products/widget-prime"]
    assert run.status == "completed"
    assert run.result_summary["extraction_verdict"] == "success"
    assert total == 1
    assert rows[0].data["title"] == "Widget Prime"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_run_enforces_url_timeout_from_settings(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/products/slow-widget",
            "surface": "ecommerce_detail",
            "settings": {"url_timeout_seconds": 0.01},
        },
    )

    async def _slow_process_single_url(*args, **kwargs):
        del args, kwargs
        await asyncio.sleep(0.05)
        raise AssertionError("timeout should fire before this returns")

    monkeypatch.setattr(
        "app.services.crawl.batch_runtime.process_single_url",
        _slow_process_single_url,
    )

    await process_run(db_session, run.id)
    await db_session.refresh(run)

    assert run.status == "completed"
    assert run.result_summary["extraction_verdict"] == "error"
    assert run.result_summary["url_verdicts"] == ["error"]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_run_default_timeout_includes_acquisition_slack(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
    patch_settings,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/products/slow-widget",
            "surface": "ecommerce_detail",
        },
    )

    patch_settings(
        url_process_timeout_seconds=0.01,
        url_process_timeout_buffer_seconds=0.03,
        acquisition_attempt_timeout_seconds=0.02,
    )

    async def _slow_process_single_url(*args, **kwargs):
        del args, kwargs
        await asyncio.sleep(0.025)
        return URLProcessingResult(
            records=[],
            verdict="success",
            url_metrics={"record_count": 0},
        )

    monkeypatch.setattr(
        "app.services.crawl.batch_runtime.process_single_url",
        _slow_process_single_url,
    )

    await process_run(db_session, run.id)
    await db_session.refresh(run)

    assert run.status == "completed"
    assert run.result_summary["extraction_verdict"] == "success"
    assert run.result_summary["url_verdicts"] == ["success"]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_batch_run_preserves_requested_fields_for_every_url(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
    patch_settings,
) -> None:
    patch_settings(url_batch_concurrency=1)
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "batch",
            "urls": [
                "https://example.com/products/widget-1",
                "https://example.com/products/widget-2",
            ],
            "surface": "ecommerce_detail",
            "requested_fields": ["materials"],
        },
    )
    captured_requested_fields: list[list[str]] = []

    async def _fake_acquire(request):
        captured_requested_fields.append(list(request.requested_fields))
        return AcquisitionResult(
            request=request,
            final_url=request.url,
            html=_detail_html(),
            method="test",
            status_code=200,
        )

    monkeypatch.setattr("app.services.pipeline.extraction_loop.acquire", _fake_acquire)

    await process_run(db_session, run.id)

    assert captured_requested_fields == [["materials"], ["materials"]]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_batch_run_preserves_proxy_list_for_every_url(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
    patch_settings,
) -> None:
    patch_settings(url_batch_concurrency=1)
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "batch",
            "urls": [
                "https://example.com/products/widget-1",
                "https://example.com/products/widget-2",
            ],
            "surface": "ecommerce_detail",
            "settings": {
                "proxy_enabled": True,
                "proxy_list": ["http://proxy-a", "http://proxy-b"],
                "proxy_profile": {
                    "enabled": True,
                    "proxy_list": ["http://proxy-a", "http://proxy-b"],
                },
            },
        },
    )
    captured_proxy_lists: list[list[str]] = []

    async def _fake_acquire(request):
        captured_proxy_lists.append(list(request.proxy_list))
        return AcquisitionResult(
            request=request,
            final_url=request.url,
            html=_detail_html(),
            method="test",
            status_code=200,
        )

    monkeypatch.setattr("app.services.pipeline.extraction_loop.acquire", _fake_acquire)

    await process_run(db_session, run.id)

    assert captured_proxy_lists == [
        ["http://proxy-a", "http://proxy-b"],
        ["http://proxy-a", "http://proxy-b"],
    ]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_batch_run_preserves_exact_requested_section_labels_for_every_url(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
    patch_settings,
) -> None:
    patch_settings(url_batch_concurrency=1)
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "batch",
            "urls": [
                "https://example.com/products/widget-1",
                "https://example.com/products/widget-2",
            ],
            "surface": "ecommerce_detail",
            "additional_fields": ["Features & Benefits"],
        },
    )
    captured_requested_fields: list[list[str]] = []

    async def _fake_acquire(request):
        captured_requested_fields.append(list(request.requested_fields))
        return AcquisitionResult(
            request=request,
            final_url=request.url,
            html=_detail_html(),
            method="test",
            status_code=200,
        )

    monkeypatch.setattr("app.services.pipeline.extraction_loop.acquire", _fake_acquire)

    await process_run(db_session, run.id)

    assert captured_requested_fields == [
        ["Features & Benefits"],
        ["Features & Benefits"],
    ]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_batch_run_resolves_urls_from_sitemap_settings(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
    patch_settings,
) -> None:
    patch_settings(url_batch_concurrency=1)
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "batch",
            "surface": "ecommerce_listing",
            "url": "https://example.com",
            "settings": {
                "sitemap_domain": "example.com",
                "sitemap_filter_keyword": "collections",
                "sitemap_max_urls": 2,
            },
        },
    )
    resolved_inputs: list[tuple[str, str, int, bool]] = []
    processed_urls: list[str] = []

    async def _fake_resolve_category_urls_from_sitemap(
        domain: str,
        filter_keyword: str,
        max_urls: int,
        allow_homepage_fallback: bool = False,
    ) -> list[str]:
        resolved_inputs.append(
            (domain, filter_keyword, max_urls, allow_homepage_fallback)
        )
        return [
            "https://example.com/collections/a",
            "https://example.com/collections/b",
        ]

    async def _fake_process_single_url(*args, **kwargs):
        del args
        url = str(kwargs.get("url") or "")
        processed_urls.append(url)
        return URLProcessingResult(
            records=[],
            verdict="success",
            url_metrics={"record_count": 0},
        )

    monkeypatch.setattr(
        "app.services.crawl.batch_runtime.resolve_category_urls_from_sitemap",
        _fake_resolve_category_urls_from_sitemap,
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.crawl.batch_runtime.process_single_url",
        _fake_process_single_url,
    )

    await process_run(db_session, run.id)
    await db_session.refresh(run)

    assert resolved_inputs == [("example.com", "collections", 2, False)]
    assert processed_urls == [
        "https://example.com/collections/a",
        "https://example.com/collections/b",
    ]
    assert run.result_summary["url_count"] == 2
    assert run.result_summary["resolved_url_list"] == processed_urls

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_batch_run_defaults_bad_sitemap_max_urls(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "batch",
            "surface": "ecommerce_listing",
            "url": "https://example.com",
            "settings": {
                "sitemap_domain": "example.com",
                "sitemap_max_urls": "not-a-number",
            },
        },
    )
    resolved_inputs: list[int] = []

    async def _fake_resolve_category_urls_from_sitemap(
        domain: str,
        filter_keyword: str,
        max_urls: int,
        allow_homepage_fallback: bool = False,
    ) -> list[str]:
        del domain, filter_keyword, allow_homepage_fallback
        resolved_inputs.append(max_urls)
        return ["https://example.com/collections/a"]

    async def _fake_process_single_url(*args, **kwargs):
        del args, kwargs
        return URLProcessingResult(records=[], verdict="success")

    monkeypatch.setattr(
        "app.services.crawl.batch_runtime.resolve_category_urls_from_sitemap",
        _fake_resolve_category_urls_from_sitemap,
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.crawl.batch_runtime.process_single_url",
        _fake_process_single_url,
    )

    await process_run(db_session, run.id)

    assert resolved_inputs == [SITEMAP_DEFAULT_MAX_URLS]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_batch_run_marks_failed_when_sitemap_resolution_fails(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "batch",
            "surface": "ecommerce_listing",
            "url": "https://example.com",
            "settings": {
                "sitemap_domain": "example.com",
                "sitemap_filter_keyword": "collections",
            },
        },
    )

    async def _fake_resolve_category_urls_from_sitemap(
        domain: str,
        filter_keyword: str,
        max_urls: int,
        allow_homepage_fallback: bool = False,
    ) -> list[str]:
        del domain, filter_keyword, max_urls, allow_homepage_fallback
        raise ValueError(
            "Sitemap fetch failed: https://example.com/sitemap.xml returned HTTP 503"
        )

    monkeypatch.setattr(
        "app.services.crawl.batch_runtime.resolve_category_urls_from_sitemap",
        _fake_resolve_category_urls_from_sitemap,
        raising=False,
    )

    await process_run(db_session, run.id)
    await db_session.refresh(run)
    logs = (
        (
            await db_session.execute(
                select(CrawlLog.message).where(CrawlLog.run_id == run.id)
            )
        )
        .scalars()
        .all()
    )

    assert run.status == "failed"
    assert run.completed_at is not None
    assert (
        run.result_summary["error"]
        == "ValueError: Sitemap fetch failed: https://example.com/sitemap.xml returned HTTP 503"
    )
    assert logs == [
        "ValueError: Sitemap fetch failed: https://example.com/sitemap.xml returned HTTP 503"
    ]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_batch_run_enables_homepage_fallback_for_auto_surface(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "batch",
            "surface": "auto",
            "url": "https://example.com",
            "settings": {
                "sitemap_domain": "example.com",
            },
        },
    )
    resolved_flags: list[bool] = []

    async def _fake_resolve_category_urls_from_sitemap(
        domain: str,
        filter_keyword: str,
        max_urls: int,
        allow_homepage_fallback: bool = False,
    ) -> list[str]:
        del domain, filter_keyword, max_urls
        resolved_flags.append(allow_homepage_fallback)
        return ["https://example.com/women"]

    async def _fake_process_single_url(*args, **kwargs):
        del args, kwargs
        return URLProcessingResult(records=[], verdict="success")

    monkeypatch.setattr(
        "app.services.crawl.batch_runtime.resolve_category_urls_from_sitemap",
        _fake_resolve_category_urls_from_sitemap,
        raising=False,
    )
    monkeypatch.setattr(
        "app.services.crawl.batch_runtime.process_single_url",
        _fake_process_single_url,
    )

    await process_run(db_session, run.id)

    assert resolved_flags == [True]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_run_continues_after_sqlalchemy_url_error(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
    patch_settings,
) -> None:
    patch_settings(url_batch_concurrency=1)
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "batch",
            "surface": "ecommerce_detail",
            "settings": {
                "urls": [
                    "https://example.com/products/bad-widget",
                    "https://example.com/products/widget-prime",
                ],
            },
        },
    )

    async def _poisoned_process_single_url(*args, **kwargs):
        del args
        url = str(kwargs.get("url") or "")
        if "bad-widget" in url:
            raise PendingRollbackError("flush failed earlier")
        session = kwargs["session"]
        session.add(
            CrawlRecord(
                run_id=run.id,
                source_url=url,
                data={"title": "Widget Prime", "url": url},
                raw_data={},
                discovered_data={},
                source_trace={},
            )
        )
        await session.flush()
        return URLProcessingResult(
            records=[{"title": "Widget Prime", "url": url}],
            verdict="success",
            url_metrics={"record_count": 1},
        )

    monkeypatch.setattr(
        "app.services.crawl.batch_runtime.process_single_url",
        _poisoned_process_single_url,
    )

    await process_run(db_session, run.id)
    await db_session.refresh(run)
    rows, total = await get_run_records(db_session, run.id, 1, 20)

    assert run.status == "completed"
    assert run.result_summary["extraction_verdict"] == "partial"
    assert run.result_summary["url_verdicts"] == ["error", "success"]
    assert total == 1
    assert rows[0].data["title"] == "Widget Prime"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_run_continues_when_failure_log_persistence_fails(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "batch",
            "surface": "ecommerce_detail",
            "settings": {
                "urls": [
                    "https://example.com/products/bad-widget",
                    "https://example.com/products/widget-prime",
                ],
            },
        },
    )

    async def _failing_process_single_url(*args, **kwargs):
        del args
        url = str(kwargs.get("url") or "")
        if "bad-widget" in url:
            raise RuntimeError("extractor failed")
        return URLProcessingResult(
            records=[],
            verdict="success",
            url_metrics={"record_count": 0},
        )

    async def _failing_failure_log(*args, **kwargs):
        del args, kwargs
        raise PendingRollbackError("failure log flush failed")

    monkeypatch.setattr(
        "app.services.crawl.batch_runtime.process_single_url",
        _failing_process_single_url,
    )
    monkeypatch.setattr(
        "app.services.crawl.batch_runtime._persist_url_failure_log",
        _failing_failure_log,
    )

    await process_run(db_session, run.id)
    await db_session.refresh(run)

    assert run.status == "completed"
    assert run.result_summary["extraction_verdict"] == "partial"
    assert run.result_summary["url_verdicts"] == ["error", "success"]

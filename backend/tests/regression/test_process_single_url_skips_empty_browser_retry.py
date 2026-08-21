from __future__ import annotations

from .test_pipeline_core import *  # noqa: F403


@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_skips_empty_browser_retry_when_budget_low(
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
            "settings": {
                "respect_robots_txt": False,
                "url_timeout_seconds": 35,
            },
        },
    )
    acquire_calls: list[dict[str, object]] = []

    @_as_async
    def _fake_acquire(request: AcquisitionRequest) -> AcquisitionResult:
        acquire_calls.append(dict(request.acquisition_profile))
        if request.acquisition_profile.get("prefer_browser"):
            raise AssertionError("empty extraction browser retry should be skipped")
        return _fake_acquire_result(
            request,
            html=(
                "<html><body><div id='__next'></div>"
                "<script>window.__NEXT_DATA__={}</script></body></html>"
            ),
            method="curl_cffi",
        )

    @_as_async
    def _fake_run_adapter(*_args, **_kwargs):
        return None

    monkeypatch.setattr("app.services.pipeline.extraction_loop.acquire", _fake_acquire)
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.run_adapter", _fake_run_adapter
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.extract_records",
        lambda *args, **kwargs: [],
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop._remaining_url_budget_seconds",
        lambda _context: 29.0,
    )

    result = await process_single_url(db_session, run, run.url)
    logs = await get_run_logs(db_session, run.id)

    assert result.records == []
    assert len(acquire_calls) == 1
    assert any("Skipping empty-extraction browser retry" in log.message for log in logs)

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_blocks_before_acquire_when_robots_disallows(
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
            "settings": {"respect_robots_txt": True},
        },
    )

    @_as_async
    def _disallow(url: str, *, user_agent: str = "*") -> RobotsPolicyResult:
        del user_agent
        return RobotsPolicyResult(
            allowed=False,
            outcome="disallowed",
            robots_url="https://example.com/robots.txt",
        )

    @_as_async
    def _unexpected_acquire(request):
        raise AssertionError(f"acquire should not run for {request.url}")

    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.check_url_crawlability", _disallow
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.acquire", _unexpected_acquire
    )

    result = await process_single_url(db_session, run, run.url)
    logs = await get_run_logs(db_session, run.id)

    assert result.records == []
    assert result.verdict == "blocked"
    assert result.url_metrics["robots"]["allowed"] is False
    assert result.url_metrics["robots"]["outcome"] == "disallowed"
    assert [log.message for log in logs] == [
        "[ROBOTS] Blocked by robots.txt: https://example.com/private/widget-prime"
    ]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_prefetch_only_returns_metrics_without_persisting_records(
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
        return _fake_acquire_result(request)

    monkeypatch.setattr("app.services.pipeline.extraction_loop.acquire", _fake_acquire)

    result = await process_single_url(
        db_session,
        run,
        run.url,
        URLProcessingConfig(prefetch_only=True),
    )
    rows, total = await get_run_records(db_session, run.id, 1, 20)

    assert result.records == []
    assert result.verdict == "success"
    assert result.url_metrics["record_count"] == 0
    assert total == 0
    assert rows == []

@pytest.mark.asyncio
@pytest.mark.regression
async def test_post_extraction_challenge_shell_retries_real_chrome(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://www.nike.com/t/widget",
            "surface": "ecommerce_detail",
            "settings": {"respect_robots_txt": False},
        },
    )
    attempted_engines: list[str] = []
    hard_blocks: list[dict[str, object]] = []

    @_as_async
    def _fake_acquire(request: AcquisitionRequest) -> AcquisitionResult:
        forced_engine = str(
            request.acquisition_profile.get("forced_browser_engine") or "patchright"
        )
        attempted_engines.append(forced_engine)
        challenge = forced_engine == "patchright"
        return _fake_acquire_result(
            request,
            html=f"<html><body>{forced_engine}</body></html>",
            method="browser",
            blocked=False,
            browser_diagnostics={
                "browser_attempted": True,
                "browser_engine": forced_engine,
                "browser_outcome": "usable_content",
                "challenge_evidence": ["strong:captcha", "provider:akamai"]
                if challenge
                else [],
                "challenge_provider_hits": ["akamai"] if challenge else [],
            },
        )

    def _fake_extract_records(html: str, *_args, **_kwargs):
        if "real_chrome" not in html:
            return []
        return [
            {
                "title": "Nike Widget",
                "url": "https://www.nike.com/t/widget",
                "price": "$50",
            }
        ]

    @_as_async
    def _fake_note_host_hard_block(value: str | None, **kwargs):
        hard_blocks.append({"value": value, **kwargs})

    monkeypatch.setattr("app.services.pipeline.extraction_loop.acquire", _fake_acquire)
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.extract_records", _fake_extract_records
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.real_chrome_browser_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.note_host_hard_block",
        _fake_note_host_hard_block,
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.run_adapter", _no_adapter
    )

    result = await process_single_url(db_session, run, run.url)
    rows, total = await get_run_records(db_session, run.id, 1, 20)

    assert attempted_engines == ["patchright", "real_chrome"]
    assert hard_blocks[0]["method"] == "browser:patchright"
    assert result.verdict == "success"
    assert total == 1
    assert rows[0].data["title"] == "Nike Widget"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_post_extraction_detail_shell_escalates_real_chrome(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://www.wayfair.com/pdp/widget",
            "surface": "ecommerce_detail",
            "settings": {"respect_robots_txt": False},
        },
    )
    attempted_engines: list[str] = []

    @_as_async
    def _fake_acquire(request: AcquisitionRequest) -> AcquisitionResult:
        forced_engine = str(
            request.acquisition_profile.get("forced_browser_engine") or "patchright"
        )
        attempted_engines.append(forced_engine)
        return _fake_acquire_result(
            request,
            html=f"<html><body>{forced_engine}</body></html>",
            method="browser",
            blocked=False,
            browser_diagnostics={
                "browser_attempted": True,
                "browser_engine": forced_engine,
                "browser_outcome": "usable_content",
            },
        )

    def _fake_extract_records(
        html: str,
        *_args,
        **_kwargs,
    ) -> list[dict[str, object]]:
        if "real_chrome" not in html:
            return []
        return [
            {
                "title": "Wayfair Widget",
                "url": run.url,
                "price": "$50",
            }
        ]

    monkeypatch.setattr("app.services.pipeline.extraction_loop.acquire", _fake_acquire)
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.extract_records",
        _fake_extract_records,
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.real_chrome_browser_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.run_adapter", _no_adapter
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.infer_detail_failure_reason",
        lambda *_args, **_kwargs: "detail_shell",
    )

    result = await process_single_url(db_session, run, run.url)
    logs = await get_run_logs(db_session, run.id)

    assert attempted_engines == ["patchright", "real_chrome"]
    assert result.verdict == "success"
    assert result.records[0]["title"] == "Wayfair Widget"
    assert any(
        "Patchright detail rejected as detail_shell; escalating real Chrome for https://www.wayfair.com/pdp/widget"
        in log.message
        for log in logs
    )

@pytest.mark.asyncio
@pytest.mark.regression
async def test_post_extraction_identity_mismatch_escalates_real_chrome(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://www.mytheresa.com/int/en/women/valentino-garavani-loco-small-floral-linen-top-handle-bag-beige-p01155657",
            "surface": "ecommerce_detail",
            "settings": {"respect_robots_txt": False},
        },
    )
    attempted_engines: list[str] = []

    @_as_async
    def _fake_acquire(request: AcquisitionRequest) -> AcquisitionResult:
        forced_engine = str(
            request.acquisition_profile.get("forced_browser_engine") or "patchright"
        )
        attempted_engines.append(forced_engine)
        return _fake_acquire_result(
            request,
            html=f"<html><body>{forced_engine}</body></html>",
            method="browser",
            blocked=False,
            browser_diagnostics={
                "browser_attempted": True,
                "browser_engine": forced_engine,
                "browser_outcome": "usable_content",
            },
        )

    def _fake_extract_records(
        html: str,
        *_args,
        **_kwargs,
    ) -> list[dict[str, object]]:
        if "real_chrome" not in html:
            return []
        return [
            {
                "title": "Valentino Garavani Loco Small Floral Linen Top Handle Bag",
                "url": run.url,
                "source_url": run.url,
                "brand": "Valentino Garavani",
                "product_id": "p01155657",
                "price": "1000.00",
                "currency": "USD",
                "image_url": "https://img.example/bag.jpg",
                "description": "Valentino Garavani loco small floral linen top handle bag.",
            }
        ]

    monkeypatch.setattr("app.services.pipeline.extraction_loop.acquire", _fake_acquire)
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.extract_records",
        _fake_extract_records,
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.real_chrome_browser_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.run_adapter", _no_adapter
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.infer_detail_failure_reason",
        lambda *_args, **_kwargs: "detail_identity_mismatch",
    )

    result = await process_single_url(db_session, run, run.url)
    logs = await get_run_logs(db_session, run.id)

    assert attempted_engines == ["patchright", "real_chrome"]
    assert result.verdict == "success"
    assert result.records[0]["title"].startswith("Valentino Garavani")
    assert any(
        "Patchright detail rejected as detail_identity_mismatch; escalating real Chrome for "
        "https://www.mytheresa.com/int/en/women/valentino-garavani-loco-small-floral-linen-top-handle-bag-beige-p01155657"
        in log.message
        for log in logs
    )

@pytest.mark.asyncio
@pytest.mark.regression
async def test_usable_detail_with_active_provider_evidence_does_not_retry_real_chrome(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://www.nike.com/t/widget",
            "surface": "ecommerce_detail",
            "settings": {"respect_robots_txt": False},
        },
    )
    attempted_engines: list[str] = []

    @_as_async
    def _fake_acquire(request: AcquisitionRequest) -> AcquisitionResult:
        forced_engine = str(
            request.acquisition_profile.get("forced_browser_engine") or "patchright"
        )
        attempted_engines.append(forced_engine)
        return _fake_acquire_result(
            request,
            html="<html><body>Nike Widget</body></html>",
            method="browser",
            blocked=False,
            browser_diagnostics={
                "browser_attempted": True,
                "browser_engine": forced_engine,
                "browser_outcome": "usable_content",
                "challenge_evidence": ["active_provider:akamai"],
                "challenge_provider_hits": ["akamai"],
            },
        )

    monkeypatch.setattr("app.services.pipeline.extraction_loop.acquire", _fake_acquire)
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.extract_records",
        lambda *_args, **_kwargs: [
            {
                "title": "Nike Widget",
                "url": "https://www.nike.com/t/widget",
                "price": "$50",
            }
        ],
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.real_chrome_browser_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.run_adapter", _no_adapter
    )

    result = await process_single_url(db_session, run, run.url)

    assert attempted_engines == ["patchright"]
    assert result.verdict == "success"
    assert result.url_metrics["blocked"] is False
    assert result.url_metrics.get("failure_reason") is None

@pytest.mark.asyncio
@pytest.mark.regression
async def test_patchright_challenge_shell_updates_host_memory(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://www.nike.com/t/widget",
            "surface": "ecommerce_detail",
            "settings": {"respect_robots_txt": False},
        },
    )
    hard_blocks: list[dict[str, object]] = []

    @_as_async
    def _fake_acquire(request: AcquisitionRequest) -> AcquisitionResult:
        return _fake_acquire_result(
            request,
            html="<html><body>patchright</body></html>",
            method="browser",
            blocked=False,
            browser_diagnostics={
                "browser_attempted": True,
                "browser_engine": "patchright",
                "browser_outcome": "usable_content",
                "challenge_evidence": ["strong:captcha", "provider:akamai"],
                "challenge_provider_hits": ["akamai"],
            },
        )

    @_as_async
    def _fake_note_host_hard_block(value: str | None, **kwargs):
        hard_blocks.append({"value": value, **kwargs})

    monkeypatch.setattr("app.services.pipeline.extraction_loop.acquire", _fake_acquire)
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.extract_records",
        lambda *_args, **_kwargs: [],
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.real_chrome_browser_available",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.note_host_hard_block",
        _fake_note_host_hard_block,
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.run_adapter", _no_adapter
    )

    await process_single_url(db_session, run, run.url)

    assert hard_blocks
    assert hard_blocks[0]["method"] == "browser:patchright"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_runs_adapter_against_browser_artifact_fragments(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://www.belk.com/home/",
            "surface": "ecommerce_listing",
            "settings": {"respect_robots_txt": False, "max_records": 10},
        },
    )

    fragment = """
    <article class="product-tile">
      <a href="/p/polo-ralph-lauren-slim-straight-jeans/123.html">
        <span class="product-name">Slim Straight Jeans</span>
      </a>
      <span class="product-brand">Polo Ralph Lauren</span>
      <span class="price">$89.50</span>
    </article>
    """

    @_as_async
    def _fake_acquire(request):
        return _fake_acquire_result(
            request,
            html="<html><body><h1>Home</h1></body></html>",
            method="browser",
            artifacts={"rendered_listing_fragments": [fragment]},
        )

    @_as_async
    def _fake_run_adapter(url, html, surface):
        if "product-tile" not in html:
            return None
        return AdapterResult(
            records=[
                {
                    "title": "Slim Straight Jeans",
                    "brand": "Polo Ralph Lauren",
                    "price": "89.50",
                    "url": "https://www.belk.com/p/polo-ralph-lauren-slim-straight-jeans/123.html",
                    "_source": "belk_adapter",
                }
            ],
            source_type="belk_adapter",
            adapter_name="belk",
        )

    @_as_async
    def _no_selector_rules(*args, **kwargs):
        del args, kwargs
        return []

    def _fake_extract_records(*args, **kwargs):
        return list(kwargs.get("adapter_records") or [])

    @_as_async
    def _persist_artifacts(**kwargs):
        del kwargs
        return "artifacts/belk.html"

    monkeypatch.setattr("app.services.pipeline.extraction_loop.acquire", _fake_acquire)
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.run_adapter", _fake_run_adapter
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.load_domain_selector_rules",
        _no_selector_rules,
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.extract_records", _fake_extract_records
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.persist_acquisition_artifacts",
        _persist_artifacts,
    )

    result = await process_single_url(db_session, run, run.url)

    assert result.url_metrics["adapter_name"] == "belk"
    assert result.records[0]["brand"] == "Polo Ralph Lauren"

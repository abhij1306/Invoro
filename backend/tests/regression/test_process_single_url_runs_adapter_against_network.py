from __future__ import annotations

from .test_pipeline_core import *  # noqa: F403


@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_runs_adapter_against_network_payloads(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://www.belk.com/p/example-pants/3200645HC01000.html",
            "surface": "ecommerce_detail",
            "settings": {"respect_robots_txt": False},
        },
    )

    payload_body = {
        "utag_data": {
            "product_name": ["Example Pants"],
            "product_url": ["https://www.belk.com/p/example-pants/3200645HC01000.html"],
            "sku_id": ["0438651111111"],
            "sku_upc": ["0019783000001"],
        }
    }
    primary_html = "<html><body><h1>Example Pants</h1></body></html>"
    fragment = "<article>Example Pants supplemental evidence</article>"
    adapter_inputs: list[str] = []

    @_as_async
    def _fake_acquire(request):
        return _fake_acquire_result(
            request,
            html=primary_html,
            method="browser",
            artifacts={
                "full_rendered_html": primary_html,
                "rendered_listing_fragments": [fragment],
            },
            network_payloads=[
                {
                    "url": "https://www.belk.com/_next/payload",
                    "content_type": "text/x-component",
                    "body": payload_body,
                },
                {
                    "url": "https://www.belk.com/_next/payload-copy",
                    "content_type": "application/json",
                    "body": payload_body,
                },
            ],
        )

    @_as_async
    def _fake_run_adapter(url, html, surface):
        del url, surface
        adapter_inputs.append(html)
        if "utag_data" not in html:
            return None
        return AdapterResult(
            records=[
                {
                    "title": "Example Pants",
                    "url": "https://www.belk.com/p/example-pants/3200645HC01000.html",
                    "variants": [{"sku": "0438651111111", "barcode": "0019783000001"}],
                    "variant_count": 1,
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
    assert adapter_inputs == [
        primary_html,
        f"<html><body>{fragment}</body></html>",
        json.dumps(payload_body, ensure_ascii=True, separators=(",", ":")),
    ]
    assert result.records[0]["variants"] == [
        {"sku": "0438651111111", "barcode": "0019783000001"}
    ]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_skips_redundant_adapter_artifacts_when_main_html_sufficient(
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
      <a href="/p/unused/999.html"><span class="product-name">Unused</span></a>
      <span class="price">$9.99</span>
    </article>
    """
    adapter_calls = 0

    @_as_async
    def _fake_acquire(request):
        return _fake_acquire_result(
            request,
            html="<html><body>main product grid</body></html>",
            method="browser",
            artifacts={"rendered_listing_fragments": [fragment]},
            browser_diagnostics={"rendered_listing_fragment_count": 2},
        )

    @_as_async
    def _fake_run_adapter(url, html, surface):
        del url, surface
        nonlocal adapter_calls
        adapter_calls += 1
        assert "unused" not in html
        return AdapterResult(
            records=[
                {
                    "title": "Main One",
                    "price": "22.75",
                    "url": "https://www.belk.com/p/main-one/1.html",
                    "_source": "belk_adapter",
                },
                {
                    "title": "Main Two",
                    "price": "39.95",
                    "url": "https://www.belk.com/p/main-two/2.html",
                    "_source": "belk_adapter",
                },
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

    assert adapter_calls == 1
    assert [row["price"] for row in result.records] == ["22.75", "39.95"]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_prefers_richer_adapter_artifact_rows(
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

    @_as_async
    def _fake_acquire(request):
        return _fake_acquire_result(
            request,
            html="<html><body>partial product-tile</body></html>",
            method="browser",
            artifacts={"rendered_listing_fragments": ["rich product-tile"]},
        )

    @_as_async
    def _fake_run_adapter(url, html, surface):
        del url, surface
        if "rich product-tile" in html:
            records = [
                {
                    "title": "Rich One",
                    "brand": "Brand",
                    "url": "https://www.belk.com/p/1.html",
                },
                {
                    "title": "Rich Two",
                    "brand": "Brand",
                    "url": "https://www.belk.com/p/2.html",
                },
            ]
        elif "partial product-tile" in html:
            records = [
                {"title": "Partial One", "url": "https://www.belk.com/p/1.html"},
            ]
        else:
            return None
        return AdapterResult(
            records=records, source_type="belk_adapter", adapter_name="belk"
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

    assert [record["title"] for record in result.records] == ["Rich One", "Rich Two"]

@pytest.mark.regression
def test_url_processing_config_syncs_compatibility_fields_from_acquisition_plan() -> (
    None
):
    config = URLProcessingConfig.from_acquisition_plan(
        AcquisitionPlan(
            surface="job_listing",
            proxy_list=("http://proxy-1",),
            traversal_mode="paginate",
            max_pages=7,
            max_scrolls=3,
            max_records=11,
            sleep_ms=900,
        ),
        persist_logs=False,
    )

    assert config.proxy_list == ["http://proxy-1"]
    assert config.traversal_mode == "paginate"
    assert config.max_pages == 7
    assert config.max_scrolls == 3
    assert config.max_records == 11
    assert config.sleep_ms == 900
    assert config.persist_logs is False

@pytest.mark.regression
def test_resolved_url_processing_config_handles_none_plan_limits() -> None:
    config = URLProcessingConfig.from_acquisition_plan(
        AcquisitionPlan(
            surface="ecommerce_detail",
            max_pages=None,  # type: ignore[arg-type]
            max_scrolls=None,  # type: ignore[arg-type]
            max_records=None,  # type: ignore[arg-type]
            sleep_ms=None,  # type: ignore[arg-type]
        )
    )

    resolved = resolved_url_processing_config(
        config,
        surface="ecommerce_detail",
        proxy_list=[],
        traversal_mode=None,
        max_pages=4,
        max_scrolls=5,
        max_records=6,
        sleep_ms=7,
        update_run_state=True,
        persist_logs=True,
    )

    assert resolved.max_pages == 4
    assert resolved.max_scrolls == 5
    assert resolved.max_records == 6
    assert resolved.sleep_ms == 7

@pytest.mark.regression
def test_resolved_url_processing_config_preserves_explicit_zero_sleep_ms() -> None:
    config = URLProcessingConfig.from_acquisition_plan(
        AcquisitionPlan(
            surface="ecommerce_listing",
            sleep_ms=0,
        )
    )

    resolved = resolved_url_processing_config(
        config,
        surface="ecommerce_listing",
        proxy_list=[],
        traversal_mode=None,
        max_pages=4,
        max_scrolls=5,
        max_records=6,
        sleep_ms=25,
        update_run_state=True,
        persist_logs=True,
    )

    assert resolved.sleep_ms == 0

@pytest.mark.asyncio
@pytest.mark.regression
async def test_acquire_normalizes_retry_reason_aliases(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    @_as_async
    def _fake_fetch_page(url: str, **kwargs):
        captured["url"] = url
        captured.update(kwargs)
        return type(
            "_FetchResult",
            (),
            {
                "final_url": url,
                "html": "<html></html>",
                "method": "browser",
                "status_code": 200,
                "content_type": "text/html",
                "blocked": False,
                "headers": {},
            },
        )()

    monkeypatch.setattr(
        "app.services.acquisition.acquirer.fetch_page", _fake_fetch_page
    )

    await acquire(
        AcquisitionRequest(
            run_id=1,
            url="https://example.com/category/widgets",
            plan=AcquisitionPlan(
                surface="ecommerce_listing", traversal_mode="paginate"
            ),
            acquisition_profile={
                "prefer_browser": True,
                "retry_reason": "thin-listing retry",
            },
        )
    )

    assert captured["browser_reason"] == "thin-listing retry"
    assert captured["listing_recovery_mode"] == "thin_listing"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_marks_empty_listing_as_listing_detection_failed(
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
            html=_listing_html(),
            method="test",
            status_code=200,
        )

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

    result = await process_single_url(db_session, run, run.url)
    rows, total = await get_run_records(db_session, run.id, 1, 20)

    assert result.records == []
    assert result.verdict == "listing_detection_failed"
    assert result.url_metrics["record_count"] == 0
    assert total == 0
    assert rows == []

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_preserves_proxy_list_for_detail_surface(
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
                "proxy_enabled": True,
                "proxy_list": ["http://proxy-1"],
                "proxy_profile": {
                    "enabled": True,
                    "proxy_list": ["http://proxy-1"],
                },
            },
        },
    )
    captured_proxy_lists: list[list[str]] = []

    @_as_async
    def _fake_acquire(request):
        captured_proxy_lists.append(list(request.proxy_list))
        return AcquisitionResult(
            request=request,
            final_url=request.url,
            html=_detail_html(),
            method="test",
            status_code=200,
        )

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
        lambda *args, **kwargs: [{"title": "Widget Prime"}],
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

    assert captured_proxy_lists == [["http://proxy-1"]]
    assert result.verdict == "success"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_repairs_missing_proxy_list_from_run_settings_when_config_is_skinny(
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
                "proxy_enabled": True,
                "proxy_list": ["http://proxy-1"],
                "proxy_profile": {
                    "enabled": True,
                    "proxy_list": ["http://proxy-1"],
                },
            },
        },
    )
    captured_proxy_lists: list[list[str]] = []

    @_as_async
    def _fake_acquire(request):
        captured_proxy_lists.append(list(request.proxy_list))
        return AcquisitionResult(
            request=request,
            final_url=request.url,
            html=_detail_html(),
            method="test",
            status_code=200,
        )

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
        lambda *args, **kwargs: [{"title": "Widget Prime"}],
    )

    @_as_async
    def _persist_artifacts(**kwargs):
        del kwargs
        return "artifacts/widget-prime.html"

    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.persist_acquisition_artifacts",
        _persist_artifacts,
    )

    result = await process_single_url(
        db_session,
        run,
        run.url,
        URLProcessingConfig.from_acquisition_plan(
            AcquisitionPlan(surface="ecommerce_detail")
        ),
    )

    assert captured_proxy_lists == [["http://proxy-1"]]
    assert result.verdict == "success"

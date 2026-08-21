from __future__ import annotations

from .test_pipeline_core import *  # noqa: F403


@pytest.mark.asyncio
@pytest.mark.regression
async def test_direct_record_llm_fallback_does_not_replace_deterministic_records(
    db_session: AsyncSession,
    test_user,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://www.notre-shop.com/products/sneaker",
            "surface": "ecommerce_detail",
            "settings": {"llm_enabled": True},
        },
    )
    deterministic_records = [
        {
            "title": "Joe Freshgoods Abzorb 1890 Sneaker",
            "url": "https://www.notre-shop.com/products/sneaker",
            "price": "19500",
            "variants": [{"size": "10 M", "price": "19500"}],
            "_source": "shopify_adapter",
        }
    ]

    @_as_async
    def _unexpected_resolve_run_config(*args, **kwargs):
        del args, kwargs
        raise AssertionError("direct LLM must not replace deterministic records")

    @_as_async
    def _unexpected_extract_records(*args, **kwargs):
        del args, kwargs
        raise AssertionError("direct LLM must not run as primary extraction")

    rows = await apply_direct_record_llm_fallback(
        db_session,
        run=run,
        page_url=run.url,
        html=_detail_html(),
        records=deterministic_records,
        resolve_run_config_fn=_unexpected_resolve_run_config,
        extract_records_fn=_unexpected_extract_records,
    )

    assert rows == deterministic_records

@pytest.mark.asyncio
@pytest.mark.regression
async def test_direct_record_llm_fallback_does_not_create_primary_records(
    db_session: AsyncSession,
    test_user,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/products/widget",
            "surface": "ecommerce_detail",
            "settings": {"llm_enabled": True},
        },
    )

    @_as_async
    def _unexpected_resolve_run_config(*args, **kwargs):
        del args, kwargs
        raise AssertionError("direct LLM must not create primary records")

    @_as_async
    def _unexpected_extract_records(*args, **kwargs):
        del args, kwargs
        raise AssertionError("direct LLM must not run as primary extraction")

    rows = await apply_direct_record_llm_fallback(
        db_session,
        run=run,
        page_url=run.url,
        html=_detail_html(),
        records=[],
        resolve_run_config_fn=_unexpected_resolve_run_config,
        extract_records_fn=_unexpected_extract_records,
    )

    assert rows == []

@pytest.mark.asyncio
@pytest.mark.regression
async def test_direct_record_llm_fallback_backfills_missing_listing_fields(
    db_session: AsyncSession,
    test_user,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/products",
            "surface": "ecommerce_listing",
            "requested_fields": ["title", "price", "image_url"],
            "settings": {"llm_enabled": True},
        },
    )
    records = [{"title": "Widget", "price": "19.99", "url": "https://example.com/p/1"}]

    @_as_async
    def _resolve_run_config(*args, **kwargs):
        del args, kwargs
        return {"provider": "test"}

    @_as_async
    def _extract_records(*args, **kwargs):
        del args, kwargs
        return ([{"image_url": "https://example.com/widget.jpg"}], None)

    rows = await apply_direct_record_llm_fallback(
        db_session,
        run=run,
        page_url=run.url,
        html=_detail_html(),
        records=records,
        resolve_run_config_fn=_resolve_run_config,
        extract_records_fn=_extract_records,
    )

    assert rows[0]["title"] == "Widget"
    assert rows[0]["price"] == "19.99"
    assert rows[0]["image_url"] == "https://example.com/widget.jpg"

@pytest.mark.regression
def test_best_adapter_result_deduplicates_unsourced_records() -> None:
    result = best_adapter_result(
        [
            AdapterResult(
                records=[{"title": "Widget", "price": "$10"}],
                source_type="json",
                adapter_name="first",
            ),
            AdapterResult(
                records=[{"price": "$10", "title": "Widget"}],
                source_type="json",
                adapter_name="second",
            ),
        ]
    )

    assert result is not None
    assert result.records == [{"title": "Widget", "price": "$10"}]

@pytest.mark.regression
def test_empty_extraction_retry_skips_static_detail_price_html() -> None:
    request = AcquisitionRequest(
        run_id=1,
        url="https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
        plan=AcquisitionPlan(surface="ecommerce_detail"),
    )
    acquisition_result = AcquisitionResult(
        request=request,
        final_url=request.url,
        html="""
        <html>
          <body>
            <article class="product_page">
              <h1>A Light in the Attic</h1>
              <p class="price_color">£51.77</p>
            </article>
          </body>
        </html>
        """,
        method="curl_cffi",
        status_code=200,
    )

    decision = empty_extraction_browser_retry_decision(
        acquisition_result,
        [],
        surface="ecommerce_detail",
        requested_fields=[],
        selector_rules=[],
    )

    assert decision == {
        "should_retry": False,
        "reason": "static_detail_extractable",
    }

@pytest.mark.regression
def test_empty_detail_extraction_retry_skips_collection_seed() -> None:
    request = AcquisitionRequest(
        run_id=1,
        url="https://example.com/collections/widgets",
        plan=AcquisitionPlan(surface="ecommerce_detail"),
    )
    acquisition_result = AcquisitionResult(
        request=request,
        final_url=request.url,
        html="<html><body><h1>Widgets</h1></body></html>",
        method="curl_cffi",
        status_code=200,
    )

    decision = empty_extraction_browser_retry_decision(
        acquisition_result,
        [],
        surface="ecommerce_detail",
        requested_fields=[],
        selector_rules=[],
    )

    assert decision == {
        "should_retry": False,
        "reason": "non_detail_seed",
    }

@pytest.mark.regression
def test_empty_detail_extraction_retry_skips_non_retryable_http_status() -> None:
    request = AcquisitionRequest(
        run_id=1,
        url="https://example.com/products/missing-widget",
        plan=AcquisitionPlan(surface="ecommerce_detail"),
    )
    acquisition_result = AcquisitionResult(
        request=request,
        final_url=request.url,
        html="<html><body><h1>404</h1><p>Product not found.</p></body></html>",
        method="curl_cffi",
        status_code=404,
    )

    decision = empty_extraction_browser_retry_decision(
        acquisition_result,
        [],
        surface="ecommerce_detail",
        requested_fields=[],
        selector_rules=[],
    )

    assert decision == {
        "should_retry": False,
        "reason": "non_retryable_http_status",
        "status_code": 404,
    }

@pytest.mark.regression
def test_empty_detail_extraction_retries_retryable_http_status() -> None:
    request = AcquisitionRequest(
        run_id=1,
        url="https://example.com/products/pragmata-switch-2",
        plan=AcquisitionPlan(surface="ecommerce_detail"),
    )
    acquisition_result = AcquisitionResult(
        request=request,
        final_url=request.url,
        html=(
            "<html><body><h1>Pragmata</h1>"
            "<span data-testid='price'>$59.99</span></body></html>"
        ),
        method="curl_cffi",
        status_code=406,
    )

    decision = empty_extraction_browser_retry_decision(
        acquisition_result,
        [],
        surface="ecommerce_detail",
        requested_fields=[],
        selector_rules=[],
    )

    assert decision == {
        "should_retry": True,
        "reason": "retryable_http_status",
        "status_code": 406,
    }

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_marks_non_retryable_http_status_as_error(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/products/missing-widget",
            "surface": "ecommerce_detail",
            "settings": {"respect_robots_txt": False},
        },
    )
    acquire_calls: list[dict[str, object]] = []

    @_as_async
    def _fake_acquire(request: AcquisitionRequest) -> AcquisitionResult:
        acquire_calls.append(dict(request.acquisition_profile))
        if request.acquisition_profile.get("prefer_browser"):
            raise AssertionError(
                "browser retry should not run for non-retryable HTTP status"
            )
        return _fake_acquire_result(
            request,
            html="<html><body><h1>404</h1><p>Product not found.</p></body></html>",
            method="curl_cffi",
            status_code=404,
        )

    monkeypatch.setattr("app.services.pipeline.extraction_loop.acquire", _fake_acquire)
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.run_adapter", _no_adapter
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.extract_records",
        lambda *args, **kwargs: [],
    )

    result = await process_single_url(db_session, run, run.url)

    assert result.records == []
    assert result.verdict == "error"
    assert result.url_metrics["status_code"] == 404
    assert result.url_metrics["failure_reason"] == "non_retryable_http_status"
    assert len(acquire_calls) == 1

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_retries_406_empty_detail_with_browser(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://www.nintendo.com/us/store/products/pragmata-switch-2/",
            "surface": "ecommerce_detail",
            "settings": {"respect_robots_txt": False},
        },
    )
    acquire_calls: list[dict[str, object]] = []

    @_as_async
    def _fake_acquire(request: AcquisitionRequest) -> AcquisitionResult:
        acquire_calls.append(dict(request.acquisition_profile))
        if request.acquisition_profile.get("prefer_browser"):
            return _fake_acquire_result(
                request,
                html="<html><body><h1>Pragmata</h1><span>$59.99</span></body></html>",
                method="browser",
                status_code=200,
                browser_diagnostics={
                    "browser_attempted": True,
                    "browser_engine": "patchright",
                    "browser_outcome": "usable_content",
                },
            )
        return _fake_acquire_result(
            request,
            html=(
                "<html><body><h1>Pragmata</h1>"
                "<span data-testid='price'>$59.99</span></body></html>"
            ),
            method="curl_cffi",
            status_code=406,
        )

    def _fake_extract_records(html: str, *_args, **_kwargs):
        if "$59.99" in html and "data-testid" not in html:
            return [{"title": "Pragmata", "price": "59.99", "currency": "USD"}]
        return []

    monkeypatch.setattr("app.services.pipeline.extraction_loop.acquire", _fake_acquire)
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.run_adapter", _no_adapter
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.extract_records",
        _fake_extract_records,
    )

    result = await process_single_url(db_session, run, run.url)
    logs = await get_run_logs(db_session, run.id)

    assert len(acquire_calls) == 2
    assert acquire_calls[1]["prefer_browser"] is True
    assert result.verdict == "success"
    assert result.records == [
        {"title": "Pragmata", "price": "59.99", "currency": "USD"}
    ]
    assert any(
        "No records via curl_cffi; retrying browser render" in log.message
        for log in logs
    )

@pytest.mark.regression
def test_low_quality_detail_retry_targets_real_non_browser_fetches() -> None:
    request = AcquisitionRequest(
        run_id=1,
        url="https://example.com/products/widget-prime",
        plan=AcquisitionPlan(surface="ecommerce_detail"),
    )
    acquisition_result = AcquisitionResult(
        request=request,
        final_url=request.url,
        html="""
        <html>
          <head>
            <script>window.__NEXT_DATA__ = {"props":{"pageProps":{"product":{"id":"123"}}}};</script>
          </head>
          <body>
            <div id="__next"></div>
            <noscript>Please enable JavaScript to continue.</noscript>
          </body>
        </html>
        """,
        method="curl_cffi",
        status_code=200,
    )

    decision = low_quality_extraction_browser_retry_decision(
        acquisition_result,
        [{"title": "Widget Prime"}],
        surface="ecommerce_detail",
        requested_fields=[],
    )

    assert decision["should_retry"] is True
    assert "price" in decision["missing_fields"]

    acquisition_result.method = "test"
    assert low_quality_extraction_browser_retry_decision(
        acquisition_result,
        [{"title": "Widget Prime"}],
        surface="ecommerce_detail",
        requested_fields=[],
    ) == {"should_retry": False, "reason": "method_not_retryable"}

@pytest.mark.regression
def test_low_quality_detail_retry_skips_when_limited_canonical_fields_complete() -> (
    None
):
    request = AcquisitionRequest(
        run_id=1,
        url="https://example.com/products/widget-prime",
        plan=AcquisitionPlan(surface="ecommerce_detail"),
    )
    acquisition_result = AcquisitionResult(
        request=request,
        final_url=request.url,
        html=_detail_html(),
        method="curl_cffi",
        status_code=200,
    )

    decision = low_quality_extraction_browser_retry_decision(
        acquisition_result,
        [
            {
                "title": "Widget Prime",
                "price": "19.99",
                "image_url": "https://example.com/widget.jpg",
            }
        ],
        surface="ecommerce_detail",
        requested_fields=[],
    )

    assert decision == {
        "should_retry": False,
        "reason": "repair_fields_complete",
    }

@pytest.mark.asyncio
@pytest.mark.regression
async def test_missing_repair_fields_uses_default_ecommerce_targets(
    db_session: AsyncSession,
    test_user,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/products/widget-prime",
            "surface": "ecommerce_detail",
            "settings": {},
        },
    )
    context = URLProcessingContext(
        session=db_session,
        run=run,
        url=run.url,
        config=URLProcessingConfig(),
        url_timeout_seconds=30.0,
        started_at_monotonic=0.0,
        requested_fields=list(run.requested_fields or []),
        surface=run.surface,
    )

    missing = records_missing_repair_fields(
        surface=context.surface,
        requested_fields=list(context.requested_fields),
        records=[{"title": "Widget Prime", "price": "19.99"}],
    )

    assert "price" not in missing
    assert missing == ["image_url"]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_process_single_url_skips_low_quality_browser_retry_when_budget_low(
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
                "url_timeout_seconds": 5,
            },
        },
    )
    acquire_calls: list[dict[str, object]] = []

    @_as_async
    def _fake_acquire(request: AcquisitionRequest) -> AcquisitionResult:
        acquire_calls.append(dict(request.acquisition_profile))
        return _fake_acquire_result(
            request,
            html="""
            <html>
              <head>
                <script>window.__NEXT_DATA__ = {"props":{"pageProps":{"product":{"id":"123"}}}};</script>
              </head>
              <body>
                <div id="__next"></div>
                <noscript>Please enable JavaScript to continue.</noscript>
              </body>
            </html>
            """,
            method="curl_cffi",
        )

    @_as_async
    def _fake_run_adapter(*_args, **_kwargs):
        return None

    def _fake_extract_records(*_args, **_kwargs):
        return [{"title": "Widget Prime"}]

    monkeypatch.setattr("app.services.pipeline.extraction_loop.acquire", _fake_acquire)
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.run_adapter", _fake_run_adapter
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.extract_records", _fake_extract_records
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop._remaining_url_budget_seconds",
        lambda _context: 4.5,
    )

    result = await process_single_url(db_session, run, run.url)
    logs = await get_run_logs(db_session, run.id)

    assert result.records
    assert len(acquire_calls) == 1
    assert any("Skipping low-quality browser retry" in log.message for log in logs)

@pytest.mark.asyncio
@pytest.mark.regression
async def test_low_quality_browser_retry_timeout_preserves_http_record(
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
    acquire_calls: list[dict[str, object]] = []

    @_as_async
    def _fake_acquire(request: AcquisitionRequest) -> AcquisitionResult:
        acquire_calls.append(dict(request.acquisition_profile))
        if request.acquisition_profile.get("prefer_browser"):
            raise TimeoutError(
                "Browser navigation stage exceeded timeout_seconds=45.00"
            )
        return _fake_acquire_result(
            request,
            html="""
            <html>
              <head>
                <script>window.__NEXT_DATA__ = {"props":{"pageProps":{"product":{"id":"123"}}}};</script>
              </head>
              <body>
                <div id="__next"></div>
                <noscript>Please enable JavaScript to continue.</noscript>
              </body>
            </html>
            """,
            method="curl_cffi",
        )

    monkeypatch.setattr("app.services.pipeline.extraction_loop.acquire", _fake_acquire)
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.run_adapter", _no_adapter
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.extract_records",
        lambda *args, **kwargs: [{"title": "Widget Prime"}],
    )

    result = await process_single_url(db_session, run, run.url)
    logs = await get_run_logs(db_session, run.id)

    assert result.records == [{"title": "Widget Prime"}]
    assert len(acquire_calls) == 2
    assert any("Browser retry failed" in log.message for log in logs)

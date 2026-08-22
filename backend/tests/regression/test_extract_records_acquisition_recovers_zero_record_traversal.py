from __future__ import annotations

from ._pipeline_core_support import _as_async, _no_adapter  # fmt: skip
import pytest
from app.services.acquisition.acquirer import AcquisitionRequest, AcquisitionResult  # fmt: skip
from app.services.acquisition_plan import AcquisitionPlan  # fmt: skip
from app.services.crawl.crud import create_crawl_run  # fmt: skip
from app.services.pipeline.extraction_loop import process_single_url  # fmt: skip
from sqlalchemy.ext.asyncio import AsyncSession  # fmt: skip


@pytest.mark.asyncio
@pytest.mark.regression
async def test_extract_records_for_acquisition_recovers_from_zero_record_traversal_using_full_rendered_html(
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
    acquisition = AcquisitionResult(
        request=AcquisitionRequest(
            run_id=run.id,
            url=run.url,
            plan=AcquisitionPlan(surface="ecommerce_listing"),
        ),
        final_url=run.url,
        html="<html><body>traversal fragment</body></html>",
        method="browser",
        status_code=200,
        artifacts={
            "full_rendered_html": "<html><body>full rendered listing</body></html>"
        },
        browser_diagnostics={
            "browser_attempted": True,
            "requested_traversal_mode": "paginate",
            "selected_traversal_mode": "paginate",
            "traversal_activated": True,
            "pages_advanced": 1,
            "traversal_progress_events": 1,
            "traversal_stop_reason": "paginate_no_progress",
        },
    )

    @_as_async
    def _no_selector_rules(*args, **kwargs):
        del args, kwargs
        return []

    @_as_async
    def _fake_acquire(request):
        del request
        return acquisition

    def _extract_records(html, *args, **kwargs):
        del args, kwargs
        if "full rendered listing" in html:
            return [
                {
                    "title": "Widget Prime",
                    "url": "https://example.com/products/widget-prime",
                }
            ]
        return []

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
        "app.services.pipeline.extraction_loop.extract_records", _extract_records
    )
    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.persist_acquisition_artifacts",
        _persist_artifacts,
    )

    result = await process_single_url(db_session, run, run.url)

    assert result.records == [
        {"title": "Widget Prime", "url": "https://example.com/products/widget-prime"}
    ]
    assert acquisition.html == "<html><body>full rendered listing</body></html>"
    assert (
        acquisition.artifacts["traversal_composed_html"]
        == "<html><body>traversal fragment</body></html>"
    )
    assert result.url_metrics["traversal_fallback_used"] is True
    assert result.url_metrics["traversal_fallback_recovered"] is True
    assert result.url_metrics["traversal_fallback_record_count"] == 1

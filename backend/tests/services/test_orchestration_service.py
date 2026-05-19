from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crawl_run import CrawlRecord, CrawlRun
from app.models.orchestration import OrchestrationStepRun
from app.models.user import User
from app.services import orchestration_service

pytestmark = pytest.mark.asyncio


async def get_workflow_steps_by_id(
    db_session: AsyncSession,
    workflow_id: int,
) -> dict[str, OrchestrationStepRun]:
    return {
        step.step_id: step
        for step in await orchestration_service.workflow_steps(db_session, workflow_id)
    }


async def test_orchestration_sequences_listing_detail_and_promotes_monitor(
    db_session: AsyncSession,
    test_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_dispatch = AsyncMock(side_effect=lambda session, run: run)
    monkeypatch.setattr(orchestration_service, "dispatch_run", mock_dispatch)
    project = await orchestration_service.create_project(
        db_session,
        user=test_user,
        payload={
            "name": "Example.com jeans watch",
            "competitors": ["example.com"],
            "category": "jeans",
            "tracked_fields": ["price", "was_price", "availability"],
        },
    )

    workflow = await orchestration_service.create_workflow(
        db_session,
        user=test_user,
        payload={
            "template_id": "competitive_pricing_snapshot",
            "project_id": project.id,
            "label": "Ajio jeans",
            "intent_inputs": {
                "listing_url": "https://example.com/jeans",
                "category": "jeans",
                "fields": ["price", "was_price", "availability"],
            },
            "advanced_overrides": {"max_items_detail": 10},
        },
    )
    assert mock_dispatch.call_count == 1
    steps = await get_workflow_steps_by_id(db_session, workflow.id)
    listing_step = steps["listing_run"]
    assert listing_step.run_id is not None
    listing_run = await db_session.get(CrawlRun, listing_step.run_id)
    assert listing_run is not None
    assert mock_dispatch.call_args_list[0].args[1].url == listing_run.url
    listing_run.set_status("running")
    listing_run.set_status("completed")
    db_session.add(
        CrawlRecord(
            run_id=listing_run.id,
            source_url="https://example.com/jeans",
            url_identity_key="listing-1",
            data={"url": "https://example.com/p/1", "title": "Slim jeans"},
            raw_data={},
            discovered_data={},
            source_trace={},
        )
    )
    await db_session.commit()

    workflow = await orchestration_service.get_workflow(
        db_session,
        workflow_id=workflow.id,
        user=test_user,
    )
    assert mock_dispatch.call_count == 2
    steps = await get_workflow_steps_by_id(db_session, workflow.id)
    detail_step = steps["detail_run"]
    assert workflow.status == "running"
    assert detail_step.run_id is not None
    detail_run = await db_session.get(CrawlRun, detail_step.run_id)
    assert detail_run is not None
    assert mock_dispatch.call_args_list[1].args[1].url == detail_run.url
    detail_run.set_status("running")
    detail_run.set_status("completed")
    db_session.add(
        CrawlRecord(
            run_id=detail_run.id,
            source_url="https://example.com/p/1",
            url_identity_key="detail-1",
            data={
                "title": "Slim jeans",
                "brand": "Demo",
                "price": "1299",
                "was_price": "1599",
                "currency": "INR",
                "availability": "in_stock",
            },
            raw_data={},
            discovered_data={},
            source_trace={},
        )
    )
    await db_session.commit()

    workflow = await orchestration_service.get_workflow(
        db_session,
        workflow_id=workflow.id,
        user=test_user,
    )
    assert workflow.status == "completed"
    comparison = await orchestration_service.price_comparison(
        db_session,
        workflow_id=workflow.id,
        user=test_user,
    )
    assert comparison["detail_run_id"] == detail_run.id
    rows = comparison["rows"]
    assert isinstance(rows, list)
    assert len(rows) == 1
    row = rows[0]
    assert isinstance(row, dict)
    assert set(row) == {
        "record_id",
        "run_id",
        "product",
        "brand",
        "domain",
        "price",
        "was_price",
        "currency",
        "availability",
        "source_url",
    }
    typed_row = row
    assert typed_row["product"] == "Slim jeans"
    assert typed_row["brand"] == "Demo"
    assert typed_row["currency"] == "INR"
    assert typed_row["availability"] == "in_stock"
    assert typed_row["was_price"] == "1599"
    assert typed_row["source_url"] == "https://example.com/p/1"
    assert typed_row["price"] == "1299"
    workflow, monitor_id, url_count, tracked_fields = await orchestration_service.promote_workflow_to_monitor(
        db_session,
        workflow_id=workflow.id,
        user=test_user,
        payload={"schedule_interval_hours": 24, "retention_days": 30},
    )
    assert workflow.monitor_id == monitor_id
    assert url_count == 1
    assert tracked_fields == ["price", "was_price", "availability"]


async def test_orchestration_detail_handoff_keeps_urls_on_listing_seed_domain(
    db_session: AsyncSession,
    test_user: User,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    mock_dispatch = AsyncMock(side_effect=lambda session, run: run)
    monkeypatch.setattr(orchestration_service, "dispatch_run", mock_dispatch)
    project = await orchestration_service.create_project(
        db_session,
        user=test_user,
        payload={
            "name": "Myntra jeans watch",
            "competitors": [],
            "category": "jeans",
            "tracked_fields": ["price", "availability"],
        },
    )
    workflow = await orchestration_service.create_workflow(
        db_session,
        user=test_user,
        payload={
            "template_id": "competitive_pricing_snapshot",
            "project_id": project.id,
            "label": "Myntra jeans",
            "intent_inputs": {
                "listing_url": "https://www.myntra.com/men-jeans",
                "fields": ["price", "availability"],
            },
        },
    )
    assert mock_dispatch.call_count == 1
    steps = await get_workflow_steps_by_id(db_session, workflow.id)
    listing_step = steps["listing_run"]
    listing_run = await db_session.get(CrawlRun, listing_step.run_id)
    assert listing_run is not None
    assert listing_run.url == "https://www.myntra.com/men-jeans"
    listing_run.set_status("running")
    listing_run.set_status("completed")
    db_session.add_all(
        [
            CrawlRecord(
                run_id=listing_run.id,
                source_url="https://www.myntra.com/men-jeans",
                url_identity_key="off-domain",
                data={
                    "url": "https://random.example/products/bad",
                    "title": "Bad external row",
                },
                raw_data={},
                discovered_data={},
                source_trace={},
            ),
            CrawlRecord(
                run_id=listing_run.id,
                source_url="https://www.myntra.com/men-jeans",
                url_identity_key="relative-product",
                data={
                    "url": "/jeans/demo/demo-slim-jeans/12345/buy",
                    "title": "Demo slim jeans",
                },
                raw_data={},
                discovered_data={},
                source_trace={},
            ),
        ]
    )
    await db_session.commit()

    workflow = await orchestration_service.get_workflow(
        db_session,
        workflow_id=workflow.id,
        user=test_user,
    )
    assert mock_dispatch.call_count == 2
    steps = await get_workflow_steps_by_id(db_session, workflow.id)
    detail_step = steps["detail_run"]
    assert workflow.status == "running"
    assert detail_step.inputs["seeds"] == [
        "https://www.myntra.com/jeans/demo/demo-slim-jeans/12345/buy"
    ]
    assert mock_dispatch.call_args_list[1].args[1].url == "https://www.myntra.com/jeans/demo/demo-slim-jeans/12345/buy"

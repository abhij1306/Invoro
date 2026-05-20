from __future__ import annotations

from datetime import timedelta

import pytest
from httpx import ASGITransport, AsyncClient
from app.core.dependencies import get_current_user, get_db
from app.main import app
from app.models.crawl_run import CrawlRun
from app.services.acquisition.acquirer import AcquisitionResult
from app.services.crawl.batch_runtime import process_run
from app.services.crawl.crud import create_crawl_run
from app.services.monitor_change_detection import ensure_monitor_change_detection_registered
from app.services.monitor_scheduler_service import MonitorSchedulerService
from app.services.monitor_service import create_monitor, utcnow
from app.services.pipeline import run_complete_callbacks


def _detail_html(*, title: str, price: str, availability: str) -> str:
    return f"""
    <html>
      <head>
        <script type="application/ld+json">
        {{
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "{title}",
          "description": "Deterministic monitor fixture",
          "sku": "W-100",
          "offers": {{"price": "{price}", "availability": "{availability}"}}
        }}
        </script>
      </head>
      <body><h1>{title}</h1></body>
    </html>
    """


class _ExistingSessionLocal:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):
        return False


@pytest.fixture
async def monitors_api_client(db_session, test_user):
    async def _override_db():
        yield db_session

    async def _override_user():
        return test_user

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_monitor_api_end_to_end_with_monitor_form_settings(
    monitors_api_client: AsyncClient,
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    url = "https://dummy-monitor.example/products/widget-prime"
    html_by_url = {
        url: _detail_html(
            title="Widget Prime",
            price="19.99",
            availability="InStock",
        )
    }
    created_run_ids: list[int] = []

    monkeypatch.setattr(run_complete_callbacks, "_run_complete_callbacks", {})
    ensure_monitor_change_detection_registered()
    monkeypatch.setattr(
        "app.services.monitor_change_detection.SessionLocal",
        lambda: _ExistingSessionLocal(db_session),
    )

    async def _allow(url_value: str, *, user_agent: str = "*"):
        del user_agent
        return type(
            "RobotsResult",
            (),
            {
                "allowed": True,
                "outcome": "allowed",
                "robots_url": f"{url_value.rstrip('/')}/robots.txt",
                "error": None,
            },
        )()

    async def _fake_acquire(request):
        return AcquisitionResult(
            request=request,
            final_url=request.url,
            html=html_by_url[request.url],
            method="test",
            status_code=200,
        )

    async def _noop_prewarm() -> None:
        return None

    async def _inline_create_and_process(session, user_id: int, payload: dict):
        effective_payload = dict(payload)
        settings = dict(effective_payload.get("settings") or {})
        settings["respect_robots_txt"] = False
        effective_payload["settings"] = settings
        run = await create_crawl_run(session, user_id, effective_payload)
        await process_run(session, run.id)
        await session.refresh(run)
        created_run_ids.append(int(run.id))
        return run

    monkeypatch.setattr(
        "app.services.pipeline.extraction_loop.check_url_crawlability",
        _allow,
    )
    monkeypatch.setattr("app.services.pipeline.extraction_loop.acquire", _fake_acquire)
    monkeypatch.setattr("app.services.crawl.batch_runtime._prewarm_browser_pool", _noop_prewarm)
    monkeypatch.setattr(
        "app.services.monitor_scheduler_service.create_crawl_run_from_payload",
        _inline_create_and_process,
    )

    create_payload = {
        "name": "Widget Watch",
        "urls": [url],
        "surface": "ecommerce_detail",
        "tracked_fields": ["price", "availability"],
        "schedule_interval_hours": 48,
        "priority": "priority",
        "retention_days": 7,
        "requested_fields": ["title", "price", "availability"],
        "settings": {
            "skip_head_check": False,
            "proxy_enabled": True,
            "fetch_profile": {
                "js_mode": "enabled",
                "extraction_source": "rendered_dom",
            },
        },
    }

    create_response = await monitors_api_client.post("/api/monitors", json=create_payload)
    assert create_response.status_code == 201
    monitor = create_response.json()
    monitor_id = monitor["id"]
    next_run_at_before = monitor["next_run_at"]
    assert monitor["tracked_fields"] == ["price", "availability"]
    assert monitor["priority"] == "priority"
    assert monitor["retention_days"] == 7
    assert monitor["settings"] == {
        "skip_head_check": False,
        "proxy_enabled": True,
        "fetch_profile": {
            "js_mode": "enabled",
            "extraction_source": "rendered_dom",
        },
    }

    first_run_response = await monitors_api_client.post(f"/api/monitors/{monitor_id}/run/now")
    assert first_run_response.status_code == 200
    first_run_payload = first_run_response.json()
    assert first_run_payload["url_count"] == 1
    assert len(first_run_payload["run_ids"]) == 1
    assert created_run_ids == first_run_payload["run_ids"]

    persisted_run = await db_session.get(CrawlRun, first_run_payload["run_id"])
    assert persisted_run is not None
    assert persisted_run.status == "completed"
    assert persisted_run.settings["monitor_id"] == monitor_id
    assert persisted_run.settings["proxy_enabled"] is True
    assert persisted_run.settings["fetch_profile"]["js_mode"] == "enabled"
    assert persisted_run.settings["fetch_profile"]["extraction_source"] == "rendered_dom"
    assert persisted_run.requested_fields == ["title", "price", "availability"]

    monitor_after_first_run = await monitors_api_client.get(f"/api/monitors/{monitor_id}")
    assert monitor_after_first_run.status_code == 200
    assert monitor_after_first_run.json()["next_run_at"] == next_run_at_before

    first_snapshot_response = await monitors_api_client.get(
        f"/api/monitors/{monitor_id}/snapshot/current"
    )
    assert first_snapshot_response.status_code == 200
    first_snapshot = first_snapshot_response.json()
    assert len(first_snapshot) == 1
    assert first_snapshot[0]["field_values"] == {
        "price": "19.99",
        "availability": "in_stock",
    }

    first_events_response = await monitors_api_client.get(f"/api/monitors/{monitor_id}/events")
    assert first_events_response.status_code == 200
    first_events_payload = first_events_response.json()
    assert first_events_payload["total"] == 1
    assert first_events_payload["items"][0]["event_type"] == "record_new"

    unread_before_change = await monitors_api_client.get("/api/notifications/unread-count")
    assert unread_before_change.status_code == 200
    assert unread_before_change.json()["count"] == 0

    html_by_url[url] = _detail_html(
        title="Widget Prime",
        price="17.49",
        availability="OutOfStock",
    )

    second_run_response = await monitors_api_client.post(f"/api/monitors/{monitor_id}/run/now")
    assert second_run_response.status_code == 200
    second_run_id = second_run_response.json()["run_id"]
    second_run = await db_session.get(CrawlRun, second_run_id)
    assert second_run is not None
    assert second_run.status == "completed"
    assert second_run.result_summary["monitor_change_count"] == 2

    second_snapshot_response = await monitors_api_client.get(
        f"/api/monitors/{monitor_id}/snapshot/current"
    )
    assert second_snapshot_response.status_code == 200
    second_snapshot = second_snapshot_response.json()
    assert second_snapshot[0]["field_values"] == {
        "price": "17.49",
        "availability": "out_of_stock",
    }

    history_response = await monitors_api_client.get(f"/api/monitors/{monitor_id}/history")
    assert history_response.status_code == 200
    history_payload = history_response.json()
    assert history_payload["total"] == 2
    assert history_payload["items"][0]["change_count"] == 2

    second_events_response = await monitors_api_client.get(f"/api/monitors/{monitor_id}/events")
    assert second_events_response.status_code == 200
    second_events_payload = second_events_response.json()
    changed_fields = {
        item["field_name"]
        for item in second_events_payload["items"]
        if item["event_type"] == "field_changed"
    }
    assert changed_fields == {"price", "availability"}

    notifications_response = await monitors_api_client.get("/api/notifications")
    assert notifications_response.status_code == 200
    notifications = notifications_response.json()
    assert len(notifications) == 1
    assert notifications[0]["event_count"] == 2

    mark_read_response = await monitors_api_client.post(
        f"/api/notifications/monitors/{monitor_id}/read"
    )
    assert mark_read_response.status_code == 200
    assert mark_read_response.json()["updated"] == 1

    unread_after_read = await monitors_api_client.get("/api/notifications/unread-count")
    assert unread_after_read.status_code == 200
    assert unread_after_read.json()["count"] == 0

    update_response = await monitors_api_client.patch(
        f"/api/monitors/{monitor_id}",
        json={
            "schedule_interval_hours": 72,
            "priority": "on_demand",
            "retention_days": 10,
            "status": "paused",
            "settings": {
                "skip_head_check": True,
                "proxy_enabled": False,
                "fetch_profile": {
                    "js_mode": "disabled",
                    "extraction_source": "raw_html",
                },
            },
        },
    )
    assert update_response.status_code == 200
    updated_monitor = update_response.json()
    assert updated_monitor["status"] == "paused"
    assert updated_monitor["priority"] == "on_demand"
    assert updated_monitor["retention_days"] == 10
    assert updated_monitor["settings"] == {
        "skip_head_check": True,
        "proxy_enabled": False,
        "fetch_profile": {
            "js_mode": "disabled",
            "extraction_source": "raw_html",
        },
    }
    assert updated_monitor["next_run_at"] != next_run_at_before

    paused_run_now = await monitors_api_client.post(f"/api/monitors/{monitor_id}/run/now")
    assert paused_run_now.status_code == 400
    assert paused_run_now.json()["detail"] == "Monitor is paused — resume it first"

    resume_response = await monitors_api_client.patch(
        f"/api/monitors/{monitor_id}",
        json={"status": "active"},
    )
    assert resume_response.status_code == 200
    assert resume_response.json()["status"] == "active"

    archive_response = await monitors_api_client.delete(f"/api/monitors/{monitor_id}")
    assert archive_response.status_code == 204

    deleted_get = await monitors_api_client.get(f"/api/monitors/{monitor_id}")
    assert deleted_get.status_code == 404
    assert deleted_get.json()["detail"] == "Monitor not found"

    archived_run_now = await monitors_api_client.post(f"/api/monitors/{monitor_id}/run/now")
    assert archived_run_now.status_code == 404
    assert archived_run_now.json()["detail"] == "Monitor not found"


@pytest.mark.asyncio
async def test_monitor_scheduler_respects_skip_head_check_setting(
    db_session,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = MonitorSchedulerService()
    dispatch_calls: list[list[str]] = []
    head_checks: list[str] = []

    monitor = await create_monitor(
        db_session,
        user=test_user,
        payload={
            "name": "Scheduled Widget Watch",
            "urls": ["https://dummy-monitor.example/products/widget-prime"],
            "surface": "ecommerce_detail",
            "tracked_fields": ["price"],
            "schedule_interval_hours": 24,
            "priority": "background",
            "retention_days": 7,
            "settings": {"skip_head_check": False},
        },
    )
    monitor.next_run_at = utcnow() - timedelta(hours=1)
    await db_session.commit()

    monkeypatch.setattr(
        "app.services.monitor_scheduler_service.SessionLocal",
        lambda: _ExistingSessionLocal(db_session),
    )

    async def _pre_check_false(url: str, state) -> bool:
        del state
        head_checks.append(url)
        return False

    async def _dispatch_capture(session, user_id: int, payload: dict):
        del session, user_id
        dispatch_calls.append(list(payload["urls"]))
        return type("Run", (), {"id": 1})()

    monkeypatch.setattr(service, "pre_check_url", _pre_check_false)
    monkeypatch.setattr(
        "app.services.monitor_scheduler_service.create_crawl_run_from_payload",
        _dispatch_capture,
    )

    await service.check_due_jobs()
    await db_session.refresh(monitor)
    assert head_checks == ["https://dummy-monitor.example/products/widget-prime"]
    assert dispatch_calls == []

    monitor.next_run_at = utcnow() - timedelta(hours=1)
    monitor.settings = {"skip_head_check": True}
    await db_session.commit()

    await service.check_due_jobs()
    await db_session.refresh(monitor)
    assert dispatch_calls == [["https://dummy-monitor.example/products/widget-prime"]]

from __future__ import annotations

import pytest
import httpx
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.dependencies import get_current_user, get_db
from app.core.public_auth import hash_api_key
from app.main import app
from app.models.api_key import ApiKey
from app.models.monitor import MonitorEvent, MonitorJob, MonitorWebhookDelivery
from app.mcp.alert_server import AlertMCPServer
from app.schemas.alert import AlertCreate
from app.services.config.monitor_settings import (
    MONITOR_EVENT_FIELD_CHANGED,
    MONITOR_PRIORITY_BACKGROUND,
    MONITOR_STATUS_ACTIVE,
    SKIP_HEAD_CHECK_KEY,
    WEBHOOK_STATUS_SENT,
)
from app.services.monitor_condition import condition_matches, validate_condition
from app.services.monitor_service import utcnow
from app.services.monitor_webhook_service import dispatch_alert_webhooks
from app.services.alert_service import alert_response, create_alert, list_alerts


class _Response:
    status_code = 204


class _HttpClient:
    def __init__(self, *args, **kwargs):
        self.posts: list[dict] = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, *, json):
        self.posts.append({"url": url, "json": json})
        return _Response()


class _FailingHttpClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, *, json):
        del json
        request = httpx.Request("POST", url)
        raise httpx.RequestError("network down", request=request)


class _BuggyHttpClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, url, *, json):
        del url, json
        raise ValueError("boom")


@pytest.fixture
async def public_client(db_session, test_user):
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


def test_alert_condition_evaluator_is_sandboxed() -> None:
    assert condition_matches(
        'price < 150 AND availability == "in_stock"',
        {"price": "129.99", "availability": "in_stock"},
    )
    assert not condition_matches("price >= 150", {"price": "129.99"})
    with pytest.raises(ValueError):
        validate_condition("__import__('os').system('whoami')")
    with pytest.raises(ValueError):
        validate_condition("sku == ABC")
    with pytest.raises(ValueError):
        validate_condition("availability < in_stock")


@pytest.mark.asyncio
async def test_alert_webhook_delivery_logs_success(db_session, test_user, monkeypatch) -> None:
    monitor = MonitorJob(
        user_id=test_user.id,
        name="Alert example.com",
        urls=["https://example.com/product/1"],
        domains=["example.com"],
        surface="ecommerce_detail",
        tracked_fields=["price", "availability"],
        schedule_interval_hours=1,
        priority=MONITOR_PRIORITY_BACKGROUND,
        retention_days=90,
        settings={SKIP_HEAD_CHECK_KEY: True},
        requested_fields=["price", "availability"],
        status=MONITOR_STATUS_ACTIVE,
        condition="price < 150",
        webhook_url="https://agent.example/webhook",
        poll_interval_seconds=300,
        last_known_values={"price": "129.99", "availability": "in_stock"},
        last_crawl_method="http",
    )
    db_session.add(monitor)
    await db_session.flush()
    event = MonitorEvent(
        monitor_id=monitor.id,
        run_id=None,
        source_url="https://example.com/product/1",
        event_type=MONITOR_EVENT_FIELD_CHANGED,
        field_name="price",
        old_value="159.99",
        new_value="129.99",
        detected_at=utcnow(),
        condition_met=True,
    )
    db_session.add(event)
    await db_session.flush()
    monkeypatch.setattr("app.services.monitor_webhook_service.httpx.AsyncClient", _HttpClient)

    await dispatch_alert_webhooks(db_session, monitor=monitor, events=[event])
    await db_session.commit()

    assert monitor.webhook_url == "https://agent.example/webhook"
    delivery = await db_session.scalar(select(MonitorWebhookDelivery))
    assert delivery is not None
    assert delivery.status == WEBHOOK_STATUS_SENT
    assert delivery.response_code == 204
    assert delivery.payload_preview["delta"]["field"] == "price"


@pytest.mark.asyncio
async def test_alert_webhook_delivery_logs_request_errors(db_session, test_user, monkeypatch) -> None:
    monitor = MonitorJob(
        user_id=test_user.id,
        name="Alert example.com",
        urls=["https://example.com/product/1"],
        domains=["example.com"],
        surface="ecommerce_detail",
        tracked_fields=["price"],
        schedule_interval_hours=1,
        priority=MONITOR_PRIORITY_BACKGROUND,
        retention_days=90,
        settings={SKIP_HEAD_CHECK_KEY: True},
        requested_fields=["price"],
        status=MONITOR_STATUS_ACTIVE,
        condition="price < 150",
        webhook_url="https://agent.example/webhook",
        poll_interval_seconds=300,
        last_known_values={"price": "129.99"},
        last_crawl_method="http",
    )
    db_session.add(monitor)
    await db_session.flush()
    event = MonitorEvent(
        monitor_id=monitor.id,
        run_id=None,
        source_url="https://example.com/product/1",
        event_type=MONITOR_EVENT_FIELD_CHANGED,
        field_name="price",
        old_value="159.99",
        new_value="129.99",
        detected_at=utcnow(),
        condition_met=True,
    )
    db_session.add(event)
    await db_session.flush()
    monkeypatch.setattr("app.services.monitor_webhook_service.httpx.AsyncClient", _FailingHttpClient)
    monkeypatch.setattr("app.services.monitor_webhook_service.WEBHOOK_MAX_RETRY_ATTEMPTS", 1)

    await dispatch_alert_webhooks(db_session, monitor=monitor, events=[event])
    await db_session.commit()

    delivery = await db_session.scalar(select(MonitorWebhookDelivery))
    assert delivery is not None
    assert delivery.status != WEBHOOK_STATUS_SENT
    assert delivery.error_message == "RequestError: network down"


@pytest.mark.asyncio
async def test_alert_webhook_delivery_propagates_unexpected_errors(
    db_session,
    test_user,
    monkeypatch,
) -> None:
    monitor = MonitorJob(
        user_id=test_user.id,
        name="Alert example.com",
        urls=["https://example.com/product/1"],
        domains=["example.com"],
        surface="ecommerce_detail",
        tracked_fields=["price"],
        schedule_interval_hours=1,
        priority=MONITOR_PRIORITY_BACKGROUND,
        retention_days=90,
        settings={SKIP_HEAD_CHECK_KEY: True},
        requested_fields=["price"],
        status=MONITOR_STATUS_ACTIVE,
        condition="price < 150",
        webhook_url="https://agent.example/webhook",
        poll_interval_seconds=300,
        last_known_values={"price": "129.99"},
        last_crawl_method="http",
    )
    db_session.add(monitor)
    await db_session.flush()
    event = MonitorEvent(
        monitor_id=monitor.id,
        run_id=None,
        source_url="https://example.com/product/1",
        event_type=MONITOR_EVENT_FIELD_CHANGED,
        field_name="price",
        old_value="159.99",
        new_value="129.99",
        detected_at=utcnow(),
        condition_met=True,
    )
    db_session.add(event)
    await db_session.flush()
    monkeypatch.setattr("app.services.monitor_webhook_service.httpx.AsyncClient", _BuggyHttpClient)
    monkeypatch.setattr("app.services.monitor_webhook_service.WEBHOOK_MAX_RETRY_ATTEMPTS", 1)

    with pytest.raises(ValueError, match="boom"):
        await dispatch_alert_webhooks(db_session, monitor=monitor, events=[event])


def test_alert_response_rejects_invalid_status() -> None:
    monitor = MonitorJob(
        id=99,
        user_id=1,
        name="Alert example.com",
        urls=["https://example.com/product/1"],
        domains=["example.com"],
        surface="ecommerce_detail",
        tracked_fields=["price"],
        schedule_interval_hours=1,
        priority=MONITOR_PRIORITY_BACKGROUND,
        retention_days=90,
        settings={SKIP_HEAD_CHECK_KEY: True},
        requested_fields=["price"],
        status="invalid-status",
        poll_interval_seconds=300,
        created_at=utcnow(),
        updated_at=utcnow(),
    )

    with pytest.raises(ValueError, match="Invalid alert status"):
        alert_response(monitor)


@pytest.mark.asyncio
async def test_public_alert_api_requires_api_key(public_client: AsyncClient) -> None:
    response = await public_client.get("/api/v1/alerts")
    assert response.status_code == 401
    assert response.json()["meta"]["duration_ms"] >= 0



@pytest.mark.asyncio
async def test_public_alert_list_uses_api_key_envelope(
    public_client: AsyncClient,
    db_session,
    test_user,
) -> None:
    raw_key = "crawlerai_test_key"
    db_session.add(
        ApiKey(
            user_id=test_user.id,
            name="test",
            key_prefix="crawlerai",
            key_hash=hash_api_key(raw_key),
            is_active=True,
        )
    )
    monitor = MonitorJob(
        user_id=test_user.id,
        name="Alert example.com",
        urls=["https://example.com/product/1"],
        domains=["example.com"],
        surface="ecommerce_detail",
        tracked_fields=["price"],
        schedule_interval_hours=1,
        priority=MONITOR_PRIORITY_BACKGROUND,
        retention_days=90,
        settings={SKIP_HEAD_CHECK_KEY: True},
        requested_fields=["price"],
        status=MONITOR_STATUS_ACTIVE,
        poll_interval_seconds=300,
        last_known_values={"price": "129.99"},
    )
    db_session.add(monitor)
    await db_session.commit()

    response = await public_client.get(
        "/api/v1/alerts",
        headers={"Authorization": f"Bearer {raw_key}"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["data"][0]["id"] == monitor.id
    assert payload["data"][0]["target_fields"] == ["price"]
    assert alert_response((await list_alerts(db_session, user_id=test_user.id))[0]).id == monitor.id


@pytest.mark.asyncio
async def test_public_alert_create_uses_public_api_contract(
    public_client: AsyncClient,
    db_session,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    raw_key = "crawlerai_create_alert_key"
    db_session.add(
        ApiKey(
            user_id=test_user.id,
            name="test",
            key_prefix="crawlerai",
            key_hash=hash_api_key(raw_key),
            is_active=True,
        )
    )
    await db_session.commit()

    monitor = MonitorJob(
        id=123,
        user_id=test_user.id,
        name="Alert example.com",
        urls=["https://example.com/product/1"],
        domains=["example.com"],
        surface="ecommerce_detail",
        tracked_fields=["price"],
        schedule_interval_hours=1,
        priority=MONITOR_PRIORITY_BACKGROUND,
        retention_days=90,
        settings={SKIP_HEAD_CHECK_KEY: True},
        requested_fields=["price"],
        status=MONITOR_STATUS_ACTIVE,
        poll_interval_seconds=300,
        last_known_values={"price": "129.99"},
        created_at=utcnow(),
        updated_at=utcnow(),
    )

    async def _fake_create_alert(session, *, user, payload):
        del session, user, payload
        return monitor, None

    monkeypatch.setattr("app.api.public_alerts.create_alert", _fake_create_alert)

    response = await public_client.post(
        "/api/v1/alerts",
        headers={"Authorization": f"Bearer {raw_key}"},
        json={"url": "https://example.com/product/1", "target_fields": ["price"]},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["data"]["id"] == 123
    assert payload["data"]["target_fields"] == ["price"]


@pytest.mark.asyncio
async def test_create_alert_failure_cleans_up_partial_monitor(
    db_session,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fail_poll(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("boom")

    monkeypatch.setattr("app.services.alert_service.run_alert_poll", _fail_poll)

    with pytest.raises(ValueError, match="Initial alert poll failed: boom"):
        await create_alert(
            db_session,
            user=test_user,
            payload=AlertCreate(
                url="https://example.com/product/1",
                target_fields=["price"],
                poll_interval_seconds=300,
            ),
        )

    monitors = list((await db_session.scalars(select(MonitorJob))).all())
    assert monitors == []


@pytest.mark.asyncio
async def test_mcp_alert_tools_map_to_public_api(monkeypatch) -> None:
    calls: list[dict] = []

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def request(self, method, url, *, headers, json=None, params=None):
            calls.append(
                {
                    "method": method,
                    "url": url,
                    "headers": headers,
                    "json": json,
                    "params": params,
                }
            )

            class _ApiResponse:
                status_code = 200

                def json(self):
                    return {"status": "ok", "data": {"alert_id": "7"}}

            return _ApiResponse()

    monkeypatch.setattr("app.mcp.alert_server.httpx.AsyncClient", lambda timeout=30: _Client())
    server = AlertMCPServer(api_key="secret", base_url="http://api.test/api/v1")

    result = await server.call_tool(
        "alert_product",
        {
            "url": "https://example.com/product/1",
            "condition": "price < 150",
            "target_fields": ["price"],
        },
    )

    assert result["status"] == "ok"
    assert calls == [
        {
            "method": "POST",
            "url": "http://api.test/api/v1/alerts",
            "headers": {"Authorization": "Bearer secret"},
            "json": {
                "url": "https://example.com/product/1",
                "condition": "price < 150",
                "target_fields": ["price"],
            },
            "params": None,
        }
    ]

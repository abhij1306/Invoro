from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from app.schemas.alert import AlertCreate, AlertUpdate
from app.services.monitor_alert_rules import (
    alert_rule_condition_met,
    alert_rule_tracked_values,
)
from app.services.alert_service import alert_response, create_alert, update_alert
from app.services.config.monitor_settings import MONITOR_STATUS_ARCHIVED


@pytest.mark.asyncio
async def test_create_alert_aligns_requested_fields_with_targets(
    db_session,
    test_user,
    monkeypatch,
) -> None:
    async def _poll(_session, *, monitor, suppress_webhooks, update_schedule):
        assert suppress_webhooks is True
        assert update_schedule is False
        return 77

    monkeypatch.setattr("app.services.alert_service.run_alert_poll", _poll)

    monitor, run_id = await create_alert(
        db_session,
        user=test_user,
        payload=AlertCreate(
            url="https://example.com/products/widget",
            target_fields=["price", "availability"],
            condition="price < 50",
            poll_interval_seconds=300,
        ),
    )

    assert run_id == 77
    assert monitor.tracked_fields == ["price", "availability"]
    assert monitor.requested_fields == ["price", "availability"]
    assert monitor.settings["skip_head_check"] is True


@pytest.mark.asyncio
async def test_update_alert_keeps_target_and_requested_fields_aligned(
    db_session,
    test_user,
    monkeypatch,
) -> None:
    async def _poll(_session, *, monitor, suppress_webhooks, update_schedule):
        return 88

    monkeypatch.setattr("app.services.alert_service.run_alert_poll", _poll)
    monitor, _ = await create_alert(
        db_session,
        user=test_user,
        payload=AlertCreate(
            url="https://example.com/products/widget",
            target_fields=["price", "availability"],
        ),
    )

    updated = await update_alert(
        db_session,
        alert_id=monitor.id,
        user_id=test_user.id,
        payload=AlertUpdate(target_fields=["sku"]),
    )

    assert updated.tracked_fields == ["sku"]
    assert updated.requested_fields == ["sku"]
    with pytest.raises(ValueError, match="Use DELETE"):
        await update_alert(
            db_session,
            alert_id=monitor.id,
            user_id=test_user.id,
            payload=AlertUpdate(status=MONITOR_STATUS_ARCHIVED),
        )


@pytest.mark.asyncio
async def test_create_alert_accepts_variant_target_rules(
    db_session,
    test_user,
    monkeypatch,
) -> None:
    async def _poll(_session, *, monitor, suppress_webhooks, update_schedule):
        return 91

    monkeypatch.setattr("app.services.alert_service.run_alert_poll", _poll)

    monitor, run_id = await create_alert(
        db_session,
        user=test_user,
        payload=AlertCreate(
            url="https://example.com/products/widget",
            target_fields=["variants"],
            target_rules=[
                {
                    "path": "variants[*].availability",
                    "label": "Any variant availability",
                    "operator": "changed",
                }
            ],
        ),
    )

    assert run_id == 91
    assert monitor.tracked_fields == ["variants"]
    assert monitor.requested_fields == ["variants"]
    assert monitor.settings["alert_rules"] == [
        {
            "path": "variants[*].availability",
            "label": "Any variant availability",
            "operator": "changed",
        }
    ]


def test_variant_alert_rule_values_are_identity_stable() -> None:
    rules = [
        {
            "path": "variants[*].availability",
            "label": "Any variant availability",
            "operator": "changed",
        },
        {
            "path": "variants[*].price",
            "label": "Small price below 900",
            "operator": "less_than",
            "value": "900",
            "variant_match": {"size": "S"},
        },
    ]
    data = {
        "variants": [
            {"sku": "sku-m", "size": "M", "availability": "in_stock", "price": "999.00"},
            {"sku": "sku-s", "size": "S", "availability": "out_of_stock", "price": "849.00"},
        ]
    }

    values = alert_rule_tracked_values(data, rules)

    assert values["Any variant availability"] == {
        "sku:sku-m": "in_stock",
        "sku:sku-s": "out_of_stock",
    }
    assert values["Small price below 900"] == "849.00"
    assert alert_rule_condition_met(rules[1], values["Small price below 900"]) is True


def test_alert_response_preserves_model_backed_stored_rules() -> None:
    class _StoredAlertRule(BaseModel):
        path: str
        label: str | None = None
        operator: str = "changed"

    timestamp = datetime.now(UTC)
    monitor = SimpleNamespace(
        id=1,
        urls=["https://example.com/products/widget"],
        surface="ecommerce_detail",
        tracked_fields=["price"],
        settings={
            "alert_rules": [
                _StoredAlertRule(
                    path="price",
                    label="Price changed",
                )
            ]
        },
        condition=None,
        webhook_url=None,
        poll_interval_seconds=300,
        status="active",
        last_checked_at=None,
        last_known_values={},
        last_error=None,
        last_crawl_method=None,
        created_at=timestamp,
        updated_at=timestamp,
    )

    response = alert_response(monitor)

    assert len(response.target_rules) == 1
    assert response.target_rules[0].path == "price"
    assert response.target_rules[0].label == "Price changed"

from __future__ import annotations

from pydantic import TypeAdapter, ValidationError
from sqlalchemy import func, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crawl_run import CrawlRun
from app.models.monitor import MonitorJob
from app.models.user import User
from app.schemas.alert import (
    AlertCreate,
    AlertHistoryItem,
    AlertResponse,
    AlertStatus,
    AlertUpdate,
)
from app.services.config.monitor_settings import (
    ALERT_RULES_SETTING_KEY,
    MAX_ALERTS_PER_USER,
    MONITOR_ID_SETTING_KEY,
    MONITOR_STATUS_ACTIVE,
    MONITOR_STATUS_ARCHIVED,
    MONITOR_STATUS_ERROR,
    MONITOR_STATUS_PAUSED,
    MONITOR_STATUS_TRIGGERED,
    MONITOR_SUPPRESS_WEBHOOKS_SETTING_KEY,
    ALERT_SURFACE,
)
from app.services.crawl.crud import create_crawl_run
from app.services.crawl.batch_runtime import process_run
from app.services.domain_utils import normalize_domain
from app.services.field_policy import preserve_requested_fields
from app.services.monitor_condition import validate_condition
from app.services.monitor_alert_rules import alert_rule_requested_fields
from app.services.monitor_service import (
    create_monitor,
    get_monitor,
    list_events,
    list_monitors,
    update_monitor,
    utcnow,
)

_ALERT_STATUS_ADAPTER: TypeAdapter[AlertStatus] = TypeAdapter(AlertStatus)


async def create_alert(
    session: AsyncSession,
    *,
    user: User,
    payload: AlertCreate,
) -> tuple[MonitorJob, int | None]:
    validate_condition(payload.condition)
    alert_count = int(
        (
            await session.scalar(
                select(func.count())
                .select_from(MonitorJob)
                .where(
                    MonitorJob.user_id == user.id,
                    MonitorJob.poll_interval_seconds.is_not(None),
                    MonitorJob.status != MONITOR_STATUS_ARCHIVED,
                )
            )
        )
        or 0
    )
    if alert_count >= MAX_ALERTS_PER_USER:
        raise ValueError("Alert limit reached")
    target_rules = _rules_payload(payload.target_rules)
    tracked_fields = _tracked_fields(payload.target_fields, target_rules)
    requested_fields = _requested_fields(tracked_fields, target_rules)
    settings = {"skip_head_check": True}
    if target_rules:
        settings[ALERT_RULES_SETTING_KEY] = target_rules
    monitor = await create_monitor(
        session,
        user=user,
        payload={
            "name": _alert_name(payload.url),
            "urls": [payload.url],
            "surface": ALERT_SURFACE,
            "tracked_fields": tracked_fields,
            "requested_fields": requested_fields,
            "schedule_interval_hours": 1,
            "retention_days": 90,
            "settings": settings,
            "condition": payload.condition,
            "webhook_url": payload.webhook_url,
            "poll_interval_seconds": payload.poll_interval_seconds,
        },
    )
    try:
        run_id = await run_alert_poll(
            session,
            monitor=monitor,
            suppress_webhooks=True,
            update_schedule=False,
        )
        await session.refresh(monitor)
    except (RuntimeError, SQLAlchemyError, TypeError, ValueError) as exc:
        await _discard_failed_alert(session, monitor_id=int(monitor.id))
        raise ValueError(f"Initial alert poll failed: {exc}") from exc
    return monitor, run_id


async def list_alerts(
    session: AsyncSession,
    *,
    user_id: int,
    status: str | None = None,
) -> list[MonitorJob]:
    return await list_monitors(
        session,
        status=status,
        user_id=user_id,
        alerts_only=True,
        exclude_archived=status is None,
    )


async def get_alert(session: AsyncSession, alert_id: int, *, user_id: int) -> MonitorJob:
    monitor = await get_monitor(session, alert_id)
    if monitor.user_id != user_id or not monitor.poll_interval_seconds:
        raise LookupError("Alert not found")
    return monitor


async def update_alert(
    session: AsyncSession,
    *,
    alert_id: int,
    user_id: int,
    payload: AlertUpdate,
) -> MonitorJob:
    monitor = await get_alert(session, alert_id, user_id=user_id)
    data = payload.model_dump(exclude_unset=True)
    if "condition" in data:
        validate_condition(data.get("condition"))
    if data.get("target_rules") is not None:
        target_rules = _rules_payload(data.pop("target_rules"))
        target_fields = _tracked_fields(data.pop("target_fields", None), target_rules)
        data["tracked_fields"] = target_fields
        data["requested_fields"] = _requested_fields(target_fields, target_rules)
        settings = dict(monitor.settings or {})
        settings[ALERT_RULES_SETTING_KEY] = target_rules
        data["settings"] = settings
    if data.get("target_fields") is not None:
        target_fields = data.pop("target_fields")
        data["tracked_fields"] = target_fields
        data["requested_fields"] = preserve_requested_fields(target_fields)
        settings = dict(monitor.settings or {})
        settings.pop(ALERT_RULES_SETTING_KEY, None)
        data["settings"] = settings
    if data.get("status") == MONITOR_STATUS_ARCHIVED:
        raise ValueError("Use DELETE to archive an alert")
    if data.get("status") not in {
        None,
        MONITOR_STATUS_ACTIVE,
        MONITOR_STATUS_PAUSED,
        MONITOR_STATUS_TRIGGERED,
        MONITOR_STATUS_ERROR,
    }:
        raise ValueError("Invalid alert status")
    updated = await update_monitor(session, monitor_id=monitor.id, payload=data)
    return updated


async def delete_alert(session: AsyncSession, *, alert_id: int, user_id: int) -> None:
    monitor = await get_alert(session, alert_id, user_id=user_id)
    monitor.status = MONITOR_STATUS_ARCHIVED
    await session.commit()


async def test_alert(session: AsyncSession, *, alert_id: int, user_id: int) -> tuple[MonitorJob, int]:
    monitor = await get_alert(session, alert_id, user_id=user_id)
    run_id = await run_alert_poll(
        session,
        monitor=monitor,
        suppress_webhooks=True,
        update_schedule=False,
    )
    await session.refresh(monitor)
    return monitor, run_id


async def alert_run_delta_count(session: AsyncSession, *, run_id: int) -> int:
    run = await session.get(CrawlRun, run_id)
    if run is None:
        return 0
    raw_count = run.summary_dict().get("monitor_change_count")
    if isinstance(raw_count, int | float):
        return int(raw_count)
    if isinstance(raw_count, str):
        try:
            return int(raw_count)
        except (TypeError, ValueError):
            return 0
    return 0


async def alert_history(
    session: AsyncSession,
    *,
    alert_id: int,
    user_id: int,
    page: int,
    limit: int,
) -> tuple[list[AlertHistoryItem], int]:
    await get_alert(session, alert_id, user_id=user_id)
    rows, total = await list_events(session, monitor_id=alert_id, page=page, limit=limit)
    return [
        AlertHistoryItem(
            id=row.id,
            alert_id=row.monitor_id,
            source_url=row.source_url,
            event_type=row.event_type,
            field_name=row.field_name,
            previous_value=row.old_value,
            current_value=row.new_value,
            detected_at=row.detected_at,
            condition_met=bool(row.condition_met),
        )
        for row in rows
    ], total


async def run_alert_poll(
    session: AsyncSession,
    *,
    monitor: MonitorJob,
    suppress_webhooks: bool,
    update_schedule: bool,
) -> int:
    settings = dict(monitor.settings or {})
    settings[MONITOR_ID_SETTING_KEY] = monitor.id
    settings[MONITOR_SUPPRESS_WEBHOOKS_SETTING_KEY] = suppress_webhooks
    payload = {
        "run_type": "crawl",
        "url": (monitor.urls or [""])[0],
        "urls": list(monitor.urls or []),
        "surface": monitor.surface,
        "settings": settings,
        "requested_fields": list(monitor.requested_fields or monitor.tracked_fields or []),
    }
    if monitor.user_id is None:
        raise ValueError("Alert monitor is missing a user id")
    run = await create_crawl_run(session, monitor.user_id, payload)
    await process_run(session, int(run.id))
    loaded_run = await session.get(CrawlRun, int(run.id))
    if loaded_run is not None and update_schedule:
        monitor.last_run_at = utcnow()
        await session.flush()
    return int(run.id)


def alert_response(monitor: MonitorJob) -> AlertResponse:
    url = (monitor.urls or [""])[0]
    try:
        status = _ALERT_STATUS_ADAPTER.validate_python(str(monitor.status))
    except ValidationError as exc:
        raise ValueError(
            f"Invalid alert status for monitor {monitor.id}: {monitor.status!r}"
        ) from exc
    return AlertResponse(
        id=monitor.id,
        url=url,
        domain=normalize_domain(url),
        surface=monitor.surface,
        target_fields=list(monitor.tracked_fields or []),
        target_rules=_rules_payload((monitor.settings or {}).get(ALERT_RULES_SETTING_KEY)),
        condition=monitor.condition,
        webhook_url=monitor.webhook_url,
        poll_interval_seconds=int(monitor.poll_interval_seconds or 0),
        status=status,
        last_checked_at=monitor.last_checked_at,
        last_known_values=dict(monitor.last_known_values or {}),
        last_error=monitor.last_error,
        last_crawl_method=monitor.last_crawl_method,
        created_at=monitor.created_at,
        updated_at=monitor.updated_at,
    )


def _alert_name(url: str) -> str:
    domain = normalize_domain(url) or "alert"
    return f"Alert {domain}"[:100]


def _rules_payload(rules) -> list[dict]:
    if not rules:
        return []
    output: list[dict] = []
    for rule in rules:
        if hasattr(rule, "model_dump"):
            output.append(rule.model_dump(exclude_none=True))
        elif isinstance(rule, dict):
            output.append({key: value for key, value in rule.items() if value is not None})
    return output


def _tracked_fields(target_fields, target_rules: list[dict]) -> list[str]:
    if target_rules:
        return preserve_requested_fields(alert_rule_requested_fields(target_rules))
    return preserve_requested_fields(list(target_fields or []))


def _requested_fields(target_fields: list[str], target_rules: list[dict]) -> list[str]:
    return preserve_requested_fields([*target_fields, *alert_rule_requested_fields(target_rules)])


async def _discard_failed_alert(session: AsyncSession, *, monitor_id: int) -> None:
    await session.rollback()
    monitor = await session.get(MonitorJob, monitor_id)
    if monitor is None:
        return
    await session.delete(monitor)
    await session.commit()

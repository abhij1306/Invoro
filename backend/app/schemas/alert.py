from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.config.monitor_settings import (
    ALERT_RULE_OPERATOR_CHANGED,
    ALERT_RULE_OPERATORS,
    ALERT_VARIANT_WILDCARD_PATH_PREFIX,
    MAX_ALERT_TARGET_FIELDS,
    MAX_ALERT_TARGET_RULES,
    MIN_ALERT_POLL_INTERVAL_SECONDS,
    ALERT_ALLOWED_FIELDS,
    ALERT_DEFAULT_TARGET_FIELDS,
)

AlertStatus = Literal["active", "paused", "triggered", "error", "archived"]


def validate_target_fields(value: list[str] | None) -> list[str] | None:
    if value is None:
        return None
    fields: list[str] = []
    seen: set[str] = set()
    for item in value:
        field = str(item or "").strip()
        if not field or field in seen:
            continue
        if field not in ALERT_ALLOWED_FIELDS:
            raise ValueError(f"Unsupported target field: {field}")
        fields.append(field)
        seen.add(field)
    if not fields:
        raise ValueError("target_fields must not be empty")
    if len(fields) > MAX_ALERT_TARGET_FIELDS:
        raise ValueError("too many target_fields")
    return fields


def validate_webhook_url(value: str | None) -> str | None:
    if value is None:
        return None
    url = value.strip()
    if not url:
        return None
    if not url.startswith(("http://", "https://")):
        raise ValueError("webhook_url must start with http:// or https://")
    return url


class AlertRule(BaseModel):
    path: str
    label: str | None = None
    operator: str = ALERT_RULE_OPERATOR_CHANGED
    value: Any = None
    variant_match: dict[str, Any] | None = None

    @field_validator("path")
    @classmethod
    def _validate_path(cls, value: str) -> str:
        path = str(value or "").strip()
        if not path:
            raise ValueError("alert rule path must not be empty")
        if path.startswith(ALERT_VARIANT_WILDCARD_PATH_PREFIX):
            field = path.removeprefix(ALERT_VARIANT_WILDCARD_PATH_PREFIX)
            if field and field.replace("_", "").isalnum() and not field[0].isdigit():
                return path
        if "." not in path and path.replace("_", "").isalnum() and not path[0].isdigit():
            return path
        raise ValueError("unsupported alert rule path")

    @field_validator("operator")
    @classmethod
    def _validate_operator(cls, value: str) -> str:
        operator = str(value or "").strip() or ALERT_RULE_OPERATOR_CHANGED
        if operator not in ALERT_RULE_OPERATORS:
            raise ValueError("unsupported alert rule operator")
        return operator


def validate_target_rules(value: list[AlertRule] | None) -> list[AlertRule] | None:
    if value is None:
        return None
    if not value:
        raise ValueError("target_rules must not be empty")
    if len(value) > MAX_ALERT_TARGET_RULES:
        raise ValueError("too many target_rules")
    return value


class AlertCreate(BaseModel):
    url: str
    target_fields: list[str] = Field(default_factory=lambda: list(ALERT_DEFAULT_TARGET_FIELDS))
    target_rules: list[AlertRule] | None = None
    condition: str | None = None
    webhook_url: str | None = None
    poll_interval_seconds: int = Field(default=300, ge=MIN_ALERT_POLL_INTERVAL_SECONDS)

    @field_validator("url")
    @classmethod
    def _validate_url(cls, value: str) -> str:
        url = str(value or "").strip()
        if not url.startswith(("http://", "https://")):
            raise ValueError("url must start with http:// or https://")
        return url

    @field_validator("target_fields")
    @classmethod
    def _validate_fields(cls, value: list[str]) -> list[str]:
        return list(validate_target_fields(value) or [])

    @field_validator("target_rules")
    @classmethod
    def _validate_rules(cls, value: list[AlertRule] | None) -> list[AlertRule] | None:
        return validate_target_rules(value)

    @field_validator("webhook_url")
    @classmethod
    def _validate_webhook(cls, value: str | None) -> str | None:
        return validate_webhook_url(value)


class AlertUpdate(BaseModel):
    condition: str | None = None
    webhook_url: str | None = None
    poll_interval_seconds: int | None = Field(default=None, ge=MIN_ALERT_POLL_INTERVAL_SECONDS)
    status: AlertStatus | None = None
    target_fields: list[str] | None = None
    target_rules: list[AlertRule] | None = None

    @field_validator("target_fields")
    @classmethod
    def _validate_fields(cls, value: list[str] | None) -> list[str] | None:
        return validate_target_fields(value)

    @field_validator("target_rules")
    @classmethod
    def _validate_rules(cls, value: list[AlertRule] | None) -> list[AlertRule] | None:
        return validate_target_rules(value)

    @field_validator("webhook_url")
    @classmethod
    def _validate_webhook(cls, value: str | None) -> str | None:
        return validate_webhook_url(value)


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    domain: str
    surface: str
    target_fields: list[str]
    target_rules: list[AlertRule] = Field(default_factory=list)
    condition: str | None = None
    webhook_url: str | None = None
    poll_interval_seconds: int
    status: AlertStatus
    last_checked_at: datetime | None = None
    last_known_values: dict[str, Any] = Field(default_factory=dict)
    last_error: str | None = None
    last_crawl_method: str | None = None
    created_at: datetime
    updated_at: datetime


class AlertHistoryItem(BaseModel):
    id: int
    alert_id: int
    source_url: str
    event_type: str
    field_name: str | None = None
    previous_value: Any = None
    current_value: Any = None
    detected_at: datetime
    condition_met: bool = False


class AlertTestResponse(BaseModel):
    alert: AlertResponse
    run_id: int
    current_snapshot: dict[str, Any]
    delta_count: int


class WebhookDeliveryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    monitor_id: int
    event_id: int | None = None
    status: str
    attempt: int
    response_code: int | None = None
    error_message: str | None = None
    payload_preview: dict[str, Any] = Field(default_factory=dict)
    delivered_at: datetime | None = None
    created_at: datetime

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.config.monitor_settings import (
    MAX_ALERT_TARGET_FIELDS,
    MIN_ALERT_POLL_INTERVAL_SECONDS,
    ALERT_ALLOWED_FIELDS,
    ALERT_DEFAULT_TARGET_FIELDS,
)

AlertStatus = Literal["active", "paused", "triggered", "error", "archived"]


class AlertCreate(BaseModel):
    url: str
    target_fields: list[str] = Field(default_factory=lambda: list(ALERT_DEFAULT_TARGET_FIELDS))
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

    @field_validator("webhook_url")
    @classmethod
    def _validate_webhook(cls, value: str | None) -> str | None:
        if value is None:
            return None
        url = value.strip()
        if not url:
            return None
        if not url.startswith(("http://", "https://")):
            raise ValueError("webhook_url must start with http:// or https://")
        return url


class AlertUpdate(BaseModel):
    condition: str | None = None
    webhook_url: str | None = None
    poll_interval_seconds: int | None = Field(default=None, ge=MIN_ALERT_POLL_INTERVAL_SECONDS)
    status: AlertStatus | None = None
    target_fields: list[str] | None = None

    @field_validator("target_fields")
    @classmethod
    def _validate_fields(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        return AlertCreate(url="https://example.com", target_fields=value).target_fields

    @field_validator("webhook_url")
    @classmethod
    def _validate_webhook(cls, value: str | None) -> str | None:
        return AlertCreate(url="https://example.com", webhook_url=value).webhook_url


class AlertResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    url: str
    domain: str
    surface: str
    target_fields: list[str]
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

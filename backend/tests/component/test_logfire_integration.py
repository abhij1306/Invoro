from __future__ import annotations

import logging
import sys
from types import SimpleNamespace

import pytest
from fastapi import FastAPI

from app.core import logfire_integration
from app.core.config import settings


def _instrumented_fake_logfire(calls: list[tuple[str, dict[str, object]]]):
    return SimpleNamespace(
        AdvancedOptions=lambda **kwargs: kwargs,
        LogfireLoggingHandler=lambda **kwargs: logging.NullHandler(),
        configure=lambda **kwargs: calls.append(("configure", kwargs)),
        instrument_fastapi=lambda app, **kwargs: calls.append(
            ("fastapi", {"app": app, **kwargs})
        ),
        instrument_celery=lambda **kwargs: calls.append(("celery", kwargs)),
        instrument_system_metrics=lambda: calls.append(("system_metrics", {})),
    )


def _calls_named(calls: list[tuple[str, dict[str, object]]], name: str):
    return [call for call in calls if call[0] == name]


@pytest.fixture(autouse=True)
def reset_logfire_state(monkeypatch):
    logfire_integration.reset_logfire_state_for_tests()
    monkeypatch.delitem(sys.modules, "logfire", raising=False)
    yield
    logfire_integration.reset_logfire_state_for_tests()
    monkeypatch.delitem(sys.modules, "logfire", raising=False)


@pytest.mark.component
def test_logfire_disabled_skips_configuration(monkeypatch) -> None:
    monkeypatch.setattr(settings, "logfire_enabled", False)

    assert logfire_integration.configure_logfire() is False


@pytest.mark.component
def test_logfire_configures_once_and_instruments(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    fake_logfire = _instrumented_fake_logfire(calls)
    monkeypatch.setitem(sys.modules, "logfire", fake_logfire)
    monkeypatch.setattr(settings, "logfire_enabled", True)
    monkeypatch.setattr(settings, "logfire_enabled_in_tests", True)
    monkeypatch.setattr(settings, "logfire_base_url", "https://logfire-us.pydantic.dev")
    monkeypatch.setattr(settings, "logfire_token", "token-123")
    monkeypatch.setattr(settings, "logfire_service_name", "invoro-test")
    monkeypatch.setattr(settings, "logfire_environment", "staging")
    monkeypatch.setattr(settings, "logfire_capture_headers", False)
    monkeypatch.setattr(settings, "logfire_send_to_logfire", "if-token-present")

    app = FastAPI()

    assert logfire_integration.instrument_fastapi(app) is True
    assert logfire_integration.instrument_celery() is True
    assert logfire_integration.instrument_fastapi(app) is True

    configure_calls = _calls_named(calls, "configure")
    fastapi_calls = _calls_named(calls, "fastapi")
    celery_calls = _calls_named(calls, "celery")
    assert configure_calls == [
        (
            "configure",
            {
                "send_to_logfire": "if-token-present",
                "token": "token-123",
                "service_name": "invoro-test",
                "environment": "staging",
                "console": False,
                "inspect_arguments": False,
                "advanced": {"base_url": "https://logfire-us.pydantic.dev"},
            },
        )
    ]
    assert len(fastapi_calls) == 1
    assert fastapi_calls[0][1]["capture_headers"] is False
    assert callable(fastapi_calls[0][1]["request_attributes_mapper"])
    assert len(celery_calls) == 1
    assert _calls_named(calls, "system_metrics") == [("system_metrics", {})]


@pytest.mark.component
def test_logfire_can_disable_cloud_export(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    fake_logfire = SimpleNamespace(
        AdvancedOptions=lambda **kwargs: kwargs,
        LogfireLoggingHandler=lambda **kwargs: logging.NullHandler(),
        configure=lambda **kwargs: calls.append(("configure", kwargs)),
        instrument_system_metrics=lambda: None,
    )
    monkeypatch.setitem(sys.modules, "logfire", fake_logfire)
    monkeypatch.setattr(settings, "logfire_enabled", True)
    monkeypatch.setattr(settings, "logfire_enabled_in_tests", True)
    monkeypatch.setattr(settings, "logfire_token", "token-123")
    monkeypatch.setattr(settings, "logfire_send_to_logfire", False)

    assert logfire_integration.configure_logfire() is True

    assert calls == [
        (
            "configure",
            {
                "send_to_logfire": False,
                "token": "token-123",
                "service_name": settings.logfire_service_name,
                "environment": settings.logfire_environment or settings.app_env,
                "console": False,
                "inspect_arguments": False,
                "advanced": {"base_url": settings.logfire_base_url},
            },
        )
    ]


@pytest.mark.component
def test_logfire_span_is_noop_when_disabled(monkeypatch) -> None:
    monkeypatch.setattr(settings, "logfire_enabled", False)

    with logfire_integration.logfire_span("test.span", run_id=1) as span:
        logfire_integration.set_logfire_attributes(span, record_count=2)

    assert span is None


@pytest.mark.component
def test_logfire_span_sanitizes_attributes(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    class FakeSpan:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def set_attributes(self, attrs):
            calls.append(("set_attributes", attrs))

    fake_logfire = SimpleNamespace(
        AdvancedOptions=lambda **kwargs: kwargs,
        LogfireLoggingHandler=lambda **kwargs: logging.NullHandler(),
        configure=lambda **kwargs: calls.append(("configure", kwargs)),
        instrument_system_metrics=lambda: None,
        span=lambda name, **kwargs: (
            calls.append(("span", {"name": name, **kwargs})) or FakeSpan()
        ),
    )
    monkeypatch.setitem(sys.modules, "logfire", fake_logfire)
    monkeypatch.setattr(settings, "logfire_enabled", True)
    monkeypatch.setattr(settings, "logfire_enabled_in_tests", True)
    monkeypatch.setattr(settings, "logfire_token", "token-123")

    with logfire_integration.logfire_span("test.span", raw=None, items=[1, None]):
        pass

    span_calls = [call for call in calls if call[0] == "span"]
    assert span_calls == [("span", {"name": "test.span", "items": [1]})]


@pytest.mark.component
def test_logfire_span_strips_url_query_attributes(monkeypatch) -> None:
    calls: list[tuple[str, dict[str, object]]] = []

    class FakeSpan:
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    fake_logfire = SimpleNamespace(
        AdvancedOptions=lambda **kwargs: kwargs,
        LogfireLoggingHandler=lambda **kwargs: logging.NullHandler(),
        configure=lambda **kwargs: calls.append(("configure", kwargs)),
        instrument_system_metrics=lambda: None,
        span=lambda name, **kwargs: (
            calls.append(("span", {"name": name, **kwargs})) or FakeSpan()
        ),
    )
    monkeypatch.setitem(sys.modules, "logfire", fake_logfire)
    monkeypatch.setattr(settings, "logfire_enabled", True)
    monkeypatch.setattr(settings, "logfire_enabled_in_tests", True)
    monkeypatch.setattr(settings, "logfire_token", "token-123")

    with logfire_integration.logfire_span(
        "test.span",
        final_url="https://example.com/p/widget?token=secret#reviews",
        domain="example.com",
    ):
        pass

    span_calls = [call for call in calls if call[0] == "span"]
    assert span_calls == [
        (
            "span",
            {
                "name": "test.span",
                "final_url": "https://example.com/p/widget",
                "domain": "example.com",
            },
        )
    ]


@pytest.mark.component
def test_logfire_fastapi_mapper_excludes_argument_values() -> None:
    mapper = logfire_integration._redact_fastapi_request_attributes

    assert mapper(
        object(),
        {
            "values": {"password": "secret", "url": "https://example.com/?token=x"},
            "errors": [{"type": "missing", "loc": ["body", "name"]}],
        },
    ) == {"errors": [{"type": "missing", "loc": ["body", "name"]}]}
    assert mapper(object(), {"values": {"password": "secret"}, "errors": []}) == {}


@pytest.mark.component
def test_logfire_disabled_under_pytest_by_default(monkeypatch) -> None:
    monkeypatch.setattr(settings, "logfire_enabled", True)
    monkeypatch.setattr(settings, "logfire_enabled_in_tests", False)

    assert logfire_integration.configure_logfire() is False

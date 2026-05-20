from __future__ import annotations

import pytest

from app.core import config


def _patch_secret_guard_settings(monkeypatch, **overrides) -> None:
    values = {
        "app_env": "production",
        "jwt_secret_key": "secure-jwt-secret-value",
        "encryption_key": "secure-encryption-secret-value",
        "default_admin_password": "VeryStrongPassword123!",
        "default_admin_email": "owner@example.com",
        "bootstrap_admin_once": True,
    }
    values.update(overrides)
    for name, value in values.items():
        monkeypatch.setattr(config.settings, name, value)


def test_secret_guard_uses_settings_app_env(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    _patch_secret_guard_settings(
        monkeypatch,
        app_env="production",
        jwt_secret_key="change-me",
    )

    with pytest.raises(RuntimeError, match="jwt_secret_key"):
        config._check_secret_defaults()


def test_secret_guard_rejects_known_weak_admin_password(monkeypatch) -> None:
    _patch_secret_guard_settings(
        monkeypatch,
        default_admin_password="AdminPassword123!",
    )

    with pytest.raises(RuntimeError, match="insecure placeholder"):
        config._check_secret_defaults()


def test_admin_password_strength_requires_16_characters() -> None:
    assert "at least 16 characters" in config.admin_password_strength_issues(
        "Short123!"
    )
    assert config.admin_password_strength_issues("VeryStrongPassword123!") == []


def test_admin_password_strength_edge_cases() -> None:
    assert config.admin_password_strength_issues("Abcdefghijklm1!x") == []
    assert "an uppercase letter" in config.admin_password_strength_issues(
        "abcdefghijklm1!x"
    )
    assert "a lowercase letter" in config.admin_password_strength_issues(
        "ABCDEFGHIJKLM1!X"
    )
    assert "a digit" in config.admin_password_strength_issues("Abcdefghijklmn!x")
    assert "a special character" in config.admin_password_strength_issues(
        "Abcdefghijklm12x"
    )

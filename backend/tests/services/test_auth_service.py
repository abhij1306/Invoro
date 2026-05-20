from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services import auth_service


@pytest.mark.asyncio
async def test_bootstrap_admin_user_creates_admin(db_session, monkeypatch) -> None:
    monkeypatch.setattr(
        auth_service,
        "load_admin_bootstrap_settings",
        lambda: SimpleNamespace(
            bootstrap_admin_once=True,
            default_admin_email="Admin@Example.com",
            default_admin_password="VeryStrongPassword123!",
        ),
    )

    user = await auth_service.bootstrap_admin_user(db_session)

    assert user is not None
    assert user.email == "admin@example.com"
    assert user.role == "admin"
    assert user.is_active is True


@pytest.mark.asyncio
async def test_authenticate_user_requires_active_user(db_session) -> None:
    user = await auth_service.create_user(
        db_session,
        "login@example.com",
        "VeryStrongPassword123!",
    )

    authenticated = await auth_service.authenticate_user(
        db_session,
        "login@example.com",
        "VeryStrongPassword123!",
    )
    bad_password = await auth_service.authenticate_user(
        db_session,
        "login@example.com",
        "wrong-password",
    )
    user.is_active = False
    await db_session.commit()
    inactive = await auth_service.authenticate_user(
        db_session,
        "login@example.com",
        "VeryStrongPassword123!",
    )

    assert authenticated is not None
    token, authenticated_user = authenticated
    assert token
    assert authenticated_user.id == user.id
    assert bad_password is None
    assert inactive is None


def test_default_admin_password_validation_uses_config_strength_rules() -> None:
    with pytest.raises(RuntimeError, match="at least 16 characters"):
        auth_service._validate_default_admin_password("Short123!")



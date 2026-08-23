from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services import auth_service


_LEGACY_PASSWORD_123_HASH = (
    "$pbkdf2-sha256$29000$bGVnYWN5dGVzdHNhbHQ$"
    "2tMNT7s/R9R.1n6HHBilYIpIm4a3B8GTVpE8EXa.53E"
)
_LEGACY_STRONG_PASSWORD_HASH = (
    "$pbkdf2-sha256$29000$bGVnYWN5dGVzdHNhbHQ$"
    "9d30ZorsSGlmALzwm8aNoRNBv1leyDYhq8v/G2rgt1I"
)


@pytest.mark.asyncio
@pytest.mark.component
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

    rerun_user = await auth_service.bootstrap_admin_user(db_session)

    assert rerun_user is not None
    assert rerun_user.id == user.id


@pytest.mark.asyncio
@pytest.mark.component
async def test_bootstrap_admin_user_rejects_preexisting_non_admin(
    db_session, monkeypatch
) -> None:
    monkeypatch.setattr(
        auth_service,
        "load_admin_bootstrap_settings",
        lambda: SimpleNamespace(
            bootstrap_admin_once=True,
            default_admin_email="admin@example.com",
            default_admin_password="VeryStrongPassword123!",
        ),
    )
    existing = await auth_service.create_user(
        db_session,
        "admin@example.com",
        "ExistingPassword123!",
    )

    with pytest.raises(RuntimeError, match="exactly one active admin"):
        await auth_service.bootstrap_admin_user(db_session)

    await db_session.refresh(existing)
    assert existing.role == "user"
    assert existing.is_active is True


@pytest.mark.asyncio
@pytest.mark.component
async def test_bootstrap_admin_user_rejects_any_other_existing_user(
    db_session, monkeypatch
) -> None:
    monkeypatch.setattr(
        auth_service,
        "load_admin_bootstrap_settings",
        lambda: SimpleNamespace(
            bootstrap_admin_once=True,
            default_admin_email="admin@example.com",
            default_admin_password="VeryStrongPassword123!",
        ),
    )
    await auth_service.create_user(
        db_session,
        "other@example.com",
        "ExistingPassword123!",
    )

    with pytest.raises(RuntimeError, match="exactly one active admin"):
        await auth_service.bootstrap_admin_user(db_session)


@pytest.mark.asyncio
@pytest.mark.component
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


@pytest.mark.component
def test_default_admin_password_validation_warns_without_blocking(caplog) -> None:
    caplog.set_level("WARNING", logger="app.auth")

    auth_service._validate_default_admin_password("Short123!")

    assert any(
        "weaker than the current recommendation" in record.message
        for record in caplog.records
    )


@pytest.mark.component
def test_hash_password_uses_argon2_by_default() -> None:
    hashed = auth_service.hash_password("password123")

    assert hashed != "password123"
    assert auth_service.verify_password("password123", hashed) is True
    assert auth_service.password_needs_rehash(hashed) is False


@pytest.mark.component
def test_password_needs_rehash_detects_legacy_pbkdf2_hash() -> None:
    assert auth_service.password_needs_rehash(_LEGACY_PASSWORD_123_HASH) is True


@pytest.mark.asyncio
@pytest.mark.component
async def test_authenticate_user_rehash_does_not_commit_unrelated_changes(
    db_session,
) -> None:
    legacy_user = await auth_service.create_user(
        db_session,
        "legacy@example.com",
        "VeryStrongPassword123!",
    )
    legacy_user.hashed_password = _LEGACY_STRONG_PASSWORD_HASH
    await db_session.commit()
    await db_session.refresh(legacy_user)

    other_user = await auth_service.create_user(
        db_session,
        "other@example.com",
        "VeryStrongPassword123!",
    )
    other_user.is_active = False

    authenticated = await auth_service.authenticate_user(
        db_session,
        "legacy@example.com",
        "VeryStrongPassword123!",
    )

    observer_factory = async_sessionmaker(
        bind=db_session.bind,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    async with observer_factory() as observer_session:
        observed_other_user = await observer_session.get(
            type(other_user), other_user.id
        )

    assert authenticated is not None
    assert observed_other_user is not None
    assert observed_other_user.is_active is True

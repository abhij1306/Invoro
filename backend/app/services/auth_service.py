# Authentication and user lifecycle service.
from __future__ import annotations

import logging

from app.core.config import (
    admin_password_strength_issues,
    load_admin_bootstrap_settings,
)
from app.core.security import (
    create_access_token,
    hash_password,
    password_needs_rehash,
    verify_password,
)
from app.models.user import User
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm.attributes import set_committed_value

DEFAULT_ADMIN_EMAIL = "DEFAULT_ADMIN_EMAIL"
DEFAULT_ADMIN_PASSWORD = "DEFAULT_ADMIN_PASSWORD"  # nosec B105 # skipcq: SCT-A000 - environment variable name, not a secret.
BOOTSTRAP_ADMIN_ONCE = "BOOTSTRAP_ADMIN_ONCE"
logger = logging.getLogger("app.auth")


def _validate_default_admin_password(password: str) -> None:
    issues = admin_password_strength_issues(password)
    if issues:
        logger.warning(
            "Admin bootstrap secret is weaker than the current recommendation: must include %s",
            ", ".join(issues),
        )


def _load_default_admin_credentials() -> tuple[str, str]:
    admin_settings = load_admin_bootstrap_settings()
    email = str(admin_settings.default_admin_email or "").strip().lower()
    password = str(admin_settings.default_admin_password or "").strip()
    if not email:
        raise RuntimeError(f"{DEFAULT_ADMIN_EMAIL} is required for admin bootstrap.")
    if not password:
        raise RuntimeError(f"{DEFAULT_ADMIN_PASSWORD} is required for admin bootstrap.")
    _validate_default_admin_password(password)
    return email, password


async def create_user(
    session: AsyncSession, email: str, password: str, role: str = "user"
) -> User:
    user = User(email=email.lower(), hashed_password=hash_password(password), role=role)
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def bootstrap_admin_user(session: AsyncSession) -> User | None:
    admin_settings = load_admin_bootstrap_settings()
    if not admin_settings.bootstrap_admin_once:
        return None

    email, password = _load_default_admin_credentials()
    users = list((await session.execute(select(User))).scalars().all())
    if not users:
        return await create_user(session, email, password, role="admin")
    if (
        len(users) != 1
        or users[0].email != email
        or users[0].role != "admin"
        or not users[0].is_active
    ):
        raise RuntimeError(
            "Admin bootstrap requires an empty database or exactly one active "
            "admin matching DEFAULT_ADMIN_EMAIL."
        )
    return users[0]


async def authenticate_user(
    session: AsyncSession, email: str, password: str
) -> tuple[str, User] | None:
    result = await session.execute(select(User).where(User.email == email.lower()))
    user = result.scalar_one_or_none()
    if (
        user is None
        or not user.is_active
        or not verify_password(password, user.hashed_password)
    ):
        return None
    if password_needs_rehash(user.hashed_password):
        await _upgrade_password_hash(session, user, password)
        logger.info("auth.password_hash_upgraded", extra={"user_id": str(user.id)})
    return create_access_token(str(user.id), token_version=user.token_version), user


async def revoke_user_sessions(session: AsyncSession, user_id: int) -> None:
    await session.execute(
        update(User)
        .where(User.id == user_id)
        .values(token_version=func.coalesce(User.token_version, 0) + 1)
    )
    await session.commit()


async def _upgrade_password_hash(
    session: AsyncSession, user: User, password: str
) -> None:
    bind = session.bind
    if bind is None:
        raise RuntimeError("AsyncSession bind is required for password hash upgrades")
    new_hash = hash_password(password)
    isolated_session_factory = async_sessionmaker(
        bind=bind,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    async with isolated_session_factory() as isolated_session:
        await isolated_session.execute(
            update(User).where(User.id == user.id).values(hashed_password=new_hash)
        )
        await isolated_session.commit()
    set_committed_value(user, "hashed_password", new_hash)

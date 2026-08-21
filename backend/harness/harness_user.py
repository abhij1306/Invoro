from __future__ import annotations

from ._support_shared import DEFAULT_HARNESS_EMAIL, DEFAULT_HARNESS_PASSWORD, logger  # fmt: skip
import os
from app.core.security import hash_password, verify_password  # fmt: skip
from app.models.user import User  # fmt: skip
from sqlalchemy import select  # fmt: skip


async def _ensure_harness_user_id(session) -> int:
    if _is_production_environment():
        raise RuntimeError(
            "Harness user access is disabled outside local/test environments"
        )
    harness_email = (
        str(os.getenv("HARNESS_EMAIL") or DEFAULT_HARNESS_EMAIL).strip().lower()
    )
    harness_password = str(
        os.getenv("HARNESS_PASSWORD") or DEFAULT_HARNESS_PASSWORD
    ).strip()
    harness_role = (
        str(os.getenv("HARNESS_ROLE") or "harness").strip().lower() or "harness"
    )
    password_sync_enabled = str(
        os.getenv("ENABLE_HARNESS_PASSWORD_SYNC") or ""
    ).strip().lower() in {"1", "true", "yes", "on"}
    user = (
        await session.execute(select(User).where(User.email == harness_email).limit(1))
    ).scalar_one_or_none()
    if user is None:
        user = User(
            email=harness_email,
            hashed_password=hash_password(harness_password),
            role=harness_role,
            is_active=True,
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)
    elif not verify_password(harness_password, user.hashed_password):
        if not password_sync_enabled:
            logger.warning(
                "Harness password mismatch for user %s; refusing auto-sync because ENABLE_HARNESS_PASSWORD_SYNC is not enabled",
                int(user.id),
            )
            raise RuntimeError(
                "Harness user password mismatch; update the DB manually or set ENABLE_HARNESS_PASSWORD_SYNC=true"
            )
        user.hashed_password = hash_password(harness_password)
        logger.info(
            "Synchronized harness user password hash with ENABLE_HARNESS_PASSWORD_SYNC",
            extra={"user_id": int(user.id)},
        )
        await session.commit()
        await session.refresh(user)
    return int(user.id)


def _is_production_environment() -> bool:
    env_name = os.getenv("APP_ENV") or os.getenv("FLASK_ENV") or os.getenv("ENV")
    return str(env_name or "").strip().lower() not in {
        "development",
        "dev",
        "local",
        "test",
        "testing",
    }


__all__ = ['DEFAULT_HARNESS_EMAIL']  # fmt: skip

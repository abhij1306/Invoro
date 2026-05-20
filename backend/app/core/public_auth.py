from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.models.api_key import ApiKey
from app.models.user import User


def hash_api_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


async def get_public_api_user(
    authorization: str | None = Header(default=None),
    session: AsyncSession = Depends(get_db),
) -> User:
    scheme, _, credentials = str(authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not credentials.strip():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="API key required")
    key_hash = hash_api_key(credentials.strip())
    api_key = await session.scalar(
        select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active.is_(True))
    )
    if api_key is None or api_key.user_id is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")
    user = await session.get(User, int(api_key.user_id))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive API user")
    api_key.last_used_at = datetime.now(UTC)
    await session.commit()
    return user

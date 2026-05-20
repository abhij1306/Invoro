from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_db
from app.core.public_auth import hash_api_key
from app.main import app
from app.models.api_key import ApiKey


@pytest.mark.asyncio
async def test_public_watches_route_is_not_registered_after_alert_rename(db_session, test_user) -> None:
    raw_key = "crawlerai_watch_key"
    db_session.add(ApiKey(user_id=test_user.id, name="watch", key_prefix="crawlerai", key_hash=hash_api_key(raw_key), is_active=True))
    await db_session.commit()

    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
            response = await client.get(
                "/api/v1/watches",
                headers={"Authorization": f"Bearer {raw_key}"},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.dependencies import get_current_user, get_db
from app.core.public_auth import hash_api_key
from app.main import app
from app.models.api_key import ApiKey
from app.services.config.public_api import PUBLIC_API_ERROR_API_KEY_REQUIRED


@pytest.fixture
async def public_client(db_session):
    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_public_api_requires_api_key(public_client: AsyncClient) -> None:
    response = await public_client.get("/api/v1/capabilities")

    assert response.status_code == 401
    payload = response.json()
    assert payload["status"] == "error"
    assert payload["error"]["code"] == PUBLIC_API_ERROR_API_KEY_REQUIRED


@pytest.mark.asyncio
async def test_api_key_crud_returns_plaintext_once(db_session, test_user) -> None:
    async def _override_db():
        yield db_session

    async def _override_user():
        return test_user

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        created = await client.post("/api/api-keys", json={"name": "Railway"})
        listed = await client.get("/api/api-keys")
    app.dependency_overrides.clear()

    assert created.status_code == 201
    payload = created.json()
    assert payload["api_key"].startswith("cai_")
    assert payload["key_prefix"] == payload["api_key"][:12]
    assert listed.status_code == 200
    assert listed.json()[0]["name"] == "Railway"
    stored = await db_session.scalar(select(ApiKey).where(ApiKey.id == payload["id"]))
    assert stored is not None
    assert stored.key_hash == hash_api_key(payload["api_key"])


@pytest.mark.asyncio
async def test_public_capabilities_uses_api_key_envelope(
    public_client: AsyncClient,
    db_session,
    test_user,
) -> None:
    raw_key = "crawlerai_public_test_key"
    db_session.add(
        ApiKey(
            user_id=test_user.id,
            name="test",
            key_prefix="crawlerai",
            key_hash=hash_api_key(raw_key),
            is_active=True,
        )
    )
    await db_session.commit()

    response = await public_client.get(
        "/api/v1/capabilities",
        headers={"Authorization": f"Bearer {raw_key}"},
    )

    assert response.status_code == 200
    assert response.headers["X-RateLimit-Limit"] == "600"
    payload = response.json()
    assert payload["status"] == "ok"
    assert "extract_product" in payload["data"]["tools"]

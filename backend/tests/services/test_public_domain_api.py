from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.dependencies import get_db
from app.core.public_auth import hash_api_key
from app.main import app
from app.models.api_key import ApiKey
from app.models.domain_memory import DomainMemory, DomainRunProfile


@pytest.mark.asyncio
async def test_public_domain_info_reads_domain_memory(db_session, test_user) -> None:
    raw_key = "crawlerai_domain_key"
    db_session.add(ApiKey(user_id=test_user.id, name="domain", key_prefix="crawlerai", key_hash=hash_api_key(raw_key), is_active=True))
    db_session.add(
        DomainMemory(
            domain="example.com",
            surface="ecommerce_detail",
            selectors={"rules": [{"id": 1, "field_name": "title", "css_selector": "h1", "is_active": True}]},
        )
    )
    db_session.add(
        DomainRunProfile(
            domain="example.com",
            surface="ecommerce_detail",
            profile={"fetch_profile": {"fetch_mode": "http_only"}},
        )
    )
    await db_session.commit()

    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        response = await client.get(
            "/api/v1/domains/example.com",
            headers={"Authorization": f"Bearer {raw_key}"},
        )
    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()["data"]
    assert data["known"] is True
    assert data["has_cached_selectors"] is True
    assert data["acquisition_profile"] == "http_preferred"

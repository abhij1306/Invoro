from __future__ import annotations

from collections import deque

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.public.rate_limit import _retry_after, _trim
from app.core.dependencies import get_db
from app.core.public_auth import hash_api_key
from app.main import app, clear_rate_limit_buckets_for_testing
from app.models.api_key import ApiKey


@pytest.mark.asyncio
async def test_public_rate_limit_is_keyed_by_api_key(
    db_session,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("app.api.public.rate_limit.PUBLIC_API_READ_RATE_LIMIT", 2)
    monkeypatch.setattr("app.api.public.rate_limit.PUBLIC_API_READ_BURST_LIMIT", 2)
    clear_rate_limit_buckets_for_testing()
    raw_key = "crawlerai_rate_key"
    db_session.add(
        ApiKey(
            user_id=test_user.id,
            name="rate",
            key_prefix="crawlerai",
            key_hash=hash_api_key(raw_key),
            is_active=True,
        )
    )
    await db_session.commit()

    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as client:
        headers = {"Authorization": f"Bearer {raw_key}"}
        first = await client.get("/api/v1/capabilities", headers=headers)
        second = await client.get("/api/v1/capabilities", headers=headers)
        third = await client.get("/api/v1/capabilities", headers=headers)
    app.dependency_overrides.clear()
    clear_rate_limit_buckets_for_testing()

    assert first.status_code == 200
    assert second.status_code == 200
    assert third.status_code == 429
    assert third.json()["error"]["code"] == "RATE_LIMITED"


def test_trim_keeps_boundary_timestamp() -> None:
    bucket = deque([10.0, 11.0, 12.0])

    _trim(bucket, 11.0)

    assert list(bucket) == [11.0, 12.0]


def test_retry_after_rounds_up_remaining_window() -> None:
    assert _retry_after(deque([10.0]), now=68.1, window_seconds=60) == 2

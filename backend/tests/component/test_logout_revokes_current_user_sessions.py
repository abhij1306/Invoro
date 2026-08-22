from __future__ import annotations

from .test_login_returns_user_only_sets_cookie_env import ASGITransport, AsyncClient, app, create_user, pytest  # fmt: skip
from app.core.dependencies import get_current_user_optional
from app.main import (
    auth_rate_limit_buckets_snapshot,
    clear_auth_rate_limit_buckets_for_testing,
    restore_auth_rate_limit_buckets_for_testing,
)

pytest_plugins = ["tests.component.test_public_api"]


@pytest.mark.asyncio
@pytest.mark.component
async def test_logout_revokes_current_user_and_clears_cookie(
    public_api_client: AsyncClient,
    db_session,
) -> None:
    user = await create_user(db_session, "logout@example.com", "password123")
    original_token_version = int(user.token_version or 0)
    login_response = await public_api_client.post(
        "/api/auth/login",
        json={"email": user.email, "password": "password123"},
    )
    assert login_response.status_code == 200

    response = await public_api_client.post("/api/auth/logout", json={})

    assert response.status_code == 204
    assert "access_token=" in response.headers["set-cookie"]
    assert "Max-Age=0" in response.headers["set-cookie"]
    await db_session.refresh(user)
    assert user.token_version == original_token_version + 1
    assert (await public_api_client.get("/api/auth/me")).status_code == 401


@pytest.mark.asyncio
@pytest.mark.component
async def test_logout_is_idempotent_without_a_valid_session(
    public_api_client: AsyncClient,
) -> None:
    first = await public_api_client.post("/api/auth/logout", json={})
    second = await public_api_client.post("/api/auth/logout", json={})

    assert first.status_code == 204
    assert second.status_code == 204
    assert "Max-Age=0" in first.headers["set-cookie"]
    assert "Max-Age=0" in second.headers["set-cookie"]


@pytest.mark.asyncio
@pytest.mark.component
async def test_logout_does_not_revoke_another_user(
    public_api_client: AsyncClient,
    db_session,
) -> None:
    first_user = await create_user(db_session, "first@example.com", "password123")
    second_user = await create_user(db_session, "second@example.com", "password123")
    second_original_version = int(second_user.token_version or 0)
    await public_api_client.post(
        "/api/auth/login",
        json={"email": first_user.email, "password": "password123"},
    )
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as second_client:
        second_login = await second_client.post(
            "/api/auth/login",
            json={"email": second_user.email, "password": "password123"},
        )
        assert second_login.status_code == 200

        assert (
            await public_api_client.post("/api/auth/logout", json={})
        ).status_code == 204

        second_me = await second_client.get("/api/auth/me")
        assert second_me.status_code == 200
        assert second_me.json()["id"] == second_user.id
    await db_session.refresh(second_user)
    assert second_user.token_version == second_original_version


@pytest.mark.asyncio
@pytest.mark.component
async def test_logout_rate_limit_runs_before_optional_user_resolution(
    public_api_client: AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    previous_buckets = auth_rate_limit_buckets_snapshot()
    clear_auth_rate_limit_buckets_for_testing()
    user_resolution_calls = 0

    async def _resolve_optional_user():
        nonlocal user_resolution_calls
        user_resolution_calls += 1
        return None

    monkeypatch.setattr(
        "app.api.auth.auth_rate_limit",
        lambda route_group: 1 if route_group == "logout" else 100,
    )
    app.dependency_overrides[get_current_user_optional] = _resolve_optional_user
    try:
        first = await public_api_client.post("/api/auth/logout", json={})
        second = await public_api_client.post("/api/auth/logout", json={})
    finally:
        app.dependency_overrides.pop(get_current_user_optional, None)
        restore_auth_rate_limit_buckets_for_testing(previous_buckets)

    assert first.status_code == 204
    assert second.status_code == 429
    assert second.headers["Retry-After"]
    assert user_resolution_calls == 1

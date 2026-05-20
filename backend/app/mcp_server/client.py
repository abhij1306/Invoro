from __future__ import annotations

from typing import Any

import httpx

from app.services.config.public_api import PUBLIC_API_MCP_API_KEY_ENV


class PublicApiClient:
    def __init__(self, *, api_key: str, base_url: str) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    async def request(
        self,
        method: str,
        path: str,
        *,
        json: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self.api_key:
            return _tool_error("API_KEY_MISSING", f"{PUBLIC_API_MCP_API_KEY_ENV} is required")
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.request(
                method,
                f"{self.base_url}{path}",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json=json,
                params=params,
            )
        payload = _safe_json(response)
        if response.status_code >= 400:
            return _api_error(payload, fallback=response.text)
        return payload


def _safe_json(response: httpx.Response) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _api_error(payload: dict[str, Any], *, fallback: str) -> dict[str, Any]:
    error = payload.get("error")
    if not isinstance(error, dict):
        detail = payload.get("detail")
        error = detail.get("error") if isinstance(detail, dict) else None
    if isinstance(error, dict):
        return _tool_error(
            str(error.get("code") or "API_ERROR"),
            str(error.get("message") or "API error"),
        )
    return _tool_error("API_ERROR", fallback or "API error")


def _tool_error(code: str, message: str) -> dict[str, Any]:
    return {"status": "error", "error": {"code": code, "message": message}}

from __future__ import annotations

from typing import Any
from urllib.parse import quote

from app.mcp_server.client import PublicApiClient


async def extract_product(
    client: PublicApiClient,
    *,
    url: str,
    fields: list[str] | None = None,
    use_cache: bool = False,
) -> dict[str, Any]:
    return await client.request(
        "POST",
        "/extract",
        json={
            "url": url,
            "surface": "ecommerce",
            "fields": fields or [],
            "options": {"use_cache": use_cache},
        },
    )


async def check_domain(client: PublicApiClient, *, domain: str) -> dict[str, Any]:
    return await client.request("GET", f"/domains/{quote(domain, safe='')}")


async def list_capabilities(client: PublicApiClient) -> dict[str, Any]:
    return await client.request("GET", "/capabilities")

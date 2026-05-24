from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from app.services.ucp_audit.discovery import discover_ucp_manifest, link_header_ucp_url


@dataclass(slots=True)
class DummyPage:
    status_code: int
    html: str
    content_type: str = "application/json"
    final_url: str = "https://example.com/.well-known/ucp"
    redirect_chain: list[str] | None = None
    version_source: str = ""


@pytest.mark.asyncio
async def test_manifest_404_returns_not_found(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch_page(*args, **kwargs):
        return DummyPage(status_code=404, html="")

    monkeypatch.setattr(
        "app.services.ucp_audit.discovery._fetch_manifest_page",
        fake_fetch_page,
    )

    result = await discover_ucp_manifest("example.com")

    assert result.manifest_found is False
    assert result.manifest_valid is False
    assert result.raw_manifest is None
    assert result.errors == ["/.well-known/ucp returned 404"]


@pytest.mark.asyncio
async def test_valid_manifest_parses_capabilities(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch_page(*args, **kwargs):
        return DummyPage(
            status_code=200,
            html=json.dumps(
                {
                    "ucp": {
                        "version": "2026-04-08",
                        "services": {
                            "dev.ucp.shopping": [
                                {
                                    "version": "2026-04-08",
                                    "transport": "mcp",
                                    "endpoint": "https://example.com/api/ucp/mcp",
                                    "schema": "https://ucp.dev/shopping/mcp.openrpc.json",
                                }
                            ]
                        },
                        "capabilities": {
                            "dev.ucp.shopping.catalog.search": {
                                "version": "2026-04-08",
                                "schema": "https://ucp.dev/catalog_search.json"
                            },
                            "dev.ucp.shopping.catalog.lookup": {
                                "version": "2026-04-08",
                                "schema": "https://ucp.dev/catalog_lookup.json"
                            },
                            "dev.ucp.shopping.cart": {
                                "version": "2026-04-08",
                                "schema": "https://ucp.dev/cart.json",
                            },
                            "dev.ucp.shopping.checkout": {
                                "version": "2026-04-08",
                                "schema": "https://ucp.dev/checkout.json",
                            },
                            "dev.ucp.shopping.order": {
                                "version": "2026-04-08",
                                "schema": "https://ucp.dev/order.json",
                            },
                            "dev.ucp.shopping.fulfillment": {
                                "version": "2026-04-08",
                                "schema": "https://ucp.dev/fulfillment.json"
                            },
                            "dev.ucp.shopping.discount": {
                                "version": "2026-04-08",
                                "schema": "https://ucp.dev/discount.json",
                            },
                        },
                    },
                    "signing_keys": [],
                }
            ),
        )

    monkeypatch.setattr(
        "app.services.ucp_audit.discovery._fetch_manifest_page",
        fake_fetch_page,
    )

    result = await discover_ucp_manifest("https://example.com")

    assert result.manifest_found is True
    assert result.manifest_valid is True
    assert "dev.ucp.shopping.catalog.search" in result.capabilities_declared
    assert result.services_declared == ["dev.ucp.shopping"]
    assert result.transport_entries[0]["transport"] == "mcp"
    assert result.missing_required_capabilities == []


@pytest.mark.asyncio
async def test_supported_version_profile_can_declare_supported_versions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    current = {
        "ucp": {
            "version": "2025-01-01",
            "supported_versions": {
                "2026-04-08": "https://example.com/ucp/2026-04-08.json"
            },
            "services": {},
            "capabilities": {},
        },
        "signing_keys": [],
    }
    supported = {
        "ucp": {
            "version": "2026-04-08",
            "supported_versions": {
                "2026-04-08": "https://example.com/ucp/2026-04-08.json"
            },
            "services": {
                "dev.ucp.shopping": {"version": "2026-04-08", "transport": "mcp"}
            },
            "capabilities": {},
        },
        "signing_keys": [],
    }

    async def fake_fetch_page(url: str, *args, **kwargs):
        del args, kwargs
        if url.endswith("2026-04-08.json"):
            return DummyPage(status_code=200, html=json.dumps(supported), final_url=url)
        return DummyPage(status_code=200, html=json.dumps(current))

    monkeypatch.setattr(
        "app.services.ucp_audit.discovery._fetch_manifest_page",
        fake_fetch_page,
    )

    result = await discover_ucp_manifest("https://example.com")

    assert result.manifest_found is True
    assert result.version_source == "supported_versions"
    assert result.selected_version == "2026-04-08"
    assert "Version-specific UCP profile" not in " ".join(result.errors)


@pytest.mark.asyncio
async def test_supported_version_can_be_declared_without_profile_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "ucp": {
            "version": "2025-01-01",
            "supported_versions": ["2026-04-08"],
            "services": {
                "dev.ucp.shopping": {"version": "2026-04-08", "transport": "mcp"}
            },
            "capabilities": {},
        },
        "signing_keys": [],
    }

    async def fake_fetch_page(*args, **kwargs):
        del args, kwargs
        return DummyPage(status_code=200, html=json.dumps(payload))

    monkeypatch.setattr(
        "app.services.ucp_audit.discovery._fetch_manifest_page",
        fake_fetch_page,
    )

    result = await discover_ucp_manifest("https://example.com")

    assert result.manifest_found is True
    assert result.version_source == "supported_versions"
    assert result.raw_manifest == payload


@pytest.mark.asyncio
async def test_unsupported_version_is_not_target_manifest_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_fetch_page(*args, **kwargs):
        del args, kwargs
        return DummyPage(
            status_code=200,
            html=json.dumps({"ucp": {"version": "2025-01-01"}}),
        )

    monkeypatch.setattr(
        "app.services.ucp_audit.discovery._fetch_manifest_page",
        fake_fetch_page,
    )

    result = await discover_ucp_manifest("https://example.com")

    assert result.manifest_found is False
    assert "not declared" in result.errors[0]


def test_link_header_ucp_url_rejects_cross_origin_manifest() -> None:
    assert (
        link_header_ucp_url(
            '<https://evil.example/.well-known/ucp>; rel="ucp"',
            "https://example.com/",
        )
        == ""
    )


@pytest.mark.asyncio
async def test_link_header_fallback_uses_well_known_final_origin(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "ucp": {
            "version": "2026-04-08",
            "services": {
                "dev.ucp.shopping": {"version": "2026-04-08", "transport": "mcp"}
            },
            "capabilities": {},
        },
        "signing_keys": [],
    }
    fetched: list[str] = []

    async def fake_fetch_page(url: str, *args, **kwargs):
        del args, kwargs
        fetched.append(url)
        if url == "https://shop.example/.well-known/ucp":
            return DummyPage(
                status_code=404,
                html="",
                final_url="https://www.shop.example/.well-known/ucp",
            )
        return DummyPage(status_code=200, html=json.dumps(payload), final_url=url)

    async def fake_discover_link_manifest_url(value: str) -> str:
        assert value == "https://www.shop.example/.well-known/ucp"
        return "https://www.shop.example/ucp.json"

    monkeypatch.setattr(
        "app.services.ucp_audit.discovery._fetch_manifest_page",
        fake_fetch_page,
    )
    monkeypatch.setattr(
        "app.services.ucp_audit.discovery._discover_link_manifest_url",
        fake_discover_link_manifest_url,
    )

    result = await discover_ucp_manifest("https://shop.example")

    assert result.manifest_found is True
    assert result.discovery_source == "link-header"
    assert fetched == [
        "https://shop.example/.well-known/ucp",
        "https://www.shop.example/ucp.json",
    ]


@pytest.mark.asyncio
async def test_valid_manifest_accepts_ucp_services(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch_page(*args, **kwargs):
        return DummyPage(
            status_code=200,
            html=json.dumps(
                {
                    "ucp": {
                        "version": "2026-04-08",
                        "services": {
                            "dev.ucp.shopping": [
                                {
                                    "version": "2026-04-08",
                                    "transport": "mcp",
                                }
                            ]
                        },
                        "capabilities": {},
                    },
                    "signing_keys": [],
                }
            ),
        )

    monkeypatch.setattr(
        "app.services.ucp_audit.discovery._fetch_manifest_page",
        fake_fetch_page,
    )

    result = await discover_ucp_manifest("https://example.com")

    assert result.manifest_found is True
    assert result.manifest_valid is True
    assert result.capabilities_declared == []
    assert result.services_declared == ["dev.ucp.shopping"]
    assert result.missing_required_capabilities


@pytest.mark.asyncio
async def test_manifest_content_type_must_be_json(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch_page(*args, **kwargs):
        return DummyPage(
            status_code=200,
            content_type="text/html",
            html=json.dumps(
                {
                    "ucp": {
                        "version": "2026-04-08",
                        "services": {"dev.ucp.shopping": {"version": "2026-04-08", "transport": "mcp"}},
                        "capabilities": {},
                    },
                    "signing_keys": [],
                }
            ),
        )

    monkeypatch.setattr(
        "app.services.ucp_audit.discovery._fetch_manifest_page",
        fake_fetch_page,
    )

    result = await discover_ucp_manifest("example.com")

    assert result.manifest_found is True
    assert result.manifest_valid is False
    assert "Content-Type" in result.errors[0] or any("Content-Type" in item for item in result.errors)


@pytest.mark.asyncio
async def test_invalid_manifest_json_reports_error(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch_page(*args, **kwargs):
        return DummyPage(status_code=200, html="{not-json")

    monkeypatch.setattr(
        "app.services.ucp_audit.discovery._fetch_manifest_page",
        fake_fetch_page,
    )

    result = await discover_ucp_manifest("example.com")

    assert result.manifest_found is True
    assert result.manifest_valid is False
    assert result.raw_manifest is None
    assert result.errors

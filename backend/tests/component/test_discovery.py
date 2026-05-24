from __future__ import annotations

import json
from dataclasses import dataclass

import pytest
import httpx

from app.services.ucp_audit import discovery
from app.services.ucp_audit.discovery import (
    check_manifest_cache_headers,
    check_version_alignment,
    discover_ucp_manifest,
    link_header_ucp_url,
)


@dataclass(slots=True)
class DummyPage:
    status_code: int
    html: str
    content_type: str = "application/json"
    final_url: str = "https://example.com/.well-known/ucp"
    redirect_chain: list[str] | None = None
    version_source: str = ""
    headers: dict | None = None


class DummyAsyncClient:
    def __init__(self, response: httpx.Response) -> None:
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def get(self, url: str, *, headers: dict):
        del url, headers
        return self.response


@pytest.mark.asyncio
@pytest.mark.component
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
@pytest.mark.component
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
                                    "spec": "https://ucp.dev/spec",
                                }
                            ]
                        },
                        "capabilities": {
                            "dev.ucp.shopping.catalog.search": {
                                "version": "2026-04-08",
                                "schema": "https://ucp.dev/catalog_search.json",
                                "spec": "https://ucp.dev/spec",
                            },
                            "dev.ucp.shopping.catalog.lookup": {
                                "version": "2026-04-08",
                                "schema": "https://ucp.dev/catalog_lookup.json",
                                "spec": "https://ucp.dev/spec",
                            },
                            "dev.ucp.shopping.cart": {
                                "version": "2026-04-08",
                                "schema": "https://ucp.dev/cart.json",
                                "spec": "https://ucp.dev/spec",
                            },
                            "dev.ucp.shopping.checkout": {
                                "version": "2026-04-08",
                                "schema": "https://ucp.dev/checkout.json",
                                "spec": "https://ucp.dev/spec",
                            },
                            "dev.ucp.shopping.order": {
                                "version": "2026-04-08",
                                "schema": "https://ucp.dev/order.json",
                                "spec": "https://ucp.dev/spec",
                            },
                            "dev.ucp.shopping.fulfillment": {
                                "version": "2026-04-08",
                                "schema": "https://ucp.dev/fulfillment.json",
                                "spec": "https://ucp.dev/spec",
                            },
                            "dev.ucp.shopping.discount": {
                                "version": "2026-04-08",
                                "schema": "https://ucp.dev/discount.json",
                                "spec": "https://ucp.dev/spec",
                            },
                        },
                    },
                    "signing_keys": [
                        {"kid": "k1", "kty": "EC", "use": "sig", "alg": "ES256"}
                    ],
                }
            ),
            headers={"cache-control": "public, max-age=300"},
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
@pytest.mark.component
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
                "dev.ucp.shopping": {
                    "version": "2026-04-08",
                    "transport": "mcp",
                    "spec": "https://ucp.dev/spec",
                }
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
@pytest.mark.component
async def test_supported_version_profile_url_may_be_relative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "ucp": {
            "version": "2025-01-01",
            "supported_versions": {"2026-04-08": "/ucp/2026-04-08.json"},
            "services": {},
            "capabilities": {},
        },
        "signing_keys": [],
    }
    supported = {
        "ucp": {
            "version": "2026-04-08",
            "services": {
                "dev.ucp.shopping": {
                    "version": "2026-04-08",
                    "transport": "mcp",
                    "spec": "https://ucp.dev/spec",
                }
            },
            "capabilities": {},
        },
        "signing_keys": [],
    }

    async def fake_fetch_page(url: str, *args, **kwargs):
        del args, kwargs
        if url == "https://example.com/ucp/2026-04-08.json":
            return DummyPage(status_code=200, html=json.dumps(supported), final_url=url)
        return DummyPage(status_code=200, html=json.dumps(payload))

    monkeypatch.setattr(
        "app.services.ucp_audit.discovery._fetch_manifest_page",
        fake_fetch_page,
    )

    result = await discover_ucp_manifest("https://example.com")

    assert result.manifest_found is True
    assert result.version_source == "supported_versions"
    assert result.raw_manifest == supported


@pytest.mark.asyncio
@pytest.mark.component
async def test_supported_version_profile_list_may_be_relative(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "ucp": {
            "version": "2025-01-01",
            "supported_versions": [
                {"version": "2026-04-08", "url": "/ucp/2026-04-08.json"}
            ],
            "services": {},
            "capabilities": {},
        },
        "signing_keys": [],
    }
    supported = {
        "ucp": {
            "version": "2026-04-08",
            "services": {
                "dev.ucp.shopping": {
                    "version": "2026-04-08",
                    "transport": "mcp",
                    "spec": "https://ucp.dev/spec",
                }
            },
            "capabilities": {},
        },
        "signing_keys": [],
    }

    async def fake_fetch_page(url: str, *args, **kwargs):
        del args, kwargs
        if url == "https://example.com/ucp/2026-04-08.json":
            return DummyPage(status_code=200, html=json.dumps(supported), final_url=url)
        return DummyPage(status_code=200, html=json.dumps(payload))

    monkeypatch.setattr(
        "app.services.ucp_audit.discovery._fetch_manifest_page",
        fake_fetch_page,
    )

    result = await discover_ucp_manifest("https://example.com")

    assert result.manifest_found is True
    assert result.version_source == "supported_versions"
    assert result.raw_manifest == supported


@pytest.mark.asyncio
@pytest.mark.component
async def test_supported_version_string_list_declares_target(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "ucp": {
            "version": "2025-01-01",
            "supported_versions": ["2026-04-08"],
            "services": {},
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
    assert "not declared" not in " ".join(result.errors)


@pytest.mark.asyncio
@pytest.mark.component
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


@pytest.mark.component
def test_link_header_ucp_url_rejects_cross_origin_manifest() -> None:
    assert (
        link_header_ucp_url(
            '<https://evil.example/.well-known/ucp>; rel="ucp"',
            "https://example.com/",
        )
        == ""
    )


@pytest.mark.asyncio
@pytest.mark.component
async def test_link_header_discovery_uses_final_origin_after_root_redirect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    response = httpx.Response(
        200,
        headers={"link": '</ucp.json>; rel="ucp"'},
        request=httpx.Request("GET", "https://www.shop.example/"),
    )
    monkeypatch.setattr(
        "app.services.ucp_audit.discovery.build_async_http_client",
        lambda **kwargs: DummyAsyncClient(response),
    )

    assert await discovery._discover_link_manifest_url("https://shop.example") == (
        "https://www.shop.example/ucp.json"
    )


@pytest.mark.component
def test_manifest_cache_headers_validate_required_directives() -> None:
    assert check_manifest_cache_headers({})
    assert check_manifest_cache_headers({"cache-control": "public, max-age=300"}) == []


@pytest.mark.component
def test_version_alignment_detects_capability_mismatch() -> None:
    mismatches = check_version_alignment(
        [{"name": "dev.ucp.shopping", "version": "2026-04-08"}],
        [{"name": "dev.ucp.shopping.cart", "version": "2026-01-11"}],
        "dev.ucp.shopping",
    )

    assert mismatches
    assert (
        check_version_alignment(
            [{"name": "dev.ucp.shopping", "version": "2026-04-08"}],
            [{"name": "dev.ucp.shopping.cart", "version": "2026-04-08"}],
            "dev.ucp.shopping",
        )
        == []
    )


@pytest.mark.component
def test_manifest_shape_validates_signing_keys_as_security_errors() -> None:
    payload = {
        "ucp": {
            "version": "2026-04-08",
            "services": {},
            "capabilities": {},
        },
        "signing_keys": [{}],
    }

    structural_errors, security_errors = discovery._validate_manifest_shape(payload)

    assert structural_errors == []
    assert any("missing required JWK fields" in item for item in security_errors)

    payload["signing_keys"] = [
        {"kid": "k1", "kty": "EC", "use": "sig", "alg": "ES256", "crv": "P-256"}
    ]

    assert discovery._validate_manifest_shape(payload) == ([], [])


@pytest.mark.component
def test_entry_versions_require_spec_url() -> None:
    entries = [{"name": "dev.ucp.shopping", "version": "2026-04-08"}]
    discovery._validate_entry_versions(entries, "service")

    assert any("Missing spec URL" in item for item in entries[0]["_errors"])

    entries = [
        {
            "name": "dev.ucp.shopping",
            "version": "2026-04-08",
            "transport": "mcp",
            "spec": "https://ucp.dev/spec",
        }
    ]
    discovery._validate_entry_versions(entries, "service")

    assert "_errors" not in entries[0]


@pytest.mark.asyncio
@pytest.mark.component
async def test_link_header_fallback_uses_requested_origin_after_redirect(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    payload = {
        "ucp": {
            "version": "2026-04-08",
            "services": {
                "dev.ucp.shopping": {
                    "version": "2026-04-08",
                    "transport": "mcp",
                    "spec": "https://ucp.dev/spec",
                }
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
@pytest.mark.component
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
                                    "spec": "https://ucp.dev/spec",
                                }
                            ]
                        },
                        "capabilities": {},
                    },
                    "signing_keys": [
                        {"kid": "k1", "kty": "EC", "use": "sig", "alg": "ES256"}
                    ],
                }
            ),
            headers={"cache-control": "public, max-age=300"},
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
@pytest.mark.component
async def test_manifest_content_type_must_be_json(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake_fetch_page(*args, **kwargs):
        return DummyPage(
            status_code=200,
            content_type="text/html",
            html=json.dumps(
                {
                    "ucp": {
                        "version": "2026-04-08",
                        "services": {
                            "dev.ucp.shopping": {
                                "version": "2026-04-08",
                                "transport": "mcp",
                                "spec": "https://ucp.dev/spec",
                            }
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

    result = await discover_ucp_manifest("example.com")

    assert result.manifest_found is True
    assert result.manifest_valid is False
    assert "Content-Type" in result.errors[0] or any("Content-Type" in item for item in result.errors)


@pytest.mark.asyncio
@pytest.mark.component
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

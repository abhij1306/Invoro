from __future__ import annotations

import pytest

from app.services.config.ucp_audit import (
    D_UCP3_ID,
    FINDING_TRANSPORT_NEGOTIATION_INCOMPLETE,
)
from app.services.ucp_audit.protocol_checks import build_protocol_dimensions, probe_transports
from app.services.ucp_audit.types import UCPManifestResult, UCPSchemaProbe, UCPTransportProbe


def test_transport_profile_required_scores_partial() -> None:
    manifest = UCPManifestResult(
        manifest_found=True,
        manifest_valid=True,
        services_declared=["dev.ucp.shopping"],
        transport_entries=[
            {
                "service": "dev.ucp.shopping",
                "transport": "mcp",
                "endpoint": "https://example.com/api/ucp/mcp",
            }
        ],
    )
    dimensions = build_protocol_dimensions(
        manifest,
        [
            UCPTransportProbe(
                service="dev.ucp.shopping",
                transport="mcp",
                endpoint="https://example.com/api/ucp/mcp",
                reachable=True,
                negotiated=False,
                profile_required=True,
                status_code=422,
            )
        ],
        [],
    )

    transport = next(item for item in dimensions if item.dimension_id == D_UCP3_ID)

    assert transport.score == 70
    assert transport.findings[0].code == FINDING_TRANSPORT_NEGOTIATION_INCOMPLETE


@pytest.mark.asyncio
async def test_probe_transports_treats_embedded_schema_as_schema_dependent() -> None:
    manifest = UCPManifestResult(
        transport_entries=[
            {
                "service": "dev.ucp.shopping",
                "transport": "embedded",
                "schema": "https://ucp.dev/embedded.openrpc.json",
            }
        ]
    )

    probes = await probe_transports(manifest)

    assert probes[0].transport == "embedded"
    assert probes[0].reachable is False
    assert probes[0].negotiated is False
    assert probes[0].schema_url == "https://ucp.dev/embedded.openrpc.json"


def test_contract_dimensions_validate_payload_schema_groups() -> None:
    manifest = UCPManifestResult(
        manifest_found=True,
        manifest_valid=True,
        services_declared=["dev.ucp.shopping"],
        capabilities_declared=[
            "dev.ucp.shopping.catalog.search",
            "dev.ucp.shopping.catalog.lookup",
            "dev.ucp.shopping.cart",
            "dev.ucp.shopping.checkout",
            "dev.ucp.shopping.order",
            "dev.ucp.shopping.fulfillment",
            "dev.ucp.shopping.discount",
        ],
        payment_handlers=["com.google.pay"],
    )
    schema_probes = [
        UCPSchemaProbe(
            url="https://ucp.dev/catalog_search.json",
            reachable=True,
            valid_json=True,
            schema_valid=True,
            field_results={
                "catalog": {
                    "product_id": True,
                    "title": True,
                    "price": True,
                    "currency": True,
                    "availability": True,
                }
            },
        ),
        UCPSchemaProbe(
            url="https://ucp.dev/cart.json",
            reachable=True,
            valid_json=True,
            schema_valid=True,
            field_results={
                "cart_checkout": {
                    "cart_id": True,
                    "line_items": True,
                    "total": True,
                    "currency": True,
                }
            },
        ),
        UCPSchemaProbe(
            url="https://ucp.dev/order.json",
            reachable=True,
            valid_json=True,
            schema_valid=True,
            field_results={
                "order_policy": {
                    "order_id": True,
                    "status": True,
                    "fulfillment": True,
                }
            },
        ),
    ]

    dimensions = build_protocol_dimensions(manifest, [], schema_probes)
    scores = {item.dimension_id: item.score for item in dimensions}

    assert scores["D-UCP4"] == 100
    assert scores["D-UCP5"] == 100
    assert scores["D-UCP6"] == 100


def test_schema_url_keywords_do_not_score_without_fields() -> None:
    manifest = UCPManifestResult(
        manifest_found=True,
        manifest_valid=True,
        services_declared=["dev.ucp.shopping"],
        capabilities_declared=[
            "dev.ucp.shopping.catalog.search",
            "dev.ucp.shopping.catalog.lookup",
        ],
    )
    schema_probes = [
        UCPSchemaProbe(
            url="https://ucp.dev/catalog_search.json",
            reachable=True,
            valid_json=True,
            schema_valid=True,
            title="Catalog Search",
            field_results={"catalog": {"product_id": False, "title": False, "price": False, "currency": False, "availability": False}},
        )
    ]

    dimensions = build_protocol_dimensions(manifest, [], schema_probes)
    scores = {item.dimension_id: item.score for item in dimensions}

    assert scores["D-UCP4"] == 60

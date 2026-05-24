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
async def test_probe_transports_treats_embedded_schema_as_declared_only() -> None:
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
    assert probes[0].reachable is True
    assert probes[0].negotiated is False


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
        UCPSchemaProbe(url="https://ucp.dev/catalog_search.json", reachable=True, valid_json=True),
        UCPSchemaProbe(url="https://ucp.dev/catalog_lookup.json", reachable=True, valid_json=True),
        UCPSchemaProbe(url="https://ucp.dev/cart.json", reachable=True, valid_json=True),
        UCPSchemaProbe(url="https://ucp.dev/checkout.json", reachable=True, valid_json=True),
        UCPSchemaProbe(url="https://ucp.dev/order.json", reachable=True, valid_json=True),
        UCPSchemaProbe(url="https://ucp.dev/fulfillment.json", reachable=True, valid_json=True),
        UCPSchemaProbe(url="https://ucp.dev/discount.json", reachable=True, valid_json=True),
    ]

    dimensions = build_protocol_dimensions(manifest, [], schema_probes)
    scores = {item.dimension_id: item.score for item in dimensions}

    assert scores["D-UCP4"] == 100
    assert scores["D-UCP5"] == 100
    assert scores["D-UCP6"] == 100

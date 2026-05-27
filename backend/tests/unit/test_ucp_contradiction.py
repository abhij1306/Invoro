from __future__ import annotations

import pytest

from app.services.ucp_audit.contradiction import detect_contradictions
from app.services.ucp_audit.evidence import EvidencePacket


def _packet(**overrides) -> EvidencePacket:
    values = {
        "url": "https://example.com/p/1",
        "jsonld_product_blocks": [
            {
                "@type": "Product",
                "name": "Ready to Apply Fresh Henna Paste",
                "offers": {"price": "429", "availability": "InStock"},
            }
        ],
        "og_tags": {
            "og:title": "Ready-to-Apply Fresh Henna Paste for Hair, Herbal Hair Color"
        },
        "dom_fields": {"price": "221", "availability": "in_stock"},
        "extracted_record": {
            "variants": [{"sku": "SKU-1", "price": "221"}, {"sku": "SKU-2", "price": "429"}]
        },
        "robots_allows_perplexitybot": True,
        "robots_allows_gptbot": True,
        "sitemap_found": True,
    }
    values.update(overrides)
    return EvidencePacket(**values)


@pytest.mark.unit
def test_price_values_are_not_used_as_contradictions() -> None:
    flags = detect_contradictions(_packet())

    assert [flag.field for flag in flags] == []


@pytest.mark.unit
def test_real_availability_mismatch_is_contradiction() -> None:
    flags = detect_contradictions(
        _packet(dom_fields={"price": "221", "availability": "out of stock"})
    )

    assert [flag.field for flag in flags] == ["availability"]

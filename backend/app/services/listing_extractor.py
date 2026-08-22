from __future__ import annotations

from typing import Any
from app.services.extraction_context import ExtractionContext, collect_structured_source_payloads
from .listing_stages import apply_listing_integrity_gate, extract_listing_records as _extract_listing_records

def extract_listing_records(
    html: str, page_url: str, surface: str, *,
    max_records: int,
    artifacts: dict[str, object] | None = None,
    selector_rules: list[dict[str, object]] | None = None,
    network_payloads: list[dict[str, object]] | None = None,
    record_dom_observed_selectors: bool = False,
    context: ExtractionContext | None = None,
) -> list[dict[str, Any]]:
    return _extract_listing_records(
        html, page_url, surface,
        max_records=max_records, artifacts=artifacts, selector_rules=selector_rules, network_payloads=network_payloads,
        record_dom_observed_selectors=record_dom_observed_selectors,
        context=context,
        structured_payload_collector=collect_structured_source_payloads,
    )

__all__ = ("apply_listing_integrity_gate", "extract_listing_records")

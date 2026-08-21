from __future__ import annotations

import pytest

from selectolax.lexbor import LexborHTMLParser

from app.services.adapters import amazon

from app.services.adapters.adp import ADPAdapter

from app.services.adapters.amazon import AmazonAdapter

from app.services.adapters.belk import BelkAdapter

from app.services.adapters.bullhorn import BullhornAdapter

from app.services.adapters.ebay import EbayAdapter

from app.services.adapters.indeed import IndeedAdapter

from app.services.adapters.linkedin import LinkedInAdapter

from app.services.adapters.nike import NikeAdapter

from app.services.config.runtime_settings import crawler_runtime_settings

from app.services.extract.detail.assembly.record_assembly import (
    build_detail_record,
    extract_detail_records,
)

from app.services.extract.field_candidates.structured_payloads import (
    collect_structured_candidates,
)

from app.services.extract.field_candidates.variant_rows import (
    _structured_variants_from_product_payload,
)

from app.services.extraction_html_helpers import extract_job_sections

from app.services.listing_extractor import extract_listing_records

from app.services.pipeline.extract_records import extract_records

from app.services.dom.xpath_service import extract_selector_value

from tests.fixtures.loader import read_optional_artifact_text


__all__ = ['ADPAdapter', 'AmazonAdapter', 'BelkAdapter', 'BullhornAdapter', 'EbayAdapter', 'IndeedAdapter', 'LexborHTMLParser', 'LinkedInAdapter', 'NikeAdapter', '_structured_variants_from_product_payload', 'amazon', 'annotations', 'build_detail_record', 'collect_structured_candidates', 'crawler_runtime_settings', 'extract_detail_records', 'extract_job_sections', 'extract_listing_records', 'extract_records', 'extract_selector_value', 'pytest', 'read_optional_artifact_text']  # fmt: skip

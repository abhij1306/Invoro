from __future__ import annotations

from pathlib import Path

import pytest

from app.services.dom.html_parser import BeautifulSoup

from selectolax.lexbor import LexborHTMLParser

from app.services.extract.detail.assembly import dom_completion as detail_dom_completion

from app.services.extract.detail.images import materialize as detail_image_materialize

from app.services.extract.detail.identity import (
    structured_pruning as detail_structured_pruning,
)

from app.services.config._export_data import load_export_data

from app.services.extraction_context import (
    ExtractionContext,
    collect_structured_source_payloads,
    prepare_extraction_context,
)

from app.services.pipeline.extract_records import extract_records

from app.services.selector_self_heal import (
    validated_xpath_rules,
    selector_heal_improved_record,
    reduce_html_for_selector_synthesis,
    selector_self_heal_targets,
)

requires_dom_completion = detail_dom_completion._requires_dom_completion

materialize_image_fields = detail_image_materialize._materialize_image_fields

prune_irrelevant_detail_structured_payload = (
    detail_structured_pruning._prune_irrelevant_detail_structured_payload
)


__all__ = ['BeautifulSoup', 'ExtractionContext', 'LexborHTMLParser', 'Path', 'annotations', 'collect_structured_source_payloads', 'detail_dom_completion', 'detail_image_materialize', 'detail_structured_pruning', 'extract_records', 'load_export_data', 'materialize_image_fields', 'prepare_extraction_context', 'prune_irrelevant_detail_structured_payload', 'pytest', 'reduce_html_for_selector_synthesis', 'requires_dom_completion', 'selector_heal_improved_record', 'selector_self_heal_targets', 'validated_xpath_rules']  # fmt: skip

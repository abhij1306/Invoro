from __future__ import annotations

from typing import Any

from app.services.config.extraction_rules import DOM_VARIANT_CARTESIAN_COMBO_LIMIT, VARIANT_CHOICE_OPTION_LIMIT
from app.services.dom.html_parser import BeautifulSoup

from . import dom_group_pipeline, dom_variant_support
from .dom_variant_support import existing_variant_cluster_has_transport_signal, primary_dom_context, record_has_rich_existing_variants

__all__ = ("existing_variant_cluster_has_transport_signal", "primary_dom_context", "record_has_rich_existing_variants", "extract_variants_from_dom", "backfill_variants_from_dom_if_missing")

def extract_variants_from_dom(
    soup: BeautifulSoup,
    *,
    page_url: str,
    js_state_objects: dict[str, Any] | None = None,
) -> dict[str, object]:
    dom_variant_support.DOM_VARIANT_CARTESIAN_COMBO_LIMIT = DOM_VARIANT_CARTESIAN_COMBO_LIMIT
    dom_variant_support.VARIANT_CHOICE_OPTION_LIMIT = VARIANT_CHOICE_OPTION_LIMIT
    return dom_group_pipeline.extract_variants_from_dom(soup, page_url=page_url, js_state_objects=js_state_objects)


def backfill_variants_from_dom_if_missing(
    record: dict[str, Any],
    *,
    soup: BeautifulSoup,
    page_url: str,
    js_state_objects: dict[str, Any] | None = None,
) -> None:
    dom_variant_support.DOM_VARIANT_CARTESIAN_COMBO_LIMIT = DOM_VARIANT_CARTESIAN_COMBO_LIMIT
    dom_variant_support.VARIANT_CHOICE_OPTION_LIMIT = VARIANT_CHOICE_OPTION_LIMIT
    dom_group_pipeline.backfill_variants_from_dom_if_missing(record, soup=soup, page_url=page_url, js_state_objects=js_state_objects)


def _collect_variant_choice_entries(*args: Any, **kwargs: Any) -> Any:
    dom_variant_support.VARIANT_CHOICE_OPTION_LIMIT = VARIANT_CHOICE_OPTION_LIMIT
    return dom_variant_support._collect_variant_choice_entries(*args, **kwargs)


def _merge_state_axis_metadata(axis_metadata: dict[str, dict[str, object]], state_targets: dict[str, dict[str, object]]) -> None:
    dom_group_pipeline._merge_state_axis_metadata(axis_metadata, state_targets)

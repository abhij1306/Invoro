from __future__ import annotations

import json

from types import SimpleNamespace

import pytest

from app.services.dom.html_parser import BeautifulSoup

from app.services.extract.detail.assembly import record_assembly

from app.services.extract.detail.assembly.record_assembly import build_detail_record

from app.services.extract import variant_choice_traversal

from app.services.extract.variant_choice_traversal import (
    iter_variant_choice_groups,
    iter_variant_select_groups,
    resolve_variant_group_name,
)

from app.services.extract.variant_axis import (
    normalized_variant_axis_key,
    variant_axis_name_is_semantic,
)

from app.services.extract.variant_identity_merge import (
    axis_values_are_mislabeled_duplicate,
    resolve_variants,
)

from app.services.extract.variant_option_value import (
    variant_option_value_is_noise,
)

from app.services.extract.variant_choice_traversal import (
    infer_variant_group_name_from_values,
)

from app.services.extract.detail.variants.dom_extraction import (
    backfill_variants_from_dom_if_missing,
    extract_variants_from_dom,
)

variant_choice_container_for_input = (
    variant_choice_traversal._variant_choice_container_for_input
)

variant_choice_container_is_overbroad = (
    variant_choice_traversal._variant_choice_container_is_overbroad
)

def _next_f_script(fragment: str) -> str:
    return f"<script>self.__next_f.push([1,{json.dumps(fragment)}])</script>"


__all__ = ['BeautifulSoup', 'SimpleNamespace', '_next_f_script', 'annotations', 'axis_values_are_mislabeled_duplicate', 'backfill_variants_from_dom_if_missing', 'build_detail_record', 'extract_variants_from_dom', 'infer_variant_group_name_from_values', 'iter_variant_choice_groups', 'iter_variant_select_groups', 'json', 'normalized_variant_axis_key', 'pytest', 'record_assembly', 'resolve_variant_group_name', 'resolve_variants', 'variant_axis_name_is_semantic', 'variant_choice_container_for_input', 'variant_choice_container_is_overbroad', 'variant_choice_traversal', 'variant_option_value_is_noise']  # fmt: skip

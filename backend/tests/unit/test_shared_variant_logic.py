from __future__ import annotations

import json

from types import SimpleNamespace

import pytest

from app.services.dom.html_parser import BeautifulSoup

from app.services.extract.detail.assembly import record_assembly

from app.services.extract.detail.assembly.record_assembly import build_detail_record

from app.services.extract.variant_choice_collection import (
    iter_variant_choice_groups,
    iter_variant_select_groups,
    variant_choice_container_for_input,
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
    resolve_variant_group_name,
    variant_choice_container_is_overbroad,
)

from app.services.extract.detail.variants.dom_extraction import (
    backfill_variants_from_dom_if_missing,
    extract_variants_from_dom,
)
from app.services.extract.detail.variants.dom_merge import (
    expand_existing_variants_with_dom_axes,
)


@pytest.mark.unit
def test_dom_axis_expansion_preserves_identity_only_for_one_to_one_rows() -> None:
    existing = [
        {
            "sku": "sku-m",
            "variant_id": "variant-m",
            "barcode": "12345678",
            "size": "M",
            "price": "10.00",
        }
    ]

    one_to_one = expand_existing_variants_with_dom_axes(
        existing,
        [{"color": "Blue"}],
    )
    one_to_many = expand_existing_variants_with_dom_axes(
        existing,
        [{"color": "Blue"}, {"color": "Red"}],
    )

    assert one_to_one[0]["sku"] == "sku-m"
    assert one_to_one[0]["variant_id"] == "variant-m"
    assert one_to_one[0]["barcode"] == "12345678"
    assert all("sku" not in row for row in one_to_many)
    assert all("variant_id" not in row for row in one_to_many)
    assert all("barcode" not in row for row in one_to_many)
    assert all(row["price"] == "10.00" for row in one_to_many)


def _next_f_script(fragment: str) -> str:
    return f"<script>self.__next_f.push([1,{json.dumps(fragment)}])</script>"


__all__ = ['BeautifulSoup', 'SimpleNamespace', '_next_f_script', 'annotations', 'axis_values_are_mislabeled_duplicate', 'backfill_variants_from_dom_if_missing', 'build_detail_record', 'extract_variants_from_dom', 'infer_variant_group_name_from_values', 'iter_variant_choice_groups', 'iter_variant_select_groups', 'json', 'normalized_variant_axis_key', 'pytest', 'record_assembly', 'resolve_variant_group_name', 'resolve_variants', 'variant_axis_name_is_semantic', 'variant_choice_container_for_input', 'variant_choice_container_is_overbroad', 'variant_option_value_is_noise']  # fmt: skip

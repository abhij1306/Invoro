from __future__ import annotations

from app.services.config import field_mappings, selectors


def test_field_mappings_static_exports_exist_in_module_dict() -> None:
    assert field_mappings.__dict__["CANONICAL_SCHEMAS"]


def test_selectors_static_exports_exist_in_module_dict() -> None:
    assert selectors.__dict__["ANCHOR_SELECTOR"] == "a[href]"

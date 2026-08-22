from __future__ import annotations

import pytest

from harness.harness_user import _is_production_environment
from harness.quality_evaluator import _quality_repair_diagnostics_ok
from harness.site_sets import build_explicit_sites, parse_test_sites_markdown


@pytest.mark.regression
def test_harness_environment_fails_closed_when_unspecified(monkeypatch) -> None:
    for name in ("APP_ENV", "FLASK_ENV", "ENV"):
        monkeypatch.delenv(name, raising=False)

    assert _is_production_environment() is True

    monkeypatch.setenv("APP_ENV", "test")
    assert _is_production_environment() is False


@pytest.mark.regression
def test_repair_diagnostics_requires_truthy_self_heal_trigger() -> None:
    result = {
        "sample_record_data": {
            "title": "Widget",
            "price": None,
            "image_url": "image.jpg",
        },
        "sample_source_trace": {"extraction": {"self_heal": {"triggered": False}}},
    }
    expectations = {"require_repair_diagnostics": True}

    assert _quality_repair_diagnostics_ok(result, expectations=expectations) is False

    result["sample_source_trace"]["extraction"]["self_heal"]["triggered"] = True
    assert _quality_repair_diagnostics_ok(result, expectations=expectations) is True


@pytest.mark.regression
def test_explicit_sites_keep_surface_alignment_across_blank_urls() -> None:
    rows = build_explicit_sites(
        ["https://example.com/list", "", "https://example.com/item"],
        explicit_surfaces=["ecommerce_listing", "", "ecommerce_detail"],
    )

    assert [row["surface"] for row in rows] == [
        "ecommerce_listing",
        "ecommerce_detail",
    ]


@pytest.mark.regression
def test_markdown_parser_keeps_scanning_after_surface_cell(tmp_path) -> None:
    fixture = tmp_path / "sites.md"
    fixture.write_text(
        "| Name | Surface | URL |\n"
        "| Product | detail | https://example.com/products/1 |\n",
        encoding="utf-8",
    )

    rows = parse_test_sites_markdown(fixture, start_line=1)

    assert rows == [
        {
            "name": "https://example.com/products/1",
            "url": "https://example.com/products/1",
            "surface": "ecommerce_detail",
        }
    ]

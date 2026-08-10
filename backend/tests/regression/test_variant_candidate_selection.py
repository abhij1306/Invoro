from __future__ import annotations

import pytest

from app.services.dom.html_parser import BeautifulSoup
from app.services.extract.detail.variants import dom_extraction


def _variant_container(generic_toggle_count: int):
    generic_toggles = "".join(
        '<button aria-pressed="false">Share</button>'
        for _index in range(generic_toggle_count)
    )
    soup = BeautifulSoup(
        f"""
        <html><body>
          <div data-option-name="size">
            {generic_toggles}
            <a href="/products/widget-small">Small</a>
            <a href="/products/widget-medium">Medium</a>
          </div>
        </body></html>
        """,
        "html.parser",
    )
    return soup.select_one("[data-option-name='size']")


@pytest.mark.regression
def test_generic_aria_pressed_controls_do_not_suppress_weak_variant_fallback() -> None:
    entries = dom_extraction._collect_variant_choice_entries(
        _variant_container(2),
        page_url="https://example.com/products/widget",
    )

    assert {entry["value"] for entry in entries} == {"Small", "Medium"}


@pytest.mark.regression
def test_generic_controls_do_not_consume_variant_candidate_cap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(dom_extraction, "VARIANT_CHOICE_OPTION_LIMIT", 2)

    entries = dom_extraction._collect_variant_choice_entries(
        _variant_container(5),
        page_url="https://example.com/products/widget",
    )

    assert {entry["value"] for entry in entries} == {"Small", "Medium"}

from __future__ import annotations

import pytest

from app.services.dom.html_parser import BeautifulSoup, InvalidSelectorError
from app.services.dom.query import safe_select
from app.services.dom.section_extraction import (
    extract_heading_sections,
    extract_section_content,
)
from app.services.dom.selector_engine import extract_node_value

pytestmark = pytest.mark.unit


def test_safe_select_swallows_only_invalid_selector_syntax() -> None:
    soup = BeautifulSoup("<div class='product'></div>", "html.parser")

    assert safe_select(soup, "div:???") == []

    class InvalidRoot:
        def select(self, _selector: str) -> list[object]:
            raise InvalidSelectorError("bad selector")

    class BrokenRoot:
        def select(self, _selector: str) -> list[object]:
            raise RuntimeError("wrapper failed")

    assert safe_select(InvalidRoot(), ".product") == []
    with pytest.raises(RuntimeError, match="wrapper failed"):
        safe_select(BrokenRoot(), ".product")


def test_html_node_select_swallows_only_parser_selector_errors() -> None:
    soup = BeautifulSoup("<div></div>", "html.parser")

    assert soup.select("div:???") == []


def test_attrs_returns_live_attribute_mapping() -> None:
    soup = BeautifulSoup("<div id='item' data-state='old'></div>", "html.parser")
    node = soup.find("div")
    assert node is not None

    attrs = node.attrs
    attrs["data-state"] = "new"
    attrs.pop("id")

    assert node.get("data-state") == "new"
    assert node.get("id") is None


def test_find_all_class_alias_matches_class_tokens() -> None:
    soup = BeautifulSoup(
        "<article class='product card'></article><article class='product-card'></article>",
        "html.parser",
    )

    matches = soup.find_all("article", class_="product")

    assert len(matches) == 1
    assert matches[0].get("class") == "product card"


def test_css_attribute_string_handles_quotes_backslashes_and_controls() -> None:
    soup = BeautifulSoup(
        '<button aria-controls="details\'panel\\main&#10;">Materials</button>'
        '<section id="details\'panel\\main&#10;">Material and care instructions.</section>',
        "html.parser",
    )
    trigger = soup.find("button")
    assert trigger is not None

    assert "Material and care" in extract_section_content(trigger, soup)


def test_navigation_anchor_is_not_extracted_as_section() -> None:
    soup = BeautifulSoup(
        """
        <html><body>
          <nav><a href="#specifications">Specifications</a></nav>
          <section id="specifications">Technical specifications and product dimensions.</section>
        </body></html>
        """,
        "html.parser",
    )

    assert "Specifications" not in extract_heading_sections(soup)


def test_variant_option_text_keeps_direct_text_without_dropped_child_text() -> None:
    soup = BeautifulSoup(
        "<button>Blue <span>Sold out</span><span>Limited edition</span></button>",
        "html.parser",
    )
    node = soup.find("button")
    assert node is not None

    assert extract_node_value(node, "color", "https://example.com/item") == (
        "Blue Limited edition"
    )

from __future__ import annotations

import pytest

from app.services import extraction_context as extraction_context_module
from app.services.extraction_context import prepare_extraction_context
from app.services.extract.detail.assembly.record_assembly import build_detail_record
from app.services.listing_extractor import extract_listing_records


@pytest.mark.regression
def test_detail_extractor_builds_each_working_dom_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser_builds = 0
    real_parser = extraction_context_module.LexborHTMLParser

    def _counting_parser(html: str):
        nonlocal parser_builds
        parser_builds += 1
        return real_parser(html)

    monkeypatch.setattr(extraction_context_module, "LexborHTMLParser", _counting_parser)
    record = build_detail_record(
        "<html><body><main><h1>Widget Prime</h1></main></body></html>",
        "https://example.com/products/widget-prime",
        "ecommerce_detail",
        ["title", "variants"],
        adapter_records=[
            {
                "title": "Widget Prime",
                "variants": [
                    {"sku": "W-1", "size": "Small", "price": "19.99"},
                    {"sku": "W-2", "size": "Large", "price": "21.99"},
                ],
            }
        ],
    )

    assert record["variant_count"] == 2
    assert parser_builds == 3


@pytest.mark.regression
def test_extraction_context_caches_pruned_dom() -> None:
    context = prepare_extraction_context(
        "<html><body><main><h1>Widget</h1></main></body></html>"
    )

    pruned_soup = context.pruned_soup(context.soup)
    assert context.pruned_soup(context.soup) is pruned_soup

    second_html = "<html><body><main><h1>Second Widget</h1></main></body></html>"
    assert (
        context.pruned_soup(prepare_extraction_context(second_html).soup)
        is not pruned_soup
    )


@pytest.mark.regression
def test_detail_extractor_keeps_pruned_parser_paired_with_pruned_soup() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
          {"@type":"Product","name":"Wrong Widget","url":"/products/wrong-widget"}
        </script>
      </head>
      <body>
        <main>
          <h1>Wrong Widget</h1>
          <h1>Right Widget</h1>
        </main>
      </body>
    </html>
    """

    record = build_detail_record(
        html,
        "https://example.com/products/right-widget",
        "ecommerce_detail",
        ["title"],
        requested_page_url="https://example.com/products/right-widget",
    )

    assert record["title"] == "Right Widget"


@pytest.mark.regression
def test_listing_extractor_builds_three_working_doms_for_rendered_fragments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parser_builds = 0
    real_parser = extraction_context_module.LexborHTMLParser

    def _counting_parser(html: str):
        nonlocal parser_builds
        parser_builds += 1
        return real_parser(html)

    monkeypatch.setattr(extraction_context_module, "LexborHTMLParser", _counting_parser)
    fragments = [
        "<article><a href='/products/one'><h2>Widget One</h2></a><span>$10.00</span></article>",
        "<article><a href='/products/two'><h2>Widget Two</h2></a><span>$20.00</span></article>",
    ]

    rows = extract_listing_records(
        "<html><body><main><h1>Widgets</h1></main></body></html>",
        "https://example.com/collections/widgets",
        "ecommerce_listing",
        max_records=10,
        artifacts={"rendered_listing_fragments": fragments},
    )

    assert len(rows) == 2
    assert parser_builds == 3


@pytest.mark.regression
def test_listing_extractor_recovers_partial_rendered_fragment_noise_removal() -> None:
    fragments = [
        "<main><article><a href='/products/one'><h2>Product One</h2></a></article></main>",
        "<nav><article><a href='/products/two'><h2>Product Two</h2></a></article></nav>",
        "<nav><article><a href='/products/three'><h2>Product Three</h2></a></article></nav>",
    ]

    rows = extract_listing_records(
        "<html><body><main><h1>Widgets</h1></main></body></html>",
        "https://example.com/collections/widgets",
        "ecommerce_listing",
        max_records=10,
        artifacts={"rendered_listing_fragments": fragments},
    )

    assert {row["title"] for row in rows} == {
        "Product One",
        "Product Two",
        "Product Three",
    }


@pytest.mark.regression
def test_vtex_listing_slug_encodes_path_and_traversal_separators() -> None:
    item = extraction_context_module._vtex_listing_item(
        "Product:1",
        {"productName": "Widget", "linkText": "../admin/item"},
        state={},
        base_origin="https://example.com",
    )

    assert item is not None
    assert item["url"] == "https://example.com/%2E%2E%2Fadmin%2Fitem/p"

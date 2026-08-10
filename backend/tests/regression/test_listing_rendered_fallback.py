from __future__ import annotations

import pytest

from app.services.listing_extractor import extract_listing_records


@pytest.mark.regression
def test_listing_extractor_retries_rendered_fragments_with_original_dom() -> None:
    rows = extract_listing_records(
        "<html><body><main><h1>Widgets</h1></main></body></html>",
        "https://example.com/collections/widgets",
        "ecommerce_listing",
        max_records=10,
        artifacts={
            "rendered_listing_fragments": [
                """
                <form>
                  <article>
                    <a href='/products/widget'><h2>Widget</h2></a>
                    <span>$19.99</span>
                  </article>
                </form>
                """
            ]
        },
    )

    assert len(rows) == 1
    assert rows[0]["title"] == "Widget"

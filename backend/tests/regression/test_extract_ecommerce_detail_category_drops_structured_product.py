from __future__ import annotations

from .test_detail_extractor_structured_sources import (
    build_detail_record,
    extract_records,
    pytest,
    structured_feature_rows,
)


@pytest.mark.regression
def test_extract_ecommerce_detail_category_drops_structured_product_crumb() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "BreadcrumbList",
          "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Products"},
            {
              "@type": "ListItem",
              "position": 2,
              "name": "Analytical Chromatography"
            },
            {
              "@type": "ListItem",
              "position": 3,
              "name": "SP<SUP>&reg;</SUP>-2560 Capillary GC Column (24056)"
            }
          ]
        }
        </script>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "SP®-2560 Capillary GC Column",
          "sku": "24056SUPELCO",
          "productID": "24056",
          "offers": {"price": "141894.10", "priceCurrency": "INR"}
        }
        </script>
      </head>
      <body><main><h1>SP®-2560 Capillary GC Column</h1></main></body>
    </html>
    """

    record = build_detail_record(
        html,
        "https://www.sigmaaldrich.com/IN/en/product/supelco/24056",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "SP®-2560 Capillary GC Column",
                "sku": "24056SUPELCO",
                "price": "141894.10",
                "currency": "INR",
            }
        ],
    )

    assert record["category"] == "Products > Analytical Chromatography"


@pytest.mark.regression
def test_extract_ecommerce_detail_keeps_structured_subscript_feature_label() -> None:
    features = structured_feature_rows(
        {
            "@type": "Product",
            "additionalProperty": [
                {
                    "@type": "PropertyValue",
                    "name": "material",
                    "value": ["fused silica"],
                },
                {"@type": "PropertyValue", "name": "Beta value", "value": ["313"]},
                {
                    "@type": "PropertyValue",
                    "name": "d<SUB>f</SUB>",
                    "value": ["0.20\xa0μm", "<span>0.25\xa0μm</span>"],
                },
                {
                    "@type": "PropertyValue",
                    "name": "L × I.D.",
                    "value": ["100\xa0m × 0.25\xa0mm"],
                },
            ],
        },
        "https://www.sigmaaldrich.com/IN/en/product/supelco/24056",
    )

    assert "df: 0.20 μm; 0.25 μm" in features
    assert "d" not in features
    assert "f" not in features
    assert ": ['0.20 μm'" not in features


@pytest.mark.regression
def test_extract_ecommerce_detail_prefers_visible_description_panel_without_inference() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "SP®-2560 Capillary GC Column",
          "sku": "24056SUPELCO",
          "description": "SP®-2560 Capillary GC Column L × I.D. 100 m × 0.25 mm, df 0.20 μm; Synonyms: SP-2560, 100M.20UM.25MM at Sigma-Aldrich",
          "offers": {"price": "141894.10", "priceCurrency": "INR"}
        }
        </script>
      </head>
      <body>
        <main>
          <h1>SP®-2560 Capillary GC Column</h1>
          <div class="skipToContainer">
            <div class="jumpLink"><button>Description</button></div>
            <div class="jumpLink">Compare Similar Items</div>
          </div>
          <div class="product-shell"><div><div><div><div><div><div>
            <div class="productDescriptions">
              <div>
                <button id="pdp-description"><p>Description</p></button>
              </div>
              <div class="MuiCollapse-root">
                <div class="MuiCollapse-wrapper">
                  <div class="MuiCollapse-wrapperInner">
                    <div class="accordionBody">
                      <div class="descriptionContainer">
                        <div class="descriptionItem">
                          <h3>General description</h3>
                          <div class="description">
                            <b>Application</b>: This highly polar biscyanopropyl column was specifically designed for detailed
                            separation of geometricpositional (cis/trans) isomers of fatty acid methyl esters (FAMEs).
                            It is extremely effective for FAME isomer applications.
                            <br><b>USP Code</b>: This column meets USP G5 requirements.
                          </div>
                        </div>
                        <div class="descriptionItem">
                          <h3>Application</h3>
                          <div class="description">
                            The SP-2560 Capillary GC Columns meets the requirements as a USP G5 and AOAC® designation.
                            They are specifically designed for the detailed separation of geometric and positional isomers.
                          </div>
                        </div>
                        <div class="descriptionItem">
                          <h3>Legal Information</h3>
                          <div class="description">AOAC is a registered trademark of AOAC International</div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div></div></div></div></div></div></div>
        </main>
      </body>
    </html>
    """

    record = build_detail_record(
        html,
        "https://www.sigmaaldrich.com/IN/en/product/supelco/24056",
        "ecommerce_detail",
        ["description", "product_details"],
    )

    assert "This highly polar biscyanopropyl column" in record["description"]
    assert "They are specifically designed" in record["description"]
    assert "Synonyms: SP-2560" not in record["description"]
    assert "Compare Similar Items" not in record["description"]
    assert "product_details" not in record


@pytest.mark.regression
def test_extract_ecommerce_detail_from_nuxt_payload_with_self_referential_wrapper() -> (
    None
):
    html = """
    <html>
      <head>
        <script id="__NUXT_DATA__" type="application/json">
          [
            {"data":1,"meta":2},
            {"product":3},
            ["Reactive",2],
            {"title":4,"vendor":5,"handle":6,"id":7,"product_type":8},
            "Nuxt Payload Widget",
            "Acme",
            "nuxt-payload-widget",
            4242,
            "Gadgets"
          ]
        </script>
      </head>
      <body></body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/nuxt-payload-widget",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["title"] == "Nuxt Payload Widget"
    assert record["brand"] == "Acme"
    assert record["_source"] == "js_state"


@pytest.mark.regression
def test_extract_ecommerce_detail_resolves_json_ld_graph_node_references() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@graph": [
            {
              "@id": "#brand",
              "@type": "Brand",
              "name": "Acme"
            },
            {
              "@id": "#offer",
              "@type": "Offer",
              "price": "29.99",
              "priceCurrency": "USD",
              "availability": "https://schema.org/InStock"
            },
            {
              "@id": "#product",
              "@type": "Product",
              "name": "Graph Widget",
              "brand": {"@id": "#brand"},
              "offers": {"@id": "#offer"}
            }
          ]
        }
        </script>
      </head>
      <body></body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/graph-widget",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["title"] == "Graph Widget"
    assert record["brand"] == "Acme"
    assert record["price"] == "29.99"
    assert record["currency"] == "USD"
    assert record["availability"] == "in_stock"
    assert record["_source"] == "json_ld"


@pytest.mark.regression
def test_extract_ecommerce_detail_prefers_json_ld_title_over_noisy_dom_h1() -> None:
    html = """
    <html>
      <head>
        <title>Products</title>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Graph Widget",
          "offers": {
            "@type": "Offer",
            "price": "29.99",
            "priceCurrency": "USD"
          }
        }
        </script>
      </head>
      <body>
        <main>
          <h1>Products</h1>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/graph-widget",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["title"] == "Graph Widget"
    assert record["_source"] == "json_ld"


@pytest.mark.regression
def test_extract_ecommerce_detail_keeps_adapter_title_over_longer_dom_h1() -> None:
    html = """
    <html>
      <body>
        <main>
          <h1>Widget Prime Deluxe Mega SEO Edition With Free Shipping And Bonus Copy</h1>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/widget-prime",
        "ecommerce_detail",
        max_records=5,
        adapter_records=[
            {
                "title": "Widget Prime",
                "url": "https://example.com/products/widget-prime",
            }
        ],
    )

    assert len(rows) == 1
    assert rows[0]["title"] == "Widget Prime"
    assert "SEO Edition" not in rows[0]["title"]


@pytest.mark.regression
def test_extract_ecommerce_detail_resolves_top_level_json_ld_array_references() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        [
          {
            "@context": "https://schema.org",
            "@id": "#brand",
            "@type": "Brand",
            "name": "Acme"
          },
          {
            "@context": "https://schema.org",
            "@id": "#offer",
            "@type": "Offer",
            "price": "39.99",
            "priceCurrency": "USD",
            "availability": "https://schema.org/InStock"
          },
          {
            "@context": "https://schema.org",
            "@id": "#product",
            "@type": "Product",
            "name": "Array Widget",
            "brand": {"@id": "#brand"},
            "offers": [{"@id": "#offer"}]
          }
        ]
        </script>
      </head>
      <body></body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/array-widget",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["title"] == "Array Widget"
    assert record["brand"] == "Acme"
    assert record["price"] == "39.99"
    assert record["currency"] == "USD"
    assert record["availability"] == "in_stock"
    assert record["_source"] == "json_ld"


@pytest.mark.regression
def test_extract_ecommerce_detail_flattens_json_ld_size_specifications() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Size Spec Widget",
          "size": {
            "@type": "SizeSpecification",
            "name": "XS",
            "sizeSystem": "https://schema.org/WearableSizeSystemUS",
            "sizeGroup": "https://schema.org/WearableSizeGroupRegular"
          },
          "hasVariant": [
            {
              "@type": "Product",
              "name": "Size Spec Widget",
              "sku": "W-XS",
              "size": {
                "@type": "SizeSpecification",
                "name": "XS",
                "sizeSystem": "https://schema.org/WearableSizeSystemUS",
                "sizeGroup": "https://schema.org/WearableSizeGroupRegular"
              },
              "offers": {
                "@type": "Offer",
                "availability": "https://schema.org/InStock"
              }
            },
            {
              "@type": "Product",
              "name": "Size Spec Widget",
              "sku": "W-XL",
              "size": {
                "@type": "SizeSpecification",
                "name": "XL",
                "sizeSystem": "https://schema.org/WearableSizeSystemUS",
                "sizeGroup": "https://schema.org/WearableSizeGroupRegular"
              },
              "offers": {
                "@type": "Offer",
                "availability": "https://schema.org/OutOfStock"
              }
            }
          ]
        }
        </script>
      </head>
      <body></body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/size-spec-widget",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["size"] == "XS"
    assert record["variants"][0]["size"] == "XS"
    assert record["variants"][1]["size"] == "XL"
    assert record["variants"][1]["availability"] == "out_of_stock"


@pytest.mark.regression
def test_extract_ecommerce_detail_backfills_visible_display_price() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Men's Flex Pants | 327 | 34 | 30",
          "brand": {"@type": "Brand", "name": "Columbia"},
          "image": "https://example.com/flex-pants.jpg",
          "description": "Trail pants with stretch fabric."
        }
        </script>
      </head>
      <body>
        <h1>Men's Flex Pants | 327 | 34 | 30</h1>
        <div data-component-id="display-price">
          <span aria-label="current price $42.00">$42.00</span>
          <s aria-label="original price $60.00">$60.00</s>
        </div>
        <p>Trail pants with stretch fabric.</p>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/flex-pants",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    assert rows[0]["price"] == "42.00"
    assert rows[0]["original_price"] == "60.00"


@pytest.mark.regression
def test_extract_detail_json_ld_offer_price_beats_bad_dom_price() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Cotton Shirt",
          "offers": {
            "@type": "Offer",
            "price": "49.00",
            "priceCurrency": "USD"
          }
        }
        </script>
      </head>
      <body>
        <main>
          <h1>Cotton Shirt</h1>
          <div data-testid="price">Related picks from $999.00</div>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/cotton-shirt",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    assert rows[0]["price"] == "49.00"
    assert rows[0]["currency"] == "USD"


@pytest.mark.regression
def test_extract_detail_json_ld_sale_and_regular_prices() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Stand Mixer",
          "offers": {
            "@type": "Offer",
            "price": "249.99",
            "highPrice": "329.99",
            "priceCurrency": "USD"
          }
        }
        </script>
      </head>
      <body><main><h1>Stand Mixer</h1></main></body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/stand-mixer",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    assert rows[0]["price"] == "249.99"
    assert rows[0]["original_price"] == "329.99"


@pytest.mark.regression
def test_extract_detail_parses_locale_decimal_price_text() -> None:
    html = """
    <html lang="fr-FR">
      <body>
        <main>
          <h1>Leather Tote</h1>
          <div data-testid="price">€1.234,56</div>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/leather-tote",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    assert rows[0]["price"] == "1234.56"
    assert rows[0]["currency"] == "EUR"


@pytest.mark.regression
def test_extract_ecommerce_detail_drops_low_signal_zero_display_price() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Classic Straight Jeans",
          "brand": {"@type": "Brand", "name": "Acme Denim"},
          "image": "https://example.com/jeans.jpg",
          "description": "Everyday jeans."
        }
        </script>
      </head>
      <body>
        <h1>Classic Straight Jeans</h1>
        <div data-component-id="display-price">
          <span aria-label="current price $0.00">$0.00</span>
        </div>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/classic-straight-jeans",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert "price" not in record


@pytest.mark.regression
def test_extract_ecommerce_detail_keeps_structured_zero_price_with_authoritative_offer() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Starter Guide Download",
          "sku": "GUIDE-001",
          "brand": {"@type": "Brand", "name": "Acme"},
          "offers": {
            "@type": "Offer",
            "priceCurrency": "USD",
            "price": "0.00",
            "availability": "https://schema.org/InStock"
          }
        }
        </script>
      </head>
      <body>
        <h1>Starter Guide Download</h1>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/starter-guide-download",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["price"] == "0.00"
    assert record["currency"] == "USD"
    assert record["_source"] == "json_ld"


@pytest.mark.regression
def test_extract_ecommerce_detail_keeps_raw_json_zero_price() -> None:
    rows = extract_records(
        '{"title":"Free Sample","price":"0.00","currency":"USD","url":"https://example.com/products/free-sample"}',
        "https://example.com/products/free-sample",
        "ecommerce_detail",
        max_records=5,
        content_type="application/json",
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["price"] == "0.00"
    assert record["currency"] == "USD"
    assert record["_source"] == "raw_json"

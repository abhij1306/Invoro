from __future__ import annotations

from .test_detail_extractor_structured_sources import BeautifulSoup, build_detail_record, extract_records, pytest, reconcile_variant_availability_from_dom, variant_option_availability  # fmt: skip

@pytest.mark.regression
def test_extract_ecommerce_detail_ignores_sort_filter_and_availability_controls_as_variants() -> (
    None
):
    html = """
    <html>
      <body>
        <main>
          <h1>Performance Crew Socks</h1>
          <div class="price">$18.00</div>
          <label for="sort-by">Sort By</label>
          <select id="sort-by">
            <option>Featured</option>
            <option>Newest</option>
          </select>
          <label for="filter-by">Filter By</label>
          <select id="filter-by">
            <option>All Reviews</option>
            <option>Most Helpful</option>
          </select>
          <fieldset>
            <legend>Availability</legend>
            <label><input type="checkbox" checked> In Stock</label>
            <label><input type="checkbox"> Out of Stock</label>
          </fieldset>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/performance-crew-socks",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert "variants" not in record

@pytest.mark.regression
def test_extract_ecommerce_detail_does_not_treat_etsy_report_radios_as_variants() -> (
    None
):
    html = """
    <html>
      <body>
        <main>
          <h1>Black Popular And In Demand Unisex T-Shirt</h1>
          <div class="price">INR 2476.00</div>
          <div class="listing-report-modal">
            <ul>
              <li>
                <input id="flag_1" type="radio" name="flag_type_mnemonic" value="LISTING_GRT_T1" />
                <label for="flag_1">It's not handmade, vintage, or craft supplies</label>
              </li>
              <li>
                <input id="flag_2" type="radio" name="flag_type_mnemonic" value="OC_PORNOGRAPHY" />
                <label for="flag_2">It's pornographic</label>
              </li>
              <li>
                <input id="flag_3" type="radio" name="flag_type_mnemonic" value="LISTING_MINOR_SAFETY" />
                <label for="flag_3">It's a threat to minor safety</label>
              </li>
            </ul>
          </div>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.etsy.com/listing/1210769675/example",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["title"] == "Black Popular And In Demand Unisex T-Shirt"
    assert record["price"] == "2476.00"
    assert "variants" not in record
    assert "variant_count" not in record

@pytest.mark.regression
def test_extract_ecommerce_detail_does_not_treat_shipping_country_selector_as_variant_axis() -> (
    None
):
    html = """
    <html>
      <body>
        <main>
          <h1>Custom Embroidered Mom Picture Sweatshirt</h1>
          <div class="price">INR 3121.00</div>
          <label for="variation-selector-1">Color</label>
          <select id="variation-selector-1">
            <option>Select an option</option>
            <option>Heather Dark Green</option>
            <option>White</option>
          </select>
          <label for="estimated-shipping-country">Country</label>
          <select
            id="estimated-shipping-country"
            name="estimated-shipping-country"
            aria-label="Choose country"
          >
            <option>----------</option>
            <option>Australia</option>
            <option>Canada</option>
            <option>France</option>
          </select>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.etsy.com/listing/1210769675/example",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["title"] == "Custom Embroidered Mom Picture Sweatshirt"
    assert record["variant_count"] == 2
    assert "choose_country" not in str(record.get("variants") or "")

@pytest.mark.regression
def test_extract_ecommerce_detail_splits_style_and_size_from_compound_select_before_color() -> (
    None
):
    html = """
    <html>
      <body>
        <main>
          <h1>Custom Sweatshirt</h1>
          <div class="price">$10.00</div>
          <label for="variation-selector-0">Style &amp; Size</label>
          <select id="variation-selector-0">
            <option value="">Select an option</option>
            <option value="1">Sweatshirt S ($10.00)</option>
            <option value="2">Sweatshirt M ($10.00)</option>
            <option value="3">Hoodie S ($12.00)</option>
            <option value="4">Hoodie M ($12.00)</option>
          </select>
          <label for="variation-selector-1">Colors</label>
          <select id="variation-selector-1">
            <option value="">Select an option</option>
            <option value="10">Black</option>
            <option value="11">White</option>
          </select>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.etsy.com/listing/1210769675/example",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["variant_count"] == 8

@pytest.mark.regression
def test_extract_ecommerce_detail_does_not_treat_question_radiogroup_as_size_variants() -> (
    None
):
    html = """
    <html>
      <body>
        <main>
          <h1>7 Cup Food Processor</h1>
          <section class="product-questions">
            <div role="radiogroup" aria-label="Will the 7 cup model chop cooked pork into a small size">
              <button type="button">Yes</button>
              <button type="button">No</button>
            </div>
          </section>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/food-processor",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert "variants" not in record

@pytest.mark.regression
def test_extract_ecommerce_detail_keeps_stronger_js_state_variants_over_dom_fallback() -> (
    None
):
    html = """
    <html>
      <body>
        <h1>Trail Runner</h1>
        <label>
          Size
          <select name="size">
            <option value="">Choose size</option>
            <option value="s">S</option>
            <option value="m">M</option>
          </select>
        </label>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/trail-runner",
        "ecommerce_detail",
        max_records=5,
        adapter_records=[
            {
                "variant_axes": {"size": ["S", "M", "L"]},
                "selected_variant": {"sku": "TRAIL-S", "option_values": {"size": "S"}},
            }
        ],
    )

    assert len(rows) == 1

@pytest.mark.regression
def test_extract_ecommerce_detail_skips_dom_variant_scan_for_rich_structured_variants() -> (
    None
):
    html = """
    <html>
      <body>
        <h1>Trail Runner</h1>
        <label>
          Size
          <select name="size">
            <option value="">Choose size</option>
            <option value="s">S</option>
            <option value="m">M</option>
          </select>
        </label>
      </body>
    </html>
    """

    record = build_detail_record(
        html,
        "https://example.com/products/trail-runner",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Trail Runner",
                "price": "99.00",
                "currency": "USD",
                "image_url": "https://example.com/trail-runner.jpg",
                "variants": [
                    {
                        "sku": "TRAIL-S",
                        "size": "S",
                        "image_url": "https://example.com/s.jpg",
                    },
                    {
                        "sku": "TRAIL-M",
                        "size": "M",
                        "image_url": "https://example.com/m.jpg",
                    },
                ],
            }
        ],
        extraction_runtime_snapshot={
            "selector_self_heal": {"enabled": True, "min_confidence": 0.55}
        },
    )

    assert record["_extraction_tiers"]["early_exit"] == "js_state"
    assert record["variants"] == [
        {"size": "S", "sku": "TRAIL-S", "image_url": "https://example.com/s.jpg"},
        {"size": "M", "sku": "TRAIL-M", "image_url": "https://example.com/m.jpg"},
    ]

@pytest.mark.regression
def test_extract_ecommerce_detail_backfills_selected_variant_price_from_record_when_dom_variants_are_sparse() -> (
    None
):
    html = """
    <html>
      <body>
        <main>
          <h1>Trail Runner</h1>
          <div class="price">$99.00</div>
          <label>
            Size
            <select name="size">
              <option value="s" selected>S</option>
              <option value="m">M</option>
            </select>
          </label>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/trail-runner",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["price"] == "99.00"

@pytest.mark.regression
def test_extract_ecommerce_detail_prunes_single_value_marketing_axes_from_final_variant_record() -> (
    None
):
    html = """
    <html>
      <head>
        <script id="__NEXT_DATA__" type="application/json">
        {
          "props": {
            "pageProps": {
              "product": {
                "id": "leggings-1",
                "title": "Everyday Seamless Leggings",
                "price": "58.00",
                "currency": "USD",
                "variants": [
                  {
                    "id": "leggings-s",
                    "available": true,
                    "selectedOptions": [
                      {"name": "Size", "value": "S"},
                      {"name": "Soft Fabric", "value": "Second-skin feel"},
                      {"name": "High Waisted", "value": "Snatched waist"}
                    ]
                  },
                  {
                    "id": "leggings-m",
                    "available": true,
                    "selectedOptions": [
                      {"name": "Size", "value": "M"},
                      {"name": "Soft Fabric", "value": "Second-skin feel"},
                      {"name": "High Waisted", "value": "Snatched waist"}
                    ]
                  }
                ]
              }
            }
          }
        }
        </script>
      </head>
      <body><main><h1>Everyday Seamless Leggings</h1></main></body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/everyday-seamless-leggings?variant=leggings-s",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    option_names = {
        str(name).strip().lower().replace(" ", "_")
        for variant in record["variants"]
        for name in variant.get("option_values", variant)
    }
    assert "soft_fabric" not in option_names
    assert "high_waisted" not in option_names

@pytest.mark.regression
def test_extract_ecommerce_detail_does_not_duplicate_parent_price_into_variants_when_uniform() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Tree Runner",
          "offers": {
            "@type": "Offer",
            "price": "100",
            "priceCurrency": "USD"
          }
        }
        </script>
        <script id="__NEXT_DATA__" type="application/json">
        {
          "props": {
            "pageProps": {
              "product": {
                "id": "tree-runner-1",
                "title": "Tree Runner",
                "currency": "USD",
                "variants": [
                  {
                    "id": "tree-runner-8",
                    "available": true,
                    "selectedOptions": [
                      {"name": "Size", "value": "8"}
                    ]
                  },
                  {
                    "id": "tree-runner-9",
                    "available": true,
                    "selectedOptions": [
                      {"name": "Size", "value": "9"}
                    ]
                  }
                ]
              }
            }
          }
        }
        </script>
      </head>
      <body><main><h1>Tree Runner</h1></main></body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/tree-runner?variant=tree-runner-8",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["price"] == "100.00"
    assert "price" not in record["variants"][0]

@pytest.mark.regression
def test_extract_ecommerce_detail_ignores_generic_selector_axis_names_without_semantic_labels() -> (
    None
):
    html = """
    <html>
      <body>
        <main>
          <h1>Camera Lens</h1>
          <div class="price">$399.00</div>
          <select id="variation_selector_0">
            <option value="">Choose</option>
            <option value="1">Leica L</option>
            <option value="2">Sony E</option>
          </select>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/camera-lens",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    assert "variation_selector_0" not in rows[0].get("variant_axes", {})

@pytest.mark.regression
def test_extract_ecommerce_detail_infers_unlabeled_select_variants_and_ignores_translate_widget() -> (
    None
):
    html = """
    <html>
      <body>
        <main>
          <h1>JARIX 1.5 ดีไซน์ใหม่ (จาริกซ์) VEPRO Foam</h1>
          <div class="price">฿1997.00</div>
          <select>
            <option>-- คลิกเพื่อเลือก สี --</option>
            <option>Sand Beige</option>
            <option>Sirrocco Nude</option>
            <option>Machine Grey</option>
            <option>1.5 Pearl White</option>
          </select>
          <select>
            <option>-- คลิกเพื่อเลือก ขนาด --</option>
            <option>EU-36</option>
            <option>EU-37</option>
            <option>EU-38</option>
          </select>
          <select aria-label="Language Translate Widget">
            <option>English</option>
            <option>Thai</option>
          </select>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.shop.ving.run/product/jarix-1-5-vepro-foam/11000742818002471",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert "language_translate_widget" not in str(record.get("variant_axes") or "")

@pytest.mark.regression
def test_extract_ecommerce_detail_keeps_size_axis_when_bad_dom_label_says_color() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/json">
        {
          "@type": "Product",
          "name": "Montecito 2.0 Hard Side Graphite Carry On Suitcase",
          "brand": "Ricardo Beverly Hills",
          "attributes": {
            "GTIN14": {"Id": "GTIN14", "Values": [{"Value": "00018982111874"}]},
            "AVAILABILITY": {"Id": "AVAILABILITY", "Values": [{"Value": "True"}]}
          }
        }
        </script>
      </head>
      <body>
        <main>
          <h1>Montecito 2.0 Hard Side Graphite Carry On Suitcase</h1>
          <div class="price">$136.00</div>
          <select aria-label="Color">
            <option>Graphite</option>
            <option>Hunter</option>
          </select>
          <select aria-label="Color">
            <option>21 in.</option>
            <option>25 in.</option>
            <option>29 in.</option>
          </select>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.belk.com/p/ricardo-beverly-hills-montecito-2.0-hard-side-graphite-carry-on-suitcase/620017811756553.html",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record.get("sku") != "AVAILABILITY"
    assert "GTIN14" not in record.get("product_attributes", {})
    assert "AVAILABILITY" not in record.get("product_attributes", {})

@pytest.mark.regression
def test_variant_option_availability_does_not_treat_disabled_control_as_out_of_stock() -> (
    None
):
    soup = BeautifulSoup(
        """
        <li class="size disabled selected">
          <input checked disabled type="radio" name="size" value="2" />
          <label>2</label>
        </li>
        """,
        "html.parser",
    )

    node = soup.select_one("input")
    label = soup.select_one("label")

    assert node is not None
    availability, stock_quantity = variant_option_availability(
        node=node,
        label_node=label,
    )

    assert availability is None
    assert stock_quantity is None

@pytest.mark.regression
def test_variant_option_availability_treats_unselected_disabled_control_as_out_of_stock() -> (
    None
):
    soup = BeautifulSoup(
        """
        <button type="button" aria-disabled="true">M 5 / W 6.5</button>
        """,
        "html.parser",
    )
    node = soup.select_one("button")

    assert node is not None
    availability, stock_quantity = variant_option_availability(
        node=node,
        label_node=None,
    )

    assert availability == "out_of_stock"
    assert stock_quantity == 0

    data_disabled_true = BeautifulSoup(
        '<button type="button" data-disabled="true">M</button>',
        "html.parser",
    ).select_one("button")

    assert variant_option_availability(node=data_disabled_true, label_node=None) == (
        "out_of_stock",
        0,
    )

    data_disabled_false = BeautifulSoup(
        '<button type="button" data-disabled="false">M</button>',
        "html.parser",
    ).select_one("button")

    assert variant_option_availability(node=data_disabled_false, label_node=None) == (
        None,
        None,
    )

@pytest.mark.regression
def test_dom_availability_appends_disabled_select_option_with_label() -> None:
    record = {
        "variants": [{"size": "S", "option_values": {"size": "S"}}],
        "variant_count": 1,
    }
    soup = BeautifulSoup(
        """
        <html><body>
          <section class="variant-options">
            <label for="size-select">Size</label>
            <select id="size-select" name="size">
              <option value="S">S</option>
              <option value="M" disabled>M</option>
            </select>
          </section>
        </body></html>
        """,
        "html.parser",
    )

    reconcile_variant_availability_from_dom(record, soup=soup)

    assert record["variant_count"] == 2
    assert record["variants"][1] == {
        "size": "M",
        "option_values": {"size": "M"},
        "availability": "out_of_stock",
        "stock_quantity": 0,
    }

@pytest.mark.regression
def test_variant_option_availability_reads_data_available_flag() -> None:
    out_of_stock = BeautifulSoup(
        '<div data-available="false">XL</div>', "html.parser"
    ).select_one("div")
    in_stock = BeautifulSoup(
        '<div data-available="true">L</div>', "html.parser"
    ).select_one("div")

    assert variant_option_availability(node=out_of_stock, label_node=None) == (
        "out_of_stock",
        0,
    )
    assert variant_option_availability(node=in_stock, label_node=None) == (
        "in_stock",
        None,
    )

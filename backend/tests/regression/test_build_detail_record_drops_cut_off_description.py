from __future__ import annotations

from .test_detail_extractor_structured_sources import build_detail_record, extract_records, json, normalize_variant_record, pytest, read_optional_artifact_text  # fmt: skip


@pytest.mark.regression
def test_build_detail_record_drops_cut_off_description_without_complete_source() -> (
    None
):
    record = build_detail_record(
        """
        <html>
          <head>
            <meta property="og:title" content="Dime Soft Rock Crewneck">
            <meta property="og:description" content="Arriving as part of the second drop from its Spring '25 collection, Montreal-based streetwear and skatewear brand Dime pays homage to one of its favorite music subgenres with this Soft Rock Crewneck. Crafted from heavyweight cotton for a comfortable, durable feel, this crewneck features an eye-catching Dime logo on the">
          </head>
          <body><main><h1>Dime Soft Rock Crewneck</h1></main></body>
        </html>
        """,
        "https://www.sneakersnstuff.com/products/dime-soft-rock-crewneck-dime2sp2542blk",
        "ecommerce_detail",
        None,
    )

    assert record.get("description") == (
        "Arriving as part of the second drop from its Spring '25 collection, "
        "Montreal-based streetwear and skatewear brand Dime pays homage to one "
        "of its favorite music subgenres with this Soft Rock Crewneck."
    )


@pytest.mark.regression
def test_build_detail_record_prefers_js_state_html_description_over_truncated_json_ld() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Technics SL-1200MK7",
          "description": "Item ships out in 15 working days.The SL-1200 – A New Chapter BeginsAs the go-to choice o...",
          "brand": "Technics",
          "image": "https://example.com/images/turntable.jpg",
          "offers": {
            "@type": "Offer",
            "price": "175000",
            "priceCurrency": "INR"
          }
        }
        </script>
        <script>
          var BspdCurrentProduct = {
            "id": 6569597796470,
            "title": "Technics SL-1200MK7",
            "handle": "technics-sl-1200mk7",
            "description": "<h3><em><span>Item ships out in 15 working days.</span></em></h3><h2>The SL-1200 – A New Chapter Begins</h2><p>As the go-to choice of DJs the world over, the SL-1200 Series has long been a dominant presence on the global music scene. Today the brand continues to set the industry standard as the direct drive turntable par excellence.</p><h2>Features</h2><p>Coreless Direct-Drive Motor</p>",
            "vendor": "Technics",
            "price": "175000",
            "available": true,
            "variants": [
              {
                "id": 42982754549878,
                "sku": "TT-TS-SL1200MK7-SILVER-N",
                "available": true,
                "price": "175000"
              }
            ],
            "images": ["https://example.com/images/turntable.jpg"]
          };
        </script>
      </head>
      <body>
        <main><h1>Technics SL-1200MK7</h1></main>
      </body>
    </html>
    """

    record = build_detail_record(
        html,
        "https://www.therevolverclub.com/products/technics-sl-1200mk7",
        "ecommerce_detail",
        None,
    )

    assert record["description"] == (
        "Item ships out in 15 working days. The SL-1200 – A New Chapter Begins "
        "As the go-to choice of DJs the world over, the SL-1200 Series has long "
        "been a dominant presence on the global music scene. Today the brand "
        "continues to set the industry standard as the direct drive turntable par excellence."
    )
    assert record["_field_sources"]["description"] == ["json_ld", "js_state"]
    assert record["features"] == ["Coreless Direct-Drive Motor"]


@pytest.mark.regression
def test_extract_ecommerce_detail_uses_dom_description_when_authoritative_copy_is_thin() -> (
    None
):
    html = """
    <html>
      <body>
        <main>
          <h1>ABC Warpstreme Jogger</h1>
          <section>
            <h2>Description</h2>
            <p>Designed for office commutes and long-haul travel.</p>
            <ul>
              <li>Warpstreme fabric feels sleek and dries fast.</li>
              <li>Secure pockets keep cards and keys close.</li>
              <li>Streamlined taper pairs easily with sneakers or loafers.</li>
            </ul>
          </section>
        </main>
      </body>
    </html>
    """

    record = build_detail_record(
        html,
        "https://shop.lululemon.com/p/men-joggers/Abc-Jogger/_/prod8530240",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "ABC Warpstreme Jogger",
                "description": (
                    "These sleek joggers feature our ABC technology for travel."
                ),
            }
        ],
    )

    assert record["description"].startswith(
        "Designed for office commutes and long-haul travel."
    )
    assert "Warpstreme fabric feels sleek and dries fast." in record["description"]
    assert record["_extraction_tiers"]["current"] == "dom"


@pytest.mark.regression
def test_extract_ecommerce_detail_prefers_displayvalue_for_variant_sizes() -> None:
    html = """
    <html>
      <body>
        <main>
          <h1>Aeron Chair</h1>
          <fieldset class="attr-group-items">
            <input
              type="radio"
              id="size-size_a_small"
              name="size"
              data-attr-displayvalue="Size A - Small"
              value="https://store.hermanmiller.com/variation?dwvar_size=size_a_small"
            />
            <label for="size-size_a_small">
              <span class="sr-only">View this product in: Size</span>
              <span class="size-value swatch-text swatch-value">
                Size A - Small
                <svg aria-labelledby="disable-danger" role="img">
                  <title id="disable-danger">disable-danger</title>
                  <use xlink:href="#disable-danger"></use>
                </svg>
              </span>
            </label>
            <input
              type="radio"
              id="size-size_b_medium"
              name="size"
              data-attr-displayvalue="Size B - Medium"
              value="https://store.hermanmiller.com/variation?dwvar_size=size_b_medium"
              checked
            />
            <label for="size-size_b_medium">
              <span class="sr-only">View this product in: Size</span>
              <span class="size-value swatch-text swatch-value">
                Size B - Medium
                <svg aria-labelledby="disable-danger" role="img">
                  <title id="disable-danger-2">disable-danger</title>
                  <use xlink:href="#disable-danger"></use>
                </svg>
              </span>
            </label>
          </fieldset>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://store.hermanmiller.com/office-chairs-aeron/aeron-chair/100073872.html?lang=en_US",
        "ecommerce_detail",
        max_records=1,
        requested_fields=["size"],
    )

    assert rows
    assert [variant["size"] for variant in rows[0]["variants"]] == [
        "Size A - Small",
        "Size B - Medium",
    ]
    assert "View this product in" not in json.dumps(rows[0]["variants"])
    assert "disable-danger" not in json.dumps(rows[0]["variants"])


@pytest.mark.regression
def test_extract_ecommerce_detail_derives_wrangler_size_length_from_variant_urls() -> (
    None
):
    html = """
    <html>
      <body>
        <main>
          <h1>Wrangler Five Star Premium Flex Relaxed Fit Bootcut Jean</h1>
          <fieldset data-option-name="color" class="swatch-attribute color">
            <legend>Color</legend>
            <input
              type="radio"
              id="color-huxley"
              name="color"
              value="/on/demandware.store/Sites-Wrangler-Site/en_US/Product-Variation?dwvar_98FRZJ_color=112316407&pid=112316407&quantity=1"
              checked
            />
            <label for="color-huxley">Huxley</label>
            <input
              type="radio"
              id="color-jennings"
              name="color"
              value="/on/demandware.store/Sites-Wrangler-Site/en_US/Product-Variation?dwvar_98FRZJ_color=112373655&pid=112373655&quantity=1"
            />
            <label for="color-jennings">Jennings</label>
          </fieldset>
          <fieldset data-option-name="size" class="swatch-attribute size">
            <legend>Size</legend>
            <input
              type="radio"
              id="size-28"
              name="size"
              value="https://www.wrangler.com/on/demandware.store/Sites-Wrangler-Site/en_US/Product-Variation?dwvar_112316407_SIZE1=28&dwvar_112316407_color=112316407&pid=112316407&quantity=1"
            />
            <label for="size-28"><span class="sr-only">Waist 28</span></label>
            <input
              type="radio"
              id="size-30"
              name="size"
              value="https://www.wrangler.com/on/demandware.store/Sites-Wrangler-Site/en_US/Product-Variation?dwvar_112316407_SIZE1=30&dwvar_112316407_color=112316407&pid=112316407&quantity=1"
            />
            <label for="size-30"><span class="sr-only">Waist 30</span></label>
          </fieldset>
          <fieldset data-option-name="length" class="swatch-attribute length">
            <legend>Length</legend>
            <input
              type="radio"
              id="length-30"
              name="length"
              value="https://www.wrangler.com/on/demandware.store/Sites-Wrangler-Site/en_US/Product-Variation?dwvar_112316407_SIZE2=30&dwvar_112316407_color=112316407&pid=112316407&quantity=1"
            />
            <label for="length-30"><span class="sr-only">Inseam 30</span></label>
            <input
              type="radio"
              id="length-32"
              name="length"
              value="https://www.wrangler.com/on/demandware.store/Sites-Wrangler-Site/en_US/Product-Variation?dwvar_112316407_SIZE2=32&dwvar_112316407_color=112316407&pid=112316407&quantity=1"
            />
            <label for="length-32"><span class="sr-only">Inseam 32</span></label>
          </fieldset>
          <fieldset data-option-name="size" class="attribute-details">
            <legend>Stretch Details</legend>
            <input type="radio" id="stretch-1" name="stretch-details" />
            <label for="stretch-1">Some Stretch attribute details</label>
            <input type="radio" id="stretch-2" name="stretch-details" />
            <label for="stretch-2">More Stretch attribute details</label>
          </fieldset>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.wrangler.com/shop/wrangler-mens-five-star-premium-flex-relaxed-fit-bootcut-jean-98FRZJ.html?dwvar_98FRZJ_color=112316407",
        "ecommerce_detail",
        max_records=1,
        requested_fields=["variants", "color", "size", "length"],
    )

    assert rows
    record = rows[0]
    assert record["variant_count"] == 8
    assert {
        (variant["color"], variant["size"], variant["length"])
        for variant in record["variants"]
    } == {
        ("Huxley", "28", "30"),
        ("Huxley", "28", "32"),
        ("Huxley", "30", "30"),
        ("Huxley", "30", "32"),
        ("Jennings", "28", "30"),
        ("Jennings", "28", "32"),
        ("Jennings", "30", "30"),
        ("Jennings", "30", "32"),
    }
    serialized = json.dumps(record["variants"])
    assert "Product-Variation" not in serialized
    assert "attribute details" not in serialized


@pytest.mark.regression
def test_extract_ecommerce_detail_drops_unresolved_url_like_size_values() -> None:
    html = """
    <html>
      <body>
        <main>
          <h1>Wrangler Five Star Premium Flex Relaxed Fit Bootcut Jean</h1>
          <fieldset data-option-name="color" class="swatch-attribute color">
            <legend>Color</legend>
            <input type="radio" id="color-huxley" name="color" checked />
            <label for="color-huxley">Huxley</label>
            <input type="radio" id="color-jennings" name="color" />
            <label for="color-jennings">Jennings</label>
          </fieldset>
          <fieldset data-option-name="size" class="swatch-attribute size">
            <legend>Size</legend>
            <input
              type="radio"
              id="size-28"
              name="size"
              value="https://www.wrangler.com/on/demandware.store/Sites-Wrangler-Site/en_US/Product-Variation?dwvar_112316407_SIZE1=28&dwvar_112316407_color=112316407&pid=112316407&quantity=1"
            />
            <label for="size-28">28</label>
            <input
              type="radio"
              id="size-30"
              name="size"
              value="https://www.wrangler.com/on/demandware.store/Sites-Wrangler-Site/en_US/Product-Variation?dwvar_112316407_SIZE1=30&dwvar_112316407_color=112316407&pid=112316407&quantity=1"
            />
            <label for="size-30">30</label>
          </fieldset>
          <fieldset class="mobile-size-clone">
            <legend>Size</legend>
            <input
              type="radio"
              id="size-clone-1"
              name="mobile-size"
              value="/on/demandware.store/Sites-Wrangler-Site/en_US/Product-Variation?dwvar_98FRZJ_color=112316407&pid=112316407&quantity=1"
            />
            <label for="size-clone-1"><span class="sr-only">Select option</span></label>
            <input
              type="radio"
              id="size-clone-2"
              name="mobile-size"
              value="/on/demandware.store/Sites-Wrangler-Site/en_US/Product-Variation?dwvar_98FRZJ_color=112373655&pid=112373655&quantity=1"
            />
            <label for="size-clone-2"><span class="sr-only">Select option</span></label>
          </fieldset>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.wrangler.com/shop/wrangler-mens-five-star-premium-flex-relaxed-fit-bootcut-jean-98FRZJ.html?dwvar_98FRZJ_color=112316407",
        "ecommerce_detail",
        max_records=1,
        requested_fields=["variants", "color", "size"],
    )

    assert rows
    record = rows[0]
    assert record["variant_count"] == 4
    assert {(variant["color"], variant["size"]) for variant in record["variants"]} == {
        ("Huxley", "28"),
        ("Huxley", "30"),
        ("Jennings", "28"),
        ("Jennings", "30"),
    }
    assert "Product-Variation" not in json.dumps(record["variants"])


@pytest.mark.regression
def test_extract_ecommerce_detail_propagates_multi_axis_dom_option_availability() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/ld+json">
          {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": "Wrangler Five Star Premium Flex Relaxed Fit Bootcut Jean",
            "offers": {
              "@type": "Offer",
              "price": "24.99",
              "priceCurrency": "USD",
              "availability": "https://schema.org/InStock"
            }
          }
        </script>
      </head>
      <body>
        <main>
          <h1>Wrangler Five Star Premium Flex Relaxed Fit Bootcut Jean</h1>
          <fieldset data-option-name="color" class="swatch-attribute color">
            <legend>Color</legend>
            <input type="radio" id="color-huxley" name="color" checked />
            <label for="color-huxley">Huxley</label>
            <input type="radio" id="color-jennings" name="color" />
            <label for="color-jennings">Jennings</label>
          </fieldset>
          <fieldset data-option-name="size" class="swatch-attribute size">
            <legend>Size</legend>
            <input
              type="radio"
              id="size-28"
              name="size"
              class="unselectable"
              aria-label="Unavailable Size 28"
              value="https://www.wrangler.com/on/demandware.store/Sites-Wrangler-Site/en_US/Product-Variation?dwvar_112316407_SIZE1=28&dwvar_112316407_color=112316407&pid=112316407&quantity=1"
            />
            <label for="size-28">28</label>
            <input
              type="radio"
              id="size-30"
              name="size"
              aria-label="Select Size 30"
              value="https://www.wrangler.com/on/demandware.store/Sites-Wrangler-Site/en_US/Product-Variation?dwvar_112316407_SIZE1=30&dwvar_112316407_color=112316407&pid=112316407&quantity=1"
            />
            <label for="size-30">30</label>
          </fieldset>
          <fieldset data-option-name="length" class="swatch-attribute length">
            <legend>Length</legend>
            <input
              type="radio"
              id="length-30"
              name="length"
              aria-label="Select Length 30"
              value="https://www.wrangler.com/on/demandware.store/Sites-Wrangler-Site/en_US/Product-Variation?dwvar_112316407_SIZE2=30&dwvar_112316407_color=112316407&pid=112316407&quantity=1"
            />
            <label for="length-30">30</label>
            <input
              type="radio"
              id="length-32"
              name="length"
              aria-label="Select Length 32"
              value="https://www.wrangler.com/on/demandware.store/Sites-Wrangler-Site/en_US/Product-Variation?dwvar_112316407_SIZE2=32&dwvar_112316407_color=112316407&pid=112316407&quantity=1"
            />
            <label for="length-32">32</label>
          </fieldset>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.wrangler.com/shop/wrangler-mens-five-star-premium-flex-relaxed-fit-bootcut-jean-98FRZJ.html?dwvar_98FRZJ_color=112316407",
        "ecommerce_detail",
        max_records=1,
        requested_fields=["variants", "availability"],
    )

    assert rows
    record = rows[0]
    assert record["availability"] == "in_stock"
    assert record["variant_count"] == 8
    availability_by_variant = {
        (variant["color"], variant["size"], variant["length"]): variant.get(
            "availability"
        )
        for variant in record["variants"]
    }
    assert availability_by_variant[("Huxley", "28", "30")] == "out_of_stock"
    assert availability_by_variant[("Jennings", "28", "32")] == "out_of_stock"
    assert availability_by_variant[("Huxley", "30", "30")] == "in_stock"
    assert availability_by_variant[("Jennings", "30", "32")] == "in_stock"


@pytest.mark.regression
def test_extract_ecommerce_detail_captures_nautica_swatchanchor_variants() -> None:
    html = """
    <html>
      <body>
        <main class="pdp-main">
          <div class="swatches color">
            <div class="variation__label"></div>
            <ul class="swatchesdisplay Color">
              <li><a class="swatchanchor" data-value="420" title="Angel Blue">Angel Blue</a></li>
              <li><a class="swatchanchor" data-value="279" title="Chino">Chino</a></li>
            </ul>
          </div>
          <div class="swatches size">
            <div class="variation__label variation__label--size">
              <span class="label">Size:</span>
              <span class="value">Select Size</span>
            </div>
            <div class="availability"><p class="in-stock-msg">In Stock</p></div>
            <ul class="swatchesdisplay sizes char2">
              <li><a class="swatchanchor" title="XS">XS</a></li>
              <li><a class="swatchanchor" title="S">S</a></li>
              <li><a class="swatchanchor" title="M">M</a></li>
            </ul>
          </div>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.nautica.com/classic-fit-garment-dyed-polo/KR5815.html",
        "ecommerce_detail",
        max_records=1,
        requested_fields=["variants", "availability"],
    )

    assert rows
    record = rows[0]
    assert record["variant_count"] == 6
    assert {(variant["color"], variant["size"]) for variant in record["variants"]} == {
        ("Angel Blue", "XS"),
        ("Angel Blue", "S"),
        ("Angel Blue", "M"),
        ("Chino", "XS"),
        ("Chino", "S"),
        ("Chino", "M"),
    }


@pytest.mark.regression
def test_extract_ecommerce_detail_keeps_public_size_color_axes_only_for_herman_style_fieldsets() -> (
    None
):
    html = read_optional_artifact_text("tests/fixtures/herman_miller_aeron.html")

    rows = extract_records(
        html,
        "https://store.hermanmiller.com/office-chairs-aeron/aeron-chair/100073872.html?lang=en_US",
        "ecommerce_detail",
        max_records=1,
        requested_fields=["variants", "size", "color"],
    )

    assert rows
    variants = rows[0]["variants"]
    assert rows[0]["variant_count"] == 4
    assert {(variant["size"], variant["color"]) for variant in variants} == {
        ("Size A - Small", "Graphite / Graphite"),
        ("Size A - Small", "Black / Onyx Ultra Matte"),
        ("Size B - Medium", "Graphite / Graphite"),
        ("Size B - Medium", "Black / Onyx Ultra Matte"),
    }
    serialized = json.dumps(variants)
    assert "Basic Back Support" not in serialized
    assert "Height-Adjustable Arms" not in serialized
    assert "Leather" not in serialized


@pytest.mark.regression
def test_extract_ecommerce_detail_ignores_embedded_json_feature_flags_and_size_rows() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Classic Four Prong Solitaire Engagement Ring in Platinum",
          "description": "Let your diamond shine brilliantly in this classic platinum four-prong solitaire engagement ring.",
          "image": "https://example.com/images/ring.jpg",
          "offers": {
            "@type": "Offer",
            "price": "1025",
            "priceCurrency": "USD"
          }
        }
        </script>
        <script type="application/json">
        {
          "env": "green",
          "appData": {
            "jaData": {
              "features": {
                "activeCampaign": "Mday26FR",
                "essentialGridCampaign": "QualityNValue",
                "payPalEnvironment": "prod",
                "topMesseg": "Happy New Year!"
              }
            }
          },
          "ssrPageData": {
            "ringSize": {
              "sizesInfo": [
                {
                  "size": 3,
                  "isAvailable": true,
                  "shippingDate": "2026-05-21",
                  "specialDays": {"byValentines": true}
                },
                {
                  "size": 3.5,
                  "isAvailable": true,
                  "shippingDate": "2026-05-21",
                  "specialDays": {"byValentines": true}
                }
              ]
            }
          }
        }
        </script>
      </head>
      <body>
        <main><h1>Classic Four Prong Solitaire Engagement Ring in Platinum</h1></main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.bluenile.com/engagement-rings/design-your-own-ring/classic-four-prong-solitaire-engagement-ring-in-platinum-item-194156",
        "ecommerce_detail",
        max_records=1,
    )

    assert rows
    record = rows[0]
    assert "features" not in record
    assert "size" not in record


@pytest.mark.regression
def test_normalize_variant_record_infers_single_variant_color_from_title_slug() -> None:
    record = {
        "title": "Men's Wool Runners - Natural Black",
        "url": "https://www.allbirds.com/products/mens-wool-runners-natural-black",
        "variants": [
            {
                "url": "https://www.allbirds.com/products/mens-wool-runners-natural-black",
            }
        ],
    }

    normalize_variant_record(record)

    assert record["variants"] == [
        {
            "url": "https://www.allbirds.com/products/mens-wool-runners-natural-black",
            "color": "Natural Black",
        }
    ]


@pytest.mark.regression
def test_normalize_variant_record_infers_shared_color_slug_for_size_variants() -> None:
    record = {
        "title": "Men's Wool Runner",
        "url": "https://www.allbirds.com/products/mens-wool-runners-tuke-river",
        "variants": [
            {
                "sku": "WR2MTRV090",
                "url": "https://www.allbirds.com/products/mens-wool-runners-tuke-river?variant=17874798215237",
                "size": "9",
                "availability": "out_of_stock",
            },
            {
                "sku": "WR2MTRV100",
                "url": "https://www.allbirds.com/products/mens-wool-runners-tuke-river?variant=17874798248005",
                "size": "10",
                "availability": "out_of_stock",
            },
        ],
    }

    normalize_variant_record(record)

    assert [(variant["size"], variant["color"]) for variant in record["variants"]] == [
        ("9", "Tuke River"),
        ("10", "Tuke River"),
    ]


@pytest.mark.regression
def test_normalize_variant_record_does_not_fold_size_token_into_color() -> None:
    record = {
        "title": "Runner Tee XS Blue",
        "variants": [
            {
                "url": "https://example.com/products/runner-tee-xs-blue",
            }
        ],
    }

    normalize_variant_record(record)

    assert record["variants"] == [
        {
            "url": "https://example.com/products/runner-tee-xs-blue",
            "size": "XS",
            "color": "Blue",
        }
    ]

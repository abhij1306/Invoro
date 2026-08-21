from __future__ import annotations

from .test_detail_extractor_structured_sources import *  # noqa: F403


@pytest.mark.regression
def test_structured_variant_rows_coerce_is_out_of_stock_flags_strictly() -> None:
    rows = _structured_variants_from_product_payload(
        {
            "variants": [
                {"id": "shoe-8", "sizeName": "8", "isOutOfStock": "false"},
                {"id": "shoe-9", "sizeName": "9", "isOutOfStock": "true"},
                {"id": "shoe-10", "sizeName": "10", "isOutOfStock": "0"},
            ]
        },
        "https://example.com/products/example-shoe",
    )

    variants_by_size = {row.get("size"): row for row in rows}
    assert variants_by_size["8"]["availability"] == "in_stock"
    assert variants_by_size["9"]["availability"] == "out_of_stock"
    assert variants_by_size["10"]["availability"] == "in_stock"

@pytest.mark.regression
def test_extract_ecommerce_detail_rejects_foreign_currency_variants() -> None:
    rows = extract_records(
        "<html><body><main><h1>Leather Jacket</h1></main></body></html>",
        "https://example.com/products/leather-jacket",
        "ecommerce_detail",
        max_records=5,
        adapter_records=[
            {
                "title": "Leather Jacket",
                "currency": "GBP",
                "price": "420.00",
                "variants": [
                    {"color": "Black", "price": "420.00", "currency": "GBP"},
                    {"color": "Black", "price": "490.00", "currency": "EUR"},
                ],
            }
        ],
    )

    assert len(rows) == 1
    assert rows[0]["variants"] == [
        {"color": "Black", "price": "420.00", "currency": "GBP"}
    ]

@pytest.mark.regression
def test_extract_ecommerce_detail_ignores_newsletter_fields_inside_size_container() -> (
    None
):
    html = """
    <html>
      <body>
        <h1>Soft Rock Crewneck</h1>
        <div class="size-selector" aria-label="Size">
          <button type="button" aria-label="S"></button>
          <button type="button" aria-label="M" class="selected"></button>
          <button type="button" aria-label="L"></button>
          <button type="button" aria-label="XL"></button>
          <input type="email" value="Email" />
          <button aria-label="Sign up for updates and promotions">Join</button>
        </div>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.sneakersnstuff.com/products/dime-soft-rock-crewneck-dime2sp2542blk",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["title"] == "Soft Rock Crewneck"
    assert "Email" not in str(record.get("size", ""))
    assert "Sign up" not in json.dumps(record)

@pytest.mark.regression
def test_extract_ecommerce_detail_rejects_promo_and_hex_only_dom_variant_values() -> (
    None
):
    html = """
    <html>
      <body>
        <h1>Everyday Tee</h1>
        <div class="promo-swatch-group" aria-label="Discount">
          <button type="button" aria-label="20% off"></button>
          <button type="button" aria-label="30% off"></button>
        </div>
        <div class="color-swatch-group" aria-label="Color">
          <button type="button" data-value="#ffffff"></button>
          <button type="button" data-value="#000000"></button>
        </div>
        <div class="color-swatch-group" aria-label="Color">
          <button type="button" aria-label="Black" style="background:#000"></button>
          <button type="button" aria-label="White" style="background:#fff"></button>
        </div>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/everyday-tee",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert "20% off" not in json.dumps(record)
    assert "#ffffff" not in json.dumps(record)
    assert record["variants"] == [
        {"color": "Black"},
        {"color": "White"},
    ]

@pytest.mark.regression
def test_extract_ecommerce_detail_rejects_cookie_disclosure_title_and_description() -> (
    None
):
    html = """
    <html>
      <head><title>Barrow Short-sleeved T-shirt</title></head>
      <body>
        <div id="onetrust-preference-center">
          <h1>_clck</h1>
          <section>
            <h2>Description</h2>
            <p>
              This cookie name is associated with software from Dynatrace.
              Used by Microsoft Clarity to connect multiple page views.
              Cookie descriptions are displayed in the Cookie List on the Preference Center.
            </p>
          </section>
        </div>
        <main class="product-detail">
          <div class="brand">Barrow</div>
          <span class="price">INR 7217.00</span>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.luisaviaroma.com/en-in/p/barrow/kids-boys/83I-UKD027",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["title"] == "Barrow Short-sleeved T-shirt"
    assert record.get("description") in (None, "")
    assert "_clck" not in json.dumps(record)
    assert "Microsoft Clarity" not in json.dumps(record)

@pytest.mark.regression
def test_extract_ecommerce_detail_recovers_radio_size_variants_with_stock_availability() -> (
    None
):
    html = """
    <html>
      <body>
        <h1>Bear Minimum Oversized T-Shirt</h1>
        <div class="product-varient-section">
          <p>Please select a size.</p>
          <ul class="sizelist">
            <li class="oval outstock">
              <input id="size_0_0" disabled type="radio" name="sub_prod_0" />
              <label for="size_0_0"><span>XXS</span></label>
              <section class="total-stock">0 Left</section>
            </li>
            <li class="oval selected">
              <input id="size_0_1" checked type="radio" name="sub_prod_0" />
              <label for="size_0_1"><span>XS</span></label>
              <section class="total-stock">17 Left</section>
            </li>
            <li class="oval">
              <input id="size_0_2" type="radio" name="sub_prod_0" />
              <label for="size_0_2"><span>S</span></label>
              <section class="total-stock">75 Left</section>
            </li>
          </ul>
        </div>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.thesouledstore.com/product/oversized-tshirts-bear-minimum",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["availability"] == "in_stock"
    assert record["variants"][0]["availability"] == "out_of_stock"
    assert record["variants"][0]["stock_quantity"] == 0
    assert record["variants"][1]["availability"] == "in_stock"
    assert record["variants"][1]["stock_quantity"] == 17

@pytest.mark.regression
def test_extract_ecommerce_detail_keeps_supported_dom_variant_axes_and_drops_unknown_axes() -> (
    None
):
    html = """
    <html>
      <body>
        <h1>MuscleBlaze Biozyme Performance Whey</h1>
        <fieldset class="weight-options">
          <legend>Weight</legend>
          <label><input checked type="radio" name="weight" value="4.4 Lb" />4.4 Lb</label>
          <label><input type="radio" name="weight" value="0.4 Lb" />0.4 Lb</label>
        </fieldset>
        <fieldset class="flavour-options">
          <legend>Flavour</legend>
          <label><input checked type="radio" name="flavour" value="Rich Chocolate" />Rich Chocolate</label>
          <label><input type="radio" name="flavour" value="Blue Tokai Coffee" />Blue Tokai Coffee</label>
        </fieldset>
        <fieldset class="shipping-options">
          <legend>Shipping</legend>
          <label><input checked type="radio" name="shipping" value="Standard" />Standard</label>
          <label><input type="radio" name="shipping" value="Express" />Express</label>
        </fieldset>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/whey",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["variant_count"] == 4
    assert isinstance(record["variants"], list)
    assert len(record["variants"]) == 4
    assert {variant.get("flavor") for variant in record["variants"]} == {
        "Rich Chocolate",
        "Blue Tokai Coffee",
    }
    assert {variant.get("weight") for variant in record["variants"]} == {
        "4.4 Lb",
        "0.4 Lb",
    }
    assert all("color" not in variant for variant in record["variants"])
    assert all("shipping" not in variant for variant in record["variants"])

@pytest.mark.regression
def test_extract_ecommerce_detail_keeps_fit_dom_variants() -> None:
    html = """
    <html>
      <body>
        <main class="product-detail">
          <h1>Nordstrom Rack Solid Notch Lapel Linen Sport Coat</h1>
          <fieldset>
            <legend>Fit</legend>
            <label><input checked type="radio" name="fit" value="Short" />Short</label>
            <label><input type="radio" name="fit" value="Regular" />Regular</label>
            <label><input type="radio" name="fit" value="Long" />Long</label>
          </fieldset>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.nordstromrack.com/s/example/8050407",
        "ecommerce_detail",
        max_records=1,
        requested_fields=["variants"],
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["variant_count"] == 3
    assert [row["fit"] for row in record["variants"]] == ["Short", "Regular", "Long"]

@pytest.mark.regression
def test_extract_ecommerce_detail_drops_addon_variant_noise_and_keeps_real_axes() -> (
    None
):
    html = """
    <html>
      <body>
        <main class="product-detail">
          <h1>Keychron V1 Max QMK/VIA Wireless Custom Mechanical Keyboard</h1>
          <form class="product-form">
            <fieldset>
              <legend>Type</legend>
              <label><input checked type="radio" name="type" value="Fully Assembled Knob" />Fully Assembled Knob</label>
              <label><input type="radio" name="type" value="Barebone Knob" />Barebone Knob</label>
            </fieldset>
            <fieldset>
              <legend>Color</legend>
              <label><input checked type="radio" name="color" value="Carbon Black" />Carbon Black</label>
            </fieldset>
            <fieldset>
              <legend>Switches</legend>
              <label><input checked type="radio" name="switches" value="Gateron Jupiter Red" />Gateron Jupiter Red</label>
              <label><input type="radio" name="switches" value="Gateron Jupiter Brown" />Gateron Jupiter Brown</label>
              <label><input type="radio" name="switches" value="Gateron Jupiter Banana" />Gateron Jupiter Banana</label>
            </fieldset>
          </form>
          <div class="convx__addons-panel" data-addon-title="Palm Rest">
            <label class="addons-option">
              <input type="checkbox" value="1" />
              <span class="addons-title">Keychron Resin Palm Rest</span>
              <span class="addons-variant">Resin / Q1 / V1 Max / Black Myth Wukong</span>
            </label>
            <label class="addons-option">
              <input type="checkbox" value="2" />
              <span class="addons-title">Keychron Silicone Palm Rest</span>
              <span class="addons-variant">Black / 75%/65% / 317mm</span>
            </label>
          </div>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.keychron.com/products/keychron-v1-max-qmk-via-wireless-custom-mechanical-keyboard",
        "ecommerce_detail",
        max_records=1,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["variant_count"] == 6
    assert {row["type"] for row in record["variants"]} == {
        "Fully Assembled Knob",
        "Barebone Knob",
    }
    assert {row["switches"] for row in record["variants"]} == {
        "Gateron Jupiter Red",
        "Gateron Jupiter Brown",
        "Gateron Jupiter Banana",
    }
    assert all("Palm Rest" not in str(row) for row in record["variants"])

@pytest.mark.regression
def test_extract_ecommerce_detail_prefers_priced_adapter_variants_over_dom_cartesian_guess() -> (
    None
):
    html = """
    <html>
      <body>
        <main class="product-detail">
          <h1>Keychron V1 Max QMK/VIA Wireless Custom Mechanical Keyboard</h1>
          <form class="product-form">
            <fieldset>
              <legend>Type</legend>
              <label><input checked type="radio" name="type" value="Fully Assembled Knob" />Fully Assembled Knob</label>
              <label><input type="radio" name="type" value="Barebone Knob" />Barebone Knob</label>
            </fieldset>
            <fieldset>
              <legend>Color</legend>
              <label><input checked type="radio" name="color" value="Carbon Black" />Carbon Black</label>
            </fieldset>
            <fieldset>
              <legend>Switches</legend>
              <label><input checked type="radio" name="switches" value="Gateron Jupiter Red" />Gateron Jupiter Red</label>
              <label><input type="radio" name="switches" value="Gateron Jupiter Brown" />Gateron Jupiter Brown</label>
              <label><input type="radio" name="switches" value="Gateron Jupiter Banana" />Gateron Jupiter Banana</label>
            </fieldset>
          </form>
        </main>
      </body>
    </html>
    """

    adapter_records = [
        {
            "title": "Keychron V1 Max QMK/VIA Wireless Custom Mechanical Keyboard",
            "price": "104.99",
            "currency": "USD",
            "color": "Carbon Black",
            "variants": [
                {
                    "type": "Fully Assembled Knob",
                    "color": "Carbon Black",
                    "switches": "Gateron Jupiter Red",
                    "sku": "V1M-D1",
                    "price": "104.99",
                    "currency": "USD",
                },
                {
                    "type": "Fully Assembled Knob",
                    "color": "Carbon Black",
                    "switches": "Gateron Jupiter Brown",
                    "sku": "V1M-D2",
                    "price": "104.99",
                    "currency": "USD",
                },
                {
                    "type": "Fully Assembled Knob",
                    "color": "Carbon Black",
                    "switches": "Gateron Jupiter Banana",
                    "sku": "V1M-D3",
                    "price": "104.99",
                    "currency": "USD",
                },
                {
                    "type": "Barebone Knob",
                    "color": "Carbon Black",
                    "switches": "Barebone",
                    "sku": "V1M-B1",
                    "price": "94.99",
                    "currency": "USD",
                },
            ],
            "variant_count": 4,
        }
    ]

    rows = extract_records(
        html,
        "https://www.keychron.com/products/keychron-v1-max-qmk-via-wireless-custom-mechanical-keyboard",
        "ecommerce_detail",
        max_records=1,
        adapter_records=adapter_records,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["variant_count"] == 4
    assert record["color"] == "Carbon Black"
    assert {
        (row["type"], row["switches"], row["price"]) for row in record["variants"]
    } == {
        ("Fully Assembled Knob", "Gateron Jupiter Red", "104.99"),
        ("Fully Assembled Knob", "Gateron Jupiter Brown", "104.99"),
        ("Fully Assembled Knob", "Gateron Jupiter Banana", "104.99"),
        ("Barebone Knob", "Barebone", "94.99"),
    }

@pytest.mark.regression
def test_extract_ecommerce_detail_prefers_structured_shopify_variants_over_dom_guess() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Keychron V1 Max QMK/VIA Wireless Custom Mechanical Keyboard",
          "offers": {"priceCurrency": "USD"},
          "options": [
            {"name": "Type"},
            {"name": "Color"},
            {"name": "Switches"}
          ],
          "variants": [
            {
              "id": "40637899669593",
              "sku": "V1M-D1",
              "price": "10499",
              "option1": "Fully Assembled Knob",
              "option2": "Carbon Black",
              "option3": "Gateron Jupiter Red",
              "url": "https://www.keychron.com/products/keychron-v1-max-qmk-via-wireless-custom-mechanical-keyboard?variant=40637899669593"
            },
            {
              "id": "40637899735129",
              "sku": "V1M-D3",
              "price": "10499",
              "option1": "Fully Assembled Knob",
              "option2": "Carbon Black",
              "option3": "Gateron Jupiter Brown",
              "url": "https://www.keychron.com/products/keychron-v1-max-qmk-via-wireless-custom-mechanical-keyboard?variant=40637899735129"
            },
            {
              "id": "40637899800665",
              "sku": "V1M-D4",
              "price": "10499",
              "option1": "Fully Assembled Knob",
              "option2": "Carbon Black",
              "option3": "Gateron Jupiter Banana",
              "url": "https://www.keychron.com/products/keychron-v1-max-qmk-via-wireless-custom-mechanical-keyboard?variant=40637899800665"
            },
            {
              "id": "40637966221401",
              "sku": "V1M-Z4",
              "price": "9499",
              "option1": "Barebone Knob",
              "option2": "Carbon Black",
              "option3": "Barebone",
              "url": "https://www.keychron.com/products/keychron-v1-max-qmk-via-wireless-custom-mechanical-keyboard?variant=40637966221401"
            }
          ]
        }
        </script>
      </head>
      <body>
        <main class="product-detail">
          <h1>Keychron V1 Max QMK/VIA Wireless Custom Mechanical Keyboard</h1>
          <form class="product-form">
            <fieldset>
              <legend>Type</legend>
              <label><input checked type="radio" name="type" value="Fully Assembled Knob" />Fully Assembled Knob</label>
              <label><input type="radio" name="type" value="Barebone Knob" />Barebone Knob</label>
            </fieldset>
            <fieldset>
              <legend>Color</legend>
              <label><input checked type="radio" name="color" value="Carbon Black" />Carbon Black</label>
            </fieldset>
            <fieldset>
              <legend>Switches</legend>
              <label><input checked type="radio" name="switches" value="Gateron Jupiter Red" />Gateron Jupiter Red</label>
              <label><input type="radio" name="switches" value="Gateron Jupiter Brown" />Gateron Jupiter Brown</label>
              <label><input type="radio" name="switches" value="Gateron Jupiter Banana" />Gateron Jupiter Banana</label>
              <label><input type="radio" name="switches" value="Barebone" />Barebone</label>
            </fieldset>
          </form>
          <div class="convx__addons-panel">
            <label class="addons-option">
              <input type="checkbox" value="1" />
              <span class="addons-title">Keychron Resin Palm Rest</span>
              <span class="addons-variant">Resin / Q1 / V1 Max / Black Myth Wukong</span>
            </label>
            <label class="addons-option">
              <input type="checkbox" value="2" />
              <span class="addons-title">Keychron Silicone Palm Rest</span>
              <span class="addons-variant">Black / 75%/65% / 317mm</span>
            </label>
          </div>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.keychron.com/products/keychron-v1-max-qmk-via-wireless-custom-mechanical-keyboard",
        "ecommerce_detail",
        max_records=1,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["variant_count"] == 4
    assert record["color"] == "Carbon Black"
    assert {
        (row["type"], row["switches"], row["price"]) for row in record["variants"]
    } == {
        ("Fully Assembled Knob", "Gateron Jupiter Red", "104.99"),
        ("Fully Assembled Knob", "Gateron Jupiter Brown", "104.99"),
        ("Fully Assembled Knob", "Gateron Jupiter Banana", "104.99"),
        ("Barebone Knob", "Barebone", "94.99"),
    }

@pytest.mark.regression
def test_should_collect_dom_variants_keeps_priced_shopify_rows_over_unpriced_dom_guess() -> (
    None
):
    candidates = {
        "variants": [
            [
                {
                    "sku": "V1M-D1",
                    "price": "10499",
                    "option1": "Fully Assembled Knob",
                    "option2": "Carbon Black",
                    "option3": "Gateron Jupiter Red",
                    "url": "https://example.com/products/keychron?variant=1",
                },
                {
                    "sku": "V1M-D2",
                    "price": "10499",
                    "option1": "Fully Assembled Knob",
                    "option2": "Carbon Black",
                    "option3": "Gateron Jupiter Brown",
                    "url": "https://example.com/products/keychron?variant=2",
                },
                {
                    "sku": "V1M-D3",
                    "price": "10499",
                    "option1": "Fully Assembled Knob",
                    "option2": "Carbon Black",
                    "option3": "Gateron Jupiter Banana",
                    "url": "https://example.com/products/keychron?variant=3",
                },
                {
                    "sku": "V1M-B1",
                    "price": "9499",
                    "option1": "Barebone Knob",
                    "option2": "Carbon Black",
                    "option3": "Barebone",
                    "url": "https://example.com/products/keychron?variant=4",
                },
            ]
        ]
    }
    dom_variants = {
        "variants": [
            {"type": "Fully Assembled Knob", "switches": "Gateron Jupiter Red"},
            {"type": "Fully Assembled Knob", "switches": "Gateron Jupiter Brown"},
            {"type": "Fully Assembled Knob", "switches": "Gateron Jupiter Banana"},
            {"type": "Fully Assembled Knob", "switches": "Barebone"},
            {"type": "Barebone Knob", "switches": "Gateron Jupiter Red"},
            {"type": "Barebone Knob", "switches": "Gateron Jupiter Brown"},
            {"type": "Barebone Knob", "switches": "Gateron Jupiter Banana"},
            {"type": "Barebone Knob", "switches": "Barebone"},
        ]
    }

    assert (
        detail_dom_completion._should_collect_dom_variants(candidates, dom_variants)
        is False
    )

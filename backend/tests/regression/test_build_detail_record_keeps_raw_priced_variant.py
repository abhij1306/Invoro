from __future__ import annotations

from .test_detail_extractor_structured_sources import *  # noqa: F403


@pytest.mark.regression
def test_build_detail_record_keeps_raw_priced_variant_rows_over_dom_backfill_guess() -> (
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

    record = build_detail_record(
        html,
        "https://www.keychron.com/products/keychron-v1-max-qmk-via-wireless-custom-mechanical-keyboard",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Keychron V1 Max QMK/VIA Wireless Custom Mechanical Keyboard",
                "variants": [
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
                ],
                "variant_count": 4,
            }
        ],
    )

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
def test_extract_ecommerce_detail_keeps_ifixit_variant_group_local_and_drops_pdp_chrome() -> (
    None
):
    html = """
    <html>
      <body>
        <section id="product-overview">
          <div class="flex">
            <div class="relative text-sm w-full" data-testid="product-info-section">
              <h1>iPhone 16 Plus Battery</h1>
              <div class="chakra-stack css-37za6y">
                <div class="chakra-stack css-24ivmg">
                  <p>Condition: New</p>
                </div>
                <div class="chakra-stack css-24ivmg">
                  <p>Part or Kit</p>
                  <div data-testid="product-variants-selector">
                    <div data-testid="IF494-001-1" data-selected="false">
                      <p><span>Option</span>Part Only<span>not selected</span></p>
                    </div>
                    <div data-testid="IF494-001-2" data-selected="true">
                      <p><span>Option</span>Fix Kit<span>selected</span></p>
                    </div>
                  </div>
                </div>
              </div>
              <div>
                <span>Shipping restrictions apply</span>
                <button aria-label="Learn more about shipping restrictions" data-state="closed">i</button>
              </div>
              <button aria-label="Learn more about our return policy" data-state="closed">i</button>
              <div data-state="open">
                <h3><button type="button" data-state="open">Compatibility</button></h3>
                <div data-state="open">
                  <a href="#compatibility">iPhone 16 Plus A3082</a>
                </div>
              </div>
              <div data-state="closed">
                <h3><button type="button" data-state="closed">Kit Contents</button></h3>
              </div>
            </div>
          </div>
        </section>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.ifixit.com/products/iphone-16-plus-battery",
        "ecommerce_detail",
        max_records=1,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["variant_count"] == 2
    assert [variant.get("bundle_type") for variant in record["variants"]] == [
        "Part Only",
        "Fix Kit",
    ]
    assert all(
        "shipping restrictions" not in str(variant).lower()
        for variant in record["variants"]
    )
    assert all(
        "return policy" not in str(variant).lower() for variant in record["variants"]
    )

@pytest.mark.regression
def test_extract_ecommerce_detail_recovers_variant_urls_from_dom_choice_links() -> None:
    html = """
    <html>
      <body>
        <h1>Norton Velvet Recliner</h1>
        <div class="color-selector" role="radiogroup" aria-label="Colour">
          <a href="/product/norton-velvet-recliner-in-grey-2207513.html">
            <button type="button" aria-label="Grey" class="selected"></button>
          </a>
          <a href="/product/norton-velvet-recliner-in-beige-2207512.html">
            <button type="button" aria-label="Beige"></button>
          </a>
          <a href="/product/norton-velvet-recliner-in-brown-2268528.html">
            <button type="button" aria-label="Brown"></button>
          </a>
        </div>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.pepperfry.com/product/norton-velvet-recliner-in-grey-2207513.html",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["variant_count"] == 3
    assert record["variants"][0]["url"] == (
        "https://www.pepperfry.com/product/norton-velvet-recliner-in-grey-2207513.html"
    )
    assert record["variants"][1]["url"] == (
        "https://www.pepperfry.com/product/norton-velvet-recliner-in-beige-2207512.html"
    )
    assert record["variants"][2]["url"] == (
        "https://www.pepperfry.com/product/norton-velvet-recliner-in-brown-2268528.html"
    )

@pytest.mark.regression
def test_extract_ecommerce_detail_recovers_anchor_only_color_swatches() -> None:
    html = """
    <html>
      <body>
        <h1>Arrival 5&quot; Shorts</h1>
        <div class="color-selector" role="radiogroup" aria-label="Colour">
          <a
            href="/products/gymshark-arrival-5-shorts-black-ss22"
            aria-label='Arrival 5" Shorts in Black'
          ></a>
          <a
            href="/products/gymshark-arrival-5-shorts-white-ss22"
            aria-label='Arrival 5" Shorts in White'
          ></a>
        </div>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.gymshark.com/products/gymshark-arrival-5-shorts-black-ss22",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["variant_count"] == 2
    assert [(variant["color"], variant["url"]) for variant in record["variants"]] == [
        (
            "Black",
            "https://www.gymshark.com/products/gymshark-arrival-5-shorts-black-ss22",
        ),
        (
            "White",
            "https://www.gymshark.com/products/gymshark-arrival-5-shorts-white-ss22",
        ),
    ]

@pytest.mark.regression
def test_extract_ecommerce_detail_recovers_unlabeled_color_swatch_urls() -> None:
    html = """
    <html>
      <body>
        <h1>Men's Wool Runner</h1>
        <div class="color-selector" role="radiogroup" aria-label="Color">
          <a href="/products/mens-wool-runners-natural-grey"></a>
          <a href="/products/mens-wool-runners-tuke-river" aria-current="true"></a>
          <a href="/products/mens-wool-runners-true-black"></a>
        </div>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.allbirds.com/products/mens-wool-runners-tuke-river",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["variant_count"] == 3
    assert [(variant["color"], variant["url"]) for variant in record["variants"]] == [
        (
            "Natural Grey",
            "https://www.allbirds.com/products/mens-wool-runners-natural-grey",
        ),
        (
            "Tuke River",
            "https://www.allbirds.com/products/mens-wool-runners-tuke-river",
        ),
        (
            "True Black",
            "https://www.allbirds.com/products/mens-wool-runners-true-black",
        ),
    ]

@pytest.mark.regression
def test_extract_ecommerce_detail_recovers_hidden_anchor_color_swatch_urls() -> None:
    html = """
    <html>
      <body>
        <h1>Ballpark Tassel Suede Sneakers - Black</h1>
        <div class="swatch-options" role="radiogroup" aria-label="Color">
          <button aria-label="Choose Blush variant" data-testid="swatch-option-ballpark-tassel-suede-sneakers-blush-unselected">
            <span style="background-color:#C98F9D"></span>
            <span class="h-0 w-0 opacity-0">
              <a aria-hidden="true" tabindex="-1" href="/products/ballpark-tassel-suede-sneakers-blush">Blush</a>
            </span>
          </button>
          <button aria-label="Choose Black variant" data-testid="swatch-option-ballpark-tassel-suede-sneakers-black-selected" aria-checked="true">
            <span style="background-color:#000000"></span>
            <span class="h-0 w-0 opacity-0">
              <a aria-hidden="true" tabindex="-1" href="/products/ballpark-tassel-suede-sneakers-black">Black</a>
            </span>
          </button>
        </div>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.fashionnova.com/products/ballpark-tassel-suede-sneakers-black",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    assert {(variant["color"], variant["url"]) for variant in rows[0]["variants"]} == {
        (
            "Blush",
            "https://www.fashionnova.com/products/ballpark-tassel-suede-sneakers-blush",
        ),
        (
            "Black",
            "https://www.fashionnova.com/products/ballpark-tassel-suede-sneakers-black",
        ),
    }

@pytest.mark.regression
def test_extract_ecommerce_detail_recovers_linked_scent_offer_variants() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Allover Body Mist",
          "offers": [
            {
              "@type": "Offer",
              "availability": "https://schema.org/InStock",
              "price": "4700.0",
              "priceCurrency": "INR",
              "url": "https://fentybeauty.com/en-in/products/allover-body-mist-green-raspberry?variant=43357324083245",
              "itemOffered": {
                "@type": "Product",
                "name": "Allover Body Mist - Green Raspberry",
                "sku": "FFS00144",
                "image": "https://fentybeauty.com/cdn/green.jpg"
              }
            },
            {
              "@type": "Offer",
              "availability": "https://schema.org/InStock",
              "price": "4700.0",
              "priceCurrency": "INR",
              "url": "https://fentybeauty.com/en-in/products/allover-body-mist-hey-bouquet?variant=44216944033837",
              "itemOffered": {
                "@type": "Product",
                "name": "Allover Body Mist - Hey, Bouquet",
                "sku": "FFS00109",
                "image": "https://fentybeauty.com/cdn/bouquet.jpg"
              }
            }
          ]
        }
        </script>
      </head>
      <body><h1>Allover Body Mist</h1></body>
    </html>
    """

    rows = extract_records(
        html,
        "https://fentybeauty.com/en-in/products/allover-body-mist-green-raspberry",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    assert {
        (variant["scent"], variant["sku"], variant["url"])
        for variant in rows[0]["variants"]
    } == {
        (
            "Green Raspberry",
            "FFS00144",
            "https://fentybeauty.com/en-in/products/allover-body-mist-green-raspberry?variant=43357324083245",
        ),
        (
            "Hey, Bouquet",
            "FFS00109",
            "https://fentybeauty.com/en-in/products/allover-body-mist-hey-bouquet?variant=44216944033837",
        ),
    }
    assert all("color" not in variant for variant in rows[0]["variants"])

@pytest.mark.asyncio
@pytest.mark.regression
async def test_shopify_adapter_expands_linked_product_color_handles(
    monkeypatch,
) -> None:
    html = """
    <html>
      <head><script>Shopify.theme = { "name": "test" };</script></head>
      <body>
        <h1>Ballpark Tassel Suede Sneakers - Black</h1>
        <div class="swatch-options" role="radiogroup" aria-label="Color">
          <a href="/products/ballpark-tassel-suede-sneakers-black" aria-label="Black"></a>
          <a href="/products/ballpark-tassel-suede-sneakers-blush" aria-label="Blush"></a>
        </div>
      </body>
    </html>
    """
    products = {
        "ballpark-tassel-suede-sneakers-black": {
            "id": 1,
            "title": "Ballpark Tassel Suede Sneakers - Black",
            "vendor": "Fashion Nova",
            "handle": "ballpark-tassel-suede-sneakers-black",
            "product_type": "Shoes",
            "options": [{"name": "Size"}],
            "images": ["https://cdn.example/black.jpg"],
            "variants": [
                {
                    "id": 101,
                    "sku": "SPECIALGUEST_Black_6",
                    "available": True,
                    "price": 3999,
                    "option1": "6",
                }
            ],
        },
        "ballpark-tassel-suede-sneakers-blush": {
            "id": 2,
            "title": "Ballpark Tassel Suede Sneakers - Blush",
            "vendor": "Fashion Nova",
            "handle": "ballpark-tassel-suede-sneakers-blush",
            "product_type": "Shoes",
            "options": [{"name": "Size"}],
            "images": ["https://cdn.example/blush.jpg"],
            "variants": [
                {
                    "id": 201,
                    "sku": "SPECIALGUEST_Blush_6",
                    "available": True,
                    "price": 3999,
                    "option1": "6",
                }
            ],
        },
    }

    async def _fake_request_json(api_url: str, **_kwargs):
        handle = api_url.rsplit("/products/", 1)[1].removesuffix(".js")
        return products[handle]

    adapter = ShopifyAdapter()
    monkeypatch.setattr(adapter, "_request_json", _fake_request_json)

    result = await adapter.extract(
        "https://www.fashionnova.com/products/ballpark-tassel-suede-sneakers-black",
        html,
        "ecommerce_detail",
    )

    record = result.records[0]
    assert record["variant_count"] == 2
    assert {
        (variant["color"], variant["size"], variant["sku"])
        for variant in record["variants"]
    } == {
        ("Black", "6", "SPECIALGUEST_Black_6"),
        ("Blush", "6", "SPECIALGUEST_Blush_6"),
    }

@pytest.mark.regression
def test_extract_ecommerce_detail_recovers_variant_urls_from_js_state_option_mapping() -> (
    None
):
    html = """
    <html>
      <head>
        <script id="__NEXT_DATA__" type="application/json">
        {
          "props": {
            "pageProps": {
              "data": {
                "productDetailData": {
                  "result": [
                    {
                      "data": {
                        "id": "140632",
                        "options": [
                          {
                            "id": "color",
                            "label": "Frame Color",
                            "optionList": [
                              {
                                "id": "14417_27737_23249_26121_23251",
                                "title": "Transparent Grey"
                              },
                              {
                                "id": "14417_27663_23245_26121_23252",
                                "title": "Transparent Pink"
                              }
                            ]
                          }
                        ],
                        "clarityOptionsMapping": [
                          {
                            "color": "14417_27737_23249_26121_23251",
                            "productId": "140632"
                          },
                          {
                            "color": "14417_27663_23245_26121_23252",
                            "productId": "208303"
                          }
                        ]
                      }
                    }
                  ]
                }
              }
            }
          }
        }
        </script>
      </head>
      <body>
        <h1>John Jacobs JJ S13313</h1>
        <div class="color-selector" role="radiogroup" aria-label="Frame Color">
          <button
            id="14417_27737_23249_26121_23251"
            type="button"
            aria-label="Transparent Grey"
            class="selected"
          ></button>
          <button
            id="14417_27663_23245_26121_23252"
            type="button"
            aria-label="Transparent Pink"
          ></button>
        </div>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.lenskart.com/john-jacobs-jj-s13313-c1-sunglasses.html?productId=140632",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["variant_count"] == 2
    assert record["variants"][0]["url"] == (
        "https://www.lenskart.com/john-jacobs-jj-s13313-c1-sunglasses.html?productId=140632"
    )
    assert record["variants"][1]["url"] == (
        "https://www.lenskart.com/john-jacobs-jj-s13313-c1-sunglasses.html?productId=208303"
    )

@pytest.mark.regression
def test_extract_ecommerce_detail_skips_unnamed_dom_variant_groups() -> None:
    html = """
    <html>
      <body>
        <h1>Trail Runner</h1>
        <div class="swatch-group">
          <button type="button" aria-label="Black"></button>
          <button type="button" aria-label="Olive"></button>
        </div>
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
    assert "variants" not in record

@pytest.mark.regression
def test_extract_ecommerce_detail_ignores_review_qa_controls_and_payment_icons() -> (
    None
):
    html = """
    <html>
      <body>
        <section class="secure-payment">
          <img src="https://cdn.example.com/assets/amex.svg" alt="American Express" />
          <img src="https://cdn.example.com/assets/paypal.svg" alt="PayPal" />
        </section>
        <main>
          <h1>7 Cup Food Processor</h1>
          <section class="product-gallery">
            <img src="https://cdn.example.com/products/food-processor.jpg?width=1200" alt="7 Cup Food Processor front view" />
          </section>
          <button aria-controls="specifications-panel">Specifications</button>
          <section id="specifications-panel">
            <p>7 cup work bowl with high, low, and pulse speed controls.</p>
          </section>
          <section class="product-questions">
            <div role="radiogroup" aria-label="1 Answers to Question: Will this shred cooked pork?">
              <button type="button">See KASA Review profile.</button>
              <button type="button">Content helpfulness</button>
              <button type="button">Report this answer by KASA Review as inappropriate.</button>
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
        requested_fields=["specifications"],
    )

    assert len(rows) == 1
    record = rows[0]
    assert (
        record["image_url"]
        == "https://cdn.example.com/products/food-processor.jpg?width=1200"
    )
    assert (
        record["specifications"]
        == "7 cup work bowl with high, low, and pulse speed controls."
    )
    assert "additional_images" not in record
    assert "variants" not in record

@pytest.mark.regression
def test_extract_ecommerce_detail_does_not_use_bundle_upsell_as_title() -> None:
    html = """
    <html>
      <head>
        <title>Rockler Table Saw Crosscut Sled</title>
      </head>
      <body>
        <main>
          <h1>Frequently Bought Together</h1>
          <div class="price">$249.99</div>
          <img src="https://cdn.example.com/products/table-saw-sled.jpg" alt="Table saw crosscut sled" />
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/rockler-table-saw-crosscut-sled",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["title"] == "Rockler Table Saw Crosscut Sled"
    assert record["title"] != "Frequently Bought Together"

from __future__ import annotations

from .test_selectolax_css_migration import AmazonAdapter, amazon, build_detail_record, crawler_runtime_settings, extract_listing_records, extract_selector_value, pytest  # fmt: skip

@pytest.mark.regression
def test_detail_extractor_normalizes_category_objects_from_network_payloads() -> None:
    record = build_detail_record(
        "<html><body><h1>Combination Pliers</h1></body></html>",
        "https://practicesoftwaretesting.com/product/01KPJ56NBS8K3WVA5E9F7GX94R",
        "ecommerce_detail",
        ["title", "category"],
        network_payloads=[
            {
                "body": {
                    "product": {
                        "title": "Combination Pliers",
                        "price": "14.15",
                        "category": {
                            "id": "01KPJ56NAAWFTC0M9X80YZJ3F5",
                            "name": "Pliers",
                            "slug": "pliers",
                        },
                    }
                }
            }
        ],
    )

    assert record["title"] == "Combination Pliers"
    assert record["category"] == "Pliers"

@pytest.mark.regression
def test_detail_extractor_reads_category_from_dom_breadcrumbs() -> None:
    record = build_detail_record(
        """
        <html>
          <body>
            <ol aria-label="breadcrumb">
              <li><a href="/">Home</a></li>
              <li><a href="/women">Women</a></li>
              <li><a href="/women/dresses">Dresses</a></li>
              <li>Linen Midi Dress</li>
            </ol>
            <main><h1>Linen Midi Dress</h1></main>
          </body>
        </html>
        """,
        "https://example.com/products/linen-midi-dress",
        "ecommerce_detail",
        ["title", "category", "gender"],
    )

    assert record["title"] == "Linen Midi Dress"
    assert record["category"] == "Women > Dresses"
    assert record["gender"] == "women"

@pytest.mark.regression
def test_detail_extractor_prefers_visible_breadcrumb_category_over_structured_category() -> (
    None
):
    record = build_detail_record(
        """
        <html>
          <head>
            <script type="application/ld+json">
            {
              "@context": "https://schema.org",
              "@type": "Product",
              "name": "Just Vibes Strapless Pant Set - Yellow",
              "category": "Furniture Sets",
              "image": "https://example.com/pant-set.jpg",
              "offers": {"@type": "Offer", "price": "18.00", "priceCurrency": "USD"}
            }
            </script>
          </head>
          <body>
            <nav class="MuiBreadcrumbs-root">
              <ol>
                <li><a href="/women">Women</a></li>
                <li aria-hidden="true">›</li>
                <li><a href="/matching-sets">Shop All Matching Sets</a></li>
                <li aria-hidden="true">›</li>
                <li><span>Just Vibes Strapless Pant Set - Yellow</span></li>
              </ol>
            </nav>
            <main><h1>Just Vibes Strapless Pant Set - Yellow</h1></main>
          </body>
        </html>
        """,
        "https://example.com/products/just-vibes-strapless-pant-set-yellow",
        "ecommerce_detail",
        None,
    )

    assert record["category"] == "Women > Matching Sets"
    assert record["gender"] == "women"

@pytest.mark.regression
def test_listing_extractor_prefers_structured_name_over_item_position_for_title() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "ItemList",
          "itemListElement": [
            {
              "@type": "ListItem",
              "position": 1,
              "item": {
                "@type": "Product",
                "name": "Dyson V12 Detect Slim",
                "url": "/vacuum-cleaners/cord-free/dyson-v12-detect-slim",
                "offers": {
                  "@type": "Offer",
                  "price": "55900",
                  "availability": "https://schema.org/InStock"
                }
              }
            }
          ]
        }
        </script>
      </head>
      <body></body>
    </html>
    """

    rows = extract_listing_records(
        html,
        "https://www.dyson.in/vacuum-cleaners/cord-free",
        "ecommerce_listing",
        max_records=10,
    )

    assert rows == [
        {
            "source_url": "https://www.dyson.in/vacuum-cleaners/cord-free",
            "_source": "structured_listing",
            "title": "Dyson V12 Detect Slim",
            "price": "55900",
            "availability": "in_stock",
            "url": "https://www.dyson.in/vacuum-cleaners/cord-free/dyson-v12-detect-slim",
        }
    ]

@pytest.mark.regression
def test_listing_extractor_uses_json_ld_product_id_as_url_with_offer_fields() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "ItemList",
          "itemListElement": [
            {
              "@type": "ListItem",
              "position": 1,
              "item": {
                "@type": "Product",
                "@id": "https://shop.example.com/products/merino-shirt/p",
                "name": "Merino Shirt",
                "brand": {"@type": "Brand", "name": "Northline"},
                "image": "https://cdn.example.com/merino-shirt.jpg",
                "offers": {
                  "@type": "AggregateOffer",
                  "lowPrice": 399,
                  "highPrice": 399,
                  "priceCurrency": "BRL"
                }
              }
            }
          ]
        }
        </script>
      </head>
      <body>
        <article class="product-card">
          <a href="https://shop.example.com/products/merino-shirt/p">
            <img src="https://cdn.example.com/merino-shirt.jpg" alt="Look-front">
            <span>Look-front</span>
            <span>$399</span>
          </a>
        </article>
      </body>
    </html>
    """

    rows = extract_listing_records(
        html,
        "https://shop.example.com/collections/shirts",
        "ecommerce_listing",
        max_records=10,
    )

    assert rows == [
        {
            "source_url": "https://shop.example.com/collections/shirts",
            "_source": "structured_listing",
            "title": "Merino Shirt",
            "brand": "Northline",
            "image_url": "https://cdn.example.com/merino-shirt.jpg",
            "price": "399",
            "original_price": "399",
            "currency": "BRL",
            "url": "https://shop.example.com/products/merino-shirt/p",
        }
    ]

@pytest.mark.regression
def test_xpath_selector_extraction_remains_unchanged() -> None:
    html = """
    <html>
      <body>
        <div class="details">
          <span data-testid="salary">$150,000</span>
        </div>
      </body>
    </html>
    """

    value, count, selector_used = extract_selector_value(
        html,
        xpath="//span[@data-testid='salary']/text()",
    )

    assert value == "$150,000"
    assert count == 1
    assert selector_used == "//span[@data-testid='salary']/text()"

@pytest.mark.regression
def test_xpath_selector_extraction_applies_regex_to_xpath_result() -> None:
    html = """
    <html>
      <body>
        <span class="rating">star-rating Three</span>
        <script>var unrelated = "star-rating Five";</script>
      </body>
    </html>
    """

    value, count, selector_used = extract_selector_value(
        html,
        xpath="//span[@class='rating']/text()",
        regex=r"star-rating\s+(\w+)",
    )

    assert value == "Three"
    assert count == 1
    assert selector_used == "//span[@class='rating']/text()"

@pytest.mark.regression
def test_xpath_regex_invalid_timeout_falls_back_without_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        crawler_runtime_settings, "selector_regex_timeout_seconds", "bad"
    )
    html = '<span class="rating">star-rating Three</span>'

    with pytest.raises(ValueError, match="selector_regex_timeout_seconds"):
        extract_selector_value(
            html,
            xpath="//span[@class='rating']/text()",
            regex=r"star-rating\s+(\w+)",
        )

@pytest.mark.asyncio
@pytest.mark.regression
async def test_amazon_adapter_preserves_css_field_output() -> None:
    result = await AmazonAdapter().extract(
        "https://www.amazon.com/dp/example",
        """
        <html>
          <body>
            <span id="productTitle">Widget Prime</span>
            <span class="a-price"><span class="a-offscreen">$19.99</span></span>
            <a id="bylineInfo">Brand: Orion</a>
            <span id="acrCustomerReviewText">128 ratings</span>
            <span id="acrPopover"><span class="a-icon-alt">4.8 out of 5 stars</span></span>
            <img id="landingImage" src="https://example.com/widget.jpg">
            <div id="feature-bullets">Fast shipping and long battery life.</div>
            <div id="availability"><span>In Stock.</span></div>
          </body>
        </html>
        """,
        "ecommerce_detail",
    )

    assert len(result.records) == 1
    record = result.records[0]
    assert record["title"] == "Widget Prime"
    assert record["price"] == "$19.99"
    assert record["brand"] == "Orion"
    assert record["rating"] == pytest.approx(4.8)
    assert record["review_count"] == 128
    assert record["image_url"] == "https://example.com/widget.jpg"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_amazon_adapter_preserves_currency_code_in_price_text() -> None:
    result = await AmazonAdapter().extract(
        "https://www.amazon.com/dp/example",
        """
        <html>
          <body>
            <span id="productTitle">Widget Prime</span>
            <span class="a-price"><span class="a-offscreen">USD 19.99</span></span>
          </body>
        </html>
        """,
        "ecommerce_detail",
    )

    record = result.records[0]
    assert record["price"] == "USD 19.99"
    assert record["currency"] == "USD"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_amazon_adapter_combines_visible_whole_and_fraction_price() -> None:
    result = await AmazonAdapter().extract(
        "https://www.amazon.com/dp/B08J5F3G18",
        """
        <html>
          <body>
            <span id="productTitle">EVGA GeForce RTX 3090</span>
            <span class="a-price">
              <span class="a-price-symbol">$</span>
              <span class="a-price-whole">1,359.</span>
              <span class="a-price-fraction">96</span>
            </span>
          </body>
        </html>
        """,
        "ecommerce_detail",
    )

    assert len(result.records) == 1
    record = result.records[0]
    assert record["price"] == "$1,359.96"
    assert record["currency"] == "USD"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_amazon_adapter_uses_currency_decimal_places_for_zero_decimal_markets() -> (
    None
):
    result = await AmazonAdapter().extract(
        "https://www.amazon.co.jp/dp/example",
        """
        <html>
          <body>
            <span id="productTitle">Desk Lamp</span>
            <span class="a-price">
              <span class="a-price-symbol">JPY</span>
              <span class="a-price-whole">1,359.</span>
              <span class="a-price-fraction">96</span>
            </span>
          </body>
        </html>
        """,
        "ecommerce_detail",
    )

    assert len(result.records) == 1
    record = result.records[0]
    assert record["price"] == "JPY 1,359"
    assert record["currency"] == "JPY"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_amazon_adapter_preserves_configured_three_decimal_price(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(amazon.CURRENCY_DECIMAL_PLACES, "BHD", 3)

    result = await AmazonAdapter().extract(
        "https://www.amazon.com/dp/example",
        """
        <html>
          <body>
            <span id="productTitle">Desk Lamp</span>
            <span class="a-price">
              <span class="a-price-symbol">BHD</span>
              <span class="a-price-whole">1,359</span>
              <span class="a-price-fraction">968</span>
            </span>
          </body>
        </html>
        """,
        "ecommerce_detail",
    )

    assert len(result.records) == 1
    record = result.records[0]
    assert record["price"] == "BHD 1,359.968"
    assert record["currency"] == "BHD"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_amazon_adapter_preserves_store_brand_suffix() -> None:
    result = await AmazonAdapter().extract(
        "https://www.amazon.com/dp/example",
        """
        <html>
          <body>
            <span id="productTitle">Mesh Shorts</span>
            <a id="bylineInfo">Visit the Under Armour Store</a>
          </body>
        </html>
        """,
        "ecommerce_detail",
    )

    assert result.records[0]["brand"] == "Under Armour"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_amazon_adapter_extracts_inline_twister_variants() -> None:
    result = await AmazonAdapter().extract(
        "https://www.amazon.com/Under-Armour-Mens-Tech-Shorts/dp/B016APPQ4S",
        """
        <html>
          <body>
            <span id="productTitle">Under Armour Men's Tech Mesh Shorts</span>
            <a id="bylineInfo">Visit the Under Armour Store</a>
            <div id="inline-twister-row-color_name"></div>
            <div id="inline-twister-row-size_name"></div>
            <script type="a-state" data-a-state='{"key":"desktop-twister-sort-filter-data"}'>
            {
              "sortedVariations": [[0,1],[0,2],[1,3],[1,0]],
              "sortedDimValuesForAllDims": {
                "size_name": [
                  {"indexInDimList":0,"defaultAsin":"B07D7TVW4Y","dimensionValueState":"UNAVAILABLE","dimensionValueDisplayText":"X-Small","pageLoadURL":"/dp/B07D7TVW4Y/ref=twister_B016APPQ4S"},
                  {"indexInDimList":1,"defaultAsin":"B095SJ18YH","dimensionValueState":"SELECTED","dimensionValueDisplayText":"Large"},
                  {"indexInDimList":2,"defaultAsin":"B095SGXBJ2","dimensionValueState":"AVAILABLE","dimensionValueDisplayText":"X-Large","pageLoadURL":"/dp/B095SGXBJ2/ref=twister_B016APPQ4S"},
                  {"indexInDimList":3,"defaultAsin":"B095SL1G2D","dimensionValueState":"UNAVAILABLE","dimensionValueDisplayText":"4X-Large Big","pageLoadURL":"/dp/B095SL1G2D/ref=twister_B016APPQ4S"}
                ],
                "color_name": [
                  {"indexInDimList":0,"defaultAsin":"B095SJ18YH","dimensionValueState":"SELECTED","dimensionValueDisplayText":"Pitch Gray-black"},
                  {"indexInDimList":1,"defaultAsin":"B095SL1G2D","dimensionValueState":"UNAVAILABLE","dimensionValueDisplayText":"Pitch Gray/Black","pageLoadURL":"/dp/B095SL1G2D/ref=twister_B016APPQ4S"}
                ]
              }
            }
            </script>
          </body>
        </html>
        """,
        "ecommerce_detail",
    )

    record = result.records[0]
    assert record["brand"] == "Under Armour"
    assert record["color"] == "Pitch Gray-black"
    assert record["size"] == "Large"
    assert record["variant_count"] == 4

@pytest.mark.asyncio
@pytest.mark.regression
async def test_amazon_adapter_variants_survive_full_detail_materialization() -> None:
    html = """
        <html>
          <body>
            <span id="productTitle">Under Armour Men's Tech Mesh Shorts</span>
            <a id="bylineInfo">Visit the Under Armour Store</a>
            <select id="quantity">
              <option>1</option>
              <option>2</option>
              <option>3</option>
              <option>4</option>
              <option>5</option>
            </select>
            <div id="inline-twister-row-color_name"></div>
            <div id="inline-twister-row-size_name"></div>
            <script type="a-state" data-a-state='{"key":"desktop-twister-sort-filter-data"}'>
            {
              "sortedVariations": [[0,1],[0,2],[1,3],[1,0]],
              "sortedDimValuesForAllDims": {
                "size_name": [
                  {"indexInDimList":0,"defaultAsin":"B07D7TVW4Y","dimensionValueState":"UNAVAILABLE","dimensionValueDisplayText":"X-Small","pageLoadURL":"/dp/B07D7TVW4Y/ref=twister_B016APPQ4S"},
                  {"indexInDimList":1,"defaultAsin":"B095SJ18YH","dimensionValueState":"SELECTED","dimensionValueDisplayText":"Large"},
                  {"indexInDimList":2,"defaultAsin":"B095SGXBJ2","dimensionValueState":"AVAILABLE","dimensionValueDisplayText":"X-Large","pageLoadURL":"/dp/B095SGXBJ2/ref=twister_B016APPQ4S"},
                  {"indexInDimList":3,"defaultAsin":"B095SL1G2D","dimensionValueState":"UNAVAILABLE","dimensionValueDisplayText":"4X-Large Big","pageLoadURL":"/dp/B095SL1G2D/ref=twister_B016APPQ4S"}
                ],
                "color_name": [
                  {"indexInDimList":0,"defaultAsin":"B095SJ18YH","dimensionValueState":"SELECTED","dimensionValueDisplayText":"Pitch Gray-black"},
                  {"indexInDimList":1,"defaultAsin":"B095SL1G2D","dimensionValueState":"UNAVAILABLE","dimensionValueDisplayText":"Pitch Gray/Black","pageLoadURL":"/dp/B095SL1G2D/ref=twister_B016APPQ4S"}
                ]
              }
            }
            </script>
          </body>
        </html>
        """

    result = await AmazonAdapter().extract(
        "https://www.amazon.com/Under-Armour-Mens-Tech-Shorts/dp/B016APPQ4S",
        html,
        "ecommerce_detail",
    )

    record = build_detail_record(
        html,
        "https://www.amazon.com/Under-Armour-Mens-Tech-Shorts/dp/B016APPQ4S",
        "ecommerce_detail",
        ["variants"],
        adapter_records=result.records,
    )

    assert record["variant_count"] == 4
    assert [variant["size"] for variant in record["variants"]] == [
        "Large",
        "X-Large",
        "4X-Large Big",
        "X-Small",
    ]

@pytest.mark.regression
def test_amazon_detail_sanitization_rejects_media_and_related_product_variants() -> (
    None
):
    record = build_detail_record(
        "<html><body><h1>EVGA GeForce RTX 3090</h1></body></html>",
        "https://www.amazon.com/dp/B08J5F3G18",
        "ecommerce_detail",
        ["variants"],
        adapter_records=[
            {
                "title": "EVGA GeForce RTX 3090",
                "variants": [
                    {
                        "color": "Shop the Store on Amazon \u203a",
                        "image_url": "https://m.media-amazon.com/images/I/51DRLHAa2AS.jpg",
                    },
                    {
                        "url": "https://www.amazon.com/dp/B08J5F3G18#",
                        "color": "Play Sponsored Video",
                        "image_url": "https://m.media-amazon.com/images/I/51DRLHAa2AS.jpg",
                    },
                    {
                        "url": "https://www.amazon.com/dp/B08J5F3G18#",
                        "color": "Pause Sponsored Video",
                        "image_url": "https://m.media-amazon.com/images/I/51DRLHAa2AS.jpg",
                    },
                    {
                        "url": "https://www.amazon.com/dp/B08J5F3G18#",
                        "color": "Mute Sponsored Video",
                        "image_url": "https://m.media-amazon.com/images/I/51DRLHAa2AS.jpg",
                    },
                    {
                        "color": (
                            "Hemobllo GPU Support Bracket 7.66In Iron White - "
                            "Anti-Sag Locking Screw for Heavy 4090/4080 - "
                            "Magnetic Base Secures PSU Shroud - for Full-Tower "
                            "or Micro-ATX PC Builds"
                        ),
                        "image_url": "https://m.media-amazon.com/images/I/21xLw9EXx7L.jpg",
                    },
                ],
            }
        ],
    )

    assert "variants" not in record
    assert "variant_count" not in record

@pytest.mark.asyncio
@pytest.mark.regression
async def test_amazon_adapter_infers_twister_dimension_order_from_valid_rows() -> None:
    url = "https://www.amazon.com/Philips-Sonicare-Toothbrush-Rechargeable-HX3681/dp/B09LD7WRVS?th=1"
    html = """
        <html>
          <body>
            <span id="productTitle">Philips Sonicare 4100 Series Electric Toothbrush</span>
            <a id="bylineInfo">Visit the Philips Sonicare Store</a>
            <div id="inline-twister-row-color_name"></div>
            <script type="a-state" data-a-state='{"key":"desktop-twister-sort-filter-data"}'>
            {
              "sortedVariations": [[0,0],[0,1],[0,2],[0,3],[0,4],[0,5]],
              "sortedDimValuesForAllDims": {
                "size_name": [
                  {"indexInDimList":0,"defaultAsin":"B09LD7WRVS","dimensionValueState":"SELECTED","dimensionValueDisplayText":"1 Count (Pack of 1)"}
                ],
                "color_name": [
                  {"indexInDimList":0,"defaultAsin":"B09LD7WRVS","dimensionValueState":"SELECTED","dimensionValueDisplayText":"Black"},
                  {"indexInDimList":1,"defaultAsin":"B0F5VQ2GP3","dimensionValueState":"AVAILABLE","dimensionValueDisplayText":"Black + Brush Head Case","pageLoadURL":"/dp/B0F5VQ2GP3/ref=twister_B0CZ8ZQL8C?_encoding=UTF8&psc=1"},
                  {"indexInDimList":2,"defaultAsin":"B09LD8VFS1","dimensionValueState":"AVAILABLE","dimensionValueDisplayText":"Deep Pink","pageLoadURL":"/dp/B09LD8VFS1/ref=twister_B0CZ8ZQL8C?_encoding=UTF8&psc=1"},
                  {"indexInDimList":3,"defaultAsin":"B0F5VG4NB2","dimensionValueState":"AVAILABLE","dimensionValueDisplayText":"Deep Pink + Brush Head Case","pageLoadURL":"/dp/B0F5VG4NB2/ref=twister_B0CZ8ZQL8C?_encoding=UTF8&psc=1"},
                  {"indexInDimList":4,"defaultAsin":"B09LD8T445","dimensionValueState":"AVAILABLE","dimensionValueDisplayText":"White","pageLoadURL":"/dp/B09LD8T445/ref=twister_B0CZ8ZQL8C?_encoding=UTF8&psc=1"},
                  {"indexInDimList":5,"defaultAsin":"B0F5VHLR3X","dimensionValueState":"AVAILABLE","dimensionValueDisplayText":"White + Brush Head Case","pageLoadURL":"/dp/B0F5VHLR3X/ref=twister_B0CZ8ZQL8C?_encoding=UTF8&psc=1"}
                ]
              }
            }
            </script>
          </body>
        </html>
        """
    result = await AmazonAdapter().extract(
        url,
        html,
        "ecommerce_detail",
    )

    record = result.records[0]
    assert record["variant_count"] == 6
    assert [variant["color"] for variant in record["variants"]] == [
        "Black",
        "Black + Brush Head Case",
        "Deep Pink",
        "Deep Pink + Brush Head Case",
        "White",
        "White + Brush Head Case",
    ]
    assert all(
        variant["size"] == "1 Count (Pack of 1)" for variant in record["variants"]
    )

    detail_record = build_detail_record(
        html,
        url,
        "ecommerce_detail",
        ["variants"],
        adapter_records=result.records,
    )
    assert detail_record["variant_count"] == 6
    assert [variant["color"] for variant in detail_record["variants"]] == [
        "Black",
        "Black + Brush Head Case",
        "Deep Pink",
        "Deep Pink + Brush Head Case",
        "White",
        "White + Brush Head Case",
    ]
    assert detail_record["variants"][0].get("url") in (None, "")
    assert (
        detail_record["variants"][1]["url"]
        == "https://www.amazon.com/dp/B0F5VQ2GP3/ref=twister_B0CZ8ZQL8C?_encoding=UTF8&psc=1"
    )
    assert (
        detail_record["variants"][2]["url"]
        == "https://www.amazon.com/dp/B09LD8VFS1/ref=twister_B0CZ8ZQL8C?_encoding=UTF8&psc=1"
    )

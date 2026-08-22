from __future__ import annotations

from .test_selectolax_css_migration import AmazonAdapter, BelkAdapter, LexborHTMLParser, amazon, build_detail_record, collect_structured_candidates, pytest  # fmt: skip


@pytest.mark.asyncio
@pytest.mark.regression
async def test_amazon_adapter_extracts_detail_completeness_fields() -> None:
    result = await AmazonAdapter().extract(
        "https://www.amazon.com/dp/B08J5F3G18",
        """
        <html>
          <body>
            <span id="productTitle">EVGA GeForce RTX 3090</span>
            <span class="a-price"><span class="a-offscreen">$1,499.99</span></span>
            <a id="bylineInfo">Visit the EVGA Store</a>
            <div id="availability"><span>In Stock.</span></div>
            <div id="wayfinding-breadcrumbs_feature_div"><ul><li>Computer Graphics Cards</li></ul></div>
            <img id="landingImage" data-old-hires="https://m.media-amazon.com/images/I/71tLsSyLUZL._SX700_.jpg">
            <div id="altImages">
              <img src="https://m.media-amazon.com/images/I/71tLsSyLUZL._SX700_.jpg">
              <img src="https://m.media-amazon.com/images/I/71tLsSyLUZL._SX900_.jpg">
            </div>
            <div id="feature-bullets">
              <ul>
                <li><span class="a-list-item">24GB GDDR6X memory</span></li>
                <li><span class="a-list-item">Triple-fan cooling</span></li>
              </ul>
            </div>
            <div id="productDescription"><p>Flagship graphics card for 4K gaming.</p></div>
            <table id="productDetails_techSpec_section_1">
              <tr><th>ASIN</th><td>B08J5F3G18</td></tr>
              <tr><th>Item model number</th><td>24G-P5-3987-KR</td></tr>
              <tr><th>UPC</th><td>843368067763</td></tr>
            </table>
            <div id="detailBullets_feature_div">
              <ul>
                <li><span>Best Sellers Rank:</span> #102 in Computers</li>
                <li>
                  <span>Customer Reviews:</span>
                  4.4 out of 5 stars
                  <script>
                    var dpAcrHasRegisteredArcLinkClickAction;
                    P.when('A', 'ready').execute(function(A) {
                      if (dpAcrHasRegisteredArcLinkClickAction !== true) {
                        dpAcrHasRegisteredArcLinkClickAction = true;
                      }
                    });
                  </script>
                </li>
              </ul>
            </div>
          </body>
        </html>
        """,
        "ecommerce_detail",
    )

    record = result.records[0]
    assert record["sku"] == "B08J5F3G18"
    assert record["product_id"] == "B08J5F3G18"
    assert record["part_number"] == "24G-P5-3987-KR"
    assert record["barcode"] == "843368067763"
    assert record["currency"] == "USD"
    assert record["availability"] == "In Stock."
    assert record["product_type"] == "Computer Graphics Cards"
    assert record["features"] == ["24GB GDDR6X memory", "Triple-fan cooling"]
    assert record["specifications"] == (
        "ASIN: B08J5F3G18 Item model number: 24G-P5-3987-KR UPC: 843368067763"
    )
    assert "Best Sellers Rank" not in record["specifications"]
    assert "Customer Reviews" not in record["specifications"]
    assert "P.when" not in record["specifications"]
    assert record["product_details"] == (
        "Flagship graphics card for 4K gaming. "
        "24GB GDDR6X memory Triple-fan cooling "
        "ASIN: B08J5F3G18 Item model number: 24G-P5-3987-KR UPC: 843368067763"
    )
    assert record["image_url"] == "https://m.media-amazon.com/images/I/71tLsSyLUZL.jpg"
    assert record["additional_images"] is None


@pytest.mark.regression
def test_amazon_image_src_fallback_normalizes_low_resolution_url() -> None:
    parser = LexborHTMLParser(
        "<img id='landingImage' src='https://m.media-amazon.com/images/I/51DRLHAa2AS._AC_US40_.jpg'>"
    )

    assert (
        amazon._amazon_image_src(parser.css_first("#landingImage"))
        == "https://m.media-amazon.com/images/I/51DRLHAa2AS.jpg"
    )


@pytest.mark.asyncio
@pytest.mark.regression
async def test_belk_adapter_extracts_nested_state_brand_price_and_currency() -> None:
    result = await BelkAdapter().extract(
        "https://www.belk.com/home/",
        """
        <html>
          <body>
            <script>
              window.__INITIAL_STATE__ = {
                "search": {
                  "products": [
                    {
                      "productName": "Checkerboard Quilt Set",
                      "brand": {"name": "Modern Southern Home"},
                      "salePrice": {"amount": "22.50", "currencyCode": "USD"},
                      "image": {"url": "https://belk.scene7.com/is/image/Belk/7100974"},
                      "productUrl": "/p/modern-southern-home--checkerboard-quilt-set/710097411786005.html"
                    }
                  ]
                }
              };
            </script>
          </body>
        </html>
        """,
        "ecommerce_listing",
    )

    assert result.records == [
        {
            "title": "Checkerboard Quilt Set",
            "brand": "Modern Southern Home",
            "price": "22.50",
            "currency": "USD",
            "image_url": "https://belk.scene7.com/is/image/Belk/7100974",
            "url": "https://www.belk.com/p/modern-southern-home--checkerboard-quilt-set/710097411786005.html",
            "_source": "belk_adapter",
        }
    ]


@pytest.mark.asyncio
@pytest.mark.regression
async def test_belk_adapter_extracts_upc_from_listwrapped_utag_data_detail() -> None:
    # Belk PDPs expose the UPC under `sku_upc` inside a Tealium `utag_data` object
    # carried by the Next.js __next_f RSC payload, where every value is a
    # single-element list. The adapter must unwrap those lists, recognize the
    # analytics object as a product, and surface the UPC as `barcode` (not leak
    # list literals into title and not drop the UPC).
    import json as _json

    utag = {
        "utag_data": {
            "product_image_url": [
                "https://belk.scene7.com/is/image/Belk?layer=0&src=8100339_TM1ECBL_A_001&"
            ],
            "product_name": ["Egg Cooker"],
            "product_brand": ["Toastmaster"],
            "product_price": ["13.95"],
            "product_original_price": ["34.00"],
            "product_id": ["8100339TM1ECBL"],
            "product_url": [
                "https://www.belk.com/p/toastmaster-egg-cooker/8100339TM1ECBL.html"
            ],
            "sku_id": ["0438684935095"],
            "sku_upc": ["0655772019097"],
            "sku_price": ["13.95"],
        }
    }
    chunk = _json.dumps("3:" + _json.dumps(utag, separators=(",", ":")))
    html = (
        "<html><body><script>self.__next_f.push([1,"
        + chunk
        + "])</script></body></html>"
    )

    result = await BelkAdapter().extract(
        "https://www.belk.com/p/toastmaster-egg-cooker/8100339TM1ECBL.html",
        html,
        "ecommerce_detail",
    )

    assert len(result.records) == 1
    record = result.records[0]
    assert record["title"] == "Egg Cooker"
    assert record["brand"] == "Toastmaster"
    # The UPC (sku_upc), not the sku_id, must win as the barcode identifier.
    assert record["barcode"] == "0655772019097"
    assert record["url"] == (
        "https://www.belk.com/p/toastmaster-egg-cooker/8100339TM1ECBL.html"
    )


@pytest.mark.asyncio
@pytest.mark.regression
async def test_belk_adapter_prefers_real_currency_fields_over_scalar_price_text() -> (
    None
):
    result = await BelkAdapter().extract(
        "https://www.belk.com/home/",
        """
        <html>
          <body>
            <script>
              window.__INITIAL_STATE__ = {
                "search": {
                  "products": [
                    {
                      "productName": "Free Sample",
                      "brand": {"name": "Acme"},
                      "price": "0.00",
                      "currencyCode": "USD",
                      "image": {"url": "https://belk.scene7.com/is/image/Belk/free-sample"},
                      "productUrl": "/p/free-sample/000.html"
                    }
                  ]
                }
              };
            </script>
          </body>
        </html>
        """,
        "ecommerce_listing",
    )

    assert result.records == [
        {
            "title": "Free Sample",
            "brand": "Acme",
            "price": "0.00",
            "currency": "USD",
            "image_url": "https://belk.scene7.com/is/image/Belk/free-sample",
            "url": "https://www.belk.com/p/free-sample/000.html",
            "_source": "belk_adapter",
        }
    ]


@pytest.mark.asyncio
@pytest.mark.regression
async def test_belk_adapter_ignores_aggregate_range_prices_in_state_payload() -> None:
    result = await BelkAdapter().extract(
        "https://www.belk.com/home/",
        """
        <html>
          <body>
            <script>
              window.__INITIAL_STATE__ = {
                "search": {
                  "products": [
                    {
                      "productName": "Plus Size Ruffle Back Cropped Pants",
                      "brand": {"name": "Crown & Ivy"},
                      "maxPrice": 225,
                      "image": {"url": "https://belk.scene7.com/is/image/Belk/35512462"},
                      "productUrl": "/p/crown-ivy-plus-size-ruffle-back-cropped-pants/180415535512462.html"
                    }
                  ]
                }
              };
            </script>
          </body>
        </html>
        """,
        "ecommerce_listing",
    )

    assert result.records == [
        {
            "title": "Plus Size Ruffle Back Cropped Pants",
            "brand": "Crown & Ivy",
            "image_url": "https://belk.scene7.com/is/image/Belk/35512462",
            "url": "https://www.belk.com/p/crown-ivy-plus-size-ruffle-back-cropped-pants/180415535512462.html",
            "_source": "belk_adapter",
        }
    ]


@pytest.mark.asyncio
@pytest.mark.regression
async def test_belk_adapter_extracts_detail_variants_with_color_and_size() -> None:
    result = await BelkAdapter().extract(
        "https://www.belk.com/p/kim-rogers-womens-denim-capri-pants/180430334287262.html",
        """
        <html>
          <body>
            <script id="__next_data__" type="application/json">
            {
              "props": {
                "pageProps": {
                  "product": {
                    "id": "180430334287262",
                    "title": "Women's Denim Capri Pants",
                    "vendor": "Kim Rogers",
                    "currency": "USD",
                    "productUrl": "/p/kim-rogers-womens-denim-capri-pants/180430334287262.html",
                    "options": [{"name": "Color"}, {"name": "Size"}],
                    "variants": [
                      {
                        "id": 101,
                        "sku": "KR-GRACE-6",
                        "price": "26.99",
                        "available": true,
                        "inventory_quantity": 3,
                        "option1": "GRACE WASH",
                        "option2": "6"
                      },
                      {
                        "id": 102,
                        "sku": "KR-DIXIE-8",
                        "price": "26.99",
                        "available": false,
                        "inventory_quantity": 0,
                        "option1": "DIXIE WASH",
                        "option2": "8"
                      }
                    ]
                  }
                }
              }
            }
            </script>
          </body>
        </html>
        """,
        "ecommerce_detail",
    )

    assert len(result.records) == 1
    record = result.records[0]
    assert record["variant_count"] == 2
    assert record["variants"] == [
        {
            "color": "GRACE WASH",
            "size": "6",
            "sku": "KR-GRACE-6",
            "price": "26.99",
            "currency": "USD",
            "availability": "in_stock",
            "stock_quantity": 3,
        },
        {
            "color": "DIXIE WASH",
            "size": "8",
            "sku": "KR-DIXIE-8",
            "price": "26.99",
            "currency": "USD",
            "availability": "out_of_stock",
            "stock_quantity": 0,
        },
    ]


@pytest.mark.asyncio
@pytest.mark.regression
async def test_belk_adapter_maps_per_variant_upc_from_utag_sku_arrays() -> None:
    # Belk's React PDP utag_data exposes per-SKU parallel arrays (one entry per
    # variant). Each variant must carry its own UPC as `barcode`, joined to the
    # size label via variantId == sku_id, and the product barcode is the first
    # in-stock variant UPC.
    import json as _json

    utag = {
        "utag_data": {
            "product_name": ["Charged Commit TR Sneakers"],
            "product_brand": ["Under Armour"],
            "product_id": ["39003106007140"],
            "product_color": ["Blue"],
            "product_url": [
                "https://www.belk.com/p/under-armour-charged-commit-tr-sneakers/39003106007140.html"
            ],
            "product_price": ["64.00"],
            "sku_id": ["0480069328350", "0480069328459"],
            "sku_upc": ["0198633940142", "0198633940517"],
            "sku_price": ["64.00", "64.00"],
            "sku_inventory": ["21", "0"],
            "sku_out_of_stock": [False, True],
        }
    }
    variant_objects = [
        {
            "variantId": "0480069328350",
            "color": "289475425516",
            "size": {"sizeId": "50500_10M", "sizeName": "10M"},
        },
        {
            "variantId": "0480069328459",
            "color": "011475425516",
            "size": {"sizeId": "50460_7.5M", "sizeName": "7.5M"},
        },
    ]
    # Embed both the utag analytics object and the variant objects in one __next_f chunk.
    inner = "3:" + _json.dumps(
        {"utag_data": utag["utag_data"], "v": variant_objects}, separators=(",", ":")
    )
    chunk = _json.dumps(inner)
    html = (
        "<html><body><script>self.__next_f.push([1,"
        + chunk
        + "])</script></body></html>"
    )

    result = await BelkAdapter().extract(
        "https://www.belk.com/p/under-armour-charged-commit-tr-sneakers/39003106007140.html",
        html,
        "ecommerce_detail",
    )

    assert len(result.records) == 1
    record = result.records[0]
    assert record["title"] == "Charged Commit TR Sneakers"
    assert record["product_id"] == "39003106007140"
    # Product barcode is the first in-stock variant UPC.
    assert record["barcode"] == "0198633940142"
    variants = record["variants"]
    assert isinstance(variants, list) and len(variants) == 2
    by_size = {v.get("size"): v for v in variants}
    assert by_size["10M"]["barcode"] == "0198633940142"
    assert by_size["10M"]["availability"] == "in_stock"
    assert by_size["7.5M"]["barcode"] == "0198633940517"
    assert by_size["7.5M"]["availability"] == "out_of_stock"


@pytest.mark.asyncio
@pytest.mark.regression
async def test_belk_adapter_extracts_detail_variants_from_captured_json_payload() -> (
    None
):
    import json as _json

    body = {
        "utag_data": {
            "product_name": ["Iron Free Premium Khaki Pants"],
            "product_brand": ["Haggar"],
            "product_id": ["3200645HC01000"],
            "product_url": [
                (
                    "https://www.belk.com/p/haggar-men-s-iron-free-premium-khaki-"
                    "classic-fit-flat-front-hidden-comfort-waistband-casual-pants/"
                    "3200645HC01000.html"
                )
            ],
            "product_price": ["44.95"],
            "sku_id": ["0438651111111", "0438652222222"],
            "sku_upc": ["0019783000001", "0019783000002"],
            "sku_price": ["44.95", "44.95"],
            "sku_inventory": ["12", "0"],
            "sku_out_of_stock": [False, True],
        },
        "colorSizeMap": {
            "colors": {
                "289356974949": {"name": "Premium Khaki"},
            }
        },
        "variants": [
            {
                "variantId": "0438651111111",
                "color": "289356974949",
                "size": {"sizeName": "32 x 30"},
            },
            {
                "variantId": "0438652222222",
                "color": "289356974949",
                "size": {"sizeName": "32 x 32"},
            },
        ],
    }

    result = await BelkAdapter().extract(
        (
            "https://www.belk.com/p/haggar-men-s-iron-free-premium-khaki-classic-fit-"
            "flat-front-hidden-comfort-waistband-casual-pants/3200645HC01000.html"
        ),
        _json.dumps(body),
        "ecommerce_detail",
    )

    assert len(result.records) == 1
    record = result.records[0]
    assert record["variant_count"] == 2
    assert record["barcode"] == "0019783000001"
    assert record["variants"] == [
        {
            "color": "Premium Khaki",
            "size": "32 x 30",
            "sku": "0438651111111",
            "barcode": "0019783000001",
            "price": "44.95",
            "availability": "in_stock",
            "stock_quantity": 12,
        },
        {
            "color": "Premium Khaki",
            "size": "32 x 32",
            "sku": "0438652222222",
            "barcode": "0019783000002",
            "price": "44.95",
            "availability": "out_of_stock",
            "stock_quantity": 0,
        },
    ]


@pytest.mark.asyncio
@pytest.mark.regression
async def test_amazon_adapter_does_not_fabricate_multi_axis_twister_product() -> None:
    result = await AmazonAdapter().extract(
        "https://www.amazon.com/Under-Armour-Mens-Tech-Shorts/dp/B016APPQ4S",
        """
        <html>
          <body>
            <span id="productTitle">Under Armour Men's Tech Mesh Shorts</span>
            <div id="inline-twister-row-color_name"></div>
            <div id="inline-twister-row-size_name"></div>
            <script type="a-state" data-a-state='{"key":"desktop-twister-sort-filter-data"}'>
            {
              "sortedDimValuesForAllDims": {
                "size_name": [
                  {"dimensionValueState":"SELECTED","dimensionValueDisplayText":"Large"},
                  {"dimensionValueState":"AVAILABLE","dimensionValueDisplayText":"X-Large"}
                ],
                "color_name": [
                  {"dimensionValueState":"SELECTED","dimensionValueDisplayText":"Black"},
                  {"dimensionValueState":"AVAILABLE","dimensionValueDisplayText":"Blue"}
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
    assert "variants" not in record


@pytest.mark.regression
def test_detail_extractor_recovers_untyped_embedded_size_options_variants() -> None:
    html = """
    <html>
      <body>
        <script id="__PRELOADED_STATE__" type="application/json">
        {
          "details": {
            "skuData": {
              "product": {
                "id": "19759526",
                "sku": "PUMAX00410571",
                "discountedPrice": 1890,
                "price": 4499,
                "imageUrl": "https://example.com/shoe.jpg",
                "color": {"name": "Black"},
                "action_url": "/puma-men-radcliff-black-sneakers/p/19759526",
                "title": "Puma",
                "subTitle": "Men Radcliff Black Sneakers",
                "isOutOfStock": 0,
                "sizeOptions": {
                  "title": "Select Size",
                  "options": [
                    {"id": "19759125", "sku": "PUMAX00410170", "sizeName": "UK 6", "discountedPrice": 1890, "price": 4499, "isOutOfStock": 1},
                    {"id": "19759126", "sku": "PUMAX00410171", "sizeName": "UK 7", "discountedPrice": 1890, "price": 4499, "isOutOfStock": 0}
                  ]
                }
              }
            }
          },
          "remoteConfigs": {
            "AB_V2": [
              {"id": "paymentOffers", "variants": [{"name": "control", "sampleRate": {"from": 0, "to": 1}}]}
            ]
          }
        }
        </script>
      </body>
    </html>
    """
    url = "https://www.nykaafashion.com/puma-men-radcliff-black-sneakers/p/19759526"

    record = build_detail_record(html, url, "ecommerce_detail", None)

    assert record["variant_count"] == 2
    assert [variant["size"] for variant in record["variants"]] == ["UK 6", "UK 7"]
    assert [variant["sku"] for variant in record["variants"]] == [
        "PUMAX00410170",
        "PUMAX00410171",
    ]
    assert all(variant["size"] != "control" for variant in record["variants"])


@pytest.mark.regression
def test_detail_extractor_recovers_untyped_embedded_one_size_variant() -> None:
    html = """
    <html>
      <body>
        <script id="__PRELOADED_STATE__" type="application/json">
        {
          "details": {
            "skuData": {
              "product": {
                "id": "21019447",
                "sku": "PUMAX00420531",
                "discountedPrice": 500,
                "price": 999,
                "imageUrl": "https://example.com/cap.jpg",
                "color": {"name": "Green"},
                "action_url": "/puma-metal-cat-classic-adjustable-baseball-cap/p/21019447",
                "title": "Puma",
                "subTitle": "Metal Cat Classic Adjustable Baseball Cap",
                "isOutOfStock": 0,
                "isOneSize": true,
                "sizeName": "One Size"
              }
            }
          },
          "remoteConfigs": {
            "AB_V2": [
              {"id": "add-to-cart-nudge", "variants": [{"name": "atc-a", "sampleRate": {"from": 0, "to": 1}}]}
            ]
          }
        }
        </script>
      </body>
    </html>
    """
    url = "https://www.nykaafashion.com/puma-metal-cat-classic-adjustable-baseball-cap/p/21019447"

    record = build_detail_record(html, url, "ecommerce_detail", None)

    assert record["variant_count"] == 1
    assert record["variants"][0]["color"] == "Green"
    assert record["variants"][0]["size"] == "One Size"
    assert record["variants"][0]["sku"] == "PUMAX00420531"
    assert record["variants"][0]["url"] == url
    assert record["variants"][0]["image_url"] == "https://example.com/cap.jpg"


@pytest.mark.regression
def test_detail_extractor_recovers_embedded_one_size_variant_with_size_name() -> None:
    html = """
    <html>
      <body>
        <script id="__PRELOADED_STATE__" type="application/json">
        {
          "details": {
            "skuData": {
              "product": {
                "id": "21019447",
                "sku": "PUMAX00420531",
                "discountedPrice": 500,
                "price": 999,
                "imageUrl": "https://example.com/cap.jpg",
                "color": {"name": "Green"},
                "title": "Puma",
                "subTitle": "Metal Cat Classic Adjustable Baseball Cap",
                "isOutOfStock": 0,
                "isOneSize": true,
                "size_name": "One Size"
              }
            }
          }
        }
        </script>
      </body>
    </html>
    """

    record = build_detail_record(
        html,
        "https://www.nykaafashion.com/puma-metal-cat-classic-adjustable-baseball-cap/p/21019447",
        "ecommerce_detail",
        None,
    )

    assert record["variant_count"] == 1
    assert record["variants"][0]["size"] == "One Size"
    assert record["variants"][0]["sku"] == "PUMAX00420531"


@pytest.mark.regression
def test_structured_product_payload_skips_duplicate_embedded_variants() -> None:
    payload = {
        "@type": "Product",
        "name": "Trail Cap",
        "sku": "CAP-1",
        "price": 10,
        "isOneSize": True,
        "sizeName": "One Size",
        "variants": [
            {"id": "CAP-1", "sku": "CAP-1", "sizeName": "One Size", "price": 10}
        ],
    }
    candidates: dict[str, list[object]] = {}

    collect_structured_candidates(
        payload,
        {},
        "https://example.com/products/trail-cap",
        candidates,
    )

    assert len(candidates["variants"]) == 1
    assert candidates["variant_count"] == [1]

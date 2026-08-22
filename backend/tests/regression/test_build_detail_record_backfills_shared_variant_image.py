from __future__ import annotations

from .test_detail_extractor_structured_sources import (
    build_detail_record,
    extract_records,
    pytest,
    read_optional_artifact_text,
)


@pytest.mark.regression
def test_build_detail_record_backfills_shared_variant_image_and_availability() -> None:
    record = build_detail_record(
        "<html><body><main><h1>Brown Ruff Rider Leather Jacket</h1></main></body></html>",
        "https://www.ssense.com/en-us/men/product/willy-chavarria/brown-ruff-rider-leather-jacket/19072301",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Brown Ruff Rider Leather Jacket",
                "image_url": "https://res.cloudinary.com/ssenseweb/image/upload/item.jpg",
                "availability": "out_of_stock",
                "variants": [
                    {
                        "size": "S",
                        "price": "3890",
                        "currency": "USD",
                        "option_values": {"size": "S"},
                    },
                    {
                        "size": "M",
                        "price": "3890",
                        "currency": "USD",
                        "option_values": {"size": "M"},
                    },
                ],
            }
        ],
    )

    assert "image_url" not in record["variants"][0]
    assert record["variants"][1]["availability"] == "out_of_stock"


@pytest.mark.regression
def test_build_detail_record_repairs_nike_uuid_variant_skus_and_empty_prices() -> None:
    record = build_detail_record(
        "<html><body><main><h1>Nike Air Force 1 '07 Men's Shoes</h1></main></body></html>",
        "https://www.nike.com/t/air-force-1-07-mens-shoes-jBrhbr/CW2288-111",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "sku": "CW2288-111",
                "title": "Nike Air Force 1 '07 Men's Shoes",
                "price": "115.00",
                "currency": "USD",
                "variants": [
                    {
                        "sku": "3c95b6cf-42e7-567c-8bf2-2ee9c9398f9d",
                        "variant_id": "3c95b6cf-42e7-567c-8bf2-2ee9c9398f9d",
                        "size": "6",
                        "price": "",
                        "currency": "USD",
                        "availability": "in_stock",
                        "option_values": {"size": "6"},
                    }
                ],
            }
        ],
    )

    assert record["variants"][0]["price"] == "115.00"
    assert "sku" not in record["variants"][0]
    assert record["sku"] == "CW2288-111"


@pytest.mark.regression
def test_build_detail_record_replaces_feature_duplicate_description_with_details() -> (
    None
):
    record = build_detail_record(
        "<html><body><main><h1>Scotch Heavy Duty Shipping Packaging Tape</h1></main></body></html>",
        "https://www.samsclub.com/ip/scotch-heavy-duty-shipping-packaging-tape-dispensers-6-pack/5113185138",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Scotch Heavy Duty Shipping Packaging Tape",
                "description": "Guaranteed to Stay Sealed. Provides excellent holding power.",
                "features": [
                    "Guaranteed to Stay Sealed.",
                    "Provides excellent holding power.",
                ],
                "product_details": (
                    "Now even the heaviest packages can withstand rough handling. "
                    "This packaging tape holds strong on recycled boxes."
                ),
            }
        ],
    )

    assert (
        record["description"]
        == "Now even the heaviest packages can withstand rough handling. This packaging tape holds strong on recycled boxes."
    )
    assert record["features"] == [
        "Guaranteed to Stay Sealed.",
        "Provides excellent holding power.",
    ]
    assert (
        record["product_details"]
        == "Now even the heaviest packages can withstand rough handling. This packaging tape holds strong on recycled boxes."
    )


@pytest.mark.regression
def test_build_detail_record_backfills_price_from_buy_button_aria_label() -> None:
    record = build_detail_record(
        """
        <html>
          <body>
            <main>
              <h1>Nike Dunk Low 'Black White'</h1>
              <button aria-label="Buy New for $99">Buy New</button>
            </main>
          </body>
        </html>
        """,
        "https://www.goat.com/sneakers/dunk-low-black-white-dd1391-100",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Nike Dunk Low 'Black White'",
                "description": "Shop the Nike Dunk Low 'Black White' and other curated styles from Nike on GOAT.",
            }
        ],
    )

    assert record["price"] == "99.00"
    assert record["currency"] == "USD"
    assert record["_field_sources"]["price"] == ["dom_text"]


@pytest.mark.regression
def test_build_detail_record_repairs_shopify_cent_variant_prices_and_numeric_titles() -> (
    None
):
    record = build_detail_record(
        "<html><body><main><h1>SATISFY TheROCKER - Jet Black</h1></main></body></html>",
        "https://kith.com/collections/mens-footwear-sneakers/products/st40002-02000",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "SATISFY TheROCKER - Jet Black",
                "price": "282.00",
                "currency": "USD",
                "variants": [
                    {
                        "sku": "13875993",
                        "price": "28200",
                        "title": "3",
                        "currency": "USD",
                        "availability": "in_stock",
                        "option_values": {"size": "3"},
                    }
                ],
                "selected_variant": {
                    "sku": "13875993",
                    "price": "28200",
                    "title": "3",
                    "currency": "USD",
                    "availability": "in_stock",
                    "option_values": {"size": "3"},
                },
            }
        ],
    )

    assert record["variants"][0]["price"] == "282.00"


@pytest.mark.regression
def test_build_detail_record_drops_shopify_internal_numeric_variant_weight() -> None:
    record = build_detail_record(
        "<html><body><main><h1>SATISFY TheROCKER - Jet Black</h1></main></body></html>",
        "https://kith.com/collections/mens-footwear-sneakers/products/st40002-02000",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "SATISFY TheROCKER - Jet Black",
                "price": "285.00",
                "currency": "USD",
                "variants": [
                    {
                        "sku": "13875993",
                        "size": "3",
                        "weight": "1361",
                        "availability": "out_of_stock",
                    },
                    {
                        "sku": "13875994",
                        "size": "3.5",
                        "weight": 1361,
                        "availability": "out_of_stock",
                    },
                ],
            }
        ],
    )

    assert len(record["variants"]) == 2
    assert all("weight" not in variant for variant in record["variants"])


@pytest.mark.regression
def test_build_detail_record_replaces_ai_outfit_title_from_url() -> None:
    record = build_detail_record(
        "<html><body><main><h1>Your AI-Generated Outfit</h1></main></body></html>",
        "https://www.nordstrom.com/s/treasure-and-bond-blouson-twill-utility-jacket/8045019",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Your AI-Generated Outfit",
                "sku": "9656609",
                "price": "59.99",
            }
        ],
    )

    assert record["title"] == "Treasure And Bond Blouson Twill Utility Jacket"


@pytest.mark.regression
def test_build_detail_record_drops_low_signal_numeric_only_variants() -> None:
    html = "<html><body><main><h1>Cozyla 32&quot; 4K Calendar+ 2 (White)</h1></main></body></html>"

    record = build_detail_record(
        html,
        "https://www.bhphotovideo.com/c/product/1882297-REG/cozyla_cd_8v543f0_white_us_32_4k_calendar_gen2_white.html",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": 'Cozyla 32" 4K Calendar+ 2 (White)',
                "price": "989.99",
                "currency": "USD",
                "variants": [
                    {
                        "price": "989.99",
                        "currency": "USD",
                        "option_values": {"size": "1"},
                    },
                    {
                        "price": "989.99",
                        "currency": "USD",
                        "option_values": {"size": "2"},
                    },
                    {
                        "price": "989.99",
                        "currency": "USD",
                        "option_values": {"size": "3"},
                    },
                ],
                "selected_variant": {
                    "price": "989.99",
                    "currency": "USD",
                    "option_values": {"size": "1"},
                },
            }
        ],
    )

    assert "variants" not in record


@pytest.mark.regression
def test_extract_hm_productgroup_detail_from_code_only_url() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "ProductGroup",
          "name": "Canvas espadrilles",
          "description": "Espadrilles in canvas with a braided jute trim around the soles.",
          "brand": {"@type": "Brand", "name": "H&M"},
          "image": "https://image.hm.com/assets/hm/9e/92/main.jpg",
          "hasVariant": [
            {
              "@type": "Product",
              "sku": "1317259001003",
              "name": "Canvas espadrilles - Black",
              "color": "Black",
              "size": "6",
              "image": "https://image.hm.com/assets/hm/9e/92/black.jpg",
              "offers": {
                "@type": "Offer",
                "url": "https://www2.hm.com/en_in/productpage.1317259001.html",
                "priceCurrency": "INR",
                "price": 1499
              }
            },
            {
              "@type": "Product",
              "sku": "1317259002003",
              "name": "Canvas espadrilles - Beige",
              "color": "Beige",
              "size": "6",
              "image": "https://image.hm.com/assets/hm/fb/81/beige.jpg",
              "offers": {
                "@type": "Offer",
                "url": "https://www2.hm.com/en_in/productpage.1317259002.html",
                "priceCurrency": "INR",
                "price": 1499
              }
            }
          ]
        }
        </script>
      </head>
      <body>
        <main>
          <h1>Black</h1>
          <div class="price">Rs. 1,499.00</div>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www2.hm.com/en_in/productpage.1317259001.html",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["title"] == "Canvas espadrilles"
    assert record["price"] == "1499.00"
    assert record["brand"] == "H&M"
    assert record["currency"] == "INR"
    assert record["_source"] == "json_ld"
    assert record["url"] == "https://www2.hm.com/en_in/productpage.1317259001.html"
    assert record["image_url"] == "https://image.hm.com/assets/hm/9e/92/main.jpg"
    assert "size" not in record


@pytest.mark.regression
def test_extract_detail_ignores_variant_leaf_jsonld_scalars_for_base_request() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Widget Prime - Black",
          "sku": "11111111",
          "url": [
            "https://example.com/products/widget-prime?variant=11111111",
            "https://example.com/products/widget-prime"
          ],
          "offers": {
            "@type": "Offer",
            "price": "10.00",
            "priceCurrency": "USD"
          },
          "seller": {
            "@type": "Organization",
            "name": "Acme",
            "url": "https://example.com"
          }
        }
        </script>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "ProductGroup",
          "name": "Widget Prime",
          "url": "https://example.com/products/widget-prime",
          "offers": {
            "@type": "Offer",
            "price": "10.00",
            "priceCurrency": "USD"
          },
          "hasVariant": [
            {
              "@type": "Product",
              "name": "Widget Prime - Black",
              "sku": "11111111",
              "offers": {
                "@type": "Offer",
                "url": "https://example.com/products/widget-prime?variant=11111111",
                "price": "10.00",
                "priceCurrency": "USD"
              }
            },
            {
              "@type": "Product",
              "name": "Widget Prime - Tan",
              "sku": "22222222",
              "offers": {
                "@type": "Offer",
                "url": "https://example.com/products/widget-prime?variant=22222222",
                "price": "10.00",
                "priceCurrency": "USD"
              }
            }
          ]
        }
        </script>
      </head>
      <body>
        <main>
          <h1>Widget Prime</h1>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/widget-prime",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["title"] == "Widget Prime"
    assert record["url"] == "https://example.com/products/widget-prime"
    assert record["price"] == "10.00"
    assert record["currency"] == "USD"
    assert "sku" not in record


@pytest.mark.regression
def test_extract_detail_backfills_current_price_variants_and_strips_unavailable_suffixes() -> (
    None
):
    html = """
    <html>
      <body>
        <script id="__NEXT_DATA__" type="application/json">
        {
          "props": {
            "pageProps": {
              "product": {
                "id": "stan-smith-1",
                "title": "Stan Smith Shoes",
                "brand": "adidas",
                "prices": {
                  "currency": "USD",
                  "currentPrice": 100
                },
                "options": [{"name": "Size"}],
                "variants": [
                  {
                    "id": "size-12.5",
                    "availability": "out_of_stock",
                    "selectedOptions": [
                      {"name": "Size", "value": "12.5 is currently unavailable."}
                    ]
                  },
                  {
                    "id": "size-13",
                    "availability": "in_stock",
                    "selectedOptions": [
                      {"name": "Size", "value": "13"}
                    ]
                  }
                ]
              }
            }
          }
        }
        </script>
      </body>
    </html>
    """

    record = extract_records(
        html,
        "https://www.adidas.com/us/stan-smith-shoes/M20324.html",
        "ecommerce_detail",
        max_records=5,
    )[0]

    assert record["price"] == "100.00"
    assert record["variants"][0]["size"] == "12.5"
    assert "price" not in record["variants"][0]


@pytest.mark.regression
def test_extract_detail_rejects_asos_mixed_product_identity_record() -> None:
    html = """
    <html>
      <head>
        <meta property="og:title" content="ASOS DESIGN Curve lightweight pull on barrel pants in darkwash">
        <meta property="og:description" content="Shop the latest ASOS DESIGN Curve lightweight pull on barrel pants in darkwash trends with ASOS!">
      </head>
      <body>
        <main>
          <h1>ASOS DESIGN oversized t-shirt with lace hem in light blue</h1>
          <img src="https://images.asos-media.com/products/asos-design-oversized-t-shirt-with-lace-hem-in-light-blue/210817202-1-lightblue">
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.asos.com/us/prd/210397084/asos-design-curve-lightweight-pull-on-barrel-pants-in-darkwash/prd/210817202",
        "ecommerce_detail",
        max_records=5,
    )

    assert rows == []


@pytest.mark.regression
def test_extract_detail_rejects_known_error_page_titles() -> None:
    html = """
    <html>
      <body>
        <main><h1>Oops, Something Went Wrong.</h1></main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.dickssportinggoods.com/p/birkenstock-womens-arizona-big-buckle-soft-footbed-sandals-25birwcasuwrznbgbcegp/25birwcasuwrznbgbcegp",
        "ecommerce_detail",
        max_records=5,
    )

    assert rows == []


@pytest.mark.regression
def test_extract_ecommerce_detail_recovers_ulta_swatch_variants_from_artifact() -> None:
    html = read_optional_artifact_text("artifacts/runs/1/pages/a33c8361651f0e2f.html")

    rows = extract_records(
        html,
        "https://www.ulta.com/p/shape-tape-concealer-xlsImpprod14251035?sku=2304917",
        "ecommerce_detail",
        max_records=1,
        requested_fields=["variants"],
    )

    assert len(rows) == 1
    variants = rows[0]["variants"]
    assert len(variants) >= 40
    assert any(
        str(row.get("color") or "").startswith("12S Fair")
        and "sku=2304917" in str(row.get("url") or "")
        for row in variants
    )


@pytest.mark.regression
def test_extract_ecommerce_detail_recovers_jd_size_button_variants_from_artifact() -> (
    None
):
    html = read_optional_artifact_text("artifacts/runs/1/pages/c4ab41de0cea1a3a.html")

    rows = extract_records(
        html,
        "https://www.jdsports.co.uk/product/pink-adidas-originals-classic-shorts/19741988/",
        "ecommerce_detail",
        max_records=1,
        requested_fields=["variants"],
    )

    assert len(rows) == 1
    sizes = [row.get("size") for row in rows[0]["variants"] if row.get("size")]
    assert sizes[:5] == ["XS", "S", "M", "L", "XL"]


@pytest.mark.regression
def test_extract_ecommerce_detail_preserves_zadig_js_state_variants_from_artifact() -> (
    None
):
    html = read_optional_artifact_text("artifacts/runs/1/pages/0ed7c0adb54a6d56.html")

    rows = extract_records(
        html,
        "https://zadig-et-voltaire.com/eu/uk/p/JMTS01771443/t-shirt-teddyx-blue-sixtine",
        "ecommerce_detail",
        max_records=1,
        requested_fields=["variants"],
    )

    assert len(rows) == 1
    sizes = [row.get("size") for row in rows[0]["variants"] if row.get("size")]
    assert sizes[:5] == ["XS", "S", "M", "L", "XL"]


@pytest.mark.regression
def test_extract_ecommerce_detail_preserves_toddsnyder_suit_component_variants() -> (
    None
):
    html = read_optional_artifact_text("artifacts/runs/1/pages/3f9356011b5bfe4f.html")

    rows = extract_records(
        html,
        "https://www.toddsnyder.com/collections/slim-fit-suits-tuxedos/products/italian-seersucker-sutton-suit-2",
        "ecommerce_detail",
        max_records=1,
        requested_fields=["variants"],
    )

    assert len(rows) == 1
    variants = rows[0].get("variants") or []
    assert any(
        variant.get("style") == "Jacket" and variant.get("size") == "36S"
        for variant in variants
    )
    assert any(
        variant.get("style") == "Trouser" and variant.get("size") == "28/32"
        for variant in variants
    )


@pytest.mark.regression
def test_build_detail_record_prefers_dom_description_over_truncated_og_copy() -> None:
    html = """
    <html>
      <head>
        <meta property="og:title" content="NXT 5 Battery Charger &amp; Maintainer">
        <meta property="og:description" content="Performance, safety, ease. Drivers can count on all three with CTEK's NXT 5 Battery Charger &amp; Maintainer, which is built both to charge and actively restore battery life. This is a fully automatic 4.3A charger that just needs...">
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "NXT 5 Battery Charger & Maintainer",
          "brand": "CTEK",
          "image": "https://example.com/images/charger.jpg",
          "offers": {
            "@type": "Offer",
            "price": "124.99",
            "priceCurrency": "USD"
          }
        }
        </script>
      </head>
      <body>
        <main>
          <h1>NXT 5 Battery Charger &amp; Maintainer</h1>
          <section>
            <h2>Description</h2>
            <p>
              Performance, safety, ease. Drivers can count on all three with CTEK's
              NXT 5 Battery Charger &amp; Maintainer, which is built both to charge
              and actively restore battery life with the help of patented
              desulphation and reconditioning modes. This is a fully automatic
              4.3A charger that just needs a power outlet and can restore deeply
              discharged batteries.
            </p>
          </section>
        </main>
      </body>
    </html>
    """

    record = build_detail_record(
        html,
        "https://www.tirerack.com/accessories/ctek-nxt-5-battery-charger-maintainer",
        "ecommerce_detail",
        None,
    )

    assert record["description"].endswith("restore deeply discharged batteries.")
    assert record["description"].endswith(("...", "…")) is False


@pytest.mark.regression
def test_build_detail_record_prefers_dom_description_over_cut_off_meta_copy() -> None:
    html = """
    <html>
      <head>
        <meta property="og:title" content="Dime Soft Rock Crewneck">
        <meta property="og:description" content="Arriving as part of the second drop from its Spring '25 collection, Montreal-based streetwear and skatewear brand Dime pays homage to one of its favorite music subgenres with this Soft Rock Crewneck. Crafted from heavyweight cotton for a comfortable, durable feel, this crewneck features an eye-catching Dime logo on the">
      </head>
      <body>
        <main>
          <h1>Dime Soft Rock Crewneck</h1>
          <section>
            <h2>Description</h2>
            <p>
              Arriving as part of the second drop from its Spring '25 collection,
              Montreal-based streetwear and skatewear brand Dime pays homage to
              one of its favorite music subgenres with this Soft Rock Crewneck.
              Crafted from heavyweight cotton for a comfortable, durable feel,
              this crewneck features an eye-catching Dime logo on the chest.
            </p>
          </section>
        </main>
      </body>
    </html>
    """

    record = build_detail_record(
        html,
        "https://www.sneakersnstuff.com/products/dime-soft-rock-crewneck-dime2sp2542blk",
        "ecommerce_detail",
        None,
    )

    assert record["description"].endswith("logo on the chest.")

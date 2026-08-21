from __future__ import annotations

from .test_detail_extractor_structured_sources import *  # noqa: F403


@pytest.mark.regression
def test_detail_currency_hint_host_matching_avoids_partial_word_false_positive() -> (
    None
):
    assert (
        detail_currency_hint_is_host_level(
            "https://www.notarget.com/products/widget",
            expected_currency="USD",
        )
        is False
    )
    assert (
        detail_currency_hint_is_host_level(
            "https://www.target.com/products/widget",
            expected_currency="USD",
        )
        is True
    )

@pytest.mark.regression
def test_reconcile_detail_currency_with_url_tracks_nested_currency_sources() -> None:
    record = {
        "selected_variant": {"price": "10.00"},
        "variants": [{"price": "10.00"}],
    }

    reconcile_detail_currency_with_url(
        record,
        page_url="https://www.target.com/p/widget",
    )

    assert record["variants"][0]["currency"] == "USD"
    assert "url_currency_hint" in record["_field_sources"]["selected_variant.currency"]
    assert "url_currency_hint" in record["_field_sources"]["variants[0].currency"]

@pytest.mark.regression
def test_extract_detail_prefers_visible_price_symbol_over_region_path_currency() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "leather disco biker jacket",
          "brand": {"@type": "Brand", "name": "Philipp Plein"},
          "offers": {"price": "13880", "priceCurrency": "INR"}
        }
        </script>
      </head>
      <body>
        <main>
          <h1>Philipp Plein</h1>
          <p>leather disco biker jacket</p>
          <div data-testid="price">$13,880</div>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.farfetch.com/in/shopping/men/philipp-plein-leather-disco-biker-jacket-item-18497263.aspx",
        "ecommerce_detail",
        max_records=1,
        requested_fields=["title", "brand", "price", "currency"],
    )

    assert rows[0]["price"] == "13880.00"
    assert rows[0]["currency"] == "USD"

@pytest.mark.regression
def test_extract_ecommerce_detail_jsonld_skips_currency_only_offer() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Trail Runner",
          "offers": [
            {"@type": "Offer", "priceCurrency": "USD"},
            {"@type": "Offer", "price": "129.95", "priceCurrency": "USD"}
          ]
        }
        </script>
      </head>
      <body><h1>Trail Runner</h1></body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/trail-runner",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    assert rows[0]["price"] == "129.95"
    assert rows[0]["currency"] == "USD"

@pytest.mark.regression
def test_extract_ecommerce_detail_rejects_url_like_structured_brand() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Vitamin D3 Mini Gels",
          "brand": "https://www.vitacost.com/brand/vitacost",
          "offers": {"price": "10.99", "priceCurrency": "USD"}
        }
        </script>
      </head>
      <body><h1>Vitamin D3 Mini Gels</h1></body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.vitacost.com/vitacost-vitamin-d3-mini-gels",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    assert "brand" not in rows[0]

@pytest.mark.regression
def test_extract_ecommerce_detail_backfills_currency_from_url_hint_when_price_exists() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Joe Freshgoods ABZORB 1890 Sneaker",
          "offers": {"price": "110.00"}
        }
        </script>
      </head>
      <body><h1>Joe Freshgoods ABZORB 1890 Sneaker</h1></body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.notre-shop.com/collections/new-arrivals/products/joe-freshgoods-abzorb-1890-sneaker-in-pirate-black-heron-persian-purple",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    assert rows[0]["price"] == "110.00"
    assert rows[0]["currency"] == "USD"

@pytest.mark.regression
def test_extract_ecommerce_detail_rejects_same_url_wrong_product_title() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "JLab GO Pop ANC True Wireless Earbuds",
          "offers": {"price": "29.99", "priceCurrency": "USD"}
        }
        </script>
      </head>
      <body><h1>JLab GO Pop ANC True Wireless Earbuds</h1></body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.bestbuy.com/product/apple-airpods-pro-2nd-generation-white/JJ8ZH6TPSW?intl=nosplash",
        "ecommerce_detail",
        max_records=5,
    )

    assert rows == []

@pytest.mark.regression
def test_extract_ecommerce_detail_rejects_access_denied_shell_title() -> None:
    html = """
    <html>
      <head><title>Access to this page has been denied</title></head>
      <body><h1>Access to this page has been denied</h1></body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.wayfair.com/furniture/pdp/flexsteel-bryce-power-reclining-sofa-with-power-headrest-xtya1522.html",
        "ecommerce_detail",
        max_records=5,
    )

    assert rows == []

@pytest.mark.regression
def test_extract_ecommerce_detail_leaves_missing_availability_unset() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Rambler 8 oz Stackable Cup",
          "image": "https://www.yeti.com/images/rambler-stackable-cup.jpg",
          "offers": {"price": "24.99", "priceCurrency": "USD"}
        }
        </script>
      </head>
      <body><h1>Rambler 8 oz Stackable Cup</h1></body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.yeti.com/drinkware/tumblers/rambler-ceramic-stackable-8oz.html",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    assert "availability" not in rows[0]

@pytest.mark.regression
def test_repair_ecommerce_detail_backfills_parent_image_from_variants() -> None:
    record = {
        "title": "American Vintage II 1972 Telecaster Thinline",
        "price": "272800.00",
        "currency": "INR",
        "variants": [
            {
                "color": "Aged Natural",
                "sku": "0110392834",
                "image_url": "https://cdn.shopify.com/s/files/1/0712/3510/9086/files/0110392834_fen_ins_frt_1_rr.png?v=1742191446",
            }
        ],
    }

    repair_ecommerce_detail_record_quality(
        record,
        html="",
        page_url="https://intl.fender.com/products/american-vintage-ii-1972-telecaster-thinline",
    )

    assert (
        record["image_url"]
        == "https://cdn.shopify.com/s/files/1/0712/3510/9086/files/0110392834_fen_ins_frt_1_rr.png?v=1742191446"
    )

@pytest.mark.regression
def test_build_detail_record_drops_single_numeric_feature_id() -> None:
    record = build_detail_record(
        "<html><body><main><h1>Soft Rock Crewneck</h1></main></body></html>",
        "https://www.sneakersnstuff.com/products/dime-soft-rock-crewneck-dime2sp2542blk",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Soft Rock Crewneck",
                "price": "64.00",
                "currency": "EUR",
                "features": ["9906444108117"],
            }
        ],
    )

    assert "features" not in record

@pytest.mark.regression
def test_build_detail_record_drops_category_dropdown_additional_images() -> None:
    record = build_detail_record(
        "<html><body><main><h1>47 NY Yankees Clean Up Cap</h1></main></body></html>",
        "https://www.endclothing.com/us/47-ny-yankees-clean-up-cap-b-rgw17gws-vn.html",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "47 NY Yankees Clean Up Cap",
                "price": "35.00",
                "currency": "USD",
                "image_url": "https://media.endclothing.com/media/catalog/product/b/r/brgw17gws-vn_1.jpg",
                "additional_images": [
                    "https://media.endclothing.com/media/catalog/category/Bound-Menswear-Jacket_03-02-26_Dropdown_426x262.jpg",
                    "https://media.endclothing.com/media/catalog/product/b/r/brgw17gws-vn_2.jpg",
                ],
            }
        ],
    )

    images = " ".join(record.get("additional_images", []))
    assert "category" not in images
    assert record["additional_images"] == [
        "https://media.endclothing.com/media/catalog/product/b/r/brgw17gws-vn_2.jpg"
    ]

@pytest.mark.regression
def test_extract_ecommerce_detail_from_microdata() -> None:
    html = """
    <html>
      <body>
        <main itemscope itemtype="https://schema.org/Product">
          <h1 itemprop="name">Microdata Widget</h1>
          <div itemprop="brand" itemscope itemtype="https://schema.org/Brand">
            <span itemprop="name">Acme</span>
          </div>
          <div itemprop="offers" itemscope itemtype="https://schema.org/Offer">
            <meta itemprop="priceCurrency" content="USD">
            <span itemprop="price">29.99</span>
            <link itemprop="availability" href="https://schema.org/InStock">
          </div>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/microdata-widget",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["title"] == "Microdata Widget"
    assert record["brand"] == "Acme"
    assert record["price"] == "29.99"
    assert record["currency"] == "USD"
    assert record["availability"] == "in_stock"
    assert record["_source"] == "microdata"

@pytest.mark.regression
def test_extract_ecommerce_detail_merges_shopify_available_sizes_over_single_jsonld_variant() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Arrival 5\\" Shorts",
          "brand": {"@type": "Brand", "name": "Gymshark"},
          "hasVariant": [
            {
              "@type": "Product",
              "sku": "A2A1M-BBBB",
              "size": "xs",
              "offers": {
                "@type": "Offer",
                "price": "26.00",
                "priceCurrency": "USD"
              }
            }
          ]
        }
        </script>
        <script id="__NEXT_DATA__" type="application/json">
        {
          "props": {
            "pageProps": {
              "productData": {
                "product": {
                  "id": 6804846346442,
                  "title": "Arrival 5\\" Shorts",
                  "handle": "gymshark-arrival-5-shorts-black-ss22",
                  "colour": "Black",
                  "price": 26,
                  "currencyCode": "USD",
                  "availableSizes": [
                    {
                      "id": 39786362568906,
                      "inStock": true,
                      "inventoryQuantity": 9170,
                      "price": 26,
                      "size": "xs",
                      "sku": "A2A1M-BBBB-XS"
                    },
                    {
                      "id": 39786362601674,
                      "inStock": true,
                      "inventoryQuantity": 22988,
                      "price": 26,
                      "size": "s",
                      "sku": "A2A1M-BBBB-S"
                    },
                    {
                      "id": 39786362634442,
                      "inStock": false,
                      "inventoryQuantity": 0,
                      "price": 26,
                      "size": "m",
                      "sku": "A2A1M-BBBB-M"
                    }
                  ]
                }
              }
            }
          }
        }
        </script>
      </head>
      <body><main><h1>Arrival 5&quot; Shorts</h1></main></body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.gymshark.com/products/gymshark-arrival-5-shorts-black-ss22",
        "ecommerce_detail",
        max_records=1,
        requested_fields=["variants", "title", "price", "currency"],
    )

    assert rows
    record = rows[0]
    assert record["title"] == 'Arrival 5" Shorts'
    assert record["variant_count"] == 3
    assert [variant["size"] for variant in record["variants"]] == ["xs", "s", "m"]
    assert [variant["sku"] for variant in record["variants"]] == [
        "A2A1M-BBBB-XS",
        "A2A1M-BBBB-S",
        "A2A1M-BBBB-M",
    ]

@pytest.mark.regression
def test_detail_record_runs_dom_tier_when_variant_dom_cues_exist() -> None:
    html = """
    <html>
      <body>
        <main>
          <h1>Trail Shoe</h1>
          <select name="color">
            <option>Black</option>
            <option>Blue</option>
          </select>
        </main>
      </body>
    </html>
    """

    record = build_detail_record(
        html,
        "https://example.com/products/trail-shoe",
        "ecommerce_detail",
        requested_fields=[
            "title",
            "price",
            "variants",
            "variant_axes",
            "selected_variant",
        ],
        adapter_records=[
            {
                "title": "Trail Shoe",
                "price": "49.99",
                "variant_axes": {"color": ["Black"]},
                "variants": [
                    {
                        "title": "Trail Shoe Black",
                        "option_values": {"color": "Black"},
                    }
                ],
                "selected_variant": {
                    "title": "Trail Shoe Black",
                    "option_values": {"color": "Black"},
                },
            }
        ],
        extraction_runtime_snapshot={
            "selector_self_heal": {"enabled": True, "min_confidence": 0.0}
        },
    )

    assert record["_extraction_tiers"]["current"] == "dom"
    assert record["_extraction_tiers"]["early_exit"] is None

@pytest.mark.regression
def test_sanitize_variant_row_keeps_option_label_titles_with_variant_signals() -> None:
    variant = {"title": "Large", "sku": "TRAIL-L", "price": "8.99"}

    assert sanitize_variant_row(
        variant,
        identity_url="https://example.com/products/trail-mix",
    )
    assert variant["title"] == "Large"

@pytest.mark.regression
def test_sanitize_variant_row_keeps_same_site_variant_url_with_axis_signal() -> None:
    variant = {
        "color": "Deep Pink",
        "url": "https://www.amazon.com/dp/B09LD8VFS1/ref=twister_B0CZ8ZQL8C?_encoding=UTF8&psc=1",
    }

    assert sanitize_variant_row(
        variant,
        identity_url="https://www.amazon.com/Philips-Sonicare-Toothbrush-Rechargeable-HX3681/dp/B09LD7WRVS?th=1",
    )
    assert variant["color"] == "Deep Pink"

@pytest.mark.regression
def test_detail_image_family_requires_full_media_code_match() -> None:
    assert not detail_image_matches_primary_family(
        "https://cdn.example.com/a999999/image.jpg",
        primary_image="https://cdn.example.com/a123456/image.jpg",
        title="",
    )

@pytest.mark.regression
def test_extract_ecommerce_detail_from_opengraph() -> None:
    html = """
    <html>
      <head>
        <meta property="og:title" content="OG Widget">
        <meta property="og:type" content="product">
        <meta property="og:image" content="https://example.com/images/og-widget.jpg">
        <meta property="og:url" content="https://example.com/products/og-widget">
        <meta property="product:price:amount" content="19.99">
        <meta property="product:price:currency" content="USD">
        <meta property="product:availability" content="in stock">
      </head>
      <body></body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/og-widget",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["title"] == "OG Widget"
    assert record["price"] == "19.99"
    assert record["currency"] == "USD"
    assert record["availability"] == "in_stock"
    assert record["image_url"] == "https://example.com/images/og-widget.jpg"
    assert record["url"] == "https://example.com/products/og-widget"
    assert record["_source"] == "opengraph"

@pytest.mark.regression
def test_extract_ecommerce_detail_prefers_localized_jsonld_price_over_state_variants() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Balm Dotcom",
          "brand": {"@type": "Brand", "name": "Glossier"},
          "offers": {
            "@type": "Offer",
            "price": "1400",
            "priceCurrency": "INR",
            "availability": "https://schema.org/InStock"
          }
        }
        </script>
        <script id="__NEXT_DATA__" type="application/json">
        {
          "props": {
            "pageProps": {
              "product": {
                "title": "Balm Dotcom",
                "currencyCode": "USD",
                "variants": [
                  {"id": 1, "title": "Original", "flavor": "Original", "price": 16, "sku": "balm-original"},
                  {"id": 2, "title": "Mint", "flavor": "Mint", "price": 16, "sku": "balm-mint"}
                ]
              }
            }
          }
        }
        </script>
      </head>
      <body>
        <main>
          <h1>Balm Dotcom</h1>
          <span class="price">Rs. 1,400.00</span>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.glossier.com/en-in/products/balm-dotcom",
        "ecommerce_detail",
        max_records=1,
        requested_fields=["price", "currency", "variants"],
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["price"] == "1400.00"
    assert record["currency"] == "INR"
    assert all(row.get("price") in (None, "1400.00") for row in record["variants"])
    assert all(row.get("currency") in (None, "INR") for row in record["variants"])

@pytest.mark.regression
def test_build_detail_record_overrides_default_market_adapter_price_with_visible_local_price() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Balm Dotcom",
          "offers": {
            "@type": "Offer",
            "price": "1400",
            "priceCurrency": "INR"
          }
        }
        </script>
      </head>
      <body>
        <main>
          <h1>Balm Dotcom</h1>
          <button class="add-to-bag"><span>Add to bag</span><span>Rs. 1,900</span></button>
          <div class="product-set__atc-price-compare">Rs. 5,500</div>
          <div class="pv-price__original js-price-original">Rs. 1,900</div>
        </main>
      </body>
    </html>
    """

    record = build_detail_record(
        html,
        "https://www.glossier.com/en-in/products/balm-dotcom",
        "ecommerce_detail",
        ["price", "currency", "variants"],
        adapter_records=[
            {
                "title": "Balm Dotcom",
                "price": "16",
                "original_price": "5500",
                "variants": [
                    {"flavor": "Original", "price": "16"},
                    {"flavor": "Mint", "price": "16"},
                ],
            }
        ],
    )

    assert record["price"] == "1900.00"
    assert record["currency"] == "INR"
    assert "original_price" not in record
    assert all("price" not in row for row in record["variants"])
    assert all("currency" not in row for row in record["variants"])

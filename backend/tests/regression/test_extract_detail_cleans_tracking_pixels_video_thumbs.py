from __future__ import annotations

from .test_detail_extractor_structured_sources import *  # noqa: F403


@pytest.mark.regression
def test_extract_detail_cleans_tracking_pixels_and_video_thumbs_from_images() -> None:
    html = """
    <html>
      <body>
        <main>
          <h1>Yellow Pebbles Tile</h1>
          <section class="product-gallery">
            <img src="/images/yellow-pebbles.jpg" alt="Yellow Pebbles Tile">
            <img src="https://securemetrics.apple.com/b/ss/pixel.gif">
            <img src="https://www.facebook.com/tr?id=123">
            <img src="https://players.boltdns.net/thumb.jpg">
            <img src="https://site.qualtrics.com/intercept/pixel.png">
          </section>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.homedepot.com/p/yellow-pebbles/202515091",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    assert rows[0]["image_url"] == "https://www.homedepot.com/images/yellow-pebbles.jpg"
    assert "additional_images" not in rows[0]

@pytest.mark.regression
def test_build_detail_record_runs_dom_tier_when_authoritative_record_has_no_images() -> (
    None
):
    html = """
    <html>
      <body>
        <main>
          <h1>Cozyla 32&quot; 4K Calendar+ 2 (White)</h1>
          <img src="https://cdn.example.com/products/cozyla-calendar-main.jpg" />
        </main>
      </body>
    </html>
    """

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
                "sku": "COCD8V543F0W",
            }
        ],
    )

    assert (
        record["image_url"]
        == "https://cdn.example.com/products/cozyla-calendar-main.jpg"
    )

@pytest.mark.regression
def test_extract_ecommerce_detail_prunes_irrelevant_nested_related_products_from_structured_data() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Going Coconuts",
          "description": "Neutral coconut shades only.",
          "image": [
            "https://cdn.shopify.com/s/files/1/1338/0845/files/EyePalette-GoingCoconuts-Closed-PDP.jpg",
            "https://cdn.shopify.com/s/files/1/1338/0845/files/EyePalette-GoingCoconuts-MacroCrush.jpg"
          ],
          "offers": {"price": "14.00", "priceCurrency": "USD"},
          "relatedProducts": [
            {
              "@type": "Product",
              "name": "Pink Dreams",
              "url": "https://colourpop.com/products/pink-dreams-shadow-palette",
              "description": "Pink Dreams should not leak into the parent PDP.",
              "image": [
                "https://cdn.shopify.com/s/files/1/1338/0845/files/PPBlushCompact-ForeverYours-editorial-square_4980.jpg"
              ]
            }
          ]
        }
        </script>
      </head>
      <body><main><h1>Going Coconuts</h1></main></body>
    </html>
    """

    rows = extract_records(
        html,
        "https://colourpop.com/products/going-coconuts-eyeshadow-palette",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["description"] == "Neutral coconut shades only."
    assert record["image_url"].endswith("EyePalette-GoingCoconuts-Closed-PDP.jpg")
    assert all(
        "ForeverYours" not in image for image in record.get("additional_images", [])
    )

@pytest.mark.regression
def test_build_detail_record_drops_related_rows_and_keeps_canonicalized_variant_axes() -> (
    None
):
    record = build_detail_record(
        "<html><body><main><h1>Going Coconuts</h1></main></body></html>",
        "https://colourpop.com/products/going-coconuts-eyeshadow-palette",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Going Coconuts",
                "price": "14.00",
                "currency": "USD",
                "variants": [
                    {
                        "title": "Blowin' Smoke",
                        "price": "14.00",
                        "currency": "USD",
                        "image_url": "https://cdn.example.com/blowin-smoke.jpg",
                    },
                    {
                        "title": "Going Coconuts - Light",
                        "option_values": {"shade": "Light"},
                        "price": "14.00",
                        "currency": "USD",
                    },
                ],
            }
        ],
    )

    assert record["variant_count"] == 1
    assert record["variants"] == [
        {"color": "Light", "price": "14.00", "currency": "USD"}
    ]

@pytest.mark.regression
def test_build_detail_record_sanitizes_cross_sell_images_placeholder_variants_and_legal_tail() -> (
    None
):
    html = "<html><body><main><h1>Black Seascape Stretch Bracelet</h1></main></body></html>"

    record = build_detail_record(
        html,
        "https://www.puravidabracelets.com/products/black-seascape-stretch-bracelet",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Black Seascape Stretch Bracelet",
                "description": (
                    "These sleek joggers feature our ABC technology. "
                    "Black Seascape Stretch Bracelet - Black - One Size. "
                    "These sleek joggers feature our ABC technology."
                ),
                "specifications": (
                    "Main material rubber. "
                    "EU product safety contact. "
                    "Customer service DECATHLON SE 4, boulevard de Mons 59665."
                ),
                "materials": "DECATHLON SE",
                "image_url": "http://www.puravidabracelets.com/cdn/shop/files/50907BLCK_1-min.jpg?v=1717477241",
                "additional_images": [
                    "https://cdn.shopify.com/s/files/1/0297/6313/files/50907BLCK_3-min.jpg?v=1717609172",
                    "https://www.puravidabracelets.com/cdn/shop/files/square-image_3_1.jpg?crop=center&height=600&v=1774914906&width=600",
                    "https://www.puravidabracelets.com/cdn/shop/products/Solid_Black_ed35d7f8-dc76-4e8a-9e2b-821126dbb895.jpg?v=1718918266&width=1200",
                    "https://www.macys.com/shop/product/1&fmt=webp",
                    "https://www.fashionnova.com/products/R0lGODlhAQABAAAAACH5BAEKAAEALAAAAAABAAEAAAICTAEAOw==",
                ],
                "variants": [
                    {
                        "price": "8.00",
                        "currency": "USD",
                        "option_values": {"size": "Please select"},
                    },
                    {
                        "price": "8.00",
                        "currency": "USD",
                        "option_values": {
                            "toggle_color_swatches": "Swatch",
                            "color": "Black",
                        },
                    },
                ],
                "selected_variant": {
                    "price": "8.00",
                    "currency": "USD",
                    "option_values": {"size": "Please select"},
                },
                "product_attributes": {"title": "Default Title"},
            }
        ],
    )

    assert record["description"] == "These sleek joggers feature our ABC technology."
    assert record["specifications"] == "Main material rubber."
    assert "materials" not in record
    assert "product_attributes" not in record
    assert "50907BLCK" in record["image_url"]
    assert all(
        bad_token not in " ".join(record.get("additional_images", []))
        for bad_token in (
            "square-image",
            "Solid_Black",
            "macys.com/shop/product",
            "R0lGODlhAQAB",
        )
    )
    assert record["variants"] == [
        {
            "price": "8.00",
            "currency": "USD",
            "color": "Black",
            "image_url": "https://www.puravidabracelets.com/cdn/shop/files/50907BLCK_1-min.jpg?v=1717477241",
        }
    ]

@pytest.mark.regression
def test_build_detail_record_drops_v6_widget_fulfillment_and_variant_scalar_noise() -> (
    None
):
    record = build_detail_record(
        "<html><body><main><h1>V6 Test Sneaker</h1></main></body></html>",
        "https://www.example.com/products/v6-test-sneaker",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "V6 Test Sneaker",
                "features": "1 2 3 4 5 6 7 8 9 10",
                "description": "Shipping, pickup, and delivery options available at checkout.",
                "size": "Size Guide Please select a size",
                "color": "Black",
            }
        ],
    )

    assert "features" not in record
    assert "description" not in record
    assert "size" not in record
    assert record["color"] == "Black"

@pytest.mark.regression
def test_build_detail_record_drops_v6_generic_title_cross_product_text_and_ad_product_type() -> (
    None
):
    record = build_detail_record(
        "<html><body><main><h1>Calvin Klein Bernard Lace-Up Oxfords</h1></main></body></html>",
        "https://www.macys.com/shop/product/calvin-klein-mens-bernard-lace-up-oxfords?ID=12345",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "MENS SHOES",
                "description": (
                    "The Hiser men's lace up oxford. "
                    "Calvin Klein Adeso dress shoe. "
                    "Club Room casual dress shoes. "
                    "Calvin Klein Bernard lace-up oxford."
                ),
                "product_type": "CriteoProductRail",
            }
        ],
    )

    assert record["title"] == "calvin klein mens bernard lace up oxfords"
    assert record["description"] == "Calvin Klein Bernard lace-up oxford."
    assert "product_type" not in record

@pytest.mark.regression
def test_build_detail_record_drops_v6_target_fulfillment_description() -> None:
    record = build_detail_record(
        "<html><body><main><h1>Apple AirPods Pro 2nd Generation</h1></main></body></html>",
        "https://www.target.com/p/apple-airpods-pro-2nd-generation-with-magsafe-case-usb-c/-/A-89791402",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Apple AirPods Pro 2nd Generation",
                "description": "Get it today with Target delivery, pickup, or shipping options available at checkout.",
            }
        ],
    )

    assert "description" not in record

@pytest.mark.regression
def test_build_detail_record_rejects_audit_artifact_candidates_before_selection() -> (
    None
):
    record = build_detail_record(
        "<html><body><main><h1>Audit Widget</h1><img src='/widget.jpg'></main></body></html>",
        "https://example.com/products/audit-widget",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Audit Widget",
                "category": "Back > Home > Men > Shoes",
                "sku": "COPY-1720644688978",
                "product_type": "inline",
                "price": "unavailable",
                "description": "Useful product copy Show More",
                "variants": [{"name": "off", "value": False}],
            }
        ],
    )

    assert record["title"] == "Audit Widget"
    assert "category" not in record
    assert "sku" not in record
    assert "product_type" not in record
    assert "price" not in record
    assert "description" not in record
    assert "variants" not in record

@pytest.mark.regression
def test_build_detail_record_strips_embedded_home_suffix_from_category_head() -> None:
    record = {
        "title": "leather disco biker jacket",
        "brand": "Philipp Plein",
        "category": "Men Home > Philipp Plein > Clothing > Leather Jackets",
    }

    sanitize_detail_placeholder_scalars(
        record,
        identity_url="https://www.farfetch.com/in/shopping/men/philipp-plein-leather-disco-biker-jacket-item-18497263.aspx",
    )

    assert record["category"] == "Men > Philipp Plein > Clothing > Leather Jackets"

@pytest.mark.regression
def test_detail_cleanup_parses_stringified_locale_category_dict() -> None:
    record = {
        "title": "Brown Ruff Rider Leather Jacket",
        "brand": "WILLY CHAVARRIA",
        "category": "{'en': 'LEATHER JACKETS'}",
    }

    sanitize_detail_placeholder_scalars(
        record,
        identity_url="https://www.ssense.com/en-us/men/product/willy-chavarria/brown-ruff-rider-leather-jacket/19072301",
    )

    assert record["category"] == "LEATHER JACKETS"

@pytest.mark.regression
def test_detail_cleanup_drops_malformed_and_broken_fetch_images() -> None:
    record = {
        "title": "Men's All Sport Ankle Socks",
        "image_url": "https://assets.bombas.com/image/fetch/c_crop",
        "additional_images": [
            "https:files/LargeCheckIn_Newport_Front.webp",
            "https://cdn.example.com/products/socks/main.jpg",
        ],
    }

    repair_ecommerce_detail_record_quality(
        record,
        html="",
        page_url="https://bombas.com/products/mens-all-purpose-performance-ankle-socks",
    )

    assert record["image_url"] == "https://cdn.example.com/products/socks/main.jpg"
    assert "additional_images" not in record

@pytest.mark.regression
def test_detail_cleanup_drops_same_url_color_only_variant_noise() -> None:
    record = {
        "title": "Black Seascape Stretch Bracelet",
        "price": "8.00",
        "currency": "USD",
        "variants": [
            {
                "url": "https://www.puravidabracelets.com/products/black-seascape-stretch-bracelet?variant=41298450153558",
                "size": "Black Seascape Stretch Bracelet",
                "color": color,
                "availability": "in_stock",
            }
            for color in ("White", "Blue", "Black")
        ],
    }

    repair_ecommerce_detail_record_quality(
        record,
        html="",
        page_url="https://www.puravidabracelets.com/products/black-seascape-stretch-bracelet",
    )

    assert "variants" not in record
    assert "variant_count" not in record

@pytest.mark.regression
def test_detail_cleanup_sets_parent_out_of_stock_when_all_variants_out() -> None:
    record = {
        "title": "Pavlova 100 Lace Up Blush Satin Boots",
        "availability": "in_stock",
        "variants_complete": True,
        "variants": [
            {"size": "36", "availability": "out_of_stock", "stock_quantity": 0},
            {"size": "37", "availability": "out_of_stock", "stock_quantity": 0},
        ],
    }

    repair_ecommerce_detail_record_quality(
        record,
        html="",
        page_url="https://savannahs.com/collections/all-boots/products/pavlova-100-lace-up-blush-satin-boots-cl28517s",
    )

    assert record["availability"] == "out_of_stock"

@pytest.mark.regression
def test_build_detail_record_rejects_structural_identity_artifacts() -> None:
    record = build_detail_record(
        "<html><body><main><h1>Stand Mixer</h1></main></body></html>",
        "https://www.example.com/products/stand-mixer",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "plp",
                "product_id": "specifications",
                "product_type": "BRIGHTCOVE VIDEO",
                "price": "449",
                "currency": "USD",
            }
        ],
    )

    assert record["title"] == "Stand Mixer"
    assert "product_id" not in record
    assert "product_type" not in record

@pytest.mark.regression
def test_build_detail_record_trims_long_text_ui_tail_when_product_copy_remains() -> (
    None
):
    record = build_detail_record(
        "<html><body><main><h1>Cotton Shirt</h1></main></body></html>",
        "https://example.com/products/cotton-shirt",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Cotton Shirt",
                "description": "Soft cotton shirt with relaxed fit and reinforced seams Show More",
            }
        ],
    )

    assert (
        record["description"]
        == "Soft cotton shirt with relaxed fit and reinforced seams"
    )

@pytest.mark.regression
def test_build_detail_record_drops_duplicate_specifications_and_materials_ui_labels() -> (
    None
):
    record = build_detail_record(
        "<html><body><main><h1>Linen Jacket</h1></main></body></html>",
        "https://example.com/products/linen-jacket",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Linen Jacket",
                "description": "Lightweight linen jacket with horn buttons.",
                "specifications": "Lightweight linen jacket with horn buttons.",
                "materials": "Reviews\nCare\nLinen shell",
            }
        ],
    )

    assert record["description"] == "Lightweight linen jacket with horn buttons."
    assert "specifications" not in record
    assert record["materials"] == "Linen shell"

@pytest.mark.regression
def test_build_detail_record_dedupes_repeated_material_weight_tail() -> None:
    record = build_detail_record(
        "<html><body><main><h1>Wrangler Jeans</h1></main></body></html>",
        "https://example.com/products/wrangler-jeans",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Wrangler Jeans",
                "materials": (
                    "78% Cotton, 20% Recycled Cotton, 2% Spandex; 11.25 oz. 11.25 oz."
                ),
            }
        ],
    )

    assert record["materials"] == (
        "78% Cotton, 20% Recycled Cotton, 2% Spandex; 11.25 oz."
    )

@pytest.mark.regression
def test_build_detail_record_drops_global_guide_and_glossary_text() -> None:
    record = build_detail_record(
        "<html><body><main><h1>Oxford Shirt</h1></main></body></html>",
        "https://example.com/products/oxford-shirt",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Oxford Shirt",
                "description": (
                    "Regular Fit - Our classic cut. Slim Fit - Two inches less. "
                    "Relaxed Fit - Roomier through the body."
                ),
                "materials": (
                    "Fabric glossary. The word 'seersucker' originates from Persian. "
                    "Oxford cloth is a basket weave."
                ),
            }
        ],
    )

    assert "description" not in record
    assert "materials" not in record

@pytest.mark.regression
def test_build_detail_record_keeps_valid_candidates_after_candidate_gate() -> None:
    record = build_detail_record(
        "<html><body><main><h1>Trail Shoe</h1><img src='/shoe.jpg'></main></body></html>",
        "https://example.com/products/trail-shoe",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Trail Shoe",
                "category": "Men > Shoes",
                "sku": "TRAIL-100",
                "product_type": "Running Shoes",
                "price": "129.95",
                "description": "Lightweight trail shoe with grippy outsole.",
                "variant_axes": {"size": ["8", "9"]},
                "variants": [{"sku": "TRAIL-100-8", "option_values": {"size": "8"}}],
            }
        ],
    )

    assert record["category"] == "Men > Shoes"
    assert record["sku"] == "TRAIL-100"
    assert record["product_type"] == "Running Shoes"
    assert record["price"] == "129.95"
    assert record["description"] == "Lightweight trail shoe with grippy outsole."

@pytest.mark.regression
def test_build_detail_record_preserves_integral_price_magnitude_without_cent_context() -> (
    None
):
    cases = [
        (
            "https://in.puma.com/in/en/pd/deviate-nitro-elite-4-run-club-mens-road-running-shoes/312907",
            "9999",
            "9999.00",
            "INR",
        ),
        (
            "https://www.farfetch.com/shopping/men/designer-sneakers-item-123.aspx",
            "13880",
            "13880.00",
            "USD",
        ),
        (
            "https://www.ssense.com/en-us/men/product/willy-chavarria/brown-ruff-rider-leather-jacket/19072301",
            "3890",
            "3890.00",
            "USD",
        ),
    ]

    for url, raw_price, expected_price, currency in cases:
        record = build_detail_record(
            "<html><body><main><h1>V6 Price Product</h1></main></body></html>",
            url,
            "ecommerce_detail",
            None,
            adapter_records=[
                {
                    "title": "V6 Price Product",
                    "price": raw_price,
                    "currency": currency,
                    "variants": [
                        {
                            "price": raw_price,
                            "currency": currency,
                            "option_values": {"size": "M"},
                        }
                    ],
                }
            ],
        )

        assert record["price"] == expected_price
        assert record["variants"][0]["price"] == expected_price

@pytest.mark.regression
def test_extract_detail_preserves_visible_integer_price_magnitude() -> None:
    rows = extract_records(
        """
        <html><body><main>
          <h1>Archive Jacket</h1>
          <div data-testid="price">$1012</div>
          <p class="description">Archive jacket starting at $1012.</p>
        </main></body></html>
        """,
        "https://www.grailed.com/listings/archive-jacket",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    assert rows[0]["price"] == "1012.00"

@pytest.mark.regression
def test_extract_detail_prefers_visible_decimal_shift_price_over_integral_jsonld() -> (
    None
):
    rows = extract_records(
        """
        <html>
          <head>
            <script type="application/ld+json">
            {"@type":"Product","name":"Scarlett Medium Satchel with Charm","offers":{"@type":"Offer","price":"2995","priceCurrency":"USD","availability":"https://schema.org/InStock"}}
            </script>
          </head>
          <body><main>
            <h1>Scarlett Medium Satchel with Charm</h1>
            <div data-testid="price">$299.50</div>
            <img src="https://example.com/bag.jpg">
          </main></body>
        </html>
        """,
        "https://www.belk.com/p/scarlett-medium-satchel/1.html",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    assert rows[0]["price"] == "299.50"

@pytest.mark.regression
def test_build_detail_record_rejects_broken_extensionless_transformed_image_urls() -> (
    None
):
    record = build_detail_record(
        "<html><body><main><h1>Adidas Samba OG Shoes</h1></main></body></html>",
        "https://www.zappos.com/p/adidas-samba-og/product/12345",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Adidas Samba OG Shoes",
                "image_url": "https://m.media-amazon.com/images/I/adidas-samba-og-shoes._AC_UL1500_.jpg",
                "additional_images": [
                    "https://m.media-amazon.com/images/I/adidas-samba-og-shoes._AC_SR1224",
                    "https://m.media-amazon.com/images/I/adidas-samba-og-shoes-alt._AC_UL1500_.jpg",
                ],
            }
        ],
    )

    images = " ".join([record["image_url"], *record.get("additional_images", [])])
    assert "_AC_SR1224" not in images
    assert record["additional_images"] == [
        "https://m.media-amazon.com/images/I/adidas-samba-og-shoes-alt._AC_UL1500_.jpg"
    ]

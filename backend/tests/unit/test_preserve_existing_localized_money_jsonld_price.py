from __future__ import annotations

from .test_normalizers import *  # noqa: F403


@pytest.mark.unit
def test_preserve_existing_localized_money_without_jsonld_price() -> None:
    record = {
        "url": "https://fentybeauty.com/en-in/products/body-mist",
        "currency": "INR",
        "price": "INR 1,999",
    }
    html = """
    <html><head>
      <meta property="product:price:currency" content="USD">
    </head><body><h1>Body Mist</h1></body></html>
    """

    backfill_detail_price_from_html(record, html=html)

    assert record["currency"] == "INR"
    assert record["price"] == "INR 1,999"

@pytest.mark.unit
def test_coerce_category_reads_locale_dict_string() -> None:
    assert (
        coerce_field_value(
            "category",
            "{'en': 'LEATHER JACKETS'}",
            "https://www.ssense.com/en-us/men/product/example/1",
        )
        == "LEATHER JACKETS"
    )

@pytest.mark.unit
def test_normalize_additional_images_preserves_url_lists_with_commas() -> None:
    value = normalize_value(
        "additional_images",
        [
            "https://cdn.example.com/images/f_auto,q_auto,w_1080/widget-2.jpg",
            "https://cdn.example.com/images/f_auto,q_auto,w_1080/widget-3.jpg",
        ],
    )

    assert value == [
        "https://cdn.example.com/images/f_auto,q_auto,w_1080/widget-2.jpg",
        "https://cdn.example.com/images/f_auto,q_auto,w_1080/widget-3.jpg",
    ]

@pytest.mark.unit
def test_normalize_decimal_price_rejects_ambiguous_integer_text_without_price_context() -> (
    None
):
    assert normalize_decimal_price("126") is None

@pytest.mark.unit
def test_normalize_decimal_price_accepts_currency_context_for_integer_text() -> None:
    assert normalize_decimal_price("$126") == "126"
    assert normalize_decimal_price("Rs. 499") == "499"
    assert normalize_decimal_price("INR 499") == "499"

@pytest.mark.unit
def test_normalize_decimal_price_accepts_price_keyword_context_for_integer_text() -> (
    None
):
    assert normalize_decimal_price("price 126") == "126"

@pytest.mark.unit
def test_normalize_decimal_price_preserves_decimal_strings_without_currency_symbol() -> (
    None
):
    assert normalize_decimal_price("59.99") == "59.99"

@pytest.mark.unit
def test_normalize_decimal_price_supports_suffix_currency_and_decimal_comma() -> None:
    assert normalize_decimal_price("62,99 €") == "62.99"

@pytest.mark.unit
def test_normalize_decimal_price_treats_dot_thousands_as_grouping() -> None:
    assert normalize_decimal_price("€17.000") == "17000"

@pytest.mark.unit
def test_normalize_decimal_price_rejects_negative_values() -> None:
    # Regression: gemini audit DQ-4 — Gucci/Sony emitted -1 / -9 default
    # fallbacks that leaked into exports. Negative prices must become None.
    assert normalize_decimal_price("-1") is None
    assert normalize_decimal_price("-9.99") is None
    assert normalize_decimal_price("$-1") is None
    assert normalize_decimal_price("-$1") is None
    assert normalize_decimal_price("-USD100") is None
    assert normalize_decimal_price("−1") is None
    assert normalize_decimal_price("$−1") is None

@pytest.mark.unit
def test_normalize_integer_field_handles_unicode_minus_as_negative() -> None:
    assert normalize_value("stock_quantity", "−123") == -123

@pytest.mark.unit
def test_normalize_decimal_price_rejects_structured_types() -> None:
    assert normalize_decimal_price({"key": "val"}) is None
    assert normalize_decimal_price([100, 200]) is None
    assert normalize_decimal_price(("100",)) is None
    assert normalize_decimal_price({100, 200}) is None

@pytest.mark.unit
def test_variant_payload_limit_accepts_explicit_max_rows() -> None:
    record = {
        "variants": [
            {"size": "S", "url": "https://example.test/s"},
            {"size": "M", "url": "https://example.test/m"},
            {"size": "L", "url": "https://example.test/l"},
        ],
        "variant_count": 3,
    }

    enforce_payload_limits(record, max_rows=2)

    assert record["variants"] == [
        {"size": "S", "url": "https://example.test/s"},
        {"size": "M", "url": "https://example.test/m"},
    ]
    assert record["variant_count"] == 2

@pytest.mark.unit
def test_normalize_variant_record_drops_geographic_state_dropdown_rows() -> None:
    record: dict[str, object] = {
        "title": "EOS R5 Body",
        "variants": [
            {"state": "Alabama"},
            {"state": "Alaska"},
            {"state": "California"},
            {"state": "Texas"},
        ],
        "variant_count": 4,
    }

    normalize_variant_record(record)

    assert "variants" not in record
    assert "variant_count" not in record

@pytest.mark.unit
def test_repair_ecommerce_detail_reconciles_parent_price_against_unanimous_variants() -> (
    None
):
    # Regression: gemini audit DQ-7 (Selfridges) — parent price 190 with both
    # variants reporting 310 is a stale/unrelated DOM scrape. The reconciler
    # should adopt the unanimous variant price as the parent.
    record: dict[str, object] = {
        "price": "190.00",
        "currency": "GBP",
        "variants": [
            {"price": "310.00", "currency": "GBP", "size": "50ml"},
            {"price": "310.00", "currency": "GBP", "size": "100ml"},
        ],
    }
    repair_ecommerce_detail_record_quality(
        record,
        html="<html></html>",
        page_url="https://www.selfridges.com/GB/en/cat/example/",
        requested_page_url="https://www.selfridges.com/GB/en/cat/example/",
    )
    assert record["price"] == "310.00"

@pytest.mark.unit
def test_repair_ecommerce_detail_skips_variant_range_reconcile_when_magnitudes_differ() -> (
    None
):
    # Guard: when parent and variant prices differ by >~2x, the mismatch is
    # more likely a cents/units magnitude issue handled by the dedicated
    # magnitude reconciler. The variant-range reconciler must not overwrite
    # the parent in that case.
    record: dict[str, object] = {
        "price": "282.00",
        "currency": "USD",
        "variants": [
            {"price": "28200", "currency": "USD"},
        ],
    }
    repair_ecommerce_detail_record_quality(
        record,
        html="<html></html>",
        page_url="https://example.com/p",
        requested_page_url="https://example.com/p",
    )
    assert record["price"] == "282.00"

@pytest.mark.unit
@pytest.mark.parametrize(
    ("url", "record", "expected_brand"),
    [
        (
            "https://www.endclothing.com/us/47-ny-yankees-clean-up-cap-b-rgw17gws-vn.html",
            {"title": "47 NY Yankees Clean Up Cap", "price": "35.00"},
            "47",
        ),
        (
            "https://www.firstcry.com/babyhug/babyhug-denim-woven-sleeveless-top-and-pant-set-with-floral-print-blue/22346676/product-detail",
            {
                "title": "Babyhug Denim Woven Sleeveless Top & Pant Set With Floral Print - Blue",
                "price": "868.21",
            },
            "Babyhug",
        ),
        (
            "https://www.aesop.com/home-fragrance/candles/aganice-aromatique-candle/HM03.html",
            {"title": "Aganice Aromatique Candle", "price": "120.00"},
            "Aesop",
        ),
        (
            "https://amsterdamvintagewatches.com/shop/rolex-day-date-18038-champagne-5/",
            {
                "title": "Rolex Day-Date 18038 - Amsterdam Vintage Watches",
                "price": "43000.00",
            },
            "Rolex",
        ),
    ],
)
def test_repair_ecommerce_detail_backfills_missing_brand_from_identity(
    url: str,
    record: dict[str, object],
    expected_brand: str,
) -> None:
    repair_ecommerce_detail_record_quality(
        record,
        html="<html></html>",
        page_url=url,
        requested_page_url=url,
    )

    assert record["brand"] == expected_brand

@pytest.mark.unit
def test_repair_ecommerce_detail_backfills_game_publisher_brand_from_description() -> (
    None
):
    record: dict[str, object] = {
        "title": "PRAGMATA",
        "price": "59.99",
        "description": "A new sci-fi adventure from Capcom's upcoming lineup.",
    }
    url = "https://www.nintendo.com/us/store/products/pragmata-switch-2/"

    repair_ecommerce_detail_record_quality(
        record,
        html="<html></html>",
        page_url=url,
        requested_page_url=url,
    )

    assert record["brand"] == "Capcom"

@pytest.mark.unit
def test_repair_ecommerce_detail_prunes_child_pdp_variants_from_adult_product() -> None:
    url = "https://www.dtlr.com/collections/men/products/jordan-air-jordan-5-retro-white-metallic-mf-white-hq7978-103"
    record: dict[str, object] = {
        "title": "Jordan Air Jordan 5 Retro 'White Metallic'",
        "price": "215.00",
        "variants": [
            {"size": "8", "price": "215", "url": f"{url}?variant=adult"},
            {
                "size": "4",
                "price": "165",
                "color": "Grade School Jf White Hq7980 103",
                "url": "https://www.dtlr.com/collections/men/products/jordan-air-jordan-5-retro-white-metallic-grade-school-jf-white-hq7980-103?variant=gs",
            },
            {
                "size": "5",
                "price": "90",
                "color": "Toddler If White Hq7981 103",
                "url": "https://www.dtlr.com/collections/men/products/jordan-air-jordan-5-retro-white-metallic-toddler-if-white-hq7981-103?variant=td",
            },
        ],
    }

    repair_ecommerce_detail_record_quality(
        record,
        html="<html></html>",
        page_url=url,
        requested_page_url=url,
    )

    assert len(record["variants"]) == 1
    assert record["variants"][0]["size"] == "8"
    assert record["variants"][0]["url"] == f"{url}?variant=adult"
    assert record["variant_count"] == 1

@pytest.mark.unit
def test_infer_shared_variant_color_drops_trailing_style_code_tokens() -> None:
    record = {
        "title": "Jordan Air Jordan 5 Retro 'White Metallic'",
        "url": "https://www.dtlr.com/collections/men/products/jordan-air-jordan-5-retro-white-metallic-mf-white-hq7978-103",
        "variants": [
            {"size": "8"},
            {"size": "8.5"},
            {"size": "9"},
        ],
    }

    hydration._hydrate_variant_axes(record)

    assert [variant.get("color") for variant in record["variants"]] == [
        "White",
        "White",
        "White",
    ]

@pytest.mark.unit
def test_repair_ecommerce_detail_drops_color_values_misread_as_sizes() -> None:
    url = "https://www.macys.com/shop/product/tommy-hilfiger-mens-hiday-casualized-hybrid-oxfords"
    record: dict[str, object] = {
        "title": "Tommy Hilfiger Mens Virat Casualized Hybrid Oxfords",
        "variants": [
            {"size": "7M", "color": "Cognac"},
            {"size": "Cognac", "color": "Cognac"},
            {"size": "Black", "color": "Cognac"},
            {"size": "8M", "color": "Black"},
            {"size": "Black", "color": "Black"},
        ],
    }

    repair_ecommerce_detail_record_quality(
        record,
        html="<html></html>",
        page_url=url,
        requested_page_url=url,
    )

    assert record["variants"] == [
        {"size": "7M", "color": "Cognac"},
        {"size": "8M", "color": "Black"},
    ]

@pytest.mark.unit
def test_repair_ecommerce_detail_drops_same_url_color_only_variant_cluster() -> None:
    url = "https://colourpop.com/products/going-coconuts-eyeshadow-palette"
    record: dict[str, object] = {
        "title": "Going Coconuts",
        "variants": [
            {"color": "Pink Dreams", "url": f"{url}?variant=31181373636690"},
            {"color": "Blue Moon", "url": f"{url}?variant=31181373636690"},
        ],
    }

    repair_ecommerce_detail_record_quality(
        record,
        html="<html></html>",
        page_url=url,
        requested_page_url=url,
    )

    assert "variants" not in record
    assert "variant_count" not in record

@pytest.mark.unit
def test_repair_ecommerce_detail_filters_related_and_low_res_images() -> None:
    url = "https://www.aesop.com/home-fragrance/candles/aganice-aromatique-candle/HM03.html"
    record: dict[str, object] = {
        "title": "Aganice Aromatique Candle",
        "image_url": "https://www.aesop.com/dw/image/v2/AANG_PRD/on/demandware.static/-/Sites-aesop-us-master-catalog/default/dwdbcd8bbe/images/products/HM03/Aesop_Home_Aganice_Aromatique_Candle_Web_Front_2000x2000px.png",
        "additional_images": [
            "https://www.aesop.com/dw/image/v2/AANG_PRD/on/demandware.static/-/Sites-aesop-us-master-catalog/default/dw00834621/images/products/HM03/Aesop_Home_Aganice_Aromatique_Candle_Vessel_&_Carton_Front_2000x2000px.jpg?sw=1536&sh=1536",
            "https://www.aesop.com/dw/image/v2/AANG_PRD/on/demandware.static/-/Sites-aesop-us-master-catalog/default/dwb2be19cc/images/products/FR11/Aesop_Fragrance_Marrakech_Intense_Parfum_10mL_Vial_NGL_2000x2000px.jpg?sw=330&sh=330",
            "https://www.aesop.com/dw/image/v2/AANG_PRD/on/demandware.static/Sites-aesop-us-Site/-/default/dw9315f36d/images/landscape.png?sw=304&sh=250",
        ],
    }

    repair_ecommerce_detail_record_quality(
        record,
        html="<html></html>",
        page_url=url,
        requested_page_url=url,
    )

    assert record["additional_images"] == [
        "https://www.aesop.com/dw/image/v2/AANG_PRD/on/demandware.static/-/Sites-aesop-us-master-catalog/default/dw00834621/images/products/HM03/Aesop_Home_Aganice_Aromatique_Candle_Vessel_&_Carton_Front_2000x2000px.jpg?sw=1536&sh=1536"
    ]

@pytest.mark.unit
def test_repair_ecommerce_detail_prefers_active_color_image_and_drops_swatch_thumbs() -> (
    None
):
    url = "https://www.patagonia.com/product/mens-nano-puff-insulated-jacket/84213.html"
    record: dict[str, object] = {
        "title": "Men's Nano Puff Jacket",
        "brand": "Patagonia",
        "color": "Aquatic Blue",
        "image_url": "https://www.patagonia.com/dw/image/v2/BDJB_PRD/on/demandware.static/-/Sites-patagonia-master/default/dw3898a537/images/hi-res/84213_SMDB.jpg?sw=1920",
        "additional_images": [
            "https://www.patagonia.com/dw/image/v2/BDJB_PRD/on/demandware.static/-/Sites-patagonia-master/default/dwb71fb616/images/hi-res/84213_AQT.jpg?sw=1920",
            "https://images.urbndata.com/is/image/Anthropologie/108064080_001_s?fit=constrain&hei=56&qlt=75",
        ],
    }

    repair_ecommerce_detail_record_quality(
        record,
        html="<html></html>",
        page_url=url,
        requested_page_url=url,
    )

    assert "84213_AQT" in str(record["image_url"])
    assert all(
        "_s?fit=constrain&hei=56" not in image
        for image in record.get("additional_images", [])
    )

@pytest.mark.unit
def test_normalize_variant_record_keeps_url_when_same_axis_value_is_repeated() -> None:
    record = {
        "variants": [
            {"url": "https://example.com/p?variant=red", "color": "Red", "size": "S"},
            {"url": "https://example.com/p?variant=red", "color": "Red"},
        ],
    }

    normalize_variant_record(record)

    assert all(variant.get("url") for variant in record["variants"])  # nosec B101

@pytest.mark.unit
def test_repair_ecommerce_detail_trims_description_to_url_identity_chunk() -> None:
    url = "https://www.macys.com/shop/product/tommy-hilfiger-mens-hiday-casualized-hybrid-oxfords"
    record: dict[str, object] = {
        "title": "Tommy Hilfiger Mens Virat Casualized Hybrid Oxfords",
        "description": (
            "The Hiday men's lace-up oxford has a classic silhouette. "
            "Subtle branding details have been added. "
            "Elevate everyday style with these Tommy Hilfiger Foray sneakers. "
            "The Florsheim Midtown shoe is a different product."
        ),
    }

    repair_ecommerce_detail_record_quality(
        record,
        html="<html></html>",
        page_url=url,
        requested_page_url=url,
    )

    assert "Hiday" in str(record["description"])
    assert "Foray" not in str(record["description"])
    assert "Florsheim" not in str(record["description"])

@pytest.mark.unit
def test_coerce_field_value_category_rejects_url_path_strings() -> None:
    # Regression: gemini audit DQ-8 — Vans exposed a joined URL path
    # ("https: > www.vans.com > en-us > c > shoes > icons > old-skool-5205")
    # as the category field. URL-looking strings must be rejected so the
    # breadcrumb fallback can provide a real category label.
    assert (
        coerce_field_value(
            "category",
            "https: > www.vans.com > en-us > c > shoes > icons > old-skool-5205",
            "",
        )
        is None
    )
    assert coerce_field_value("category", "https://example.com/c/shoes", "") is None
    # But a real breadcrumb path must still pass through.
    assert (
        coerce_field_value("category", "Shoes > Icons > Old Skool", "")
        == "Shoes > Icons > Old Skool"
    )

@pytest.mark.unit
def test_normalize_value_price_preserves_semantic_integer_price_fields() -> None:
    assert normalize_value("price", "126") == "126"

@pytest.mark.unit
def test_normalize_value_price_normalizes_clean_decimal_strings() -> None:
    assert normalize_value("price", "0012.50") == "12.50"

@pytest.mark.unit
def test_normalize_value_unwraps_singleton_barcode_list_and_rounds_rating() -> None:
    assert normalize_value("barcode", "['0840424803104']") == "0840424803104"
    assert normalize_value("rating", "2.399113082039911") == pytest.approx(2.4)

@pytest.mark.unit
def test_coerce_text_fields_join_literal_list_strings() -> None:
    assert (
        coerce_field_value(
            "product_details",
            "['Leather upper with perforated toe box', 'Rubber outsole']",
            "",
        )
        == "Leather upper with perforated toe box; Rubber outsole"
    )

@pytest.mark.unit
def test_normalize_availability_schema_url() -> None:
    assert (
        normalize_value("availability", "https://schema.org/LimitedAvailability")
        == "limited_stock"
    )

@pytest.mark.unit
def test_variant_price_backfill_handles_numeric_string_equivalence() -> None:
    record: dict[str, object] = {
        "price": "10.00",
        "currency": "USD",
        "variants": [
            {"sku": "TEN", "price": 10.0},
            {"sku": "UNKNOWN"},
        ],
    }

    backfill._backfill_variant_context(record)

    assert record["variants"][0]["price"] == pytest.approx(10.0)
    assert record["variants"][1]["price"] == "10.00"

@pytest.mark.unit
def test_variant_price_backfill_treats_numeric_zero_as_distinct() -> None:
    record: dict[str, object] = {
        "price": "10.00",
        "currency": "USD",
        "variants": [
            {"sku": "FREE", "price": 0},
            {"sku": "UNKNOWN"},
        ],
    }

    backfill._backfill_variant_context(record)

    assert record["variants"][0]["price"] == 0
    assert "price" not in record["variants"][1]

@pytest.mark.unit
def test_field_coercion_repairs_source_quality_before_enrichment() -> None:
    assert coerce_field_value("brand", {"0": "Apple"}, "") == "Apple"
    assert coerce_field_value("brand", "8552", "") is None
    assert (
        coerce_field_value("availability", "https://schema.org/LimitedAvailability", "")
        == "limited_stock"
    )
    assert coerce_field_value("rating", {"ratingValue": "4.5"}, "") == pytest.approx(
        4.5
    )
    assert coerce_field_value("product_type", {"variationGroup": True}, "") is None

@pytest.mark.unit
def test_variant_option_dom_text_drops_child_price_badges() -> None:
    soup = BeautifulSoup(
        """
        <button role="radio" class="color-option">
          <span>Black</span><span>$382.00</span>
        </button>
        """,
        "html.parser",
    )

    assert extract_node_value(soup.button, "color", "https://example.com") == "Black"

@pytest.mark.unit
def test_normalize_variant_record_preserves_referenced_single_value_axes() -> None:
    record = {
        "variant_axes": {"size": ["Small", "Large"], "scent": ["Lavender"]},
        "variants": [
            {"option_values": {"size": "Small", "scent": "Lavender"}, "sku": "LAV-S"},
            {"option_values": {"size": "Large", "scent": "Lavender"}, "sku": "LAV-L"},
        ],
    }

    normalize_variant_record(record)

    assert record["variants"] == [
        {"size": "Small", "scent": "Lavender", "sku": "LAV-S"},
        {"size": "Large", "scent": "Lavender", "sku": "LAV-L"},
    ]
    assert record["variant_count"] == 2

@pytest.mark.unit
def test_normalize_variant_record_drops_subset_rows_using_indexed_axis_lookup() -> None:
    record = {
        "variants": [
            {"size": "M"},
            {"size": "M", "color": "Black"},
            {"size": "L"},
            {"size": "L", "color": "Black"},
        ],
    }

    normalize_variant_record(record)

    assert record["variants"] == [
        {"size": "M", "color": "Black"},
        {"size": "L", "color": "Black"},
    ]
    assert record["variant_count"] == 2

@pytest.mark.unit
def test_normalize_variant_record_drops_parent_sku_alias_rows_using_indexed_lookup() -> (
    None
):
    record = {
        "variants": [
            {"sku": "BOMBAS-BLACK", "size": "M"},
            {"sku": "BOMBAS-BLACK-M", "size": "M", "availability": "InStock"},
            {"sku": "BOMBAS-BLACK-L", "size": "L", "availability": "InStock"},
        ],
    }

    normalize_variant_record(record)

    assert record["variants"] == [
        {"sku": "BOMBAS-BLACK-M", "size": "M", "availability": "in_stock"},
        {"sku": "BOMBAS-BLACK-L", "size": "L", "availability": "in_stock"},
    ]
    assert record["variant_count"] == 2

@pytest.mark.unit
def test_normalize_variant_record_drops_axisless_rows_and_rejects_foreign_currency() -> (
    None
):
    record = {
        "currency": "GBP",
        "variants": [
            {"sku": "SKU-ONLY", "price": "10.00", "currency": "GBP"},
            {"color": "Black", "sku": "BLACK-1", "price": "10.00", "currency": "GBP"},
            {"size": "M", "sku": "RED-M", "price": "12.00", "currency": "EUR"},
        ],
    }

    normalize_variant_record(record)

    assert record["variants"] == [
        {"color": "Black", "sku": "BLACK-1", "price": "10.00", "currency": "GBP"}
    ]
    assert record["variant_count"] == 1

@pytest.mark.unit
def test_normalize_variant_record_drops_ui_control_variant_values() -> None:
    record = {
        "variants": [
            {"url": "javascript:void(0)", "size": "Your Cookie Settings"},
            {"size": "Show Reviews with 5 stars"},
            {"color": "Previous"},
            {"color": "Show image 1"},
            {"color": "Enable Keyboard Shortcuts:"},
            {"color": "Now & Every 15 Days"},
            {"size": "Shipping Restrictions : Sales and Export of this item"},
        ],
    }

    normalize_variant_record(record)

    assert "variants" not in record
    assert "variant_count" not in record

@pytest.mark.unit
def test_normalize_variant_record_drops_polluted_parent_scalar_axes() -> None:
    record = {
        "color": "Color",
        "size": "100 Softgels 200 Softgels 365 Softgels",
        "variants": [{"size": "100 Softgels"}, {"size": "200 Softgels"}],
    }

    normalize_variant_record(record)

    assert "color" not in record
    assert "size" not in record
    assert record["variant_count"] == 2

@pytest.mark.unit
def test_repair_ecommerce_detail_backfills_dom_variants_before_sanitizing_noise() -> (
    None
):
    html = """
    <main>
      <h1>Trail Shoe</h1>
      <select name="size">
        <option>Please select</option>
        <option>S</option>
        <option>M</option>
      </select>
    </main>
    """
    record = {
        "title": "Trail Shoe",
        "price": "49.99",
        "currency": "USD",
        "variants": [
            {"size": "Please select", "option_values": {"size": "Please select"}},
        ],
    }

    repair_ecommerce_detail_record_quality(
        record,
        html=html,
        page_url="https://example.com/products/trail-shoe",
        soup=BeautifulSoup(html, "html.parser"),
    )

    assert record["variants"] == [{"size": "S"}, {"size": "M"}]
    assert record["variant_count"] == 2

@pytest.mark.unit
def test_normalize_variant_record_drops_ce4_ui_and_cookie_axis_values() -> None:
    record = {
        "variants": [
            {"size": "Save to Wishlist"},
            {"size": "Saved to wishlist"},
            {"size": "Login to add to account Wishlist"},
            {"size": "necessary"},
            {"size": "functional"},
            {"size": "performance"},
            {"size": "targeting"},
            {"color": "Make Offer"},
            {"color": "Buy Now"},
            {"size": "sign in"},
            {"size": "Link your member number,"},
            {"size": "a lifetime of benefits."},
            {"size": "5 stars"},
            {"size": "-"},
            {"size": "+"},
        ],
    }

    normalize_variant_record(record)

    assert "variants" not in record
    assert "variant_count" not in record

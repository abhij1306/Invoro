from __future__ import annotations

from .test_normalizers import _reconcile_variant_derived_parent_fields, backfill, coerce_field_value, hydration, normalize_variant_record, pytest, repair_ecommerce_detail_record_quality, sanitization, sanitize_variant_row  # fmt: skip


@pytest.mark.unit
def test_normalize_variant_record_strips_learn_more_from_real_size() -> None:
    record = {
        "variants": [
            {
                "url": "https://www.size.co.uk/product/purple-shoe/19738059/?size=7",
                "size": "7 Learn More",
            },
            {
                "url": "https://www.size.co.uk/product/purple-shoe/19738059/?size=7-5",
                "size": "7.5 Learn More",
            },
        ],
    }

    normalize_variant_record(record)

    assert record["variants"] == [
        {
            "url": "https://www.size.co.uk/product/purple-shoe/19738059/?size=7",
            "size": "7",
        },
        {
            "url": "https://www.size.co.uk/product/purple-shoe/19738059/?size=7-5",
            "size": "7.5",
        },
    ]


@pytest.mark.unit
def test_normalize_variant_record_drops_quantity_size_controls_preserves_real_rows() -> (
    None
):
    record = {
        "variants": [
            {"size": "-", "color": "Black"},
            {"size": "+", "color": "Black"},
            {"size": "8 oz Ceramic", "color": "Black"},
        ],
    }

    normalize_variant_record(record)

    assert record["variants"] == [{"size": "8 oz Ceramic", "color": "Black"}]
    assert record["variant_count"] == 1


@pytest.mark.unit
def test_normalize_variant_record_preserves_real_short_axes_after_ui_noise_prune() -> (
    None
):
    record = {
        "variants": [
            {"url": "https://example.com/products/shirt?variant=1", "size": "M"},
            {"url": "https://example.com/products/shirt?variant=2", "color": "Navy"},
        ],
    }

    normalize_variant_record(record)

    assert record["variants"] == [
        {"size": "M", "url": "https://example.com/products/shirt?variant=1"},
        {"color": "Navy", "url": "https://example.com/products/shirt?variant=2"},
    ]
    assert record["variant_count"] == 2


@pytest.mark.unit
def test_normalize_variant_record_collapses_backmarket_carousel_compare_rows() -> None:
    record = {
        "variants": [
            {"color": "Previous", "storage": "128 GB", "condition": "Compare"},
            {"color": "Show image 1", "storage": "128 GB", "condition": "Compare"},
            {"color": "Next", "storage": "128 GB", "condition": "Compare"},
        ],
    }

    normalize_variant_record(record)

    assert record["variants"] == [{"storage": "128 GB"}]
    assert record["variant_count"] == 1


@pytest.mark.unit
def test_normalize_variant_record_promotes_color_values_misfiled_as_size() -> None:
    record = {
        "variants": [
            {"size": "Smoke Green (sold out)"},
            {"size": "Matte Black sold out"},
        ],
    }

    normalize_variant_record(record)

    assert record["variants"] == [
        {"color": "Smoke Green"},
        {"color": "Matte Black"},
    ]
    assert record["variant_count"] == 2


@pytest.mark.unit
def test_normalize_variant_record_infers_bombas_sizes_from_sku_suffixes() -> None:
    record = {
        "title": "Men's All Sport Ankle Socks",
        "variants": [
            {
                "sku": "A-E-A-129AM3-SADS-01P-BLACK-XL",
                "color": "black onyx",
                "price": "15.00",
            },
            {
                "sku": "A-E-A-129A44-CLAS-01P-BLACK-M",
                "color": "charcoal marl",
                "price": "15.00",
            },
            {
                "sku": "A-E-A-129A44-SOLI-01P-WHITE-L-2024",
                "color": "True White",
                "price": "15.00",
            },
        ],
    }

    normalize_variant_record(record)

    assert [variant.get("size") for variant in record["variants"]] == ["XL", "M", "L"]
    assert [variant.get("color") for variant in record["variants"]] == [
        "black onyx",
        "charcoal marl",
        "True White",
    ]
    assert record["variant_count"] == 3


@pytest.mark.unit
def test_normalize_variant_record_prunes_patagonia_cross_product_size_noise() -> None:
    record = {
        "title": "Men's Nano Puff Jacket",
        "gender": "Men",
        "variants": [
            {"size": "NB-7lb"},
            {"size": "0-3m"},
            {"size": "2T"},
            {"size": "XS"},
            {"size": "S"},
            {"size": "M"},
            {"size": "L"},
            {"size": "Climbing"},
            {"size": "Yoga"},
            {"size": "Runs Small"},
            {"size": "True to Size"},
        ],
    }

    normalize_variant_record(record)

    assert [variant["size"] for variant in record["variants"]] == ["XS", "S", "M", "L"]


@pytest.mark.unit
def test_normalize_variant_record_drops_backmarket_condition_tabs() -> None:
    record = {
        "variants": [
            {"color": "Black", "storage": "128 GB", "condition": "Fair"},
            {"color": "Blue", "storage": "128 GB", "condition": "Good"},
            {"color": "Black", "storage": "128 GB", "condition": "More"},
            {"color": "Black", "storage": "128 GB", "condition": "Condition (476)"},
            {"color": "Black", "storage": "128 GB", "condition": "Quality (383)"},
        ],
    }

    normalize_variant_record(record)

    assert record["variants"] == [
        {"color": "Black", "storage": "128 GB", "condition": "Fair"},
        {"color": "Blue", "storage": "128 GB", "condition": "Good"},
    ]
    assert record["variant_count"] == 2


@pytest.mark.unit
def test_normalize_variant_record_preserves_separate_suit_sizes_with_dimension_labels() -> (
    None
):
    record = {
        "title": "Italian Seersucker Sutton Suit",
        "variants": [
            {"size": "36S"},
            {"size": "40R"},
            {"size": "28/32"},
            {"size": "34/30"},
        ],
    }

    normalize_variant_record(record)

    assert record["variants"] == [
        {"size": "36S", "style": "Jacket"},
        {"size": "40R", "style": "Jacket"},
        {"size": "28/32", "style": "Pant"},
        {"size": "34/30", "style": "Pant"},
    ]
    assert record["variant_count"] == 4


@pytest.mark.unit
def test_normalize_variant_record_cleans_code_polluted_parent_color() -> None:
    record = {
        "title": "Jordan Air Jordan 5 Retro 'White Metallic'",
        "color": "Mf White Hq7978 103",
        "variants": [
            {"size": "8", "color": "Mf White Hq7978 103"},
            {"size": "8.5", "color": "Mf White Hq7978 103"},
        ],
    }

    normalize_variant_record(record)

    assert record["color"] == "White"


@pytest.mark.unit
def test_prune_unrecognized_size_rows_does_not_treat_any_style_as_size_dimension() -> (
    None
):
    record = {
        "title": "Sneaker",
        "variants": [
            {"size": "US 8"},
            {"size": "US 9"},
            {"size": "Comfort", "option_values": {"style": "Wide"}},
        ],
    }

    normalize_variant_record(record)

    assert record["variants"] == [{"size": "US 8"}, {"size": "US 9"}]
    assert record["variant_count"] == 2


@pytest.mark.unit
def test_enforce_variant_currency_context_keeps_all_mismatched_variants_for_review() -> (
    None
):
    record = {
        "currency": "INR",
        "variants": [
            {"size": "S", "currency": "USD", "price": "10"},
            {"size": "M", "currency": "EUR", "price": "12"},
        ],
    }

    backfill._enforce_variant_currency_context(record)

    assert record["variants"] == [
        {"size": "S", "currency": "USD", "price": "10"},
        {"size": "M", "currency": "EUR", "price": "12"},
    ]
    assert record["variant_count"] == 2
    assert len(record["variants_currency_mismatch"]) == 2


@pytest.mark.unit
def test_hydrate_variant_size_from_precompiled_sku_suffix_pattern(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        hydration,
        "variant_sku_size_suffix_patterns",
        (hydration.re.compile(r"-(?P<size>xs|xl)$", hydration.re.I),),
    )
    record = {
        "variants": [
            {"sku": "WIDGET-XS"},
            {"sku": "WIDGET-XL"},
        ],
    }

    hydration._hydrate_variant_axes(record)

    assert [variant["size"] for variant in record["variants"]] == ["XS", "XL"]


@pytest.mark.unit
def test_record_url_suffix_after_title_rejects_non_color_suffix_tokens() -> None:
    """SKU codes, product IDs, and structural tokens must not become color values.

    Regression: phase-eight URLs like
    ``/product/lucinda-spot-midi-dress-10015500806.html`` were producing
    ``"10015500806 Html"`` as the inferred shared variant color. URL suffix
    tokens that are pure digits/``html`` get filtered, and any single
    alphanumeric token with an embedded digit is treated as a SKU/style code.
    """
    # Numeric product id + .html suffix (Phase Eight pattern).
    assert (
        hydration._record_url_suffix_after_title(
            {
                "title": "Lucinda Spot Midi Dress",
                "url": "https://www.phase-eight.com/product/lucinda-spot-midi-dress-10015500806.html",
            }
        )
        == ""
    )
    # SKU-style alphanumeric trailing token (savannahs/Pavlova pattern).
    assert (
        hydration._record_url_suffix_after_title(
            {
                "title": "Pavlova 100 Lace Up Blush Satin Boots",
                "url": "https://savannahs.com/products/pavlova-100-lace-up-blush-satin-boots-cl28517s",
            }
        )
        == ""
    )
    # Genuine alphabetic color slug is still preserved (Allbirds Tuke River).
    assert (
        hydration._record_url_suffix_after_title(
            {
                "title": "Men's Wool Runner",
                "url": "https://www.allbirds.com/products/mens-wool-runners-tuke-river",
            }
        )
        == "Tuke River"
    )


@pytest.mark.unit
def test_infer_shared_variant_color_skips_when_url_suffix_is_not_a_color() -> None:
    """End-to-end: variants without color stay clean when URL suffix is a code."""
    record = {
        "title": "Lucinda Spot Midi Dress",
        "url": "https://www.phase-eight.com/product/lucinda-spot-midi-dress-10015500806.html",
        "variants": [
            {"size": "UK 06"},
            {"size": "UK 08"},
            {"size": "UK 10"},
        ],
    }

    hydration._hydrate_variant_axes(record)

    for variant in record["variants"]:
        assert "color" not in variant or not variant["color"]


@pytest.mark.unit
def test_sanitize_variant_axes_normalizes_mixed_case_axis_keys() -> None:
    record = {
        "variants": [
            {"Size": "US 8", "Color": "Black", "sku": "A"},
            {"Size": "US 9", "Color": "Black", "sku": "B"},
        ],
    }

    sanitization._sanitize_variant_axes(record)

    assert record["variants"] == [
        {"sku": "A", "size": "US 8", "color": "Black"},
        {"sku": "B", "size": "US 9", "color": "Black"},
    ]


@pytest.mark.unit
def test_normalize_variant_record_keeps_independent_color_rows_without_selected_parent_color() -> (
    None
):
    record = {
        "title": "Canvas Sneaker",
        "variants": [
            {"color": "Black"},
            {"color": "White"},
            {"size": "US 8"},
            {"size": "US 9"},
        ],
    }

    normalize_variant_record(record)

    assert record["variants"] == [
        {"color": "Black"},
        {"color": "White"},
        {"size": "US 8"},
        {"size": "US 9"},
    ]


@pytest.mark.unit
def test_normalize_variant_record_drops_foreign_product_titles_misfiled_as_colors() -> (
    None
):
    record = {
        "title": "40th Anniversary Graphic Womens Short Sleeve Shirt",
        "variants": [
            {"color": "Black/Red"},
            {"color": "Flight Muay Thai Mens Shorts (Black/Sail/University Red)"},
            {"color": 'Brooklyn Graphic 9" Mens Shorts (Black/Gray)'},
        ],
    }

    normalize_variant_record(record)

    assert record["variants"] == [{"color": "Black/Red"}]


@pytest.mark.unit
def test_normalize_variant_record_prunes_global_axes_and_collapses_permutations() -> (
    None
):
    variants = []
    for size in ("8 US", "9 US"):
        for site in ("Kith.com", "Kith.eu"):
            for currency in ("AL / L", "AD / EUR"):
                variants.append(
                    {
                        "price": "282",
                        "currency": "USD",
                        "option_values": {
                            "size": size,
                            "select_site": site,
                            "select_currency": currency,
                        },
                    }
                )
    record = {
        "variant_axes": {
            "size": ["8 US", "9 US"],
            "select_site": ["Kith.com", "Kith.eu"],
            "select_currency": ["AL / L", "AD / EUR"],
        },
        "variants": variants,
    }

    normalize_variant_record(record)

    assert record["variant_count"] == 2


@pytest.mark.unit
def test_normalize_variant_record_strips_currently_unavailable_suffixes() -> None:
    record = {
        "variant_axes": {"size": ["12.5 is currently unavailable.", "13"]},
        "variants": [
            {
                "size": "12.5 is currently unavailable.",
                "availability": "out_of_stock",
                "option_values": {"size": "12.5 is currently unavailable."},
            },
            {
                "size": "13",
                "option_values": {"size": "13"},
            },
        ],
    }

    normalize_variant_record(record)

    assert record["variants"][0]["size"] == "12.5"


@pytest.mark.unit
def test_normalize_variant_record_preserves_identity_less_variants_and_drops_selected_variant() -> (
    None
):
    record = {
        "selected_variant": {
            "title": "Selected from adapter",
            "option_values": {"size": "Large"},
        },
        "variants": [
            {"sku": "sku-1", "option_values": {"size": "Large"}},
            {"sku": "sku-2", "option_values": {"size": "XL"}},
        ],
    }

    normalize_variant_record(record)

    assert "selected_variant" not in record
    assert record["variant_count"] == 2
    assert len(record["variants"]) == 2
    assert any(
        variant.get("sku") == "sku-1" and variant.get("size") == "Large"
        for variant in record["variants"]
    )
    assert any(
        variant.get("sku") == "sku-2" and variant.get("size") == "XL"
        for variant in record["variants"]
    )


@pytest.mark.unit
def test_normalize_variant_record_merges_semantic_duplicate_rows_and_size_aliases() -> (
    None
):
    record = {
        "variant_axes": {"size": ["3", "4", "8", "8 US"]},
        "variants": [
            {
                "sku": "13875993",
                "variant_id": "45140428423360",
                "size": "3",
                "price": "284.00",
                "currency": "USD",
                "availability": "out_of_stock",
                "option_values": {"size": "3"},
            },
            {
                "sku": "13875994",
                "variant_id": "45140428456128",
                "size": "4",
                "price": "284.00",
                "currency": "USD",
                "availability": "out_of_stock",
                "option_values": {"size": "4"},
            },
            {
                "size": "3",
                "price": "284.00",
                "currency": "USD",
                "availability": "in_stock",
                "option_values": {"size": "3"},
            },
            {
                "size": "4",
                "price": "284.00",
                "currency": "USD",
                "availability": "in_stock",
                "option_values": {"size": "4"},
            },
            {
                "sku": "13876003",
                "variant_id": "45140428619904",
                "size": "8",
                "price": "284.00",
                "currency": "USD",
                "availability": "out_of_stock",
                "option_values": {"size": "8"},
            },
            {
                "size": "8 US",
                "price": "284.00",
                "currency": "USD",
                "availability": "in_stock",
                "option_values": {"size": "8 US"},
            },
        ],
        "selected_variant": {
            "size": "4",
            "price": "284.00",
            "currency": "USD",
            "availability": "in_stock",
            "option_values": {"size": "4"},
        },
    }

    normalize_variant_record(record)

    assert record["variant_count"] == 3


@pytest.mark.unit
def test_detail_record_quality_repairs_invalid_original_prices_and_selected_variant_availability() -> (
    None
):
    record = {
        "sku": "M20324",
        "url": "https://www.adidas.com/us/stan-smith-shoes/M20324.html",
        "size": "4",
        "price": "100.00",
        "currency": "USD",
        "availability": "out_of_stock",
        "original_price": "1.00",
        "title": "Stan Smith Shoes",
        "variants": [
            {
                "size": "4",
                "price": "100.00",
                "currency": "USD",
                "availability": "out_of_stock",
                "option_values": {"size": "4"},
                "original_price": "1.00",
            },
            {
                "size": "4.5",
                "price": "100.00",
                "currency": "USD",
                "availability": "out_of_stock",
                "option_values": {"size": "4.5"},
                "original_price": "1.00",
            },
        ],
        "selected_variant": {
            "sku": "M20324",
            "size": "4",
            "price": "100.00",
            "currency": "USD",
            "availability": "in_stock",
            "option_values": {"size": "4"},
            "original_price": "1.00",
        },
    }

    normalize_variant_record(record)
    repair_ecommerce_detail_record_quality(
        record,
        html="<html></html>",
        page_url="https://www.adidas.com/us/stan-smith-shoes/M20324.html",
    )

    assert record["original_price"] == "100.00"
    assert all("original_price" not in variant for variant in record["variants"])


@pytest.mark.unit
def test_detail_record_quality_does_not_downgrade_in_stock_parent_from_partial_variants() -> (
    None
):
    record = {
        "title": "Example Shoe",
        "price": "100.00",
        "currency": "USD",
        "availability": "in_stock",
        "variants": [
            {
                "size": "8",
                "availability": "out_of_stock",
                "option_values": {"size": "8"},
            },
            {
                "size": "9",
                "availability": "unknown",
                "option_values": {"size": "9"},
            },
        ],
    }

    repair_ecommerce_detail_record_quality(
        record,
        html="<html></html>",
        page_url="https://example.com/products/example-shoe",
    )

    assert record["availability"] == "in_stock"


@pytest.mark.unit
def test_reconcile_variant_derived_parent_fields_clears_stale_values_without_variants() -> (
    None
):
    record = {
        "image_url": "https://cdn.example.com/variant.jpg",
        "availability": "out_of_stock",
    }

    _reconcile_variant_derived_parent_fields(
        record,
        variant_parent_image="https://cdn.example.com/variant.jpg",
        variant_parent_availability="out_of_stock",
    )

    assert "image_url" not in record
    assert "availability" not in record


@pytest.mark.unit
def test_detail_record_quality_does_not_overwrite_structured_color_from_description() -> (
    None
):
    record = {
        "title": "Example Jacket",
        "color": "Black",
        "description": "Made with 'Red' leather upper.",
        "_field_sources": {"color": ["structured"]},
    }

    repair_ecommerce_detail_record_quality(
        record,
        html="<html></html>",
        page_url="https://example.com/products/example-jacket",
    )

    assert record["color"] == "Black"
    assert record["_field_sources"]["color"] == ["structured"]


@pytest.mark.unit
def test_detail_record_quality_does_not_assign_numeric_prefix_brand_without_url_match() -> (
    None
):
    record = {"title": "123 Example Jacket"}

    repair_ecommerce_detail_record_quality(
        record,
        html="<html></html>",
        page_url="https://example.com/products/example-jacket",
    )

    assert "brand" not in record


@pytest.mark.unit
def test_field_coerce_ignores_non_json_structured_category_text() -> None:
    assert (
        coerce_field_value(
            "category",
            "{not json but user visible category text",
            "https://example.com/products/example",
        )
        == "{not json but user visible category text"
    )


@pytest.mark.unit
def test_sanitize_variant_row_preserves_relative_image_paths() -> None:
    variant = {"size": "8", "image_url": "/images/example-shoe-8.jpg"}

    assert sanitize_variant_row(
        variant,
        identity_url="https://example.com/products/example-shoe",
        title_hint="Example Shoe",
    )
    assert variant["image_url"] == "/images/example-shoe-8.jpg"

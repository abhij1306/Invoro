from __future__ import annotations

from .test_field_value_core import Decimal, absolute_url, coerce_field_value, decimal_for_shared_price, direct_record_to_surface_fields, extract_currency_code, is_title_noise, public_record_data_for_surface, pytest, registrable_host, same_site, strip_tracking_query_params, surface_alias_lookup, validate_record_for_surface  # fmt: skip

@pytest.mark.unit
def test_absolute_url_promotes_bare_host_candidates_to_https() -> None:
    assert (
        absolute_url(
            "https://www.asos.com/us/prd/210817202",
            "images.asos-media.com/products/widget/image-1.jpg",
        )
        == "https://images.asos-media.com/products/widget/image-1.jpg"
    )

@pytest.mark.unit
def test_absolute_url_does_not_promote_hosts_with_edge_hyphen_labels() -> None:
    assert absolute_url("https://example.com/base/", "-bad.example/path") == (
        "https://example.com/base/-bad.example/path"
    )
    assert absolute_url("https://example.com/base/", "bad-.example/path") == (
        "https://example.com/base/bad-.example/path"
    )

@pytest.mark.unit
def test_coerce_brand_rejects_url_like_values() -> None:
    assert (
        coerce_field_value(
            "brand",
            "https://www.vitacost.com/brand",
            "https://www.vitacost.com/p/x",
        )
        is None
    )
    assert (
        coerce_field_value(
            "brand",
            {"@type": "Brand", "name": "https://www.example.com/brand/acme"},
            "https://www.example.com/p/x",
        )
        is None
    )
    assert (
        coerce_field_value("brand", {"name": "Acme"}, "https://example.com/p/x")
        == "Acme"
    )

@pytest.mark.unit
def test_coerce_title_supports_structured_values_key() -> None:
    assert (
        coerce_field_value(
            "title",
            {"values": "Widget Prime"},
            "https://example.com/products/widget-prime",
        )
        == "Widget Prime"
    )

@pytest.mark.unit
def test_coerce_brand_keeps_non_url_scheme_text_but_rejects_full_bare_host() -> None:
    assert (
        coerce_field_value("brand", "foo:bar", "https://example.com/p/x") == "foo:bar"
    )
    assert (
        coerce_field_value("brand", "shop.example.com", "https://example.com/p/x")
        is None
    )

@pytest.mark.unit
def test_frequently_bought_together_is_title_noise() -> None:
    assert is_title_noise("Frequently Bought Together") is True

@pytest.mark.unit
def test_validate_record_for_surface_drops_unknown_fields_but_keeps_canonical_fields() -> (
    None
):
    cleaned, errors = validate_record_for_surface(
        {
            "title": "Widget Prime",
            "price": {"amount": "19.99"},
            "random_garbage_key": "keep me out",
        },
        "ecommerce_detail",
    )

    assert cleaned == {"title": "Widget Prime", "price": {"amount": "19.99"}}
    assert errors == []

@pytest.mark.unit
def test_ecommerce_aliases_keep_product_id_distinct_from_sku() -> None:
    aliases = surface_alias_lookup("ecommerce_detail", None)

    assert aliases["product_id"] == "product_id"
    assert aliases["sku"] == "sku"

@pytest.mark.unit
def test_ecommerce_price_original_aliases_to_original_price() -> None:
    aliases = surface_alias_lookup("ecommerce_detail", None)

    assert aliases["price_original"] == "original_price"

@pytest.mark.unit
def test_direct_record_to_surface_fields_rejects_unknown_requested_fields() -> None:
    shaped = direct_record_to_surface_fields(
        {
            "title": "Widget Prime",
            "unknown_requested_field": "leak",
        },
        surface="ecommerce_detail",
        page_url="https://example.com/products/widget-prime",
        requested_fields=["unknown_requested_field"],
    )

    assert shaped == {"title": "Widget Prime"}

@pytest.mark.unit
def test_decimal_for_shared_price_supports_european_decimal_format() -> None:
    assert decimal_for_shared_price("1.234,56") == Decimal("1234.56")
    assert decimal_for_shared_price("234,56") == Decimal("234.56")
    assert decimal_for_shared_price("1.234.567,89") == Decimal("1234567.89")

@pytest.mark.unit
def test_coerce_price_rejects_negative_currency_fallbacks() -> None:
    url = "https://www.gucci.com/int/en/pr/men/accessories-for-men/scarves-for-men/scarves-for-men/gg-wool-silk-jacquard-stole-p-8705434GAK31360"

    assert coerce_field_value("price", "-1", url) is None
    assert coerce_field_value("price", "$-1", url) is None
    assert coerce_field_value("price", "−1", url) is None
    assert coerce_field_value("price", {"amount": "$-1"}, url) is None

@pytest.mark.unit
def test_persistence_schema_firewall_drops_unknown_and_internal_fields() -> None:
    data, rejected = public_record_data_for_surface(
        {
            "title": "Widget Prime",
            "price": "19.99",
            "_source": "llm_direct_record_extraction",
            "debug_payload": {"raw": True},
        },
        surface="ecommerce_detail",
        page_url="https://example.com/products/widget-prime",
    )

    assert data == {"title": "Widget Prime", "price": "19.99"}
    assert rejected == {"debug_payload": "field_not_allowed_for_surface"}

@pytest.mark.unit
def test_persistence_schema_firewall_keeps_ecommerce_gender() -> None:
    data, rejected = public_record_data_for_surface(
        {
            "title": "Linen Dress",
            "gender": "women",
        },
        surface="ecommerce_detail",
        page_url="https://example.com/products/linen-dress",
    )

    assert data == {"title": "Linen Dress", "gender": "Women"}
    assert rejected == {}

@pytest.mark.unit
def test_public_record_firewall_validates_identity_shapes() -> None:
    data, rejected = public_record_data_for_surface(
        {
            "barcode": "COPY-ABC123",
            "gender": "default",
            "brand": "Acme | US",
            "product_id": "specifications",
            "product_type": "BRIGHTCOVE VIDEO PLAYER",
            "sku": "tmp-ABC-123",
        },
        surface="ecommerce_detail",
        page_url="https://example.com/products/widget",
    )

    assert data == {"sku": "ABC-123", "brand": "Acme"}
    assert rejected == {
        "barcode": "empty_after_coercion",
        "gender": "empty_after_coercion",
        "product_id": "empty_after_coercion",
        "product_type": "empty_after_coercion",
    }

@pytest.mark.unit
def test_coerce_sku_drops_draft_prefixed_numeric_artifacts() -> None:
    assert (
        coerce_field_value(
            "sku",
            "COPY-1720644688978",
            "https://example.com/products/widget",
        )
        is None
    )

@pytest.mark.unit
def test_public_record_firewall_flattens_variants_to_public_shape() -> None:
    data, rejected = public_record_data_for_surface(
        {
            "title": "Widget",
            "variants": [
                {
                    "variant_id": "1",
                    "title": "Widget Red Small",
                    "option_values": {"Colour": "Red", "Size": "S"},
                    "sku": "W-S",
                    "barcode": "ABC123",
                    "price": "$19.99",
                    "currency": "USD",
                    "url": "/products/widget?variant=1",
                }
            ],
            "variant_count": 1,
            "selected_variant": {"sku": "legacy"},
            "variant_axes": {"size": ["S"]},
            "available_sizes": ["S"],
            "option1_name": "size",
            "option1_values": ["S"],
        },
        surface="ecommerce_detail",
        page_url="https://example.com/products/widget",
    )

    assert data == {
        "title": "Widget",
        "variants": [
            {
                "color": "Red",
                "size": "S",
                "sku": "W-S",
                "price": "19.99",
                "currency": "USD",
                "url": "https://example.com/products/widget?variant=1",
            }
        ],
        "variant_count": 1,
    }
    assert rejected == {
        "selected_variant": "public_contract_excluded",
        "variant_axes": "public_contract_excluded",
        "available_sizes": "public_contract_excluded",
        "option1_name": "public_contract_excluded",
        "option1_values": "public_contract_excluded",
    }

@pytest.mark.unit
def test_public_record_firewall_preserves_url_query_currency_param() -> None:
    data, _rejected = public_record_data_for_surface(
        {
            "title": "Widget",
            "variants": [
                {
                    "url": "/products/widget?country=IN&currency%3DINR&variant=1",
                    "color": "Silver",
                },
                {
                    "url": "/products/widget?country=IN&amp;currency%3DINR&amp;variant=2",
                    "color": "Black",
                },
            ],
        },
        surface="ecommerce_detail",
        page_url="https://example.com/products/widget",
    )

    assert data["variants"] == [
        {
            "color": "Silver",
            "url": "https://example.com/products/widget?country=IN&currency%3DINR&variant=1",
        },
        {
            "color": "Black",
            "url": "https://example.com/products/widget?country=IN&currency%3DINR&variant=2",
        },
    ]

@pytest.mark.unit
def test_public_record_firewall_normalizes_variant_axis_aliases() -> None:
    data, _rejected = public_record_data_for_surface(
        {
            "title": "Widget",
            "variants": [
                {
                    "option_values": {
                        "Hue": "Midnight Black",
                        "Measurements": "10 x 12 x 2 cm",
                        "Part or Kit": "Starter Pack",
                    },
                    "sku": "W-BLK",
                }
            ],
            "variant_count": 1,
        },
        surface="ecommerce_detail",
        page_url="https://example.com/products/widget",
    )

    assert data == {
        "title": "Widget",
        "variants": [
            {
                "color": "Midnight Black",
                "dimensions": "10 x 12 x 2 cm",
                "bundle_type": "Starter Pack",
                "sku": "W-BLK",
            }
        ],
        "variant_count": 1,
    }

@pytest.mark.unit
def test_public_record_firewall_preserves_flat_variant_style_axis() -> None:
    data, rejected = public_record_data_for_surface(
        {
            "title": "Italian Seersucker Sutton Suit",
            "variants": [
                {
                    "option_values": {"style": "Jacket", "size": "36S"},
                    "sku": "SUIT-JKT-36S",
                },
                {
                    "option_values": {"style": "Pant", "size": "28/32"},
                    "sku": "SUIT-PANT-28-32",
                },
            ],
            "variant_count": 2,
        },
        surface="ecommerce_detail",
        page_url="https://example.com/products/suit",
    )

    assert data == {
        "title": "Italian Seersucker Sutton Suit",
        "variants": [
            {"size": "36S", "style": "Jacket", "sku": "SUIT-JKT-36S"},
            {"size": "28/32", "style": "Pant", "sku": "SUIT-PANT-28-32"},
        ],
        "variant_count": 2,
    }
    assert rejected == {}

@pytest.mark.unit
def test_public_record_firewall_preserves_type_switches_fit_and_length_axes() -> None:
    data, rejected = public_record_data_for_surface(
        {
            "title": "Variant Widget",
            "variants": [
                {
                    "option_values": {
                        "Type": "Fully Assembled Knob",
                        "Color": "Carbon Black",
                        "Switches": "Gateron Jupiter Red",
                    },
                    "sku": "V1M-D1",
                },
                {
                    "option_values": {
                        "Fit": "Short",
                        "Length": "Regular",
                    },
                    "sku": "COAT-SHORT",
                },
            ],
            "variant_count": 2,
        },
        surface="ecommerce_detail",
        page_url="https://example.com/products/variant-widget",
    )

    assert data == {
        "title": "Variant Widget",
        "variants": [
            {
                "type": "Fully Assembled Knob",
                "color": "Carbon Black",
                "switches": "Gateron Jupiter Red",
                "sku": "V1M-D1",
            },
            {
                "fit": "Short",
                "length": "Regular",
                "sku": "COAT-SHORT",
            },
        ],
        "variant_count": 2,
    }
    assert rejected == {}

@pytest.mark.unit
def test_public_record_firewall_drops_parent_shared_variant_fields_but_keeps_price_currency() -> (
    None
):
    data, rejected = public_record_data_for_surface(
        {
            "title": "Widget",
            "price": "19.99",
            "currency": "USD",
            "url": "https://example.com/products/widget",
            "image_url": "https://cdn.example.com/widget.jpg",
            "variants": [
                {
                    "option_values": {"Colour": "Red", "Size": "S"},
                    "price": "$19.99",
                    "currency": "USD",
                    "url": "https://example.com/products/widget",
                    "image_url": "https://cdn.example.com/widget.jpg",
                },
                {
                    "option_values": {"Colour": "Blue", "Size": "M"},
                    "price": "$24.99",
                    "currency": "USD",
                    "url": "https://example.com/products/widget?variant=blue-m",
                    "image_url": "https://cdn.example.com/widget.jpg",
                },
            ],
            "variant_count": 2,
        },
        surface="ecommerce_detail",
        page_url="https://example.com/products/widget",
    )

    assert data == {
        "title": "Widget",
        "price": "19.99",
        "currency": "USD",
        "url": "https://example.com/products/widget",
        "image_url": "https://cdn.example.com/widget.jpg",
        "variants": [
            {
                "color": "Red",
                "size": "S",
                "price": "19.99",
                "currency": "USD",
                "url": "https://example.com/products/widget",
            },
            {
                "color": "Blue",
                "size": "M",
                "price": "24.99",
                "currency": "USD",
                "url": "https://example.com/products/widget?variant=blue-m",
            },
        ],
        "variant_count": 2,
    }
    assert rejected == {}

@pytest.mark.unit
def test_public_record_firewall_drops_ecommerce_tags_even_when_allowed() -> None:
    data, rejected = public_record_data_for_surface(
        {
            "title": "Widget",
            "tags": ["size_10", "stock_in-stock", "featured"],
        },
        surface="ecommerce_detail",
        page_url="https://example.com/products/widget",
        requested_fields=["tags"],
    )

    assert data == {"title": "Widget"}
    assert rejected == {"tags": "public_contract_excluded"}

@pytest.mark.unit
def test_persistence_schema_firewall_drops_default_ecommerce_schema_pollution() -> None:
    data, rejected = public_record_data_for_surface(
        {
            "title": "Widget Prime",
            "brand": "Acme",
            "vendor": "Acme",
            "product_type": "CriteoProductRail",
            "image_count": 12,
            "variant_count": 4,
            "option1_name": "Size",
            "option1_values": ["4 lb", "12 lb"],
            "canonical_url": "https://example.com/products/widget-prime",
            "created_at": "2026-04-28T10:00:00Z",
            "published_at": "2026-04-28T10:00:00Z",
        },
        surface="ecommerce_detail",
        page_url="https://example.com/products/widget-prime",
    )

    assert data == {
        "title": "Widget Prime",
        "brand": "Acme",
        "vendor": "Acme",
        "product_type": "CriteoProductRail",
        "variant_count": 4,
    }
    assert rejected == {
        "image_count": "default_public_field_excluded",
        "option1_name": "public_contract_excluded",
        "option1_values": "public_contract_excluded",
        "canonical_url": "default_public_field_excluded",
        "created_at": "default_public_field_excluded",
        "published_at": "default_public_field_excluded",
    }

@pytest.mark.unit
def test_persistence_schema_firewall_keeps_explicitly_requested_pollution_field() -> (
    None
):
    data, rejected = public_record_data_for_surface(
        {
            "title": "Widget Prime",
            "product_type": "Dog Food",
            "vendor": "Acme",
        },
        surface="ecommerce_detail",
        page_url="https://example.com/products/widget-prime",
        requested_fields=["product_type"],
    )

    assert data == {
        "title": "Widget Prime",
        "product_type": "Dog Food",
        "vendor": "Acme",
    }
    assert rejected == {}

@pytest.mark.unit
def test_persistence_schema_firewall_canonicalizes_detail_url_query_params() -> None:
    data, rejected = public_record_data_for_surface(
        {
            "title": "Shape Tape Concealer",
            "url": (
                "https://www.ulta.com/p/shape-tape-concealer-xlsImpprod14251035"
                "?sku=2501218&size=0.33oz&utm_source=ad"
            ),
        },
        surface="ecommerce_detail",
        page_url="https://www.ulta.com/p/shape-tape-concealer-xlsImpprod14251035",
    )

    assert data == {
        "title": "Shape Tape Concealer",
        "url": "https://www.ulta.com/p/shape-tape-concealer-xlsImpprod14251035",
    }
    assert rejected == {}

@pytest.mark.unit
def test_persistence_schema_firewall_normalizes_availability_enum_values() -> None:
    data, rejected = public_record_data_for_surface(
        {
            "title": "Apple AirPods",
            "availability": "OUT_OF_STOCK",
        },
        surface="ecommerce_detail",
        page_url="https://www.walmart.com/ip/Apple-AirPods/604342441",
    )

    assert data["availability"] == "out_of_stock"
    assert rejected == {}

@pytest.mark.unit
def test_persistence_schema_firewall_strips_size_cta_suffixes() -> None:
    data, rejected = public_record_data_for_surface(
        {
            "title": "Shape Tape Concealer",
            "size": "0.33 oz Find your shade",
        },
        surface="ecommerce_detail",
        page_url="https://www.ulta.com/p/shape-tape-concealer-xlsImpprod14251035",
    )

    assert data["size"] == "0.33 oz"
    assert rejected == {}

@pytest.mark.unit
def test_listing_url_firewall_preserves_functional_variant_query_params() -> None:
    data, rejected = public_record_data_for_surface(
        {
            "title": "Widget Prime",
            "url": "https://example.com/products/widget-prime?variant=blue",
        },
        surface="ecommerce_listing",
        page_url="https://example.com/collections/widgets",
    )

    assert data == {
        "title": "Widget Prime",
        "url": "https://example.com/products/widget-prime?variant=blue",
    }
    assert rejected == {}

@pytest.mark.unit
def test_listing_url_firewall_rejects_api_event_click_urls() -> None:
    data, rejected = public_record_data_for_surface(
        {
            "title": "Tracked card",
            "url": "https://www.chewy.com/api/event/p/sar/click?adsOrigin=aspen1&id=opaque",
            "price": "$12.50",
        },
        surface="ecommerce_listing",
        page_url="https://www.chewy.com/b/dog-leashes-and-collars-344",
    )

    assert data == {"title": "Tracked card", "price": "12.50"}
    assert rejected == {"url": "unsafe_navigation_url"}

@pytest.mark.unit
def test_llm_outputs_pass_same_schema_firewall() -> None:
    data, rejected = public_record_data_for_surface(
        {
            "_source": "llm_missing_field_extraction",
            "title": "LLM Widget",
            "url": "javascript:alert(1)",
            "unknown_llm_field": "do not persist",
        },
        surface="ecommerce_listing",
        page_url="https://example.com/category/widgets",
    )

    assert data == {"title": "LLM Widget"}
    assert rejected == {
        "url": "unsafe_navigation_url",
        "unknown_llm_field": "field_not_allowed_for_surface",
    }

@pytest.mark.unit
def test_strip_tracking_query_params_removes_etsy_style_click_tracking_but_keeps_functional_values() -> (
    None
):
    cleaned = strip_tracking_query_params(
        "https://example.com/products/widget-prime"
        "?click_key=opaque"
        "&click_sum=12345"
        "&ls=r"
        "&external=1"
        "&sr_prefetch=0"
        "&pf_from=rlp"
        "&pro=1"
        "&frs=1"
        "&sts=1"
        "&content_source=opaque_source"
        "&variant=blue"
    )

    assert cleaned == "https://example.com/products/widget-prime?variant=blue"

@pytest.mark.unit
def test_strip_tracking_query_params_keeps_short_flags_without_detail_context_tracking() -> (
    None
):
    cleaned = strip_tracking_query_params(
        "https://example.com/products/widget-prime?gclid=opaque&ls=r&variant=blue"
    )

    assert cleaned == "https://example.com/products/widget-prime?ls=r&variant=blue"

@pytest.mark.unit
def test_registrable_host_returns_ipv4_address() -> None:
    assert registrable_host("http://192.168.1.1/product") == "192.168.1.1"

@pytest.mark.unit
def test_same_site_ipv4_same_host_is_true() -> None:
    assert same_site("http://192.168.1.1/product", "http://192.168.1.1/cart")

@pytest.mark.unit
def test_same_site_ipv4_different_host_is_false() -> None:
    assert not same_site("http://192.168.1.1/product", "http://192.168.1.2/cart")

@pytest.mark.unit
def test_extract_currency_code_supports_rs_price_prefixes() -> None:
    assert extract_currency_code("Rs. 3,990.00") == "INR"
    assert extract_currency_code("INR 499") == "INR"

@pytest.mark.unit
def test_extract_currency_code_ignores_non_currency_uppercase_acronyms() -> None:
    assert extract_currency_code("SKU 499") is None

@pytest.mark.unit
def test_literal_list_text_uses_readable_delimiters() -> None:
    assert (
        coerce_field_value(
            "description",
            "['Digital max resolution', 'Real boost clock: 1800 MHz']",
            "https://example.com/p/card",
        )
        == "Digital max resolution; Real boost clock: 1800 MHz"
    )

@pytest.mark.unit
def test_price_dict_prefers_formatted_money_over_low_signal_scalar() -> None:
    assert (
        coerce_field_value(
            "price",
            {
                "value": 1,
                "formattedPrice": "2299.99",
                "priceCurrency": "USD",
            },
            "https://www.costco.com/p/example",
        )
        == "2299.99"
    )

@pytest.mark.unit
def test_price_dict_prefers_formatted_money_when_value_is_close() -> None:
    assert (
        coerce_field_value(
            "price",
            {"value": 100, "formattedPrice": "$100.00", "priceCurrency": "USD"},
            "https://example.com/p/widget",
        )
        == "$100.00"
    )

@pytest.mark.unit
def test_price_dict_uses_value_when_formatted_missing() -> None:
    assert (
        coerce_field_value(
            "price",
            {"value": 100, "formattedPrice": "", "priceCurrency": "USD"},
            "https://example.com/p/widget",
        )
        == "100"
    )

@pytest.mark.unit
def test_price_dict_handles_missing_currency() -> None:
    assert (
        coerce_field_value(
            "price",
            {"value": 100, "formattedPrice": "100.00"},
            "https://example.com/p/widget",
        )
        == "100.00"
    )

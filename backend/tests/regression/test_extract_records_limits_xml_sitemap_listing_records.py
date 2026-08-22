from __future__ import annotations

from .test_crawl_engine import dom_variants_add_missing_existing_axis, extract_records, map_js_state_to_fields, normalize_variant_record, pytest, sanitize_variant_row  # fmt: skip


@pytest.mark.regression
def test_extract_records_limits_xml_sitemap_listing_records() -> None:
    xml = """
    <?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>https://example.com/products/widget-prime</loc></url>
      <url><loc>https://example.com/products/widget-pro</loc></url>
    </urlset>
    """

    rows = extract_records(
        xml,
        "https://example.com/media/sitemap-products.xml",
        "ecommerce_listing",
        max_records=1,
        content_type="application/xml; charset=utf-8",
    )

    assert [row["url"] for row in rows] == ["https://example.com/products/widget-prime"]


@pytest.mark.regression
def test_extract_records_emits_rss_listing_records_from_link_nodes() -> None:
    rss = """
    <?xml version="1.0" encoding="UTF-8"?>
    <rss version="2.0">
      <channel>
        <item>
          <title>Widget Prime</title>
          <link>https://example.com/products/widget-prime</link>
        </item>
        <item>
          <title>Widget Pro</title>
          <link>https://example.com/products/widget-pro</link>
        </item>
      </channel>
    </rss>
    """

    rows = extract_records(
        rss,
        "https://example.com/feed.xml",
        "ecommerce_listing",
        max_records=10,
        content_type="application/rss+xml; charset=utf-8",
    )

    assert len(rows) == 2
    assert rows[0]["_source"] == "xml_sitemap"
    assert rows[0]["url"] == "https://example.com/products/widget-prime"
    assert rows[1]["title"] == "widget pro"


@pytest.mark.regression
def test_extract_records_emits_atom_listing_records_from_link_href() -> None:
    atom = """
    <?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <title>Widget Prime</title>
        <link href="https://example.com/products/widget-prime" />
      </entry>
      <entry>
        <title>Widget Pro</title>
        <link href="https://example.com/products/widget-pro" />
      </entry>
    </feed>
    """

    rows = extract_records(
        atom,
        "https://example.com/atom.xml",
        "ecommerce_listing",
        max_records=10,
        content_type="application/atom+xml; charset=utf-8",
    )

    assert len(rows) == 2
    assert rows[0]["_source"] == "xml_sitemap"
    assert rows[0]["url"] == "https://example.com/products/widget-prime"
    assert rows[1]["title"] == "widget pro"


@pytest.mark.regression
def test_extract_detail_keeps_dom_stage_for_high_scoring_js_state_when_long_text_missing() -> (
    None
):
    html = """
    <html>
      <body>
        <script type="application/json" id="__NEXT_DATA__">
        {
          "props": {
            "pageProps": {
              "product": {
                "title": "Trail Runner",
                "vendor": "Acme Outdoors",
                "handle": "trail-runner",
                "price": "119.00",
                "availability": "In Stock",
                "images": [{"src": "https://cdn.example.com/trail.jpg"}],
                "variants": [{"id": "v1", "sku": "TRAIL-1", "available": true}]
              }
            }
          }
        }
        </script>
        <h2>Description</h2>
        <div>Stable all-terrain shoe for long trail runs.</div>
        <h2>Specifications</h2>
        <div>Rubber outsole, reinforced toe cap.</div>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/trail-runner",
        "ecommerce_detail",
        max_records=5,
        requested_fields=["description", "specifications"],
        extraction_runtime_snapshot={
            "selector_self_heal": {"enabled": True, "min_confidence": 0.55}
        },
    )

    assert len(rows) == 1
    record = rows[0]
    assert "Stable all-terrain shoe" in record["description"]
    assert "Rubber outsole" in record["specifications"]
    assert record["_extraction_tiers"]["current"] == "dom"
    assert record["_extraction_tiers"]["early_exit"] is None


@pytest.mark.regression
def test_extract_detail_uses_requested_custom_fields_from_network_payloads() -> None:
    html = """
    <html>
      <head>
        <meta property="og:title" content="Whirlpool">
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Whirlpool",
          "brand": {"name": "Whirlpool"},
          "offers": {
            "price": "16690",
            "priceCurrency": "INR",
            "availability": "https://schema.org/InStock"
          }
        }
        </script>
      </head>
      <body>
        <h1>Whirlpool</h1>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://india.whirlpool.in/vitamagic-pro-192l-3-star-radiant-steel-auto-defrost-single-door-refrigerator-radiant-steel-y/p?sc=1",
        "ecommerce_detail",
        max_records=5,
        requested_fields=["capacity", "energy_rating"],
        network_payloads=[
            {
                "url": "https://india.whirlpool.in/productBySKU/1506",
                "endpoint_type": "generic_json",
                "body": {
                    "ProductName": "Vitamagic Pro 192L 3 Star Radiant Steel Auto Defrost Single Door Refrigerator - Radiant Steel-Y",
                    "BrandName": "Whirlpool",
                    "DetailUrl": "/vitamagic-pro-192l-3-star-radiant-steel-auto-defrost-single-door-refrigerator-radiant-steel-y/p",
                    "ProductSpecifications": [
                        {"FieldName": "Capacity(L)", "FieldValues": ["192 L"]},
                        {"FieldName": "Energy Rating", "FieldValues": ["3 Star"]},
                    ],
                },
            }
        ],
    )

    assert len(rows) == 1
    record = rows[0]
    assert (
        record["title"]
        == "Vitamagic Pro 192L 3 Star Radiant Steel Auto Defrost Single Door Refrigerator - Radiant Steel-Y"
    )
    assert record["capacity"] == "192 L"
    assert record["energy_rating"] == "3 Star"
    assert record["_field_sources"]["title"][0] == "network_payload"


@pytest.mark.regression
def test_extract_detail_keeps_long_product_titles_that_include_star_ratings() -> None:
    html = """
    <html>
      <head>
        <meta property="og:title" content="Whirlpool">
      </head>
      <body>
        <h1>Whirlpool</h1>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://india.whirlpool.in/example/p?sc=1",
        "ecommerce_detail",
        max_records=1,
        requested_fields=["energy_rating"],
        network_payloads=[
            {
                "url": "https://india.whirlpool.in/productBySKU/1506",
                "endpoint_type": "generic_json",
                "body": {
                    "ProductName": "Vitamagic Pro 192L 3 Star Radiant Steel Refrigerator",
                    "BrandName": "Whirlpool",
                    "DetailUrl": "/example/p",
                    "ProductSpecifications": [
                        {"FieldName": "Energy Rating", "FieldValues": ["3 Star"]},
                    ],
                },
            }
        ],
    )

    assert len(rows) == 1
    assert rows[0]["title"] == "Vitamagic Pro 192L 3 Star Radiant Steel Refrigerator"


@pytest.mark.regression
def test_extract_detail_allows_safe_early_exit_before_dom_when_pre_dom_record_is_complete() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Widget Prime",
          "description": "A deterministic widget with enough detail to avoid DOM fallback.",
          "brand": {"name": "Acme"},
          "image": "https://example.com/images/widget-1.jpg",
          "offers": {
            "price": "19.99",
            "priceCurrency": "USD",
            "availability": "https://schema.org/InStock"
          }
        }
        </script>
      </head>
      <body>
        <div class="noise">No useful DOM selectors required</div>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/widget-prime",
        "ecommerce_detail",
        max_records=5,
        extraction_runtime_snapshot={
            "selector_self_heal": {"enabled": True, "min_confidence": 0.55}
        },
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["_extraction_tiers"]["early_exit"] == "js_state"
    assert record["_extraction_tiers"]["current"] == "js_state"


@pytest.mark.regression
def test_extract_detail_records_preserves_selector_trace_for_selected_rule() -> None:
    html = """
    <html>
      <body>
        <div class="selector-title">Selector Widget</div>
        <div class="selector-price">$19.99</div>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/selector-widget",
        "ecommerce_detail",
        max_records=1,
        selector_rules=[
            {
                "id": 11,
                "field_name": "title",
                "css_selector": ".selector-title",
                "source": "domain_memory",
                "source_run_id": 55,
            },
            {
                "id": 12,
                "field_name": "price",
                "css_selector": ".selector-price",
                "source": "domain_memory",
                "source_run_id": 55,
            },
        ],
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["_selector_traces"]["title"] == {
        "selector_kind": "css_selector",
        "selector_value": ".selector-title",
        "selector_source": "domain_memory",
        "selector_record_id": 11,
        "source_run_id": 55,
        "sample_value": "Selector Widget",
        "page_url": "https://example.com/products/selector-widget",
    }
    assert record["_selector_traces"]["price"] == {
        "selector_kind": "css_selector",
        "selector_value": ".selector-price",
        "selector_source": "domain_memory",
        "selector_record_id": 12,
        "source_run_id": 55,
        "sample_value": "$19.99",
        "page_url": "https://example.com/products/selector-widget",
    }


@pytest.mark.regression
def test_extract_listing_records_preserves_selector_trace_for_selected_rule() -> None:
    html = """
    <html>
      <body>
        <article class="card">
          <a href="/products/selector-widget">Selector Widget</a>
          <div class="selector-price">$19.99</div>
        </article>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/collections/widgets",
        "ecommerce_listing",
        max_records=5,
        selector_rules=[
            {
                "id": 21,
                "field_name": "price",
                "css_selector": ".selector-price",
                "source": "domain_memory",
                "source_run_id": 66,
            }
        ],
    )

    assert len(rows) == 1
    assert rows[0]["_selector_traces"]["price"] == {
        "selector_kind": "css_selector",
        "selector_value": ".selector-price",
        "selector_source": "domain_memory",
        "selector_record_id": 21,
        "source_run_id": 66,
        "sample_value": "$19.99",
        "page_url": "https://example.com/collections/widgets",
    }


@pytest.mark.regression
def test_extract_detail_rejects_non_variant_options_object_from_structured_payload() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/json">
        {
          "@type": "Product",
          "name": "Duracell Ultra AA Alkaline Batteries (Pack of 8)",
          "sku": "OFF.MIS.25278554",
          "brand": "Duracell",
          "material": "Alkaline",
          "options": {
            "renderableComponents": [
              {"url": "/user/account", "title": "My Profile"},
              {"url": "/user/orders", "title": "My Orders"},
              {"title": "Logout", "action": {"type": "LOGOUT"}}
            ]
          }
        }
        </script>
      </head>
      <body>
        <h1>Duracell Ultra AA Alkaline Batteries (Pack of 8)</h1>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.industrybuying.com/battery-cell-duracell-OFF.MIS.25278554",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["title"] == "Duracell Ultra AA Alkaline Batteries (Pack of 8)"
    assert record["sku"] == "OFF.MIS.25278554"
    assert (
        record["url"]
        == "https://www.industrybuying.com/battery-cell-duracell-OFF.MIS.25278554"
    )
    assert "availability" not in record


@pytest.mark.regression
def test_extract_detail_keeps_valid_variant_axes_from_structured_options_alias() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/json">
        {
          "@type": "Product",
          "name": "MuscleBlaze Biozyme Performance Whey",
          "options": {
            "weight": ["4.4 Lb", "0.4 Lb"],
            "flavour": ["Rich Chocolate", "Blue Tokai Coffee"]
          }
        }
        </script>
      </head>
      <body>
        <h1>MuscleBlaze Biozyme Performance Whey</h1>
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


@pytest.mark.regression
def test_normalize_variant_record_drops_scalar_legacy_variant_axes() -> None:
    record = {
        "variant_axes": {
            "size": ["M"],
            "stock": 5,
        }
    }

    normalize_variant_record(record)

    assert "size" not in record
    assert "stock" not in record
    assert "variant_axes" not in record


@pytest.mark.regression
def test_dom_variant_axis_detection_ignores_unknown_option_value_axes() -> None:
    existing = [
        {
            "sku": "sku-s",
            "size": "S",
            "option_values": {"size": "S", "material": "Cotton"},
        }
    ]
    dom_rows = [{"option_values": {"material": "Linen"}}]

    assert dom_variants_add_missing_existing_axis(existing, dom_rows) is False


@pytest.mark.regression
def test_variant_sanitizer_rejects_unrelated_amazon_cross_asin_url() -> None:
    variant = {
        "url": "https://www.amazon.com/Other-Product/dp/B000OTHER1",
        "size": "M",
    }

    assert (
        sanitize_variant_row(
            variant,
            identity_url="https://www.amazon.com/Parent-Product/dp/B000PARENT1",
            title_hint="Parent Product",
        )
        is False
    )


@pytest.mark.regression
def test_variant_numeric_noise_keeps_decimal_size() -> None:
    variant = {"option_values": {"size": "3.5"}}

    assert sanitize_variant_row(variant, identity_url="https://example.com/p/shoe")
    assert variant["option_values"] == {"size": "3.5"}


@pytest.mark.regression
def test_normalize_variant_record_strips_legacy_option_summaries_and_selected_variant() -> (
    None
):
    record = {
        "option1_name": "Flavour",
        "option1_values": "Rich Chocolate, Blue Tokai Coffee",
        "option2_name": "pr type",
        "option2_values": "OptOut, RemoveMe, MyInfo",
        "variant_axes": {
            "flavor": ["Rich Chocolate", "Blue Tokai Coffee"],
            "type": ["OptOut", "RemoveMe", "MyInfo"],
        },
        "variants": [
            {
                "option_values": {
                    "flavor": "Rich Chocolate",
                    "type": "OptOut",
                }
            }
        ],
        "selected_variant": {
            "option_values": {
                "flavor": "Rich Chocolate",
                "type": "OptOut",
            }
        },
    }

    normalize_variant_record(record)

    # Legacy scaffolding fields are always stripped; only the canonical
    # ``variants`` list (carrying public axes like ``flavor``)
    # may survive. The option-summary / selected_variant / variant_axes
    # dicts must not leak into the public record.
    assert "selected_variant" not in record
    assert "variant_axes" not in record
    assert "option1_name" not in record
    assert "option2_name" not in record
    assert "option1_values" not in record
    assert "option2_values" not in record
    assert record["variants"] == [{"flavor": "Rich Chocolate"}]


@pytest.mark.regression
def test_normalize_variant_record_drops_parent_shared_variant_prices_and_axes() -> None:
    record = {
        "price": "115.00",
        "currency": "USD",
        "color": "Blue",
        "variants": [
            {"size": "S", "color": "Blue", "price": "115.0", "currency": "USD"},
            {"size": "M", "color": "Blue", "price": "115", "currency": "USD"},
        ],
    }

    normalize_variant_record(record)

    assert record["variants"] == [{"size": "S"}, {"size": "M"}]


@pytest.mark.regression
def test_map_js_state_variant_axes_coerces_dict_values_to_labels() -> None:
    mapped = map_js_state_to_fields(
        {
            "__NEXT_DATA__": {
                "props": {
                    "pageProps": {
                        "product": {
                            "name": "Performance Socks",
                            "handle": "performance-socks",
                            "variants": [
                                {
                                    "id": "v1",
                                    "sku": "SOCK-BLK",
                                    "price": "1500",
                                    "color": {
                                        "id": "black-onyx",
                                        "title": "black onyx",
                                    },
                                }
                            ],
                        }
                    }
                }
            }
        },
        surface="ecommerce_detail",
        page_url="https://example.com/products/performance-socks",
    )

    assert mapped["variants"][0]["color"] == "black onyx"
    assert not mapped["variants"][0]["color"].startswith("{")


@pytest.mark.regression
def test_normalize_variant_record_coerces_dict_like_axis_strings_to_labels() -> None:
    record = {
        "variants": [
            {
                "sku": "SOCK-BLK",
                "color": "{'id': 'black-onyx', 'title': 'black onyx'}",
            }
        ]
    }

    normalize_variant_record(record)

    assert record["variants"] == [{"sku": "SOCK-BLK", "color": "black onyx"}]


@pytest.mark.regression
def test_extract_dom_variants_rejects_payment_button_text_as_size() -> None:
    rows = extract_records(
        """
        <html>
          <head>
            <script type="application/ld+json">
            {"@context":"https://schema.org","@type":"Product","name":"Cotton Tee",
             "offers":{"@type":"Offer","price":"14.90","priceCurrency":"USD"}}
            </script>
          </head>
          <body>
            <main>
              <h1>Cotton Tee</h1>
              <select name="Size">
                <option>S</option>
                <option>Apple Pay</option>
                <option>M</option>
              </select>
            </main>
          </body>
        </html>
        """,
        "https://example.com/products/cotton-tee",
        "ecommerce_detail",
        max_records=5,
    )

    assert rows[0]["variants"] == [{"size": "S"}, {"size": "M"}]


@pytest.mark.regression
def test_variant_axis_headers_do_not_pollute_size_or_available_sizes() -> None:
    record = {
        "size": "100",
        "available_sizes": ["Sizes", "Sizes: Standard", "XS", "M"],
        "variant_axes": {
            "size": ["Sizes", "Sizes: Standard", "Sizes: Tall", "XS", "M"],
        },
        "variants": [
            {"size": "Sizes", "option_values": {"size": "Sizes"}},
            {"size": "Sizes: Standard", "option_values": {"size": "Sizes: Standard"}},
            {"size": "XS", "option_values": {"size": "XS"}},
            {"size": "M", "option_values": {"size": "M"}},
        ],
        "selected_variant": {
            "size": "Sizes: Standard",
            "option_values": {"size": "Sizes: Standard"},
        },
    }

    normalize_variant_record(record)

    assert record["size"] == "100"
    assert record["variant_count"] == 2
    assert [variant["size"] for variant in record["variants"]] == ["XS", "M"]
    assert "available_sizes" not in record
    assert "selected_variant" not in record


@pytest.mark.regression
def test_normalize_variant_record_infers_size_from_variant_titles() -> None:
    record = {
        "title": "Chicken Recipe Dry Dog Food",
        "original_price": "64.99",
        "variants": [
            {
                "title": "Chicken Recipe Dry Dog Food, 4-lb bag",
                "url": "https://www.chewy.com/acme-food/dp/123?size=4-lb",
                "price": "18.99",
            },
            {
                "title": "Chicken Recipe Dry Dog Food, 12-lb bag",
                "url": "https://www.chewy.com/acme-food/dp/123?size=12-lb",
                "price": "42.99",
            },
        ],
    }

    normalize_variant_record(record)

    assert "original_price" not in record["variants"][0]
    assert "original_price" not in record["variants"][1]

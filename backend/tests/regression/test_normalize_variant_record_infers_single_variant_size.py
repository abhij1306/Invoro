from __future__ import annotations

from .test_detail_extractor_structured_sources import backfill_detail_price_from_html, extract_records, normalize_variant_record, pytest, read_optional_artifact_text  # fmt: skip

@pytest.mark.regression
def test_normalize_variant_record_infers_single_variant_size_from_title_tokens() -> (
    None
):
    record = {
        "title": "Arizona Sandal - EU 42",
        "url": "https://www.birkenstock.com/us/arizona-birko-flor/arizona-core-birkoflor-0-eva-u_1.html",
        "variants": [
            {
                "url": "https://www.birkenstock.com/us/arizona-birko-flor/arizona-core-birkoflor-0-eva-u_1.html",
            }
        ],
    }

    normalize_variant_record(record)

    assert record["variants"] == [
        {
            "url": "https://www.birkenstock.com/us/arizona-birko-flor/arizona-core-birkoflor-0-eva-u_1.html",
            "size": "EU 42",
        }
    ]

@pytest.mark.regression
def test_extract_ecommerce_detail_reads_scalar_size_from_two_span_label_value_row() -> (
    None
):
    html = """
    <html>
      <body>
        <main>
          <h1>Colorful Eyeshadow</h1>
          <div><span>Color</span><span>209 Mocha Latte - soft mocha brown matte</span></div>
          <div><span>Size</span><span>0.035 oz / 0.99 g</span></div>
          <div data-testid="price">$8.00</div>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.sephora.com/product/colorful-eyeshadow-P515026",
        "ecommerce_detail",
        max_records=1,
        requested_fields=["size", "title", "price", "color"],
    )

    assert rows
    assert rows[0]["title"] == "Colorful Eyeshadow"
    assert rows[0]["price"] == "8.00"
    assert rows[0]["color"] == "209 Mocha Latte - soft mocha brown matte"
    assert rows[0]["size"] == "0.035 oz / 0.99 g"

@pytest.mark.regression
def test_extract_detail_ignores_nordstrom_sold_out_gift_option_price_from_artifact() -> (
    None
):
    html = read_optional_artifact_text("artifacts/runs/1/pages/9192dbfda15a2ac3.html")
    rows = extract_records(
        html,
        "https://www.nordstrom.com/s/nike-air-force-1-07-basketball-sneaker-men/7507996",
        "ecommerce_detail",
        max_records=1,
        requested_fields=["variants", "price", "currency", "availability", "image_url"],
    )

    record = rows[0]
    assert record["title"] == "Air Force 1 '07 Basketball Sneaker"
    assert record["availability"] == "out_of_stock"
    assert "price" not in record
    assert "currency" not in record
    assert "variant_count" not in record

@pytest.mark.regression
def test_out_of_stock_record_allows_dom_variant_price_repair() -> None:
    record = {
        "url": "https://example.com/products/widget",
        "availability": "out_of_stock",
        "variants": [{"sku": "WIDGET-S"}],
        "_field_sources": {"availability": ["json_ld"]},
    }

    backfill_detail_price_from_html(
        record,
        html="""
        <html>
          <head><meta property="product:price:currency" content="USD"></head>
          <body><main><div data-testid="price">$19.99</div></main></body>
        </html>
        """,
    )

    assert "price" not in record
    assert record["variants"][0]["price"] == "19.99"
    assert record["variants"][0]["currency"] == "USD"

@pytest.mark.regression
def test_extract_detail_recovers_end_option_variants_from_artifact() -> None:
    html = read_optional_artifact_text("artifacts/runs/1/pages/3b8d6be40db29760.html")
    rows = extract_records(
        html,
        (
            "https://www.endclothing.com/us/47-ny-yankees-clean-up-cap-b-rgw17gws-vn.html"
            "?queryID=92cd67a81343c72b1e7ea4257417a975"
        ),
        "ecommerce_detail",
        max_records=1,
        requested_fields=["variants", "price", "currency", "availability"],
    )

    record = rows[0]
    assert record["variant_count"] == 1
    assert record["variants"][0]["size"] == "One Size"
    assert record["availability"] == "in_stock"

@pytest.mark.regression
def test_extract_detail_recovers_asos_stock_price_and_size_variants_from_artifact() -> (
    None
):
    html = read_optional_artifact_text("artifacts/runs/1/pages/db1fce245d2380a5.html")
    rows = extract_records(
        html,
        (
            "https://www.asos.com/us/asos-curve/"
            "asos-design-curve-lightweight-pull-on-barrel-pants-in-darkwash/"
            "prd/210397084#colourWayId-210397088"
        ),
        "ecommerce_detail",
        max_records=1,
        requested_fields=["variants", "price", "currency", "availability"],
    )

    record = rows[0]
    assert record["price"] == "59.99"
    assert record["currency"] == "USD"
    assert record["variant_count"] == 6
    assert {variant.get("size") for variant in record["variants"]} >= {
        "US 14",
        "US 24",
    }
    assert any(
        variant.get("availability") == "in_stock" for variant in record["variants"]
    )

@pytest.mark.regression
def test_extract_detail_recovers_ssense_next_f_size_variants_from_artifact() -> None:
    html = read_optional_artifact_text("artifacts/runs/1/pages/99f37e207742af7a.html")
    rows = extract_records(
        html,
        "https://www.ssense.com/en-us/men/product/willy-chavarria/brown-ruff-rider-leather-jacket/19072301",
        "ecommerce_detail",
        max_records=1,
        requested_fields=["variants", "price", "currency", "availability"],
    )

    record = rows[0]
    assert record["variant_count"] == 4
    assert {variant.get("size") for variant in record["variants"]} == {
        "S",
        "M",
        "L",
        "XL",
    }
    assert all(
        variant.get("availability") == "out_of_stock" for variant in record["variants"]
    )

@pytest.mark.regression
def test_extract_detail_recovers_carhartt_ng_state_variant_matrix_rows_from_artifact() -> (
    None
):
    html = read_optional_artifact_text("artifacts/runs/11/pages/9d986b49e5c2fb5d.html")
    rows = extract_records(
        html,
        "https://www.carhartt.com/en-eu/p/irvine-relaxed-truck-t-shirt/107455",
        "ecommerce_detail",
        max_records=1,
        requested_fields=["variants", "price", "currency", "availability"],
    )

    record = rows[0]
    assert record["price"] == "32.99"
    assert record["currency"] == "EUR"
    assert record["variant_count"] >= 5
    assert {variant.get("size") for variant in record["variants"]} >= {
        "S",
        "M",
        "L",
        "XL",
        "2XL",
    }
    assert all(
        variant.get("sku")
        and isinstance(variant.get("stock_quantity"), int)
        and variant.get("stock_quantity") > 0
        and variant.get("length") == "REG"
        for variant in record["variants"]
    )

@pytest.mark.regression
def test_extract_detail_recovers_llbean_dom_size_variants_from_artifact() -> None:
    html = read_optional_artifact_text("artifacts/runs/13/pages/0e49fd0d4e316b84.html")
    rows = extract_records(
        html,
        "https://global.llbean.com/llb/shop/1000010103.html?cgid=20010166&page=Performance-Pima-Short-Sleeve-Polo-Mens-Tall&showReviews=true",
        "ecommerce_detail",
        max_records=1,
        requested_fields=["variants", "price", "currency"],
    )

    record = rows[0]
    assert record["price"] == "7400.00"
    assert record["currency"] == "INR"
    assert record["variant_count"] == 4
    assert {variant.get("size") for variant in record["variants"]} == {
        "Small",
        "X-Large",
        "XX-Large",
        "XXX-Large",
    }
    assert all(
        "dwvar_1000010103_size=" in str(variant.get("url") or "")
        for variant in record["variants"]
    )

@pytest.mark.regression
def test_extract_detail_recovers_patagonia_boldmetrics_variants_from_artifact() -> None:
    html = read_optional_artifact_text("artifacts/runs/1/pages/72d532d622b8051e.html")
    rows = extract_records(
        html,
        "https://www.patagonia.com/product/mens-nano-puff-insulated-jacket/84213.html",
        "ecommerce_detail",
        max_records=1,
        requested_fields=["variants", "price", "currency", "availability"],
    )

    record = rows[0]
    assert record["price"] == "229.00"
    assert record["availability"] == "in_stock"
    assert record["variant_count"] == 7
    assert {variant.get("size") for variant in record["variants"]} >= {"XS", "3XL"}

@pytest.mark.regression
def test_extract_detail_recovers_bh_primary_image_from_artifact() -> None:
    html = read_optional_artifact_text("artifacts/runs/1/pages/6c0655481681f545.html")
    rows = extract_records(
        html,
        "https://www.bhphotovideo.com/c/product/1882297-REG/cozyla_cd_8v543f0_white_us_32_4k_calendar_gen2_white.html",
        "ecommerce_detail",
        max_records=1,
        requested_fields=["image_url", "title"],
    )

    assert rows[0]["image_url"].endswith(
        "cozyla_cd_8v543f0_white_us_32_4k_calendar_gen2_white_1882297.jpg"
    )

@pytest.mark.regression
def test_extract_detail_rejects_amazon_adding_to_cart_title_from_artifact() -> None:
    html = read_optional_artifact_text("artifacts/runs/1/pages/d244c66cea62f06d.html")
    rows = extract_records(
        html,
        "https://www.amazon.com/Sparkling-Prebiotic-Beverage-Vinegar-Seltzer/dp/B0F5Y3X8PP/?th=1",
        "ecommerce_detail",
        max_records=1,
        requested_fields=["title", "brand", "image_url", "price"],
    )

    assert rows[0]["title"] != "Adding to Cart..."
    assert "Prebiotic" in rows[0]["title"]

from __future__ import annotations

from .test_crawl_engine import backfill_detail_price_from_html, detail_url_is_utility, extract_records, pytest, select_variant  # fmt: skip

@pytest.mark.regression
def test_listing_raw_json_honors_max_records() -> None:
    html = (
        "["
        + ",".join(
            f'{{"title":"Product {index}","url":"https://example.com/p/{index}","price":"${index}.00"}}'
            for index in range(1, 6)
        )
        + "]"
    )

    rows = extract_records(
        html,
        "https://example.com/collections/all",
        "ecommerce_listing",
        max_records=3,
        content_type="application/json",
    )

    assert [row["title"] for row in rows] == [
        "Product 1",
        "Product 2",
        "Product 3",
    ]

@pytest.mark.regression
def test_detail_product_url_with_support_slug_is_not_utility() -> None:
    assert (
        detail_url_is_utility(
            "https://example.com/products/123-hormone-healthy-eats-support?source=search"
        )
        is False
    )

@pytest.mark.regression
def test_detail_price_backfill_replaces_visible_outlier_price() -> None:
    record = {
        "url": "https://www.thomann.co.uk/akg_k702.htm",
        "price": "3.95",
        "currency": "GBP",
        "_field_sources": {"price": ["dom_selector"]},
    }
    html = """
    <html>
      <head>
        <meta itemprop="priceCurrency" content="GBP">
        <meta itemprop="price" content="154">
      </head>
      <body>
        <main>
          <h1>AKG K-702</h1>
          <div class="shipping-price">Shipping GBP 3.95</div>
          <div class="product-price">GBP 154</div>
        </main>
      </body>
    </html>
    """

    backfill_detail_price_from_html(record, html=html)

    assert record["price"] == "154"
    assert "dom_text" in record["_field_sources"]["price"]

@pytest.mark.regression
def test_detail_price_backfill_replaces_visible_decimal_shift_outlier_price() -> None:
    record = {
        "url": "https://www.belk.com/p/scarlett-medium-satchel/1.html",
        "price": "2995.00",
        "currency": "USD",
        "_field_sources": {"price": ["json_ld"], "currency": ["json_ld"]},
    }
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {"@type":"Product","offers":{"@type":"Offer","price":"2995","priceCurrency":"USD"}}
        </script>
      </head>
      <body>
        <main>
          <h1>Scarlett Medium Satchel with Charm</h1>
          <div data-testid="price">$299.50</div>
        </main>
      </body>
    </html>
    """

    backfill_detail_price_from_html(record, html=html)

    assert record["price"] == "299.50"
    assert "dom_text" in record["_field_sources"]["price"]

@pytest.mark.regression
def test_detail_price_backfill_uses_visible_local_price_when_jsonld_currency_conflicts() -> (
    None
):
    record = {
        "url": "https://www.glossier.com/en-in/products/balm-dotcom",
        "price": "16.00",
        "currency": "INR",
        "_field_sources": {"price": ["js_state"]},
    }
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {"@type":"Product","offers":{"@type":"Offer","price":"16","priceCurrency":"USD"}}
        </script>
      </head>
      <body><main><div class="product-price">₹1,800</div></main></body>
    </html>
    """

    backfill_detail_price_from_html(record, html=html)

    assert record["price"] == "1800"
    assert record["currency"] == "INR"

@pytest.mark.regression
def test_detail_price_backfill_reads_local_price_from_add_to_bag_button() -> None:
    record = {
        "url": "https://www.glossier.com/en-in/products/balm-dotcom",
        "price": "16.00",
        "currency": "INR",
        "original_price": "5500.00",
        "_field_sources": {"price": ["js_state"], "original_price": ["js_state"]},
    }
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {"@type":"Product","offers":{"@type":"Offer","price":"16","priceCurrency":"USD"}}
        </script>
      </head>
      <body>
        <main>
          <button class="add-to-bag"><span>Add to bag</span><span>Rs. 1,900</span></button>
        </main>
      </body>
    </html>
    """

    backfill_detail_price_from_html(record, html=html)

    assert record["price"] == "1900"
    assert record["currency"] == "INR"
    assert "original_price" not in record

@pytest.mark.regression
def test_detail_price_backfill_drops_unverified_localized_state_price() -> None:
    record = {
        "url": "https://www.glossier.com/en-in/products/balm-dotcom",
        "price": "16.00",
        "currency": "INR",
        "original_price": "5500.00",
        "variants": [{"price": "16.00", "currency": "INR", "flavor": "Original"}],
        "_field_sources": {"price": ["js_state"], "original_price": ["js_state"]},
    }
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {"@type":"Product","offers":{"@type":"Offer","price":"16","priceCurrency":"USD"}}
        </script>
      </head>
      <body><main><h1>Balm Dotcom</h1></main></body>
    </html>
    """

    backfill_detail_price_from_html(record, html=html)

    assert "price" not in record
    assert "currency" not in record
    assert "original_price" not in record
    assert "price" not in record["variants"][0]
    assert "currency" not in record["variants"][0]

@pytest.mark.regression
def test_detail_price_backfill_keeps_existing_parent_price_for_variants_when_host_currency_conflicts() -> (
    None
):
    record = {
        "url": "https://www.firstcry.com/p/balm-dotcom/12345/product-detail",
        "price": "1800",
        "currency": "INR",
        "variants": [{"size": "One Size"}],
        "_field_sources": {"price": ["js_state"]},
    }
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {"@type":"Product","offers":{"@type":"Offer","price":"16","priceCurrency":"USD"}}
        </script>
      </head>
      <body><main><h1>Balm Dotcom</h1></main></body>
    </html>
    """

    backfill_detail_price_from_html(record, html=html)

    assert record["price"] == "1800"
    assert record["variants"][0]["price"] == "1800"
    assert record["variants"][0]["currency"] == "INR"

@pytest.mark.regression
def test_detail_price_backfill_reads_data_test_id_price_display() -> None:
    record = {
        "url": "https://www.wayfair.com/furniture/pdp/widget.html",
        "description": "A" * 200,
        "image_url": "https://assets.example.com/widget.jpg",
        "_field_sources": {},
    }
    html = """
    <html>
      <body>
        <main>
          <h1>Widget</h1>
          <span data-test-id="PriceDisplay" data-name-id="PriceDisplay">$850.00</span>
          <s data-test-id="PriceDisplay">$930.00</s>
        </main>
      </body>
    </html>
    """

    backfill_detail_price_from_html(record, html=html)

    assert record["price"] == "850.00"
    assert record["original_price"] == "930.00"
    assert "dom_text" in record["_field_sources"]["price"]

@pytest.mark.regression
def test_detail_price_backfill_skips_dom_price_when_product_is_out_of_stock() -> None:
    record = {
        "url": "https://www.nordstrom.com/s/nike-air-force-1-07-basketball-sneaker-men/7507996",
        "availability": "out_of_stock",
        "_field_sources": {"availability": ["js_state"]},
    }
    html = """
    <html>
      <body>
        <main>
          <h1>Air Force 1 '07 Basketball Sneaker</h1>
          <div class="shipping-price">$5.00 pickup fee</div>
          <div data-testid="price">$5.00</div>
        </main>
      </body>
    </html>
    """

    backfill_detail_price_from_html(record, html=html)

    assert "price" not in record
    assert "currency" not in record
    assert "price" not in record.get("_field_sources", {})

@pytest.mark.regression
def test_detail_price_backfill_keeps_original_price_when_out_of_stock_price_blocked() -> (
    None
):
    record = {
        "url": "https://example.com/products/widget",
        "availability": "out_of_stock",
        "_field_sources": {"availability": ["json_ld"]},
    }
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {"@type":"Product","offers":{"@type":"Offer","highPrice":"39.99","priceCurrency":"USD"}}
        </script>
      </head>
      <body><main><h1>Widget</h1></main></body>
    </html>
    """

    backfill_detail_price_from_html(record, html=html)

    assert "price" not in record
    assert record["original_price"] == "39.99"
    assert record["currency"] == "USD"
    assert record["_field_sources"]["original_price"] == ["json_ld"]

@pytest.mark.regression
def test_select_variant_falls_back_to_partial_axis_match() -> None:
    variants = [
        {"size": "M", "availability": "out_of_stock"},
        {"size": "M", "availability": "in_stock"},
        {"size": "L", "availability": "in_stock"},
    ]

    selected = select_variant(
        variants,
        page_url="https://example.com/products/widget?size=M&color=Blue",
    )

    assert selected == variants[1]

@pytest.mark.regression
def test_select_variant_prefers_highest_ranked_partial_axis_match() -> None:
    variants = [
        {"size": "M", "color": "Blue", "availability": "out_of_stock"},
        {"size": "M", "color": "Green", "availability": "in_stock"},
        {"size": "S", "color": "Blue", "availability": "in_stock"},
    ]

    selected = select_variant(
        variants,
        page_url="https://example.com/products/widget?size=M&color=Blue&material=Cotton",
    )

    assert selected == variants[0]

@pytest.mark.regression
def test_extract_detail_keeps_encoded_cdn_image_url() -> None:
    image_url = (
        "https://i.example-cdn.com/rs:fit/g:sm/q:90/h:600/w:600/"
        "czM6Ly9pbWFnZXM/LmpwZWc.jpeg"
    )
    rows = extract_records(
        f"""
        <html>
          <head>
            <meta property="og:title" content="Never Gonna Give You Up">
            <meta property="og:image" content="{image_url}">
            <meta property="og:url" content="https://www.discogs.com/release/249504">
            <script type="application/ld+json">{{
              "@context": "https://schema.org",
              "@type": "Product",
              "name": "Never Gonna Give You Up",
              "image": "{image_url}",
              "url": "https://www.discogs.com/release/249504",
              "offers": {{"@type": "Offer", "price": "0.68", "priceCurrency": "USD"}}
            }}</script>
          </head>
          <body><h1>Never Gonna Give You Up</h1></body>
        </html>
        """,
        "https://www.discogs.com/release/249504",
        "ecommerce_detail",
        max_records=5,
        requested_page_url="https://www.discogs.com/release/249504",
    )

    assert rows[0]["image_url"] == image_url

@pytest.mark.regression
def test_extract_records_recovers_flattened_listing_cards_from_visual_artifacts() -> (
    None
):
    html = """
    <html>
      <body>
        <div class="grid-shell">
          <a href="/products/widget-prime"></a>
          <img src="/images/widget-prime.jpg" alt="Widget Prime">
          <h2>Widget Prime</h2>
          <div>$19.99</div>
        </div>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/collections/widgets",
        "ecommerce_listing",
        max_records=10,
        artifacts={
            "listing_visual_elements": [
                {
                    "tag": "a",
                    "href": "/products/widget-prime",
                    "x": 20,
                    "y": 40,
                    "width": 180,
                    "height": 180,
                    "text": "",
                },
                {
                    "tag": "img",
                    "src": "/images/widget-prime.jpg",
                    "alt": "Widget Prime",
                    "x": 20,
                    "y": 40,
                    "width": 180,
                    "height": 140,
                    "text": "",
                },
                {
                    "tag": "h2",
                    "text": "Widget Prime",
                    "x": 24,
                    "y": 190,
                    "width": 170,
                    "height": 24,
                },
                {
                    "tag": "div",
                    "text": "$19.99",
                    "x": 24,
                    "y": 220,
                    "width": 80,
                    "height": 24,
                },
            ]
        },
    )

    assert rows == [
        {
            "source_url": "https://example.com/collections/widgets",
            "_source": "visual_listing",
            "title": "Widget Prime",
            "price": "19.99",
            "currency": "USD",
            "image_url": "https://example.com/images/widget-prime.jpg",
            "url": "https://example.com/products/widget-prime",
        }
    ]

@pytest.mark.regression
def test_extract_records_visual_listing_backfills_brand_from_brand_node_and_url() -> (
    None
):
    rows = extract_records(
        "<html><body></body></html>",
        "https://www.belk.com/shoes/womens-shoes/sandals/flat/",
        "ecommerce_listing",
        max_records=10,
        artifacts={
            "listing_visual_elements": [
                {
                    "tag": "a",
                    "href": "/p/northside-dogwood-footbed-sandals/290092111811620.html",
                    "x": 20,
                    "y": 40,
                    "width": 180,
                    "height": 180,
                    "text": "",
                },
                {
                    "tag": "h2",
                    "text": "Dogwood Footbed Sandals",
                    "x": 24,
                    "y": 190,
                    "width": 170,
                    "height": 24,
                },
                {
                    "tag": "div",
                    "text": "Northside",
                    "ariaLabel": "brand",
                    "x": 24,
                    "y": 216,
                    "width": 170,
                    "height": 20,
                },
                {
                    "tag": "div",
                    "text": "$24.99",
                    "x": 24,
                    "y": 240,
                    "width": 80,
                    "height": 24,
                },
                {
                    "tag": "a",
                    "href": "/p/dv-dolce-vita-ubar-sandals/2900965UBAR.html",
                    "x": 220,
                    "y": 40,
                    "width": 180,
                    "height": 180,
                    "text": "",
                },
                {
                    "tag": "h2",
                    "text": "Ubar Sandals",
                    "x": 224,
                    "y": 190,
                    "width": 170,
                    "height": 24,
                },
                {
                    "tag": "div",
                    "text": "$20.00",
                    "x": 224,
                    "y": 220,
                    "width": 80,
                    "height": 24,
                },
            ]
        },
    )

    assert rows[0]["brand"] == "Northside"
    assert rows[1]["brand"] == "Dv Dolce Vita"

@pytest.mark.regression
def test_extract_records_visual_listing_rejects_numeric_product_id_brand_prefix() -> (
    None
):
    rows = extract_records(
        "<html><body></body></html>",
        "https://www.desertcart.in/category/fashion/men/accessories",
        "ecommerce_listing",
        max_records=10,
        artifacts={
            "listing_visual_elements": [
                {
                    "tag": "a",
                    "href": "/products/492216804-black-leather-belts-for-men?source=category",
                    "x": 20,
                    "y": 40,
                    "width": 180,
                    "height": 180,
                    "text": "",
                },
                {
                    "tag": "h2",
                    "text": "Black Leather Belts for Men",
                    "x": 24,
                    "y": 190,
                    "width": 170,
                    "height": 24,
                },
                {
                    "tag": "div",
                    "text": "Rs. 2,791",
                    "x": 24,
                    "y": 220,
                    "width": 80,
                    "height": 24,
                },
            ]
        },
    )

    assert rows[0]["title"] == "Black Leather Belts for Men"
    assert "brand" not in rows[0]

@pytest.mark.regression
def test_extract_records_reads_desertcart_style_product_anchor_cards() -> None:
    rows = extract_records(
        """
        <html><body>
          <a class="SearchResultsContainer_cardWrapper__0mkW_"
             href="/products/492216804-black-leather-belts-for-men?source=category">
            <div class="ProductCard_productCardContainer__svsD_">
              <img src="/belt.jpg" alt="Black Leather Belts for Men">
              <h3 class="ProductCoreDetails_title__m_0uZ">Black Leather Belts for Men</h3>
              <span>Rs. 2,791</span>
            </div>
          </a>
        </body></html>
        """,
        "https://www.desertcart.in/category/fashion/men/accessories",
        "ecommerce_listing",
        max_records=10,
    )

    assert rows[0]["title"] == "Black Leather Belts for Men"
    assert rows[0]["url"] == (
        "https://www.desertcart.in/products/"
        "492216804-black-leather-belts-for-men?source=category"
    )
    assert "brand" not in rows[0]

@pytest.mark.regression
def test_extract_records_honors_listing_max_records_above_fragment_default() -> None:
    cards = "\n".join(
        f"""
        <a class="SearchResultsContainer_cardWrapper__0mkW_"
           href="/products/{index}-widget-{index}?source=category">
          <div class="ProductCard_productCardContainer__svsD_">
            <h3 class="ProductCoreDetails_title__m_0uZ">Widget {index}</h3>
            <span>Rs. {1000 + index}</span>
          </div>
        </a>
        """
        for index in range(1, 206)
    )

    rows = extract_records(
        f"<html><body>{cards}</body></html>",
        "https://www.desertcart.in/category/fashion/men/accessories",
        "ecommerce_listing",
        max_records=205,
    )

    assert len(rows) == 205

@pytest.mark.regression
def test_extract_records_visual_listing_orders_top_grid_before_lower_recommendations() -> (
    None
):
    rows = extract_records(
        "<html><body></body></html>",
        "https://www.belk.com/men/mens-clothing/sport-coats-blazers/",
        "ecommerce_listing",
        max_records=2,
        artifacts={
            "listing_visual_elements": [
                {
                    "tag": "img",
                    "href": "/p/crown-ivy-men-s-chambray-sport-coat/3203855BL1962J.html",
                    "src": "/images/sport-coat.jpg",
                    "alt": "Men's Chambray Sport Coat",
                    "x": 907,
                    "y": 582,
                    "width": 349,
                    "height": 499,
                    "score": 30,
                },
                {
                    "tag": "div",
                    "text": "$99.99",
                    "x": 907,
                    "y": 1098,
                    "width": 120,
                    "height": 24,
                    "score": 18,
                },
                {
                    "tag": "img",
                    "href": "/p/izod-advantage-performance-polo-shirt-classic-fit/3203960IZAGB24R.html",
                    "src": "/images/polo.jpg",
                    "alt": "Men's Advantage Performance Polo Shirt Classic Fit",
                    "x": 395,
                    "y": 13129,
                    "width": 160,
                    "height": 228,
                    "score": 4,
                },
                {
                    "tag": "a",
                    "href": "/p/izod-advantage-performance-polo-shirt-classic-fit/3203960IZAGB24R.html",
                    "text": "Quick Add IZOD Men's Advantage Performance Polo Shirt Classic Fit $20.00 after coupon $50.00",
                    "x": 395,
                    "y": 13129,
                    "width": 160,
                    "height": 343,
                    "score": 4,
                },
            ]
        },
    )

    assert rows[0] == {
        "source_url": "https://www.belk.com/men/mens-clothing/sport-coats-blazers/",
        "_source": "visual_listing",
        "title": "Men's Chambray Sport Coat",
        "brand": "Crown Ivy",
        "price": "99.99",
        "currency": "USD",
        "image_url": "https://www.belk.com/images/sport-coat.jpg",
        "url": "https://www.belk.com/p/crown-ivy-men-s-chambray-sport-coat/3203855BL1962J.html",
    }
    assert [row["title"] for row in rows] == [
        "Men's Chambray Sport Coat",
        "Men's Advantage Performance Polo Shirt Classic Fit",
    ]

@pytest.mark.regression
def test_detail_identity_codes_require_exact_match() -> None:
    from app.services.extract.detail.identity.core import detail_identity_codes_match

    assert (
        detail_identity_codes_match(
            {"ABC12345"},
            {"ABC123456"},
        )
        is False
    )
    assert (
        detail_identity_codes_match(
            {"ABC12345"},
            {"ABC12345"},
        )
        is True
    )

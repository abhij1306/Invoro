from __future__ import annotations

from .test_detail_extractor_structured_sources import BeautifulSoup, detail_raw_signals, extract_records, harvest_js_state_objects, pytest, reconcile_parent_price_against_variant_range  # fmt: skip


@pytest.mark.regression
def test_extract_ecommerce_detail_keeps_page_url_when_opengraph_url_is_site_root() -> (
    None
):
    html = """
    <html>
      <head>
        <meta property="og:title" content="Personal Blender">
        <meta property="og:type" content="product">
        <meta property="og:image" content="https://demo.spreecommerce.org/images/personal-blender.jpg">
        <meta property="og:url" content="https://demo.spreecommerce.org">
        <meta property="product:price:amount" content="149.99">
        <meta property="product:price:currency" content="USD">
        <meta property="product:availability" content="in stock">
      </head>
      <body></body>
    </html>
    """

    rows = extract_records(
        html,
        "https://demo.spreecommerce.org/us/en/products/personal-blender",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["title"] == "Personal Blender"
    assert (
        record["url"]
        == "https://demo.spreecommerce.org/us/en/products/personal-blender"
    )
    assert record["_source"] == "opengraph"


@pytest.mark.regression
def test_extract_ecommerce_detail_ignores_placeholder_same_site_json_ld_url() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Biltmore Egyptian Collection Medium/Firm Support Pillow, White, King, Cotton",
          "url": "https://www.joinhoney.com/shop/undefined/p/undefined/",
          "priceCurrency": "USD"
        }
        </script>
      </head>
      <body>
        <h1>Biltmore Egyptian Collection Medium/Firm Support Pillow, White, King, Cotton</h1>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.joinhoney.com/it/shop/belk/p/7367171691114074156_8bce8b8cc8892988fb42b26670ceaa09_7121c9215dcc3274f45b6a172cf8e8a8",
        "ecommerce_detail",
        max_records=1,
        requested_page_url="https://www.joinhoney.com/it/shop/belk/p/7367171691114074156_8bce8b8cc8892988fb42b26670ceaa09_7121c9215dcc3274f45b6a172cf8e8a8",
    )

    assert len(rows) == 1
    assert (
        rows[0]["title"]
        == "Biltmore Egyptian Collection Medium/Firm Support Pillow, White, King, Cotton"
    )
    assert (
        rows[0]["url"]
        == "https://www.joinhoney.com/it/shop/belk/p/7367171691114074156_8bce8b8cc8892988fb42b26670ceaa09_7121c9215dcc3274f45b6a172cf8e8a8"
    )


@pytest.mark.regression
def test_extract_ecommerce_detail_ignores_review_json_ld_title_description_and_images() -> (
    None
):
    html = """
    <html>
      <head>
        <meta property="og:description" content="Weather resistant pack for daily commuting.">
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Commuter Backpack",
          "image": "https://example.com/images/product.jpg",
          "sku": "CB-001"
        }
        </script>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Review",
          "name": "Best choice I ever made",
          "description": "normal",
          "image": "https://example.com/images/review-photo.jpg"
        }
        </script>
      </head>
      <body>
        <h1>Commuter Backpack</h1>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/commuter-backpack",
        "ecommerce_detail",
        max_records=5,
        requested_fields=["description"],
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["title"] == "Commuter Backpack"
    assert record["description"] == "Weather resistant pack for daily commuting."
    assert record["image_url"] == "https://example.com/images/product.jpg"


@pytest.mark.regression
def test_extract_ecommerce_detail_ignores_nested_person_name_inside_product_json_ld() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Skechers Max Cushioning Elite",
          "brand": {
            "@type": "Brand",
            "name": "Skechers"
          },
          "manufacturer": {
            "@type": "Organization",
            "name": "Skechers",
            "founder": {
              "@type": "Person",
              "name": "Robert Greenberg"
            }
          },
          "offers": {
            "@type": "Offer",
            "priceCurrency": "USD",
            "price": "130.00",
            "availability": "https://schema.org/InStock"
          }
        }
        </script>
      </head>
      <body>
        <h1>Skechers Max Cushioning Elite</h1>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.skechers.com/max-cushioning-elite/220000.html",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["title"] == "Skechers Max Cushioning Elite"
    assert record["brand"] == "Skechers"
    assert "Robert Greenberg" not in record.values()


@pytest.mark.regression
def test_extract_ecommerce_detail_ignores_noisy_h1_and_uses_page_title() -> None:
    html = """
    <html>
      <head>
        <title>Widget Prime</title>
      </head>
      <body>
        <main>
          <h1>Save 20% With Code SPRING</h1>
          <div class="price">$19.99</div>
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
    assert record["price"] == "19.99"


@pytest.mark.regression
def test_extract_ecommerce_detail_from_array_style_nuxt_payload() -> None:
    html = """
    <html>
      <head>
        <script id="__NUXT_DATA__" type="application/json">
          [
            {"data":1},
            ["Reactive",2],
            {"product":3},
            {"title":4,"vendor":5,"handle":6,"id":7,"product_type":8},
            "Nuxt Payload Widget",
            "Acme",
            "nuxt-payload-widget",
            4242,
            "Gadgets"
          ]
        </script>
      </head>
      <body></body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/nuxt-payload-widget",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["title"] == "Nuxt Payload Widget"
    assert record["brand"] == "Acme"
    assert "vendor" not in record
    assert record["product_id"] == "4242"
    assert record["category"] == "Gadgets"
    assert record["_source"] == "js_state"


@pytest.mark.regression
def test_extract_ecommerce_detail_ignores_js_state_gift_option_price() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Air Force 1 '07 Basketball Sneaker",
          "offers": {
            "@type": "Offer",
            "price": "0",
            "priceCurrency": "INR",
            "availability": "https://schema.org/OutOfStock"
          }
        }
        </script>
        <script>
        window.__INITIAL_CONFIG__ = {
          "product": {
            "productName": "Air Force 1 '07 Basketball Sneaker",
            "styleNumber": "10014429",
            "price": null,
            "isAvailable": false
          },
          "giftServicesAvailable": [
            {
              "id": "gift-bag",
              "type": "giftOption",
              "title": "Fabric gift bag",
              "price": 5,
              "availability": ["delivery"]
            }
          ]
        };
        </script>
      </head>
      <body><h1>Air Force 1 '07 Basketball Sneaker</h1></body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.nordstrom.com/s/nike-air-force-1-07-basketball-sneaker-men/7507996",
        "ecommerce_detail",
        max_records=1,
        requested_fields=["title", "price", "currency", "availability"],
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["title"] == "Air Force 1 '07 Basketball Sneaker"
    assert record["availability"] == "out_of_stock"
    assert "price" not in record
    assert "currency" not in record


@pytest.mark.regression
def test_extract_ecommerce_detail_reads_plain_initial_state_variants() -> None:
    html = """
    <html>
      <head>
        <script>
        window.INITIAL_STATE = {
          "pdp": {
            "product": {
              "id": "19072301",
              "name": {"en": "Brown Ruff Rider Leather Jacket"},
              "price": 3890,
              "currency": "USD",
              "variants": [
                {"sku": "261232M18102300", "size": "S", "inStock": false},
                {"sku": "261232M18102301", "size": "M", "inStock": false},
                {"sku": "261232M18102302", "size": "L", "inStock": false},
                {"sku": "261232M18102303", "size": "XL", "inStock": false}
              ]
            }
          }
        };
        </script>
      </head>
      <body><h1>Brown Ruff Rider Leather Jacket</h1></body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.ssense.com/en-us/men/product/willy-chavarria/brown-ruff-rider-leather-jacket/19072301",
        "ecommerce_detail",
        max_records=1,
        requested_fields=["variants", "price", "currency", "availability"],
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["variant_count"] == 4
    assert {variant["size"] for variant in record["variants"]} == {"S", "M", "L", "XL"}
    assert all(
        variant.get("availability") == "out_of_stock" for variant in record["variants"]
    )


@pytest.mark.regression
def test_plain_initial_state_requires_global_assignment() -> None:
    html = """
    <html>
      <head>
        <script>
        var INITIAL_STATE = {"product": {"name": "Unrelated Widget"}};
        window.ACTUAL_STATE = {"product": {"name": "Real Widget"}};
        </script>
      </head>
    </html>
    """

    state_objects = harvest_js_state_objects(None, html)

    assert "INITIAL_STATE" not in state_objects


@pytest.mark.regression
def test_extract_ecommerce_detail_gender_from_explicit_structured_attribute() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Linen Midi Dress",
          "additionalProperty": [
            {"@type": "PropertyValue", "name": "Gender", "value": "Women"}
          ]
        }
        </script>
      </head>
      <body><h1>Linen Midi Dress</h1></body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/linen-midi-dress",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    assert rows[0]["gender"] == "Women"


@pytest.mark.regression
def test_extract_ecommerce_detail_uses_breadcrumblist_json_ld_category() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "BreadcrumbList",
          "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home"},
            {"@type": "ListItem", "position": 2, "name": "Women"},
            {"@type": "ListItem", "position": 3, "name": "Dresses"},
            {"@type": "ListItem", "position": 4, "name": "Linen Midi Dress"}
          ]
        }
        </script>
        <script type="application/ld+json">
        {"@context": "https://schema.org", "@type": "Product", "name": "Linen Midi Dress"}
        </script>
      </head>
      <body><h1>Linen Midi Dress</h1></body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/linen-midi-dress",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    assert rows[0]["category"] == "Women > Dresses"


@pytest.mark.regression
def test_extract_ecommerce_detail_category_drops_collection_branch_noise() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "BreadcrumbList",
          "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Sports"},
            {"@type": "ListItem", "position": 2, "name": "Padel"},
            {"@type": "ListItem", "position": 3, "name": "Collections"},
            {"@type": "ListItem", "position": 4, "name": "Back to the court"}
          ]
        }
        </script>
        <script type="application/ld+json">
        {"@context": "https://schema.org", "@type": "Product", "name": "Pressurised Padel Balls PB Speed Tri-Pack"}
        </script>
      </head>
      <body><h1>Pressurised Padel Balls PB Speed Tri-Pack</h1></body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/p/pressurised-padel-balls-pb-speed-tri-pack/347273/m8804642",
        "ecommerce_detail",
        max_records=5,
    )

    assert rows[0]["category"] == "Sports > Padel"


@pytest.mark.regression
def test_extract_ecommerce_detail_category_from_dom_breadcrumb() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {"@context": "https://schema.org", "@type": "Product", "name": "Linen Midi Dress"}
        </script>
      </head>
      <body>
        <nav aria-label="Breadcrumb">
          <ol>
            <li><a href="/">Home</a></li>
            <li><a href="/women">Women</a></li>
            <li><a href="/women/dresses">Dresses</a></li>
            <li><span>Linen Midi Dress</span></li>
          </ol>
        </nav>
        <h1>Linen Midi Dress</h1>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/linen-midi-dress",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    assert rows[0]["category"] == "Women > Dresses"
    assert rows[0]["gender"] == "women"


@pytest.mark.regression
def test_extract_ecommerce_detail_dom_breadcrumb_drops_ui_tokens_and_title_suffix() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {"@context": "https://schema.org", "@type": "Product", "name": "Trail Shoe Pro"}
        </script>
      </head>
      <body>
        <nav class="breadcrumbs">
          <a>Back</a>
          <a>Home</a>
          <a>Men</a>
          <a>Shoes</a>
          <span>Trail-Shoe Pro</span>
        </nav>
        <h1>Trail Shoe Pro</h1>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/trail-shoe-pro",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    assert rows[0]["category"] == "Men > Shoes"


@pytest.mark.regression
def test_breadcrumb_noise_icon_regex_logs_once_when_invalid(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(detail_raw_signals, "_BREADCRUMB_NOISE_ICON_PATTERNS", (r"[",))
    detail_raw_signals._compiled_breadcrumb_noise_icon_patterns.cache_clear()
    caplog.set_level("WARNING")
    soup = BeautifulSoup(
        """
        <nav class="breadcrumbs">
          <a>Home</a>
          <a>Women</a>
          <a>Dresses</a>
          <span>Trail Dress</span>
        </nav>
        """,
        "html.parser",
    )

    try:
        labels = detail_raw_signals.breadcrumb_labels_from_dom(
            soup,
            current_title="Trail Dress",
        )
        detail_raw_signals.breadcrumb_labels_from_dom(
            soup,
            current_title="Trail Dress",
        )
    finally:
        detail_raw_signals._compiled_breadcrumb_noise_icon_patterns.cache_clear()

    assert labels == ["Women", "Dresses"]
    assert (
        len(
            [
                record
                for record in caplog.records
                if record.message == "Invalid breadcrumb noise icon regex"
            ]
        )
        == 1
    )


@pytest.mark.regression
def test_extract_ecommerce_detail_json_ld_breadcrumb_beats_noisy_dom() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "BreadcrumbList",
          "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Home"},
            {"@type": "ListItem", "position": 2, "name": "Women"},
            {"@type": "ListItem", "position": 3, "name": "Dresses"},
            {"@type": "ListItem", "position": 4, "name": "Trail Dress"}
          ]
        }
        </script>
      </head>
      <body>
        <nav class="breadcrumbs">
          <a>Home</a>
          <a>Best Sellers</a>
          <a>Shop by Occasion</a>
          <span>Trail Dress</span>
        </nav>
        <h1>Trail Dress</h1>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/trail-dress",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    assert rows[0]["category"] == "Women > Dresses"


@pytest.mark.regression
def test_reconcile_parent_price_against_variant_range_repairs_lower_parent_price() -> (
    None
):
    record = {
        "price": "89.00",
        "variants": [
            {"price": "310.00", "currency": "USD"},
            {"price": "310.00", "currency": "USD"},
        ],
        "_field_sources": {"price": ["dom_text"]},
    }

    reconcile_parent_price_against_variant_range(record)

    assert record["price"] == "310.00"
    assert "variant_price_range" in record["_field_sources"]["price"]


@pytest.mark.regression
def test_extract_ecommerce_detail_category_drops_terminal_sku() -> None:
    html = """
    <html>
      <body>
        <nav class="breadcrumbs">
          <a>Home</a>
          <a>Tools</a>
          <a>Drills</a>
          <span>SKU-7788</span>
        </nav>
        <h1>Hammer Drill</h1>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/hammer-drill",
        "ecommerce_detail",
        max_records=5,
        adapter_records=[{"sku": "SKU-7788"}],
    )

    assert len(rows) == 1
    assert rows[0]["category"] == "Tools > Drills"

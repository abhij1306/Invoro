from __future__ import annotations

from .test_crawl_engine import (
    extract_records,
    pytest,
)


@pytest.mark.regression
def test_extract_detail_infers_chewy_style_offer_variant_sizes() -> None:
    html = """
    <html><head>
      <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "Chicken Recipe Dry Dog Food",
        "brand": {"@type": "Brand", "name": "Acme"},
        "offers": [
          {
            "@type": "Offer",
            "name": "Chicken Recipe Dry Dog Food, 4-lb bag",
            "url": "https://www.chewy.com/acme-food/dp/123?size=4-lb",
            "price": "18.99",
            "priceCurrency": "USD"
          },
          {
            "@type": "Offer",
            "name": "Chicken Recipe Dry Dog Food, 12-lb bag",
            "url": "https://www.chewy.com/acme-food/dp/123?size=12-lb",
            "price": "42.99",
            "priceCurrency": "USD"
          }
        ]
      }
      </script>
    </head><body><h1>Chicken Recipe Dry Dog Food</h1></body></html>
    """

    rows = extract_records(
        html,
        "https://www.chewy.com/acme-food/dp/123",
        "ecommerce_detail",
        max_records=1,
    )

    assert len(rows) == 1
    record = rows[0]
    assert [row["price"] for row in record["variants"]] == ["18.99", "42.99"]


@pytest.mark.regression
def test_extract_ecommerce_detail_does_not_infer_price_from_shell_chrome_text() -> None:
    html = """
    <html>
      <head>
        <meta property="og:title" content="iPhone">
      </head>
      <body>
        <aside>
          <p>Trade-in</p>
          <p>Get up to $20 for your old device</p>
        </aside>
        <main>
          <h2>Category navigation</h2>
          <a href="/en-us/l/iphone/example">See all iPhone deals</a>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.backmarket.com/en-us/p/iphone-14-128-gb-midnight/dba71a89-1e8e-4278-967e-0ef1c0d05f31",
        "ecommerce_detail",
        max_records=1,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["title"] == "iPhone"
    assert "price" not in record
    assert "currency" not in record


@pytest.mark.regression
def test_extract_ecommerce_detail_does_not_infer_price_from_404_body_text() -> None:
    html = """
    <html>
      <head>
        <meta property="og:title" content="MacBook Pro 15-inch Retina Display Mid 2015 Battery">
      </head>
      <body>
        <main>
          <h1>404</h1>
          <p>Page not found</p>
          <p>Repair kits from $1.99 ship fast.</p>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.ifixit.com/products/macbook-pro-15-inch-retina-display-mid-2015-battery",
        "ecommerce_detail",
        max_records=1,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["title"] == "MacBook Pro 15-inch Retina Display Mid 2015 Battery"
    assert "price" not in record
    assert "currency" not in record


@pytest.mark.regression
def test_extract_ecommerce_detail_rejects_404_record_with_filter_variants() -> None:
    html = """
    <html>
      <body>
        <main>
          <h1>Error 404 .</h1>
          <label for="search-type">Type</label>
          <select id="search-type" name="type">
            <option>all</option>
            <option>release</option>
            <option>artist</option>
            <option>label</option>
          </select>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.discogs.com/release/stale",
        "ecommerce_detail",
        max_records=1,
    )

    assert rows == []


@pytest.mark.regression
def test_extract_ecommerce_detail_reads_books_table_price_currency() -> None:
    html = """
    <html>
      <body>
        <article class="product_page">
          <h1>A Light in the Attic</h1>
          <table>
            <tr><th>Price (excl. tax)</th><td>£51.77</td></tr>
            <tr><th>Availability</th><td>In stock</td></tr>
          </table>
          <p class="price_color">£51.77</p>
        </article>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
        "ecommerce_detail",
        max_records=1,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["price"] == "51.77"
    assert record["currency"] == "GBP"


@pytest.mark.regression
def test_extract_detail_normalizes_shopify_embedded_compare_at_price_from_cents() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Trompette 100 suede boots",
          "offers": {
            "price": "939.00",
            "priceCurrency": "EUR",
            "availability": "https://schema.org/InStock"
          }
        }
        </script>
        <script>
          ShopifyAnalytics.meta = {
            "product": {
              "id": 8214341320770,
              "title": "Trompette 100 suede boots",
              "handle": "trompette-100-suede-boots-rv27109s",
              "vendor": "Roger Vivier",
              "product_type": "Boots",
              "compare_at_price": 156500,
              "variants": [
                {
                  "id": 43633663574082,
                  "price": 93900,
                  "compare_at_price": 156500,
                  "option1": "36",
                  "inventory_quantity": 1
                }
              ]
            }
          };
        </script>
      </head>
      <body>
        <h1>Trompette 100 suede boots</h1>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://savannahs.com/collections/all-boots/products/trompette-100-suede-boots-rv27109s",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["price"] == "939.00"
    assert record["original_price"] == "1565.00"


@pytest.mark.regression
def test_extract_detail_keeps_shopify_variant_record_when_requested_url_has_product_code_prefix() -> (
    None
):
    html = """
    <html>
      <head>
        <script>
          ShopifyAnalytics.meta = {
            "product": {
              "id": 8214341320770,
              "title": "Phoenix dark brown leather boots",
              "vendor": "Chloe",
              "product_type": "Boots",
              "variants": [
                {
                  "id": 43633711644738,
                  "sku": "CH28105S360",
                  "price": 126500,
                  "option1": "36"
                }
              ]
            }
          };
        </script>
      </head>
      <body>
        <h1>Phoenix dark brown leather boots</h1>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://savannahs.com/collections/all-boots/products/phoenix-dark-brown-leather-boots-ch28105s",
        "ecommerce_detail",
        max_records=5,
        requested_page_url="https://savannahs.com/collections/all-boots/products/phoenix-dark-brown-leather-boots-ch28105s",
    )

    assert len(rows) == 1
    assert rows[0]["title"] == "Phoenix dark brown leather boots"


@pytest.mark.regression
def test_extract_detail_strips_variant_availability_suffix_from_option_values() -> None:
    html = """
    <html>
      <body>
        <h1>Phoenix dark brown leather boots</h1>
        <fieldset>
          <legend>Size</legend>
          <input id="size-36" type="radio" name="size" checked>
          <label for="size-36">36 Variant sold out or unavailable</label>
          <input id="size-37" type="radio" name="size">
          <label for="size-37">37 Variant sold out or unavailable</label>
        </fieldset>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://savannahs.com/collections/all-boots/products/phoenix-dark-brown-leather-boots-ch28105s",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    assert [variant["size"] for variant in rows[0]["variants"]] == ["36", "37"]


@pytest.mark.regression
def test_extract_detail_dom_images_excludes_related_product_cards() -> None:
    html = """
    <html>
      <body>
        <h1>Trail Runner</h1>
        <section class="product-gallery">
          <img src="/images/trail-runner-1.jpg" alt="Trail Runner front">
          <img src="/images/trail-runner-2.jpg" alt="Trail Runner side">
        </section>
        <section class="related-products">
          <a href="/products/city-runner">
            <img src="/images/city-runner.jpg" alt="City Runner">
          </a>
          <a href="/products/mountain-runner">
            <img src="/images/mountain-runner.jpg" alt="Mountain Runner">
          </a>
        </section>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/trail-runner",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["image_url"] == "https://example.com/images/trail-runner-1.jpg"
    assert record["additional_images"] == [
        "https://example.com/images/trail-runner-2.jpg"
    ]


@pytest.mark.regression
def test_extract_detail_dom_images_excludes_compare_model_assets() -> None:
    html = """
    <html>
      <body>
        <h1>iPhone 16</h1>
        <main>
          <section class="product-gallery">
            <img src="/images/iphone-16-front.jpg" alt="iPhone 16 front">
            <img src="/images/iphone-16-side.jpg" alt="iPhone 16 side">
          </section>
          <section class="compare-models">
            <img src="/images/iphone-17-pro.jpg" alt="iPhone 17 Pro">
            <img src="/images/iphone-air.jpg" alt="iPhone Air">
          </section>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/iphone-16",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["image_url"] == "https://example.com/images/iphone-16-front.jpg"
    assert record["additional_images"] == [
        "https://example.com/images/iphone-16-side.jpg"
    ]


@pytest.mark.regression
def test_extract_detail_scopes_text_away_from_customers_also_viewed_products() -> None:
    html = """
    <html>
      <body>
        <main class="pdp-main">
          <h1>Alfani Theo Cap Toe Oxford</h1>
          <section class="product-description">
            <h2>Description</h2>
            <p>Polished cap toe oxford with cushioned comfort for formal wear.</p>
          </section>
          <section class="customers-also-viewed">
            <a href="/products/tommy-hilfiger-hiday">Tommy Hilfiger Mens Hiday Casualized Hybrid Oxfords</a>
            <p>Hybrid oxford with sneaker outsole.</p>
            <a href="/products/cole-haan-grand-remix">Cole Haan Grand Remix</a>
            <p>Leather shoe with brogue detail.</p>
          </section>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/alfani-theo-cap-toe-oxford",
        "ecommerce_detail",
        max_records=5,
    )

    record = rows[0]
    assert record["title"] == "Alfani Theo Cap Toe Oxford"
    assert "Polished cap toe oxford" in record["description"]
    assert "Tommy Hilfiger" not in record["description"]
    assert "Cole Haan" not in record["description"]


@pytest.mark.regression
def test_extract_detail_rejects_placeholder_and_ui_asset_images() -> None:
    html = """
    <html>
      <body>
        <main>
          <h1>Vans Old Skool</h1>
          <section class="product-gallery">
            <img src="https://via.placeholder.com/600" alt="placeholder">
            <img src="/assets/white.svg" alt="white icon">
            <img src="/images/vans-old-skool.jpg" alt="Vans Old Skool">
          </section>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/vans-old-skool",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    assert rows[0]["image_url"] == "https://example.com/images/vans-old-skool.jpg"


@pytest.mark.regression
def test_extract_detail_generic_original_price_from_del_or_was_price() -> None:
    html = """
    <html>
      <body>
        <main>
          <h1>Sale Jacket</h1>
          <span class="price-current">$79.99</span>
          <del>$129.99</del>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/sale-jacket",
        "ecommerce_detail",
        max_records=5,
    )

    assert rows[0]["price"] == "79.99"
    assert rows[0]["original_price"] == "129.99"

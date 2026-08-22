from __future__ import annotations

from .test_crawl_engine import HostProtectionPolicy, _js_shell_html, crawl_fetch_runtime, detail_extractor, extract_records, pytest  # fmt: skip

@pytest.mark.regression
def test_extract_records_does_not_leak_standalone_product_payloads_when_itemlist_exists() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@graph": [
            {
              "@type": "ItemList",
              "itemListElement": [
                {
                  "@type": "ListItem",
                  "position": 1,
                  "item": {
                    "@type": "Product",
                    "name": "Widget One",
                    "url": "/products/widget-one"
                  }
                },
                {
                  "@type": "ListItem",
                  "position": 2,
                  "item": {
                    "@type": "Product",
                    "name": "Widget Two",
                    "url": "/products/widget-two"
                  }
                }
              ]
            },
            {
              "@type": "Product",
              "name": "Category Hero Product",
              "url": "/products/category-hero"
            }
          ]
        }
        </script>
      </head>
      <body></body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/collections/widgets",
        "ecommerce_listing",
        max_records=10,
    )

    assert [row["title"] for row in rows] == ["Widget One", "Widget Two"]
    assert [row["url"] for row in rows] == [
        "https://example.com/products/widget-one",
        "https://example.com/products/widget-two",
    ]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_fetch_page_uses_browser_after_js_shell_detection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await crawl_fetch_runtime.reset_fetch_runtime_state()

    async def fake_curl(url: str, timeout_seconds: float):
        return crawl_fetch_runtime.PageFetchResult(
            url=url,
            final_url=url,
            html=_js_shell_html(),
            status_code=200,
            method="curl_cffi",
        )

    async def unexpected_http(url: str, timeout_seconds: float):
        raise AssertionError(
            f"http fallback should not run for {url} {timeout_seconds}"
        )

    browser_calls: list[str] = []

    async def fake_browser(url: str, timeout_seconds: float, **kwargs):
        del timeout_seconds, kwargs
        browser_calls.append(url)
        return crawl_fetch_runtime.PageFetchResult(
            url=url,
            final_url=url,
            html="<html><body><h1>Rendered</h1></body></html>",
            status_code=200,
            method="browser",
        )

    monkeypatch.setattr(crawl_fetch_runtime, "_curl_fetch", fake_curl)
    monkeypatch.setattr(crawl_fetch_runtime, "_http_fetch", unexpected_http)
    monkeypatch.setattr(crawl_fetch_runtime, "_browser_fetch", fake_browser)

    first = await crawl_fetch_runtime.fetch_page("https://example.com/listing")
    second = await crawl_fetch_runtime.fetch_page("https://example.com/detail")

    assert first.method == "browser"
    assert second.method == "browser"
    assert browser_calls == [
        "https://example.com/listing",
        "https://example.com/detail",
    ]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_fetch_page_keeps_http_for_structured_shopify_detail(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await crawl_fetch_runtime.reset_fetch_runtime_state()

    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {"@context":"https://schema.org","@type":"Product","name":"The Relaxed Wide Leg Maternity Jean"}
        </script>
        <script>
          ShopifyAnalytics.meta = {"product":{"id":8199133855921,"title":"The Relaxed Wide Leg Maternity Jean"}};
        </script>
      </head>
      <body>
        <div id="__next"></div>
        <h1>The Relaxed Wide Leg Maternity Jean</h1>
      </body>
    </html>
    """

    async def fake_curl(url: str, timeout_seconds: float):
        return crawl_fetch_runtime.PageFetchResult(
            url=url,
            final_url=url,
            html=html,
            status_code=200,
            method="curl_cffi",
        )

    async def unexpected_browser(url: str, timeout_seconds: float, **kwargs):
        raise AssertionError(
            f"browser fallback should not run for {url} {timeout_seconds} {kwargs}"
        )

    async def fake_load_host_protection_policy(
        url: str,
        *,
        ttl_seconds: int | None = None,
    ) -> HostProtectionPolicy:
        del ttl_seconds
        return HostProtectionPolicy(host=url)

    monkeypatch.setattr(crawl_fetch_runtime, "_curl_fetch", fake_curl)
    monkeypatch.setattr(crawl_fetch_runtime, "_browser_fetch", unexpected_browser)
    monkeypatch.setattr(
        crawl_fetch_runtime,
        "load_host_protection_policy",
        fake_load_host_protection_policy,
    )

    result = await crawl_fetch_runtime.fetch_page(
        "https://example.com/products/hatch-jean"
    )

    assert result.method == "curl_cffi"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_fetch_page_uses_browser_first_for_requires_browser_platform(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    await crawl_fetch_runtime.reset_fetch_runtime_state()

    async def unexpected_curl(url: str, timeout_seconds: float):
        raise AssertionError(
            f"curl fetch should not run for browser-first platform {url} {timeout_seconds}"
        )

    async def unexpected_http(url: str, timeout_seconds: float):
        raise AssertionError(
            f"http fallback should not run for browser-first platform {url} {timeout_seconds}"
        )

    async def fake_browser(url: str, timeout_seconds: float, **kwargs):
        del timeout_seconds, kwargs
        return crawl_fetch_runtime.PageFetchResult(
            url=url,
            final_url=url,
            html="<html><body><h1>Rendered ADP</h1></body></html>",
            status_code=200,
            method="browser",
        )

    monkeypatch.setattr(crawl_fetch_runtime, "_curl_fetch", unexpected_curl)
    monkeypatch.setattr(crawl_fetch_runtime, "_http_fetch", unexpected_http)
    monkeypatch.setattr(crawl_fetch_runtime, "_browser_fetch", fake_browser)

    result = await crawl_fetch_runtime.fetch_page(
        "https://workforcenow.adp.com/recruitment/recruitment.html?jobId=12345"
    )

    assert result.method == "browser"

@pytest.mark.regression
def test_browser_runtime_snapshot_exposes_capacity_shape() -> None:
    snapshot = crawl_fetch_runtime.browser_runtime_snapshot()

    assert {"ready", "size", "max_size", "active", "queued", "capacity"} <= set(
        snapshot
    )
    assert int(snapshot["max_size"]) >= 1

@pytest.mark.regression
def test_extract_ecommerce_detail_returns_normalized_record() -> None:
    html = """
    <html>
      <head>
        <title>Widget Prime</title>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Widget Prime",
          "description": "A deterministic widget",
          "sku": "W-100",
          "mpn": "MP-9",
          "brand": {"name": "Acme"},
          "category": "Widgets",
          "image": [
            "https://example.com/images/widget-1.jpg",
            "https://example.com/images/widget-2.jpg"
          ],
          "offers": {
            "price": "19.99",
            "priceCurrency": "USD",
            "availability": "https://schema.org/InStock"
          },
          "aggregateRating": {
            "ratingValue": "4.7",
            "reviewCount": "128"
          }
        }
        </script>
        <script type="application/json">
        {
          "product": {
            "vendor": "Acme Retail",
            "product_type": "Gadget",
            "handle": "widget-prime",
            "barcode": "1234567890123",
            "tags": ["featured", "new"],
            "available_sizes": ["S", "M", "L"],
            "variant_axes": {"size": ["S", "M", "L"]},
            "variants": [{"sku": "W-100-S", "size": "S"}]
          }
        }
        </script>
      </head>
      <body>
        <h1>Widget Prime</h1>
        <section class="product-features">
          Lightweight body
          Long battery life
        </section>
        <p>Materials: Cotton blend</p>
        <p>Care: Machine wash</p>
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
    expected_fields = {
        "title": "Widget Prime",
        "price": "19.99",
        "currency": "USD",
        "availability": "in_stock",
        "brand": "Acme",
        "vendor": "Acme Retail",
        "sku": "W-100",
        "part_number": "MP-9",
        "barcode": "1234567890123",
        "product_type": "Gadget",
        "category": "Widgets",
        "image_url": "https://example.com/images/widget-1.jpg",
        "review_count": 128,
        "features": ["Lightweight body", "Long battery life"],
        "materials": "Cotton blend",
        "care": "Machine wash",
        "size": "S",
    }
    assert {key: record[key] for key in expected_fields} == expected_fields
    assert any("widget-2.jpg" in value for value in record["additional_images"])
    assert record["rating"] == pytest.approx(4.7)
    assert isinstance(record["_confidence"], dict)
    assert record["_confidence"]["level"] in {"medium", "high"}

@pytest.mark.regression
def test_extract_ecommerce_detail_rejects_site_shell_with_listing_payload_pollution() -> (
    None
):
    html = """
    <html>
      <head>
        <meta property="og:title" content="Practice Software Testing">
        <meta property="og:image" content="https://practicesoftwaretesting.com/assets/img/barn-2400x1600.avif">
        <meta property="og:description" content="Modern application used to learn software testing or test automation.">
        <title>Practice Software Testing</title>
      </head>
      <body>
        <main>
          <article class="product-card">
            <a href="/product/01KPSB7HREA049EFVP5SV8Z46Y">
              <img class="card-img-top" alt="Combination Pliers" src="assets/img/products/pliers01.avif">
              <span class="price">$14.15</span>
            </a>
          </article>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://practicesoftwaretesting.com/#/product/01HB",
        "ecommerce_detail",
        max_records=5,
        requested_fields=[
            "title",
            "price",
            "image_url",
            "description",
            "category",
            "brand",
        ],
        network_payloads=[
            {
                "url": "https://api.practicesoftwaretesting.com/products?page=1",
                "endpoint_type": "generic_json",
                "body": {
                    "current_page": 1,
                    "data": [
                        {
                            "id": "01KPSB7HREA049EFVP5SV8Z46Y",
                            "name": "Combination Pliers",
                            "description": "Listing summary for pliers.",
                            "price": "14.15",
                            "brand": "ForgeFlex Tools",
                            "image": "https://practicesoftwaretesting.com/assets/img/products/pliers01.avif",
                            "url": "https://practicesoftwaretesting.com/#/product/01KPSB7HREA049EFVP5SV8Z46Y",
                        },
                        {
                            "id": "01KPSB7HREA049EFVP5SV8Z470",
                            "name": "Bolt Cutters",
                            "description": "Listing summary for cutters.",
                            "price": "24.99",
                            "brand": "ForgeFlex Tools",
                            "image": "https://practicesoftwaretesting.com/assets/img/products/pliers03.avif",
                            "url": "https://practicesoftwaretesting.com/#/product/01KPSB7HREA049EFVP5SV8Z470",
                        },
                    ],
                },
            }
        ],
    )

    assert rows == []

@pytest.mark.regression
def test_extract_ecommerce_detail_rejects_brand_shell_with_app_prompt_copy() -> None:
    html = """
    <html>
      <head>
        <title>UNIQLO - LifeWear</title>
        <meta property="og:title" content="UNIQLO - LifeWear" />
        <meta property="og:description" content="Shop on our app for the best experience" />
        <meta property="og:url" content="https://www.uniqlo.com/in/en/products/E474244-000/01" />
        <meta property="og:image" content="https://image.uniqlo.com/UQ/ST3/in/imagesgoods/474244/item/ingoods_57_474244_3x4.jpg" />
      </head>
      <body>
        <main>
          <h1>UNIQLO - LifeWear</h1>
          <div role="radiogroup" aria-label="Color">
            <button aria-label="57 OLIVE">57 OLIVE</button>
          </div>
          <img src="https://image.uniqlo.com/UQ/ST3/in/imagesgoods/474244/item/ingoods_57_474244_3x4.jpg" alt="57 OLIVE" />
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.uniqlo.com/in/en/products/E474244-000/01?colorDisplayCode=57&sizeDisplayCode=005",
        "ecommerce_detail",
        max_records=5,
        requested_page_url="https://www.uniqlo.com/in/en/products/E474244-000/01",
    )

    assert rows == []

@pytest.mark.regression
def test_extract_ecommerce_detail_prefers_requested_identity_on_same_site_utility_redirect() -> (
    None
):
    html = """
    <html>
      <head>
        <title>Online Shopping for Men &amp; Women Clothing, Accessories at The Souled Store</title>
        <meta property="og:title" content="Buy Oversized T-Shirt: Bear Minimum Oversized T-Shirts Online" />
        <meta property="og:description" content="Shop for Oversized T-Shirt: Bear Minimum Oversized T-Shirts Online" />
        <meta property="og:url" content="https://www.thesouledstore.com/product/oversized-tshirts-bear-minimum?gte=1" />
        <meta property="og:image" content="https://prod-img.thesouledstore.com/public/theSoul/uploads/catalog/product/1749147636_7690605.jpg" />
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Oversized T-Shirt: Bear Minimum Oversized T-Shirts By The Souled Store",
          "image": "https://prod-img.thesouledstore.com/public/theSoul/uploads/catalog/product/1749147636_7690605.jpg",
          "sku": "305537",
          "description": "Shop for Oversized T-Shirt: Bear Minimum Oversized T-Shirts Online",
          "offers": {
            "@type": "Offer",
            "priceCurrency": "INR",
            "availability": "InStock",
            "price": "1199",
            "url": "https://www.thesouledstore.com/product/oversized-tshirts-bear-minimum?gte=1"
          },
          "brand": {
            "@type": "Thing",
            "name": "The Souled Store"
          }
        }
        </script>
      </head>
      <body>
        <div class="wishlistDiv">Wishlist shell</div>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.thesouledstore.com/mywishlist",
        "ecommerce_detail",
        max_records=5,
        requested_page_url="https://www.thesouledstore.com/product/oversized-tshirts-bear-minimum?gte=1",
    )

    assert len(rows) == 1
    record = rows[0]
    assert (
        record["url"]
        == "https://www.thesouledstore.com/product/oversized-tshirts-bear-minimum?gte=1"
    )
    assert (
        record["source_url"]
        == "https://www.thesouledstore.com/product/oversized-tshirts-bear-minimum?gte=1"
    )
    assert (
        record["title"]
        == "Oversized T-Shirt: Bear Minimum Oversized T-Shirts By The Souled Store"
    )
    assert record["sku"] == "305537"

@pytest.mark.regression
def test_extract_ecommerce_detail_rejects_same_site_utility_redirect_with_mismatched_product_payload() -> (
    None
):
    html = """
    <html>
      <head>
        <meta property="og:title" content="Avatar: Fire Bender Oversized T-Shirts By Avatar: The Last Airbender" />
        <meta property="og:description" content="Shop for Avatar: Fire Bender Oversized T-Shirts Online" />
        <meta property="og:image" content="https://prod-img.thesouledstore.com/public/theSoul/uploads/catalog/product/1753379330_3880870.jpg" />
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Avatar: Fire Bender Oversized T-Shirts By Avatar: The Last Airbender",
          "image": "https://prod-img.thesouledstore.com/public/theSoul/uploads/catalog/product/1753379330_3880870.jpg",
          "sku": "309454",
          "description": "Shop for Avatar: Fire Bender Oversized T-Shirts Online",
          "offers": {
            "@type": "Offer",
            "priceCurrency": "INR",
            "availability": "InStock",
            "price": "1199",
            "url": "https://www.thesouledstore.com/product/avatar-fire-bender-menoversized-tshirt?gte=1"
          }
        }
        </script>
      </head>
      <body>
        <section class="faq-wrapper">
          <h2>Returns, Exchange &amp; Refund</h2>
        </section>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.thesouledstore.com/faqs",
        "ecommerce_detail",
        max_records=5,
        requested_page_url="https://www.thesouledstore.com/product/marvel-spider-x-venom-oversized-tshirt?gte=1",
    )

    assert rows == []

@pytest.mark.regression
def test_extract_ecommerce_detail_rejects_same_site_wrong_product_payload_without_utility_redirect() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Hanes Authentic T-shirt",
          "url": "https://www.customink.com/products/t-shirts/4",
          "image": "https://www.customink.com/images/hanes-shirt.jpg",
          "description": "A basic t-shirt product."
        }
        </script>
      </head>
      <body>
        <h1>Medic Shirts</h1>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.customink.com/t-shirts/medic-shirts",
        "ecommerce_detail",
        max_records=10,
        requested_page_url="https://www.customink.com/t-shirts/medic-shirts",
    )

    assert rows == []

@pytest.mark.regression
def test_extract_ecommerce_detail_keeps_same_url_color_variant_product_path() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Bondi 9",
          "brand": {
            "@type": "Brand",
            "name": "Hoka"
          },
          "color": "Berry Jam/Berry Patch",
          "description": "Women's Hoka Bondi 9 by Hoka at Zappos.com.",
          "image": "https://m.media-amazon.com/images/I/71tLsSyLUZL._SX700_.jpg",
          "offers": {
            "@type": "Offer",
            "price": "175.00",
            "priceCurrency": "USD"
          }
        }
        </script>
      </head>
      <body>
        <main>
          <h1>Bondi 9</h1>
          <div class="price">$175.00</div>
        </main>
      </body>
    </html>
    """

    requested_url = (
        "https://www.zappos.com/kratos/p/"
        "womens-hoka-bondi-9-berry-jam-berry-patch/product/9984296/color/318988"
        "?zlfid=191"
    )

    rows = extract_records(
        html,
        requested_url,
        "ecommerce_detail",
        max_records=5,
        requested_page_url=requested_url,
    )

    assert len(rows) == 1
    assert rows[0]["title"] == "Bondi 9"

@pytest.mark.regression
def test_extract_ecommerce_detail_rejects_fragment_backed_shell_payload_from_spa_root() -> (
    None
):
    html = """
    <html>
      <head>
        <meta property="og:title" content="Practice Software Testing" />
        <meta property="og:description" content="Modern application used to learn software testing or test automation." />
        <meta property="og:url" content="https://www.practicesoftwaretesting.com/" />
      </head>
      <body>
        <main>
          <h1>Practice Software Testing</h1>
          <label for="sort">Sort</label>
          <select id="sort">
            <option>Name (A - Z)</option>
            <option>Name (Z - A)</option>
          </select>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://practicesoftwaretesting.com/#/product/01HB",
        "ecommerce_detail",
        max_records=5,
        requested_page_url="https://practicesoftwaretesting.com/#/product/01HB",
    )

    assert rows == []

@pytest.mark.regression
def test_detail_rejection_does_not_claim_identity_mismatch_when_same_url_never_redirected() -> (
    None
):
    requested_url = (
        "https://www.zara.com/us/en/rustic-cotton-t-shirt-p04424306.html?v1=527078510"
    )
    record = {
        "title": "United States",
        "url": requested_url,
    }

    assert (
        detail_extractor.detail_record_rejection_reason(
            record,
            page_url=requested_url,
            requested_page_url=requested_url,
        )
        is None
    )

@pytest.mark.regression
def test_detail_rejection_labels_product_shell_as_detail_shell_not_non_detail_seed() -> (
    None
):
    requested_url = (
        "https://www.wayfair.com/furniture/pdp/"
        "flexsteel-bryce-power-reclining-sofa-with-power-headrest-xtya1522.html"
        "?piid=94673717"
    )
    record = {
        "title": "flexsteel bryce power reclining sofa with power headrest xtya1522",
        "url": requested_url,
        "_field_sources": {"title": ["dom_h1", "url_slug"]},
        "_source": "dom_h1",
        "_confidence": {
            "score": 0.1217,
            "level": "low",
        },
    }

    assert (
        detail_extractor.detail_record_rejection_reason(
            record,
            page_url=requested_url,
            requested_page_url=requested_url,
        )
        == "detail_shell"
    )

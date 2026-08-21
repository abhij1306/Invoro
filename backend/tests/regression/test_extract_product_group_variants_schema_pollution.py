from __future__ import annotations

from .test_crawl_engine import *  # noqa: F403


@pytest.mark.regression
def test_extract_product_group_variants_without_schema_pollution() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@graph": [{
            "@type": "ProductGroup",
            "name": "Jim Bag",
            "description": "Soft grained leather bag adorned with a chain and rhinestone wing.",
            "material": "Material: 100% Cow leather",
            "brand": {"name": "Zadig&Voltaire"},
            "image": [
              "https://example.com/jim-1.jpg",
              "https://example.com/jim-2.jpg"
            ],
            "additionalProperty": [
              {"@type": "PropertyValue", "name": "Composition", "value": "Material: 100% Cow leather"},
              {"@type": "PropertyValue", "name": "Care", "value": "Protect from humidity"}
            ],
            "hasVariant": [
              {
                "@type": "Product",
                "sku": "LWBA04310011UNI",
                "name": "Jim Bag - One size",
                "size": "One size",
                "color": "Black",
                "gtin13": "3607624735775",
                "image": "https://example.com/jim-1.jpg",
                "offers": {
                  "@type": "Offer",
                  "url": "https://example.com/jim-bag?filter=size-One%20size",
                  "priceCurrency": "GBP",
                  "price": 470,
                  "availability": "https://schema.org/InStock"
                }
              }
            ]
          }]
        }
        </script>
        <script>window.__NUXT__ = {"config":{"public":{"env":"production"}}};</script>
      </head>
      <body>
        <h1>Jim Bag</h1>
        <footer>Download our app type: marketing shell</footer>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/p/jim-bag",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["title"] == "Jim Bag"
    assert record["brand"] == "Zadig&Voltaire"
    assert record["materials"] == "Material: 100% Cow leather"
    assert record["care"] == "Protect from humidity"
    assert isinstance(record["variants"], list)
    assert record["variant_count"] == 1
    assert (
        record["description"]
        == "Soft grained leather bag adorned with a chain and rhinestone wing."
    )
    assert "marketing shell" not in record.get("description", "")

@pytest.mark.regression
def test_extract_ecommerce_listing_returns_card_records() -> None:
    html = """
    <html>
      <body>
        <article class="product-card">
          <a href="/products/widget-prime">
            <img src="/images/widget-prime.jpg" alt="Widget Prime">
            <h2 class="product-title">Widget Prime</h2>
          </a>
          <div class="price">$19.99</div>
        </article>
        <article class="product-card">
          <a href="/products/widget-pro">
            <img src="/images/widget-pro.jpg" alt="Widget Pro">
            <h2 class="product-title">Widget Pro</h2>
          </a>
          <div class="price">$29.99</div>
        </article>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/collections/widgets",
        "ecommerce_listing",
        max_records=10,
    )

    assert len(rows) == 2
    assert rows[0]["title"] == "Widget Prime"
    assert rows[0]["url"] == "https://example.com/products/widget-prime"
    assert rows[0]["price"] == "19.99"
    assert rows[0]["image_url"] == "https://example.com/images/widget-prime.jpg"
    assert "additional_images" not in rows[0]
    assert rows[1]["title"] == "Widget Pro"

@pytest.mark.regression
def test_extract_ecommerce_listing_preserves_functional_query_params() -> None:
    html = """
    <html>
      <body>
        <article class="product-card">
          <a href="/products/widget-prime?utm_source=newsletter&variant=blue&ref=campaign">
            <img src="/images/widget-prime.jpg" alt="Widget Prime">
            <h2 class="product-title">Widget Prime</h2>
          </a>
          <div class="price">$19.99</div>
        </article>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/collections/widgets?utm_campaign=spring&sort=featured",
        "ecommerce_listing",
        max_records=10,
    )

    assert len(rows) == 1
    assert rows[0]["url"] == "https://example.com/products/widget-prime?variant=blue"
    assert (
        rows[0]["source_url"] == "https://example.com/collections/widgets?sort=featured"
    )

@pytest.mark.regression
def test_extract_ecommerce_listing_keeps_title_only_detail_candidates_without_detail_markers() -> (
    None
):
    html = """
    <html>
      <body>
        <article class="product-card">
          <a href="/browse/widget-prime">
            <h2 class="product-title">Widget Prime Ultra</h2>
          </a>
        </article>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/catalog",
        "ecommerce_listing",
        max_records=10,
    )

    assert rows == [
        {
            "source_url": "https://example.com/catalog",
            "_source": "dom_listing",
            "title": "Widget Prime Ultra",
            "url": "https://example.com/browse/widget-prime",
        }
    ]

@pytest.mark.regression
def test_extract_ecommerce_listing_does_not_treat_supportive_product_paths_as_utility_urls() -> (
    None
):
    html = """
    <html>
      <body>
        <article class="product-card">
          <a href="/products/supportive-chair">
            <h2 class="product-title">Supportive Chair</h2>
          </a>
        </article>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/catalog",
        "ecommerce_listing",
        max_records=10,
    )

    assert rows == [
        {
            "source_url": "https://example.com/catalog",
            "_source": "dom_listing",
            "title": "Supportive Chair",
            "url": "https://example.com/products/supportive-chair",
        }
    ]

@pytest.mark.regression
def test_extract_ecommerce_listing_keeps_same_site_cross_subdomain_detail_links() -> (
    None
):
    html = """
    <html>
      <body>
        <article class="product-card">
          <a href="https://www.indiamart.com/proddetail/widget-prime-123.html">
            <img src="https://img.indiamart.com/widget-prime.jpg" alt="Widget Prime" />
            <h2 class="product-title">Widget Prime</h2>
          </a>
          <div class="price">₹71</div>
        </article>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://dir.indiamart.com/impcat/widgets.html",
        "ecommerce_listing",
        max_records=10,
    )

    assert len(rows) == 1
    assert (
        rows[0]["url"] == "https://www.indiamart.com/proddetail/widget-prime-123.html"
    )
    assert rows[0]["title"] == "Widget Prime"
    assert rows[0]["price"] == "71"

@pytest.mark.regression
def test_extract_ecommerce_listing_treats_proddetail_paths_as_detail_links() -> None:
    html = """
    <html>
      <body>
        <article class="product-card">
          <a href="https://www.indiamart.com/proddetail/widget-prime-123.html">
            <h2 class="product-title">Widget Prime</h2>
          </a>
        </article>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://dir.indiamart.com/impcat/widgets.html",
        "ecommerce_listing",
        max_records=10,
    )

    assert len(rows) == 1
    assert (
        rows[0]["url"] == "https://www.indiamart.com/proddetail/widget-prime-123.html"
    )
    assert rows[0]["title"] == "Widget Prime"

@pytest.mark.regression
def test_extract_ecommerce_listing_keeps_id_product_links_over_productlist_facets() -> (
    None
):
    html = """
    <html>
      <body>
        <aside>
          <article class="product-card">
            <a href="/store/c/productlist/N=361945">
              <h2 class="product-title">Acne & Blemish Treatments</h2>
            </a>
          </article>
          <article class="product-card">
            <a href="/store/c/productlist/N=360500">
              <h2 class="product-title">Allergy Medications</h2>
            </a>
          </article>
        </aside>
        <main>
          <article class="product-card">
            <a href="/store/c/binaxnow-covid-19-antigen-rapid-self-test-at-home-kit/ID=300414527-product">
              <img src="/images/binax.jpg" alt="BinaxNOW COVID-19 Antigen Rapid Self-Test at Home Kit" />
              <h2 class="product-title">BinaxNOW COVID-19 Antigen Rapid Self-Test at Home Kit - 2 ea</h2>
            </a>
            <div class="price">$23.99</div>
          </article>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.walgreens.com/store/c/productlist/N=20007318",
        "ecommerce_listing",
        max_records=10,
    )

    assert len(rows) == 1
    assert rows[0]["url"] == (
        "https://www.walgreens.com/store/c/"
        "binaxnow-covid-19-antigen-rapid-self-test-at-home-kit/"
        "ID=300414527-product"
    )
    assert (
        rows[0]["title"]
        == "BinaxNOW COVID-19 Antigen Rapid Self-Test at Home Kit - 2 ea"
    )
    assert rows[0]["price"] == "23.99"

@pytest.mark.regression
def test_listing_identity_rejects_productlist_as_detail_marker() -> None:
    listing_url = "https://www.walgreens.com/store/c/productlist/N=20007318"
    product_url = (
        "https://www.walgreens.com/store/c/"
        "binaxnow-covid-19-antigen-rapid-self-test-at-home-kit/"
        "ID%3D300414527-product"
    )

    assert listing_detail_like_path(listing_url, is_job=False) is False
    assert listing_detail_like_path(product_url, is_job=False) is True

@pytest.mark.regression
def test_extract_ecommerce_listing_falls_back_to_original_dom_when_cleaned_dom_strips_card_headers() -> (
    None
):
    html = """
    <html>
      <body>
        <ul>
          <li>
            <article class="product-card">
              <header>
                <a href="https://www.indiamart.com/proddetail/widget-prime-123.html">
                  <img src="https://img.indiamart.com/widget-prime.jpg" alt="Widget Prime" />
                  <h2 class="product-title">Widget Prime</h2>
                </a>
              </header>
              <section class="product-info">
                <div class="price">₹71</div>
              </section>
            </article>
          </li>
        </ul>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://dir.indiamart.com/impcat/widgets.html",
        "ecommerce_listing",
        max_records=10,
    )

    assert len(rows) == 1
    assert (
        rows[0]["url"] == "https://www.indiamart.com/proddetail/widget-prime-123.html"
    )
    assert rows[0]["title"] == "Widget Prime"
    assert rows[0]["price"] == "71"
    assert rows[0]["image_url"] == "https://img.indiamart.com/widget-prime.jpg"

@pytest.mark.regression
def test_extract_ecommerce_listing_does_not_treat_repeated_testimonials_as_products() -> (
    None
):
    html = """
    <html>
      <body>
        <div class="quote">
          <span class="text">“The world as we have created it is a process of our thinking.”</span>
          <span>by <small class="author">Albert Einstein</small></span>
        </div>
        <div class="quote">
          <span class="text">“It is our choices that show what we truly are.”</span>
          <span>by <small class="author">J.K. Rowling</small></span>
        </div>
        <div class="quote">
          <span class="text">“There are only two ways to live your life.”</span>
          <span>by <small class="author">Albert Einstein</small></span>
        </div>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/testimonials",
        "ecommerce_listing",
        max_records=10,
    )

    assert rows == []

@pytest.mark.regression
def test_extract_ecommerce_listing_from_embedded_js_assignment_products() -> None:
    html = """
    <html>
      <body>
        <script>
          var products = [
            {
              "title": "Trail Runner",
              "url": "/products/trail-runner",
              "price": "109.95"
            },
            {
              "title": "Commuter Backpack",
              "url": "/products/commuter-backpack",
              "price": "89.50"
            }
          ];
        </script>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://store.example.com/collections/featured",
        "ecommerce_listing",
        max_records=10,
    )

    assert len(rows) == 2
    assert rows[0]["title"] == "Trail Runner"
    assert rows[0]["url"] == "https://store.example.com/products/trail-runner"
    assert rows[0]["_source"] == "structured_listing"

@pytest.mark.regression
def test_extract_records_emits_raw_json_array_items() -> None:
    raw_json = """
    [
      {"id": 1, "title": "Fjallraven Backpack", "price": 109.95, "description": "Travel pack"},
      {"id": 2, "title": "Mens Casual Tee", "price": 22.3, "description": "Cotton tee"}
    ]
    """

    rows = extract_records(
        raw_json,
        "https://fakestoreapi.com/products",
        "ecommerce_listing",
        max_records=10,
        content_type="application/json; charset=utf-8",
    )

    assert len(rows) == 2
    assert rows[0]["title"] == "Fjallraven Backpack"
    assert rows[0]["price"] == "109.95"
    assert rows[0]["_source"] == "raw_json"

@pytest.mark.regression
def test_extract_records_rejects_low_overlap_raw_json_array_items() -> None:
    raw_json = """
    [
      {"id": 1, "label": "Fjallraven Backpack", "permalink": "/products/fjallraven-backpack"},
      {"id": 2, "label": "Mens Casual Tee", "permalink": "/products/mens-casual-tee"}
    ]
    """

    rows = extract_records(
        raw_json,
        "https://store.example.com/api/products",
        "ecommerce_listing",
        max_records=10,
        content_type="application/json; charset=utf-8",
    )

    assert rows == []

@pytest.mark.regression
def test_extract_records_emits_nested_raw_json_list_items() -> None:
    raw_json = """
    {
      "products": [
        {"id": 1, "title": "Essence Mascara Lash Princess", "description": "Popular mascara", "price": 9.99, "brand": "Essence"},
        {"id": 2, "title": "Eyeshadow Palette", "description": "Neutral tones", "price": 19.99, "brand": "Glamour"}
      ],
      "total": 2
    }
    """

    rows = extract_records(
        raw_json,
        "https://dummyjson.com/products",
        "ecommerce_listing",
        max_records=10,
        content_type="application/json; charset=utf-8",
    )

    assert len(rows) == 2
    assert rows[0]["title"] == "Essence Mascara Lash Princess"
    assert rows[0]["description"] == "Popular mascara"
    assert rows[0]["brand"] == "Essence"

@pytest.mark.regression
def test_extract_records_rejects_low_overlap_nested_raw_json_list_items() -> None:
    raw_json = """
    {
      "data": {
        "entries": [
          {"id": 1, "label": "Trail Runner", "permalink": "/products/trail-runner"},
          {"id": 2, "label": "Commuter Backpack", "permalink": "/products/commuter-backpack"}
        ]
      }
    }
    """

    rows = extract_records(
        raw_json,
        "https://store.example.com/api/search",
        "ecommerce_listing",
        max_records=10,
        content_type="application/json; charset=utf-8",
    )

    assert rows == []

@pytest.mark.regression
def test_has_surface_field_overlap_short_circuits_after_required_matches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[int] = []
    original = extraction_runtime._payload_has_surface_field_overlap
    items = [
        {"title": f"Product {index}", "id": index} if index <= 5 else {"id": index}
        for index in range(1, 21)
    ]

    def _counting_overlap(payload, canonical, *, overlap_cache=None):
        calls.append(int(payload.get("id", 0)))
        return original(payload, canonical, overlap_cache=overlap_cache)

    monkeypatch.setattr(
        extraction_runtime,
        "_payload_has_surface_field_overlap",
        _counting_overlap,
    )

    assert (
        extraction_runtime._has_surface_field_overlap(
            items,
            surface="ecommerce_listing",
        )
        is True
    )
    assert calls == [1, 2, 3, 4, 5]

@pytest.mark.regression
def test_best_nested_listing_items_skips_variant_descendants_for_strong_products_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    overlap_calls: list[int] = []
    original = extraction_runtime._has_surface_field_overlap
    payload = {
        "products": [
            {
                "title": "Trail Runner",
                "price": "109.95",
                "variants": [{"size": "M"}, {"size": "L"}],
            },
            {
                "title": "Commuter Backpack",
                "price": "89.50",
                "variants": [{"size": "One Size"}],
            },
        ]
    }

    def _counting_overlap(items, *, surface):
        overlap_calls.append(len(items))
        return original(items, surface=surface)

    monkeypatch.setattr(
        extraction_runtime,
        "_has_surface_field_overlap",
        _counting_overlap,
    )

    result = extraction_runtime._best_nested_listing_items(
        payload,
        surface="ecommerce_listing",
    )

    assert result == payload["products"]
    assert overlap_calls == [2]

@pytest.mark.regression
def test_extract_records_emits_nested_graphql_listing_items() -> None:
    raw_json = """
    {
      "data": {
        "search": {
          "edges": [
            {
              "node": {
                "id": "sku-1",
                "title": "Trail Runner",
                "url": "/products/trail-runner",
                "price": "109.95"
              }
            },
            {
              "node": {
                "id": "sku-2",
                "title": "Commuter Backpack",
                "url": "/products/commuter-backpack",
                "price": "89.50"
              }
            }
          ]
        }
      }
    }
    """

    rows = extract_records(
        raw_json,
        "https://store.example.com/api/search",
        "ecommerce_listing",
        max_records=10,
        content_type="application/json; charset=utf-8",
    )

    assert len(rows) == 2
    assert rows[0]["title"] == "Trail Runner"
    assert rows[1]["url"] == "https://store.example.com/products/commuter-backpack"

@pytest.mark.regression
def test_extract_records_does_not_synthesize_listing_from_nested_json_without_items() -> (
    None
):
    raw_json = """
    {
      "data": {
        "search": {
          "summary": {
            "title": "Featured products",
            "description": "Top picks for spring"
          }
        }
      }
    }
    """

    rows = extract_records(
        raw_json,
        "https://store.example.com/api/search",
        "ecommerce_listing",
        max_records=10,
        content_type="application/json; charset=utf-8",
    )

    assert rows == []

@pytest.mark.regression
def test_extract_records_emits_xml_sitemap_listing_records() -> None:
    xml = """
    <?xml version="1.0" encoding="UTF-8"?>
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url>
        <loc>https://example.com/products/widget-prime</loc>
      </url>
      <url>
        <loc>https://example.com/products/widget-pro</loc>
      </url>
    </urlset>
    """

    rows = extract_records(
        xml,
        "https://example.com/media/sitemap-products.xml",
        "ecommerce_listing",
        max_records=10,
        content_type="application/xml; charset=utf-8",
    )

    assert len(rows) == 2
    assert rows[0]["_source"] == "xml_sitemap"
    assert rows[0]["url"] == "https://example.com/products/widget-prime"
    assert rows[0]["title"] == "widget prime"

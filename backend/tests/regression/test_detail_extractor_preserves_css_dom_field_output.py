from __future__ import annotations

from .test_selectolax_css_migration import (
    build_detail_record,
    extract_listing_records,
    pytest,
    read_optional_artifact_text,
)


@pytest.mark.regression
def test_detail_extractor_preserves_css_dom_field_output() -> None:
    html = """
    <html>
      <head>
        <title>Noise Title</title>
      </head>
      <body>
        <aside>
          <h1>Ignore This Title</h1>
          <div>$999.99</div>
        </aside>
        <main>
          <h1>Widget Prime</h1>
          <div class="price">$19.99</div>
          <p>Rated 4.8 out of 5 stars with 128 reviews</p>
        </main>
      </body>
    </html>
    """

    record = build_detail_record(
        html,
        "https://example.com/products/widget-prime",
        "ecommerce_detail",
        ["title", "price", "rating", "review_count"],
    )

    assert record["title"] == "Widget Prime"
    assert record["price"] == "19.99"
    assert record["rating"] == pytest.approx(4.8)
    assert record["review_count"] == 128


@pytest.mark.regression
def test_listing_extractor_preserves_css_card_field_output() -> None:
    html = """
    <html>
      <body>
        <nav>
          <article class="product-card">
            <a href="/products/ignore-me">
              <h2>Ignore Me</h2>
            </a>
            <div class="price">$999.99</div>
          </article>
        </nav>
        <section>
          <article class="product-card">
            <a href="/products/widget-prime">
              <img src="/images/widget-prime.jpg" alt="Widget Prime">
              <h2 class="product-title">Widget Prime</h2>
            </a>
            <div class="price">$19.99</div>
            <div>4.7 out of 5 stars 128 reviews</div>
          </article>
        </section>
      </body>
    </html>
    """

    rows = extract_listing_records(
        html,
        "https://example.com/collections/widgets",
        "ecommerce_listing",
        max_records=10,
    )

    assert len(rows) == 1
    assert rows[0]["title"] == "Widget Prime"
    assert rows[0]["url"] == "https://example.com/products/widget-prime"
    assert rows[0]["price"] == "19.99"
    assert rows[0]["image_url"] == "https://example.com/images/widget-prime.jpg"
    assert rows[0]["rating"] == pytest.approx(4.7)
    assert rows[0]["review_count"] == 128


@pytest.mark.regression
def test_listing_extractor_prefers_row_detail_link_and_name_over_breadcrumb_links() -> (
    None
):
    html = """
    <html>
      <body>
        <table class="catalog-list__body-main">
          <tr class="catalog-list__body-header">
            <td>Image</td>
            <td>Item No.</td>
            <td>Description</td>
          </tr>
          <tr>
            <td align="center">
              <span class="blCatalogImagePopup">
                <img
                  src="https://img.bricklink.com/ItemImage/ST/0/1428-1.t1.png"
                  alt="Set No: 1428 Name: Small Soccer Set 1 {Kabaya Version}"
                />
              </span>
            </td>
            <td nowrap>
              <a href="/v2/catalog/catalogitem.page?S=1428-1">1428-1</a>
              (<a href="catalogItemInv.asp?S=1428-1">Inv</a>)
            </td>
            <td>
              <strong>Small Soccer Set 1 {Kabaya Version}</strong>
              <br />
              20 Parts, 1 Minifigure, 2002
              <br />
              <a href="catalog.asp">Catalog</a>:
              <a href="catalogTree.asp?itemType=S">Sets</a>:
              <a href="/catalogList.asp?catType=S&catString=473">Sports</a>:
              <a href="/catalogList.asp?catType=S&catString=473.224">Soccer</a>
            </td>
          </tr>
          <tr>
            <td align="center">
              <span class="blCatalogImagePopup">
                <img
                  src="https://img.bricklink.com/ItemImage/ST/0/1428-2.t1.png"
                  alt="Set No: 1428 Name: Small Soccer Set 1 polybag"
                />
              </span>
            </td>
            <td nowrap>
              <a href="/v2/catalog/catalogitem.page?S=1428-2">1428-2</a>
              (<a href="catalogItemInv.asp?S=1428-2">Inv</a>)
            </td>
            <td>
              <strong>Small Soccer Set 1 polybag</strong>
              <br />
              20 Parts, 1 Minifigure, 2002
              <br />
              <a href="catalog.asp">Catalog</a>:
              <a href="catalogTree.asp?itemType=S">Sets</a>:
              <a href="/catalogList.asp?catType=S&catString=473">Sports</a>:
              <a href="/catalogList.asp?catType=S&catString=473.224">Soccer</a>
            </td>
          </tr>
        </table>
      </body>
    </html>
    """

    rows = extract_listing_records(
        html,
        "https://www.bricklink.com/catalogList.asp?catType=S&catString=473",
        "ecommerce_listing",
        max_records=10,
    )

    assert rows == [
        {
            "source_url": "https://www.bricklink.com/catalogList.asp?catType=S&catString=473",
            "_source": "dom_listing",
            "title": "Small Soccer Set 1 {Kabaya Version}",
            "image_url": "https://img.bricklink.com/ItemImage/ST/0/1428-1.t1.png",
            "url": "https://www.bricklink.com/v2/catalog/catalogitem.page?S=1428-1",
        },
        {
            "source_url": "https://www.bricklink.com/catalogList.asp?catType=S&catString=473",
            "_source": "dom_listing",
            "title": "Small Soccer Set 1 polybag",
            "image_url": "https://img.bricklink.com/ItemImage/ST/0/1428-2.t1.png",
            "url": "https://www.bricklink.com/v2/catalog/catalogitem.page?S=1428-2",
        },
    ]


@pytest.mark.regression
def test_listing_extractor_does_not_remove_body_for_sidebar_layouts() -> None:
    html = """
    <html>
      <body class="right-sidebar woocommerce-active">
        <main>
          <ul class="products columns-4">
            <li class="product">
              <a href="https://www.scrapingcourse.com/ecommerce/product/abominable-hoodie/" class="woocommerce-LoopProduct-link woocommerce-loop-product__link">
                <img src="https://www.scrapingcourse.com/ecommerce/wp-content/uploads/2024/03/mh09-blue_main.jpg" alt="">
                <h2 class="woocommerce-loop-product__title">Abominable Hoodie</h2>
                <span class="price">$69.00</span>
              </a>
            </li>
          </ul>
        </main>
      </body>
    </html>
    """

    rows = extract_listing_records(
        html,
        "https://www.scrapingcourse.com/ecommerce/",
        "ecommerce_listing",
        max_records=10,
    )

    assert rows == [
        {
            "source_url": "https://www.scrapingcourse.com/ecommerce/",
            "_source": "dom_listing",
            "title": "Abominable Hoodie",
            "price": "69.00",
            "currency": "USD",
            "image_url": "https://www.scrapingcourse.com/ecommerce/wp-content/uploads/2024/03/mh09-blue_main.jpg",
            "url": "https://www.scrapingcourse.com/ecommerce/product/abominable-hoodie/",
        }
    ]


@pytest.mark.regression
def test_listing_extractor_preserves_faceted_grid_results() -> None:
    html = """
    <html>
      <body>
        <div class="faceted-grid">
          <ul class="rc-listing-grid">
            <li class="rc-listing-grid__item">
              <article class="product-card">
                <a href="/item/alpha-strat">
                  <h2 class="product-title">Alpha Strat</h2>
                </a>
                <div class="price">$1,299.00</div>
              </article>
            </li>
          </ul>
        </div>
      </body>
    </html>
    """

    rows = extract_listing_records(
        html,
        "https://reverb.com/marketplace?product_type=electric-guitars",
        "ecommerce_listing",
        max_records=10,
    )

    assert rows == [
        {
            "source_url": "https://reverb.com/marketplace?product_type=electric-guitars",
            "_source": "dom_listing",
            "title": "Alpha Strat",
            "price": "1299.00",
            "currency": "USD",
            "url": "https://reverb.com/item/alpha-strat",
        }
    ]


@pytest.mark.regression
def test_listing_extractor_accepts_image_link_cards_with_separate_title_text() -> None:
    html = """
    <html>
      <body>
        <div class="product-card">
          <a href="/p/connect-in-colour-eyeshadow-palette-rose-lens?sku=2640287" aria-label="View product image">
            <img src="/images/rose-lens.jpg" alt="Connect In Colour Eyeshadow Palette Rose Lens">
          </a>
          <div class="product-brand">MAC</div>
          <div class="product-name">Connect In Colour Eyeshadow Palette Rose Lens</div>
          <div class="price">$35.00</div>
          <a href="/bag/add?sku=2640287">Add to bag</a>
        </div>
      </body>
    </html>
    """

    rows = extract_listing_records(
        html,
        "https://www.ulta.com/shop/makeup/makeup-palettes",
        "ecommerce_listing",
        max_records=10,
    )

    assert rows == [
        {
            "source_url": "https://www.ulta.com/shop/makeup/makeup-palettes",
            "_source": "dom_listing",
            "title": "Connect In Colour Eyeshadow Palette Rose Lens",
            "brand": "MAC",
            "price": "35.00",
            "currency": "USD",
            "image_url": "https://www.ulta.com/images/rose-lens.jpg",
            "url": "https://www.ulta.com/p/connect-in-colour-eyeshadow-palette-rose-lens?sku=2640287",
        }
    ]


@pytest.mark.regression
def test_listing_extractor_does_not_emit_additional_images() -> None:
    html = """
    <html>
      <body>
        <article class="product-card">
          <a href="/products/widget-prime">
            <img src="/images/widget-prime-main.jpg" alt="Widget Prime">
            <img src="/images/widget-prime-alt.jpg" alt="Widget Prime alternate">
            <h2 class="product-title">Widget Prime</h2>
          </a>
          <div class="price">$19.99</div>
        </article>
      </body>
    </html>
    """

    rows = extract_listing_records(
        html,
        "https://example.com/collections/widgets",
        "ecommerce_listing",
        max_records=10,
    )

    assert rows == [
        {
            "source_url": "https://example.com/collections/widgets",
            "_source": "dom_listing",
            "title": "Widget Prime",
            "price": "19.99",
            "currency": "USD",
            "image_url": "https://example.com/images/widget-prime-main.jpg",
            "url": "https://example.com/products/widget-prime",
        }
    ]


@pytest.mark.regression
def test_listing_extractor_prefers_explicit_price_node_over_description_mentions_and_keeps_currency() -> (
    None
):
    html = """
    <html>
      <body>
        <article class="product-card">
          <a href="/products/remastered">
            <img src="/images/remastered.jpg" alt="The Last of Us Remastered">
            <h2 class="product-title">The Last of Us Remastered</h2>
          </a>
          <p class="description">
            Includes additional game content: over $30 in value.
          </p>
          <div class="price-wrapper">92,99 €</div>
        </article>
      </body>
    </html>
    """

    rows = extract_listing_records(
        html,
        "https://sandbox.oxylabs.io/products",
        "ecommerce_listing",
        max_records=10,
    )

    assert rows == [
        {
            "source_url": "https://sandbox.oxylabs.io/products",
            "_source": "dom_listing",
            "title": "The Last of Us Remastered",
            "price": "92.99",
            "currency": "EUR",
            "image_url": "https://sandbox.oxylabs.io/images/remastered.jpg",
            "url": "https://sandbox.oxylabs.io/products/remastered",
        }
    ]


@pytest.mark.regression
def test_listing_extractor_avoids_numeric_title_nodes_when_real_title_exists() -> None:
    html = """
    <html>
      <body>
        <div class="product-card">
          <a href="/products/widget-prime" aria-label="Widget Prime">
            <img src="/images/widget-prime.jpg" alt="Widget Prime">
          </a>
          <div class="product-title">1</div>
          <div class="product-name">Widget Prime</div>
          <div class="price">$19.99</div>
        </div>
      </body>
    </html>
    """

    rows = extract_listing_records(
        html,
        "https://example.com/collections/widgets",
        "ecommerce_listing",
        max_records=10,
    )

    assert rows == [
        {
            "source_url": "https://example.com/collections/widgets",
            "_source": "dom_listing",
            "title": "Widget Prime",
            "price": "19.99",
            "currency": "USD",
            "image_url": "https://example.com/images/widget-prime.jpg",
            "url": "https://example.com/products/widget-prime",
        }
    ]


@pytest.mark.regression
def test_listing_extractor_filters_category_cloud_links_when_supported_product_tiles_exist() -> (
    None
):
    product_rows = "\n".join(
        f"""
        <li class="product-grid-product">
          <a href="/in/en/regular-fit-shirt-p44{i:02d}.html">
            <img src="/images/p{i}.jpg" alt="Regular Fit Shirt {i}">
            <span>Regular Fit Shirt {i}</span>
          </a>
          <span>₹ 3,950.00</span>
        </li>
        """
        for i in range(1, 13)
    )
    category_links = "\n".join(
        f'<li><a href="/in/en/man-shirts-l{index}.html">Men Shirts {index}</a></li>'
        for index in range(1, 10)
    )
    html = f"""
    <html>
      <body>
        <nav><ul>{category_links}</ul></nav>
        <main><ul class="product-grid">{product_rows}</ul></main>
      </body>
    </html>
    """

    rows = extract_listing_records(
        html,
        "https://www.zara.com/in/en/man-shirts-l737.html",
        "ecommerce_listing",
        max_records=20,
    )

    assert len(rows) == 12
    assert all("/regular-fit-shirt-p44" in row["url"] for row in rows)
    assert all("Men Shirts" not in row["title"] for row in rows)


@pytest.mark.parametrize(
    ("artifact_path", "url", "surface", "blocked_terms"),
    [
        (
            "artifacts/runs/8/pages/169dea1b9aaaa49e.html",
            "https://www.usajobs.gov/search/results/?k=software+engineer&p=1",
            "job_listing",
            ("sort by", "career explorer"),
        ),
        (
            "artifacts/runs/9/pages/4eabd73fbea7fd19.html",
            "https://startup.jobs/",
            "job_listing",
            ("bookmark apply",),
        ),
        (
            "artifacts/runs/19/pages/b1c15ef21f4b7b2d.html",
            "https://www.karenmillen.com/eu/categories/womens-trousers",
            "ecommerce_listing",
            ("flash promo", "code:"),
        ),
    ],
)
@pytest.mark.regression
def test_listing_extractor_filters_acceptance_artifact_noise(
    artifact_path: str,
    url: str,
    surface: str,
    blocked_terms: tuple[str, ...],
) -> None:
    html = read_optional_artifact_text(artifact_path)
    if html is None:
        pytest.skip(f"artifact fixture missing: {artifact_path}")

    rows = extract_listing_records(
        html,
        url,
        surface,
        max_records=10,
    )

    for row in rows:
        lowered_title = str(row.get("title") or "").lower()
        lowered_url = str(row.get("url") or "").lower()
        assert all(term not in lowered_title for term in blocked_terms)
        assert all(term not in lowered_url for term in blocked_terms)


@pytest.mark.regression
def test_job_listing_extractor_accepts_careerdetail_id_cards() -> None:
    html = """
    <html>
      <body>
        <ul>
          <li data-testid="careers-search-result-listing">
            <article class="mb-2">
              <a href="/careerdetail/?id=100901" class="listings__link bg-white rounded-lg p-4 md:p-6 text-left block">
                <div>
                  <img src="https://cdn.example.com/logo.png" alt="">
                  <h2 data-testid="careers-search-result-listing-job-title">
                    1st Shift Inbound Assistant Manager
                  </h2>
                  <span data-testid="careers-search-result-listing-company-name">
                    WebstaurantStore
                  </span>
                  <span data-testid="careers-search-result-listing-job-location">
                    <img src="https://cdn.example.com/vectorlocation.svg" alt="location:">
                    Dayton, NV
                  </span>
                </div>
              </a>
            </article>
          </li>
        </ul>
      </body>
    </html>
    """

    rows = extract_listing_records(
        html,
        "https://careers.clarkassociatesinc.biz/",
        "job_listing",
        max_records=10,
    )

    assert len(rows) == 1
    assert rows[0]["title"] == "1st Shift Inbound Assistant Manager"
    assert (
        rows[0]["url"]
        == "https://careers.clarkassociatesinc.biz/careerdetail/?id=100901"
    )


@pytest.mark.regression
def test_job_listing_extractor_rejects_footer_document_asset_rows() -> None:
    html = """
    <html>
      <body>
        <footer>
          <div>
            <p>
              © 2025 Lewis & Clark Behavioral Health
              <a href="https://lcbhs.net/privacy-policy/" title="Privacy Policy">Privacy Policy</a>
              <a href="https://lcbhs.net/wp-content/uploads/990-Posted-on-Website-2023.pdf"
                 title="LCBHS 990">LCBHS 990</a>
              <a href="https://productionmonkeys.com/" title="Production Monkeys">
                Website Design by Production Monkeys
              </a>
            </p>
          </div>
        </footer>
      </body>
    </html>
    """

    rows = extract_listing_records(
        html,
        "https://lcbhs.net/careers/",
        "job_listing",
        max_records=10,
    )

    assert rows == []


@pytest.mark.regression
def test_listing_extractor_ignores_none_embedded_json_payloads(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    html = """
    <html>
      <body>
        <section>
          <article class="product-card">
            <a href="/products/widget-prime">
              <h2>Widget Prime</h2>
            </a>
            <div>$19.99</div>
          </article>
        </section>
      </body>
    </html>
    """

    def _fake_structured_payloads(*args, **kwargs):
        del args, kwargs
        return (
            ("json_ld", []),
            ("microdata", []),
            ("opengraph", []),
            ("embedded_json", [None, {"@type": "ItemList", "itemListElement": []}]),
            ("js_state", []),
        )

    monkeypatch.setattr(
        "app.services.listing_extractor.collect_structured_source_payloads",
        _fake_structured_payloads,
    )

    rows = extract_listing_records(
        html,
        "https://example.com/collections/widgets",
        "ecommerce_listing",
        max_records=10,
    )

    assert rows == [
        {
            "source_url": "https://example.com/collections/widgets",
            "_source": "dom_listing",
            "title": "Widget Prime",
            "price": "19.99",
            "currency": "USD",
            "url": "https://example.com/products/widget-prime",
        }
    ]


@pytest.mark.regression
def test_detail_extractor_ignores_js_state_inside_removed_noise_containers() -> None:
    html = """
    <html>
      <body>
        <aside>
          <script type="application/json" id="__NEXT_DATA__">
          {
            "props": {
              "pageProps": {
                "product": {
                  "title": "Noise Widget",
                  "price": "999.99",
                  "description": "Sidebar state that should be ignored."
                }
              }
            }
          }
          </script>
        </aside>
        <main>
          <h1>Widget Prime</h1>
          <div class="price">$19.99</div>
          <p>Built from the primary content area.</p>
        </main>
      </body>
    </html>
    """

    record = build_detail_record(
        html,
        "https://example.com/products/widget-prime",
        "ecommerce_detail",
        ["title", "price", "description"],
    )

    assert record["title"] == "Widget Prime"
    assert record["price"] == "19.99"
    assert record["_source"] != "js_state"


@pytest.mark.regression
def test_listing_extractor_ignores_structured_payloads_inside_removed_noise_containers() -> (
    None
):
    html = """
    <html>
      <body>
        <aside>
          <script type="application/json">
          {
            "@type": "Product",
            "name": "Noise Widget",
            "url": "/products/noise-widget",
            "offers": {
              "price": "999.99"
            }
          }
          </script>
        </aside>
        <main>
          <article class="product-card">
            <a href="/products/widget-prime">
              <h2>Widget Prime</h2>
            </a>
            <div class="price">$19.99</div>
          </article>
        </main>
      </body>
    </html>
    """

    rows = extract_listing_records(
        html,
        "https://example.com/collections/widgets",
        "ecommerce_listing",
        max_records=10,
    )

    assert rows == [
        {
            "source_url": "https://example.com/collections/widgets",
            "_source": "dom_listing",
            "title": "Widget Prime",
            "price": "19.99",
            "currency": "USD",
            "url": "https://example.com/products/widget-prime",
        }
    ]

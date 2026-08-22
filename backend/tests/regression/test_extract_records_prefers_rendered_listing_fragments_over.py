from __future__ import annotations

from .test_crawl_engine import BelkAdapter, _rendered_listing_fragment, extract_listing_records, extract_records, extraction_runtime, pytest  # fmt: skip

@pytest.mark.regression
def test_extract_records_prefers_rendered_listing_fragments_over_thin_structured_records() -> (
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
              "@type": "Product",
              "name": "Widget Prime",
              "url": "/products/widget-prime"
            },
            {
              "@type": "Product",
              "name": "Widget Pro",
              "url": "/products/widget-pro"
            }
          ]
        }
        </script>
      </head>
      <body><div id="__next"></div></body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/collections/widgets",
        "ecommerce_listing",
        max_records=10,
        artifacts={
            "rendered_listing_fragments": [
                _rendered_listing_fragment(
                    title="Widget Prime",
                    url="https://example.com/products/widget-prime",
                    price="$19.99",
                    image_url="https://example.com/images/widget-prime.jpg",
                    brand="Acme",
                ),
                _rendered_listing_fragment(
                    title="Widget Pro",
                    url="https://example.com/products/widget-pro",
                    price="$29.99",
                    image_url="https://example.com/images/widget-pro.jpg",
                    brand="Acme",
                ),
            ]
        },
    )

    assert len(rows) == 2
    assert rows[0]["_source"] == "dom_listing"
    assert rows[0]["price"] == "19.99"
    assert rows[0]["image_url"] == "https://example.com/images/widget-prime.jpg"

@pytest.mark.regression
def test_extract_records_prefers_browser_visual_rows_over_weak_promo_dom_rows() -> None:
    html = """
    <html><body>
      <section>
        <a href="/handbags/">Sunnies Sunglasses Shop</a>
        <span>$50</span>
      </section>
      <section>
        <a href="/mothers-day/">Designer Handbags & Accessories</a>
        <span>$25</span>
      </section>
    </body></html>
    """

    rows = extract_records(
        html,
        "https://www.belk.com/home/",
        "ecommerce_listing",
        max_records=10,
        artifacts={
            "listing_visual_elements": [
                {
                    "tag": "a",
                    "text": "Super Soft Solid Microfiber Sheet Set",
                    "href": "https://www.belk.com/p/modern-southern-home--super-soft-solid-microfiber-sheet-set-/92007011175487.html",
                    "x": 10,
                    "y": 20,
                    "width": 220,
                    "height": 40,
                },
                {
                    "tag": "span",
                    "text": "$22.50",
                    "x": 10,
                    "y": 70,
                    "width": 80,
                    "height": 20,
                },
                {
                    "tag": "a",
                    "text": "Signature Bath Rug",
                    "href": "https://www.belk.com/p/modern-southern-home---signature-bath-rug/920089711724242.html",
                    "x": 10,
                    "y": 140,
                    "width": 220,
                    "height": 40,
                },
                {
                    "tag": "span",
                    "text": "$18.00",
                    "x": 10,
                    "y": 190,
                    "width": 80,
                    "height": 20,
                },
                {
                    "tag": "a",
                    "text": "Basic Bath Bundle",
                    "href": "https://www.belk.com/p/modern-southern-home--basic-bath-bundle-/920071211789570.html",
                    "x": 10,
                    "y": 260,
                    "width": 220,
                    "height": 40,
                },
                {
                    "tag": "span",
                    "text": "$34.00",
                    "x": 10,
                    "y": 310,
                    "width": 80,
                    "height": 20,
                },
            ]
        },
    )

    assert len(rows) == 3
    assert {row["_source"] for row in rows} == {"visual_listing"}
    assert {row["title"] for row in rows} == {
        "Super Soft Solid Microfiber Sheet Set",
        "Signature Bath Rug",
        "Basic Bath Bundle",
    }

@pytest.mark.regression
def test_extract_records_enriches_generic_listing_rows_from_matching_adapter_rows() -> (
    None
):
    html = """
    <html><body>
      <article class="product-card">
        <a href="/p/modern-southern-home--checkerboard-quilt-set/710097411786005.html">Checkerboard Quilt Set</a>
        <span>$22.50</span>
      </article>
    </body></html>
    """

    rows = extract_records(
        html,
        "https://www.belk.com/home/",
        "ecommerce_listing",
        max_records=10,
        adapter_records=[
            {
                "title": "Checkerboard Quilt Set",
                "brand": "Modern Southern Home",
                "url": "https://www.belk.com/p/modern-southern-home--checkerboard-quilt-set/710097411786005.html",
                "_source": "belk_adapter",
            }
        ],
    )

    assert rows[0]["_source"] == "dom_listing"
    assert rows[0]["brand"] == "Modern Southern Home"
    assert rows[0]["price"] == "22.50"

@pytest.mark.regression
def test_extract_records_prefers_myntra_adapter_rows_over_promo_category_dom_rows() -> (
    None
):
    rows = extract_records(
        "<html><body></body></html>",
        "https://www.myntra.com/men-jeans",
        "ecommerce_listing",
        max_records=10,
        artifacts={
            "rendered_listing_fragments": [
                _rendered_listing_fragment(
                    title="Dresses Under Rs.599",
                    url="https://www.myntra.com/fwdgenzcollection?f=Categories%3ADresses&rf=Price%3A0.0_600.0_0.0%20TO%20600.0",
                    price="Rs. 599",
                ),
                _rendered_listing_fragment(
                    title="Tops Under Rs.399",
                    url="https://www.myntra.com/fwdgenzcollection?f=Categories%3ATops&rf=Price%3A0.0_400.0_0.0%20TO%20400.0",
                    price="Rs. 399",
                ),
            ]
        },
        adapter_records=[
            {
                "title": "StyleCast x Revolte Men Wide Leg Mid-Rise Light Fade Jeans",
                "brand": "StyleCast x Revolte",
                "price": "1439",
                "image_url": "https://assets.myntassets.com/jeans.jpg",
                "url": "https://www.myntra.com/jeans/stylecast+x+revolte/stylecast-x-revolte-men-wide-leg-mid-rise-light-fade-jeans/37943174/buy",
                "_source": "myntra_adapter",
            }
        ],
    )

    assert len(rows) == 1
    assert rows[0]["_source"] == "myntra_adapter"
    assert (
        rows[0]["title"] == "StyleCast x Revolte Men Wide Leg Mid-Rise Light Fade Jeans"
    )

@pytest.mark.regression
def test_listing_integrity_gate_sees_cohort_failed_candidate_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        extraction_runtime.crawler_runtime_settings,
        "listing_cohort_homogeneity_min_ratio",
        1.01,
    )
    artifacts: dict[str, object] = {}

    rows = extract_listing_records(
        """
        <html><body>
          <article class="product-card"><a href="/products/alpha-shirt">Alpha Shirt</a><span>$10</span></article>
          <article class="product-card"><a href="/products/bravo-pants">Bravo Pants</a><span>$20</span></article>
        </body></html>
        """,
        "https://example.com/collections/all",
        "ecommerce_listing",
        max_records=10,
        artifacts=artifacts,
    )

    assert rows == []
    assert artifacts["listing_integrity"]["outcome"] == "promo_only_cluster"
    assert artifacts["listing_integrity"]["reason"] == "cohort_heterogeneous"

@pytest.mark.regression
def test_final_adapter_listing_set_refreshes_listing_integrity_artifact() -> None:
    artifacts: dict[str, object] = {}

    rows = extract_records(
        """
        <html><body>
          <article class="product-card"><a href="/c/promo-a">Promo A</a></article>
          <article class="product-card"><a href="/c/promo-b">Promo B</a></article>
        </body></html>
        """,
        "https://example.com/c/main",
        "ecommerce_listing",
        max_records=10,
        adapter_records=[
            {
                "title": "Real Product A",
                "url": "https://example.com/products/real-product-a",
                "price": "$10.00",
                "image_url": "https://example.com/a.jpg",
                "_source": "adapter",
            },
            {
                "title": "Real Product B",
                "url": "https://example.com/products/real-product-b",
                "price": "$20.00",
                "image_url": "https://example.com/b.jpg",
                "_source": "adapter",
            },
        ],
        artifacts=artifacts,
    )

    assert [row["title"] for row in rows] == ["Real Product A", "Real Product B"]
    assert artifacts["listing_integrity"]["outcome"] == "product_grid"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_belk_adapter_extracts_listing_brand_from_state_and_tiles() -> None:
    html = """
    <html>
      <body>
        <script>
          window.__INITIAL_STATE__ = {
            "search": {
              "products": [
                {
                  "productName": "Slim Straight Jeans",
                  "brandName": "Polo Ralph Lauren",
                  "productUrl": "/p/polo-ralph-lauren-slim-straight-jeans/123.html",
                  "salePrice": "$89.50",
                  "imageUrl": "https://belk.scene7.com/is/image/Belk/123"
                }
              ]
            }
          };
        </script>
        <article class="product-tile">
          <a href="/p/polo-ralph-lauren-slim-straight-jeans/123.html">
            <img src="https://belk.scene7.com/is/image/Belk/123" alt="Slim Straight Jeans">
            <span class="product-name">Slim Straight Jeans</span>
          </a>
          <span class="product-brand">Polo Ralph Lauren</span>
          <span class="price">$89.50</span>
        </article>
      </body>
    </html>
    """

    result = await BelkAdapter().extract(
        "https://www.belk.com/c/men-jeans/",
        html,
        "ecommerce_listing",
    )

    assert result.records[0]["brand"] == "Polo Ralph Lauren"
    assert result.records[0]["title"] == "Slim Straight Jeans"

@pytest.mark.regression
async def test_belk_adapter_extracts_detail_sku_upc_without_overwriting_sku() -> None:
    html = """
    <html>
      <body>
        <script>
          window.__INITIAL_STATE__ = {
            "product": {
              "productName": "511 Slim Fit Stretch Jeans",
              "brandName": "Levi's",
              "productUrl": "/p/levi-s-511-slim-fit-stretch-jeans/32009271204401.html",
              "salePrice": "$59.99",
              "imageUrl": "https://belk.scene7.com/is/image/Belk/3200927",
              "productId": "32009271204401",
              "sku": "32009271204401",
              "variants": [
                {
                  "color": "Dark Wash",
                  "sku_upc": "00194500874886"
                }
              ]
            }
          };
        </script>
      </body>
    </html>
    """

    result = await BelkAdapter().extract(
        "https://www.belk.com/p/levi-s-511-slim-fit-stretch-jeans/32009271204401.html",
        html,
        "ecommerce_detail",
    )

    assert result.records[0]["sku_upc"] == "00194500874886"
    assert result.records[0]["barcode"] == "00194500874886"
    assert result.records[0]["product_id"] == "32009271204401"
    assert result.records[0].get("sku") != "00194500874886"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_belk_adapter_extracts_title_brand_from_rendered_card_attrs() -> None:
    html = """
    <html><body>
      <article class="product-tile" data-cnstrc-item-name="Cuddlebed 2.0 Mattress Pad" data-cnstrc-item-id="92002171202220">
        <a href="/p/cuddlebed-cuddlebed-2-0-mattress-pad/92002171202220.html">
          <img alt="Cuddlebed 2.0 Mattress Pad" src="https://belk.scene7.com/is/image/Belk/9200217">
        </a>
        <span>$22.50</span>
      </article>
      <article class="product-tile" data-cnstrc-item-name="Crown &amp; Ivy™ Hydrangea Vase">
        <a href="/p/crown-ivy-hydrangea-vase/760161676226SPH0073IJ.html">
          <img alt="Crown &amp; Ivy™ Hydrangea Vase" src="https://belk.scene7.com/is/image/Belk/7601616">
        </a>
      </article>
    </body></html>
    """

    result = await BelkAdapter().extract(
        "https://www.belk.com/home/",
        html,
        "ecommerce_listing",
    )

    assert result.records[0]["title"] == "Cuddlebed 2.0 Mattress Pad"
    assert result.records[0]["brand"] == "Cuddlebed"
    assert result.records[0]["price"] == "22.50"
    assert result.records[0]["product_id"] == "92002171202220"
    assert result.records[1]["brand"] == "Crown & Ivy™"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_belk_adapter_dom_card_price_overrides_stale_state_price() -> None:
    html = """
    <html><body>
      <script>
        window.__BELK__ = {
          product: {
            name: "Wrangler Relaxed Bootcut Jeans",
            brand: "Wrangler",
            productUrl: "/p/wrangler--relaxed-bootcut-jeans-/3200040112342570.html",
            price: "50"
          }
        };
      </script>
      <article class="product-tile" data-cnstrc-item-name="Wrangler Relaxed Bootcut Jeans" data-cnstrc-item-id="3200040112342570">
        <a href="/p/wrangler--relaxed-bootcut-jeans-/3200040112342570.html">
          <img alt="Wrangler Relaxed Bootcut Jeans" src="https://belk.scene7.com/is/image/Belk/3200040">
        </a>
        <span class="product-brand">Wrangler</span>
        <span class="price">$39.95</span>
      </article>
    </body></html>
    """

    result = await BelkAdapter().extract(
        "https://www.belk.com/men/mens-clothing/jeans/",
        html,
        "ecommerce_listing",
    )

    assert result.records[0]["title"] == "Wrangler Relaxed Bootcut Jeans"
    assert result.records[0]["price"] == "39.95"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_belk_adapter_infers_brand_from_url_when_title_is_truncated() -> None:
    html = """
    <html><body>
      <article class="product-tile" data-cnstrc-item-name="500 Thread Count Damask Strip US Grown Cotton Softy-Around 95/5 Goose Feather/Down Pillow (2...">
        <a href="/p/beautyrest-500-thread-count-damask-stripe-us-grown-cotton-softy-around-95-5-goose-feather-down-pillow/92002171202220.html">
          <img alt="500 Thread Count Damask Strip US Grown Cotton Softy-Around 95/5 Goose Feather/Down Pillow (2..." src="https://belk.scene7.com/is/image/Belk/9200217">
        </a>
        <span>$75.50 - $95.50</span>
      </article>
    </body></html>
    """

    result = await BelkAdapter().extract(
        "https://www.belk.com/home/",
        html,
        "ecommerce_listing",
    )

    assert result.records[0]["brand"] == "Beautyrest"
    assert result.records[0]["price"] == "75.50"

@pytest.mark.regression
def test_listing_extractor_extracts_brand_from_product_tile() -> None:
    rows = extract_records(
        """
        <html><body>
          <article class="product-tile">
            <a href="/p/polo-ralph-lauren-slim-straight-jeans/123.html">
              <img src="/images/123.jpg" alt="Slim Straight Jeans">
              <span class="product-name">Slim Straight Jeans</span>
            </a>
            <span class="product-brand">Polo Ralph Lauren</span>
            <span class="price">$89.50</span>
          </article>
        </body></html>
        """,
        "https://www.belk.com/c/men-jeans/",
        "ecommerce_listing",
        max_records=10,
    )

    assert rows[0]["brand"] == "Polo Ralph Lauren"

@pytest.mark.regression
def test_listing_extractor_does_not_infer_belk_brand_from_pdp_slug_when_fragment_lacks_brand() -> (
    None
):
    rows = extract_records(
        """
        <html><body>
          <article>
            <a href="/p/polo-ralph-lauren-6-inch-polo-prepster-stretch-twill-shorts/320160211731376.html?dwvar_320160211731376_color=250312822425">
              <img src="/images/123.jpg" alt="6 Inch Polo Prepster Stretch Twill Shorts">
              <span>6 Inch Polo Prepster Stretch Twill Shorts</span>
            </a>
            <span class="price">$225.00</span>
          </article>
        </body></html>
        """,
        "https://www.belk.com/men/mens-clothing/shorts/",
        "ecommerce_listing",
        max_records=10,
    )

    assert "brand" not in rows[0]

@pytest.mark.regression
def test_extract_records_belk_listing_ignores_purchase_promo_price() -> None:
    rows = extract_records(
        """
        <html><body>
          <article class="product-tile">
            <a href="/p/izod--comfort-stretch-blue-denim-jeans-/3203394I39JN16.html">
              <img src="/images/jeans.jpg" alt="Comfort Stretch Blue Denim Jeans">
              <span>IZOD Comfort Stretch Blue Denim Jeans</span>
            </a>
            <div class="mb-2">
              <span class="font-bold text-red-600">$22.75</span>
              <span class="text-black line-through ml-2">$65.00</span>
            </div>
            <div class="text-xs font-bold text-blue-500">
              $39.99 Your Choice Effy Freshwater Pearl Pendant or Earrings with $50 Purchase
            </div>
          </article>
        </body></html>
        """,
        "https://www.belk.com/men/mens-clothing/jeans/",
        "ecommerce_listing",
        max_records=10,
    )

    assert rows[0]["price"] == "22.75"

@pytest.mark.regression
def test_extract_records_returns_sufficient_adapter_listing_without_dom_rescan() -> (
    None
):
    rows = extract_records(
        """
        <html><body>
          <article class="product-tile">
            <a href="/p/izod--comfort-stretch-blue-denim-jeans-/3203394I39JN16.html">
              <img src="/images/jeans-a.jpg" alt="Comfort Stretch Blue Denim Jeans">
              <span>IZOD Comfort Stretch Blue Denim Jeans</span>
            </a>
            <div class="text-xs font-bold text-blue-500">$50 Purchase</div>
          </article>
          <article class="product-tile">
            <a href="/p/wrangler--relaxed-bootcut-jeans-/3200040112342570.html">
              <img src="/images/jeans-b.jpg" alt="Relaxed Bootcut Jeans">
              <span>Wrangler Relaxed Bootcut Jeans</span>
            </a>
            <div class="text-xs font-bold text-blue-500">$50 Purchase</div>
          </article>
        </body></html>
        """,
        "https://www.belk.com/men/mens-clothing/jeans/",
        "ecommerce_listing",
        max_records=10,
        adapter_records=[
            {
                "title": "IZOD Comfort Stretch Blue Denim Jeans",
                "price": "22.75",
                "image_url": "https://www.belk.com/images/jeans-a.jpg",
                "url": "https://www.belk.com/p/izod--comfort-stretch-blue-denim-jeans-/3203394I39JN16.html",
                "_source": "belk_adapter",
            },
            {
                "title": "Wrangler Relaxed Bootcut Jeans",
                "price": "39.95",
                "image_url": "https://www.belk.com/images/jeans-b.jpg",
                "url": "https://www.belk.com/p/wrangler--relaxed-bootcut-jeans-/3200040112342570.html",
                "_source": "belk_adapter",
            },
        ],
    )

    assert [row["price"] for row in rows] == ["22.75", "39.95"]
    assert {row["_source"] for row in rows} == {"belk_adapter"}

@pytest.mark.regression
def test_extract_records_prefers_generic_listing_rows_over_thin_adapter_rows() -> None:
    rows = extract_records(
        "<html><body></body></html>",
        "https://www.myntra.com/hand-towels",
        "ecommerce_listing",
        max_records=10,
        adapter_records=[
            {
                "title": "Microfiber Face Towel",
                "url": "https://www.myntra.com/products/microfiber-face-towel",
                "brand": "Personal Touch Skincare",
                "_source": "myntra_adapter",
            }
        ],
        artifacts={
            "rendered_listing_fragments": [
                _rendered_listing_fragment(
                    title="Microfiber Face Towel",
                    url="https://www.myntra.com/products/microfiber-face-towel",
                    price="Rs. 499",
                    image_url="https://assets.myntassets.com/assets/images/towel.jpg",
                    brand="Personal Touch Skincare",
                )
            ]
        },
    )

    assert rows == [
        {
            "source_url": "https://www.myntra.com/hand-towels",
            "_source": "dom_listing",
            "title": "Microfiber Face Towel",
            "url": "https://www.myntra.com/products/microfiber-face-towel",
            "price": "499",
            "currency": "INR",
            "image_url": "https://assets.myntassets.com/assets/images/towel.jpg",
            "brand": "Personal Touch Skincare",
        }
    ]

@pytest.mark.regression
def test_extract_records_drops_rendered_listing_utility_rows_when_real_products_exist() -> (
    None
):
    rows = extract_records(
        "<html><body></body></html>",
        "https://example.com/collections/widgets",
        "ecommerce_listing",
        max_records=10,
        artifacts={
            "rendered_listing_fragments": [
                _rendered_listing_fragment(
                    title="Product Help",
                    url="https://example.com/help/product-help",
                ),
                _rendered_listing_fragment(
                    title="Widget Prime",
                    url="https://example.com/products/widget-prime",
                    price="$19.99",
                    image_url="https://example.com/images/widget-prime.jpg",
                ),
                _rendered_listing_fragment(
                    title="Widget Pro",
                    url="https://example.com/products/widget-pro",
                    price="$29.99",
                    image_url="https://example.com/images/widget-pro.jpg",
                ),
            ]
        },
    )

    assert [row["title"] for row in rows] == ["Widget Prime", "Widget Pro"]
    assert all("/products/" in row["url"] for row in rows)

@pytest.mark.regression
def test_extract_records_drops_detail_like_category_links_without_product_signals() -> (
    None
):
    rows = extract_records(
        "<html><body></body></html>",
        "https://www.customink.com/products/sweatshirts/hoodies/71",
        "ecommerce_listing",
        max_records=10,
        artifacts={
            "rendered_listing_fragments": [
                _rendered_listing_fragment(
                    title="Short Sleeve T-shirts",
                    url="https://www.customink.com/products/t-shirts/short-sleeve-t-shirts/16",
                ),
                _rendered_listing_fragment(
                    title="Women's T-shirts",
                    url="https://www.customink.com/products/t-shirts/womens-t-shirts/104",
                ),
                _rendered_listing_fragment(
                    title="Independent Trading Midweight Hooded Sweatshirt",
                    url="https://www.customink.com/products/hoodies/independent-trading-midweight-hooded-sweatshirt/827800",
                    price="$39.99",
                    image_url="https://www.customink.com/images/hoodie-1.jpg",
                ),
                _rendered_listing_fragment(
                    title="Gildan Heavy Blend Hooded Sweatshirt",
                    url="https://www.customink.com/products/hoodies/gildan-heavy-blend-hooded-sweatshirt/836000",
                    price="$29.99",
                    image_url="https://www.customink.com/images/hoodie-2.jpg",
                ),
            ]
        },
    )

    assert [row["title"] for row in rows] == [
        "Independent Trading Midweight Hooded Sweatshirt",
        "Gildan Heavy Blend Hooded Sweatshirt",
    ]

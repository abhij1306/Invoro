from __future__ import annotations

from .test_crawl_engine import detail_extractor, detail_identity_codes_from_url, detail_title_from_url, extract_records, pytest, read_optional_artifact_text  # fmt: skip


@pytest.mark.regression
def test_detail_identity_allows_canonical_product_url_with_variant_sku_suffix() -> None:
    requested_url = (
        "https://savannahs.com/collections/all-boots/products/"
        "shadow-ban-30-soft-leather-black-boots-hl28112s"
    )
    record = {
        "title": "Shadow Ban 30 soft leather black boots - 36",
        "url": (
            "https://savannahs.com/products/"
            "shadow-ban-30-soft-leather-black-boots-hl28112s?variant=43633735827522"
        ),
        "sku": "HL28112S360",
        "description": "Black leather ankle boots from Herbert Levine.",
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
def test_detail_identity_allows_canonical_url_with_reordered_query_after_redirect() -> (
    None
):
    requested_url = (
        "https://www.converse.com/shop/p/"
        "chuck-taylor-all-star-retro-embroidery-womens-high-top-shoe/A16914F.html"
        "?dwvar_A16914F_color=black%2Fnew%20found%20bloom"
        "&dwvar_A16914F_width=standard&styleNo=A16914F&cgid=womens-high-top-shoes"
    )
    current_url = requested_url.replace("-womens-", "-unisex-")
    record = {
        "title": "Chuck Taylor All Star Retro Embroidery",
        "url": (
            "https://www.converse.com/shop/p/"
            "chuck-taylor-all-star-retro-embroidery-womens-high-top-shoe/A16914F.html"
            "?cgid=womens-high-top-shoes&dwvar_A16914F_color=black%2Fnew%20found%20bloom"
            "&styleNo=A16914F&dwvar_A16914F_width=standard"
        ),
        "price": "70.00",
        "image_url": "https://www.converse.com/images/A16914F.jpg",
    }

    assert (
        detail_extractor.detail_record_rejection_reason(
            record,
            page_url=current_url,
            requested_page_url=requested_url,
        )
        is None
    )


@pytest.mark.regression
def test_detail_identity_extracts_numeric_hm_product_codes_from_url() -> None:
    url = "https://www2.hm.com/en_in/productpage.1317259001.html"

    assert detail_identity_codes_from_url(url) == {"1317259001"}
    assert detail_title_from_url(url) is None


@pytest.mark.regression
def test_extract_records_rejects_visual_artifact_cta_and_footer_clusters() -> None:
    rows = extract_records(
        "<html><body></body></html>",
        "https://www.dyson.in/hair-care/hair-stylers",
        "ecommerce_listing",
        max_records=10,
        artifacts={
            "listing_visual_elements": [
                {
                    "tag": "a",
                    "href": "/airwrap-id-multi-styler-dryer-vinca-blue-topaz",
                    "x": 557,
                    "y": 3347,
                    "width": 142,
                    "height": 22,
                    "text": "",
                },
                {
                    "tag": "a",
                    "href": "/airwrap-id-multi-styler-dryer-vinca-blue-topaz",
                    "x": 510,
                    "y": 4026,
                    "width": 236,
                    "height": 68,
                    "text": "Shop now",
                },
                {
                    "tag": "img",
                    "src": "https://dyson-h.assetsadobe2.com/is/image/content/dam/dyson/images/back-up/tick-outline-green.png?scl=1&fmt=png-alpha",
                    "x": 520,
                    "y": 3958,
                    "width": 24,
                    "height": 24,
                    "text": "",
                },
                {
                    "tag": "a",
                    "href": "/products/hair-care/hair-care-accessories",
                    "x": 115,
                    "y": 8048,
                    "width": 478,
                    "height": 40,
                    "text": "",
                },
                {
                    "tag": "h2",
                    "text": "Talking to us is easy.",
                    "x": 115,
                    "y": 7969,
                    "width": 478,
                    "height": 68,
                },
                {
                    "tag": "img",
                    "src": "https://dyson-h.assetsadobe2.com/is/image/content/dam/dyson/icons/owner-footer/mydyson/haircare-icon.png?scl=1&fmt=png-alpha",
                    "x": 120,
                    "y": 7890,
                    "width": 48,
                    "height": 48,
                    "text": "",
                },
                {
                    "tag": "a",
                    "href": "https://www.dyson.in/select-your-location",
                    "x": 1281,
                    "y": 8586,
                    "width": 74,
                    "height": 22,
                    "text": "India",
                    "ariaLabel": "select language and region: India",
                },
            ]
        },
    )

    assert rows == []


@pytest.mark.regression
def test_extract_records_keeps_visual_artifact_product_without_price_when_title_matches_url() -> (
    None
):
    rows = extract_records(
        "<html><body></body></html>",
        "https://www.dyson.in/hair-care/hair-stylers",
        "ecommerce_listing",
        max_records=10,
        artifacts={
            "listing_visual_elements": [
                {
                    "tag": "a",
                    "href": "/airwrap-id-multi-styler-dryer-vinca-blue-topaz",
                    "x": 557,
                    "y": 3347,
                    "width": 142,
                    "height": 22,
                    "text": "",
                },
                {
                    "tag": "h2",
                    "text": "Airwrap i.d. multi-styler and dryer Vinca Blue/Topaz",
                    "x": 510,
                    "y": 3440,
                    "width": 236,
                    "height": 68,
                },
                {
                    "tag": "img",
                    "src": "https://example.com/images/airwrap-id.jpg",
                    "alt": "Airwrap i.d. multi-styler and dryer Vinca Blue/Topaz",
                    "x": 510,
                    "y": 3508,
                    "width": 236,
                    "height": 236,
                    "text": "",
                },
            ]
        },
    )

    assert rows == [
        {
            "source_url": "https://www.dyson.in/hair-care/hair-stylers",
            "_source": "visual_listing",
            "title": "Airwrap i.d. multi-styler and dryer Vinca Blue/Topaz",
            "image_url": "https://example.com/images/airwrap-id.jpg",
            "url": "https://www.dyson.in/airwrap-id-multi-styler-dryer-vinca-blue-topaz",
        }
    ]


@pytest.mark.regression
def test_extract_records_reads_listing_card_data_url_and_rejects_chrome_rows() -> None:
    rows = extract_records(
        """
        <html><body>
          <div class="promos__item promos_title_content">
            <a href="/products/hair-care/hair-care-accessories">Explore accessories</a>
          </div>
          <ul class="products-grid">
            <li class="item product product-item">
              <div class="product-item-link" data-url="/hair-care/hair-straighteners/airstrait-blue-copper">
                <img src="/airstrait-blue.png" alt="">
                <h3 class="card_product_name">
                  <a class="product name product-item-name">Dyson Airstrait dryer and straightener Blue Copper</a>
                </h3>
                <span class="price">₹34,900.00</span>
                <a href="javascript:void(0)">Add to cart</a>
              </div>
            </li>
            <li class="item product product-item">
              <div class="product-item-link" data-url="/hair-care/hair-straighteners/corrale-copper-nickel">
                <img src="/corrale.png" alt="">
                <h3 class="card_product_name">
                  <a class="product name product-item-name">Dyson Corrale straightener Copper Nickel</a>
                </h3>
                <span class="price">₹29,900.00</span>
                <a href="javascript:void(0)">Add to cart</a>
              </div>
            </li>
          </ul>
        </body></html>
        """,
        "https://www.dyson.in/hair-care/hair-straighteners",
        "ecommerce_listing",
        max_records=10,
    )

    assert [row["title"] for row in rows] == [
        "Dyson Airstrait dryer and straightener Blue Copper",
        "Dyson Corrale straightener Copper Nickel",
    ]
    assert rows[0]["url"] == (
        "https://www.dyson.in/hair-care/hair-straighteners/airstrait-blue-copper"
    )
    assert rows[0]["price"] == "34900.00"


@pytest.mark.regression
def test_extract_records_keeps_adjacent_visual_product_cards_separate() -> None:
    rows = extract_records(
        "<html><body></body></html>",
        "https://www.belk.com/beauty/makeup/face-makeup/",
        "ecommerce_listing",
        max_records=10,
        artifacts={
            "listing_visual_elements": [
                {
                    "tag": "img",
                    "href": "/p/brand-alpha-foundation/111.html",
                    "src": "/images/alpha-a.jpg",
                    "alt": "Alpha Foundation",
                    "x": 204,
                    "y": 582,
                    "width": 349,
                    "height": 499,
                    "text": "",
                },
                {
                    "tag": "img",
                    "href": "/p/brand-alpha-foundation/111.html",
                    "src": "/images/alpha-b.jpg",
                    "alt": "Alpha Foundation",
                    "x": 204,
                    "y": 582,
                    "width": 349,
                    "height": 499,
                    "text": "",
                },
                {
                    "tag": "img",
                    "href": "/p/brand-beta-concealer/222.html",
                    "src": "/images/beta-a.jpg",
                    "alt": "Beta Concealer",
                    "x": 587,
                    "y": 582,
                    "width": 349,
                    "height": 499,
                    "text": "",
                },
                {
                    "tag": "img",
                    "href": "/p/brand-gamma-powder/333.html",
                    "src": "/images/gamma-a.jpg",
                    "alt": "Gamma Powder",
                    "x": 970,
                    "y": 582,
                    "width": 349,
                    "height": 499,
                    "text": "",
                },
            ]
        },
    )

    assert [row["title"] for row in rows] == [
        "Alpha Foundation",
        "Beta Concealer",
        "Gamma Powder",
    ]
    assert [row["url"] for row in rows] == [
        "https://www.belk.com/p/brand-alpha-foundation/111.html",
        "https://www.belk.com/p/brand-beta-concealer/222.html",
        "https://www.belk.com/p/brand-gamma-powder/333.html",
    ]


@pytest.mark.regression
def test_extract_records_rejects_visual_artifact_auth_links_without_dropping_product() -> (
    None
):
    rows = extract_records(
        "<html><body></body></html>",
        "https://www.customink.com/products/sweatshirts/hoodies/71",
        "ecommerce_listing",
        max_records=10,
        artifacts={
            "listing_visual_elements": [
                {
                    "tag": "a",
                    "href": "https://www.customink.com/profiles/users/sign_in",
                    "x": 24,
                    "y": 120,
                    "width": 160,
                    "height": 24,
                    "text": "Sign In",
                },
                {
                    "tag": "h2",
                    "text": "Sign In Sign In",
                    "x": 24,
                    "y": 148,
                    "width": 180,
                    "height": 28,
                },
                {
                    "tag": "a",
                    "href": "https://www.customink.com/products/hoodies/independent-trading-midweight-hooded-sweatshirt/827800",
                    "x": 24,
                    "y": 220,
                    "width": 220,
                    "height": 32,
                    "text": "",
                },
                {
                    "tag": "img",
                    "src": "https://www.customink.com/images/hoodie-1.jpg",
                    "x": 24,
                    "y": 220,
                    "width": 160,
                    "height": 160,
                    "text": "",
                },
                {
                    "tag": "h2",
                    "text": "Independent Trading Midweight Hooded Sweatshirt",
                    "x": 24,
                    "y": 388,
                    "width": 340,
                    "height": 28,
                },
                {
                    "tag": "div",
                    "text": "$39.99",
                    "x": 24,
                    "y": 420,
                    "width": 80,
                    "height": 24,
                },
            ]
        },
    )

    assert rows == [
        {
            "source_url": "https://www.customink.com/products/sweatshirts/hoodies/71",
            "_source": "visual_listing",
            "title": "Independent Trading Midweight Hooded Sweatshirt",
            "price": "39.99",
            "currency": "USD",
            "image_url": "https://www.customink.com/images/hoodie-1.jpg",
            "url": "https://www.customink.com/products/hoodies/independent-trading-midweight-hooded-sweatshirt/827800",
        }
    ]


@pytest.mark.regression
def test_extract_records_prefers_image_hint_over_brand_or_review_title_noise() -> None:
    html = """
    <html>
      <body>
        <article class="product-tile">
          <a href="/p/laila-small-satchel/260083130S5S9IS1V.html">
            <img src="/images/laila.jpg" alt="Laila Small Satchel">
          </a>
          <div class="tile-copy">
            <a href="/p/laila-small-satchel/260083130S5S9IS1V.html">
              <div class="font-bold">MICHAEL Michael Kors</div>
            </a>
            <a href="/p/laila-small-satchel/260083130S5S9IS1V.html">
              <div class="line-clamp-2">Laila Small Satchel</div>
            </a>
          </div>
          <a href="/p/laila-small-satchel/260083130S5S9IS1V.html">428 reviews</a>
          <div class="price">$118.80</div>
        </article>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.belk.com/handbags",
        "ecommerce_listing",
        max_records=10,
    )

    assert rows == [
        {
            "source_url": "https://www.belk.com/handbags",
            "_source": "dom_listing",
            "title": "Laila Small Satchel",
            "price": "118.80",
            "currency": "USD",
            "review_count": 428,
            "image_url": "https://www.belk.com/images/laila.jpg",
            "url": "https://www.belk.com/p/laila-small-satchel/260083130S5S9IS1V.html",
        }
    ]


@pytest.mark.regression
def test_extract_records_filters_blocked_detail_artifact_html() -> None:
    html = read_optional_artifact_text(
        "artifacts/runs/20/pages/41f3046f3de7bf0e.html",
        fixture_subdir="artifact_html",
    )

    rows = extract_records(
        html,
        "https://www.belk.com/p/michael-michael-kors-scarlett-medium-satchel-/260083130F4GETS2B.html",
        "ecommerce_detail",
        max_records=5,
    )

    assert rows == []


@pytest.mark.regression
def test_extract_records_cleans_titles_from_belk_listing_artifact() -> None:
    html = read_optional_artifact_text(
        "artifacts/runs/19/pages/a0c2607fa750138d.html",
        fixture_subdir="artifact_html",
    )

    rows = extract_records(
        html,
        "https://www.belk.com/shop-by-brand",
        "ecommerce_listing",
        max_records=12,
    )

    assert rows
    titles = {str(row.get("title") or "") for row in rows[:12]}
    assert "Laila Small Satchel" in titles
    assert "Lucca Leather Hobo Bag" in titles
    assert all("review" not in str(row.get("title") or "").lower() for row in rows[:12])
    assert "Dooney & Bourke" not in titles


@pytest.mark.regression
def test_extract_records_belk_listing_artifact_does_not_emit_currency_without_price() -> (
    None
):
    html = read_optional_artifact_text(
        "artifacts/runs/22/pages/5e2f27bc09df481d.html",
        fixture_subdir="artifact_html",
    )

    rows = extract_records(
        html,
        "https://www.belk.com/men/mens-clothing/pants/",
        "ecommerce_listing",
        max_records=100,
    )

    assert rows
    assert all(row.get("price") or not row.get("currency") for row in rows)


@pytest.mark.regression
def test_extract_records_drops_orphan_listing_currency_without_price() -> None:
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
                    "name": "Widget Prime",
                    "url": "https://example.com/products/widget-prime",
                    "offers": {
                      "@type": "Offer",
                      "priceCurrency": "USD"
                    }
                  }
                }
              ]
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
        max_records=5,
    )

    assert rows == [
        {
            "source_url": "https://example.com/collections/widgets",
            "_source": "structured_listing",
            "title": "Widget Prime",
            "url": "https://example.com/products/widget-prime",
        }
    ]


@pytest.mark.regression
def test_extract_records_rejects_redirected_belk_detail_artifact_identity_mismatch() -> (
    None
):
    html = read_optional_artifact_text(
        "artifacts/runs/23/pages/ee049a2bdeed124a.html",
        fixture_subdir="artifact_html",
    )
    requested_url = (
        "https://www.belk.com/p/haggar-premium-stretch-no-iron-khaki-classic-fit-hidden-expandable-"
        "waistband-flat-front-pants/3200645HC10884.html?dwvar_3200645HC10884_color=251278239931"
    )
    canonical_url = "https://www.belk.com/p/kenneth-cole-mens-reaction-urban-heather-dress-pants-/3200898KD00379.html"

    rows = extract_records(
        html,
        canonical_url,
        "ecommerce_detail",
        max_records=5,
        requested_page_url=requested_url,
    )

    assert rows == []


@pytest.mark.regression
def test_extract_records_recovers_variants_and_cleans_color_from_belk_detail_artifact() -> (
    None
):
    html = read_optional_artifact_text(
        "artifacts/runs/23/pages/ee049a2bdeed124a.html",
        fixture_subdir="artifact_html",
    )
    canonical_url = "https://www.belk.com/p/kenneth-cole-mens-reaction-urban-heather-dress-pants-/3200898KD00379.html"

    rows = extract_records(
        html,
        canonical_url,
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert "color" not in record
    assert record["variants"][0]["color"] == "HTR GREY"
    assert record["variant_count"] == 6


@pytest.mark.regression
def test_extract_records_normalizes_belk_run_26_detail_variants_without_duplicate_axes() -> (
    None
):
    html = read_optional_artifact_text(
        "artifacts/runs/26/pages/612cf7570cdbf8e1.html",
        fixture_subdir="artifact_html",
    )
    canonical_url = (
        "https://www.belk.com/p/kim-rogers-womens-denim-capri-pants/180430334287262.html"
        "?dwvar_180430334287262_color=460475611850"
    )

    rows = extract_records(
        html,
        canonical_url,
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["title"] == "Women's Denim Capri Pants"
    assert record["availability"] == "in_stock"
    assert len(record["variants"]) == 21
    assert all("price" not in variant for variant in record["variants"])
    assert all("currency" not in variant for variant in record["variants"])
    assert all("availability" not in variant for variant in record["variants"])

    def _has_axis(variant: dict) -> bool:
        if variant.get("color") or variant.get("size"):
            return True
        option_values = variant.get("option_values")
        return isinstance(option_values, dict) and any(
            option_values.get(axis) for axis in ("color", "size")
        )

    assert all(_has_axis(variant) for variant in record["variants"])


@pytest.mark.regression
def test_extract_records_normalizes_boolean_availability_and_shared_variant_price_from_json() -> (
    None
):
    html = """
    {
      "title": "Trail Runner",
      "price": "26.99",
      "currency": "USD",
      "availability": true,
      "variant_axes": {
        "size": ["6", "8"],
        "color": ["Blue", "Black"]
      },
      "variants": [
        {"option_values": {"size": "6", "color": "Blue"}},
        {"option_values": {"size": "8", "color": "Blue"}}
      ],
      "selected_variant": {
        "option_values": {"size": "6", "color": "Blue"}
      }
    }
    """

    rows = extract_records(
        html,
        "https://example.com/products/trail-runner",
        "ecommerce_detail",
        max_records=5,
        content_type="application/json",
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["availability"] == "in_stock"
    assert record["price"] == "26.99"
    assert record["currency"] == "USD"

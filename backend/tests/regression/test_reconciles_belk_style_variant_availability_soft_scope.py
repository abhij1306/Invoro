from __future__ import annotations

from .test_detail_extractor_structured_sources import build_detail_record, extract_detail_records, extract_records, pytest, read_optional_artifact_text  # fmt: skip


@pytest.mark.regression
def test_reconciles_belk_style_variant_availability_from_soft_scope() -> None:
    html = """
    <html>
      <body>
        <main>
          <h1>Belk Shirt</h1>
          <div class="pdp-swatch">
            <button aria-label="Select Black color" value="048001">Black</button>
          </div>
          <div class="border-gray-200">
            <div role="radiogroup" class="grid gap-3">
              <label><button role="radio" value="10965_S"></button>S</label>
              <label><button role="radio" value="10970_M" disabled data-disabled=""></button>M</label>
            </div>
          </div>
        </main>
      </body>
    </html>
    """

    rows = extract_detail_records(
        html,
        "https://www.belk.com/p/belk-shirt/123.html",
        "ecommerce_detail",
        adapter_records=[
            {
                "title": "Belk Shirt",
                "price": "10.00",
                "image_url": "https://www.belk.com/image.jpg",
                "availability": "in_stock",
                "variants": [{"size": "S"}, {"size": "M"}],
            }
        ],
    )

    assert len(rows) == 1
    variants = rows[0]["variants"]
    assert variants == [
        {"size": "S", "availability": "in_stock"},
        {
            "size": "M",
            "availability": "out_of_stock",
            "stock_quantity": 0,
        },
    ]


@pytest.mark.regression
def test_recovers_nike_artifact_available_variant_labels() -> None:
    html = read_optional_artifact_text("artifacts/runs/1/pages/1bcb5c849a75b86f.html")

    rows = extract_detail_records(
        html,
        "https://www.nike.com/t/air-force-1-07-mens-shoes-jBrhbr/CW2288-111",
        "ecommerce_detail",
    )

    assert len(rows) == 1
    variants = rows[0]["variants"]
    assert len(variants) == 19
    assert {row.get("availability") for row in variants} <= {None, "in_stock"}
    assert variants[0]["size"].startswith("M ")


@pytest.mark.regression
def test_extract_detail_variants_from_plain_buttons_without_data_attributes() -> None:
    html = """
    <html>
      <body>
        <main>
          <h1>Widget Prime</h1>
          <div role="radiogroup" aria-label="Size">
            <button type="button" aria-pressed="true">S</button>
            <button type="button">M</button>
            <button type="button">L</button>
          </div>
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
    assert record["variants"] == [{"size": "S"}, {"size": "M"}, {"size": "L"}]
    assert record["variant_count"] == 3


@pytest.mark.regression
def test_extract_automobile_detail_ignores_irrelevant_video_json_ld_when_dom_title_exists() -> (
    None
):
    html = """
    <html>
      <head>
        <link rel="canonical" href="https://www.autotrader.co.uk/cars/leasing/product/202402287036788" />
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "VideoObject",
          "name": "NEW Abarth 500E: The LOUDEST Electric Car! 4K",
          "description": "Promo video copy that is not the vehicle detail.",
          "thumbnailUrl": "https://m.atcdn.co.uk/a/media/w800/b75b88d781b647dcb7f8a802e7b6fa8e.jpg",
          "publisher": {
            "@type": "Organization",
            "name": "Auto Trader",
            "logo": {
              "@type": "ImageObject",
              "url": "https://m.atcdn.co.uk/static/media/logos/autotrader-logo.png"
            }
          }
        }
        </script>
      </head>
      <body>
        <main>
          <h1>Abarth 500e 42kWh Turismo Auto 3dr</h1>
          <p>Lease deal available now.</p>
          <img src="https://m.atcdn.co.uk/a/media/w800/b75b88d781b647dcb7f8a802e7b6fa8e.jpg" alt="Abarth 500e 42kWh Turismo Auto 3dr" />
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.autotrader.co.uk/cars/leasing/product/202402287036788",
        "automobile_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["title"] == "Abarth 500e 42kWh Turismo Auto 3dr"
    assert (
        record["url"]
        == "https://www.autotrader.co.uk/cars/leasing/product/202402287036788"
    )
    assert record["_source"] == "dom_h1"


@pytest.mark.regression
def test_extract_automobile_detail_accepts_vehicle_json_ld_title_and_image() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Vehicle",
          "name": "Roadster GT",
          "image": "https://example.com/roadster.jpg",
          "url": "https://example.com/cars/roadster-gt"
        }
        </script>
      </head>
      <body></body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/cars/roadster-gt",
        "automobile_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["title"] == "Roadster GT"
    assert record["image_url"] == "https://example.com/roadster.jpg"
    assert record["url"] == "https://example.com/cars/roadster-gt"
    assert record["_source"] == "json_ld"


@pytest.mark.regression
def test_extract_ecommerce_detail_allows_dom_variants_to_fill_weak_js_state_variants() -> (
    None
):
    html = """
    <html>
      <head>
        <script id="__NEXT_DATA__" type="application/json">
        {
          "props": {
            "pageProps": {
              "product": {
                "id": 9001,
                "title": "Trail Runner",
                "variants": [
                  {
                    "id": "weak-1",
                    "sku": "TRAIL-WEAK"
                  }
                ]
              }
            }
          }
        }
        </script>
      </head>
      <body>
        <h1>Trail Runner</h1>
        <label>
          Size
          <select name="size">
            <option value="">Choose size</option>
            <option value="s">S</option>
            <option value="m">M</option>
          </select>
        </label>
        <div class="color-swatch-group" aria-label="Color">
          <button type="button" aria-label="Black"></button>
          <button type="button" aria-label="Olive"></button>
        </div>
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
    assert len(record["variants"]) == 4


@pytest.mark.regression
def test_extract_ecommerce_detail_merges_deduped_additional_images_across_js_state_and_dom() -> (
    None
):
    html = """
    <html>
      <head>
        <script id="__NEXT_DATA__" type="application/json">
        {
          "props": {
            "pageProps": {
              "product": {
                "id": 9001,
                "title": "Trail Runner",
                "images": [
                  {"src": "https://cdn.example.com/products/trail-runner-1.jpg?width=400"},
                  {"src": "https://cdn.example.com/products/trail-runner-2.jpg?width=400"},
                  {"src": "https://cdn.example.com/assets/payment-badge.svg"}
                ],
                "variants": []
              }
            }
          }
        }
        </script>
      </head>
      <body>
        <main class="pdp-main">
          <h1>Trail Runner</h1>
          <section class="hero-media">
            <img src="https://cdn.example.com/products/trail-runner-1.jpg?width=1200" alt="Trail Runner front view" />
            <img src="https://cdn.example.com/products/trail-runner-2.jpg?width=1200" alt="Trail Runner side view" />
            <img src="https://cdn.example.com/products/trail-runner-3.jpg?width=1200" alt="Trail Runner outsole" />
          </section>
        </main>
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
    assert (
        record["image_url"]
        == "https://cdn.example.com/products/trail-runner-1.jpg?width=1200"
    )
    assert record["additional_images"] == [
        "https://cdn.example.com/products/trail-runner-2.jpg?width=1200",
        "https://cdn.example.com/products/trail-runner-3.jpg?width=1200",
    ]


@pytest.mark.regression
def test_build_detail_record_collapses_responsive_cdn_image_duplicates() -> None:
    record = build_detail_record(
        "<html><body><main><h1>Aganice Aromatique Candle</h1></main></body></html>",
        "https://www.aesop.com/home-fragrance/candles/aganice-aromatique-candle/HM03.html",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "Aganice Aromatique Candle",
                "image_url": (
                    "https://www.aesop.com/on/demandware.static/-/Sites-aesop-us-master-catalog/"
                    "default/dwdbcd8bbe/images/products/HM03/"
                    "Aesop_Home_Aganice_Aromatique_Candle_Web_Front_2000x2000px.png"
                ),
                "additional_images": [
                    (
                        "https://www.aesop.com/dw/image/v2/AANG_PRD/on/demandware.static/"
                        "-/Sites-aesop-us-master-catalog/default/dwdbcd8bbe/images/products/HM03/"
                        "Aesop_Home_Aganice_Aromatique_Candle_Web_Front_2000x2000px.jpg"
                        "?sw=430&sh=430&sm=cut&sfrm=png&q=70&bgcolor=fffef2"
                    ),
                    (
                        "https://www.aesop.com/dw/image/v2/AANG_PRD/on/demandware.static/"
                        "-/Sites-aesop-us-master-catalog/default/dwdbcd8bbe/images/products/HM03/"
                        "Aesop_Home_Aganice_Aromatique_Candle_Web_Front_2000x2000px.jpg"
                        "?sw=1536&sh=1536&sm=cut&sfrm=png&q=70&bgcolor=fffef2"
                    ),
                    (
                        "https://www.aesop.com/dw/image/v2/AANG_PRD/on/demandware.static/"
                        "-/Sites-aesop-us-master-catalog/default/dw00834621/images/products/HM03/"
                        "Aesop_Home_Aganice_Aromatique_Candle_Vessel_&_Carton_Front_2000x2000px.jpg"
                        "?sw=430&sh=430&sm=cut&sfrm=png&q=70&bgcolor=fffef2"
                    ),
                    (
                        "https://www.aesop.com/dw/image/v2/AANG_PRD/on/demandware.static/"
                        "-/Sites-aesop-us-master-catalog/default/dw00834621/images/products/HM03/"
                        "Aesop_Home_Aganice_Aromatique_Candle_Vessel_&_Carton_Front_2000x2000px.jpg"
                        "?sw=1536&sh=1536&sm=cut&sfrm=png&q=70&bgcolor=fffef2"
                    ),
                ],
            }
        ],
    )

    assert record["additional_images"] == [
        (
            "https://www.aesop.com/dw/image/v2/AANG_PRD/on/demandware.static/"
            "-/Sites-aesop-us-master-catalog/default/dw00834621/images/products/HM03/"
            "Aesop_Home_Aganice_Aromatique_Candle_Vessel_&_Carton_Front_2000x2000px.jpg"
            "?sw=1536&sh=1536&sm=cut&sfrm=png&q=70&bgcolor=fffef2"
        )
    ]


@pytest.mark.regression
def test_build_detail_record_collapses_semicolon_image_resize_duplicates() -> None:
    record = build_detail_record(
        "<html><body><main><h1>AirPods Pro</h1></main></body></html>",
        "https://www.bestbuy.com/product/apple-airpods-pro-2nd-generation-white/JJ8ZH6TPSW",
        "ecommerce_detail",
        None,
        adapter_records=[
            {
                "title": "AirPods Pro",
                "image_url": (
                    "https://pisces.bbystatic.com/image2/BestBuy_US/images/products/"
                    "4900/4900964_sd.jpg;maxHeight=128;maxWidth=64?format=webp"
                ),
                "additional_images": [
                    (
                        "https://pisces.bbystatic.com/image2/BestBuy_US/images/products/"
                        "4900/4900964_sd.jpg;maxHeight=64;maxWidth=64?format=webp"
                    ),
                    (
                        "https://pisces.bbystatic.com/image2/BestBuy_US/images/products/"
                        "4900/4900964_sd.jpg;maxHeight=1080;maxWidth=900?format=webp"
                    ),
                    (
                        "https://pisces.bbystatic.com/image2/BestBuy_US/images/products/"
                        "4900/4900964_rd.jpg;maxHeight=1080;maxWidth=900?format=webp"
                    ),
                    (
                        "https://pisces.bbystatic.com/image2/BestBuy_US/images/products/"
                        "4900/4900964_rd.jpg;maxHeight=1920;maxWidth=900?format=webp"
                    ),
                ],
            }
        ],
    )

    assert record["image_url"].endswith(
        "4900964_sd.jpg;maxHeight=1080;maxWidth=900?format=webp"
    )
    assert record["additional_images"] == [
        (
            "https://pisces.bbystatic.com/image2/BestBuy_US/images/products/"
            "4900/4900964_rd.jpg;maxHeight=1920;maxWidth=900?format=webp"
        )
    ]


@pytest.mark.regression
def test_extract_detail_keeps_dom_images_live_when_structured_data_only_has_primary_image() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Trail Runner",
          "image": "https://cdn.example.com/products/trail-runner-1.jpg",
          "offers": {
            "price": "99.00",
            "priceCurrency": "USD",
            "availability": "https://schema.org/InStock"
          }
        }
        </script>
      </head>
      <body>
        <main>
          <h1>Trail Runner</h1>
          <section class="gallery">
            <img src="https://cdn.example.com/products/trail-runner-1.jpg" alt="Trail Runner front view" />
            <a href="https://cdn.example.com/products/trail-runner-2.jpg">
              <img src="https://cdn.example.com/products/trail-runner-2-thumb.jpg" alt="Trail Runner side view" />
            </a>
            <a href="https://cdn.example.com/products/trail-runner-3.jpg">
              <img src="https://cdn.example.com/products/trail-runner-3-thumb.jpg" alt="Trail Runner outsole" />
            </a>
          </section>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/trail-runner",
        "ecommerce_detail",
        max_records=5,
        extraction_runtime_snapshot={
            "selector_self_heal": {"enabled": True, "min_confidence": 0.55}
        },
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["_extraction_tiers"]["current"] == "dom"
    assert record["_extraction_tiers"]["early_exit"] is None
    assert record["additional_images"] == [
        "https://cdn.example.com/products/trail-runner-2-thumb.jpg",
        "https://cdn.example.com/products/trail-runner-3-thumb.jpg",
    ]


@pytest.mark.regression
def test_extract_ecommerce_detail_prefers_full_dom_description_and_keeps_product_details_separate() -> (
    None
):
    html = """
    <html>
      <head>
        <meta property="og:title" content="Headless + Omnichannel in a pill">
        <meta property="og:description" content="Launch new markets fast">
        <meta property="og:image" content="https://storefront1.saleor.cloud/media/thumbnails/products/saleor-headless-omnichannel-book_thumbnail_1024.webp">
      </head>
      <body>
        <main>
          <h1>Headless + Omnichannel in a pill</h1>
          <section>
            <h2>Description</h2>
            <p><strong>Launch new markets fast</strong></p>
            <p>Compact, actionable insights for modern retail.</p>
            <p>Headless + Omnichannel in a Pill explains how businesses can:</p>
            <ul>
              <li>Rapidly launch new markets</li>
              <li>Localize content efficiently</li>
              <li>Deliver seamless omnichannel experiences</li>
            </ul>
            <p>It also covers:</p>
            <ul>
              <li>Mobile, web, and in-store integration</li>
              <li>Emerging channels and technologies</li>
              <li>Headless architecture benefits</li>
            </ul>
          </section>
          <section>
            <button aria-controls="product-details-panel">Product Details</button>
            <section id="product-details-panel">
              <dl>
                <div><dt>Publisher</dt><dd>Digital Audio</dd></div>
                <div><dt>Description Summary</dt><dd>A fast-paced guide to launching new markets with headless and omnichannel strategies.</dd></div>
                <div><dt>Lector</dt><dd>Sophia Keller</dd></div>
                <div><dt>Release Date</dt><dd>2022-06-15</dd></div>
              </dl>
            </section>
          </section>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://demo.saleor.io/default-channel/products/headless-omnichannel-commerce",
        "ecommerce_detail",
        max_records=5,
        requested_fields=["description", "product_details"],
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["description"].startswith(
        "Launch new markets fast Compact, actionable insights for modern retail."
    )
    assert "Rapidly launch new markets" in record["description"]
    assert "Headless architecture benefits" in record["description"]
    assert record["product_details"] == (
        "Publisher Digital Audio Description Summary A fast-paced guide to launching new markets "
        "with headless and omnichannel strategies. Lector Sophia Keller Release Date 2022-06-15"
    )
    assert "specifications" not in record


@pytest.mark.regression
def test_extract_ecommerce_detail_keeps_dom_tier_live_for_product_details_without_requested_fields() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Headless + Omnichannel in a pill",
          "brand": {"name": "Audiobooks"},
          "description": "Launch new markets fast",
          "image": "https://storefront1.saleor.cloud/media/thumbnails/products/saleor-headless-omnichannel-book_thumbnail_1024.webp",
          "offers": {
            "priceCurrency": "USD",
            "availability": "https://schema.org/InStock"
          }
        }
        </script>
      </head>
      <body>
        <main>
          <h1>Headless + Omnichannel in a pill</h1>
          <section>
            <h2>Description</h2>
            <p><strong>Launch new markets fast</strong></p>
            <p>Compact, actionable insights for modern retail.</p>
            <p>Headless architecture benefits.</p>
          </section>
          <section>
            <button aria-controls="product-details-panel">Product Details</button>
            <section id="product-details-panel">
              <dl>
                <div><dt>Publisher</dt><dd>Digital Audio</dd></div>
                <div><dt>Description Summary</dt><dd>A fast-paced guide to launching new markets with headless and omnichannel strategies.</dd></div>
              </dl>
            </section>
          </section>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://demo.saleor.io/default-channel/products/headless-omnichannel-commerce",
        "ecommerce_detail",
        max_records=5,
        extraction_runtime_snapshot={
            "selector_self_heal": {"enabled": True, "min_confidence": 0.55}
        },
    )

    assert len(rows) == 1
    record = rows[0]
    assert "Headless architecture benefits" in record["description"]
    assert record["product_details"] == (
        "Publisher Digital Audio Description Summary A fast-paced guide to launching new markets "
        "with headless and omnichannel strategies."
    )
    assert record["_extraction_tiers"]["current"] == "dom"
    assert record["_extraction_tiers"]["early_exit"] is None


@pytest.mark.regression
def test_extract_ecommerce_detail_dedupes_next_image_proxy_duplicates() -> None:
    html = """
    <html>
      <head>
        <meta property="og:title" content="Headless + Omnichannel in a pill">
        <meta property="og:image" content="https://storefront1.saleor.cloud/media/thumbnails/products/saleor-headless-omnichannel-book_thumbnail_1024.webp">
      </head>
      <body>
        <main>
          <h1>Headless + Omnichannel in a pill</h1>
          <section class="gallery">
            <img src="https://storefront1.saleor.cloud/media/thumbnails/products/saleor-headless-omnichannel-book_thumbnail_1024.webp" alt="Book cover">
            <img src="https://demo.saleor.io/_next/image?url=https%3A%2F%2Fstorefront1.saleor.cloud%2Fmedia%2Fthumbnails%2Fproducts%2Fsaleor-headless-omnichannel-book_thumbnail_1024.webp&w=1080&q=75" alt="Book cover transformed">
          </section>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://demo.saleor.io/default-channel/products/headless-omnichannel-commerce",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["image_url"] == (
        "https://storefront1.saleor.cloud/media/thumbnails/products/saleor-headless-omnichannel-book_thumbnail_1024.webp"
    )
    assert "additional_images" not in record


@pytest.mark.regression
def test_extract_ecommerce_detail_keeps_real_description_when_dom_sections_only_see_tabs() -> (
    None
):
    html = """
    <html>
      <head>
        <meta property="og:title" content="Airdopes Supreme Long Playback Earbuds">
        <meta property="og:description" content="Experience superior sound with boAt Airdopes Supreme — 50H playback, AI ENx, Cinematic Spatial Audio and BEAST Mode.">
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Airdopes Supreme Long Playback Earbuds",
          "brand": {"name": "boAt"},
          "offers": {
            "price": "1399",
            "priceCurrency": "INR",
            "availability": "https://schema.org/InStock"
          }
        }
        </script>
      </head>
      <body>
        <main>
          <h1>Airdopes Supreme Long Playback Earbuds</h1>
          <div class="product-description">
            Experience superior sound with boAt Airdopes Supreme — 50H playback, AI ENx, Cinematic Spatial Audio and BEAST Mode.
          </div>
          <section>
            <h2>Description</h2>
            <div>
              <button>Description</button>
              <button>specifications</button>
              <button>Reviews (192)</button>
            </div>
          </section>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.boat-lifestyle.com/products/airdopes-supreme-long-playback-earbuds",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["description"] == (
        "Experience superior sound with boAt Airdopes Supreme — 50H playback, AI ENx, "
        "Cinematic Spatial Audio and BEAST Mode."
    )
    assert "handle" not in record

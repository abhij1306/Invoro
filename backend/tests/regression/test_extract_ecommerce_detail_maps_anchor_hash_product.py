from __future__ import annotations

from .test_detail_extractor_structured_sources import detail_product_type_is_low_signal, detail_redirect_identity_is_mismatched, detail_slug_title_fallback_from_url, detail_title_fallback_looks_like_code, extract_records, pytest, read_optional_artifact_text, reconcile_detail_currency_with_url, repair_ecommerce_detail_record_quality, title_needs_promotion  # fmt: skip

@pytest.mark.regression
def test_extract_ecommerce_detail_maps_anchor_hash_product_description_upstream() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Superman: Krypto The Superdog Oversized T-Shirts By DC Comics™",
          "description": "Shop for Superman: Crypto Men Oversized Fit T-shirts Online",
          "brand": {"name": "DC Comics™"},
          "offers": {
            "price": "899",
            "priceCurrency": "INR",
            "availability": "https://schema.org/InStock"
          }
        }
        </script>
      </head>
      <body>
        <main>
          <h1>Superman: Krypto The Superdog</h1>
          <div id="accordion">
            <div class="card">
              <div role="tab" id="headingOne" class="card-header">
                <h5 class="mb-0 accordianheading">
                  <a data-toggle="collapse" data-parent="#accordion" href="#collapseOne" aria-expanded="true" aria-controls="collapseOne">
                    Product Details
                  </a>
                </h5>
              </div>
              <div id="collapseOne" role="tabpanel" aria-labelledby="headingOne" class="collapse show">
                <div class="card-block">
                  <p><b>Material &amp; Care:</b><br>Premium Heavy Gauge Fabric<br>100% Cotton<br>Machine Wash</p>
                </div>
              </div>
            </div>
            <div class="card">
              <div role="tab" id="headingTwo" class="card-header">
                <h5 class="mb-0 accordianheading">
                  <a data-toggle="collapse" data-parent="#accordion" href="#collapseTwo" aria-expanded="false" aria-controls="collapseTwo">
                    Product Description
                  </a>
                </h5>
              </div>
              <div id="collapseTwo" role="tabpanel" aria-labelledby="headingTwo" class="collapse">
                <div class="card-block">
                  <p><b>Official Licensed Superman Oversized T-Shirt.</b></p>
                  <p>Shop for Superman: Krypto The Superdog Oversized T-Shirts at The Souled Store.</p>
                </div>
              </div>
            </div>
            <div class="card">
              <div role="tab" id="headingArtist" class="card-header">
                <h5 class="mb-0 accordianheading">
                  <a data-toggle="collapse" data-parent="#accordion" href="#collapseArtist" aria-expanded="false" aria-controls="collapseArtist">
                    Artist's Details
                  </a>
                </h5>
              </div>
              <div id="collapseArtist" role="tabpanel" aria-labelledby="headingArtist" class="collapse">
                <div class="card-block">
                  <p>Suit up with Justice League merchandise.</p>
                </div>
              </div>
            </div>
          </div>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.thesouledstore.com/product/men-oversized-fit-superman-crypto?gte=1",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["description"] == (
        "Official Licensed Superman Oversized T-Shirt. "
        "Shop for Superman: Krypto The Superdog Oversized T-Shirts at The Souled Store."
    )
    assert record["product_details"] == (
        "Material & Care: Premium Heavy Gauge Fabric 100% Cotton Machine Wash"
    )
    assert record["_field_sources"]["description"] == ["json_ld", "dom_sections"]
    assert "dom_sections" in record["_field_sources"]["product_details"]

@pytest.mark.regression
def test_extract_ecommerce_detail_filters_zara_copy_code_from_dom_variants() -> None:
    html = """
    <html>
      <body>
        <main>
          <h1>Regular Fit Shirt</h1>
          <fieldset>
            <legend>Color</legend>
            <div class="product-detail-color-selector">
              <button type="button" aria-label="Black"></button>
              <button type="button" aria-label="Blue/White"></button>
              <button type="button" aria-label="White"></button>
              <button type="button" aria-label="Sky blue"></button>
              <button type="button" aria-label="Ecru / Blue"></button>
              <button type="button" aria-label="White / Sky blue"></button>
              <button type="button" aria-label="4493/144/800"></button>
            </div>
          </fieldset>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.zara.com/in/en/regular-fit-shirt-p04493144.html",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert "4493/144/800" not in str(record.get("option1_values") or "")
    assert record["variant_count"] == 6

@pytest.mark.regression
def test_extract_ecommerce_detail_maps_zara_composition_block_to_materials() -> None:
    html = """
    <html>
      <body>
        <main>
          <h1>CONTRAST RIBBED T-SHIRT WITH RUFFLES</h1>
          <div class="product-detail-description">
            <p>SLIM FIT - ROUND NECK - REGULAR LENGTH - SHORT SLEEVES</p>
          </div>
          <ul class="product-detail-actions product-detail-info__product-actions">
            <li class="product-detail-actions__action">
              <button class="product-detail-size-guide-action product-detail-actions__action-button">
                <span>Product Measurements</span>
              </button>
            </li>
            <li class="product-detail-actions__action product-detail-actions__clevercare">
              <button class="product-detail-actions__action-button">
                Composition, care &amp; origin
              </button>
            </li>
          </ul>
        </main>
        <div class="product-detail-view__secondary-content">
          <div class="product-detail-composition product-detail-view__detailed-composition">
            <ul>
              <li class="product-detail-composition__item product-detail-composition__part">
                <span class="product-detail-composition__part-name">OUTER SHELL</span>
                <ul>
                  <li class="product-detail-composition__item product-detail-composition__area">
                    <span class="product-detail-composition__part-name">MAIN FABRIC</span>
                    <ul><li>96% cotton</li><li>4% elastane</li></ul>
                  </li>
                  <li class="product-detail-composition__item product-detail-composition__area">
                    <span class="product-detail-composition__part-name">SECONDARY FABRIC</span>
                    <ul><li>100% cotton</li></ul>
                  </li>
                </ul>
              </li>
            </ul>
          </div>
        </div>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.zara.com/in/en/contrast-ribbed-t-shirt-with-ruffles-p01044154.html",
        "ecommerce_detail",
        max_records=5,
        requested_fields=["materials", "dimensions"],
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["materials"] == (
        "OUTER SHELL: MAIN FABRIC: 96% cotton; 4% elastane "
        "SECONDARY FABRIC: 100% cotton"
    )
    assert record["_field_sources"]["materials"] == ["dom_sections"]
    assert "dimensions" not in record

@pytest.mark.regression
def test_extract_detail_keeps_requested_custom_dom_sections_live_past_structured_early_exit() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Darter Pro",
          "description": "Instant cushioning for everyday road runs.",
          "brand": {"name": "PUMA"},
          "image": "https://example.com/darter-pro.jpg",
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
          <h1>Darter Pro</h1>
          <section>
            <h2>Product Story</h2>
            <p>
              Hit new strides in the Darter Pro with a lightweight mesh upper and
              responsive cushioning built for daily miles.
            </p>
          </section>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/darter-pro",
        "ecommerce_detail",
        max_records=5,
        requested_fields=["product story"],
        extraction_runtime_snapshot={
            "selector_self_heal": {"enabled": True, "min_confidence": 0.55}
        },
    )

    assert len(rows) == 1
    record = rows[0]
    assert "lightweight mesh upper" in record["product_story"]
    assert record["_field_sources"]["product_story"] == ["dom_sections"]
    assert record["_extraction_tiers"]["current"] == "dom"
    assert record["_extraction_tiers"]["early_exit"] is None

@pytest.mark.regression
def test_extract_detail_matches_exact_requested_section_label_without_collapsing_it() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Deviate Nitro Elite 4",
          "description": "Race-ready road running shoes.",
          "brand": {"name": "PUMA"},
          "offers": {
            "price": "230.00",
            "priceCurrency": "USD",
            "availability": "https://schema.org/InStock"
          }
        }
        </script>
      </head>
      <body>
        <main>
          <h1>Deviate Nitro Elite 4</h1>
          <section>
            <h2>FEATURES &amp; BENEFITS</h2>
            <ul>
              <li>NITROFOAM Elite delivers lightweight responsiveness.</li>
              <li>PWRPLATE drives energy transfer through toe-off.</li>
            </ul>
          </section>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://in.puma.com/in/en/pd/deviate-nitro-elite-4-run-club-mens-road-running-shoes/312907?swatch=01",
        "ecommerce_detail",
        max_records=5,
        requested_fields=["Features & Benefits"],
        extraction_runtime_snapshot={
            "selector_self_heal": {"enabled": True, "min_confidence": 0.55}
        },
    )

    assert len(rows) == 1
    record = rows[0]
    assert "NITROFOAM Elite" in record["features_benefits"]
    assert "PWRPLATE drives energy transfer" in record["features_benefits"]
    assert record["_field_sources"]["features_benefits"] == ["dom_sections"]
    assert record["_extraction_tiers"]["current"] == "dom"
    assert record["_extraction_tiers"]["early_exit"] is None
    assert "benefits" not in record

@pytest.mark.regression
def test_extract_detail_keeps_company_details_body_for_requested_custom_field() -> None:
    html = read_optional_artifact_text("artifacts/runs/8/pages/dc80e38b20c25b9b.html")

    rows = extract_records(
        html,
        "https://www.tradeindia.com/products/calcium-carbonate-powder-c10587655.html",
        "ecommerce_detail",
        max_records=5,
        requested_fields=["company_details"],
        extraction_runtime_snapshot={
            "selector_self_heal": {"enabled": True, "min_confidence": 0.55}
        },
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["company_details"].startswith(
        "Lyotex Lifesciences Private Limited is a reliable name in the manufacturing"
    )
    assert (
        "Business Type Manufacturer, Supplier, Trading Company"
        in record["company_details"]
    )
    assert "GST NO 27AAECL9071B1ZK" in record["company_details"]
    assert record["_field_sources"]["company_details"] == ["dom_sections"]

@pytest.mark.regression
def test_extract_detail_keeps_slug_match_when_identity_codes_disagree() -> None:
    requested_url = (
        "https://example.com/products/widget-premium?dwvar_ABCD1234_color=red"
    )
    html = """
    <html>
      <head>
        <link rel="canonical" href="https://example.com/products/widget-premium?dwvar_EFGH5678_color=red" />
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Widget Premium",
          "description": "Widget Premium for everyday use.",
          "offers": {
            "price": "19.99",
            "priceCurrency": "USD"
          }
        }
        </script>
      </head>
      <body>
        <main><h1>Widget Premium</h1></main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/widget-premium?dwvar_EFGH5678_color=red",
        "ecommerce_detail",
        max_records=5,
        requested_page_url=requested_url,
    )

    assert len(rows) == 1
    assert rows[0]["title"] == "Widget Premium"

@pytest.mark.regression
def test_extract_detail_accepts_same_url_with_code_mismatch() -> None:
    requested_url = "https://izod.com/products/ss-adv-polo-46izagb03r-440"
    html = """
    <html>
      <head>
        <link rel="canonical" href="https://izod.com/products/ss-adv-polo-46izagb03r-440">
        <script type="application/ld+json">
        {
          "@context": "https://schema.org/",
          "@type": "Product",
          "name": "Short Sleeve Advantage Polo",
          "image": "https://example.com/polo.jpg",
          "sku": "196407820454",
          "offers": {
            "@type": "Offer",
            "price": "44.00",
            "priceCurrency": "USD",
            "availability": "https://schema.org/InStock"
          }
        }
        </script>
      </head>
      <body>
        <main>
          <h1>Short Sleeve Advantage Polo</h1>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        requested_url,
        "ecommerce_detail",
        max_records=5,
        requested_page_url=requested_url,
    )

    assert len(rows) == 1
    assert rows[0]["title"] == "Short Sleeve Advantage Polo"
    assert rows[0]["price"] == "44.00"

@pytest.mark.regression
def test_extract_detail_keeps_nike_record_when_canonical_drops_style_code() -> None:
    requested_url = "https://www.nike.com/t/air-force-1-07-mens-shoes-jBrhbr/CW2288-111"
    html = """
    <html>
      <head>
        <link rel="canonical" href="https://www.nike.com/t/air-force-1-07-mens-shoes-jBrhbr">
        <meta property="og:title" content="Nike Air Force 1 '07 Men's Shoes">
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Nike Air Force 1 '07 Men's Shoes",
          "brand": {"@type": "Brand", "name": "Nike"},
          "sku": "CW2288-111",
          "mpn": "CW2288-111",
          "image": "https://static.nike.com/af1.png",
          "description": "Comfortable, durable and timeless.",
          "offers": {
            "@type": "Offer",
            "price": "115",
            "priceCurrency": "USD"
          }
        }
        </script>
      </head>
      <body><main><h1>Nike Air Force 1 '07 Men's Shoes</h1></main></body>
    </html>
    """

    rows = extract_records(
        html,
        requested_url,
        "ecommerce_detail",
        max_records=5,
        requested_page_url=requested_url,
    )

    assert len(rows) == 1
    assert rows[0]["title"] == "Nike Air Force 1 '07 Men's Shoes"
    assert rows[0]["part_number"] == "CW2288-111"

@pytest.mark.regression
def test_extract_detail_keeps_shopify_collection_detail_when_canonical_collapses_path() -> (
    None
):
    requested_url = (
        "https://kith.com/collections/mens-footwear-sneakers/products/st40002-02000"
    )
    html = """
    <html>
      <head>
        <link rel="canonical" href="https://kith.com/products/st40002-02000">
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "SATISFY TheROCKER - Jet Black",
          "brand": {"@type": "Brand", "name": "SATISFY"},
          "sku": "13876003",
          "image": "https://kith.com/files/therocker.jpg",
          "description": "TheROCKER silhouette.",
          "offers": {
            "@type": "Offer",
            "price": "28200",
            "priceCurrency": "INR",
            "availability": "https://schema.org/OutOfStock"
          }
        }
        </script>
      </head>
      <body><main><h1>SATISFY TheROCKER - Jet Black</h1></main></body>
    </html>
    """

    rows = extract_records(
        html,
        requested_url,
        "ecommerce_detail",
        max_records=5,
        requested_page_url=requested_url,
    )

    assert len(rows) == 1
    assert rows[0]["title"] == "SATISFY TheROCKER - Jet Black"
    assert rows[0]["currency"] == "USD"
    assert rows[0]["price"] == "282.00"

@pytest.mark.regression
def test_extract_detail_corrects_host_currency_hint_integer_cent_price() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "SATISFY TheROCKER - Jet Black",
          "offers": {"price": "28200", "priceCurrency": "INR"}
        }
        </script>
      </head>
      <body><main><h1>SATISFY TheROCKER - Jet Black</h1></main></body>
    </html>
    """

    rows = extract_records(
        html,
        "https://kith.com/collections/mens-footwear-sneakers/products/st40002-02000",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    assert rows[0]["currency"] == "USD"
    assert rows[0]["price"] == "282.00"

@pytest.mark.regression
def test_extract_detail_keeps_decimal_price_when_currency_conflicts_with_host_hint() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "EVGA GeForce RTX 3090",
          "offers": {"price": "260650.21", "priceCurrency": "INR"}
        }
        </script>
      </head>
      <body><main><h1>EVGA GeForce RTX 3090</h1></main></body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.amazon.com/dp/B08J5F3G18",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    assert rows[0]["currency"] == "INR"
    assert rows[0]["price"] == "260650.21"

@pytest.mark.regression
def test_extract_detail_does_not_backfill_low_signal_price_after_currency_conflict() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Poppi Soda",
          "offers": {"price": "2153.05", "priceCurrency": "INR"}
        }
        </script>
      </head>
      <body>
        <main>
          <h1>Poppi Soda</h1>
          <span class="a-price"><span class="a-offscreen">$1.00</span></span>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.amazon.com/dp/B0F5Y3X8PP",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    assert rows[0]["currency"] == "INR"
    assert rows[0]["price"] == "2153.05"

@pytest.mark.regression
def test_repair_ecommerce_detail_replaces_mismatched_title_when_slug_evidence_matches() -> (
    None
):
    record = {
        "title": "Yonder Jr. 600 mL / 20 oz Water Bottle",
        "price": "25.00",
        "currency": "USD",
        "image_url": "https://yeti-webmedia.imgix.net/site_studio_drinkware_Rambler_8oz_CL_Tumbler_Seafoam_Front.png",
        "description": "The perk-friendly stackable cup that brings the cafe to any terrain.",
        "variants": [
            {
                "color": "Seafoam",
                "url": "https://www.yeti.com/on/demandware.store/Sites-Yeti_US-Site/en_US/Product-Variation?dwvar_rambler-stackable_color=seafoam&dwvar_rambler-stackable_size=ceramic-8oz&pid=rambler-stackable",
            }
        ],
    }

    repair_ecommerce_detail_record_quality(
        record,
        html="",
        page_url="https://www.yeti.com/drinkware/tumblers/rambler-ceramic-stackable-8oz.html",
    )

    assert record["title"] == "Rambler Ceramic Stackable 8Oz"

@pytest.mark.regression
def test_detail_title_prime_is_not_promoted_when_supported_by_url() -> None:
    assert not title_needs_promotion(
        "Prime",
        page_url="https://example.com/products/prime",
    )

@pytest.mark.regression
def test_detail_title_prime_is_not_promoted_when_supported_by_terminal_slug_tokens() -> (
    None
):
    assert not title_needs_promotion(
        "Prime",
        page_url="https://example.com/products/prime-day-shirt",
    )

@pytest.mark.regression
def test_detail_slug_title_fallback_keeps_semantic_slug_with_model_suffix() -> None:
    assert (
        detail_slug_title_fallback_from_url(
            "https://example.com/products/rambler-stackable-8oz"
        )
        == "rambler stackable 8oz"
    )

@pytest.mark.regression
def test_detail_title_fallback_code_guard_skips_multi_token_numeric_slug() -> None:
    assert detail_title_fallback_looks_like_code("iphone-16-pro") is False
    assert (
        detail_slug_title_fallback_from_url(
            "https://example.com/products/iphone-16-pro"
        )
        == "iphone 16 pro"
    )

@pytest.mark.regression
def test_detail_product_type_low_signal_includes_artifact_values() -> None:
    assert detail_product_type_is_low_signal("promotionalcallout")

@pytest.mark.regression
def test_detail_redirect_identity_detects_model_conflict_without_sku_evidence() -> None:
    assert detail_redirect_identity_is_mismatched(
        {"title": "Canon EOS R5 Camera", "price": "3999.00"},
        page_url="https://example.com/products/canon-eos-r6-camera",
        requested_page_url="https://example.com/products/canon-eos-r6-camera",
    )

@pytest.mark.regression
def test_currency_reconcile_keeps_adapter_localized_price_over_host_hint() -> None:
    record = {
        "price": "INR 2,153.05",
        "currency": "INR",
        "variants": [{"price": "INR 2,153.05", "currency": "INR", "size": "12 pack"}],
        "_field_sources": {"price": ["adapter"], "variants": ["adapter"]},
    }

    reconcile_detail_currency_with_url(
        record,
        page_url="https://www.amazon.com/dp/B0F5Y3X8PP",
    )

    assert record["price"] == "INR 2,153.05"
    assert record["currency"] == "INR"
    assert record["variants"][0]["currency"] == "INR"

from __future__ import annotations

from .test_crawl_engine import *  # noqa: F403


@pytest.mark.regression
def test_infer_detail_failure_reason_labels_wayfair_pdp_shell_as_detail_shell() -> None:
    url = (
        "https://www.wayfair.com/furniture/pdp/"
        "flexsteel-bryce-power-reclining-sofa-with-power-headrest-xtya1522.html"
        "?piid=94673717"
    )
    html = """
    <html>
      <head>
        <title>Flexsteel Bryce Power Reclining Sofa with Power Headrest &amp; Reviews | Wayfair</title>
      </head>
      <body></body>
    </html>
    """

    assert (
        detail_extractor.infer_detail_failure_reason(
            html,
            url,
            "ecommerce_detail",
            [],
            requested_page_url=url,
        )
        == "detail_shell"
    )

@pytest.mark.regression
def test_build_detail_record_keeps_real_wayfair_pdp_title_instead_of_url_slug() -> None:
    url = (
        "https://www.wayfair.com/furniture/pdp/"
        "flexsteel-bryce-power-reclining-sofa-with-power-headrest-xtya1522.html"
        "?piid=94673717"
    )
    description = " ".join(
        ["Traditional comfort with power reclining and headrest support."] * 8
    )
    html = f"""
    <html>
      <head>
        <title>Flexsteel Bryce Power Reclining Sofa with Power Headrest &amp; Reviews | Wayfair</title>
        <meta property="og:title" content="Flexsteel Bryce Power Reclining Sofa with Power Headrest &amp; Reviews | Wayfair" />
        <meta property="og:description" content="{description}" />
        <meta property="og:image" content="https://assets.wfcdn.com/im/widget.jpg" />
        <link rel="canonical" href="{url}" />
      </head>
      <body>
        <main>
          <h1>Bryce Power Reclining Sofa with Power Headrest</h1>
          <div>$2,499.99</div>
          <img src="https://assets.wfcdn.com/im/widget.jpg" />
          <section>
            <h2>About This Product</h2>
            <p>{description}</p>
          </section>
        </main>
      </body>
    </html>
    """

    record = detail_extractor.build_detail_record(
        html,
        url,
        "ecommerce_detail",
        [],
        requested_page_url=url,
    )

    assert record.get("title") == (
        "Flexsteel Bryce Power Reclining Sofa with Power Headrest & Reviews | Wayfair"
    )
    assert "url_slug" not in (record.get("_field_sources", {}).get("title") or [])

@pytest.mark.regression
def test_detail_rejection_keeps_rich_wayfair_pdp_with_promotional_title() -> None:
    requested_url = (
        "https://www.wayfair.com/furniture/pdp/"
        "flexsteel-bryce-power-reclining-sofa-with-power-headrest-xtya1522.html"
        "?piid=94673717"
    )
    record = {
        "title": (
            "Flexsteel Bryce Power Reclining Sofa with Power Headrest & Reviews | Wayfair"
        ),
        "url": requested_url,
        "price": "2499.99",
        "currency": "USD",
        "image_url": "https://assets.wfcdn.com/im/widget.jpg",
        "description": "A" * 220,
        "_field_sources": {
            "title": ["opengraph", "dom_h1"],
            "price": ["dom_text"],
            "image_url": ["opengraph"],
            "description": ["opengraph"],
        },
        "_source": "opengraph",
        "_confidence": {
            "score": 0.5113,
            "level": "low",
        },
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
def test_detail_identity_rejects_wrong_explicit_variant_query_match() -> None:
    requested_url = "https://example.com/products/widget-prime?variant=22222222"
    record = {
        "title": "Widget Prime",
        "url": "https://example.com/products/widget-prime?variant=11111111",
        "sku": "11111111",
        "price": "10.00",
    }

    assert (
        detail_extractor.detail_record_rejection_reason(
            record,
            page_url=requested_url,
            requested_page_url=requested_url,
        )
        == "detail_identity_mismatch"
    )

@pytest.mark.regression
def test_detail_identity_trusts_matching_product_id_when_slug_numbers_differ() -> None:
    requested_url = (
        "https://www.harrods.com/en-gb/p/"
        "brinkhaus-emperor-100percent-arctic-duck-down-duvet-85-tog-000000000004579693"
    )
    record = {
        "title": "Brinkhaus Emperor 100% Arctic Duck Down Duvet (8.5 Tog)",
        "url": (
            "https://www.harrods.com/en-gb/p/"
            "brinkhaus-emperor-100percent-arctic-duck-down-duvet-85-tog-000000000004579694"
        ),
        "product_id": "000000000004579693",
        "description": "Arctic duck down duvet with silk and Lyocell casing.",
        "price": "5000.00",
        "currency": "GBP",
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
def test_detail_category_sanitization_drops_embedded_title_segments() -> None:
    html = """
    <html><head>
      <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": "iPhone 16",
        "url": "https://www.apple.com/shop/buy-iphone/iphone-16",
        "offers": {"price": "699", "priceCurrency": "USD"}
      }
      </script>
      <script type="application/ld+json">
      {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
          {"@type": "ListItem", "position": 1, "name": "iPhone"},
          {"@type": "ListItem", "position": 2, "name": "iPhone 16"},
          {"@type": "ListItem", "position": 3, "name": "Buy iPhone 16 and iPhone 16 Plus"}
        ]
      }
      </script>
    </head><body><h1>iPhone 16</h1></body></html>
    """

    rows = extract_records(
        html,
        "https://www.apple.com/shop/buy-iphone/iphone-16",
        "ecommerce_detail",
        max_records=1,
        requested_page_url="https://www.apple.com/shop/buy-iphone/iphone-16",
    )

    assert rows[0]["category"] == "iPhone"

@pytest.mark.regression
def test_detail_rejection_keeps_rich_pdp_without_strong_identity_fields() -> None:
    requested_url = (
        "https://www.wayfair.com/furniture/pdp/"
        "flexsteel-bryce-power-reclining-sofa-with-power-headrest-xtya1522.html"
        "?piid=94673717"
    )
    record = {
        "title": "flexsteel bryce power reclining sofa with power headrest xtya1522",
        "url": requested_url,
        "price": "850.00",
        "currency": "USD",
        "image_url": "https://assets.wfcdn.com/im/widget.jpg",
        "description": "A" * 220,
        "_field_sources": {
            "title": ["dom_h1", "url_slug"],
            "price": ["dom_text"],
        },
        "_source": "dom_h1",
        "_confidence": {
            "score": 0.2883,
            "level": "low",
        },
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
def test_extract_ecommerce_detail_rejects_search_results_shell_with_sort_filter_controls() -> (
    None
):
    html = """
    <html>
      <head>
        <meta property="og:title" content="Trail Shoes" />
      </head>
      <body>
        <main>
          <h1>Trail Shoes</h1>
          <label for="sort-by">Sort By</label>
          <select id="sort-by">
            <option>Featured</option>
            <option>Price: Low to High</option>
          </select>
          <label for="filter-by">Filter By</label>
          <select id="filter-by">
            <option>All</option>
            <option>Men</option>
          </select>
          <article class="product-card">
            <a href="/dp/B0TRAIL123">
              <img src="https://cdn.example.com/trail-shoe.jpg" alt="Trail Runner GTX" />
              <h2>Trail Runner GTX</h2>
            </a>
            <div class="price">$129.99</div>
          </article>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.example.com/s?k=trail+shoes",
        "ecommerce_detail",
        max_records=1,
    )

    assert rows == []

@pytest.mark.regression
def test_extract_ecommerce_detail_rejects_placeholder_not_found_title_without_product_signals() -> (
    None
):
    html = """
    <html>
      <body>
        <main>
          <h1>Oops! The page you're looking for can't be found.</h1>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.vitacost.com/now-foods-ultra-omega-3-fish-oil-500-epa-250-dha-180-softgels",
        "ecommerce_detail",
        max_records=1,
    )

    assert rows == []

@pytest.mark.regression
def test_extract_ecommerce_detail_recovers_firstcry_static_js_state_price() -> None:
    html = """
    <html>
      <head>
        <meta property="og:title" content="Buy Babyhug Denim Woven Sleeveless Top &amp; Pant Set With Floral Print - Blue for Girls (3-4 Years) Online in India, Shop at FirstCry.com - 22346676" />
        <meta property="og:image" content="https://cdn.fcglcdn.com/brainbees/images/products/438x531/22346676a.webp" />
        <meta property="og:url" content="https://www.firstcry.com/babyhug/babyhug-denim-woven-sleeveless-top-and-pant-set-with-floral-print-blue/22346676/product-detail" />
        <script>
          var CurrentProductID=22346676,CurrentProductDetailJSON={
            "22346676":{
              "pid":22346676,
              "pn":"Babyhug Denim Woven Sleeveless Top & Pant Set With Floral Print - Blue",
              "pd":"Babyhug Sets & Suits Female 3-4Y BLUE/BLUE",
              "mrp":1099,
              "Dis":21,
              "Img":"22346676a.jpg;22346676b.jpg;"
            }
          };
        </script>
      </head>
      <body>
        <h1>product detail</h1>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.firstcry.com/babyhug/babyhug-denim-woven-sleeveless-top-and-pant-set-with-floral-print-blue/22346676/product-detail",
        "ecommerce_detail",
        max_records=1,
        requested_page_url="https://www.firstcry.com/babyhug/babyhug-denim-woven-sleeveless-top-and-pant-set-with-floral-print-blue/22346676/product-detail",
        requested_fields=["title", "price", "image_url"],
    )

    assert len(rows) == 1
    record = rows[0]
    assert (
        record["title"]
        == "Babyhug Denim Woven Sleeveless Top & Pant Set With Floral Print - Blue"
    )
    assert record["price"] == "868.21"
    assert (
        record["image_url"]
        == "https://cdn.fcglcdn.com/brainbees/images/products/438x531/22346676a.webp"
    )

@pytest.mark.regression
def test_extract_ecommerce_detail_recovers_firstcry_keyed_size_variants_from_artifact() -> (
    None
):
    html = read_optional_artifact_text("artifacts/runs/1/pages/911cb20ab9926f3d.html")

    rows = extract_records(
        html,
        "https://www.firstcry.com/babyhug/babyhug-denim-woven-sleeveless-top-and-pant-set-with-floral-print-blue/22346676/product-detail",
        "ecommerce_detail",
        max_records=1,
        requested_page_url="https://www.firstcry.com/babyhug/babyhug-denim-woven-sleeveless-top-and-pant-set-with-floral-print-blue/22346676/product-detail",
        requested_fields=["variants"],
    )

    assert len(rows) == 1
    sizes = {row.get("size") for row in rows[0]["variants"]}
    assert {"2-3Y", "3-4Y", "4-5Y"} <= sizes

@pytest.mark.regression
def test_extract_ecommerce_detail_rejects_brand_shell_with_tracking_pixel_image() -> (
    None
):
    html = """
    <html>
      <head>
        <meta property="og:title" content="Rockler Woodworking and Hardware" />
        <meta property="og:image" content="https://www.facebook.com/tr?id=244606169432534&ev=PageView&noscript=1" />
      </head>
      <body>
        <main>
          <h1>Rockler Woodworking and Hardware</h1>
          <p>Family-owned since 1954 Rockler is your go to source for high quality and innovative woodworking tools, hardware, lumber and expert advice.</p>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://www.rockler.com/jessem-mast-r-lift-ii-excel-router-lift",
        "ecommerce_detail",
        max_records=1,
    )

    assert rows == []

@pytest.mark.regression
def test_extract_ecommerce_detail_keeps_structured_product_when_title_still_needs_promotion() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Buy Widget Prime | Example",
          "description": "A real widget with structured content.",
          "image": "https://example.com/widget.jpg",
          "offers": {
            "price": "19.99",
            "priceCurrency": "USD"
          }
        }
        </script>
      </head>
      <body>
        <main>
          <h1>Buy Widget Prime | Example</h1>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/products/12345",
        "ecommerce_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["title"] == "Buy Widget Prime | Example"
    assert record["price"] == "19.99"
    assert record["image_url"] == "https://example.com/widget.jpg"

@pytest.mark.regression
def test_extract_job_detail_returns_requested_sections() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "JobPosting",
          "title": "Senior Data Engineer",
          "datePosted": "2026-04-18",
          "employmentType": "Full-time",
          "description": "Build deterministic data pipelines.",
          "jobLocationType": "TELECOMMUTE",
          "hiringOrganization": {"name": "Data Corp"},
          "jobLocation": {
            "address": {
              "addressLocality": "Bengaluru",
              "addressRegion": "KA",
              "addressCountry": "IN"
            }
          },
          "baseSalary": {
            "@type": "MonetaryAmount",
            "currency": "INR",
            "value": {
              "@type": "QuantitativeValue",
              "minValue": "2500000",
              "maxValue": "3500000",
              "unitText": "YEAR"
            }
          },
          "url": "https://example.com/jobs/senior-data-engineer"
        }
        </script>
      </head>
      <body>
        <h1>Senior Data Engineer</h1>
        <h2>Responsibilities</h2>
        <div>Build pipelines and maintain ingestion services.</div>
        <h2>Qualifications</h2>
        <div>5+ years of Python and SQL.</div>
        <h2>Benefits</h2>
        <div>Remote-first, health cover.</div>
        <h2>Skills</h2>
        <div>Python, SQL, Airflow.</div>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/jobs/senior-data-engineer",
        "job_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["title"] == "Senior Data Engineer"
    assert record["company"] == "Data Corp"
    assert record["location"] == "Bengaluru, KA, IN"
    assert record["job_type"] == "Full-time"
    assert record["posted_date"] == "2026-04-18"
    assert record["salary"] == "INR 2500000 - 3500000 YEAR"
    assert record["remote"] is True
    assert "Build pipelines" in record["responsibilities"]
    assert "5+ years" in record["qualifications"]
    assert "health cover" in record["benefits"]
    assert "Python, SQL, Airflow." in record["skills"]

@pytest.mark.regression
def test_extract_job_detail_strips_tracking_params_from_output_urls() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "JobPosting",
          "title": "Senior Data Engineer",
          "hiringOrganization": {"name": "Data Corp"},
          "url": "https://example.com/jobs/senior-data-engineer?utm_source=linkedin&fbclid=abc123&jobId=42"
        }
        </script>
      </head>
      <body>
        <h1>Senior Data Engineer</h1>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/jobs/senior-data-engineer?utm_medium=email&sid=session-1&jobId=42",
        "job_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["url"] == "https://example.com/jobs/senior-data-engineer?jobId=42"
    assert (
        record["apply_url"] == "https://example.com/jobs/senior-data-engineer?jobId=42"
    )
    assert (
        record["source_url"] == "https://example.com/jobs/senior-data-engineer?jobId=42"
    )

@pytest.mark.regression
def test_extract_greenhouse_job_detail_from_remix_state() -> None:
    html = """
    <html>
      <head>
        <title>Job Application for Manager, Engineering at Greenhouse</title>
        <script>
          window.__remixContext = {
            "state": {
              "loaderData": {
                "routes/$url_token_.jobs_.$job_post_id": {
                  "jobPost": {
                    "title": "Manager, Engineering",
                    "company_name": "Greenhouse",
                    "job_post_location": "Ontario",
                    "public_url": "https://job-boards.greenhouse.io/greenhouse/jobs/7704699?gh_jid=7704699",
                    "published_at": "2026-04-09T10:05:53-04:00",
                    "content": "<p>Lead the reporting and analytics engineering domain.</p><h2>What you’ll do</h2><ul><li>Lead and mentor engineers.</li></ul><h2>You should have</h2><ul><li>5+ years of engineering experience.</li></ul><h2>Benefits</h2><p>Remote-first and health cover.</p>"
                  }
                }
              }
            }
          };
        </script>
      </head>
      <body>
        <h1>Manager, Engineering</h1>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://job-boards.greenhouse.io/greenhouse/jobs/7704699?gh_jid=7704699",
        "job_detail",
        max_records=5,
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["title"] == "Manager, Engineering"
    assert record["company"] == "Greenhouse"
    assert record["location"] == "Ontario"
    assert (
        record["apply_url"]
        == "https://job-boards.greenhouse.io/greenhouse/jobs/7704699?gh_jid=7704699"
    )
    assert "Lead and mentor engineers." in record["responsibilities"]
    assert "5+ years of engineering experience." in record["qualifications"]
    assert "Remote-first and health cover." in record["benefits"]
    assert record["_source"] == "js_state"

@pytest.mark.regression
def test_extract_job_detail_ignores_cross_surface_requested_image_fields() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "JobPosting",
          "title": "Senior Data Engineer",
          "description": "Build deterministic data pipelines.",
          "hiringOrganization": {
            "name": "Data Corp",
            "logo": "https://example.com/images/company-logo.jpg"
          },
          "image": [
            "https://example.com/images/company-logo.jpg",
            "https://example.com/images/office.jpg"
          ],
          "jobLocation": {
            "address": {
              "addressLocality": "Bengaluru",
              "addressRegion": "KA",
              "addressCountry": "IN"
            }
          },
          "url": "https://example.com/jobs/senior-data-engineer"
        }
        </script>
      </head>
      <body>
        <h1>Senior Data Engineer</h1>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/jobs/senior-data-engineer",
        "job_detail",
        max_records=5,
        requested_fields=["image_url", "additional_images", "description"],
    )

    assert len(rows) == 1
    record = rows[0]
    assert record["title"] == "Senior Data Engineer"
    assert record["company"] == "Data Corp"
    assert record["description"] == "Build deterministic data pipelines."
    assert "image_url" not in record
    assert "additional_images" not in record

from __future__ import annotations

from .test_selectolax_css_migration import *  # noqa: F403


@pytest.mark.regression
def test_structured_product_payload_single_size_variant_accepts_snake_case() -> None:
    rows = _structured_variants_from_product_payload(
        {
            "sku": "CAP-1",
            "price": 10,
            "is_one_size": True,
            "size_name": "One Size",
        },
        "https://example.com/products/trail-cap",
    )

    assert rows == [
        {
            "option_values": {"size": "One Size"},
            "sku": "CAP-1",
            "price": "10",
            "size": "One Size",
        }
    ]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_nike_adapter_maps_preloaded_state_product() -> None:
    result = await NikeAdapter().extract(
        "https://www.nike.in/nike-pro-training-men-s-dri-fit-short-sleeve-top/p/24829693",
        """
        <html>
          <body>
            <script id="__PRELOADED_STATE__" type="application/json">
            {
              "details": {
                "skuData": {
                  "product": {
                    "id": "24829693",
                    "sku": "NIKEX00027953",
                    "discountedPrice": 1996,
                    "price": 2495,
                    "imageUrl": "https://example.com/nike-1.jpg",
                    "color": {"name": "Green"},
                    "action_url": "/nike-pro-training-men-s-dri-fit-short-sleeve-top/p/24829693",
                    "title": "Nike Pro Training",
                    "subTitle": "Men's Dri-FIT Short-Sleeve Top",
                    "isOutOfStock": 0,
                    "product_summary": {"description": "Train with ease."},
                    "productMedia": [
                      {"mediaType": "image", "url": "https://example.com/nike-1.jpg"},
                      {"mediaType": "image", "url": "https://example.com/nike-2.jpg"}
                    ],
                    "sizeOptions": {
                      "title": "Select Size",
                      "options": [
                        {"id": "24828378", "sku": "NIKEX00026638", "sizeName": "XXS", "discountedPrice": 1996, "price": 2495, "isOutOfStock": 1},
                        {"id": "24828336", "sku": "NIKEX00026596", "sizeName": "S", "discountedPrice": 1996, "price": 2495, "isOutOfStock": 0}
                      ]
                    }
                  }
                }
              }
            }
            </script>
          </body>
        </html>
        """,
        "ecommerce_detail",
    )

    record = result.records[0]
    assert record["title"] == "Nike Pro Training Men's Dri-FIT Short-Sleeve Top"
    assert record["brand"] == "Nike"
    assert record["price"] == "1996"
    assert record["original_price"] == "2495"
    assert record["color"] == "Green"
    assert "size" not in record

@pytest.mark.asyncio
@pytest.mark.regression
async def test_nike_detail_extraction_uses_adapter_and_rejects_shell_json_ld() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {"@context":"https://schema.org","@type":"Corporation","name":"Nike","founders":[{"@type":"Person","name":"Bill Bowerman"}]}
        </script>
      </head>
      <body>
        <label>Text
          <select><option>White</option><option>Black</option><option>Red</option></select>
        </label>
        <label>Background
          <select><option>Opaque</option><option>Semi-Transparent</option></select>
        </label>
        <script id="__PRELOADED_STATE__" type="application/json">
        {
          "details": {
            "skuData": {
              "product": {
                "id": "24809354",
                "sku": "NIKEX00021288",
                "discountedPrice": 1495,
                "price": 1495,
                "imageUrl": "https://example.com/nike.jpg",
                "color": {"name": "Black"},
                "action_url": "/nike-pro-men-s-dri-fit-tight-sleeveless-fitness-top/p/24809354",
                "title": "Nike Pro",
                "subTitle": "Men's Dri-FIT Tight Sleeveless Fitness Top",
                "isOutOfStock": 0,
                "sizeOptions": {
                  "title": "Select Size",
                  "options": [
                    {"id": "24809169", "sku": "NIKEX00021103", "sizeName": "XS", "discountedPrice": 1495, "price": 1495, "isOutOfStock": 1},
                    {"id": "24809174", "sku": "NIKEX00021108", "sizeName": "S", "discountedPrice": 1495, "price": 1495, "isOutOfStock": 0}
                  ]
                }
              }
            }
          }
        }
        </script>
      </body>
    </html>
    """
    url = "https://www.nike.in/nike-pro-men-s-dri-fit-tight-sleeveless-fitness-top/p/24809354"
    adapter_records = (
        await NikeAdapter().extract(url, html, "ecommerce_detail")
    ).records
    records = extract_detail_records(
        html,
        url,
        "ecommerce_detail",
        None,
        adapter_records=adapter_records,
    )

    record = records[0]
    assert record["title"] == "Nike Pro Men's Dri-FIT Tight Sleeveless Fitness Top"
    assert record["brand"] == "Nike"
    assert record["variant_count"] == 2
    assert "size" not in record
    assert "Bill Bowerman" not in record.values()

@pytest.mark.asyncio
@pytest.mark.regression
async def test_nike_adapter_maps_next_data_selected_product_payload() -> None:
    result = await NikeAdapter().extract(
        "https://www.nike.com/t/air-force-1-07-mens-shoes-jBrhbr/CW2288-111",
        """
        <html>
          <body>
            <script id="__NEXT_DATA__" type="application/json">
            {
              "props": {
                "pageProps": {
                  "colorwayImages": [
                    {
                      "portraitImg": "https://static.nike.com/af1-main.jpg",
                      "squarishImg": "https://static.nike.com/af1-alt.jpg"
                    }
                  ],
                  "selectedProduct": {
                    "id": "13071857",
                    "styleCode": "CW2288",
                    "styleColor": "CW2288-111",
                    "colorDescription": "White/White",
                    "prices": {
                      "currency": "USD",
                      "currentPrice": 115,
                      "initialPrice": 115
                    },
                    "productInfo": {
                      "title": "Nike Air Force 1 '07",
                      "subtitle": "Men's Shoes",
                      "productDescription": "Comfortable, durable and timeless.",
                      "path": "/t/air-force-1-07-mens-shoes-jBrhbr/CW2288-111",
                      "featuresAndBenefits": [
                        {"body": "<ul><li>Padded collar</li></ul>"}
                      ]
                    },
                    "sizes": [
                      {
                        "label": "6",
                        "status": "ACTIVE",
                        "merchSkuId": "sku-6",
                        "gtins": [{"gtin": "00194500874886"}]
                      },
                      {
                        "label": "7",
                        "status": "OOS",
                        "merchSkuId": "sku-7",
                        "gtins": [{"gtin": "00194500874909"}]
                      }
                    ]
                  }
                }
              }
            }
            </script>
          </body>
        </html>
        """,
        "ecommerce_detail",
    )

    record = result.records[0]
    assert record["title"] == "Nike Air Force 1 '07 Men's Shoes"
    assert record["sku"] == "CW2288-111"
    assert record["price"] == "115"
    assert record["currency"] == "USD"
    assert record["image_url"] == "https://static.nike.com/af1-main.jpg"
    assert record["additional_images"] == ["https://static.nike.com/af1-alt.jpg"]
    # Nike exposes a distinct GTIN per size, and `barcode` is a flat-variant key
    # (FLAT_VARIANT_KEYS), so each variant keeps its own barcode.
    assert record["variants"][0]["barcode"] == "00194500874886"
    assert record["variants"][1]["barcode"] == "00194500874909"
    assert record["variants"][0]["price"] == "115"
    assert record["variants"][1]["availability"] == "out_of_stock"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_nike_adapter_maps_nested_next_data_price_objects() -> None:
    result = await NikeAdapter().extract(
        "https://www.nike.com/t/air-force-1-07-mens-shoes-jBrhbr/CW2288-111",
        """
        <html>
          <body>
            <script id="__NEXT_DATA__" type="application/json">
            {
              "props": {
                "pageProps": {
                  "selectedProduct": {
                    "id": "13071857",
                    "styleColor": "CW2288-111",
                    "colorDescription": "White/White",
                    "prices": {
                      "currentPrice": {"value": 115},
                      "initialPrice": {"value": 130}
                    },
                    "productInfo": {
                      "title": "Nike Air Force 1 '07",
                      "subtitle": "Men's Shoes",
                      "path": "/t/air-force-1-07-mens-shoes-jBrhbr/CW2288-111"
                    },
                    "sizes": [
                      {
                        "label": "6",
                        "status": "ACTIVE",
                        "merchSkuId": "sku-6"
                      }
                    ]
                  }
                }
              }
            }
            </script>
          </body>
        </html>
        """,
        "ecommerce_detail",
    )

    record = result.records[0]
    assert record["price"] == "115"
    assert record["original_price"] == "130"
    assert record["variants"][0]["price"] == "115"
    assert "original_price" not in record["variants"][0]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_nike_adapter_does_not_infer_empty_sizes_as_out_of_stock() -> None:
    result = await NikeAdapter().extract(
        "https://www.nike.fr/t/example-product/ABC123",
        """
        <html>
          <body>
            <script id="__NEXT_DATA__" type="application/json">
            {
              "props": {
                "pageProps": {
                  "selectedProduct": {
                    "id": "13071857",
                    "styleColor": "CW2288-111",
                    "colorDescription": "White/White",
                    "prices": {
                      "currentPrice": 115,
                      "initialPrice": 130
                    },
                    "productInfo": {
                      "title": "Nike Air Force 1 '07",
                      "subtitle": "Men's Shoes",
                      "path": "/t/example-product/ABC123"
                    },
                    "sizes": []
                  }
                }
              }
            }
            </script>
          </body>
        </html>
        """,
        "ecommerce_detail",
    )

    record = result.records[0]
    assert record["title"] == "Nike Air Force 1 '07 Men's Shoes"
    assert record["price"] == "115"
    assert record["availability"] == "in_stock"
    assert record["currency"] == "EUR"
    assert len(record.get("variants", [])) == 0

@pytest.mark.asyncio
@pytest.mark.regression
async def test_ebay_adapter_preserves_css_listing_output() -> None:
    result = await EbayAdapter().extract(
        "https://www.ebay.com/sch/i.html?_nkw=widget",
        """
        <html>
          <body>
            <div class="s-item">
              <a class="s-item__link" href="https://www.ebay.com/itm/123">
                <div class="s-item__title">Widget Prime</div>
              </a>
              <div class="s-item__price">$29.99</div>
              <div class="s-item__image-wrapper">
                <img src="https://example.com/ebay-widget.jpg">
              </div>
            </div>
          </body>
        </html>
        """,
        "ecommerce_listing",
    )

    assert result.records == [
        {
            "title": "Widget Prime",
            "price": "$29.99",
            "image_url": "https://example.com/ebay-widget.jpg",
            "url": "https://www.ebay.com/itm/123",
        }
    ]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_indeed_adapter_preserves_css_listing_output() -> None:
    result = await IndeedAdapter().extract(
        "https://www.indeed.com/jobs?q=engineer",
        """
        <html>
          <body>
            <div class="job_seen_beacon">
              <h2><a href="/viewjob?jk=123"><span>Data Engineer</span></a></h2>
              <div data-testid="company-name">Data Corp</div>
              <div data-testid="text-location">Bengaluru</div>
              <div class="salary-snippet-container">₹30,00,000 a year</div>
            </div>
          </body>
        </html>
        """,
        "job_listing",
    )

    assert result.records == [
        {
            "title": "Data Engineer",
            "company": "Data Corp",
            "location": "Bengaluru",
            "salary": "₹30,00,000 a year",
            "apply_url": "https://www.indeed.com/viewjob?jk=123",
        }
    ]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_indeed_adapter_uses_source_origin_for_relative_listing_urls() -> None:
    result = await IndeedAdapter().extract(
        "https://ca.indeed.com/jobs?q=engineer",
        """
        <html>
          <body>
            <div class="job_seen_beacon">
              <h2><a href="/viewjob?jk=123"><span>Data Engineer</span></a></h2>
              <div data-testid="company-name">Data Corp</div>
            </div>
          </body>
        </html>
        """,
        "job_listing",
    )

    assert result.records[0]["apply_url"] == "https://ca.indeed.com/viewjob?jk=123"

@pytest.mark.regression
def test_extract_job_sections_stops_collecting_at_strong_headings() -> None:
    sections = extract_job_sections(
        """
        <div>
          <strong>Benefits</strong>
          <p>Remote-first.</p>
          <strong>Skills</strong>
          <p>Python.</p>
        </div>
        """
    )

    assert sections["benefits"] == "Remote-first."
    assert sections["skills"] == "Python."

@pytest.mark.asyncio
@pytest.mark.regression
async def test_linkedin_adapter_preserves_css_detail_output() -> None:
    result = await LinkedInAdapter().extract(
        "https://www.linkedin.com/jobs/view/123",
        """
        <html>
          <body>
            <h1 class="top-card-layout__title">Senior Data Engineer</h1>
            <div class="top-card-layout__company-name">Data Corp</div>
            <div class="top-card-layout__bullet">Bengaluru</div>
            <div class="description__job-criteria-item">
              <h3 class="description__job-criteria-subheader">Employment type</h3>
              <span class="description__job-criteria-text">Full-time</span>
            </div>
            <div class="description__text">Build deterministic pipelines.</div>
          </body>
        </html>
        """,
        "job_detail",
    )

    assert result.records == [
        {
            "title": "Senior Data Engineer",
            "company": "Data Corp",
            "location": "Bengaluru",
            "job_type": "Full-time",
            "description": "Build deterministic pipelines.",
            "apply_url": "https://www.linkedin.com/jobs/view/123",
            "url": "https://www.linkedin.com/jobs/view/123",
        }
    ]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_adp_adapter_preserves_css_listing_output() -> None:
    result = await ADPAdapter().extract(
        "https://example.wd5.myworkforcenow.com/recruitment/recruitment.html",
        """
        <html>
          <body>
            <div class="current-openings-item" id="job_123456">
              <a id="lblTitle_123456">Senior Data Engineer</a>
              <div class="current-opening-location-item"><span>Bengaluru</span></div>
              <div class="current-opening-post-date">2 days ago</div>
            </div>
          </body>
        </html>
        """,
        "job_listing",
    )

    assert len(result.records) == 1
    record = result.records[0]
    assert record["title"] == "Senior Data Engineer"
    assert record["job_id"] == "123456"
    assert record["location"] == "Bengaluru"
    assert record["posted_date"] == "2 days ago"
    assert record["apply_url"].endswith("jobId=123456#123456")

@pytest.mark.asyncio
@pytest.mark.regression
async def test_job_listing_pipeline_preserves_adp_adapter_rows_with_query_job_ids() -> (
    None
):
    url = "https://workforcenow.adp.com/mascsr/default/mdf/recruitment/recruitment.html?cid=tenant&selectedMenuKey=CurrentOpenings"
    html = """
    <html>
      <body>
        <div class="current-openings-item" id="job_item_view_main_div_9202786317663_1">
          <sdf-link id="lblTitle_9202786317663_1">ORAL SURGEON<a href="#"></a></sdf-link>
          <label class="current-opening-location-item"><span>New York, NY, US</span></label>
          <span class="current-opening-post-date">8 days ago</span>
        </div>
        <div class="current-openings-item" id="job_item_view_main_div_9202786030399_1">
          <sdf-link id="lblTitle_9202786030399_1">PHARMACIST<a href="#"></a></sdf-link>
          <label class="current-opening-location-item"><span>Queens, NY, US</span></label>
          <span class="current-opening-post-date">9 days ago</span>
        </div>
      </body>
    </html>
    """
    adapter_result = await ADPAdapter().extract(url, html, "job_listing")

    rows = extract_records(
        html,
        url,
        "job_listing",
        max_records=10,
        adapter_records=adapter_result.records,
    )

    assert [row["title"] for row in rows] == ["ORAL SURGEON", "PHARMACIST"]
    assert [("jobId=9202786317663_1" in row["url"]) for row in rows] == [True, False]
    assert [("jobId=9202786030399_1" in row["url"]) for row in rows] == [False, True]

@pytest.mark.regression
def test_job_listing_pipeline_prefers_icims_adapter_rows_over_career_nav_chrome() -> (
    None
):
    url = (
        "https://ehccareers-emory.icims.com/jobs/search?pr=0&searchRelation=keyword_all"
    )
    html = """
    <html>
      <body>
        <div class="job-card">
          <a href="https://www.emoryhealthcare.org/careers/life-at-emory">
            <h3>Life at Emory Back Life at Emory Hospitals Our Communities</h3>
          </a>
        </div>
        <div class="job-card">
          <a href="https://www.emoryhealthcare.org/careers/how-we-hire">
            <h3>How We Hire Back How We Hire Eligibility Requirements Hiring Disclosures</h3>
          </a>
        </div>
      </body>
    </html>
    """
    adapter_records = [
        {
            "title": "Blood Bank Medical Lab Scientist",
            "url": "https://clinical-emory.icims.com/jobs/166851/blood-bank-medical-lab-scientist/job?hub=14",
            "location": "Atlanta, GA",
            "company": "Emory Univ Hospital",
            "job_id": "166851",
        },
        {
            "title": "Director, Enterprise Sterile Processing",
            "url": "https://non-clinical-emory.icims.com/jobs/166766/director-enterprise-sterile-processing/job?hub=14",
            "location": "Atlanta, GA",
            "company": "Emory Healthcare Inc.",
            "job_id": "166766",
        },
    ]

    rows = extract_records(
        html,
        url,
        "job_listing",
        max_records=10,
        adapter_records=adapter_records,
    )

    assert [row["title"] for row in rows] == [
        "Blood Bank Medical Lab Scientist",
        "Director, Enterprise Sterile Processing",
    ]

@pytest.mark.asyncio
@pytest.mark.regression
async def test_bullhorn_adapter_extracts_public_job_board_rows(monkeypatch) -> None:
    html = """
    <script>
      var API_BASE='https://public-rest32.bullhornstaffing.com/rest-services/a7084/query/JobBoardPost';
      var url=API_BASE+"?where=(branchCode=%27Internal%27) AND (isOpen=true) AND (isDeleted=false)&fields="+FIELDS;
    </script>
    """
    captured_urls: list[str] = []

    async def fake_request_json(self, url, **kwargs):
        del self, kwargs
        captured_urls.append(url)
        return {
            "data": [
                {
                    "id": 123,
                    "title": "Talent Acquisition Associate",
                    "publishedCategory": {"name": "Recruiting"},
                    "address": {"city": "Houston", "state": "TX"},
                    "employmentType": "Direct Hire",
                    "dateLastPublished": 1779200924763,
                    "publicDescription": "<p>Build strong candidate pipelines.</p>",
                }
            ]
        }

    monkeypatch.setattr(BullhornAdapter, "_request_json", fake_request_json)

    assert await BullhornAdapter().can_handle("https://www.vc5partners.com/jobs/", html)

    result = await BullhornAdapter().extract(
        "https://www.vc5partners.com/jobs/",
        html,
        "job_listing",
    )

    assert len(result.records) == 1
    record = result.records[0]
    assert record["title"] == "Talent Acquisition Associate"
    assert record["job_id"] == "123"
    assert record["location"] == "Houston, TX"
    assert record["department"] == "Recruiting"
    assert record["job_type"] == "Direct Hire"
    assert record["posted_date"] == "2026-05-19"
    assert record["description"] == "Build strong candidate pipelines."
    assert "branchCode" in captured_urls[0]
    assert "%28branchCode" in captured_urls[0]

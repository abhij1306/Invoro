from __future__ import annotations

from .test_crawl_engine import *  # noqa: F403


@pytest.mark.regression
def test_extract_records_rejects_concatenated_resource_menu_listing_titles() -> None:
    rows = extract_records(
        "<html><body></body></html>",
        "https://www.customink.com/products/sweatshirts/hoodies/71",
        "ecommerce_listing",
        max_records=10,
        artifacts={
            "rendered_listing_fragments": [
                _rendered_listing_fragment(
                    title="Tools & Resources Group Ordering Fundraising Online Stores Pro Services Tips & Advice T-shirt Maker",
                    url="https://www.customink.com/fundraising",
                ),
                _rendered_listing_fragment(
                    title="Independent Trading Midweight Hooded Sweatshirt",
                    url="https://www.customink.com/products/hoodies/independent-trading-midweight-hooded-sweatshirt/827800",
                    price="$39.99",
                    image_url="https://www.customink.com/images/hoodie-1.jpg",
                ),
            ]
        },
    )

    assert [row["title"] for row in rows] == [
        "Independent Trading Midweight Hooded Sweatshirt",
    ]

@pytest.mark.regression
def test_extract_records_drops_shallow_editorial_listing_links_without_product_signals() -> (
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
                    title="Diversity & Belonging",
                    url="https://www.customink.com/equity-for-all",
                ),
                _rendered_listing_fragment(
                    title="Customer Reviews",
                    url="https://www.customink.com/reviews",
                ),
                _rendered_listing_fragment(
                    title="Customer Photos",
                    url="https://www.customink.com/photos",
                ),
                _rendered_listing_fragment(
                    title="T-shirt Maker",
                    url="https://www.customink.com/services/t-shirt-maker-creator",
                ),
                _rendered_listing_fragment(
                    title="Corporate Swag",
                    url="https://www.customink.com/ink/business/corporate-swag-branded-merchandise",
                ),
                _rendered_listing_fragment(
                    title="Content Guidelines",
                    url="https://www.customink.com/help_center/content-guidelines",
                ),
                _rendered_listing_fragment(
                    title="Custom Products",
                    url="https://www.customink.com/ink/custom-products",
                ),
                _rendered_listing_fragment(
                    title="Sign In Sign In",
                    url="https://www.customink.com/profiles/users/sign_in",
                ),
                _rendered_listing_fragment(
                    title="Independent Trading Midweight Hooded Sweatshirt",
                    url="https://www.customink.com/products/hoodies/independent-trading-midweight-hooded-sweatshirt/827800",
                    price="$39.99",
                    image_url="https://www.customink.com/images/hoodie-1.jpg",
                ),
            ]
        },
    )

    assert [row["title"] for row in rows] == [
        "Independent Trading Midweight Hooded Sweatshirt",
    ]

@pytest.mark.regression
def test_extract_records_drops_rendered_listing_download_app_cta_rows() -> None:
    rows = extract_records(
        "<html><body></body></html>",
        "https://www.reverb.com/marketplace?product_type=electric-guitars",
        "ecommerce_listing",
        max_records=10,
        artifacts={
            "rendered_listing_fragments": [
                _rendered_listing_fragment(
                    title="Download the Reverb App",
                    url="https://reverb.com/featured/reverb-app",
                )
            ]
        },
    )

    assert rows == []

@pytest.mark.regression
def test_extract_records_drops_rendered_listing_category_hub_rows_without_supporting_signals() -> (
    None
):
    rows = extract_records(
        "<html><body></body></html>",
        "https://www.karenmillen.com/eu/categories/womens-trousers",
        "ecommerce_listing",
        max_records=10,
        artifacts={
            "rendered_listing_fragments": [
                _rendered_listing_fragment(
                    title="Womens Clothing",
                    url="https://www.karenmillen.com/eu/categories/womens-clothing",
                )
            ]
        },
    )

    assert rows == []

@pytest.mark.regression
def test_extract_records_rejects_footer_policy_links_on_skeleton_plp() -> None:
    html = """
    <html>
      <body>
        <main>
          <div class="PLP_placeholderWrap">
            <div class="ProductCardSkeleton productSkeleton"></div>
          </div>
        </main>
        <footer>
          <div class="Footer_uspIcons">
            <a href="https://content.abfrl.in/shipping-policy">
              <img src="https://imagescdn.reebok.in/uploads/micrositmedia/production/alteration_Copy_2alteration-.png" alt="FREE SHIPPING" />
              <span>FREE SHIPPING</span>
            </a>
          </div>
          <div class="Footer_uspIcons">
            <a href="https://content.abfrl.in/returns-cancel-policy">
              <img src="https://imagescdn.reebok.in/uploads/micrositmedia/production/alteration_Copyreturn-1.png" alt="RETURN WITHIN 15 DAYS" />
              <span>RETURN WITHIN 15 DAYS</span>
            </a>
          </div>
        </footer>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://reebok.abfrl.in/c/leggings-and-tights",
        "ecommerce_listing",
        max_records=10,
    )

    assert rows == []
    assert (
        extract_listing_records(
            html,
            "https://reebok.abfrl.in/c/leggings-and-tights",
            "ecommerce_listing",
            max_records=10,
        )
        == []
    )

@pytest.mark.regression
def test_extract_records_recovers_rendered_listing_price_from_fragment_text() -> None:
    rows = extract_records(
        "<html><body></body></html>",
        "https://www.uniqlo.com/in/en/men/shirts-and-polo-shirts",
        "ecommerce_listing",
        max_records=10,
        artifacts={
            "rendered_listing_fragments": [
                _rendered_listing_fragment(
                    title="Cotton Linen Shirt Jacket Long Sleeve",
                    url="https://www.uniqlo.com/in/en/products/E482443-000/00?colorDisplayCode=38",
                    image_url="https://image.uniqlo.com/UQ/ST3/in/imagesgoods/482443/item/ingoods_69_482443_3x4.jpg?width=300",
                    price="Rs. 3,990.00",
                )
            ]
        },
    )

    assert rows == [
        {
            "source_url": "https://www.uniqlo.com/in/en/men/shirts-and-polo-shirts",
            "_source": "dom_listing",
            "title": "Cotton Linen Shirt Jacket Long Sleeve",
            "price": "3990.00",
            "currency": "INR",
            "image_url": "https://image.uniqlo.com/UQ/ST3/in/imagesgoods/482443/item/ingoods_69_482443_3x4.jpg?width=300",
            "url": "https://www.uniqlo.com/in/en/products/E482443-000/00?colorDisplayCode=38",
        }
    ]

@pytest.mark.regression
def test_extract_records_backfills_listing_price_from_network_payload_candidates() -> (
    None
):
    rows = extract_records(
        "<html><body></body></html>",
        "https://www.uniqlo.com/in/en/men/shirts-and-polo-shirts",
        "ecommerce_listing",
        max_records=10,
        artifacts={
            "rendered_listing_fragments": [
                _rendered_listing_fragment(
                    title="Cotton Linen Shirt Jacket Long Sleeve",
                    url="https://www.uniqlo.com/in/en/products/E482443-000/00?colorDisplayCode=38",
                    image_url="https://image.uniqlo.com/UQ/ST3/in/imagesgoods/482443/item/ingoods_38_482443_3x4.jpg",
                )
            ]
        },
        network_payloads=[
            {
                "body": {
                    "result": {
                        "items": [
                            {
                                "productId": "E482443-000",
                                "name": "Cotton Linen Shirt Jacket Long Sleeve",
                                "prices": {
                                    "base": {
                                        "value": 3990,
                                        "currency": {"code": "INR"},
                                    }
                                },
                            }
                        ]
                    }
                }
            }
        ],
    )

    assert rows == [
        {
            "source_url": "https://www.uniqlo.com/in/en/men/shirts-and-polo-shirts",
            "_source": "dom_listing",
            "title": "Cotton Linen Shirt Jacket Long Sleeve",
            "url": "https://www.uniqlo.com/in/en/products/E482443-000/00?colorDisplayCode=38",
            "price": "3990",
            "currency": "INR",
            "image_url": "https://image.uniqlo.com/UQ/ST3/in/imagesgoods/482443/item/ingoods_38_482443_3x4.jpg",
        }
    ]

@pytest.mark.regression
def test_extract_records_uses_network_payload_listing_rows_when_dom_is_empty() -> None:
    rows = extract_records(
        "<html><body></body></html>",
        "https://arcteryx.com/ca/en/c/mens/footwear-run/wid-kjyr4dq9",
        "ecommerce_listing",
        max_records=10,
        network_payloads=[
            {
                "body": {
                    "result": {
                        "data": {
                            "json": {
                                "productList": [
                                    {
                                        "id": "X000010398",
                                        "marketingName": "Norvan LD 4 Shoe Men's",
                                        "shortDescription": "Adaptable, long-distance mountain running shoe",
                                        "slug": "shop/mens/norvan-ld-4-shoe-0398",
                                        "priceRange": {
                                            "currency": "CAD",
                                            "regularPrice": 220,
                                            "minDiscountPrice": 220,
                                            "maxDiscountPrice": 220,
                                        },
                                        "review": {"count": 94, "rating": 4.1277},
                                        "hoverImage": {
                                            "url": "https://images.arcteryx.com/details/1350x1710/F25-X000010398-Norvan-LD-4-Shoe-Black-Cloud-Hover.jpg",
                                            "alt": "Norvan LD 4 Shoe Men's",
                                        },
                                    }
                                ]
                            }
                        }
                    }
                }
            }
        ],
    )

    assert rows == [
        {
            "source_url": "https://arcteryx.com/ca/en/c/mens/footwear-run/wid-kjyr4dq9",
            "_source": "network_listing",
            "title": "Norvan LD 4 Shoe Men's",
            "url": "https://arcteryx.com/shop/mens/norvan-ld-4-shoe-0398",
            "product_id": "X000010398",
            "description": "Adaptable, long-distance mountain running shoe",
            "image_url": "https://images.arcteryx.com/details/1350x1710/F25-X000010398-Norvan-LD-4-Shoe-Black-Cloud-Hover.jpg",
            "rating": 4.13,
            "review_count": 94,
            "price": "220",
            "currency": "CAD",
        }
    ]

@pytest.mark.regression
def test_extract_records_backfills_listing_brand_and_range_price_from_network_payload_candidates() -> (
    None
):
    rows = extract_records(
        "<html><body></body></html>",
        "https://www.belk.com/home/",
        "ecommerce_listing",
        max_records=10,
        artifacts={
            "rendered_listing_fragments": [
                _rendered_listing_fragment(
                    title="Beyond Down Bed Pillow",
                    url="https://www.belk.com/p/beyond-down-bed-pillow/92002171202220.html",
                    image_url="https://belk.scene7.com/is/image/Belk/9200217",
                )
            ]
        },
        network_payloads=[
            {
                "body": {
                    "result": {
                        "items": [
                            {
                                "productId": "92002171202220",
                                "name": "Beyond Down Bed Pillow",
                                "brandName": "Beyond Down",
                                "offers": {
                                    "lowPrice": "21.00",
                                    "highPrice": "26.00",
                                    "priceCurrency": "USD",
                                },
                            }
                        ]
                    }
                }
            }
        ],
    )

    assert rows == [
        {
            "source_url": "https://www.belk.com/home/",
            "_source": "dom_listing",
            "title": "Beyond Down Bed Pillow",
            "url": "https://www.belk.com/p/beyond-down-bed-pillow/92002171202220.html",
            "image_url": "https://belk.scene7.com/is/image/Belk/9200217",
            "price": "21.00",
            "currency": "USD",
            "brand": "Beyond Down",
        }
    ]

@pytest.mark.regression
def test_extract_records_backfills_listing_brand_from_network_when_dom_price_exists() -> (
    None
):
    rows = extract_records(
        "<html><body></body></html>",
        "https://www.belk.com/home/",
        "ecommerce_listing",
        max_records=10,
        artifacts={
            "rendered_listing_fragments": [
                _rendered_listing_fragment(
                    title="Beyond Down Bed Pillow",
                    url="https://www.belk.com/p/beyond-down-bed-pillow/92002171202220.html",
                    price="$21.00",
                )
            ]
        },
        network_payloads=[
            {
                "body": {
                    "result": {
                        "items": [
                            {
                                "productId": "92002171202220",
                                "name": "Beyond Down Bed Pillow",
                                "brandName": "Beyond Down",
                                "offers": {
                                    "lowPrice": "21.00",
                                    "highPrice": "26.00",
                                    "priceCurrency": "USD",
                                },
                            }
                        ]
                    }
                }
            }
        ],
    )

    assert rows == [
        {
            "source_url": "https://www.belk.com/home/",
            "_source": "dom_listing",
            "title": "Beyond Down Bed Pillow",
            "url": "https://www.belk.com/p/beyond-down-bed-pillow/92002171202220.html",
            "price": "21.00",
            "currency": "USD",
            "brand": "Beyond Down",
        }
    ]

@pytest.mark.regression
def test_extract_records_backfills_listing_brand_from_network_candidate_without_price() -> (
    None
):
    rows = extract_records(
        "<html><body></body></html>",
        "https://www.belk.com/home/",
        "ecommerce_listing",
        max_records=10,
        artifacts={
            "rendered_listing_fragments": [
                _rendered_listing_fragment(
                    title="Elite Airflow Jumbo Pillow",
                    url="https://www.belk.com/p/sealy-elite-airflow-jumbo-pillow/92002171202220.html",
                    price="$15.00",
                )
            ]
        },
        network_payloads=[
            {
                "body": {
                    "result": {
                        "items": [
                            {
                                "productId": "92002171202220",
                                "productName": "Elite Airflow Jumbo Pillow",
                                "brandName": "Sealy",
                            }
                        ]
                    }
                }
            }
        ],
    )

    assert rows == [
        {
            "source_url": "https://www.belk.com/home/",
            "_source": "dom_listing",
            "title": "Elite Airflow Jumbo Pillow",
            "price": "15.00",
            "currency": "USD",
            "url": "https://www.belk.com/p/sealy-elite-airflow-jumbo-pillow/92002171202220.html",
            "brand": "Sealy",
        }
    ]

@pytest.mark.regression
def test_extract_records_backfills_listing_from_network_by_belk_product_id_when_title_differs() -> (
    None
):
    rows = extract_records(
        "<html><body></body></html>",
        "https://www.belk.com/home/",
        "ecommerce_listing",
        max_records=10,
        artifacts={
            "rendered_listing_fragments": [
                _rendered_listing_fragment(
                    title="Promo Copy That Does Not Match Payload Title",
                    url="https://www.belk.com/p/beyond-down-bed-pillow/92002171202220.html",
                    price="$21.00",
                    image_url="https://belk.scene7.com/is/image/Belk/9200217",
                )
            ]
        },
        network_payloads=[
            {
                "body": {
                    "result": {
                        "items": [
                            {
                                "productId": "92002171202220",
                                "name": "Beyond Down Bed Pillow",
                                "brandName": "Beyond Down",
                                "offers": {
                                    "lowPrice": "21.00",
                                    "priceCurrency": "USD",
                                },
                            }
                        ]
                    }
                }
            }
        ],
    )

    assert rows == [
        {
            "source_url": "https://www.belk.com/home/",
            "_source": "dom_listing",
            "title": "Promo Copy That Does Not Match Payload Title",
            "url": "https://www.belk.com/p/beyond-down-bed-pillow/92002171202220.html",
            "price": "21.00",
            "currency": "USD",
            "brand": "Beyond Down",
        }
    ]

@pytest.mark.regression
def test_extract_records_backfills_adapter_brand_by_belk_product_identity_when_urls_differ() -> (
    None
):
    rows = extract_records(
        """
        <html><body>
          <article>
            <a href="/p/sealy-elite-airflow-jumbo-pillow/92002171202220.html?dwvar_color=White">
              <img src="/images/9200217.jpg" alt="Elite Airflow Jumbo Pillow">
              <span>Elite Airflow Jumbo Pillow</span>
            </a>
            <span class="price">$15.00</span>
          </article>
        </body></html>
        """,
        "https://www.belk.com/home/",
        "ecommerce_listing",
        max_records=10,
        adapter_records=[
            {
                "title": "Elite Airflow Jumbo Pillow",
                "brand": "Sealy",
                "url": "https://www.belk.com/p/sealy-elite-airflow-jumbo-pillow/92002171202220.html",
                "_source": "belk_adapter",
            }
        ],
    )

    assert rows == [
        {
            "source_url": "https://www.belk.com/home/",
            "_source": "dom_listing",
            "title": "Elite Airflow Jumbo Pillow",
            "price": "15.00",
            "currency": "USD",
            "image_url": "https://www.belk.com/images/9200217.jpg",
            "url": "https://www.belk.com/p/sealy-elite-airflow-jumbo-pillow/92002171202220.html?dwvar_color=White",
            "brand": "Sealy",
        }
    ]

@pytest.mark.regression
def test_extract_records_rejects_external_rendered_listing_utility_links() -> None:
    rows = extract_records(
        "<html><body></body></html>",
        "https://www2.hm.com/en_in/men/shoes/view-all.html",
        "ecommerce_listing",
        max_records=10,
        artifacts={
            "rendered_listing_fragments": [
                _rendered_listing_fragment(
                    title="Canvas trainers",
                    url="https://www2.hm.com/en_in/productpage.1309854002.html",
                    price="Rs. 2,799.00",
                ),
                _rendered_listing_fragment(
                    title="Customer Service",
                    url="https://www2.hm.com/en_in/customer-service.html",
                ),
                _rendered_listing_fragment(
                    title="Follow us on Instagram",
                    url="https://www.instagram.com/hm",
                ),
                _rendered_listing_fragment(
                    title="Sustainability",
                    url="https://hmgroup.com/sustainability/",
                ),
            ]
        },
    )

    assert rows == [
        {
            "source_url": "https://www2.hm.com/en_in/men/shoes/view-all.html",
            "_source": "dom_listing",
            "title": "Canvas trainers",
            "price": "2799.00",
            "currency": "INR",
            "url": "https://www2.hm.com/en_in/productpage.1309854002.html",
        }
    ]

@pytest.mark.regression
def test_extract_records_prefers_rich_dom_listing_rows_when_structured_rows_fill_limit() -> (
    None
):
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@graph": [
            {"@type": "Product", "name": "widget-one", "url": "/products/widget-one"},
            {"@type": "Product", "name": "widget-two", "url": "/products/widget-two"},
            {"@type": "Product", "name": "widget-three", "url": "/products/widget-three"},
            {"@type": "Product", "name": "widget-four", "url": "/products/widget-four"},
            {"@type": "Product", "name": "widget-five", "url": "/products/widget-five"}
          ]
        }
        </script>
      </head>
      <body>
        <main>
          <section class="product-grid">
            <article class="product-card">
              <a href="/products/widget-one"><img src="/images/widget-one.jpg" alt="Widget One" /><h2>Widget One</h2></a>
              <span class="price">$19.99</span>
            </article>
            <article class="product-card">
              <a href="/products/widget-two"><img src="/images/widget-two.jpg" alt="Widget Two" /><h2>Widget Two</h2></a>
              <span class="price">$29.99</span>
            </article>
            <article class="product-card">
              <a href="/products/widget-three"><img src="/images/widget-three.jpg" alt="Widget Three" /><h2>Widget Three</h2></a>
              <span class="price">$39.99</span>
            </article>
            <article class="product-card">
              <a href="/products/widget-four"><img src="/images/widget-four.jpg" alt="Widget Four" /><h2>Widget Four</h2></a>
              <span class="price">$49.99</span>
            </article>
            <article class="product-card">
              <a href="/products/widget-five"><img src="/images/widget-five.jpg" alt="Widget Five" /><h2>Widget Five</h2></a>
              <span class="price">$59.99</span>
            </article>
          </section>
        </main>
      </body>
    </html>
    """

    rows = extract_records(
        html,
        "https://example.com/collections/widgets",
        "ecommerce_listing",
        max_records=5,
    )

    assert len(rows) == 5
    assert all(row["_source"] == "dom_listing" for row in rows)
    assert all(row["price"] for row in rows)

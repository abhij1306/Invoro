from __future__ import annotations

from .test_state_mappers import (
    map_js_state_to_fields,
    map_network_payloads_to_fields,
    pytest,
)
from app.services.js_state.variant_options import variant_option_values

@pytest.mark.unit
def test_variant_option_values_reads_attribute_mapping() -> None:
    assert variant_option_values(
        {"attributes": {"Color": "Blue"}},
        option_names=[],
    ) == {"color": "Blue"}
    assert variant_option_values(
        {"attributes": {}, "traits": {"Size": "M"}},
        option_names=[],
    ) == {"size": "M"}

@pytest.mark.unit
def test_map_js_state_to_fields_recovers_existing_state_product_fields() -> None:
    js_state_objects = {
        "__INITIAL_STATE__": {
            "catalog": {
                "selected": {
                    "product": {
                        "id": "sku-123",
                        "name": "Commuter Backpack",
                        "vendor": {"name": "Urban Carry"},
                        "handle": "commuter-backpack",
                        "description": "Weather resistant pack",
                        "type": "Bags",
                        "price": "89.50",
                        "sku": "CB-001",
                        "availability": "In Stock",
                        "image": [
                            "/images/commuter-1.jpg",
                            "/images/commuter-2.jpg",
                        ],
                    }
                }
            }
        }
    }

    mapped = map_js_state_to_fields(
        js_state_objects,
        surface="ecommerce_detail",
        page_url="https://store.example.com/products/commuter-backpack",
    )

    assert mapped["title"] == "Commuter Backpack"
    assert mapped["brand"] == "Urban Carry"
    assert mapped["vendor"] == "Urban Carry"
    assert mapped["handle"] == "commuter-backpack"
    assert mapped["description"] == "Weather resistant pack"
    assert mapped["product_id"] == "sku-123"
    assert "category" not in mapped
    assert mapped["product_type"] == "Bags"
    assert mapped["price"] == "89.50"
    assert mapped["sku"] == "CB-001"
    assert mapped["availability"] == "in_stock"
    assert mapped["image_url"] == "https://store.example.com/images/commuter-1.jpg"
    assert mapped["additional_images"] == [
        "https://store.example.com/images/commuter-2.jpg"
    ]

@pytest.mark.unit
def test_map_js_state_to_fields_ignores_header_payment_state_before_real_product() -> (
    None
):
    js_state_objects = {
        "__INITIAL_STATE__": {
            "header": {
                "paymentMethods": {
                    "title": "We accept",
                    "images": [
                        {"src": "https://cdn.example.com/assets/amex.svg"},
                        {"src": "https://cdn.example.com/assets/paypal.svg"},
                    ],
                }
            },
            "catalog": {
                "selected": {
                    "product": {
                        "id": "sku-123",
                        "name": "Commuter Backpack",
                        "vendor": {"name": "Urban Carry"},
                        "handle": "commuter-backpack",
                        "description": "Weather resistant pack",
                        "type": "Bags",
                        "price": "89.50",
                        "sku": "CB-001",
                        "availability": "In Stock",
                        "image": [
                            "/images/commuter-1.jpg",
                            "/images/commuter-2.jpg",
                        ],
                    }
                }
            },
        }
    }

    mapped = map_js_state_to_fields(
        js_state_objects,
        surface="ecommerce_detail",
        page_url="https://store.example.com/products/commuter-backpack",
    )

    assert mapped["title"] == "Commuter Backpack"
    assert mapped["image_url"] == "https://store.example.com/images/commuter-1.jpg"
    assert mapped["additional_images"] == [
        "https://store.example.com/images/commuter-2.jpg"
    ]

@pytest.mark.unit
def test_map_js_state_to_fields_does_not_merge_variants_from_different_product_identity() -> (
    None
):
    js_state_objects = {
        "__INITIAL_STATE__": {
            "catalog": {
                "selected": {
                    "product": {
                        "id": "sku-123",
                        "name": "Commuter Backpack",
                        "handle": "commuter-backpack",
                        "price": "89.50",
                    }
                }
            }
        },
        "__NEXT_DATA__": {
            "props": {
                "pageProps": {
                    "product": {
                        "id": "sku-999",
                        "title": "Trail Runner",
                        "handle": "trail-runner",
                        "variants": [
                            {"id": 101, "price": 9900, "option1": "Black"},
                            {"id": 102, "price": 10900, "option1": "Sand"},
                        ],
                    }
                }
            }
        },
    }

    mapped = map_js_state_to_fields(
        js_state_objects,
        surface="ecommerce_detail",
        page_url="https://store.example.com/products/commuter-backpack",
    )

    assert mapped["product_id"] == "sku-123"
    assert mapped.get("variants") in (None, [])

@pytest.mark.unit
def test_map_network_payloads_to_fields_recovers_workday_job_detail_payload() -> None:
    mapped = map_network_payloads_to_fields(
        [
            {
                "url": "https://example.wd5.myworkdayjobs.com/wday/cxs/acme/External/job/123",
                "endpoint_type": "job_api",
                "endpoint_family": "workday",
                "body": {
                    "jobPostingInfo": {
                        "title": "Assembler",
                        "jobDescription": "<p>Build things.</p>",
                        "location": "Grafton, WI",
                        "postedOn": "Posted Today",
                        "timeType": "Full time",
                        "jobReqId": "REQ-100",
                        "externalUrl": "https://example.wd5.myworkdayjobs.com/en-US/External/job/123",
                    },
                    "hiringOrganization": {"name": "Acme Manufacturing"},
                },
            }
        ],
        surface="job_detail",
        page_url="https://example.wd5.myworkdayjobs.com/en-US/External/job/123",
    )

    assert mapped == [
        {
            "title": "Assembler",
            "company": "Acme Manufacturing",
            "location": "Grafton, WI",
            "apply_url": "https://example.wd5.myworkdayjobs.com/en-US/External/job/123",
            "url": "https://example.wd5.myworkdayjobs.com/en-US/External/job/123",
            "posted_date": "Posted Today",
            "job_type": "Full time",
            "job_id": "REQ-100",
            "description": "Build things.",
        }
    ]

@pytest.mark.unit
def test_map_js_state_to_fields_recovers_generic_nextjs_product_payload_without_schema_bleed() -> (
    None
):
    mapped = map_js_state_to_fields(
        {
            "__NEXT_DATA__": {
                "props": {
                    "pageProps": {
                        "initialData": {
                            "product": {
                                "id": "prod_42",
                                "name": "Commuter Backpack",
                                "vendor": "Urban Carry",
                                "handle": "commuter-backpack",
                                "description": "Weather resistant pack",
                                "category": "Travel Gear",
                                "type": "Backpacks",
                                "price": "89.50",
                                "sku": "CB-001",
                                "availability": "In Stock",
                                "image": [
                                    "/images/commuter-1.jpg",
                                    "/images/commuter-2.jpg",
                                ],
                            }
                        }
                    }
                }
            }
        },
        surface="ecommerce_detail",
        page_url="https://store.example.com/products/commuter-backpack",
    )

    assert mapped["title"] == "Commuter Backpack"
    assert mapped["category"] == "Travel Gear"
    assert mapped["product_type"] == "Backpacks"
    assert mapped["sku"] == "CB-001"
    assert mapped["image_url"] == "https://store.example.com/images/commuter-1.jpg"

@pytest.mark.unit
def test_map_js_state_to_fields_recovers_nuxt_array_payload_variant() -> None:
    mapped = map_js_state_to_fields(
        {
            "__NUXT_DATA__": [
                {
                    "data": {
                        "product": {
                            "id": "sku-123",
                            "name": "Commuter Backpack",
                            "vendor": {"name": "Urban Carry"},
                            "handle": "commuter-backpack",
                            "description": "Weather resistant pack",
                            "category": "Travel Gear",
                            "product_type": "Backpacks",
                            "price": "89.50",
                            "sku": "CB-001",
                            "availability": "In Stock",
                            "image": [
                                "/images/commuter-1.jpg",
                                "/images/commuter-2.jpg",
                            ],
                        }
                    }
                }
            ]
        },
        surface="ecommerce_detail",
        page_url="https://store.example.com/products/commuter-backpack",
    )

    assert mapped["title"] == "Commuter Backpack"
    assert mapped["category"] == "Travel Gear"
    assert mapped["product_type"] == "Backpacks"
    assert mapped["availability"] == "in_stock"
    assert mapped["image_url"] == "https://store.example.com/images/commuter-1.jpg"

@pytest.mark.unit
def test_map_js_state_to_fields_prefers_richer_nested_product_payload_for_variant_recovery() -> (
    None
):
    mapped = map_js_state_to_fields(
        {
            "__INITIAL_STATE__": {
                "navigation": {
                    "landing": {
                        "title": "iPhone",
                        "id": "landing-node",
                        "url": "/en-us/l/iphone/landing-node",
                    }
                },
                "pdp": {
                    "product": {
                        "id": "phone-14-128",
                        "name": "iPhone 14",
                        "brand": {"name": "Apple"},
                        "description": "Refurbished iPhone 14 with warranty.",
                        "price": "399.00",
                        "currency": "USD",
                        "image": [
                            "https://cdn.example.com/iphone-14-front.jpg",
                            "https://cdn.example.com/iphone-14-back.jpg",
                        ],
                        "variants": [
                            {
                                "id": "good-128",
                                "storage": "128 GB",
                                "condition": "Good",
                                "price": "399.00",
                                "currency": "USD",
                                "availability": "In Stock",
                            },
                            {
                                "id": "excellent-128",
                                "storage": "128 GB",
                                "condition": "Excellent",
                                "price": "459.00",
                                "currency": "USD",
                                "availability": "In Stock",
                            },
                        ],
                    }
                },
            }
        },
        surface="ecommerce_detail",
        page_url="https://store.example.com/products/iphone-14?variant=excellent-128",
    )

    assert mapped["title"] == "iPhone 14"
    assert mapped["brand"] == "Apple"
    assert mapped["price"] == "459.00"
    assert mapped["image_url"] == "https://cdn.example.com/iphone-14-front.jpg"
    assert mapped["additional_images"] == ["https://cdn.example.com/iphone-14-back.jpg"]

@pytest.mark.unit
def test_map_js_state_to_fields_backfills_richer_variant_state_from_later_same_product_object() -> (
    None
):
    mapped = map_js_state_to_fields(
        {
            "__STATE_A__": {
                "product": {
                    "id": "prod-1",
                    "name": "Dress",
                    "price": "99.95",
                    "currency": "USD",
                    "variants": [
                        {
                            "id": "v1",
                            "size": "2",
                            "price": "99.95",
                            "available": False,
                        },
                        {
                            "id": "v2",
                            "size": "4",
                            "price": "99.95",
                            "available": False,
                        },
                    ],
                }
            },
            "__STATE_B__": {
                "product": {
                    "id": "prod-1",
                    "name": "Dress",
                    "variants": [
                        {
                            "id": "v1",
                            "size": "2",
                            "price": "99.95",
                            "available": True,
                            "inventory_quantity": 5,
                            "compare_at_price": "119.95",
                        },
                        {
                            "id": "v2",
                            "size": "4",
                            "price": "99.95",
                            "available": True,
                            "inventory_quantity": 6,
                            "compare_at_price": "119.95",
                        },
                    ],
                }
            },
        },
        surface="ecommerce_detail",
        page_url="https://example.com/p/dress?variant=v1",
    )

    assert mapped["availability"] == "in_stock"
    assert mapped["stock_quantity"] == 5
    assert mapped["original_price"] == "119.95"
    assert mapped["variants"][0]["availability"] == "in_stock"
    assert mapped["variants"][0]["stock_quantity"] == 5
    assert mapped["variants"][1]["availability"] == "in_stock"
    assert mapped["variants"][1]["stock_quantity"] == 6

@pytest.mark.unit
def test_map_js_state_to_fields_preserves_lone_numeric_product_size() -> None:
    mapped = map_js_state_to_fields(
        {
            "__NEXT_DATA__": {
                "props": {
                    "pageProps": {
                        "product": {
                            "id": "prod-1",
                            "name": "Trail Runner",
                            "size": "10",
                            "price": "129.95",
                        }
                    }
                }
            }
        },
        surface="ecommerce_detail",
        page_url="https://example.com/products/trail-runner",
    )

    assert mapped["size"] == "10"

@pytest.mark.unit
def test_map_js_state_to_fields_merges_same_product_sibling_payloads() -> None:
    mapped = map_js_state_to_fields(
        {
            "__NEXT_DATA__": {
                "props": {
                    "pageProps": {
                        "product": {
                            "id": "prod-1",
                            "name": "Trail Runner",
                            "image": "https://example.com/trail.jpg",
                        },
                        "pricing": {
                            "id": "prod-1",
                            "name": "Trail Runner",
                            "price": "129.95",
                            "currency": "USD",
                            "variants": [
                                {"id": "blue-9", "color": "Blue", "size": "9"},
                                {"id": "blue-10", "color": "Blue", "size": "10"},
                                {"id": "red-9", "color": "Red", "size": "9"},
                                {"id": "red-10", "color": "Red", "size": "10"},
                            ],
                        },
                        "recommendations": [
                            {
                                "id": "prod-2",
                                "name": "Other Shoe",
                                "price": "49.00",
                                "currency": "USD",
                            }
                        ],
                    }
                }
            }
        },
        surface="ecommerce_detail",
        page_url="https://example.com/products/trail-runner?variant=blue-9",
    )

    assert mapped["title"] == "Trail Runner"
    assert mapped["price"] == "129.95"

@pytest.mark.unit
def test_map_js_state_to_fields_backfills_url_matched_variant_payload() -> None:
    mapped = map_js_state_to_fields(
        {
            "__STATE_A__": {
                "product": {
                    "id": "prod-1",
                    "name": "Trail Runner Black",
                    "price": "129.95",
                }
            },
            "__STATE_B__": {
                "variantIndex": {
                    "id": "variant-index",
                    "name": "All Sizes",
                    "handle": "trail-runner",
                    "variants": [
                        {"id": "black-9", "color": "Black", "size": "9"},
                        {"id": "black-10", "color": "Black", "size": "10"},
                    ],
                }
            },
        },
        surface="ecommerce_detail",
        page_url="https://example.com/products/trail-runner?variant=black-9",
    )

    assert mapped["title"] == "Trail Runner Black"
    assert mapped["variant_count"] == 2

@pytest.mark.unit
def test_map_js_state_to_fields_prefers_preloaded_state_product_over_app_banner_payload() -> (
    None
):
    mapped = map_js_state_to_fields(
        {
            "__PRELOADED_STATE__": {
                "appBanner": {
                    "name": "UNIQLO - LifeWear",
                    "title": "UNIQLO - LifeWear",
                    "description": "Shop on our app for the best experience",
                    "buttonText": "Open app",
                    "buttonLink": "/app",
                    "appIcon": "https://cdn.example.com/assets/app-icon.png",
                },
                "entity": {
                    "pdpEntity": {
                        "E474244-000-01": {
                            "product": {
                                "name": "AIRism Cotton Crew Neck T-Shirt",
                                "productId": "E474244-000",
                                "productType": "innerwear",
                                "prices": {
                                    "base": {"currency": {"code": "INR"}, "value": 990},
                                    "promo": {
                                        "currency": {"code": "INR"},
                                        "value": 390,
                                    },
                                },
                                "colors": [
                                    {"name": "OLIVE"},
                                    {"name": "BLACK"},
                                ],
                                "sizes": [
                                    {"name": "S"},
                                    {"name": "M"},
                                    {"name": "L"},
                                ],
                                "images": {
                                    "main": {
                                        "57": {
                                            "image": "https://cdn.example.com/products/airism-olive-main.jpg"
                                        }
                                    },
                                    "sub": [
                                        {
                                            "image": "https://cdn.example.com/products/airism-detail-1.jpg"
                                        },
                                        {
                                            "image": "https://cdn.example.com/products/airism-detail-2.jpg"
                                        },
                                    ],
                                },
                            }
                        }
                    }
                },
            }
        },
        surface="ecommerce_detail",
        page_url="https://www.uniqlo.com/in/en/products/E474244-000/01",
    )

    assert mapped["title"] == "AIRism Cotton Crew Neck T-Shirt"
    assert mapped["product_id"] == "E474244-000"
    assert mapped["product_type"] == "innerwear"
    assert mapped["price"] == "390"
    assert mapped["original_price"] == "990"
    assert mapped["currency"] == "INR"
    assert (
        mapped["image_url"] == "https://cdn.example.com/products/airism-olive-main.jpg"
    )
    assert mapped["additional_images"] == [
        "https://cdn.example.com/products/airism-detail-1.jpg",
        "https://cdn.example.com/products/airism-detail-2.jpg",
    ]

@pytest.mark.unit
def test_map_js_state_to_fields_recovers_direct_grade_and_storage_axes_from_variants() -> (
    None
):
    mapped = map_js_state_to_fields(
        {
            "__INITIAL_STATE__": {
                "product": {
                    "id": "console-1tb",
                    "name": "Game Console",
                    "variants": [
                        {
                            "id": "fair-512",
                            "grade": "Fair",
                            "storage": "512 GB",
                            "price": "249.00",
                            "currency": "USD",
                        },
                        {
                            "id": "good-1tb",
                            "grade": "Good",
                            "storage": "1 TB",
                            "price": "299.00",
                            "currency": "USD",
                        },
                    ],
                }
            }
        },
        surface="ecommerce_detail",
        page_url="https://store.example.com/products/game-console?variant=good-1tb",
    )

    assert mapped["title"] == "Game Console"
    assert mapped["price"] == "299.00"

@pytest.mark.unit
def test_map_js_state_to_fields_replaces_existing_variant_query_parameter() -> None:
    mapped = map_js_state_to_fields(
        {
            "__INITIAL_STATE__": {
                "product": {
                    "name": "Commuter Backpack",
                    "variants": [
                        {
                            "id": "sku-123",
                            "available": True,
                        }
                    ],
                }
            }
        },
        surface="ecommerce_detail",
        page_url="https://store.example.com/products/commuter-backpack?ref=hero&variant=old",
    )

    assert mapped["variants"][0]["url"] == (
        "https://store.example.com/products/commuter-backpack?ref=hero&variant=sku-123"
    )

@pytest.mark.unit
def test_map_js_state_to_fields_keeps_ambiguous_availability_neutral() -> None:
    mapped = map_js_state_to_fields(
        {
            "__INITIAL_STATE__": {
                "product": {
                    "name": "Commuter Backpack",
                    "variants": [
                        {
                            "id": "sku-123",
                            "available": 2,
                        }
                    ],
                }
            }
        },
        surface="ecommerce_detail",
        page_url="https://store.example.com/products/commuter-backpack",
    )

    assert "availability" not in mapped
    assert "availability" not in mapped["variants"][0]

@pytest.mark.unit
def test_map_js_state_to_fields_drops_transport_only_variant_matrix_rows() -> None:
    mapped = map_js_state_to_fields(
        {
            "__INITIAL_STATE__": {
                "product": {
                    "name": "Relaxed Tee",
                    "price": "32.99",
                    "variantMatrix": [
                        {
                            "isLeaf": True,
                            "variantValueCategory": {"name": "M"},
                            "parentVariantCategory": {"name": "Size"},
                            "variantOption": {
                                "code": "tee-m",
                                "url": "/products/relaxed-tee?size=m",
                                "priceData": {"value": "32.99", "currencyIso": "USD"},
                                "stock": {
                                    "stockLevel": 4,
                                    "stockLevelStatus": "inStock",
                                },
                            },
                        },
                        {
                            "isLeaf": True,
                            "variantOption": {
                                "code": "tee-orphan",
                                "url": "/products/relaxed-tee?size=unknown",
                                "priceData": {"value": "32.99", "currencyIso": "USD"},
                                "stock": {
                                    "stockLevel": 2,
                                    "stockLevelStatus": "inStock",
                                },
                            },
                        },
                    ],
                }
            }
        },
        surface="ecommerce_detail",
        page_url="https://store.example.com/products/relaxed-tee?size=m",
    )

    assert mapped["variant_count"] == 1
    assert mapped["size"] == "M"
    assert len(mapped["variants"]) == 1
    assert mapped["variants"][0]["size"] == "M"
    assert mapped["variants"][0]["sku"] == "tee-m"
    assert mapped["variants"][0]["price"] == "32.99"
    assert mapped["variants"][0]["currency"] == "USD"
    assert mapped["variants"][0]["url"] == "/products/relaxed-tee?size=m"
    assert mapped["variants"][0]["availability"] == "in_stock"
    assert mapped["variants"][0]["stock_quantity"] == 4

@pytest.mark.unit
def test_map_js_state_to_fields_ignores_malformed_variant_matrix_stock_level() -> None:
    mapped = map_js_state_to_fields(
        {
            "__INITIAL_STATE__": {
                "product": {
                    "name": "Relaxed Tee",
                    "price": "32.99",
                    "variantMatrix": [
                        {
                            "isLeaf": True,
                            "variantValueCategory": {"name": "M"},
                            "parentVariantCategory": {"name": "Size"},
                            "variantOption": {
                                "code": "tee-m",
                                "stock": {
                                    "stockLevel": "unknown",
                                    "stockLevelStatus": "inStock",
                                },
                            },
                        }
                    ],
                }
            }
        },
        surface="ecommerce_detail",
        page_url="https://store.example.com/products/relaxed-tee?size=m",
    )

    assert mapped["variants"][0]["availability"] == "in_stock"
    assert "stock_quantity" not in mapped["variants"][0]

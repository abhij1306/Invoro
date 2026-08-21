from __future__ import annotations

from .test_state_mappers import *  # noqa: F403


@pytest.mark.unit
def test_availability_value_normalizes_primary_string_aliases() -> None:
    assert availability_value({"availability": "out-of-stock"}) == "out_of_stock"
    assert availability_value({"inventory_status": "unavailable"}) == "out_of_stock"
    assert availability_value({"stock_status": "0"}) == "out_of_stock"

@pytest.mark.unit
def test_map_js_state_to_fields_recovers_next_data_shopify_product_fields() -> None:
    js_state_objects = {
        "__NEXT_DATA__": {
            "props": {
                "pageProps": {
                    "product": {
                        "id": 9001,
                        "title": "Trail Runner",
                        "vendor": "Acme Outdoors",
                        "handle": "trail-runner",
                        "body_html": "<p>Stable all-terrain shoe.</p>",
                        "product_type": "Shoes",
                        "currency": "USD",
                        "images": [
                            {"src": "https://cdn.example.com/products/trail-1.jpg"},
                            {"src": "https://cdn.example.com/products/trail-2.jpg"},
                        ],
                        "options": [{"name": "Color"}, {"name": "Size"}],
                        "variants": [
                            {
                                "id": 101,
                                "sku": "TRAIL-BLK-8",
                                "price": 9900,
                                "compare_at_price": 12900,
                                "available": True,
                                "inventory_quantity": 7,
                                "featured_image": {
                                    "src": "https://cdn.example.com/products/trail-black-8.jpg"
                                },
                                "option1": "Black",
                                "option2": "8",
                                "barcode": "1111111111111",
                            },
                            {
                                "id": 102,
                                "sku": "TRAIL-SND-9",
                                "price": 10900,
                                "compare_at_price": 13900,
                                "available": False,
                                "inventory_quantity": 0,
                                "featured_image": {
                                    "src": "https://cdn.example.com/products/trail-sand-9.jpg"
                                },
                                "option1": "Sand",
                                "option2": "9",
                                "barcode": "2222222222222",
                            },
                        ],
                    }
                }
            }
        }
    }

    mapped = map_js_state_to_fields(
        js_state_objects,
        surface="ecommerce_detail",
        page_url="https://store.example.com/products/trail-runner?variant=102",
    )

    expected_fields = {
        "title": "Trail Runner",
        "brand": "Acme Outdoors",
        "vendor": "Acme Outdoors",
        "handle": "trail-runner",
        "description": "Stable all-terrain shoe.",
        "product_id": 9001,
        "product_type": "Shoes",
        "price": "109",
        "original_price": "139",
        "currency": "USD",
        "availability": "out_of_stock",
        "stock_quantity": 0,
        "sku": "TRAIL-SND-9",
        "barcode": "2222222222222",
        "color": "Sand",
        "size": "9",
        "image_url": "https://cdn.example.com/products/trail-sand-9.jpg",
        "variant_count": 2,
    }
    assert {key: mapped[key] for key in expected_fields} == expected_fields
    assert "category" not in mapped
    assert mapped["additional_images"] == [
        "https://cdn.example.com/products/trail-2.jpg"
    ]
    assert mapped["variants"][1]["stock_quantity"] == 0
    assert (
        mapped["variants"][1]["url"]
        == "https://store.example.com/products/trail-runner?variant=102"
    )

@pytest.mark.unit
def test_map_js_state_to_fields_recovers_axis_keyed_variant_dict_rows() -> None:
    mapped = map_js_state_to_fields(
        {
            "__INITIAL_STATE__": {
                "product": {
                    "id": "19759526",
                    "title": "Puma Men Radcliff Black Sneakers",
                    "brand": "Puma",
                    "price": 1650,
                    "currency": "INR",
                    "variants": {
                        "size": [
                            {
                                "sku": "PUMAX00412442",
                                "id": "19758924",
                                "variant_id": "4694",
                                "name": "UK 6",
                                "in_stock": "0",
                            },
                            {
                                "sku": "PUMAX00412443",
                                "id": "19758925",
                                "variant_id": "4695",
                                "name": "UK 7",
                                "in_stock": "1",
                            },
                        ]
                    },
                }
            }
        },
        surface="ecommerce_detail",
        page_url="https://www.nykaafashion.com/puma-men-radcliff-black-sneakers/p/19759526",
    )

    assert mapped["variant_count"] == 2
    assert [variant["size"] for variant in mapped["variants"]] == ["UK 6", "UK 7"]
    assert [variant["sku"] for variant in mapped["variants"]] == [
        "PUMAX00412442",
        "PUMAX00412443",
    ]
    assert [variant["availability"] for variant in mapped["variants"]] == [
        "out_of_stock",
        "in_stock",
    ]

@pytest.mark.unit
def test_map_js_state_to_fields_drops_geographic_state_dropdown_variants() -> None:
    mapped = map_js_state_to_fields(
        {
            "__NEXT_DATA__": {
                "props": {
                    "pageProps": {
                        "product": {
                            "sku": "4147C002",
                            "title": "EOS R5 Body",
                            "brand": "Canon",
                            "price": "2999.00",
                            "currency": "USD",
                            "options": [{"name": "State"}],
                            "variants": [
                                {"option1": "Alabama"},
                                {"option1": "Alaska"},
                                {"option1": "California"},
                                {"option1": "Texas"},
                            ],
                        }
                    }
                }
            }
        },
        surface="ecommerce_detail",
        page_url="https://www.usa.canon.com/shop/p/eos-r5",
    )

    assert mapped["title"] == "EOS R5 Body"
    assert mapped["sku"] == "4147C002"
    assert mapped["price"] == "2999.00"
    assert "variants" not in mapped
    assert "variant_count" not in mapped

@pytest.mark.unit
def test_map_js_state_to_fields_keeps_bridge_variants_with_primary_rows() -> None:
    mapped = map_js_state_to_fields(
        {
            "product": {
                "title": "Example Tee",
                "variants": [{"id": "base", "size": "S"}],
                "plp_pdp_bridge": {
                    "variants": {
                        "color": [
                            {"id": "black", "name": "Black"},
                            {"id": "white", "name": "White"},
                        ]
                    }
                },
            }
        },
        surface="ecommerce_detail",
        page_url="https://example.com/products/example-tee",
    )

    assert {variant.get("color") for variant in mapped["variants"]} >= {
        "Black",
        "White",
    }

@pytest.mark.unit
def test_map_js_state_to_fields_treats_shopify_product_level_prices_as_cents() -> None:
    mapped = map_js_state_to_fields(
        {
            "__NEXT_DATA__": {
                "props": {
                    "pageProps": {
                        "product": {
                            "id": 123,
                            "title": "Abzorb 1890 Sneaker",
                            "handle": "abzorb-1890-sneaker",
                            "currency": "USD",
                            "prices": {
                                "currentPrice": 19650,
                                "initialPrice": 22000,
                            },
                            "variants": [
                                {
                                    "id": 53040530784367,
                                    "sku": "U18908JY-5",
                                    "option1": "5 M",
                                    "available": True,
                                }
                            ],
                        }
                    }
                }
            }
        },
        surface="ecommerce_detail",
        page_url="https://www.notre-shop.com/products/abzorb-1890-sneaker",
    )

    # Cents-trigger: no prices.currency, so product-level currency makes numeric prices cents.
    assert mapped["handle"] == "abzorb-1890-sneaker"
    assert mapped["currency"] == "USD"
    assert mapped["price"] == "USD 196.50"
    assert mapped["original_price"] == "USD 220.00"

@pytest.mark.unit
def test_map_js_state_to_fields_handles_null_product_type() -> None:
    mapped = map_js_state_to_fields(
        {
            "__NEXT_DATA__": {
                "props": {
                    "pageProps": {
                        "product": {
                            "id": 123,
                            "title": "Trail Runner",
                            "type": None,
                            "product_type": None,
                            "productType": None,
                            "@type": None,
                            "price": 99,
                            "currency": "USD",
                        }
                    }
                }
            }
        },
        surface="ecommerce_detail",
        page_url="https://store.example.com/products/trail-runner",
    )

    assert mapped["title"] == "Trail Runner"

@pytest.mark.unit
def test_map_js_state_to_fields_recovers_shopify_available_sizes_rows() -> None:
    mapped = map_js_state_to_fields(
        {
            "__NEXT_DATA__": {
                "props": {
                    "pageProps": {
                        "productData": {
                            "product": {
                                "id": 6804846346442,
                                "title": 'Arrival 5" Shorts',
                                "handle": "gymshark-arrival-5-shorts-black-ss22",
                                "colour": "Black",
                                "price": 26,
                                "currencyCode": "USD",
                                "availableSizes": [
                                    {
                                        "id": 39786362568906,
                                        "inStock": True,
                                        "inventoryQuantity": 9170,
                                        "price": 26,
                                        "size": "xs",
                                        "sku": "A2A1M-BBBB-XS",
                                        "barcode": "5057913931872",
                                    },
                                    {
                                        "id": 39786362601674,
                                        "inStock": False,
                                        "inventoryQuantity": 0,
                                        "price": 26,
                                        "size": "s",
                                        "sku": "A2A1M-BBBB-S",
                                        "barcode": "5057913931865",
                                    },
                                ],
                            }
                        }
                    }
                }
            }
        },
        surface="ecommerce_detail",
        page_url="https://www.gymshark.com/products/gymshark-arrival-5-shorts-black-ss22",
    )

    assert mapped["title"] == 'Arrival 5" Shorts'
    assert mapped["variant_count"] == 2
    assert [variant["size"] for variant in mapped["variants"]] == ["xs", "s"]
    assert [variant["sku"] for variant in mapped["variants"]] == [
        "A2A1M-BBBB-XS",
        "A2A1M-BBBB-S",
    ]
    assert mapped["variants"][0]["availability"] == "in_stock"
    assert mapped["variants"][0]["stock_quantity"] == 9170
    assert mapped["variants"][1]["availability"] == "out_of_stock"
    assert mapped["variants"][1]["stock_quantity"] == 0

@pytest.mark.unit
def test_map_js_state_to_fields_merges_same_family_sibling_product_urls() -> None:
    mapped = map_js_state_to_fields(
        {
            "__NEXT_DATA__": {
                "props": {
                    "pageProps": {
                        "productData": {
                            "product": {
                                "id": 6804846346442,
                                "title": 'Arrival 5" Shorts',
                                "handle": "gymshark-arrival-5-shorts-black-ss22",
                                "colour": "Black",
                                "price": 26,
                                "currencyCode": "USD",
                                "onlineStoreUrl": "https://www.gymshark.com/products/gymshark-arrival-5-shorts-black-ss22",
                                "availableSizes": [
                                    {
                                        "id": 101,
                                        "inStock": True,
                                        "inventoryQuantity": 9,
                                        "price": 26,
                                        "size": "s",
                                        "sku": "A2A1M-BBBB-S",
                                    },
                                    {
                                        "id": 102,
                                        "inStock": True,
                                        "inventoryQuantity": 7,
                                        "price": 26,
                                        "size": "m",
                                        "sku": "A2A1M-BBBB-M",
                                    },
                                ],
                            },
                            "variants": [
                                {
                                    "id": 6804846117066,
                                    "title": 'Gymshark Arrival 5" Shorts - White',
                                    "handle": "gymshark-arrival-5-shorts-white-ss22",
                                    "colour": "White",
                                    "price": 26,
                                    "currencyCode": "USD",
                                    "onlineStoreUrl": "https://www.gymshark.com/products/gymshark-arrival-5-shorts-white-ss22",
                                    "availableSizes": [
                                        {
                                            "id": 201,
                                            "inStock": True,
                                            "inventoryQuantity": 6,
                                            "price": 26,
                                            "size": "s",
                                            "sku": "A2A1M-WWWW-S",
                                        },
                                        {
                                            "id": 202,
                                            "inStock": False,
                                            "inventoryQuantity": 0,
                                            "price": 26,
                                            "size": "m",
                                            "sku": "A2A1M-WWWW-M",
                                        },
                                    ],
                                }
                            ],
                        }
                    }
                }
            }
        },
        surface="ecommerce_detail",
        page_url="https://www.gymshark.com/products/gymshark-arrival-5-shorts-black-ss22",
    )

    assert mapped["title"] == 'Arrival 5" Shorts'
    assert mapped["variant_count"] == 4
    assert {
        (variant["color"], variant["size"], variant["url"])
        for variant in mapped["variants"]
    } == {
        (
            "Black",
            "s",
            "https://www.gymshark.com/products/gymshark-arrival-5-shorts-black-ss22",
        ),
        (
            "Black",
            "m",
            "https://www.gymshark.com/products/gymshark-arrival-5-shorts-black-ss22",
        ),
        (
            "White",
            "s",
            "https://www.gymshark.com/products/gymshark-arrival-5-shorts-white-ss22",
        ),
        (
            "White",
            "m",
            "https://www.gymshark.com/products/gymshark-arrival-5-shorts-white-ss22",
        ),
    }

@pytest.mark.unit
def test_map_js_state_to_fields_reads_variant_attributes_axes() -> None:
    mapped = map_js_state_to_fields(
        {
            "nuxt": {
                "product": {
                    "id": "VN000E9TBPG",
                    "name": "Old Skool Shoe",
                    "currency": "USD",
                    "price": {"current": 85},
                    "attributes": [
                        {
                            "type": "color",
                            "options": [
                                {
                                    "id": "VN000E9TBPG",
                                    "value": "VN000E9TBPG - True White",
                                    "label": "True White",
                                }
                            ],
                        },
                        {
                            "type": "size",
                            "options": [
                                {
                                    "value": "8.5 Men = 10.0 Women",
                                    "label": "M8.5 / W10",
                                }
                            ],
                        },
                    ],
                    "variants": [
                        {
                            "id": "VN:000E9T:BPG:085:M:1:",
                            "price": {"current": 85},
                            "attributes": {
                                "color": "VN000E9TBPG - True White",
                                "size": "8.5 Men = 10.0 Women",
                            },
                        }
                    ],
                }
            }
        },
        surface="ecommerce_detail",
        page_url="https://www.vans.com/en-us/p/old-skool-VN000E9TBPG",
    )

    assert mapped["variants"][0]["color"] == "True White"
    assert mapped["variants"][0]["size"] == "M8.5 / W10"
    assert mapped["color"] == "True White"
    assert mapped["size"] == "M8.5 / W10"

@pytest.mark.unit
def test_map_js_state_to_fields_reads_variant_traits_axes() -> None:
    mapped = map_js_state_to_fields(
        {
            "__NEXT_DATA__": {
                "props": {
                    "pageProps": {
                        "product": {
                            "id": "stockx-1",
                            "title": "Nike Dunk Low Retro White Black Panda",
                            "brand": "Nike",
                            "variants": [
                                {
                                    "id": "size-35",
                                    "traits": {"size": "3.5"},
                                    "sizeChart": {"baseSize": "3.5"},
                                },
                                {
                                    "id": "size-4",
                                    "traits": {"size": "4"},
                                    "sizeChart": {"baseSize": "4"},
                                },
                            ],
                        }
                    }
                }
            }
        },
        surface="ecommerce_detail",
        page_url="https://stockx.com/nike-dunk-low-retro-white-black-2021",
    )

    assert mapped["variant_count"] == 2
    assert [variant["size"] for variant in mapped["variants"]] == ["3.5", "4"]
    assert [variant["url"] for variant in mapped["variants"]] == [
        "https://stockx.com/nike-dunk-low-retro-white-black-2021?variant=size-35",
        "https://stockx.com/nike-dunk-low-retro-white-black-2021?variant=size-4",
    ]

@pytest.mark.unit
def test_map_js_state_to_fields_reads_target_variation_hierarchy() -> None:
    mapped = map_js_state_to_fields(
        {
            "__NEXT_DATA__": {
                "props": {
                    "dehydratedState": {
                        "queries": [
                            {
                                "state": {
                                    "data": {
                                        "data": {
                                            "product": {
                                                "tcin": "1002150739",
                                                "item": {
                                                    "product_description": {
                                                        "title": "Tobago Stripe Duvet Cover Set - Levtex Home"
                                                    },
                                                    "enrichment": {
                                                        "buy_url": "https://www.target.com/p/tobago/-/A-1002150739"
                                                    },
                                                },
                                                "variation_hierarchy": [
                                                    {
                                                        "name": "size",
                                                        "value": "full/queen",
                                                        "tcin": "1002150738",
                                                        "buy_url": "https://www.target.com/p/tobago-full/-/A-1002150738",
                                                    },
                                                    {
                                                        "name": "size",
                                                        "value": "twin/twin xl",
                                                        "tcin": "1002150742",
                                                        "buy_url": "https://www.target.com/p/tobago-twin/-/A-1002150742",
                                                    },
                                                ],
                                            }
                                        }
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        },
        surface="ecommerce_detail",
        page_url="https://www.target.com/p/tobago/-/A-1002150739?preselect=1002150742",
    )

    assert mapped["title"] == "Tobago Stripe Duvet Cover Set - Levtex Home"
    assert mapped["product_id"] == "1002150739"
    assert mapped["variant_count"] == 2
    assert [variant["size"] for variant in mapped["variants"]] == [
        "full/queen",
        "twin/twin xl",
    ]
    assert [variant["url"] for variant in mapped["variants"]] == [
        "https://www.target.com/p/tobago-full/-/A-1002150738",
        "https://www.target.com/p/tobago-twin/-/A-1002150742",
    ]

@pytest.mark.unit
def test_map_js_state_to_fields_uses_variation_attribute_display_names() -> None:
    mapped = map_js_state_to_fields(
        {
            "mobify-data": {
                "product": {
                    "id": "2078471",
                    "name": "Terminal Roamer Pants",
                    "brand": "Columbia",
                    "currency": "USD",
                    "price": 60,
                    "variationAttributes": [
                        {
                            "id": "color",
                            "name": "Color",
                            "values": [
                                {"value": "019", "name": "Cool Grey"},
                                {"value": "023", "name": "City Grey"},
                            ],
                        },
                        {
                            "id": "size",
                            "name": "Size",
                            "values": [
                                {"value": "S", "name": "S"},
                                {"value": "M", "name": "M"},
                            ],
                        },
                    ],
                    "variants": [
                        {
                            "id": "195980349741",
                            "sku": "195980349741",
                            "variationValues": {"color": "019", "size": "S"},
                        },
                        {
                            "id": "195980349888",
                            "sku": "195980349888",
                            "variationValues": {"color": "023", "size": "M"},
                        },
                    ],
                }
            }
        },
        surface="ecommerce_detail",
        page_url="https://www.columbia.com/p/mens-pfg-terminal-roamer-stretch-pants-2078471.html?color=019&size=S",
    )

    assert mapped["color"] == "Cool Grey"
    assert mapped["size"] == "S"

@pytest.mark.unit
def test_map_js_state_to_fields_does_not_pick_arbitrary_parent_size_without_explicit_selection() -> (
    None
):
    mapped = map_js_state_to_fields(
        {
            "__NEXT_DATA__": {
                "props": {
                    "pageProps": {
                        "product": {
                            "id": "af1-1",
                            "title": "Air Force 1",
                            "brand": "Nike",
                            "prices": {
                                "currency": "USD",
                                "currentPrice": 115,
                                "initialPrice": 130,
                            },
                            "options": [{"name": "Size"}],
                            "variants": [
                                {
                                    "id": "size-6",
                                    "available": True,
                                    "sku": "AF1-6",
                                    "selectedOptions": [{"name": "Size", "value": "6"}],
                                },
                                {
                                    "id": "size-7",
                                    "available": True,
                                    "sku": "AF1-7",
                                    "selectedOptions": [{"name": "Size", "value": "7"}],
                                },
                            ],
                        }
                    }
                }
            }
        },
        surface="ecommerce_detail",
        page_url="https://store.example.com/products/air-force-1",
    )

    assert mapped["price"] == "USD 115"
    assert mapped["original_price"] == "USD 130"
    assert mapped["currency"] == "USD"
    assert mapped["variant_count"] == 2
    assert "size" not in mapped
    assert "sku" not in mapped

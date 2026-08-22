from __future__ import annotations

from .test_state_mappers import js_state_mapper, map_configured_state_payload, map_js_state_to_fields, map_network_payloads_to_fields, pytest  # fmt: skip

@pytest.mark.unit
def test_job_detail_mappers_keep_shared_html_section_behavior() -> None:
    description_html = (
        "<p>Lead platform delivery.</p>"
        "<h2>What you'll do</h2><ul><li>Ship backend systems.</li></ul>"
        "<h2>You should have</h2><ul><li>Python experience.</li></ul>"
        "<h2>Benefits</h2><p>Remote-first.</p>"
        "<h3>Skills</h3><p>Clear writing.</p>"
    )

    js_mapped = map_js_state_to_fields(
        {
            "__remixContext": {
                "state": {
                    "loaderData": {
                        "routes/$url_token_.jobs_.$job_post_id": {
                            "jobPost": {
                                "title": "Platform Engineer",
                                "company_name": "Acme",
                                "job_post_location": "Remote",
                                "public_url": "https://jobs.example.com/platform-engineer",
                                "published_at": "2026-04-10",
                                "content": description_html,
                            }
                        }
                    }
                }
            }
        },
        surface="job_detail",
        page_url="https://jobs.example.com/platform-engineer",
    )
    network_rows = map_network_payloads_to_fields(
        [
            {
                "body": {
                    "title": "Platform Engineer",
                    "company_name": "Acme",
                    "location": {"name": "Remote"},
                    "absolute_url": "https://jobs.example.com/platform-engineer",
                    "first_published": "2026-04-10",
                    "updated_at": "2026-04-12",
                    "content": description_html,
                }
            }
        ],
        surface="job_detail",
        page_url="https://jobs.example.com/platform-engineer",
    )

    assert js_mapped["responsibilities"] == "Ship backend systems."
    assert js_mapped["qualifications"] == "Python experience."
    assert js_mapped["benefits"] == "Remote-first."
    assert js_mapped["skills"] == "Clear writing."
    assert js_mapped["description"] == (
        "Lead platform delivery. What you'll do Ship backend systems. "
        "You should have Python experience. Benefits Remote-first. "
        "Skills Clear writing."
    )
    assert network_rows == [
        {
            "title": "Platform Engineer",
            "company": "Acme",
            "location": "Remote",
            "apply_url": "https://jobs.example.com/platform-engineer",
            "posted_date": "2026-04-10",
            "updated_at": "2026-04-12",
            "responsibilities": "Ship backend systems.",
            "qualifications": "Python experience.",
            "benefits": "Remote-first.",
            "skills": "Clear writing.",
            "description": js_mapped["description"],
            "url": "https://jobs.example.com/platform-engineer",
        }
    ]

@pytest.mark.unit
def test_map_js_state_to_fields_uses_platform_owned_job_detail_selector_config() -> (
    None
):
    mapped = map_js_state_to_fields(
        {
            "__remixContext": {
                "state": {
                    "loaderData": {
                        "routes/$url_token_.jobs_.$job_post_id": {
                            "jobPost": {
                                "title": "Manager, Engineering",
                                "company_name": "Greenhouse",
                                "job_post_location": "Ontario",
                                "public_url": "https://job-boards.greenhouse.io/greenhouse/jobs/7704699?gh_jid=7704699",
                                "published_at": "2026-04-09T10:05:53-04:00",
                                "content": (
                                    "<p>Lead the reporting and analytics engineering domain.</p>"
                                    "<h2>What you’ll do</h2><ul><li>Lead and mentor engineers.</li></ul>"
                                    "<h2>You should have</h2><ul><li>5+ years of engineering experience.</li></ul>"
                                ),
                            }
                        }
                    }
                }
            }
        },
        surface="job_detail",
        page_url="https://job-boards.greenhouse.io/greenhouse/jobs/7704699?gh_jid=7704699",
    )

    assert mapped["title"] == "Manager, Engineering"
    assert mapped["company"] == "Greenhouse"
    assert mapped["location"] == "Ontario"
    assert (
        mapped["apply_url"]
        == "https://job-boards.greenhouse.io/greenhouse/jobs/7704699?gh_jid=7704699"
    )
    assert mapped["posted_date"] == "2026-04-09T10:05:53-04:00"
    assert "Lead and mentor engineers." in mapped["responsibilities"]
    assert "5+ years of engineering experience." in mapped["qualifications"]
    assert (
        mapped["url"]
        == "https://job-boards.greenhouse.io/greenhouse/jobs/7704699?gh_jid=7704699"
    )

@pytest.mark.unit
def test_configured_state_payload_merges_later_root_fields() -> None:
    mapped = map_configured_state_payload(
        {
            "first": {"title": "Platform Engineer"},
            "second": {"company_name": "Acme"},
        },
        root_paths=[["first"], ["second"]],
        field_paths={
            "title": [["title"]],
            "company": [["company_name"]],
        },
    )

    assert mapped == {"title": "Platform Engineer", "company": "Acme"}

@pytest.mark.unit
def test_map_js_state_to_fields_rejects_dict_tags_from_promotional_ui() -> None:
    js_state_objects = {
        "__NEXT_DATA__": {
            "props": {
                "pageProps": {
                    "product": {
                        "id": 9002,
                        "title": "Maternity Jean",
                        "vendor": "Hatch",
                        "handle": "the-relaxed-wide-leg-maternity-jean-1",
                        "body_html": "<p>Comfortable maternity denim.</p>",
                        "product_type": "Jeans",
                        "currency": "USD",
                        "tags": {
                            "button": "Add",
                            "freeGiftHint": "Free gift",
                            "freeGiftWarning": "Add gift to cart to proceed to checkout",
                            "goalReached": "Congrats - all tiers unlocked!",
                            "rewardName1": "20% off",
                            "rewardName2": "25% off",
                            "rewardName3": "30% off",
                        },
                        "variants": [
                            {
                                "id": 201,
                                "sku": "HJ-BLU-28",
                                "price": 19800,
                                "compare_at_price": 24800,
                                "available": True,
                                "option1": "Blue",
                                "option2": "28",
                            }
                        ],
                        "options": [{"name": "Color"}, {"name": "Size"}],
                        "images": [
                            {"src": "https://cdn.example.com/jean-1.jpg"},
                        ],
                    }
                }
            }
        }
    }
    mapped = map_js_state_to_fields(
        js_state_objects,
        surface="ecommerce_detail",
        page_url="https://www.hatchcollection.com/products/the-relaxed-wide-leg-maternity-jean-1",
    )
    assert mapped.get("title") == "Maternity Jean"
    assert mapped.get("tags") is None

@pytest.mark.unit
def test_map_product_payload_tolerates_product_glom_failures(
    monkeypatch,
) -> None:
    original_glom = js_state_mapper.glom

    def _fake_glom(target, spec, default=None):
        if spec is js_state_mapper.PRODUCT_FIELD_SPEC:
            raise RuntimeError("boom")
        return original_glom(target, spec, default=default)

    monkeypatch.setattr(js_state_mapper, "glom", _fake_glom)

    mapped = js_state_mapper._map_product_payload(
        {"id": "prod-1", "variants": []},
        page_url="https://store.example.com/products/commuter-backpack",
        category_fallback_from_type=False,
    )

    assert mapped == {}

@pytest.mark.unit
def test_map_product_payload_uses_configured_jmespaths_when_glom_fails(
    monkeypatch,
) -> None:
    original_glom = js_state_mapper.glom

    def _fake_glom(target, spec, default=None):
        if spec is js_state_mapper.PRODUCT_FIELD_SPEC:
            raise RuntimeError("boom")
        return original_glom(target, spec, default=default)

    monkeypatch.setattr(js_state_mapper, "glom", _fake_glom)

    mapped = js_state_mapper._map_product_payload(
        {
            "name": "Config Mapped Pack",
            "vendor": {"name": "Urban Carry"},
            "price": "89.50",
            "variants": [],
        },
        page_url="https://store.example.com/products/config-mapped-pack",
        category_fallback_from_type=False,
        field_jmespaths={
            "title": ["title", "name"],
            "brand": ["brand.name", "brand", "vendor.name", "vendor"],
            "price": ["price"],
        },
    )

    assert mapped == {
        "title": "Config Mapped Pack",
        "brand": "Urban Carry",
        "price": "89.50",
    }

@pytest.mark.unit
def test_map_product_payload_normalizes_raw_price_fallbacks() -> None:
    mapped = js_state_mapper._map_product_payload(
        {
            "id": "prod-1",
            "variants": [],
            "prices": {
                "currentPrice": "$129.50",
                "initialPrice": {"value": 149},
            },
        },
        page_url="https://store.example.com/products/commuter-backpack",
        category_fallback_from_type=False,
    )

    assert mapped["price"] == "129.50"
    assert mapped["original_price"] == "149"

@pytest.mark.unit
def test_normalize_variant_tolerates_non_dict_glom_result(
    monkeypatch,
) -> None:
    original_glom = js_state_mapper.glom

    def _fake_glom(target, spec, default=None):
        if spec is js_state_mapper._VARIANT_FIELD_SPEC:
            return None
        return original_glom(target, spec, default=default)

    monkeypatch.setattr(js_state_mapper, "glom", _fake_glom)

    mapped = js_state_mapper._normalize_variant(
        {"id": "sku-123"},
        option_names=[],
        page_url="https://store.example.com/products/commuter-backpack",
        interpret_integral_as_cents=False,
    )

    assert mapped == {
        "variant_id": "sku-123",
        "url": "https://store.example.com/products/commuter-backpack?variant=sku-123",
    }

@pytest.mark.unit
def test_normalize_variant_does_not_use_product_id_as_variant_id() -> None:
    mapped = js_state_mapper._normalize_variant(
        {"productId": "prod-1"},
        option_names=[],
        page_url="https://store.example.com/products/commuter-backpack",
        interpret_integral_as_cents=False,
    )

    assert mapped is None

@pytest.mark.unit
def test_map_js_state_to_fields_uses_selected_options_and_skips_marketing_axis_names() -> (
    None
):
    mapped = map_js_state_to_fields(
        {
            "__NEXT_DATA__": {
                "props": {
                    "pageProps": {
                        "product": {
                            "id": "leggings-1",
                            "title": "Everyday Seamless Leggings",
                            "vendor": "Gym Co",
                            "price": "58.00",
                            "currency": "USD",
                            "options": [
                                {"name": "Soft Fabric"},
                                {"name": "High Waisted"},
                            ],
                            "variants": [
                                {
                                    "id": "black-s",
                                    "available": True,
                                    "selectedOptions": [
                                        {"name": "Color", "value": "Black"},
                                        {"name": "Size", "value": "S"},
                                    ],
                                },
                                {
                                    "id": "black-m",
                                    "available": True,
                                    "selectedOptions": [
                                        {"name": "Color", "value": "Black"},
                                        {"name": "Size", "value": "M"},
                                    ],
                                },
                            ],
                        }
                    }
                }
            }
        },
        surface="ecommerce_detail",
        page_url="https://store.example.com/products/everyday-seamless-leggings?variant=black-s",
    )

    assert mapped["variant_count"] == 2
    assert mapped["variants"][0]["option_values"] == {"color": "Black", "size": "S"}
    assert mapped["variants"][1]["option_values"] == {"color": "Black", "size": "M"}
    assert "soft_fabric" not in mapped["variants"][0]["option_values"]
    assert "high_waisted" not in mapped["variants"][0]["option_values"]

@pytest.mark.unit
def test_map_js_state_to_fields_reads_nested_variant_price_objects() -> None:
    mapped = map_js_state_to_fields(
        {
            "__NEXT_DATA__": {
                "props": {
                    "pageProps": {
                        "product": {
                            "id": "runner-1",
                            "title": "Tree Runner",
                            "vendor": "Allbirds",
                            "price": {"amount": "100.00", "currencyCode": "USD"},
                            "options": [
                                {"name": "Color"},
                                {"name": "Size"},
                            ],
                            "variants": [
                                {
                                    "id": "jet-black-8",
                                    "available": True,
                                    "price": {
                                        "amount": "100.00",
                                        "currencyCode": "USD",
                                    },
                                    "selectedOptions": [
                                        {"name": "Color", "value": "Jet Black"},
                                        {"name": "Size", "value": "8"},
                                    ],
                                },
                                {
                                    "id": "jet-black-9",
                                    "available": True,
                                    "priceV2": {
                                        "amount": "100.00",
                                        "currencyCode": "USD",
                                    },
                                    "selectedOptions": [
                                        {"name": "Color", "value": "Jet Black"},
                                        {"name": "Size", "value": "9"},
                                    ],
                                },
                            ],
                        }
                    }
                }
            }
        },
        surface="ecommerce_detail",
        page_url="https://store.example.com/products/tree-runner?variant=jet-black-8",
    )

    assert mapped["price"] == "100.00"
    assert mapped["variants"][0]["price"] == "100.00"
    assert mapped["variants"][1]["price"] == "100.00"

@pytest.mark.unit
def test_map_js_state_to_fields_recovers_nested_choice_item_variants() -> None:
    mapped = map_js_state_to_fields(
        {
            "__INITIAL_CONFIG__": {
                "productDisplay": {
                    "entities": {
                        "7507996": {
                            "legacyStyleGroupId": "10014429",
                            "webPathAlias": "nike-air-force-1-07-basketball-sneaker-men",
                            "copyProductTitle": "Air Force 1 '07 Basketball Sneaker",
                            "copyDescription": "Basketball sneaker with heritage details.",
                            "labelDisplayName": "Nike",
                            "coreProducts": [
                                {
                                    "nptHierarchy": "npt.shoes.sneakers",
                                    "coreChoices": [
                                        {
                                            "coreChoiceId": "4444444TRN",
                                            "displayColorDescription": "WHITE/ BLACK",
                                            "orderedShots": [
                                                {
                                                    "imageUrl": (
                                                        "https://n.nordstrommedia.com/it/"
                                                        "shoe.jpeg"
                                                    )
                                                }
                                            ],
                                            "items": [
                                                {
                                                    "npin": "22222Q92NG",
                                                    "concatenatedDisplaySize": "7.5 M",
                                                    "sku": {
                                                        "skuId": "A7293017",
                                                        "propositions": [
                                                            {
                                                                "salability": {
                                                                    "status": "SELLABLE"
                                                                },
                                                                "availability": {
                                                                    "isAvailable": True,
                                                                    "shipQuantity": 1,
                                                                },
                                                                "pricings": [
                                                                    {
                                                                        "sellingRetail": {
                                                                            "price": "69.00"
                                                                        },
                                                                        "baseRetail": {
                                                                            "price": "115.00"
                                                                        },
                                                                    }
                                                                ],
                                                            }
                                                        ],
                                                    },
                                                },
                                                {
                                                    "npin": "22222X2S9M",
                                                    "sizeDimension1": {"label": "8"},
                                                    "sizeDimension2": {"label": "M"},
                                                    "sku": {
                                                        "skuId": "A7293024",
                                                        "propositions": [
                                                            {
                                                                "salability": {
                                                                    "status": "SOLD_OUT"
                                                                },
                                                                "availability": {
                                                                    "isAvailable": False,
                                                                    "shipQuantity": 0,
                                                                },
                                                                "pricings": [
                                                                    {
                                                                        "sellingRetail": {
                                                                            "price": "69.00"
                                                                        }
                                                                    }
                                                                ],
                                                            }
                                                        ],
                                                    },
                                                },
                                            ],
                                        }
                                    ],
                                }
                            ],
                        }
                    }
                }
            }
        },
        surface="ecommerce_detail",
        page_url="https://www.nordstrom.com/s/nike-air-force-1-07-basketball-sneaker-men/7507996",
    )

    assert mapped["title"] == "Air Force 1 '07 Basketball Sneaker"
    assert mapped["brand"] == "Nike"
    assert mapped["variant_count"] == 2
    assert mapped["variants"][0]["sku"] == "A7293017"
    assert mapped["variants"][0]["size"] == "7.5 M"
    assert mapped["variants"][0]["color"] == "WHITE/ BLACK"
    assert mapped["variants"][0]["price"] == "69.00"
    assert mapped["variants"][0]["original_price"] == "115.00"
    assert mapped["variants"][0]["availability"] == "in_stock"
    assert mapped["variants"][1]["size"] == "8"
    assert mapped["variants"][1]["sku"] == "A7293024"
    assert mapped["variants"][1]["price"] == "69.00"
    assert mapped["variants"][1]["color"] == "WHITE/ BLACK"
    assert mapped["variants"][1]["availability"] == "out_of_stock"

@pytest.mark.unit
def test_map_js_state_to_fields_reads_nested_variant_original_price_objects() -> None:
    mapped = map_js_state_to_fields(
        {
            "__NEXT_DATA__": {
                "props": {
                    "pageProps": {
                        "product": {
                            "id": "runner-1",
                            "title": "Tree Runner",
                            "options": [{"name": "Size"}],
                            "variants": [
                                {
                                    "id": "runner-8",
                                    "compare_at_price": {
                                        "amount": "120.00",
                                        "currencyCode": "USD",
                                    },
                                    "selectedOptions": [{"name": "Size", "value": "8"}],
                                },
                                {
                                    "id": "runner-9",
                                    "compareAtPrice": {
                                        "amount": "130.00",
                                        "currencyCode": "USD",
                                    },
                                    "selectedOptions": [{"name": "Size", "value": "9"}],
                                },
                            ],
                        }
                    }
                }
            }
        },
        surface="ecommerce_detail",
        page_url="https://store.example.com/products/tree-runner?variant=runner-9",
    )

    assert mapped["original_price"] == "130.00"
    assert [row["original_price"] for row in mapped["variants"]] == ["120.00", "130.00"]

@pytest.mark.unit
def test_map_js_state_to_fields_reads_current_price_style_product_fields() -> None:
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
                                    "selectedOptions": [{"name": "Size", "value": "6"}],
                                },
                                {
                                    "id": "size-7",
                                    "available": False,
                                    "selectedOptions": [{"name": "Size", "value": "7"}],
                                },
                            ],
                        }
                    }
                }
            }
        },
        surface="ecommerce_detail",
        page_url="https://store.example.com/products/air-force-1?variant=size-6",
    )

    assert mapped["price"] == "USD 115"
    assert mapped["original_price"] == "USD 130"
    assert mapped["currency"] == "USD"

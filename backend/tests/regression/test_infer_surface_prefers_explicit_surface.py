from __future__ import annotations

from .test_harness_support import Path, build_explicit_sites, classify_failure_mode, evaluate_quality, harness_support, infer_surface, load_site_set, parse_test_sites_markdown, pytest, run_test_sites_acceptance  # fmt: skip

@pytest.mark.regression
def test_infer_surface_prefers_explicit_surface() -> None:
    assert (
        infer_surface("https://example.com/collections", explicit_surface="job_listing")
        == "job_listing"
    )

@pytest.mark.regression
def test_infer_surface_classifies_job_and_commerce_urls() -> None:
    assert infer_surface("https://example.com/careers") == "job_listing"
    assert infer_surface("https://example.com/products/widget-1") == "ecommerce_detail"
    assert (
        infer_surface(
            "https://secure7.saashr.com/ta/6208610.careers?ein_id=1&career_portal_id=2&ShowJob=587687242"
        )
        == "job_detail"
    )

@pytest.mark.regression
def test_infer_surface_handles_acceptance_critical_hosts() -> None:
    assert (
        infer_surface("https://www.usajobs.gov/search/results/?k=software+engineer&p=1")
        == "job_listing"
    )
    assert (
        infer_surface("https://www.indeed.com/search?q=data+engineer") == "job_listing"
    )
    assert infer_surface("https://startup.jobs/") == "job_listing"
    assert (
        infer_surface(
            "https://www.autozone.com/motor-oil-and-transmission-fluid/motor-oil/mobil-1/mobil-1-extended-performance-full-synthetic-motor-oil-5w-30-5-quart/881036_0_0"
        )
        == "ecommerce_detail"
    )
    assert (
        infer_surface(
            "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html"
        )
        == "ecommerce_detail"
    )
    assert (
        infer_surface("https://www.vitacost.com/vitacost-vitamin-d3-mini-gels")
        == "ecommerce_detail"
    )
    assert (
        infer_surface("https://www.rockler.com/rockler-table-saw-crosscut-sled")
        == "ecommerce_detail"
    )

@pytest.mark.regression
def test_parse_test_sites_markdown_reads_urls_from_tail(tmp_path: Path) -> None:
    path = tmp_path / "TEST_SITES.md"
    path.write_text(
        "ignore\nhttps://example.com/careers\nnot a url\nhttps://shop.example.com/collections\n",
        encoding="utf-8",
    )
    rows = parse_test_sites_markdown(path, start_line=2)

    assert rows == [
        {
            "name": "https://example.com/careers",
            "url": "https://example.com/careers",
            "surface": "job_listing",
        },
        {
            "name": "https://shop.example.com/collections",
            "url": "https://shop.example.com/collections",
            "surface": "ecommerce_listing",
        },
    ]

@pytest.mark.regression
def test_parse_test_sites_markdown_reads_urls_from_markdown_tables(
    tmp_path: Path,
) -> None:
    fixture = tmp_path / "TEST_SITES.md"
    fixture.write_text(
        "\n".join(
            [
                "| Name | URL | Type |",
                "| --- | --- | --- |",
                "| Listing | https://web-scraping.dev/products | Listing |",
                "| Detail | https://web-scraping.dev/product/1 | Detail |",
                "| Tool | https://practicesoftwaretesting.com/product/01HB | Detail |",
            ]
        ),
        encoding="utf-8",
    )

    rows = parse_test_sites_markdown(fixture, start_line=1)

    assert any(
        row["url"] == "https://web-scraping.dev/products"
        and row["surface"] == "ecommerce_listing"
        for row in rows
    )
    assert any(
        row["url"] == "https://web-scraping.dev/product/1"
        and row["surface"] == "ecommerce_detail"
        for row in rows
    )
    assert any(
        row["url"] == "https://practicesoftwaretesting.com/product/01HB"
        and row["surface"] == "ecommerce_detail"
        for row in rows
    )

@pytest.mark.regression
def test_build_explicit_sites_preserves_explicit_surface_order() -> None:
    rows = build_explicit_sites(
        [
            "https://example.com/search?q=widgets",
            "https://example.com/products/widget-prime",
        ],
        explicit_surfaces=["ecommerce_listing", "ecommerce_detail"],
    )

    assert rows == [
        {
            "name": "https://example.com/search?q=widgets",
            "url": "https://example.com/search?q=widgets",
            "surface": "ecommerce_listing",
        },
        {
            "name": "https://example.com/products/widget-prime",
            "url": "https://example.com/products/widget-prime",
            "surface": "ecommerce_detail",
        },
    ]

@pytest.mark.regression
def test_build_explicit_sites_rejects_mismatched_surface_count() -> None:
    with pytest.raises(ValueError, match="surface counts must match"):
        build_explicit_sites(
            ["https://example.com/products/widget-prime"],
            explicit_surfaces=["ecommerce_detail", "ecommerce_listing"],
        )

@pytest.mark.regression
def test_load_site_set_preserves_curated_surface_and_bucket(tmp_path: Path) -> None:
    manifest = tmp_path / "sites.json"
    manifest.write_text(
        """
        {
          "site_sets": {
            "commerce": {
              "sites": [
                {
                  "name": "Catalog",
                  "url": "https://example.com/search?q=widgets",
                  "surface": "ecommerce_listing",
                  "bucket": "must_pass",
                  "expected_failure_modes": ["success"],
                  "artifact_run_id": 77,
                  "seed_failure_mode": "listing_chrome_noise",
                  "quality_expectations": {"require_price": true}
                }
              ]
            }
          }
        }
        """,
        encoding="utf-8",
    )

    rows = load_site_set(manifest, site_set_name="commerce")

    assert rows == [
        {
            "name": "Catalog",
            "url": "https://example.com/search?q=widgets",
            "surface": "ecommerce_listing",
            "bucket": "must_pass",
            "expected_failure_modes": ["success"],
            "artifact_run_id": 77,
            "seed_failure_mode": "listing_chrome_noise",
            "quality_expectations": {"require_price": True},
        }
    ]

@pytest.mark.regression
def test_load_site_set_reports_json_path_on_decode_error(tmp_path: Path) -> None:
    manifest = tmp_path / "bad-sites.json"
    manifest.write_text("{ invalid json", encoding="utf-8")

    with pytest.raises(ValueError, match="bad-sites.json"):
        load_site_set(manifest, site_set_name="commerce")

@pytest.mark.regression
def test_load_site_set_merges_defaults(tmp_path: Path) -> None:
    manifest = tmp_path / "sites.json"
    manifest.write_text(
        """
        {
          "name": "commerce",
          "defaults": {
            "surface": "ecommerce_detail",
            "bucket": "commerce_extended",
            "gate": "soft",
            "quality_expectations": {"require_identity": true, "require_price": true}
          },
          "sites": [
            {
              "name": "Product",
              "url": "https://example.com/products/widget",
              "quality_expectations": {"require_price": false}
            }
          ]
        }
        """,
        encoding="utf-8",
    )

    rows = load_site_set(manifest, site_set_name="commerce")

    assert rows == [
        {
            "name": "Product",
            "url": "https://example.com/products/widget",
            "surface": "ecommerce_detail",
            "bucket": "commerce_extended",
            "expected_failure_modes": [],
            "artifact_run_id": None,
            "seed_failure_mode": None,
            "quality_expectations": {
                "require_identity": True,
                "require_price": False,
            },
            "gate": "soft",
        }
    ]

@pytest.mark.regression
def test_classify_failure_mode_flags_missing_adapter_registration() -> None:
    result = {
        "ok": False,
        "platform_family": "ultipro_ukg",
        "surface": "job_listing",
        "adapter_name": None,
        "adapter_records": 0,
        "records": 0,
    }

    assert classify_failure_mode(result) == "adapter_not_matched"

@pytest.mark.regression
def test_classify_failure_mode_treats_browser_challenge_diagnostics_as_blocked() -> (
    None
):
    result = {
        "ok": False,
        "blocked": False,
        "browser_diagnostics": {
            "browser_outcome": "usable_content",
            "challenge_evidence": [
                "strong:captcha",
                "provider:cloudflare",
            ],
            "challenge_provider_hits": ["cloudflare"],
        },
        "surface": "ecommerce_listing",
        "records": 0,
        "adapter_records": 0,
    }

    assert classify_failure_mode(result) == "blocked"

@pytest.mark.regression
def test_challenge_summary_extracts_provider_and_evidence() -> None:
    diagnostics = {
        "browser_outcome": "challenge_page",
        "challenge_provider_hits": ["DataDome"],
        "challenge_element_hits": ["captcha-form"],
        "challenge_evidence": [
            "http_status:429",
            "title:Verifying your connection...",
            "provider:datadome",
        ],
    }

    assert harness_support._challenge_summary_from_diagnostics(diagnostics) == {
        "browser_outcome": "challenge_page",
        "provider": "datadome",
        "providers": ["datadome"],
        "elements": ["captcha-form"],
        "evidence": [
            "http_status:429",
            "title:Verifying your connection...",
            "provider:datadome",
        ],
    }

@pytest.mark.regression
def test_classify_failure_mode_rejects_placeholder_success_titles() -> None:
    result = {
        "verdict": "success",
        "records": 1,
        "sample_title": "Page Not Found",
        "populated_fields": 1,
        "surface": "ecommerce_listing",
    }

    assert classify_failure_mode(result) == "wrong_content_or_placeholder"

@pytest.mark.regression
def test_classify_failure_mode_rejects_oops_not_found_titles() -> None:
    result = {
        "verdict": "success",
        "records": 1,
        "sample_title": "Oops! The page you're looking for can't be found.",
        "populated_fields": 4,
        "surface": "ecommerce_detail",
    }

    assert classify_failure_mode(result) == "wrong_content_or_placeholder"

@pytest.mark.regression
def test_classify_failure_mode_reports_utility_chrome_as_success_reporting_only() -> (
    None
):
    result = {
        "verdict": "success",
        "records": 1,
        "sample_title": "Product Help",
        "sample_url": "https://example.com/help/product-help",
        "populated_fields": 3,
        "surface": "ecommerce_listing",
    }

    assert classify_failure_mode(result) == "success"

@pytest.mark.regression
def test_classify_failure_mode_rejects_detail_identity_mismatches() -> None:
    result = {
        "verdict": "success",
        "records": 1,
        "surface": "ecommerce_detail",
        "requested_url": "https://www.practicesoftwaretesting.com/product/practice-software-testing",
        "sample_title": "Practice Software Testing - Toolshop - v5.0",
        "sample_url": "https://www.practicesoftwaretesting.com/",
        "populated_fields": 4,
    }

    assert classify_failure_mode(result) == "detail_identity_mismatch"

@pytest.mark.regression
def test_classify_failure_mode_rejects_fragment_backed_detail_identity_mismatches() -> (
    None
):
    result = {
        "verdict": "success",
        "records": 1,
        "surface": "ecommerce_detail",
        "requested_url": "https://www.practicesoftwaretesting.com/#/product/01HB",
        "sample_title": "Practice Software Testing",
        "sample_url": "https://www.practicesoftwaretesting.com/",
        "populated_fields": 4,
    }

    assert classify_failure_mode(result) == "detail_identity_mismatch"

@pytest.mark.regression
def test_classify_failure_mode_rejects_same_site_wrong_product_slug() -> None:
    result = {
        "verdict": "success",
        "records": 1,
        "surface": "ecommerce_detail",
        "requested_url": "https://www.thriftbooks.com/w/the-pragmatic-programmer_david-thomas_andrew-hunt/286697/",
        "sample_title": "The Biggest Loser Fitness Program",
        "sample_url": "https://www.thriftbooks.com/w/the-biggest-loser-fitness-program_maggie-greenwood-robinson/286697/",
        "populated_fields": 9,
    }

    assert classify_failure_mode(result) == "detail_identity_mismatch"

@pytest.mark.regression
def test_classify_failure_mode_does_not_infer_detail_identity_mismatch_without_requested_url() -> (
    None
):
    result = {
        "verdict": "success",
        "records": 1,
        "surface": "ecommerce_detail",
        "sample_title": "Widget Prime",
        "sample_url": "https://example.com/",
        "populated_fields": 4,
    }

    assert classify_failure_mode(result) == "success"

@pytest.mark.regression
def test_acceptance_runner_requires_unbucketed_runs_to_succeed() -> None:
    site = {
        "name": "Catalog",
        "url": "https://example.com/catalog",
        "surface": "ecommerce_listing",
    }
    result = {
        "failure_mode": "listing_extraction_empty",
    }

    assert run_test_sites_acceptance._expectation_met(site, result) is False

@pytest.mark.regression
def test_evaluate_quality_flags_shell_false_success() -> None:
    site = {
        "url": "https://www.uniqlo.com/in/en/products/E474244-000/01",
        "surface": "ecommerce_detail",
        "quality_expectations": {
            "require_identity": True,
            "require_price": True,
            "expect_variants": True,
            "require_semantic_variant_labels": True,
            "require_variant_price": True,
        },
    }
    result = {
        "surface": "ecommerce_detail",
        "requested_url": "https://www.uniqlo.com/in/en/products/E474244-000/01",
        "sample_title": "UNIQLO - LifeWear",
        "sample_url": "https://www.uniqlo.com/in/en/products/E474244-000/01",
        "populated_fields": 6,
        "sample_semantics": {
            "price_present": False,
            "variant_count": 0,
            "variants_with_axes_count": 0,
            "variants_all_have_axes": False,
            "variants_with_price_count": 0,
            "legacy_variant_keys_present": False,
        },
        "failure_mode": "success",
        "sample_records": [],
    }

    quality = evaluate_quality(site, result)

    assert quality["quality_verdict"] == "bad_output"
    assert quality["observed_failure_mode"] == "shell_false_success"
    assert quality["quality_checks"]["identity_ok"] is False

@pytest.mark.regression
def test_evaluate_quality_flags_axis_pollution_as_gap() -> None:
    site = {
        "url": "https://www.gymshark.com/products/example",
        "surface": "ecommerce_detail",
        "quality_expectations": {
            "require_identity": True,
            "require_price": True,
            "expect_variants": True,
            "require_semantic_variant_labels": True,
            "require_variant_price": True,
        },
    }
    result = {
        "surface": "ecommerce_detail",
        "requested_url": "https://www.gymshark.com/products/example",
        "sample_title": "Everyday Seamless Leggings",
        "sample_url": "https://www.gymshark.com/products/example",
        "populated_fields": 20,
        "sample_semantics": {
            "price_present": True,
            "variant_count": 7,
            "variants_with_axes_count": 0,
            "variants_all_have_axes": False,
            "variants_with_price_count": 7,
            "legacy_variant_keys_present": False,
        },
        "failure_mode": "success",
        "sample_records": [],
    }

    quality = evaluate_quality(site, result)

    assert quality["quality_verdict"] == "usable_with_gaps"
    assert quality["observed_failure_mode"] == "axis_pollution"
    assert quality["quality_checks"]["identity_ok"] is True
    assert quality["quality_checks"]["variant_labels_ok"] is False

@pytest.mark.regression
def test_evaluate_quality_flags_audit_price_magnitude_anomaly() -> None:
    site = {
        "surface": "ecommerce_detail",
        "quality_expectations": {
            "require_identity": True,
            "require_price": True,
            "require_price_sane": True,
        },
    }
    result = {
        "surface": "ecommerce_detail",
        "requested_url": "https://example.com/products/food-processor",
        "sample_title": "KitchenAid Food Processor",
        "sample_url": "https://example.com/products/food-processor",
        "populated_fields": 8,
        "sample_record_data": {
            "title": "KitchenAid Food Processor",
            "url": "https://example.com/products/food-processor",
            "price": "22999.00",
            "currency": "USD",
        },
        "sample_semantics": {"price_present": True},
        "failure_mode": "success",
    }

    quality = evaluate_quality(site, result)

    assert quality["quality_verdict"] == "bad_output"
    assert quality["observed_failure_mode"] == "price_magnitude_anomaly"
    assert quality["quality_checks"]["price_sane_ok"] is False

@pytest.mark.regression
def test_evaluate_quality_flags_audit_category_pollution() -> None:
    site = {
        "surface": "ecommerce_detail",
        "quality_expectations": {"require_clean_category": True},
    }
    result = {
        "surface": "ecommerce_detail",
        "requested_url": "https://example.com/products/shoe",
        "sample_title": "Stan Smith Shoes",
        "sample_url": "https://example.com/products/shoe",
        "populated_fields": 8,
        "sample_record_data": {
            "title": "Stan Smith Shoes",
            "url": "https://example.com/products/shoe",
            "category": "Back > Home > Men > Shoes",
            "price": "99.99",
        },
        "sample_semantics": {"price_present": True},
        "failure_mode": "success",
    }

    quality = evaluate_quality(site, result)

    assert quality["quality_verdict"] == "bad_output"
    assert quality["observed_failure_mode"] == "category_pollution"
    assert quality["quality_checks"]["category_clean_ok"] is False

@pytest.mark.regression
def test_evaluate_quality_flags_audit_long_text_pollution() -> None:
    site = {
        "surface": "ecommerce_detail",
        "quality_expectations": {"require_clean_long_text": True},
    }
    result = {
        "surface": "ecommerce_detail",
        "requested_url": "https://example.com/products/duvet",
        "sample_title": "Cotton Duvet",
        "sample_url": "https://example.com/products/duvet",
        "populated_fields": 8,
        "sample_record_data": {
            "title": "Cotton Duvet",
            "url": "https://example.com/products/duvet",
            "description": "Choose from Same Day Delivery, Drive Up or Order Pickup",
            "price": "49.99",
        },
        "sample_semantics": {"price_present": True},
        "failure_mode": "success",
    }

    quality = evaluate_quality(site, result)

    assert quality["quality_verdict"] == "bad_output"
    assert quality["observed_failure_mode"] == "long_text_pollution"
    assert quality["quality_checks"]["long_text_clean_ok"] is False

@pytest.mark.regression
def test_evaluate_quality_flags_audit_variant_and_system_artifacts() -> None:
    site = {
        "surface": "ecommerce_detail",
        "quality_expectations": {
            "require_clean_variants": True,
            "require_clean_system_fields": True,
        },
    }
    result = {
        "surface": "ecommerce_detail",
        "requested_url": "https://example.com/products/jacket",
        "sample_title": "Leather Jacket",
        "sample_url": "https://example.com/products/jacket",
        "populated_fields": 10,
        "sample_record_data": {
            "title": "Leather Jacket",
            "url": "https://example.com/products/jacket",
            "price": "1500.00",
            "sku": "COPY-1720644688978",
            "product_type": "inline",
            "variant_axes": {"discount": ["20%"]},
            "variants": [{"option_values": {"discount": "20%"}}],
        },
        "sample_semantics": {
            "price_present": True,
            "variant_count": 1,
            "variants_with_axes_count": 0,
            "variants_all_have_axes": False,
            "variants_with_price_count": 1,
            "legacy_variant_keys_present": True,
        },
        "failure_mode": "success",
    }

    quality = evaluate_quality(site, result)

    assert quality["quality_verdict"] == "bad_output"
    assert quality["observed_failure_mode"] == "variant_artifact_pollution"
    assert quality["quality_checks"]["variant_artifacts_ok"] is False
    assert quality["quality_checks"]["system_artifacts_ok"] is False

@pytest.mark.regression
def test_evaluate_quality_flags_cross_cutting_detail_invariants() -> None:
    site = {
        "surface": "ecommerce_detail",
        "quality_expectations": {
            "require_clean_category": True,
            "require_clean_long_text": True,
            "require_clean_variants": True,
            "require_variant_currency_parity": True,
            "require_identifier_shapes": True,
            "require_title_not_internal_token": True,
        },
    }
    result = {
        "surface": "ecommerce_detail",
        "requested_url": "https://example.com/products/widget",
        "sample_title": "specifications",
        "sample_url": "https://example.com/products/widget",
        "populated_fields": 10,
        "sample_record_data": {
            "title": "specifications",
            "url": "https://example.com/products/widget",
            "category": "Shop by Shoes > Best Sellers > specifications",
            "description": "Shipping and Returns Orders may take up to 48 business hours.",
            "barcode": "ABC123",
            "gender": "default",
            "currency": "USD",
            "variants": [{"size": "M", "price": "19.99", "currency": "EUR"}],
        },
        "sample_semantics": {"price_present": True, "variant_count": 1},
        "failure_mode": "success",
    }

    quality = evaluate_quality(site, result)

    assert quality["quality_verdict"] == "bad_output"
    assert quality["quality_checks"]["category_clean_ok"] is False
    assert quality["quality_checks"]["long_text_clean_ok"] is False
    assert quality["quality_checks"]["variant_currency_parity_ok"] is False
    assert quality["quality_checks"]["variant_artifacts_ok"] is True
    assert quality["quality_checks"]["identifier_shapes_ok"] is False
    assert quality["quality_checks"]["title_token_ok"] is False
    assert quality["observed_failure_mode"] == "category_pollution"

@pytest.mark.regression
def test_evaluate_quality_flags_missing_repair_diagnostics() -> None:
    site = {
        "surface": "ecommerce_detail",
        "quality_expectations": {"require_repair_diagnostics": True},
    }
    result = {
        "surface": "ecommerce_detail",
        "requested_url": "https://example.com/products/widget",
        "sample_title": "Widget",
        "sample_record_data": {"title": "Widget"},
        "sample_source_trace": {"extraction": {}},
        "sample_semantics": {"price_present": False},
        "failure_mode": "success",
    }

    quality = evaluate_quality(site, result)

    assert quality["quality_verdict"] == "bad_output"
    assert quality["observed_failure_mode"] == "repair_diagnostic_missing"
    assert quality["quality_checks"]["repair_diagnostics_ok"] is False

@pytest.mark.regression
def test_evaluate_quality_accepts_visible_repair_diagnostics() -> None:
    site = {
        "surface": "ecommerce_detail",
        "quality_expectations": {"require_repair_diagnostics": True},
    }
    result = {
        "surface": "ecommerce_detail",
        "requested_url": "https://example.com/products/widget",
        "sample_title": "Widget",
        "sample_record_data": {"title": "Widget"},
        "sample_source_trace": {
            "extraction": {
                "field_repair": {
                    "action": "skipped",
                    "reason": "llm_disabled",
                }
            }
        },
        "sample_semantics": {"price_present": False},
        "failure_mode": "success",
    }

    quality = evaluate_quality(site, result)

    assert quality["quality_checks"]["repair_diagnostics_ok"] is True

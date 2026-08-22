from __future__ import annotations

from .test_crawl_service import AsyncSession, CrawlerConfigurationError, ProgrammingError, ReviewPromotion, apply_acquisition_contract_to_profile, build_success_acquisition_contract, create_crawl_run, dependencies_module, load_domain_run_profile, normalize_acquisition_contract, normalize_crawl_settings, normalize_domain_run_profile, note_acquisition_contract_failure, pytest, record_acquisition_contract_outcome, resolve_url_acquisition_recipe, save_domain_run_profile, settings  # fmt: skip

@pytest.mark.component
def test_get_run_dispatcher_reuses_dispatch_mode_singletons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dependencies_module._run_dispatchers.clear()
    try:
        monkeypatch.setattr(settings, "celery_dispatch_enabled", False)
        local_dispatcher = dependencies_module.get_run_dispatcher()

        assert dependencies_module.get_run_dispatcher() is local_dispatcher

        monkeypatch.setattr(settings, "celery_dispatch_enabled", True)
        celery_dispatcher = dependencies_module.get_run_dispatcher()

        assert dependencies_module.get_run_dispatcher() is celery_dispatcher
        assert celery_dispatcher is not local_dispatcher
    finally:
        dependencies_module._run_dispatchers.clear()

@pytest.mark.asyncio
@pytest.mark.component
async def test_create_crawl_run_sets_pending_and_preserves_surface(
    db_session: AsyncSession,
    test_user,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/product/widget",
            "surface": "ecommerce_detail",
        },
    )

    assert run.id is not None
    assert run.status == "pending"
    assert run.surface == "ecommerce_detail"
    assert run.result_summary["url_count"] == 1

@pytest.mark.asyncio
@pytest.mark.component
async def test_create_crawl_run_preserves_raw_additional_fields_and_keeps_domain_fields(
    db_session: AsyncSession,
    test_user,
) -> None:
    seed_run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/product/seed",
            "surface": "ecommerce_detail",
        },
    )
    db_session.add(
        ReviewPromotion(
            run_id=seed_run.id,
            domain="example.com",
            surface="ecommerce_detail",
            approved_schema={"fields": ["title", "materials"]},
            field_mapping={"material_notes": "materials"},
        )
    )
    await db_session.commit()

    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/product/widget",
            "surface": "ecommerce_detail",
            "additional_fields": ["care instructions"],
        },
    )

    assert "materials" in run.requested_fields
    assert "care instructions" in run.requested_fields
    assert "care" not in run.requested_fields
    assert run.settings["requested_fields"] == run.requested_fields

@pytest.mark.asyncio
@pytest.mark.component
async def test_create_crawl_run_preserves_exact_custom_additional_field_labels(
    db_session: AsyncSession,
    test_user,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/product/widget",
            "surface": "ecommerce_detail",
            "additional_fields": ["Features & Benefits", "Product Story"],
        },
    )

    assert run.requested_fields == ["Features & Benefits", "Product Story"]
    assert run.settings["requested_fields"] == ["Features & Benefits", "Product Story"]

@pytest.mark.asyncio
@pytest.mark.component
async def test_create_crawl_run_merges_saved_domain_run_profile_for_single_url(
    db_session: AsyncSession,
    test_user,
) -> None:
    await save_domain_run_profile(
        db_session,
        domain="example.com",
        surface="ecommerce_detail",
        profile={
            "fetch_profile": {
                "fetch_mode": "http_then_browser",
                "extraction_source": "rendered_dom",
                "js_mode": "enabled",
                "include_iframes": False,
                "traversal_mode": "paginate",
                "request_delay_ms": 1200,
                "max_pages": 8,
                "max_scrolls": 12,
            },
            "locality_profile": {
                "geo_country": "IN",
                "language_hint": "en-IN",
                "currency_hint": "INR",
            },
            "diagnostics_profile": {
                "capture_html": True,
                "capture_screenshot": False,
                "capture_network": "matched_only",
                "capture_response_headers": True,
                "capture_browser_diagnostics": True,
            },
            "acquisition_contract": {
                "preferred_browser_engine": "real_chrome",
                "prefer_browser": True,
                "handoff_eligible": True,
                "handoff_cookie_engine": "real_chrome",
            },
            "proxy_profile": {
                "enabled": True,
                "proxy_list": ["http://proxy-a", "http://proxy-b"],
            },
        },
        source_run_id=91,
    )
    await db_session.commit()

    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/product/widget",
            "surface": "ecommerce_detail",
            "settings": {
                "fetch_profile": {
                    "request_delay_ms": 900,
                }
            },
        },
    )

    assert run.settings["fetch_profile"]["fetch_mode"] == "http_then_browser"
    assert run.settings["fetch_profile"]["traversal_mode"] == "paginate"
    assert run.settings["fetch_profile"]["request_delay_ms"] == 900
    assert run.settings["locality_profile"]["geo_country"] == "IN"
    assert run.settings["diagnostics_profile"]["capture_network"] == "matched_only"
    assert run.settings["acquisition_contract"]["preferred_browser_engine"] == "auto"
    assert run.settings["acquisition_contract"]["handoff_eligible"] is False
    assert run.settings["proxy_enabled"] is False
    assert run.settings["proxy_list"] == []
    assert run.settings["proxy_profile"] == {
        "enabled": False,
        "proxy_list": [],
    }

@pytest.mark.asyncio
@pytest.mark.component
async def test_explicit_forced_engine_overrides_saved_contract(
    db_session: AsyncSession,
    test_user,
) -> None:
    await save_domain_run_profile(
        db_session,
        domain="example.com",
        surface="ecommerce_detail",
        profile={
            "acquisition_contract": {
                "preferred_browser_engine": "real_chrome",
                "prefer_browser": True,
                "handoff_eligible": True,
                "handoff_cookie_engine": "real_chrome",
            },
        },
        source_run_id=91,
    )
    await db_session.commit()

    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/product/widget",
            "surface": "ecommerce_detail",
            "settings": {
                "acquisition_contract": {
                    "preferred_browser_engine": "patchright",
                    "prefer_browser": True,
                    "handoff_eligible": False,
                    "handoff_cookie_engine": "patchright",
                },
            },
        },
    )

    contract = run.settings["acquisition_contract"]
    assert contract["preferred_browser_engine"] == "patchright"
    assert contract["handoff_eligible"] is False
    assert contract["handoff_cookie_engine"] == "patchright"

@pytest.mark.asyncio
@pytest.mark.component
async def test_browser_only_run_disables_saved_handoff_contract(
    db_session: AsyncSession,
    test_user,
) -> None:
    await save_domain_run_profile(
        db_session,
        domain="example.com",
        surface="ecommerce_detail",
        profile={
            "fetch_profile": {"fetch_mode": "http_then_browser"},
            "acquisition_contract": {
                "preferred_browser_engine": "real_chrome",
                "prefer_browser": True,
                "handoff_eligible": True,
                "handoff_cookie_engine": "real_chrome",
            },
        },
        source_run_id=91,
    )
    await db_session.commit()

    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://example.com/product/widget",
            "surface": "ecommerce_detail",
            "settings": {
                "advanced_enabled": True,
                "fetch_profile": {"fetch_mode": "browser_only"},
            },
        },
    )

    contract = run.settings["acquisition_contract"]
    assert run.settings["fetch_profile"]["fetch_mode"] == "browser_only"
    assert contract["prefer_browser"] is True
    assert contract["handoff_eligible"] is False
    assert contract["handoff_cookie_engine"] == "auto"

@pytest.mark.component
def test_browser_only_profile_application_drops_handoff() -> None:
    profile = apply_acquisition_contract_to_profile(
        {"fetch_mode": "browser_only"},
        {
            "preferred_browser_engine": "real_chrome",
            "prefer_browser": True,
            "handoff_eligible": True,
            "handoff_cookie_engine": "real_chrome",
        },
    )

    assert profile["prefer_browser"] is True
    assert profile["forced_browser_engine"] == "real_chrome"
    assert "prefer_curl_handoff" not in profile
    assert "handoff_cookie_engine" not in profile

@pytest.mark.component
def test_normalize_acquisition_contract_accepts_legacy_handoff_flag() -> None:
    contract = normalize_acquisition_contract({"prefer_curl_handoff": True})

    assert contract["handoff_eligible"] is True

@pytest.mark.component
def test_build_success_acquisition_contract_tolerates_bad_payload_count() -> None:
    contract = build_success_acquisition_contract(
        method="browser",
        browser_engine="patchright",
        browser_diagnostics={"network_payload_count": "not-a-number"},
        record_count=1,
        requested_fields=["title"],
        found_fields=["title"],
        source_run_id=10,
    )

    assert contract["required_network_payloads"] is False
    assert contract["handoff_eligible"] is True

@pytest.mark.asyncio
@pytest.mark.component
async def test_create_crawl_run_rejects_invalid_traversal_mode(
    db_session: AsyncSession,
    test_user,
) -> None:
    with pytest.raises(
        CrawlerConfigurationError,
        match="Unsupported traversal_mode",
    ):
        await create_crawl_run(
            db_session,
            test_user.id,
            {
                "run_type": "crawl",
                "url": "https://example.com/collections/widgets",
                "surface": "ecommerce_listing",
                "settings": {
                    "advanced_enabled": True,
                    "fetch_profile": {
                        "traversal_mode": "unsupported_mode",
                    },
                },
            },
        )

@pytest.mark.asyncio
@pytest.mark.component
async def test_contract_marks_stale_after_repeated_quality_failures(
    db_session: AsyncSession,
) -> None:
    await save_domain_run_profile(
        db_session,
        domain="example.com",
        surface="ecommerce_detail",
        profile={
            "acquisition_contract": {
                "preferred_browser_engine": "real_chrome",
                "prefer_browser": True,
                "handoff_eligible": True,
                "handoff_cookie_engine": "real_chrome",
                "last_quality_success": {
                    "method": "browser",
                    "browser_engine": "real_chrome",
                    "record_count": 1,
                    "field_coverage": {
                        "requested": ["title"],
                        "found": ["title"],
                        "missing": [],
                    },
                    "source_run_id": 12,
                    "timestamp": "2026-04-30T00:00:00+00:00",
                },
            },
        },
        source_run_id=12,
    )
    await db_session.commit()

    first = await note_acquisition_contract_failure(
        db_session,
        domain="example.com",
        surface="ecommerce_detail",
        threshold=2,
    )
    second = await note_acquisition_contract_failure(
        db_session,
        domain="example.com",
        surface="ecommerce_detail",
        threshold=2,
    )

    assert first["acquisition_contract"]["stale_after_failures"] == {
        "failure_count": 1,
        "stale": False,
    }
    assert second["acquisition_contract"]["stale_after_failures"] == {
        "failure_count": 2,
        "stale": True,
    }

@pytest.mark.asyncio
@pytest.mark.component
async def test_contract_failure_tolerates_bad_source_run_id(
    db_session: AsyncSession,
) -> None:
    await save_domain_run_profile(
        db_session,
        domain="example.com",
        surface="ecommerce_detail",
        profile={
            "source_run_id": "bad-value",
            "acquisition_contract": {
                "last_quality_success": {"method": "browser"},
                "stale_after_failures": {"failure_count": 0, "stale": False},
            },
        },
        source_run_id=1,
    )

    updated = await note_acquisition_contract_failure(
        db_session,
        domain="example.com",
        surface="ecommerce_detail",
        threshold=1,
    )

    assert updated is not None
    assert updated["acquisition_contract"]["stale_after_failures"] == {
        "failure_count": 1,
        "stale": True,
    }

@pytest.mark.asyncio
@pytest.mark.component
async def test_contract_outcome_can_skip_non_acquisition_failures(
    db_session: AsyncSession,
) -> None:
    await save_domain_run_profile(
        db_session,
        domain="example.com",
        surface="ecommerce_detail",
        profile={
            "acquisition_contract": {
                "preferred_browser_engine": "real_chrome",
                "prefer_browser": True,
                "handoff_eligible": True,
                "handoff_cookie_engine": "real_chrome",
                "last_quality_success": {
                    "method": "browser",
                    "browser_engine": "real_chrome",
                    "record_count": 1,
                    "field_coverage": {
                        "requested": ["title"],
                        "found": ["title"],
                        "missing": [],
                    },
                    "source_run_id": 12,
                    "timestamp": "2026-04-30T00:00:00+00:00",
                },
            },
        },
        source_run_id=12,
    )
    await db_session.commit()

    await record_acquisition_contract_outcome(
        db_session,
        domain="example.com",
        surface="ecommerce_detail",
        source_run_id=13,
        method="browser",
        browser_engine="real_chrome",
        browser_diagnostics={},
        requested_fields=["title"],
        records=[],
        persisted_count=0,
        verdict="blocked",
        blocked=True,
    )

    row = await load_domain_run_profile(
        db_session,
        domain="example.com",
        surface="ecommerce_detail",
    )
    assert row is not None
    assert row.profile["acquisition_contract"]["stale_after_failures"] == {
        "failure_count": 0,
        "stale": False,
    }

@pytest.mark.asyncio
@pytest.mark.component
async def test_resolve_url_acquisition_recipe_reuses_saved_profile_for_batch_defaults(
    db_session: AsyncSession,
) -> None:
    await save_domain_run_profile(
        db_session,
        domain="example.com",
        surface="ecommerce_detail",
        profile={
            "fetch_profile": {
                "fetch_mode": "browser_only",
                "request_delay_ms": 1200,
            },
            "locality_profile": {
                "geo_country": "IN",
            },
            "diagnostics_profile": {
                "capture_network": "matched_only",
            },
            "acquisition_contract": {
                "preferred_browser_engine": "real_chrome",
                "prefer_browser": True,
                "handoff_eligible": True,
                "handoff_cookie_engine": "real_chrome",
            },
        },
        source_run_id=91,
    )
    await db_session.commit()

    resolved = await resolve_url_acquisition_recipe(
        db_session,
        url="https://example.com/products/widget",
        surface="ecommerce_detail",
        explicit_settings=normalize_crawl_settings({}),
    )

    assert resolved["fetch_profile"]["fetch_mode"] == "browser_only"
    assert resolved["fetch_profile"]["request_delay_ms"] == 1200
    assert resolved["locality_profile"]["geo_country"] == "IN"
    assert resolved["diagnostics_profile"]["capture_network"] == "matched_only"
    assert resolved["acquisition_contract"]["preferred_browser_engine"] == "real_chrome"
    assert resolved["acquisition_contract"]["handoff_eligible"] is True

@pytest.mark.asyncio
@pytest.mark.component
async def test_record_acquisition_contract_outcome_saves_internal_api_endpoint(
    db_session: AsyncSession,
) -> None:
    await record_acquisition_contract_outcome(
        db_session,
        domain="example.com",
        surface="ecommerce_detail",
        source_run_id=92,
        method="browser",
        browser_engine="patchright",
        browser_diagnostics={"network_payload_count": 1},
        requested_fields=["title", "price"],
        records=[
            {
                "title": "Replay Widget",
                "price": 19.99,
                "_field_sources": {
                    "title": ["network_payload"],
                    "price": ["network_payload"],
                },
            }
        ],
        persisted_count=1,
        verdict="success",
        blocked=False,
        page_url="https://example.com/products/replay-widget",
        network_payloads=[
            {
                "url": "https://example.com/api/products/replay-widget.json",
                "method": "GET",
                "status": 200,
                "content_type": "application/json",
                "endpoint_type": "product_api",
                "endpoint_family": "generic",
                "body": {
                    "product": {
                        "title": "Replay Widget",
                        "price": {"amount": "19.99"},
                        "sku": "RW-100",
                        "url": "https://example.com/products/replay-widget",
                    }
                },
            }
        ],
    )

    row = await load_domain_run_profile(
        db_session,
        domain="example.com",
        surface="ecommerce_detail",
    )

    assert row is not None
    assert row.profile["internal_api_endpoints"] == [
        {
            "url": "https://example.com/api/products/replay-widget.json",
            "method": "GET",
            "endpoint_type": "product_api",
            "endpoint_family": "generic",
            "source_run_id": 92,
        }
    ]

@pytest.mark.asyncio
@pytest.mark.component
async def test_record_acquisition_contract_outcome_counts_empty_detail_failure(
    db_session: AsyncSession,
) -> None:
    await save_domain_run_profile(
        db_session,
        domain="example.com",
        surface="ecommerce_detail",
        profile={
            "acquisition_contract": {
                "preferred_browser_engine": "real_chrome",
                "prefer_browser": True,
                "handoff_eligible": True,
                "handoff_cookie_engine": "real_chrome",
                "last_quality_success": {
                    "method": "browser",
                    "browser_engine": "real_chrome",
                    "record_count": 1,
                    "field_coverage": {
                        "requested": ["title"],
                        "found": ["title"],
                        "missing": [],
                    },
                    "source_run_id": 12,
                    "timestamp": "2026-04-30T00:00:00+00:00",
                },
            },
        },
        source_run_id=12,
    )
    await db_session.commit()

    await record_acquisition_contract_outcome(
        db_session,
        domain="example.com",
        surface="ecommerce_detail",
        source_run_id=13,
        method="browser",
        browser_engine="real_chrome",
        browser_diagnostics={},
        requested_fields=["title"],
        records=[],
        persisted_count=0,
        verdict="empty",
        blocked=False,
    )

    row = await load_domain_run_profile(
        db_session,
        domain="example.com",
        surface="ecommerce_detail",
    )
    assert row is not None
    assert row.profile["acquisition_contract"]["stale_after_failures"] == {
        "failure_count": 1,
        "stale": False,
    }

@pytest.mark.component
def test_normalize_domain_run_profile_rejects_invalid_source_run_id() -> None:
    with pytest.raises(ValueError, match="source_run_id must be a positive integer"):
        normalize_domain_run_profile({}, source_run_id="invalid")  # type: ignore[arg-type]

@pytest.mark.parametrize(
    ("legacy_value", "expected"),
    [
        ("pagination", "paginate"),
        ("infinite_scroll", "scroll"),
    ],
)
@pytest.mark.component
def test_normalize_domain_run_profile_translates_legacy_traversal_mode(
    legacy_value: str,
    expected: str,
) -> None:
    normalized = normalize_domain_run_profile(
        {
            "fetch_profile": {
                "traversal_mode": legacy_value,
            }
        },
        source_run_id=91,
    )

    assert normalized["fetch_profile"]["traversal_mode"] == expected

@pytest.mark.asyncio
@pytest.mark.component
async def test_save_domain_run_profile_propagates_programming_error_from_profile_load(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_load_domain_run_profile(*args, **kwargs):
        del args, kwargs
        raise ProgrammingError("select 1", {}, Exception("missing table"))

    monkeypatch.setattr(
        "app.services.crawl.profile.repository.load_domain_run_profile",
        _fake_load_domain_run_profile,
    )

    with pytest.raises(ProgrammingError):
        await save_domain_run_profile(
            db_session,
            domain="example.com",
            surface="ecommerce_detail",
            profile={},
            source_run_id=91,
        )

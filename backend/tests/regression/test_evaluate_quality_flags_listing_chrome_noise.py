from __future__ import annotations

from .test_harness_support import AcquisitionPlan, SimpleNamespace, classify_failure_mode, evaluate_quality, harness_support, hash_password, pytest, run_test_sites_acceptance, select, site_harness_runner, verify_password  # fmt: skip
from app.models.user import User

@pytest.mark.regression
def test_evaluate_quality_flags_listing_chrome_noise() -> None:
    site = {
        "url": "https://www.customink.com/products/sweatshirts/hoodies/71",
        "surface": "ecommerce_listing",
        "quality_expectations": {
            "require_listing_noise_free": True,
            "require_price": True,
        },
    }
    result = {
        "surface": "ecommerce_listing",
        "sample_records": [
            {
                "title": "Customer Reviews",
                "url": "https://www.customink.com/reviews",
                "populated_fields": 3,
                "price_present": False,
            }
        ],
        "sample_title": "Customer Reviews",
        "sample_url": "https://www.customink.com/reviews",
        "sample_looks_like_utility_chrome": True,
        "failure_mode": "success",
    }

    quality = evaluate_quality(site, result)

    assert quality["quality_verdict"] == "bad_output"
    assert quality["observed_failure_mode"] == "listing_chrome_noise"

@pytest.mark.regression
def test_evaluate_quality_flags_listing_sample_window_without_real_product_rows() -> (
    None
):
    site = {
        "url": "https://www.customink.com/products/sweatshirts/hoodies/71",
        "surface": "ecommerce_listing",
        "quality_expectations": {
            "require_listing_noise_free": True,
            "require_price": True,
        },
    }
    result = {
        "surface": "ecommerce_listing",
        "sample_title": "Diversity & Belonging",
        "sample_url": "https://www.customink.com/equity-for-all",
        "records": 14,
        "populated_fields": 2,
        "sample_records": [
            {
                "title": "Diversity & Belonging",
                "url": "https://www.customink.com/equity-for-all",
                "populated_fields": 2,
                "price_present": False,
            },
            {
                "title": "Customer Reviews",
                "url": "https://www.customink.com/reviews",
                "populated_fields": 2,
                "price_present": False,
            },
            {
                "title": "Customer Photos",
                "url": "https://www.customink.com/photos",
                "populated_fields": 2,
                "price_present": False,
            },
        ],
        "sample_semantics": {
            "price_present": False,
            "variant_count": 0,
            "variants_with_axes_count": 0,
            "variants_all_have_axes": False,
            "variants_with_price_count": 0,
            "legacy_variant_keys_present": False,
        },
        "failure_mode": "success",
    }

    quality = evaluate_quality(site, result)

    assert quality["quality_verdict"] == "bad_output"
    assert quality["observed_failure_mode"] == "listing_chrome_noise"
    assert quality["quality_checks"]["listing_noise_ok"] is False

@pytest.mark.regression
def test_evaluate_quality_accepts_non_utility_listing_rows_without_price_when_field_coverage_is_strong() -> (
    None
):
    site = {
        "url": "https://www.sigmaaldrich.com/IN/en/products/chemistry-and-biochemicals/biochemicals/antibiotics",
        "surface": "ecommerce_listing",
        "quality_expectations": {
            "require_listing_noise_free": True,
        },
    }
    result = {
        "surface": "ecommerce_listing",
        "sample_title": "Antibiotic Antimycotic Solution (100×), Stabilized",
        "sample_url": "https://www.sigmaaldrich.com/IN/en/product/sigma/a5955",
        "records": 8,
        "populated_fields": 3,
        "sample_records": [
            {
                "title": "Antibiotic Antimycotic Solution (100×), Stabilized",
                "url": "https://www.sigmaaldrich.com/IN/en/product/sigma/a5955",
                "populated_fields": 3,
                "price_present": False,
            },
            {
                "title": "Puromycin dihydrochloride from Streptomyces alboniger",
                "url": "https://www.sigmaaldrich.com/IN/en/product/sigma/p8833",
                "populated_fields": 3,
                "price_present": False,
            },
            {
                "title": "Ampicillin sodium salt",
                "url": "https://www.sigmaaldrich.com/IN/en/product/sigma/a5354",
                "populated_fields": 3,
                "price_present": False,
            },
        ],
        "sample_semantics": {
            "price_present": False,
            "variant_count": 0,
            "variants_with_axes_count": 0,
            "variants_all_have_axes": False,
            "variants_with_price_count": 0,
            "legacy_variant_keys_present": False,
        },
        "failure_mode": "success",
    }

    quality = evaluate_quality(site, result)

    assert quality["quality_verdict"] == "good"
    assert quality["observed_failure_mode"] == "control_good"
    assert quality["quality_checks"]["listing_noise_ok"] is True

@pytest.mark.regression
def test_evaluate_quality_does_not_flag_job_account_slug_as_utility() -> None:
    site = {
        "name": "EU Remote Jobs",
        "url": "https://euremotejobs.com/",
        "surface": "job_listing",
        "quality_expectations": {"require_listing_noise_free": True},
    }
    result = {
        "status": "completed",
        "verdict": "success",
        "records": 1,
        "sample_records": [
            {
                "title": "Account Manager: Generator Customers",
                "url": "https://euremotejobs.com/job/account-manager-generator-customers/",
                "populated_fields": 7,
                "price_present": False,
            }
        ],
        "sample_semantics": {
            "price_present": False,
            "variant_count": 0,
            "variants_with_axes_count": 0,
            "variants_all_have_axes": False,
            "variants_with_price_count": 0,
            "legacy_variant_keys_present": False,
        },
        "failure_mode": "success",
    }

    quality = evaluate_quality(site, result)

    assert quality["quality_verdict"] == "bad_output"
    assert quality["observed_failure_mode"] == "bad_output"
    assert quality["quality_checks"]["listing_noise_ok"] is True

@pytest.mark.regression
def test_acceptance_runner_uses_quality_verdict_for_curated_sites() -> None:
    site = {
        "name": "Catalog",
        "url": "https://example.com/catalog",
        "surface": "ecommerce_listing",
        "bucket": "must_pass",
        "quality_expectations": {"require_listing_noise_free": True},
    }
    result = {
        "quality_verdict": "usable_with_gaps",
    }

    assert run_test_sites_acceptance._expectation_met(site, result) is False

@pytest.mark.regression
def test_acceptance_runner_allows_bucketed_expected_failure_modes() -> None:
    site = {
        "name": "Blocked catalog",
        "url": "https://example.com/catalog",
        "surface": "ecommerce_listing",
        "bucket": "known_issue",
        "expected_failure_modes": ["listing_extraction_empty"],
    }
    result = {
        "failure_mode": "listing_extraction_empty",
    }

    assert run_test_sites_acceptance._expectation_met(site, result) is True

@pytest.mark.regression
def test_classify_failure_mode_buckets_spa_shell_failures() -> None:
    shell_404 = {
        "status_code": 404,
        "browser_diagnostics": {"browser_outcome": "low_content_shell"},
        "surface": "ecommerce_listing",
        "records": 0,
    }
    shell_low_content = {
        "status_code": 200,
        "browser_diagnostics": {"browser_outcome": "low_content_shell"},
        "surface": "ecommerce_listing",
        "records": 0,
    }
    readiness_timeout = {
        "status_code": 200,
        "browser_diagnostics": {
            "browser_outcome": "usable_content",
            "networkidle_timed_out": True,
        },
        "surface": "ecommerce_listing",
        "records": 0,
    }

    assert classify_failure_mode(shell_404) == "spa_shell_404"
    assert classify_failure_mode(shell_low_content) == "spa_shell_low_content"
    assert classify_failure_mode(readiness_timeout) == "spa_readiness_timeout"

@pytest.mark.regression
def test_classify_failure_mode_treats_uppercase_success_verdict_as_success() -> None:
    result = {
        "verdict": "SUCCESS",
        "browser_diagnostics": {},
        "records": 1,
        "sample_title": "Widget",
        "populated_fields": 3,
    }

    assert classify_failure_mode(result) == "success"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_run_site_harness_supports_acquisition_only_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            del exc_type, exc, tb
            return False

    class _FakeSettingsView:
        def acquisition_plan(self, *, surface: str):
            return AcquisitionPlan(surface=surface)

    async def _fake_create_crawl_run(session, user_id, payload):
        del session, user_id
        return SimpleNamespace(
            id=11,
            status="queued",
            url=payload["url"],
            settings_view=_FakeSettingsView(),
        )

    async def _fake_ensure_harness_user_id(session):
        del session
        return 7

    async def _fake_process_single_url(*, session, run, url, config):
        del session, run, url, config
        return SimpleNamespace(
            verdict="success",
            url_metrics={
                "method": "curl_cffi",
                "platform_family": "generic",
                "status_code": 200,
                "blocked": False,
                "record_count": 0,
                "browser_diagnostics": {},
            },
        )

    monkeypatch.setattr(site_harness_runner, "SessionLocal", lambda: _FakeSession())
    monkeypatch.setattr(
        site_harness_runner,
        "_ensure_harness_user_id",
        _fake_ensure_harness_user_id,
    )
    monkeypatch.setattr(site_harness_runner, "create_crawl_run", _fake_create_crawl_run)
    monkeypatch.setattr(
        site_harness_runner, "process_single_url", _fake_process_single_url
    )

    result = await harness_support.run_site_harness(
        url="https://example.com/catalog",
        surface="ecommerce_listing",
        mode=harness_support.HARNESS_MODE_ACQUISITION_ONLY,
    )

    assert result["verdict"] == "success"
    assert result["method"] == "curl_cffi"
    assert result["status_code"] == 200
    assert result["records"] == 0

@pytest.mark.asyncio
@pytest.mark.regression
async def test_run_site_harness_surfaces_challenge_summary_in_acquisition_only_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeSession:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            del exc_type, exc, tb
            return False

    class _FakeSettingsView:
        def acquisition_plan(self, *, surface: str):
            return AcquisitionPlan(surface=surface)

    async def _fake_create_crawl_run(session, user_id, payload):
        del session, user_id
        return SimpleNamespace(
            id=12,
            status="queued",
            url=payload["url"],
            settings_view=_FakeSettingsView(),
        )

    async def _fake_ensure_harness_user_id(session):
        del session
        return 7

    async def _fake_process_single_url(*, session, run, url, config):
        del session, run, url, config
        return SimpleNamespace(
            verdict="blocked",
            url_metrics={
                "method": "browser",
                "platform_family": "generic",
                "status_code": 429,
                "blocked": True,
                "record_count": 0,
                "browser_diagnostics": {
                    "browser_outcome": "challenge_page",
                    "challenge_provider_hits": ["DataDome"],
                    "challenge_evidence": [
                        "http_status:429",
                        "title:Verifying your connection...",
                    ],
                },
            },
        )

    monkeypatch.setattr(site_harness_runner, "SessionLocal", lambda: _FakeSession())
    monkeypatch.setattr(
        site_harness_runner,
        "_ensure_harness_user_id",
        _fake_ensure_harness_user_id,
    )
    monkeypatch.setattr(site_harness_runner, "create_crawl_run", _fake_create_crawl_run)
    monkeypatch.setattr(
        site_harness_runner, "process_single_url", _fake_process_single_url
    )

    result = await harness_support.run_site_harness(
        url="https://example.com/catalog",
        surface="ecommerce_listing",
        mode=harness_support.HARNESS_MODE_ACQUISITION_ONLY,
    )

    assert result["verdict"] == "blocked"
    assert result["challenge_summary"] == {
        "browser_outcome": "challenge_page",
        "provider": "datadome",
        "providers": ["datadome"],
        "elements": [],
        "evidence": [
            "http_status:429",
            "title:Verifying your connection...",
        ],
    }

@pytest.mark.asyncio
@pytest.mark.regression
async def test_ensure_harness_user_id_reuses_user_by_configured_email(
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("HARNESS_EMAIL", "harness@example.invalid")
    monkeypatch.setenv("HARNESS_PASSWORD", "HarnessSecret123!")
    monkeypatch.setenv("HARNESS_ROLE", "harness")

    first_user_id = await harness_support._ensure_harness_user_id(db_session)
    second_user_id = await harness_support._ensure_harness_user_id(db_session)
    user = (
        await db_session.execute(
            select(User).where(
                User.email == "harness@example.invalid"
            )
        )
    ).scalar_one()

    assert first_user_id == second_user_id == user.id
    assert user.role == "harness"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_ensure_harness_user_id_uses_local_default_credentials_without_env(
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("HARNESS_EMAIL", raising=False)
    monkeypatch.delenv("HARNESS_PASSWORD", raising=False)
    monkeypatch.delenv("HARNESS_ROLE", raising=False)

    user_id = await harness_support._ensure_harness_user_id(db_session)
    user = (
        await db_session.execute(
            select(User).where(
                User.email == harness_support.DEFAULT_HARNESS_EMAIL
            )
        )
    ).scalar_one()

    assert user_id == user.id
    assert user.role == "harness"

@pytest.mark.asyncio
@pytest.mark.regression
async def test_ensure_harness_user_id_rejects_production_environment(
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("HARNESS_EMAIL", "harness@example.invalid")
    monkeypatch.setenv("HARNESS_PASSWORD", "HarnessSecret123!")

    with pytest.raises(
        RuntimeError,
        match="Harness user access is disabled outside local/test environments",
    ):
        await harness_support._ensure_harness_user_id(db_session)

@pytest.mark.asyncio
@pytest.mark.regression
async def test_ensure_harness_user_id_rejects_password_sync_without_flag(
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("HARNESS_EMAIL", "harness@example.invalid")
    monkeypatch.setenv("HARNESS_PASSWORD", "NewHarnessSecret123!")
    monkeypatch.delenv("ENABLE_HARNESS_PASSWORD_SYNC", raising=False)

    user = User(
        email="harness@example.invalid",
        hashed_password=hash_password("OldHarnessSecret123!"),
        role="harness",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    with pytest.raises(RuntimeError, match="ENABLE_HARNESS_PASSWORD_SYNC=true"):
        await harness_support._ensure_harness_user_id(db_session)

    persisted = (
        await db_session.execute(
            select(User).where(
                User.email == "harness@example.invalid"
            )
        )
    ).scalar_one()
    assert verify_password("OldHarnessSecret123!", persisted.hashed_password)
    assert not verify_password("NewHarnessSecret123!", persisted.hashed_password)

@pytest.mark.asyncio
@pytest.mark.regression
async def test_ensure_harness_user_id_allows_password_sync_with_flag(
    db_session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.setenv("HARNESS_EMAIL", "harness@example.invalid")
    monkeypatch.setenv("HARNESS_PASSWORD", "NewHarnessSecret123!")
    monkeypatch.setenv("ENABLE_HARNESS_PASSWORD_SYNC", "true")

    user = User(
        email="harness@example.invalid",
        hashed_password=hash_password("OldHarnessSecret123!"),
        role="harness",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()

    user_id = await harness_support._ensure_harness_user_id(db_session)
    persisted = (
        await db_session.execute(
            select(User).where(
                User.email == "harness@example.invalid"
            )
        )
    ).scalar_one()

    assert user_id == persisted.id
    assert verify_password("NewHarnessSecret123!", persisted.hashed_password)

@pytest.mark.regression
def test_harness_user_module_does_not_export_private_ensure_helper() -> None:
    from harness import harness_user

    assert harness_user.__all__ == ["DEFAULT_HARNESS_EMAIL"]

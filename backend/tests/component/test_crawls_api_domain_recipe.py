from __future__ import annotations

import pytest
from tests.fixtures.assertions import (
    assert_equal,
    assert_is,
    assert_is_not,
    assert_not_in,
    assert_true,
)
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.core.dependencies import get_current_user, get_db
from app.main import app
from app.models.domain_memory import DomainFieldFeedback
from app.services.crawl.batch_runtime import process_run
from app.services.acquisition.cookie_store import persist_storage_state_for_domain
from app.services.acquisition.acquirer import AcquisitionResult
from app.services.crawl.crud import create_crawl_run
from app.services.domain_memory_service import save_domain_memory


def _authenticated_proxy_url() -> str:
    return "http://user:" + "secret" + "@example-proxy.local:8080"


@pytest.fixture
async def crawls_api_client(db_session, test_user):
    async def _override_db():
        yield db_session

    async def _override_user():
        return test_user

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.mark.asyncio
@pytest.mark.component
async def test_crawls_logs_query_params_are_validated(
    crawls_api_client: AsyncClient,
) -> None:
    response = await crawls_api_client.get(
        "/api/crawls/1/logs",
        params={"after_id": -1, "limit": 2001},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
@pytest.mark.component
async def test_domain_recipe_does_not_mark_browser_required_from_summary_usage_only(
    crawls_api_client: AsyncClient,
    db_session,
    test_user,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://domain-recipe.example.invalid/products/summary-only-widget",
            "surface": "ecommerce_detail",
        },
    )
    run.result_summary = {"acquisition_summary": {"methods": {"browser": 1}}}
    await db_session.commit()

    response = await crawls_api_client.get(f"/api/crawls/{run.id}/domain-recipe")

    assert response.status_code == 200
    recipe = response.json()
    assert recipe["acquisition_evidence"]["actual_fetch_method"] == "browser"
    assert recipe["acquisition_evidence"]["browser_used"] is True
    assert recipe["affordance_candidates"]["browser_required"] is False


@pytest.mark.asyncio
@pytest.mark.component
async def test_crawls_domain_recipe_routes_round_trip(
    crawls_api_client: AsyncClient,
    db_session,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lookup_before_run = await crawls_api_client.get(
        "/api/crawls/domain-run-profile",
        params={
            "url": "https://domain-recipe.example.invalid/products/domain-recipe-widget",
            "surface": "ecommerce_detail",
        },
    )
    assert_equal(lookup_before_run.status_code, 200)
    assert_equal(
        lookup_before_run.json(),
        {
            "domain": "domain-recipe.example.invalid",
            "surface": "ecommerce_detail",
            "saved_run_profile": None,
        },
    )

    await save_domain_memory(
        db_session,
        domain="domain-recipe.example.invalid",
        surface="ecommerce_detail",
        selectors={
            "rules": [
                {
                    "id": 1,
                    "field_name": "title",
                    "css_selector": ".saved-title",
                    "sample_value": "Saved Selector Widget",
                    "source": "domain_memory",
                    "status": "validated",
                    "is_active": True,
                    "source_run_id": 41,
                }
            ]
        },
    )
    await db_session.commit()

    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://domain-recipe.example.invalid/products/domain-recipe-widget",
            "surface": "ecommerce_detail",
            "additional_fields": ["brand"],
            "settings": {
                "extraction_contract": [
                    {
                        "field_name": "price",
                        "css_selector": ".run-price",
                    }
                ]
            },
        },
    )

    async def _fake_acquire(request):
        return AcquisitionResult(
            request=request,
            final_url=request.url,
            html="""
            <html>
              <body>
                <div class="saved-title">Saved Selector Widget</div>
                <div class="run-price">$19.99</div>
                <div class="brand">Example Brand</div>
              </body>
            </html>
            """,
            method="browser",
            status_code=200,
            browser_diagnostics={"browser_reason": "http-escalation"},
        )

    monkeypatch.setattr("app.services.pipeline.extraction_loop.acquire", _fake_acquire)

    await process_run(db_session, run.id)

    recipe_response = await crawls_api_client.get(f"/api/crawls/{run.id}/domain-recipe")
    assert_equal(recipe_response.status_code, 200)
    recipe = recipe_response.json()
    assert_equal(
        recipe["requested_field_coverage"],
        {
            "requested": ["brand"],
            "found": ["brand"],
            "missing": [],
        },
    )
    assert_is(recipe["affordance_candidates"]["browser_required"], True)
    assert_equal(
        {row["field_name"] for row in recipe["selector_candidates"]},
        {
            "brand",
            "price",
            "title",
        },
    )
    assert_equal(recipe["acquisition_evidence"]["actual_fetch_method"], "browser")
    assert_equal(recipe["acquisition_evidence"]["browser_reason"], "http-escalation")
    if recipe["saved_run_profile"] is not None:
        assert_not_in("proxy_profile", recipe["saved_run_profile"])

    save_profile_response = await crawls_api_client.post(
        f"/api/crawls/{run.id}/domain-recipe/save-run-profile",
        json={
            "profile": {
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
                    "last_quality_success": None,
                    "required_rendering": False,
                    "required_traversal": False,
                    "required_network_payloads": False,
                    "stale_after_failures": {"failure_count": 0, "stale": False},
                },
                "proxy_profile": {
                    "enabled": True,
                    "proxy_list": [
                        _authenticated_proxy_url(),
                        "https://clean-proxy.example:8443",
                    ],
                },
            }
        },
    )
    assert_equal(save_profile_response.status_code, 200)
    saved_profile = save_profile_response.json()
    assert_equal(saved_profile["fetch_profile"]["fetch_mode"], "http_then_browser")
    assert_equal(
        saved_profile["acquisition_contract"]["preferred_browser_engine"], "real_chrome"
    )
    assert_is(saved_profile["acquisition_contract"]["handoff_eligible"], True)
    assert_equal(saved_profile["locality_profile"]["geo_country"], "IN")
    assert_equal(saved_profile["source_run_id"], run.id)
    assert_not_in("proxy_profile", saved_profile)

    lookup_after_save = await crawls_api_client.get(
        "/api/crawls/domain-run-profile",
        params={
            "url": "https://domain-recipe.example.invalid/products/domain-recipe-widget",
            "surface": "ecommerce_detail",
        },
    )
    assert_equal(lookup_after_save.status_code, 200)
    assert_equal(
        lookup_after_save.json()["saved_run_profile"]["fetch_profile"]["fetch_mode"],
        "http_then_browser",
    )
    assert_not_in("proxy_profile", lookup_after_save.json()["saved_run_profile"])

    list_profiles_response = await crawls_api_client.get(
        "/api/crawls/domain-memory/run-profiles",
        params={"domain": "domain-recipe.example.invalid"},
    )
    assert_equal(list_profiles_response.status_code, 200)
    assert_equal(
        list_profiles_response.json()[0]["domain"], "domain-recipe.example.invalid"
    )
    assert_equal(list_profiles_response.json()[0]["surface"], "ecommerce_detail")
    assert_equal(
        list_profiles_response.json()[0]["profile"]["fetch_profile"]["fetch_mode"],
        "http_then_browser",
    )

    normalized_profiles_response = await crawls_api_client.get(
        "/api/crawls/domain-memory/run-profiles",
        params={
            "domain": "HTTPS://domain-recipe.example.invalid/products/domain-recipe-widget",
            "surface": " ECOMMERCE_DETAIL ",
        },
    )
    assert_equal(normalized_profiles_response.status_code, 200)
    assert_equal(len(normalized_profiles_response.json()), 1)

    promote_response = await crawls_api_client.post(
        f"/api/crawls/{run.id}/domain-recipe/promote-selectors",
        json={
            "selectors": [
                {
                    "candidate_key": "price|css_selector|.run-price",
                    "field_name": "price",
                    "selector_kind": "css_selector",
                    "selector_value": ".run-price",
                    "sample_value": "$19.99",
                }
            ]
        },
    )
    assert_equal(promote_response.status_code, 200)
    promoted = promote_response.json()
    assert_equal(len(promoted), 1)
    assert_equal(promoted[0]["field_name"], "price")
    assert_equal(promoted[0]["source"], "domain_recipe")
    assert_equal(promoted[0]["source_run_id"], run.id)

    recipe_after_save = await crawls_api_client.get(
        f"/api/crawls/{run.id}/domain-recipe"
    )
    assert_equal(recipe_after_save.status_code, 200)
    saved_recipe = recipe_after_save.json()
    assert_equal(
        saved_recipe["saved_run_profile"]["fetch_profile"]["fetch_mode"],
        "http_then_browser",
    )
    assert_not_in("proxy_profile", saved_recipe["saved_run_profile"])
    assert_true(
        any(row["field_name"] == "price" for row in saved_recipe["saved_selectors"])
    )
    promoted_candidate = None
    for row in saved_recipe["selector_candidates"]:
        if row["field_name"] == "price":
            promoted_candidate = row
            break
    assert_is_not(promoted_candidate, None)
    assert_is(promoted_candidate["already_saved"], True)
    assert_equal(promoted_candidate["saved_selector_id"], promoted[0]["id"])

    field_action_response = await crawls_api_client.post(
        f"/api/crawls/{run.id}/domain-recipe/field-action",
        json={
            "field_name": "price",
            "action": "reject",
            "selector_kind": "css_selector",
            "selector_value": ".run-price",
            "source_record_ids": [1],
        },
    )
    assert_equal(field_action_response.status_code, 200)
    assert_equal(field_action_response.json()["action"], "reject")
    feedback_rows = list(
        (await db_session.execute(select(DomainFieldFeedback))).scalars().all()
    )
    assert_equal(len(feedback_rows), 1)

    await persist_storage_state_for_domain(
        "domain-recipe.example.invalid",
        {
            "cookies": [
                {
                    "name": "session",
                    "value": "abc",
                    "domain": ".domain-recipe.example.invalid",
                    "path": "/",
                }
            ],
            "origins": [],
        },
        session=db_session,
    )
    cookies_response = await crawls_api_client.get(
        "/api/crawls/domain-memory/cookies",
        params={"domain": "domain-recipe.example.invalid"},
    )
    assert_equal(cookies_response.status_code, 200)
    assert_equal(cookies_response.json()[0]["domain"], "domain-recipe.example.invalid")
    assert_equal(cookies_response.json()[0]["cookie_count"], 1)

    feedback_response = await crawls_api_client.get(
        "/api/crawls/domain-memory/field-feedback",
        params={
            "domain": "domain-recipe.example.invalid",
            "surface": "ecommerce_detail",
        },
    )
    assert_equal(feedback_response.status_code, 200)
    feedback_payload = feedback_response.json()
    assert_equal(len(feedback_payload), 1)
    assert_equal(
        feedback_payload[0],
        {
            **feedback_payload[0],
            "id": feedback_rows[0].id,
            "domain": "domain-recipe.example.invalid",
            "surface": "ecommerce_detail",
            "field_name": "price",
            "action": "reject",
            "source_kind": "selector",
            "source_value": ".run-price",
            "source_run_id": run.id,
            "selector_kind": "css_selector",
            "selector_value": ".run-price",
            "source_record_ids": [1],
        },
    )


@pytest.mark.asyncio
@pytest.mark.component
async def test_domain_run_profile_contract_autosaves_real_chrome_success(
    crawls_api_client: AsyncClient,
    db_session,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = await create_crawl_run(
        db_session,
        test_user.id,
        {
            "run_type": "crawl",
            "url": "https://domain-recipe.example.invalid/products/real-chrome-widget",
            "surface": "ecommerce_detail",
            "requested_fields": ["title"],
            "settings": {},
        },
    )

    async def _fake_acquire(request):
        return AcquisitionResult(
            request=request,
            final_url=request.url,
            html="<html><body><h1>Real Chrome Widget</h1></body></html>",
            method="browser",
            status_code=200,
            browser_diagnostics={
                "browser_reason": "acquisition-contract",
                "browser_engine": "real_chrome",
            },
        )

    monkeypatch.setattr("app.services.pipeline.extraction_loop.acquire", _fake_acquire)

    await process_run(db_session, run.id)

    lookup = await crawls_api_client.get(
        "/api/crawls/domain-run-profile",
        params={
            "url": "https://domain-recipe.example.invalid/products/real-chrome-widget",
            "surface": "ecommerce_detail",
        },
    )
    assert lookup.status_code == 200
    contract = lookup.json()["saved_run_profile"]["acquisition_contract"]
    assert contract["preferred_browser_engine"] == "real_chrome"
    assert contract["prefer_browser"] is True
    assert contract["handoff_eligible"] is True
    assert contract["handoff_cookie_engine"] == "real_chrome"
    assert contract["required_rendering"] is False
    assert contract["required_traversal"] is False
    assert contract["required_network_payloads"] is False
    assert contract["last_quality_success"]["field_coverage"] == {
        "requested": ["title", "price", "image_url"],
        "found": ["title"],
        "missing": ["price", "image_url"],
    }
    assert contract["stale_after_failures"] == {"failure_count": 0, "stale": False}

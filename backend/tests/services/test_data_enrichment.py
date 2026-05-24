from __future__ import annotations

import asyncio
from dataclasses import replace
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.exc import PendingRollbackError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models.data_enrichment import EnrichedProduct
from app.models.crawl_run import CrawlRecord
from app.schemas.data_enrichment import DataEnrichmentJobDetailResponse
from app.services.llm.types import LLMTaskResult
from app.services.llm.errors import LLMErrorCategory
from app.services.config.data_enrichment import (
    DATA_ENRICHMENT_LLM_TASK,
    DATA_ENRICHMENT_STATUS_DEGRADED,
    DATA_ENRICHMENT_STATUS_ENRICHED,
    DATA_ENRICHMENT_STATUS_FAILED,
    DATA_ENRICHMENT_STATUS_PENDING,
    DATA_ENRICHMENT_STATUS_RUNNING,
    DATA_ENRICHMENT_TAXONOMY_VERSION,
)
from app.services.data_enrichment.service import (
    ai_discovery_allowed_tags_for_product,
    run_job,
    build_deterministic_enrichment,
    llm_prompt_context,
    build_data_enrichment_job_payload,
    create_data_enrichment_job,
    get_data_enrichment_job,
    list_data_enrichment_jobs,
)
from app.services.data_enrichment import service as enrichment_service
from app.services.data_enrichment.deterministic import normalize_price
from app.services.data_enrichment.deterministic import (
    category_url_context,
    percentage_material_parse,
    plausible_size_value,
)
from app.services.data_enrichment.shopify_catalog import (
    accessory_path_conflict,
    normalize_taxonomy_token,
    special_token_conflict,
    sport_specific_conflict,
    taxonomy_candidate_conflicts,
    toys_vs_sports_conflict,
)

BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _as_async(fn):
    async def _wrapped(*args, **kwargs):
        await asyncio.sleep(0)
        return fn(*args, **kwargs)

    return _wrapped


@pytest.mark.asyncio
async def test_data_enrichment_job_creates_pending_rows(
    db_session: AsyncSession,
    create_test_run,
    test_user,
) -> None:
    run = await create_test_run(
        url="https://example.com/products/linen-dress",
        surface="ecommerce_detail",
    )
    record = CrawlRecord(
        run_id=run.id,
        source_url="https://example.com/products/linen-dress",
        data={
            "title": "Navy Linen Dress",
            "price": "$49.99",
            "currency": "USD",
            "category": "Women > Dresses",
            "gender": "women",
        },
    )
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(record)

    job = await create_data_enrichment_job(
        db_session,
        user=test_user,
        payload={"source_record_ids": [record.id]},
    )

    product = (
        await db_session.scalars(
            select(EnrichedProduct).where(EnrichedProduct.job_id == job.id)
        )
    ).one()
    await db_session.refresh(record)

    assert job.status == DATA_ENRICHMENT_STATUS_PENDING
    assert job.summary["accepted_count"] == 1
    assert record.enrichment_status == DATA_ENRICHMENT_STATUS_PENDING
    assert product.source_record_id == record.id
    assert product.status == DATA_ENRICHMENT_STATUS_PENDING
    assert product.price_normalized is None
    assert product.gender_normalized is None


@pytest.mark.asyncio
async def test_data_enrichment_allows_already_enriched_records(
    db_session: AsyncSession,
    create_test_run,
    test_user,
) -> None:
    run = await create_test_run(
        url="https://example.com/products/linen-dress",
        surface="ecommerce_detail",
    )
    record = CrawlRecord(
        run_id=run.id,
        source_url="https://example.com/products/linen-dress",
        data={"title": "Linen Dress"},
        enrichment_status=DATA_ENRICHMENT_STATUS_ENRICHED,
    )
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(record)

    job = await create_data_enrichment_job(
        db_session,
        user=test_user,
        payload={"source_record_ids": [record.id]},
    )
    product = (
        await db_session.scalars(
            select(EnrichedProduct).where(EnrichedProduct.job_id == job.id)
        )
    ).one()
    await db_session.refresh(record)

    assert job.summary["accepted_count"] == 1
    assert record.enrichment_status == DATA_ENRICHMENT_STATUS_PENDING
    assert product.source_record_id == record.id


@pytest.mark.asyncio
async def test_data_enrichment_skips_active_records(
    db_session: AsyncSession,
    create_test_run,
    test_user,
) -> None:
    run = await create_test_run(
        url="https://example.com/products/linen-dress",
        surface="ecommerce_detail",
    )
    record = CrawlRecord(
        run_id=run.id,
        source_url="https://example.com/products/linen-dress",
        data={"title": "Linen Dress"},
        enrichment_status=DATA_ENRICHMENT_STATUS_RUNNING,
    )
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(record)

    with pytest.raises(
        ValueError, match="No eligible ecommerce detail records selected"
    ):
        await create_data_enrichment_job(
            db_session,
            user=test_user,
            payload={"source_record_ids": [record.id]},
        )


@pytest.mark.asyncio
async def test_data_enrichment_rejects_non_ecommerce_detail_records(
    db_session: AsyncSession,
    create_test_run,
    test_user,
) -> None:
    run = await create_test_run(
        url="https://jobs.example.com/job/123",
        surface="job_detail",
    )
    record = CrawlRecord(
        run_id=run.id,
        source_url="https://jobs.example.com/job/123",
        data={"title": "Engineer"},
    )
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(record)

    with pytest.raises(
        ValueError, match="No eligible ecommerce detail records selected"
    ):
        await create_data_enrichment_job(
            db_session,
            user=test_user,
            payload={"source_record_ids": [record.id]},
        )


@pytest.mark.asyncio
async def test_data_enrichment_job_detail_payload_serializes(
    db_session: AsyncSession,
    create_test_run,
    test_user,
) -> None:
    run = await create_test_run(
        url="https://example.com/products/linen-dress",
        surface="ecommerce_detail",
    )
    record = CrawlRecord(
        run_id=run.id,
        source_url="https://example.com/products/linen-dress",
        data={"title": "Linen Dress"},
    )
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(record)
    job = await create_data_enrichment_job(
        db_session,
        user=test_user,
        payload={"source_record_ids": [record.id]},
    )

    jobs = await list_data_enrichment_jobs(db_session, user=test_user)
    loaded = await get_data_enrichment_job(db_session, user=test_user, job_id=job.id)
    payload = await build_data_enrichment_job_payload(db_session, job=loaded)
    response = DataEnrichmentJobDetailResponse.model_validate(payload)

    assert [row.id for row in jobs] == [job.id]
    assert response.job.id == job.id
    assert len(response.enriched_products) == 1


@pytest.mark.asyncio
async def test_data_enrichment_job_defers_running_commit_until_complete(
    db_session: AsyncSession,
    create_test_run,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run = await create_test_run(
        url="https://example.com/products/navy-linen-dress",
        surface="ecommerce_detail",
    )
    record = CrawlRecord(
        run_id=run.id,
        source_url="https://example.com/products/navy-linen-dress",
        data={"title": "Navy Linen Midi Dress", "category": "Dresses"},
    )
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(record)
    job = await create_data_enrichment_job(
        db_session,
        user=test_user,
        payload={"source_record_ids": [record.id], "options": {"llm_enabled": False}},
    )
    started = asyncio.Event()
    release = asyncio.Event()

    async def _blocking_enrich_product(*args, **kwargs):
        del args, kwargs
        started.set()
        await release.wait()

    monkeypatch.setattr(
        "app.services.data_enrichment.service._enrich_product",
        _blocking_enrich_product,
    )

    task = asyncio.create_task(run_job(db_session, job))
    await asyncio.wait_for(started.wait(), timeout=2)
    session_factory = async_sessionmaker(
        db_session.bind,
        expire_on_commit=False,
        class_=AsyncSession,
    )
    async with session_factory() as check_session:
        visible_job = await check_session.get(type(job), job.id)

    release.set()
    await task

    assert visible_job is not None
    assert visible_job.status == DATA_ENRICHMENT_STATUS_RUNNING


@pytest.mark.asyncio
async def test_data_enrichment_deterministic_job_populates_enriched_fields(
    db_session: AsyncSession,
    create_test_run,
    test_user,
) -> None:
    run = await create_test_run(
        url="https://example.com/products/navy-linen-dress",
        surface="ecommerce_detail",
    )
    record = CrawlRecord(
        run_id=run.id,
        source_url="https://example.com/products/navy-linen-dress",
        data={
            "title": "Navy Linen Midi Dress",
            "brand": "Acme",
            "price": "$49.99",
            "currency": "USD",
            "color": "navy",
            "size": "medium",
            "gender": "women",
            "materials": "100% linen",
            "availability": "In stock",
            "category": "Dresses",
            "description": "<p>Elegant linen dress for events.</p>",
        },
    )
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(record)
    job = await create_data_enrichment_job(
        db_session,
        user=test_user,
        payload={"source_record_ids": [record.id], "options": {"llm_enabled": False}},
    )

    await run_job(db_session, job)
    product = (
        await db_session.scalars(
            select(EnrichedProduct).where(EnrichedProduct.job_id == job.id)
        )
    ).one()
    await db_session.refresh(record)

    assert job.status == DATA_ENRICHMENT_STATUS_ENRICHED
    assert record.enrichment_status == DATA_ENRICHMENT_STATUS_ENRICHED
    assert product.status == DATA_ENRICHMENT_STATUS_ENRICHED
    assert product.price_normalized == {"amount": 49.99, "currency": "USD"}
    assert product.color_family == "blue"
    assert product.size_normalized == ["M"]
    assert product.size_system == "alpha"
    assert product.gender_normalized == "female"
    assert product.materials_normalized == ["linen"]
    assert product.availability_normalized == "in_stock"
    assert product.category_path
    assert product.category_path == "Apparel & Accessories > Clothing > Dresses"
    assert product.taxonomy_version == DATA_ENRICHMENT_TAXONOMY_VERSION
    assert (
        product.diagnostics["product_category"]["category_path"]
        == "Apparel & Accessories > Clothing > Dresses"
    )
    assert (
        product.diagnostics["product_category"]["taxonomy_reference"]["category_path"]
        == "Apparel & Accessories > Clothing > Dresses"
    )
    assert (
        product.diagnostics["product_category"]["taxonomy_version"]
        == DATA_ENRICHMENT_TAXONOMY_VERSION
    )
    assert "fabric" in product.diagnostics["product_attributes"]["present_attributes"]
    assert "image_link" in product.diagnostics["product_attributes"]["null_attributes"]
    assert "linen" in product.seo_keywords
    assert product.intent_attributes is None


@pytest.mark.asyncio
async def test_data_enrichment_uses_job_llm_snapshot_over_source_run_snapshot(
    db_session: AsyncSession,
    create_test_run,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _stale_run_snapshot(_session):
        return {
            "general": {
                "provider": "nvidia",
                "model": "stale-run-model",
                "task_type": "general",
                "id": 3,
                "api_key_encrypted": "enc-stale",
            }
        }

    monkeypatch.setattr(
        "app.services.crawl.crud.snapshot_active_configs",
        _stale_run_snapshot,
    )
    run = await create_test_run(
        url="https://example.com/products/navy-linen-dress",
        surface="ecommerce_detail",
    )

    async def _job_snapshot(_session, task_types=None):
        assert task_types == [DATA_ENRICHMENT_LLM_TASK]
        return {
            DATA_ENRICHMENT_LLM_TASK: {
                "provider": "groq",
                "model": "live-enrichment-model",
                "task_type": DATA_ENRICHMENT_LLM_TASK,
                "id": 7,
                "api_key_encrypted": "enc-live",
            }
        }

    monkeypatch.setattr(
        "app.services.data_enrichment.service.snapshot_active_configs",
        _job_snapshot,
    )

    record = CrawlRecord(
        run_id=run.id,
        source_url="https://example.com/products/navy-linen-dress",
        data={
            "title": "Navy Linen Midi Dress",
            "price": "$49.99",
            "currency": "USD",
            "category": "Dresses",
            "description": "Elegant linen dress for events.",
        },
    )
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(record)

    job = await create_data_enrichment_job(
        db_session,
        user=test_user,
        payload={"source_record_ids": [record.id], "options": {"llm_enabled": True}},
    )

    async def fake_run_prompt_task(
        session,
        *,
        task_type,
        run_id,
        domain,
        variables,
        budget_scope,
        timeout_seconds,
        config_snapshot,
    ):
        del session, domain, variables, budget_scope, timeout_seconds
        assert task_type == DATA_ENRICHMENT_LLM_TASK
        assert run_id == run.id
        assert isinstance(config_snapshot, dict)
        config = config_snapshot[DATA_ENRICHMENT_LLM_TASK]
        assert config["provider"] == "groq"
        assert config["model"] == "live-enrichment-model"
        return LLMTaskResult(
            payload={"audience": ["occasion"]},
            provider="groq",
            model="live-enrichment-model",
        )

    monkeypatch.setattr(
        "app.services.data_enrichment.service.run_prompt_task",
        fake_run_prompt_task,
    )

    await run_job(db_session, job)
    product = (
        await db_session.scalars(
            select(EnrichedProduct).where(EnrichedProduct.job_id == job.id)
        )
    ).one()

    assert (
        job.options["llm_config_snapshot"][DATA_ENRICHMENT_LLM_TASK]["provider"]
        == "groq"
    )
    assert product.diagnostics["llm"]["provider"] == "groq"
    assert product.diagnostics["llm"]["model"] == "live-enrichment-model"


@pytest.mark.asyncio
async def test_data_enrichment_category_low_confidence_stays_null(
    db_session: AsyncSession,
    create_test_run,
    test_user,
) -> None:
    run = await create_test_run(
        url="https://example.com/products/mystery",
        surface="ecommerce_detail",
    )
    record = CrawlRecord(
        run_id=run.id,
        source_url="https://example.com/products/mystery",
        data={"title": "ZXQ Plinth", "category": "ZXQ Plinth"},
    )
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(record)
    job = await create_data_enrichment_job(
        db_session,
        user=test_user,
        payload={"source_record_ids": [record.id]},
    )

    await run_job(db_session, job)
    product = (
        await db_session.scalars(
            select(EnrichedProduct).where(EnrichedProduct.job_id == job.id)
        )
    ).one()

    assert product.category_path is None


@pytest.mark.asyncio
async def test_data_enrichment_reenrichment_clears_taxonomy_version_before_rerun(
    db_session: AsyncSession,
    create_test_run,
    test_user,
) -> None:
    run = await create_test_run(
        url="https://example.com/products/dress",
        surface="ecommerce_detail",
    )
    record = CrawlRecord(
        run_id=run.id,
        source_url="https://example.com/products/dress",
        data={"title": "Linen Dress", "category": "Dresses"},
    )
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(record)

    first_job = await create_data_enrichment_job(
        db_session,
        user=test_user,
        payload={"source_record_ids": [record.id]},
    )
    await run_job(db_session, first_job)
    product = (
        await db_session.scalars(
            select(EnrichedProduct).where(EnrichedProduct.source_record_id == record.id)
        )
    ).one()
    assert product.taxonomy_version == DATA_ENRICHMENT_TAXONOMY_VERSION

    second_job = await create_data_enrichment_job(
        db_session,
        user=test_user,
        payload={"source_record_ids": [record.id]},
    )
    refreshed = (
        await db_session.scalars(
            select(EnrichedProduct).where(EnrichedProduct.job_id == second_job.id)
        )
    ).one()

    assert refreshed.taxonomy_version is None


@pytest.mark.asyncio
async def test_data_enrichment_llm_disabled_makes_no_call(
    db_session: AsyncSession,
    create_test_run,
    test_user,
    monkeypatch,
) -> None:
    def fail_run_prompt_task(*args, **kwargs):
        raise AssertionError("LLM must not run when llm_enabled is false")

    monkeypatch.setattr(
        "app.services.data_enrichment.service.run_prompt_task",
        _as_async(fail_run_prompt_task),
    )
    run = await create_test_run(
        url="https://example.com/products/dress",
        surface="ecommerce_detail",
    )
    record = CrawlRecord(
        run_id=run.id,
        source_url="https://example.com/products/dress",
        data={"title": "Linen Dress", "category": "Dresses"},
    )
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(record)
    job = await create_data_enrichment_job(
        db_session,
        user=test_user,
        payload={"source_record_ids": [record.id], "options": {"llm_enabled": False}},
    )

    await run_job(db_session, job)

    assert job.status == DATA_ENRICHMENT_STATUS_ENRICHED


def test_data_enrichment_llm_prompt_context_excludes_raw_artifacts() -> None:
    product = EnrichedProduct(
        job_id=1,
        source_url="https://example.com/products/dress",
        status=DATA_ENRICHMENT_STATUS_PENDING,
        price_normalized={"amount": 49.99, "currency": "USD"},
        color_family="blue",
        size_normalized=["M"],
        size_system="alpha",
        gender_normalized="female",
        materials_normalized=["linen"],
        availability_normalized="in_stock",
        seo_keywords=["linen", "dress"],
        category_path="Media > Books",
        taxonomy_version=DATA_ENRICHMENT_TAXONOMY_VERSION,
    )

    context = llm_prompt_context(
        {
            "title": "Linen Dress",
            "description": "<section>Clean description</section>",
            "raw_html": "<html>secret</html>",
            "_source": "artifact",
        },
        product=product,
        category_candidates=[],
    )

    assert "raw_html" not in context
    assert "_source" not in context
    assert context["description_excerpt"] == "Clean description"
    assert context["taxonomy_version"] == DATA_ENRICHMENT_TAXONOMY_VERSION
    assert "audience_allowed_values" not in context


def test_data_enrichment_llm_prompt_context_includes_structured_taxonomy_data() -> None:
    product = EnrichedProduct(
        job_id=1,
        source_url="https://example.com/products/dress",
        status=DATA_ENRICHMENT_STATUS_PENDING,
        seo_keywords=["linen dress", "summer dress"],
        materials_normalized=["linen"],
        color_family="blue",
        gender_normalized="female",
    )
    description = "x" * 700

    context = llm_prompt_context(
        {
            "title": "Linen Dress",
            "description": description,
            "category": "Dresses",
        },
        product=product,
        category_candidates=[
            {
                "category_id": "aa-1",
                "category_path": "Apparel & Accessories > Clothing > Dresses",
                "score": 0.52,
                "source": "scored_match",
                "taxonomy_version": DATA_ENRICHMENT_TAXONOMY_VERSION,
                "taxonomy_reference": {
                    "attribute_handles": ["color", "fabric", "target_gender"]
                },
            }
        ],
    )

    assert context["description_excerpt"] == description[:600]
    assert context["taxonomy_candidates"] == [
        {
            "category_id": "aa-1",
            "category_path": "Apparel & Accessories > Clothing > Dresses",
            "score": 0.52,
            "source": "scored_match",
            "taxonomy_version": DATA_ENRICHMENT_TAXONOMY_VERSION,
            "attribute_handles": ["color", "fabric", "target_gender"],
        }
    ]
    assert "linen-dress" in context["ai_discovery_allowed_tags"]
    assert "female" in context["ai_discovery_allowed_tags"]


def test_data_enrichment_semantic_system_prompt_documents_schema() -> None:
    prompt_path = (
        BACKEND_ROOT
        / "app"
        / "data"
        / "prompts"
        / "data_enrichment_semantic.system.txt"
    )
    prompt = prompt_path.read_text(encoding="utf-8")

    assert "Output schema" in prompt
    assert "missing_backfill_fields" in prompt
    assert "Real Shopify taxonomy path only" in prompt
    assert "Return only valid JSON" in prompt


def test_plausible_size_value_accepts_known_numeric_system_before_strong_gate() -> None:
    assert plausible_size_value(
        "42",
        aliases={},
        systems={"numeric": {"42"}},
        require_strong=False,
    )


def test_percentage_material_parse_trims_context_near_percentage() -> None:
    assert percentage_material_parse("Made with cotton 60 percent and polyester 40%.") == [
        "cotton",
        "polyester",
    ]


def test_category_url_context_returns_none_for_malformed_input() -> None:
    assert category_url_context("http://[bad") is None


def test_normalize_taxonomy_token_keeps_size_tokens_and_singularizes() -> None:
    assert normalize_taxonomy_token("s") == "s"
    assert normalize_taxonomy_token("m") == "m"
    assert normalize_taxonomy_token("l") == "l"
    assert normalize_taxonomy_token("handbags") == "bag"
    assert normalize_taxonomy_token("dresses") == "dress"


def test_taxonomy_conflict_helpers_keep_accessory_and_sport_rules_explicit() -> None:
    assert accessory_path_conflict(
        "electronics > audio > audio accessories",
        {"headphone"},
    )
    assert not accessory_path_conflict(
        "electronics > audio > audio accessories",
        {"case"},
    )
    assert toys_vs_sports_conflict("toys & games > games", {"fitness"})
    assert not toys_vs_sports_conflict("toys & games > building toys", {"toy"})
    assert sport_specific_conflict({"soccer"}, {"basketball"})
    assert special_token_conflict({"ball"}, {"basketball"})
    assert taxonomy_candidate_conflicts(
        {"fitness"},
        "Toys & Games > Games",
    )


def test_data_enrichment_llm_prompt_context_requests_semantic_fields() -> None:
    product = EnrichedProduct(
        job_id=1,
        source_url="https://example.com/products/dress",
        status=DATA_ENRICHMENT_STATUS_PENDING,
        price_normalized={"amount": 49.99, "currency": "USD"},
        color_family="blue",
        size_normalized=["M"],
        size_system="alpha",
        gender_normalized="female",
        materials_normalized=["linen"],
        availability_normalized="in_stock",
        seo_keywords=["linen", "dress"],
        category_path="Apparel & Accessories > Clothing > Dresses",
        taxonomy_version=DATA_ENRICHMENT_TAXONOMY_VERSION,
    )

    context = llm_prompt_context(
        {"title": "Linen Dress"},
        product=product,
        category_candidates=[],
    )

    assert "intent_attributes" in context["missing_backfill_fields"]
    assert "style_tags" in context["missing_backfill_fields"]
    assert "ai_discovery_tags" in context["missing_backfill_fields"]
    assert "suggested_bundles" in context["missing_backfill_fields"]


def test_normalize_price_range_rejects_trailing_noise() -> None:
    assert normalize_price(
        {"price": "$10 - $20 each"},
        source_url="https://example.com/products/widget",
    ) == {"price_min": 10.0, "price_max": 20.0, "currency": "USD"}
    noisy = normalize_price(
        {"price": "$10 - $20 random words"},
        source_url="https://example.com/products/widget",
    )
    assert noisy == {"amount": 10.0, "currency": "USD"}


def test_data_enrichment_variant_dict_values_do_not_pollute_sizes_or_availability() -> (
    None
):
    enrichment = build_deterministic_enrichment(
        {
            "title": "Cotton Shirt",
            "category": "Shirts",
            "variants": [
                {
                    "size": "medium",
                    "color": "blue",
                    "sku": "CD",
                    "image": "https://example.com/image.jpg",
                }
            ],
        },
        source_url="https://example.com/products/shirt",
    )

    assert enrichment["size_normalized"] == ["M"]
    assert enrichment["color_family"] == "blue"
    assert enrichment["availability_normalized"] is None


def test_data_enrichment_variant_fit_does_not_become_size() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "Cotton Trouser",
            "category": "Pants",
            "variants": [
                {
                    "size": "medium",
                    "fit": "regular fit",
                    "width": "wide",
                }
            ],
        },
        source_url="https://example.com/products/trouser",
    )

    assert enrichment["size_normalized"] == ["M"]


def test_data_enrichment_category_uses_primary_category_before_title_noise() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "KitchenAid 13-cup food processor",
            "brand": "KitchenAid",
            "category": "Kitchen Appliances",
        },
        source_url="https://example.com/products/food-processor",
    )

    assert (
        enrichment["category_path"]
        == "Home & Garden > Kitchen & Dining > Kitchen Appliances"
    )
    assert "Cup Sleeves" not in str(enrichment["category_path"])


def test_data_enrichment_uses_apparel_context_for_pant_set_taxonomy() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "Fashion Nova Pant Set",
            "category": "Women Pant Sets",
            "product_type": "Pant Set",
        },
        source_url="https://example.com/products/pant-set",
    )

    assert (
        enrichment["category_path"] == "Apparel & Accessories > Clothing > Outfit Sets"
    )


def test_data_enrichment_maps_apparel_breadcrumb_matching_sets_to_outfit_sets() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "Just Vibes Strapless Pant Set - Yellow",
            "category": "Women > Matching Sets",
        },
        source_url="https://www.fashionnova.com/products/just-vibes-strapless-pant-set-yellow",
    )

    assert (
        enrichment["category_path"] == "Apparel & Accessories > Clothing > Outfit Sets"
    )


def test_data_enrichment_exact_shopify_path_match_wins() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "Navy Linen Midi Dress",
            "category": "Apparel & Accessories > Clothing > Dresses",
        },
        source_url="https://example.com/products/dress",
    )

    assert enrichment["category_path"] == "Apparel & Accessories > Clothing > Dresses"
    assert enrichment["_taxonomy_match"]["source"] == "exact_path"


def test_data_enrichment_scored_match_maps_category_phrase_to_shopify_path() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "Navy Linen Midi Dress",
            "category": "Cocktail Dresses",
        },
        source_url="https://example.com/products/dress",
    )

    assert enrichment["category_path"] == "Apparel & Accessories > Clothing > Dresses"
    assert enrichment["_taxonomy_match"]["source"] == "scored_match"


def test_data_enrichment_taxonomy_keeps_apparel_shorts_out_of_lingerie() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "adidas Originals Classic Shorts",
            "gender": "Women",
            "category": "Women > Womens Clothing > Shorts",
        },
        source_url="https://example.com/products/shorts",
    )

    assert enrichment["category_path"] == "Apparel & Accessories > Clothing > Shorts"


def test_data_enrichment_taxonomy_rejects_gender_only_category_match() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "adidas Originals SL 72 PT",
            "category": "Men's",
        },
        source_url="https://example.com/products/shoe",
    )

    assert enrichment["category_path"] is None


def test_data_enrichment_taxonomy_maps_footwear_to_shopify_shoes() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "adidas Originals SL 72 PT",
            "category": "Men's > Footwear",
            "gender": "Men",
        },
        source_url="https://example.com/products/shoe",
    )

    assert enrichment["category_path"] == "Apparel & Accessories > Shoes"


def test_data_enrichment_taxonomy_maps_food_processor_product_not_accessory() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "13-Cup Food Processor",
            "brand": "KitchenAid",
            "category": "Food processors > Processors and Choppers",
            "product_type": "SDA",
            "description": (
                "Easily tackle tough chopping, shredding and kneading tasks with "
                "a powerful motor and durable blades."
            ),
        },
        source_url="https://example.com/products/food-processor",
    )

    assert (
        enrichment["category_path"]
        == "Home & Garden > Kitchen & Dining > Kitchen Appliances > Food Processors"
    )


def test_data_enrichment_taxonomy_maps_electric_kettle_from_title() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "Stagg EKG Electric Kettle",
            "brand": "Fellow",
            "category": "Fellow",
            "description": "Variable temperature control kettle for pour-over coffee.",
        },
        source_url="https://example.com/products/stagg-ekg",
    )

    assert (
        enrichment["category_path"]
        == "Home & Garden > Kitchen & Dining > Kitchen Appliances > Electric Kettles"
    )


def test_data_enrichment_taxonomy_maps_espresso_machine_to_leaf() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "Breville Bambino Plus Espresso Machine",
            "category": "Kitchen Appliances + Electrics > Coffee, Espresso & Tea > Espresso Machines",
        },
        source_url="https://example.com/products/breville-bambino-plus",
    )

    assert (
        enrichment["category_path"]
        == "Home & Garden > Kitchen & Dining > Kitchen Appliances > Coffee Makers & Espresso Machines > Espresso Machines"
    )


def test_data_enrichment_taxonomy_maps_headphone_product_not_accessory() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "AKG K-702",
            "brand": "AKG",
            "category": "Accessories > Headphones > HiFi Headphones > AKG > K-702",
            "description": (
                "High End Reference Headphones Open Circumaural full size dynamic "
                "headphones with impedance specs and included jack adapter."
            ),
        },
        source_url="https://example.com/products/akg-k702",
    )

    assert enrichment["category_path"] in {
        "Electronics > Audio > Audio Components > Headphones & Headsets",
        "Electronics > Audio > Audio Components > Headphones & Headsets > Headphones",
        "Electronics > Audio > Audio Components > Headphones & Headsets > Headphones > Over-Ear Headphones",
    }
    assert "Accessories" not in str(enrichment["category_path"])


def test_data_enrichment_taxonomy_rejects_sport_ball_toy_false_positive() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "Pressurised Padel Balls PB Speed Tri-Pack",
            "brand": "KUIKMA",
            "category": "Sports > Padel",
            "product_type": "sport",
            "description": (
                "Premium ball approved by the FIP with high speed and good "
                "resistance to friction."
            ),
        },
        source_url="https://example.com/products/padel-balls",
    )

    assert enrichment["category_path"] is None


def test_data_enrichment_taxonomy_maps_electric_guitar_from_description() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "American Vintage II 1972 Telecaster Thinline",
            "brand": "Fender",
            "description": (
                "Period-accurate pickups and hardware for a classic electric guitar."
            ),
        },
        source_url="https://example.com/products/telecaster",
    )

    assert (
        enrichment["category_path"]
        == "Arts & Entertainment > Hobbies & Creative Arts > Musical Instruments > String Instruments > Guitars > Electric Guitars"
    )


def test_data_enrichment_taxonomy_does_not_map_guitar_part_words_to_saddles() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "American Vintage II 1972 Telecaster Thinline",
            "brand": "Fender",
            "description": (
                "Semi-hollow instrument with humbucking pickups and six adjustable "
                "bridge saddles."
            ),
        },
        source_url="https://example.com/products/telecaster",
    )

    assert enrichment["category_path"] is None


def test_data_enrichment_taxonomy_uses_url_category_context_for_camera() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "alpha9 III with global shutter",
            "brand": "SONY",
            "description": "Discover the ILCE-9M3 from Sony.",
            "url": "https://www.sony.co.in/interchangeable-lens-cameras/products/ilce-9m3",
        },
        source_url="https://www.sony.co.in/interchangeable-lens-cameras/products/ilce-9m3",
    )

    assert enrichment["category_path"] in {
        "Cameras & Optics > Cameras > Digital Cameras",
        "Cameras & Optics > Cameras > Digital Cameras > Mirrorless Digital Cameras",
    }
    assert "Accessories" not in str(enrichment["category_path"])


def test_data_enrichment_taxonomy_rejects_sparse_star_wars_false_positive() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "Millennium Falcon",
            "brand": "LEGO",
            "category": "Star Wars",
            "description": "Includes classic character minifigures and a BB-8 droid figure.",
        },
        source_url="https://example.com/products/millennium-falcon",
    )

    assert enrichment["category_path"] is None


def test_data_enrichment_taxonomy_rejects_video_game_action_figure_false_positive() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "Games",
            "category": "PRAGMATA",
            "description": (
                "Learn about PRAGMATA for Nintendo Switch 2, including preorder "
                "details and Capcom's sci-fi action adventure."
            ),
        },
        source_url="https://www.nintendo.com/us/store/products/pragmata-switch-2/",
    )

    assert enrichment["category_path"] is None


def test_data_enrichment_taxonomy_maps_checked_luggage_from_description() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "Large Check-In",
            "brand": "ROAM Luggage",
            "description": (
                "The largest checked luggage in our collection, designed for "
                "week-long trips and beyond."
            ),
        },
        source_url="https://example.com/products/large-check-in",
    )

    assert enrichment["category_path"] == "Luggage & Bags > Suitcases > Checked Suitcases"


def test_data_enrichment_seo_keywords_filter_stopwords_from_all_sources() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "Navy Linen Dress",
            "brand": "Acme",
            "category": "Sale Dresses With Linen",
            "materials": "linen",
        },
        source_url="https://example.com/products/dress",
    )

    keywords = set(enrichment["seo_keywords"] or [])
    assert "sale" not in keywords
    assert "with" not in keywords
    assert "linen" in keywords


def test_data_enrichment_gender_uses_department_source() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "PUMA ESS+ Hooded Jacket",
            "department": "Womens Clothing",
        },
        source_url="https://example.com/products/jacket",
    )

    assert enrichment["gender_normalized"] == "female"


def test_data_enrichment_color_aliases_cover_common_retail_names() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "Wrap Dress",
            "category": "Dresses",
            "color": "Blush",
        },
        source_url="https://example.com/products/wrap-dress",
    )

    assert enrichment["color_family"] == "pink"


def test_data_enrichment_size_split_handles_semicolon_and_middle_dot() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "Running Shoe",
            "product_type": "Shoes",
            "size": "38; 40 · 42",
        },
        source_url="https://example.com/products/running-shoe",
    )

    assert enrichment["size_normalized"] == ["38", "40", "42"]
    assert enrichment["size_system"] == "numeric"


def test_data_enrichment_numeric_size_allowed_with_size_context() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "Runner Sneaker",
            "category": "Clearance",
            "product_type": "Footwear",
            "size": "10",
        },
        source_url="https://example.com/products/runner-sneaker",
    )

    assert enrichment["size_normalized"] == ["10"]
    assert enrichment["size_system"] == "numeric"


def test_data_enrichment_does_not_normalize_numeric_size_without_size_context() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "American Vintage II 1972 Telecaster Thinline",
            "brand": "Fender",
            "size": "14",
        },
        source_url="https://example.com/products/telecaster",
    )

    assert enrichment["size_normalized"] is None
    assert enrichment["size_system"] is None


def test_data_enrichment_does_not_normalize_non_apparel_numeric_size() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "ColourPop 24 pan eyeshadow palette",
            "category": "Beauty > Makeup > Eyeshadow",
            "size": "24",
        },
        source_url="https://example.com/products/palette",
    )

    assert enrichment["size_normalized"] is None
    assert enrichment["size_system"] is None


def test_data_enrichment_materials_ignore_care_instruction_noise() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "Linen Shirt",
            "category": "Shirts",
            "product_attributes": {"Composition": "100% linen"},
            "description": "Care: Iron warm if needed. Cotton denim leather glossary.",
        },
        source_url="https://example.com/products/shirt",
    )

    assert enrichment["materials_normalized"] == ["linen"]


def test_data_enrichment_material_percentages_survive_wash_text() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "Everyday Shirt",
            "category": "Shirts",
            "description": "Care: machine wash safe. 60% cotton 40% polyester.",
        },
        source_url="https://example.com/products/shirt",
    )

    assert enrichment["materials_normalized"] == ["cotton", "polyester"]


def test_data_enrichment_material_percentages_parse_reverse_and_percent_words() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "Everyday Shirt",
            "category": "Shirts",
            "description": "Cotton 60 percent and polyester 40%.",
        },
        source_url="https://example.com/products/shirt",
    )

    assert enrichment["materials_normalized"] == ["cotton", "polyester"]


def test_data_enrichment_price_keeps_sale_and_original_amounts() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "Sale Dress",
            "price": "$49.99",
            "sale_price": "$49.99",
            "original_price": "$79.99",
            "currency": "USD",
        },
        source_url="https://example.com/products/sale-dress",
    )

    assert enrichment["price_normalized"] == {
        "amount": 49.99,
        "sale_price": 49.99,
        "original_price": 79.99,
        "currency": "USD",
    }


def test_data_enrichment_price_uses_alternate_current_and_compare_fields() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "Sale Shoe",
            "current_price": "$59.99",
            "compare_at_price": "$89.99",
            "currency": "USD",
        },
        source_url="https://example.com/products/sale-shoe",
    )

    assert enrichment["price_normalized"] == {
        "amount": 59.99,
        "original_price": 89.99,
        "currency": "USD",
    }


def test_data_enrichment_price_infers_firstcry_currency() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "Black Seascape Stretch Bracelet",
            "price": "868.21",
            "category": "Bracelets",
        },
        source_url="https://www.firstcry.com/example/product-detail",
    )

    assert enrichment["price_normalized"] == {"amount": 868.21, "currency": "INR"}


def test_data_enrichment_seo_keywords_include_title_bigrams() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "Black Seascape Stretch Bracelet",
            "price": "868.21",
            "category": "Bracelets",
        },
        source_url="https://www.firstcry.com/example/product-detail",
    )

    assert "black seascape" in set(enrichment["seo_keywords"] or [])


def test_data_enrichment_seo_keywords_preserve_brand_phrase_and_dedupe_stems() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "Running Run Jacket",
            "brand": "Calvin Klein",
            "category": "Jackets",
        },
        source_url="https://example.com/products/run-jacket",
    )

    keywords = set(enrichment["seo_keywords"] or [])
    assert "calvin klein" in keywords
    assert not {"running", "run"} <= keywords


def test_data_enrichment_seo_keywords_keep_short_plural_identity_terms() -> None:
    enrichment = build_deterministic_enrichment(
        {
            "title": "Camera Lens Kit",
            "brand": "Sony",
            "category": "Camera Lenses",
        },
        source_url="https://example.com/products/lens-kit",
    )

    keywords = set(enrichment["seo_keywords"] or [])
    assert "lens" in keywords
    assert "len" not in keywords


@pytest.mark.asyncio
async def test_data_enrichment_rolls_back_after_sqlalchemy_product_failure(
    db_session: AsyncSession,
    create_test_run,
    test_user,
    monkeypatch,
) -> None:
    run = await create_test_run(
        url="https://example.com/products/batch",
        surface="ecommerce_detail",
    )
    bad_record = CrawlRecord(
        run_id=run.id,
        source_url="https://example.com/products/bad",
        data={"title": "Bad Shirt", "category": "Shirts"},
    )
    good_record = CrawlRecord(
        run_id=run.id,
        source_url="https://example.com/products/good",
        data={"title": "Good Shirt", "category": "Shirts"},
    )
    db_session.add_all([bad_record, good_record])
    await db_session.commit()
    await db_session.refresh(bad_record)
    await db_session.refresh(good_record)
    job = await create_data_enrichment_job(
        db_session,
        user=test_user,
        payload={"source_record_ids": [bad_record.id, good_record.id]},
    )
    calls = 0
    original_rollback = db_session.rollback
    rollbacks = 0

    async def counted_rollback() -> None:
        nonlocal rollbacks
        rollbacks += 1
        await original_rollback()

    def fake_enrich_product(session, *, job, product, record, llm_enabled):
        nonlocal calls
        del session, job, llm_enabled
        calls += 1
        if calls == 1:
            raise PendingRollbackError("flush failed earlier")
        product.category_path = "Apparel & Accessories > Clothing > Shirts"
        product.diagnostics = {"deterministic": True}

    monkeypatch.setattr(db_session, "rollback", counted_rollback)
    monkeypatch.setattr(
        "app.services.data_enrichment.service._enrich_product",
        _as_async(fake_enrich_product),
    )

    await run_job(db_session, job)
    products = list(
        (
            await db_session.scalars(
                select(EnrichedProduct)
                .where(EnrichedProduct.job_id == job.id)
                .order_by(EnrichedProduct.id)
            )
        ).all()
    )

    assert rollbacks == 1
    assert job.status == DATA_ENRICHMENT_STATUS_DEGRADED
    assert [product.status for product in products] == [
        DATA_ENRICHMENT_STATUS_FAILED,
        DATA_ENRICHMENT_STATUS_ENRICHED,
    ]


@pytest.mark.asyncio
async def test_data_enrichment_llm_enabled_backfills_missing_fields_in_one_call(
    db_session: AsyncSession,
    create_test_run,
    test_user,
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_run_prompt_task(
        session,
        *,
        task_type,
        run_id,
        domain,
        variables,
        budget_scope,
        timeout_seconds,
        config_snapshot=None,
    ):
        del session, run_id, domain, config_snapshot
        captured["task_type"] = task_type
        captured["budget_scope"] = budget_scope
        captured["timeout_seconds"] = timeout_seconds
        captured["variables"] = variables
        return LLMTaskResult(
            payload={
                "category_path": "Apparel & Accessories > Clothing > Dresses",
                "color_family": "blue",
                "size_normalized": ["Medium (M)"],
                "size_system": "alpha",
                "gender_normalized": "female",
                "materials_normalized": ["linen"],
                "availability_normalized": "in_stock",
                "intent_attributes": ["cocktail"],
                "audience": ["cocktail shoppers", "summer event guests"],
                "style_tags": ["classic"],
                "ai_discovery_tags": ["linen-dress"],
                "suggested_bundles": ["heels"],
            },
            provider="anthropic",
            model="claude",
        )

    monkeypatch.setattr(
        "app.services.data_enrichment.service.run_prompt_task",
        _as_async(fake_run_prompt_task),
    )
    run = await create_test_run(
        url="https://example.com/products/dress",
        surface="ecommerce_detail",
    )
    record = CrawlRecord(
        run_id=run.id,
        source_url="https://example.com/products/dress",
        data={"title": "Linen Dress", "category": "ZXQ Plinth"},
    )
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(record)
    job = await create_data_enrichment_job(
        db_session,
        user=test_user,
        payload={"source_record_ids": [record.id], "options": {"llm_enabled": True}},
    )

    await run_job(db_session, job)
    product = (
        await db_session.scalars(
            select(EnrichedProduct).where(EnrichedProduct.job_id == job.id)
        )
    ).one()

    assert captured["task_type"] == "data_enrichment_semantic"
    assert captured["budget_scope"] == f"data_enrichment_semantic:{job.id}"
    assert captured["timeout_seconds"] == pytest.approx(20.0)
    assert "product_json" in captured["variables"]
    prompt_product = captured["variables"]["product_json"]
    assert "intent_attributes" in prompt_product["missing_backfill_fields"]
    assert "suggested_bundles" in prompt_product["missing_backfill_fields"]
    assert product.category_path == "Apparel & Accessories > Clothing > Dresses"
    assert product.color_family == "blue"
    assert product.size_normalized == ["M"]
    assert product.size_system == "alpha"
    assert product.gender_normalized == "female"
    assert product.materials_normalized == ["linen"]
    assert product.availability_normalized == "in_stock"
    assert product.intent_attributes == ["cocktail"]
    assert product.audience == ["cocktail shoppers", "summer event guests"]
    assert product.ai_discovery_tags == ["linen-dress"]
    assert product.diagnostics["llm"]["applied_fields"]


@pytest.mark.asyncio
async def test_data_enrichment_llm_does_not_overwrite_deterministic_fields(
    db_session: AsyncSession,
    create_test_run,
    test_user,
    monkeypatch,
) -> None:
    def fake_run_prompt_task(
        session,
        *,
        task_type,
        run_id,
        domain,
        variables,
        budget_scope,
        timeout_seconds,
        config_snapshot=None,
    ):
        del (
            session,
            task_type,
            run_id,
            domain,
            variables,
            budget_scope,
            timeout_seconds,
            config_snapshot,
        )
        return LLMTaskResult(
            payload={
                "category_path": "Apparel & Accessories > Clothing > Shirts",
                "color_family": "red",
                "size_normalized": ["XL"],
                "gender_normalized": "male",
                "materials_normalized": ["wool"],
                "availability_normalized": "out_of_stock",
                "intent_attributes": ["useful"],
                "audience": ["linen dress shoppers"],
                "style_tags": ["sharp"],
                "ai_discovery_tags": ["linen-dress"],
                "suggested_bundles": ["boots"],
            }
        )

    monkeypatch.setattr(
        "app.services.data_enrichment.service.run_prompt_task",
        _as_async(fake_run_prompt_task),
    )
    run = await create_test_run(
        url="https://example.com/products/mystery",
        surface="ecommerce_detail",
    )
    record = CrawlRecord(
        run_id=run.id,
        source_url="https://example.com/products/dress",
        data={
            "title": "Linen Dress",
            "category": "Dresses",
            "color": "navy",
            "size": "medium",
            "gender": "women",
            "materials": "linen",
            "availability": "In stock",
        },
    )
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(record)
    job = await create_data_enrichment_job(
        db_session,
        user=test_user,
        payload={"source_record_ids": [record.id], "options": {"llm_enabled": True}},
    )

    await run_job(db_session, job)
    product = (
        await db_session.scalars(
            select(EnrichedProduct).where(EnrichedProduct.job_id == job.id)
        )
    ).one()

    assert product.category_path == "Apparel & Accessories > Clothing > Dresses"
    assert product.color_family == "blue"
    assert product.size_normalized == ["M"]
    assert product.gender_normalized == "female"
    assert product.materials_normalized == ["linen"]
    assert product.availability_normalized == "in_stock"
    assert product.intent_attributes == ["useful"]
    assert product.audience == ["linen dress shoppers"]
    assert product.suggested_bundles == ["boots"]


@pytest.mark.asyncio
async def test_data_enrichment_llm_audience_accepts_semantic_descriptors(
    db_session: AsyncSession,
    create_test_run,
    test_user,
    monkeypatch,
) -> None:
    def fake_run_prompt_task(
        session,
        *,
        task_type,
        run_id,
        domain,
        variables,
        budget_scope,
        timeout_seconds,
        config_snapshot=None,
    ):
        del (
            session,
            task_type,
            run_id,
            domain,
            variables,
            budget_scope,
            timeout_seconds,
            config_snapshot,
        )
        return LLMTaskResult(
            payload={
                "gender_normalized": "unisex",
                "audience": ["coastal home decorators", "guest room refreshers"],
            }
        )

    monkeypatch.setattr(
        "app.services.data_enrichment.service.run_prompt_task",
        _as_async(fake_run_prompt_task),
    )
    run = await create_test_run(
        url="https://example.com/products/duvet-cover",
        surface="ecommerce_detail",
    )
    record = CrawlRecord(
        run_id=run.id,
        source_url="https://example.com/products/duvet-cover",
        data={
            "title": "Duvet Cover",
            "category": "Duvet Covers",
            "description": "Soft bedding for daily use.",
        },
    )
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(record)
    job = await create_data_enrichment_job(
        db_session,
        user=test_user,
        payload={"source_record_ids": [record.id], "options": {"llm_enabled": True}},
    )

    await run_job(db_session, job)
    product = (
        await db_session.scalars(
            select(EnrichedProduct).where(EnrichedProduct.job_id == job.id)
        )
    ).one()

    assert product.audience == ["coastal home decorators", "guest room refreshers"]


@pytest.mark.asyncio
async def test_data_enrichment_llm_audience_preserves_semantic_target_tags(
    db_session: AsyncSession,
    create_test_run,
    test_user,
    monkeypatch,
) -> None:
    def fake_run_prompt_task(
        session,
        *,
        task_type,
        run_id,
        domain,
        variables,
        budget_scope,
        timeout_seconds,
        config_snapshot=None,
    ):
        del (
            session,
            task_type,
            run_id,
            domain,
            variables,
            budget_scope,
            timeout_seconds,
            config_snapshot,
        )
        return LLMTaskResult(
            payload={
                "category_path": "Media > Books",
                "audience": ["gift buyers", "young readers", "classroom libraries"],
            }
        )

    monkeypatch.setattr(
        "app.services.data_enrichment.service.run_prompt_task",
        _as_async(fake_run_prompt_task),
    )
    run = await create_test_run(
        url="https://example.com/products/book",
        surface="ecommerce_detail",
    )
    record = CrawlRecord(
        run_id=run.id,
        source_url="https://example.com/products/book",
        data={
            "title": "Example Book",
            "category": "Books",
            "description": "A print book.",
        },
    )
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(record)
    job = await create_data_enrichment_job(
        db_session,
        user=test_user,
        payload={"source_record_ids": [record.id], "options": {"llm_enabled": True}},
    )

    await run_job(db_session, job)
    product = (
        await db_session.scalars(
            select(EnrichedProduct).where(EnrichedProduct.job_id == job.id)
        )
    ).one()

    assert product.category_path == "Media > Books"
    assert product.audience == ["gift buyers", "young readers", "classroom libraries"]


@pytest.mark.asyncio
async def test_data_enrichment_llm_filters_ai_discovery_tags_to_allowed_evidence(
    db_session: AsyncSession,
    create_test_run,
    test_user,
    monkeypatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    def fake_run_prompt_task(
        session,
        *,
        task_type,
        run_id,
        domain,
        variables,
        budget_scope,
        timeout_seconds,
        config_snapshot=None,
    ):
        del (
            session,
            task_type,
            run_id,
            domain,
            variables,
            budget_scope,
            timeout_seconds,
            config_snapshot,
        )
        return LLMTaskResult(
            payload={
                "intent_attributes": ["summer weddings"],
                "ai_discovery_tags": ["linen-dress", "cosmic-made-up-tag"],
            }
        )

    monkeypatch.setattr(
        "app.services.data_enrichment.service.run_prompt_task",
        _as_async(fake_run_prompt_task),
    )
    run = await create_test_run(
        url="https://example.com/products/linen-dress",
        surface="ecommerce_detail",
    )
    record = CrawlRecord(
        run_id=run.id,
        source_url="https://example.com/products/linen-dress",
        data={
            "title": "Linen Dress",
            "category": "Dresses",
            "materials": "linen",
        },
    )
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(record)
    job = await create_data_enrichment_job(
        db_session,
        user=test_user,
        payload={"source_record_ids": [record.id], "options": {"llm_enabled": True}},
    )

    with caplog.at_level("WARNING"):
        await run_job(db_session, job)
    product = (
        await db_session.scalars(
            select(EnrichedProduct).where(EnrichedProduct.job_id == job.id)
        )
    ).one()

    assert product.ai_discovery_tags == ["linen-dress"]
    assert "cosmic-made-up-tag" in caplog.text


def test_ai_discovery_allowed_tags_prioritizes_source_importance() -> None:
    product = EnrichedProduct(
        seo_keywords=[f"seo-{index}" for index in range(55)],
        category_path="Apparel & Accessories > Clothing > Dresses",
        color_family="blue",
        gender_normalized="female",
        materials_normalized=["linen"],
        size_normalized=["M"],
    )

    tags = ai_discovery_allowed_tags_for_product(product)

    assert len(tags) == 50
    assert tags[:2] == ["seo-0", "seo-1"]
    assert "apparel-accessories-clothing-dresses" not in tags


@pytest.mark.asyncio
async def test_data_enrichment_llm_uses_exponential_rate_limit_retry_delay(
    db_session: AsyncSession,
    create_test_run,
    test_user,
    monkeypatch,
) -> None:
    calls = 0
    sleeps: list[float] = []
    monkeypatch.setattr(
        enrichment_service,
        "data_enrichment_settings",
        replace(
            enrichment_service.data_enrichment_settings,
            llm_rate_limit_retries=2,
            llm_rate_limit_retry_delay_seconds=3.0,
        ),
    )

    def fake_run_prompt_task(
        session,
        *,
        task_type,
        run_id,
        domain,
        variables,
        budget_scope,
        timeout_seconds,
        config_snapshot=None,
    ):
        del (
            session,
            task_type,
            run_id,
            domain,
            variables,
            budget_scope,
            timeout_seconds,
            config_snapshot,
        )
        nonlocal calls
        calls += 1
        if calls < 3:
            return LLMTaskResult(
                payload=None,
                error_message="HTTP 429: rate limited",
                error_category=LLMErrorCategory.RATE_LIMITED,
            )
        return LLMTaskResult(payload={"intent_attributes": ["travel"]})

    async def fake_sleep(_delay: float) -> None:
        if _delay:
            sleeps.append(_delay)
        return None

    monkeypatch.setattr(
        "app.services.data_enrichment.service.run_prompt_task",
        _as_async(fake_run_prompt_task),
    )
    monkeypatch.setattr("app.services.data_enrichment.service.asyncio.sleep", fake_sleep)
    run = await create_test_run(
        url="https://example.com/products/luggage",
        surface="ecommerce_detail",
    )
    record = CrawlRecord(
        run_id=run.id,
        source_url="https://example.com/products/luggage",
        data={"title": "Large Check-In"},
    )
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(record)
    job = await create_data_enrichment_job(
        db_session,
        user=test_user,
        payload={"source_record_ids": [record.id], "options": {"llm_enabled": True}},
    )

    await run_job(db_session, job)
    product = (
        await db_session.scalars(
            select(EnrichedProduct).where(EnrichedProduct.job_id == job.id)
        )
    ).one()

    assert calls == 3
    assert sleeps == [3.0, 6.0]
    assert product.intent_attributes == ["travel"]
    assert product.diagnostics["llm"]["applied"] is True


@pytest.mark.asyncio
async def test_data_enrichment_llm_semantic_lists_keep_eighty_chars(
    db_session: AsyncSession,
    create_test_run,
    test_user,
    monkeypatch,
) -> None:
    long_style = "sustainable outdoor activity wear for long weekend travel layers"
    assert 60 < len(long_style) < 80

    def fake_run_prompt_task(
        session,
        *,
        task_type,
        run_id,
        domain,
        variables,
        budget_scope,
        timeout_seconds,
        config_snapshot=None,
    ):
        del (
            session,
            task_type,
            run_id,
            domain,
            variables,
            budget_scope,
            timeout_seconds,
            config_snapshot,
        )
        return LLMTaskResult(payload={"style_tags": [long_style]})

    monkeypatch.setattr(
        "app.services.data_enrichment.service.run_prompt_task",
        _as_async(fake_run_prompt_task),
    )
    run = await create_test_run(
        url="https://example.com/products/jacket",
        surface="ecommerce_detail",
    )
    record = CrawlRecord(
        run_id=run.id,
        source_url="https://example.com/products/jacket",
        data={"title": "Trail Jacket", "category": "Jackets"},
    )
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(record)
    job = await create_data_enrichment_job(
        db_session,
        user=test_user,
        payload={"source_record_ids": [record.id], "options": {"llm_enabled": True}},
    )

    await run_job(db_session, job)
    product = (
        await db_session.scalars(
            select(EnrichedProduct).where(EnrichedProduct.job_id == job.id)
        )
    ).one()

    assert product.style_tags == [long_style]


@pytest.mark.asyncio
async def test_data_enrichment_llm_rejects_non_shopify_category_path(
    db_session: AsyncSession,
    create_test_run,
    test_user,
    monkeypatch,
) -> None:
    def fake_run_prompt_task(
        session,
        *,
        task_type,
        run_id,
        domain,
        variables,
        budget_scope,
        timeout_seconds,
        config_snapshot=None,
    ):
        del (
            session,
            task_type,
            run_id,
            domain,
            variables,
            budget_scope,
            timeout_seconds,
            config_snapshot,
        )
        return LLMTaskResult(
            payload={
                "category_path": "Hardware > Plinths",
                "intent_attributes": ["useful"],
            }
        )

    monkeypatch.setattr(
        "app.services.data_enrichment.service.run_prompt_task",
        _as_async(fake_run_prompt_task),
    )
    run = await create_test_run(
        url="https://example.com/products/mystery",
        surface="ecommerce_detail",
    )
    record = CrawlRecord(
        run_id=run.id,
        source_url="https://example.com/products/mystery",
        data={"title": "ZXQ Plinth", "category": "ZXQ Plinth"},
    )
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(record)
    job = await create_data_enrichment_job(
        db_session,
        user=test_user,
        payload={"source_record_ids": [record.id], "options": {"llm_enabled": True}},
    )

    await run_job(db_session, job)
    product = (
        await db_session.scalars(
            select(EnrichedProduct).where(EnrichedProduct.job_id == job.id)
        )
    ).one()

    assert product.category_path is None
    assert product.intent_attributes == ["useful"]
    assert "category_path" not in product.diagnostics["llm"]["applied_fields"]


@pytest.mark.asyncio
async def test_data_enrichment_llm_ignores_non_dict_payload(
    db_session: AsyncSession,
    create_test_run,
    test_user,
    monkeypatch,
) -> None:
    def fake_run_prompt_task(
        session,
        *,
        task_type,
        run_id,
        domain,
        variables,
        budget_scope,
        timeout_seconds,
        config_snapshot=None,
    ):
        del (
            session,
            task_type,
            run_id,
            domain,
            variables,
            budget_scope,
            timeout_seconds,
            config_snapshot,
        )
        return LLMTaskResult(payload="bad-payload")

    monkeypatch.setattr(
        "app.services.data_enrichment.service.run_prompt_task",
        _as_async(fake_run_prompt_task),
    )
    run = await create_test_run(
        url="https://example.com/products/dress",
        surface="ecommerce_detail",
    )
    record = CrawlRecord(
        run_id=run.id,
        source_url="https://example.com/products/dress",
        data={"title": "Linen Dress", "category": "Dresses"},
    )
    db_session.add(record)
    await db_session.commit()
    await db_session.refresh(record)
    job = await create_data_enrichment_job(
        db_session,
        user=test_user,
        payload={"source_record_ids": [record.id], "options": {"llm_enabled": True}},
    )

    await run_job(db_session, job)
    product = (
        await db_session.scalars(
            select(EnrichedProduct).where(EnrichedProduct.job_id == job.id)
        )
    ).one()

    assert product.category_path == "Apparel & Accessories > Clothing > Dresses"
    assert product.diagnostics["llm"]["applied"] is False

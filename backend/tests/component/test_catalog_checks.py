from __future__ import annotations

import pytest

from app.services.config import aid_score as config
from app.services.ucp_audit.catalog_checks import (
    build_catalog_contract,
    build_catalog_dimensions,
)
from app.services.ucp_audit.catalog_crawl import CatalogCrawlResult
from app.services.ucp_audit.evidence import build_evidence_packets
from app.services.ucp_audit.llm_rubric import RubricFinding, RubricResult, RubricVerdict


def _clean_result() -> CatalogCrawlResult:
    return CatalogCrawlResult(
        domain="example.com",
        pages_crawled=2,
        jsonld_blocks=[
            {
                "@type": "Product",
                "name": "Widget",
                "offers": {"@type": "Offer", "price": "100", "availability": "InStock"},
                "aggregateRating": {"ratingValue": "4.8", "reviewCount": "12"},
            },
            {"@type": "LocalBusiness", "name": "Example Store"},
        ],
        og_tags={"@type": "product", "price": "100"},
        product_records=[
            {
                "source_url": "https://example.com/p/1",
                "title": "Widget",
                "description": "Useful product description. " * 8,
                "price": "100",
                "image_url": "https://example.com/p.jpg",
                "variants": [{"size": "M"}],
                "sku": "SKU-1",
                "brand": "Example",
                "_dom_price": "100",
                "_page_text": "Visa Mastercard EMI delivery return",
                "_jsonld": [
                    {
                        "@type": "Product",
                        "offers": {
                            "@type": "Offer",
                            "price": "100",
                            "availability": "InStock",
                        },
                    }
                ],
            }
        ],
        robots_directives={},
        sitemap_found=True,
        sampled_urls=["https://example.com", "https://example.com/p/1"],
    )


@pytest.mark.component
def test_build_catalog_dimensions_scores_clean_catalog() -> None:
    dimensions = build_catalog_dimensions(_clean_result())
    by_id = {item.dimension_id: item for item in dimensions}

    assert set(by_id) == {
        config.D_AID1_ID,
        config.D_AID2_ID,
        config.D_AID3_ID,
        config.D_AID4_ID,
        config.D_AID5_ID,
        config.D_AID6_ID,
    }
    assert all(item.score >= 95 for item in dimensions)
    assert all(not item.findings for item in dimensions)


@pytest.mark.component
def test_missing_jsonld_applies_gate_dimension() -> None:
    result = _clean_result()
    result.jsonld_blocks = []

    aid1 = build_catalog_dimensions(result)[0]

    assert aid1.dimension_id == config.D_AID1_ID
    assert aid1.score == 0
    assert aid1.findings[0].code == config.FINDING_AID1_JSONLD_MISSING


@pytest.mark.component
def test_catalog_completeness_reports_blocking_title_and_price_gaps() -> None:
    result = _clean_result()
    result.product_records = [{"description": "short", "_page_text": ""}]

    aid2 = build_catalog_dimensions(result)[1]
    codes = {finding.code for finding in aid2.findings}

    assert config.FINDING_AID2_TITLE_MISSING in codes
    assert config.FINDING_AID2_PRICE_MISSING in codes
    assert aid2.score < 50


@pytest.mark.component
def test_catalog_completeness_uses_visible_copy_and_variant_skus() -> None:
    result = _clean_result()
    result.product_records = [
        {
            "source_url": "https://example.com/p/1",
            "title": "Widget",
            "description": "Widget",
            "price": "100",
            "image_url": "https://example.com/p.jpg",
            "variants": [{"sku": "SKU-1", "price": "100"}],
            "brand": "Example",
            "_page_text": (
                "Widget Benefits Ingredients How to Use "
                + "Detailed product evidence for buyer questions. " * 20
            ),
        }
    ]

    aid2 = build_catalog_dimensions(result)[1]
    codes = {finding.code for finding in aid2.findings}

    assert config.FINDING_AID2_DESCRIPTION_SHORT not in codes
    assert config.FINDING_AID2_IDENTIFIERS_MISSING not in codes


@pytest.mark.component
def test_single_variant_or_no_variant_products_do_not_create_variant_gap() -> None:
    result = _clean_result()
    result.product_records = [
        {
            "source_url": "https://example.com/p/1",
            "title": "Widget",
            "description": "Useful product description. " * 8,
            "price": "100",
            "image_url": "https://example.com/p.jpg",
            "sku": "SKU-1",
            "brand": "Example",
        }
    ]

    aid2 = build_catalog_dimensions(result)[1]
    codes = {finding.code for finding in aid2.findings}

    assert config.FINDING_AID2_VARIANTS_MISSING not in codes


@pytest.mark.component
def test_offer_availability_and_discovery_findings() -> None:
    result = _clean_result()
    result.jsonld_blocks = [{"@type": "Product", "offers": {"price": "100"}}]
    result.product_records[0]["_jsonld"] = result.jsonld_blocks
    result.robots_directives = {"gptbot": ["/"]}
    result.sitemap_found = False

    dimensions = build_catalog_dimensions(result)
    codes = {finding.code for dimension in dimensions for finding in dimension.findings}

    assert config.FINDING_AID4_AVAILABILITY_MISSING in codes
    assert config.FINDING_AID6_ROBOTS_BLOCKING_AI in codes
    assert config.FINDING_AID6_SITEMAP_MISSING in codes


@pytest.mark.component
def test_visible_record_rating_counts_as_trust_signal() -> None:
    result = _clean_result()
    result.jsonld_blocks = [{"@type": "Product", "offers": {"price": "100", "availability": "InStock"}}]
    result.product_records[0]["rating"] = 4.7
    result.product_records[0]["review_count"] = 28

    aid5 = build_catalog_dimensions(result)[4]

    assert aid5.score == 100
    assert aid5.findings == []


@pytest.mark.component
def test_build_catalog_contract_summarizes_crawl_result() -> None:
    result = _clean_result()
    packets = build_evidence_packets(result)
    contract = build_catalog_contract(result, evidence_packets=packets)

    assert contract["catalog"]["pages_crawled"] == 2
    assert contract["structured_markup"]["product_jsonld_count"] == 1
    assert contract["discovery"]["sitemap_found"] is True
    assert contract["ai_assessment"]["enabled"] is False


@pytest.mark.component
def test_high_confidence_llm_variant_findings_reduce_dimension_scores() -> None:
    llm_results = [
        RubricResult(
            url="https://example.com/p/1",
            findings=[
                RubricFinding(
                    dimension="variant_inferability",
                    verdict=RubricVerdict.FAIL,
                    evidence_quote="variants array contains unrelated products instead of this product's sizes",
                    finding_code=config.FINDING_AID_LLM_VARIANTS_UNRESOLVABLE,
                    recommendation="Remove unrelated product variants.",
                )
            ],
        )
    ]

    dimensions = build_catalog_dimensions(_clean_result(), llm_results=llm_results)
    aid2 = {item.dimension_id: item for item in dimensions}[config.D_AID2_ID]

    assert aid2.score < 100
    assert aid2.findings[-1].code == config.FINDING_AID_LLM_VARIANTS_UNRESOLVABLE
    assert aid2.findings[-1].severity == config.AID_FINDING_WARNING
    assert aid2.findings[-1].evidence == [
        {
            "quote": "variants array contains unrelated products instead of this product's sizes",
            "url": "https://example.com/p/1",
        }
    ]


@pytest.mark.component
def test_uncertain_or_subjective_llm_findings_are_excluded_from_scored_report() -> None:
    llm_results = [
        RubricResult(
            url="https://example.com/p/1",
            findings=[
                RubricFinding(
                    dimension="description_quality",
                    verdict=RubricVerdict.FAIL,
                    evidence_quote="Some lightweight advisory.",
                    finding_code=config.FINDING_AID_LLM_DESCRIPTION_FLUFF,
                    recommendation="Consider adding more detail.",
                ),
                RubricFinding(
                    dimension="description_quality",
                    verdict=RubricVerdict.PARTIAL,
                    evidence_quote="Some lightweight advisory.",
                    finding_code=config.FINDING_AID_LLM_DESCRIPTION_FLUFF,
                    recommendation="Consider adding more detail.",
                )
            ],
        )
    ]

    dimensions = build_catalog_dimensions(_clean_result(), llm_results=llm_results)
    aid2 = {item.dimension_id: item for item in dimensions}[config.D_AID2_ID]

    assert aid2.score == 100
    assert aid2.findings == []

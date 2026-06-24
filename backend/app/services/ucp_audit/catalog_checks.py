from __future__ import annotations

import re
from typing import Any

from app.services.config import aid_score as config
from app.services.ucp_audit.catalog_crawl import CatalogCrawlResult
from app.services.ucp_audit.evidence import EvidencePacket
from app.services.ucp_audit.llm_rubric import RubricResult, RubricVerdict
from app.services.ucp_audit.types import UCPDimensionScore, UCPFinding


def build_catalog_contract(
    result: CatalogCrawlResult,
    *,
    evidence_packets: list[EvidencePacket] | None = None,
    llm_results: list[RubricResult] | None = None,
) -> dict[str, Any]:
    return {
        "catalog": {
            "domain": result.domain,
            "pages_crawled": result.pages_crawled,
            "sampled_urls": result.sampled_urls,
            "crawl_errors": result.crawl_errors,
        },
        "structured_markup": {
            "product_jsonld_count": len(_product_blocks(result)),
            "jsonld_block_count": len(result.jsonld_blocks),
            "jsonld_parse_errors": result.jsonld_parse_errors,
            "open_graph": result.og_tags,
        },
        "product_records": [
            _public_record_summary(record) for record in result.product_records
        ],
        "discovery": {
            "robots_directives": result.robots_directives,
            "sitemap_found": result.sitemap_found,
        },
        "ai_assessment": {
            "enabled": bool(llm_results),
            "results": [item.to_contract() for item in llm_results or []],
            "contradictions": [
                {
                    "url": packet.url,
                    "flags": [
                        {
                            "field": flag.field,
                            "source_a": flag.source_a,
                            "value_a": flag.value_a,
                            "source_b": flag.source_b,
                            "value_b": flag.value_b,
                        }
                        for flag in packet.contradictions
                    ],
                }
                for packet in evidence_packets or []
                if packet.contradictions
            ],
        },
    }


def build_catalog_dimensions(
    result: CatalogCrawlResult,
    *,
    llm_results: list[RubricResult] | None = None,
) -> list[UCPDimensionScore]:
    dimensions = [
        _markup_dimension(result),
        _completeness_dimension(result),
        _commerce_dimension(result),
        _freshness_dimension(result),
        _trust_dimension(result),
        _local_dimension(result),
    ]
    if llm_results:
        _apply_llm_findings(dimensions, llm_results)
    return dimensions


def _apply_llm_findings(
    dimensions: list[UCPDimensionScore],
    llm_results: list[RubricResult],
) -> None:
    by_id = {dimension.dimension_id: dimension for dimension in dimensions}
    for result in llm_results:
        for finding in result.findings:
            if finding.verdict != RubricVerdict.FAIL:
                continue
            if not _is_high_confidence_llm_finding(finding):
                continue
            dimension_id = config.AID_LLM_DIMENSION_TO_AID.get(finding.dimension)
            if not dimension_id or dimension_id not in by_id:
                continue
            severity = _llm_severity(finding)
            target = by_id[dimension_id]
            target.findings.append(
                _finding(
                    finding.finding_code,
                    dimension_id,
                    severity,
                    finding.recommendation,
                    evidence=[{"quote": finding.evidence_quote, "url": result.url}],
                )
            )
            target.score = max(
                0,
                target.score - config.AID_LLM_FAIL_PENALTY,
            )
            target.status = _status_for(target.score, target.findings)


def _is_high_confidence_llm_finding(finding: Any) -> bool:
    if finding.dimension != "variant_inferability":
        return False
    if finding.finding_code != config.FINDING_AID_LLM_VARIANTS_UNRESOLVABLE:
        return False
    evidence = f"{finding.evidence_quote} {finding.recommendation}".lower()
    return any(
        token in evidence
        for token in (
            "unrelated",
            "wrong product",
            "different product",
            "instead of",
            "does not belong",
        )
    )


def _llm_severity(finding: Any) -> str:
    if finding.verdict == RubricVerdict.FAIL and finding.dimension in config.AID_LLM_BLOCKING_DIMENSIONS:
        return config.AID_FINDING_BLOCKING
    if finding.verdict == RubricVerdict.FAIL:
        return config.AID_FINDING_WARNING
    return config.AID_FINDING_INFO


def _markup_dimension(result: CatalogCrawlResult) -> UCPDimensionScore:
    findings: list[UCPFinding] = []
    product_blocks = _product_blocks(result)
    if not result.jsonld_blocks:
        findings.append(
            _finding(
                config.FINDING_AID1_JSONLD_MISSING,
                config.D_AID1_ID,
                config.AID_FINDING_BLOCKING,
                "No JSON-LD structured data was detected on sampled product pages.",
            )
        )
        return _dimension(config.D_AID1_ID, 0, findings)
    if not product_blocks:
        findings.append(
            _finding(
                config.FINDING_AID1_PRODUCT_TYPE_MISSING,
                config.D_AID1_ID,
                config.AID_FINDING_BLOCKING,
                "JSON-LD is present, but no schema.org Product node was detected.",
            )
        )
    if not _has_product_og(result):
        findings.append(
            _finding(
                config.FINDING_AID1_OPEN_GRAPH_MISSING,
                config.D_AID1_ID,
                config.AID_FINDING_WARNING,
                "No Open Graph product signal was detected.",
            )
        )
    if result.jsonld_parse_errors:
        findings.append(
            _finding(
                config.FINDING_AID1_SCHEMA_INVALID,
                config.D_AID1_ID,
                config.AID_FINDING_WARNING,
                "One or more JSON-LD blocks could not be parsed.",
                affected_count=len(result.jsonld_parse_errors),
                evidence=[{"errors": result.jsonld_parse_errors[:5]}],
            )
        )
    score = 100
    if not product_blocks:
        score = 0
    elif not _has_product_og(result):
        score -= 15
    if product_blocks and result.jsonld_parse_errors:
        score -= 10
    return _dimension(config.D_AID1_ID, score, findings)


def _completeness_dimension(result: CatalogCrawlResult) -> UCPDimensionScore:
    fields = ("title", "description", "price", "images", "identifiers", "brand")
    records = result.product_records or [{}]
    present = 0
    findings: list[UCPFinding] = []
    missing_by_field = {field: 0 for field in fields}
    urls_by_field: dict[str, list[str]] = {field: [] for field in fields}
    for record in records:
        checks = {
            "title": _has_any(record, "title", "name"),
            "description": _has_description_evidence(record),
            "price": _has_any(record, "price", "sale_price", "current_price"),
            "images": _has_images(record),
            "identifiers": _has_identifiers(record),
            "brand": _has_any(record, "brand"),
        }
        for field, ok in checks.items():
            if ok:
                present += 1
            else:
                missing_by_field[field] += 1
                url = _text(record.get("source_url") or record.get("url"))
                if url:
                    urls_by_field[field].append(url)
    total = len(records) * len(fields)
    if missing_by_field["title"]:
        findings.append(_count_finding(config.FINDING_AID2_TITLE_MISSING, config.D_AID2_ID, config.AID_FINDING_BLOCKING, missing_by_field["title"], "Product title is missing on sampled pages.", affected_urls=urls_by_field["title"]))
    if missing_by_field["price"]:
        findings.append(_count_finding(config.FINDING_AID2_PRICE_MISSING, config.D_AID2_ID, config.AID_FINDING_BLOCKING, missing_by_field["price"], "Product price is missing on sampled pages.", affected_urls=urls_by_field["price"]))
    if missing_by_field["description"]:
        findings.append(_count_finding(config.FINDING_AID2_DESCRIPTION_SHORT, config.D_AID2_ID, config.AID_FINDING_WARNING, missing_by_field["description"], "Product description is missing or under 100 characters.", affected_urls=urls_by_field["description"]))
    if missing_by_field["images"]:
        findings.append(_count_finding(config.FINDING_AID2_IMAGES_MISSING, config.D_AID2_ID, config.AID_FINDING_WARNING, missing_by_field["images"], "Product images are missing.", affected_urls=urls_by_field["images"]))
    if missing_by_field["identifiers"]:
        findings.append(_count_finding(config.FINDING_AID2_IDENTIFIERS_MISSING, config.D_AID2_ID, config.AID_FINDING_WARNING, missing_by_field["identifiers"], "SKU, GTIN, or MPN is missing.", affected_urls=urls_by_field["identifiers"]))
    return _dimension(config.D_AID2_ID, round((present / total) * 100) if total else 0, findings)


def _commerce_dimension(result: CatalogCrawlResult) -> UCPDimensionScore:
    findings: list[UCPFinding] = []
    score = 100
    if not any(_offers(block) for block in _product_blocks(result)):
        findings.append(_finding(config.FINDING_AID3_OFFER_MISSING, config.D_AID3_ID, config.AID_FINDING_BLOCKING, "No schema.org Offer block was detected."))
        score -= 40
    return _dimension(config.D_AID3_ID, score, findings)


def _freshness_dimension(result: CatalogCrawlResult) -> UCPDimensionScore:
    findings: list[UCPFinding] = []
    score = 100
    product_blocks = _product_blocks(result)
    if not any(_availability(block) for block in product_blocks):
        findings.append(_finding(config.FINDING_AID4_AVAILABILITY_MISSING, config.D_AID4_ID, config.AID_FINDING_BLOCKING, "No schema.org availability signal was detected."))
        score -= 40
    return _dimension(config.D_AID4_ID, score, findings)


def _trust_dimension(result: CatalogCrawlResult) -> UCPDimensionScore:
    findings: list[UCPFinding] = []
    ratings = [_rating(block) for block in _product_blocks(result)]
    ratings = [item for item in ratings if item]
    record_rating_count = sum(1 for record in result.product_records if _record_has_rating(record))
    score = 100
    if not ratings and not record_rating_count:
        findings.append(_finding(config.FINDING_AID5_RATING_MISSING, config.D_AID5_ID, config.AID_FINDING_WARNING, "No aggregateRating was detected in structured data."))
        score = 70
    elif any(_review_count(item) == 0 for item in ratings):
        findings.append(_finding(config.FINDING_AID5_REVIEW_COUNT_ZERO, config.D_AID5_ID, config.AID_FINDING_WARNING, "Rating is present but review count is zero."))
        score -= 15
    if any(_review_invalid(block) for block in _product_blocks(result)):
        findings.append(_finding(config.FINDING_AID5_REVIEW_SCHEMA_INVALID, config.D_AID5_ID, config.AID_FINDING_INFO, "Review markup is malformed."))
        score -= 5
    return _dimension(config.D_AID5_ID, score, findings)


def _local_dimension(result: CatalogCrawlResult) -> UCPDimensionScore:
    findings: list[UCPFinding] = []
    score = 100
    blocked_agents = _blocked_ai_agents(result.robots_directives)
    if blocked_agents:
        findings.append(_finding(config.FINDING_AID6_ROBOTS_BLOCKING_AI, config.D_AID6_ID, config.AID_FINDING_WARNING, "robots.txt blocks one or more AI crawlers.", evidence=[{"blocked_agents": blocked_agents}]))
        score -= 20
    if not result.sitemap_found:
        findings.append(_finding(config.FINDING_AID6_SITEMAP_MISSING, config.D_AID6_ID, config.AID_FINDING_INFO, "No sitemap.xml was detected."))
        score -= 5
    return _dimension(config.D_AID6_ID, score, findings)


def _dimension(dimension_id: str, score: int, findings: list[UCPFinding]) -> UCPDimensionScore:
    bounded = max(0, min(100, int(score)))
    return UCPDimensionScore(
        dimension_id=dimension_id,
        score=bounded,
        status=_status_for(bounded, findings),
        findings=findings,
        weight=config.DIMENSION_WEIGHTS[dimension_id],
    )


def _status_for(score: int, findings: list[UCPFinding]) -> str:
    if any(finding.severity == config.AID_FINDING_BLOCKING for finding in findings):
        return config.AID_STATUS_FAIL if score == 0 else config.AID_STATUS_WARNING
    if findings:
        return config.AID_STATUS_WARNING
    return config.AID_STATUS_PASS


def _finding(
    code: str,
    dimension_id: str,
    severity: str,
    message: str,
    *,
    affected_count: int = 0,
    evidence: list[dict[str, Any]] | None = None,
) -> UCPFinding:
    return UCPFinding(
        code=code,
        dimension_id=dimension_id,
        severity=severity,
        message=message,
        affected_count=affected_count,
        evidence=list(evidence or []),
    )


def _count_finding(
    code: str,
    dimension_id: str,
    severity: str,
    count: int,
    message: str,
    *,
    affected_urls: list[str] | None = None,
) -> UCPFinding:
    finding = _finding(code, dimension_id, severity, message, affected_count=count)
    finding.affected_urls = list(dict.fromkeys(affected_urls or []))
    if finding.affected_urls:
        finding.evidence.append({"affected_urls": finding.affected_urls[:5]})
    return finding


def _product_blocks(result: CatalogCrawlResult) -> list[dict[str, Any]]:
    return [block for block in result.jsonld_blocks if _type_matches(block, "product")]


def _type_matches(block: dict[str, Any], expected: str) -> bool:
    raw = block.get("@type") or block.get("type")
    values = raw if isinstance(raw, list) else [raw]
    return any(str(value or "").strip().lower().endswith(expected.lower()) for value in values)


def _has_product_og(result: CatalogCrawlResult) -> bool:
    text = " ".join(f"{key} {value}" for key, value in result.og_tags.items()).lower()
    return "product" in text or "price" in text


def _public_record_summary(record: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in record.items()
        if not key.startswith("_") and value not in (None, "", [], {})
    }


def _has_any(record: dict[str, Any], *keys: str) -> bool:
    return any(record.get(key) not in (None, "", [], {}) for key in keys)


def _has_images(record: dict[str, Any]) -> bool:
    return _has_any(record, "image", "image_url", "primary_image", "images") or bool(record.get("additional_images"))


def _has_description_evidence(record: dict[str, Any]) -> bool:
    if len(_text(record.get("description"))) >= config.AID_DESCRIPTION_MIN_CHARS:
        return True
    page_text = _text(record.get("_page_text"))
    if len(page_text) < config.AID_VISIBLE_DESCRIPTION_MIN_CHARS:
        return False
    title = _text(record.get("title") or record.get("name")).lower()
    page_lower = page_text.lower()
    if title and title not in page_lower:
        return False
    return any(term in page_lower for term in config.AID_VISIBLE_DESCRIPTION_SIGNAL_TERMS)


def _has_identifiers(record: dict[str, Any]) -> bool:
    if _has_any(record, "sku", "gtin", "mpn", "product_id", "productId"):
        return True
    variants = record.get("variants")
    if not isinstance(variants, list):
        return False
    return any(
        isinstance(variant, dict)
        and _has_any(variant, "sku", "gtin", "mpn", "product_id", "productId")
        for variant in variants
    )


def _text(value: object) -> str:
    if isinstance(value, list):
        return " ".join(_text(item) for item in value)
    if isinstance(value, dict):
        return " ".join(_text(item) for item in value.values())
    return str(value or "").strip()


def _offers(block: dict[str, Any]) -> list[dict[str, Any]]:
    offers = block.get("offers") or block.get("Offers")
    if isinstance(offers, dict):
        return [offers]
    if isinstance(offers, list):
        return [item for item in offers if isinstance(item, dict)]
    return []


def _availability(block: dict[str, Any]) -> str:
    for offer in _offers(block):
        value = _text(offer.get("availability"))
        if value:
            return value
    return _text(block.get("availability"))


def _rating(block: dict[str, Any]) -> dict[str, Any]:
    rating = block.get("aggregateRating") or block.get("aggregate_rating")
    return rating if isinstance(rating, dict) else {}


def _review_count(rating: dict[str, Any]) -> int:
    value = _number(rating.get("reviewCount") or rating.get("ratingCount"))
    return int(value or 0)


def _record_has_rating(record: dict[str, Any]) -> bool:
    return _number(record.get("rating") or record.get("rating_value")) is not None or _number(
        record.get("review_count") or record.get("rating_count")
    ) is not None


def _review_invalid(block: dict[str, Any]) -> bool:
    review = block.get("review")
    return isinstance(review, dict) and not (review.get("author") and review.get("reviewRating"))


def _blocked_ai_agents(directives: dict[str, list[str]]) -> list[str]:
    blocked: list[str] = []
    for agent in ("gptbot", "perplexitybot"):
        disallows = [str(item).strip() for item in directives.get(agent, [])]
        if "/" in disallows:
            blocked.append(agent)
    return blocked


def _number(value: object) -> float | None:
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"\d+(?:[,.]\d+)?", _text(value).replace(",", ""))
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None

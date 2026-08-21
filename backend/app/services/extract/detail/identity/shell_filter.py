from __future__ import annotations

__all__ = (
    "looks_like_site_shell_record",
    "detail_url_has_multiple_product_segments",
    "detail_image_looks_like_tracking_or_shell",
    "title_looks_like_brand_shell",
    "description_looks_like_shell_copy",
)

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

from app.services.config.extraction_rules import (
    AVAILABILITY_UNKNOWN,
    DETAIL_BRAND_SHELL_DESCRIPTION_PHRASES,
    DETAIL_BRAND_SHELL_TITLE_TOKENS,
    TRACKING_PIXEL_PATTERNS,
)
from app.services.extract.detail.identity.core import (
    detail_url_is_collection_like,
    detail_url_is_utility,
)
from app.services.extract.detail.assembly.record_sanitization import (
    detail_title_looks_like_placeholder,
)
from app.services.extract.detail.assembly.title_scorer import (
    title_needs_promotion,
)
from app.services.shared.field_coerce import (
    clean_text,
    is_title_noise,
    object_dict,
    object_list,
    text_or_none,
)

_ALNUM_SPLIT_PATTERN = r"[^a-z0-9]+"


def _present(
    record: dict[str, Any], fields: tuple[str, ...], *, ignore_brand: bool = False
) -> bool:
    return any(
        record.get(field) not in (None, "", [], {})
        for field in fields
        if field != "brand" or not ignore_brand
    )


@dataclass(frozen=True)
class _ShellEvidence:
    record: dict[str, Any]
    page_url: str
    title: str
    title_sources: set[str]
    confidence: float
    generic: bool
    strong: bool
    identity: bool
    rich_pdp: bool


def _shell_evidence(record: dict[str, Any], page_url: str) -> _ShellEvidence:
    fields = object_dict(record.get("_field_sources"))
    title_sources = {
        str(source).strip()
        for source in object_list(fields.get("title"))
        if str(source).strip()
    }
    brand_sources = {
        str(source).strip()
        for source in object_list(fields.get("brand"))
        if str(source).strip()
    }
    ignore_brand = bool(record.get("brand")) and brand_sources == {"identity_repair"}
    generic = _present(
        record, ("price", "currency", "brand", "category"), ignore_brand=ignore_brand
    )
    strong = _present(
        record,
        ("brand", "sku", "part_number", "barcode", "variants"),
        ignore_brand=ignore_brand,
    )
    availability = text_or_none(record.get("availability"))
    strong = strong or bool(availability and availability != AVAILABILITY_UNKNOWN)
    identity = _present(
        record,
        (
            "price",
            "original_price",
            "currency",
            "brand",
            "sku",
            "part_number",
            "barcode",
            "description",
            "image_url",
            "availability",
        ),
        ignore_brand=ignore_brand,
    )
    confidence_payload = record.get("_confidence")
    score = (
        confidence_payload.get("score")
        if isinstance(confidence_payload, dict)
        else None
    )
    confidence = float(score) if isinstance(score, (int, float, str)) else 0.0
    description = clean_text(record.get("description"))
    rich_pdp = (
        all(
            record.get(field) not in (None, "", [], {})
            for field in ("price", "image_url")
        )
        and len(description) >= 160
    )
    return _ShellEvidence(
        record=record,
        page_url=page_url,
        title=text_or_none(record.get("title")) or "",
        title_sources=title_sources,
        confidence=confidence,
        generic=generic,
        strong=strong,
        identity=identity,
        rich_pdp=rich_pdp,
    )


def _weak_irrelevant_dom_title(evidence: _ShellEvidence) -> bool:
    public_payload = any(
        value not in (None, "", [], {})
        for key, value in evidence.record.items()
        if not str(key).startswith("_") and key not in {"source_url", "url", "title"}
    )
    return all(
        (
            evidence.confidence < 0.2,
            bool(evidence.record.get("_irrelevant_detail_structured_product")),
            evidence.title_sources == {"dom_h1"},
            not public_payload,
            not evidence.generic,
            not evidence.strong,
            not evidence.identity,
        )
    )


def _weak_slug_or_shell_copy(evidence: _ShellEvidence) -> bool:
    shell_copy = description_looks_like_shell_copy(evidence.record.get("description"))
    weak_slug = (
        evidence.confidence < 0.5
        and not evidence.strong
        and "url_slug" in evidence.title_sources
        and not evidence.rich_pdp
    )
    weak_copy = (
        evidence.confidence < 0.5
        and shell_copy
        and not evidence.generic
        and not evidence.strong
    )
    shell_title = title_looks_like_brand_shell(
        evidence.title, page_url=evidence.page_url
    )
    commerce = _present(
        evidence.record, ("price", "original_price", "currency", "brand", "variants")
    )
    availability = text_or_none(evidence.record.get("availability"))
    weak_brand_shell = (
        evidence.confidence < 0.5
        and shell_copy
        and shell_title
        and not commerce
        and availability in (None, AVAILABILITY_UNKNOWN)
    )
    return weak_slug or weak_copy or weak_brand_shell


def _placeholder_or_low_source(evidence: _ShellEvidence) -> bool:
    placeholder = detail_title_looks_like_placeholder(evidence.title)
    placeholder_support = _present(
        evidence.record,
        (
            "price",
            "original_price",
            "image_url",
            "sku",
            "part_number",
            "barcode",
            "brand",
        ),
    )
    low_source = str(evidence.record.get("_source") or "").strip() in {
        "opengraph",
        "json_ld_page_level",
        "microdata",
    }
    unsupported_slug = (
        "url_slug" in evidence.title_sources
        and evidence.confidence < 0.5
        and low_source
        and not evidence.strong
    )
    return (
        (placeholder and not placeholder_support)
        or unsupported_slug
        or (placeholder and not evidence.generic and not evidence.strong)
    )


def _usable_title_is_shell(evidence: _ShellEvidence) -> bool:
    shell_title = title_looks_like_brand_shell(
        evidence.title, page_url=evidence.page_url
    )
    weak_description = (
        description_looks_like_shell_copy(evidence.record.get("description"))
        or detail_image_looks_like_tracking_or_shell(evidence.record.get("image_url"))
        or len(clean_text(evidence.record.get("description"))) <= 120
    )
    if (
        shell_title
        and not evidence.generic
        and not evidence.strong
        and weak_description
    ):
        return True
    if not detail_url_is_utility(evidence.page_url):
        return False
    record_url = text_or_none(evidence.record.get("url")) or ""
    return not evidence.strong or detail_url_is_utility(record_url)


def _weak_identity_rejected(evidence: _ShellEvidence) -> bool:
    if any(
        predicate(evidence)
        for predicate in (
            _weak_irrelevant_dom_title,
            _weak_slug_or_shell_copy,
            _placeholder_or_low_source,
        )
    ):
        return True
    return all(
        (
            evidence.confidence < 0.4,
            "url_slug" in evidence.title_sources,
            evidence.strong,
            not evidence.identity,
        )
    )


def looks_like_site_shell_record(record: dict[str, Any], *, page_url: str) -> bool:
    evidence = _shell_evidence(record, page_url)
    if any(
        (
            detail_url_has_multiple_product_segments(page_url),
            is_title_noise(evidence.title),
            detail_url_is_collection_like(page_url),
        )
    ):
        return True
    if _weak_identity_rejected(evidence):
        return True
    if (
        evidence.rich_pdp
        and "url_slug" not in evidence.title_sources
        and not detail_url_is_utility(page_url)
    ):
        return False
    if not title_needs_promotion(evidence.title, page_url=page_url):
        return _usable_title_is_shell(evidence)
    if str(record.get("_source") or "").strip() in {
        "adapter",
        "network_payload",
        "json_ld",
        "microdata",
        "embedded_json",
        "js_state",
    }:
        return False
    if (
        title_looks_like_brand_shell(evidence.title, page_url=page_url)
        and not evidence.generic
        and description_looks_like_shell_copy(record.get("description"))
    ):
        return True
    return not evidence.strong


def detail_url_has_multiple_product_segments(url: str) -> bool:
    path = str(urlparse(url).path or "").lower()
    return any(path.count(segment) > 1 for segment in ("/prd/", "/dp/", "/products/"))


def detail_image_looks_like_tracking_or_shell(value: object) -> bool:
    image_url = text_or_none(value)
    if not image_url:
        return False
    lowered = image_url.lower()
    return any(token in lowered for token in tuple(TRACKING_PIXEL_PATTERNS or ()))


def title_looks_like_brand_shell(title: str, *, page_url: str) -> bool:
    normalized_title = str(title or "").strip().lower()
    if not normalized_title:
        return False
    host = str(urlparse(page_url).hostname or "").strip().lower()
    host_label = host.removeprefix("www.").split(".", 1)[0]
    if _title_matches_compact_host(normalized_title, host_label):
        return True
    host_tokens = {
        token for token in re.split(_ALNUM_SPLIT_PATTERN, host_label) if len(token) >= 3
    }
    if not host_tokens:
        return False
    title_tokens = {
        token
        for token in re.split(_ALNUM_SPLIT_PATTERN, normalized_title)
        if len(token) >= 3
    }
    if not title_tokens or not (title_tokens & host_tokens):
        return False
    extra_tokens = title_tokens - host_tokens
    return bool(extra_tokens) and (
        extra_tokens <= set(DETAIL_BRAND_SHELL_TITLE_TOKENS)
        or (len(extra_tokens) <= 3 and len(title_tokens) <= 5)
    )


def _title_matches_compact_host(title: str, host_label: str) -> bool:
    compact_title = re.sub(_ALNUM_SPLIT_PATTERN, "", title)
    compact_host = re.sub(_ALNUM_SPLIT_PATTERN, "", host_label)
    return bool(compact_title and compact_host and compact_title == compact_host)


def description_looks_like_shell_copy(description: object) -> bool:
    normalized_description = str(text_or_none(description) or "").strip().lower()
    if not normalized_description:
        return False
    return any(
        phrase in normalized_description
        for phrase in DETAIL_BRAND_SHELL_DESCRIPTION_PHRASES
    )

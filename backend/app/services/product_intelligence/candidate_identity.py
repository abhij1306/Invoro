from __future__ import annotations

import re
from typing import Protocol

from app.services.config.product_intelligence import (
    DISCOVERY_GENERIC_PRODUCT_TOKENS,
    DISCOVERY_TITLE_MISMATCH_MIN_DISTINCTIVE_TOKENS,
    DISCOVERY_TITLE_MISMATCH_MIN_OVERLAP_RATIO,
)
from app.services.product_intelligence.candidate_urls import (
    looks_like_product_detail_url,
    normalized_compare_url,
)
from app.services.product_intelligence.matching import (
    manufacturer_style_code,
    normalize_brand,
    source_domain,
)


class RankedCandidate(Protocol):
    url: str
    payload: dict[str, object] | None


def candidate_matches_product(
    product: dict[str, object], url: str, payload: dict[str, object] | None
) -> bool:
    if not looks_like_product_detail_url(url):
        return False
    result_text = search_result_text(payload)
    candidate_text = " ".join(part for part in (result_text, url) if part)
    if identity_token_match(product, candidate_text):
        return True
    if has_conflicting_numeric_identity(product, result_text):
        return False
    return not title_mismatch(product, result_text or url)


def search_result_text(payload: dict[str, object] | None) -> str:
    data = payload if isinstance(payload, dict) else {}
    raw_value = data.get("raw")
    raw = raw_value if isinstance(raw_value, dict) else {}
    values = [
        data.get("title"),
        data.get("snippet"),
        data.get("source"),
        raw.get("title"),
        raw.get("snippet"),
        raw.get("displayed_link"),
        raw.get("source"),
    ]
    return " ".join(str(value or "") for value in values).strip()


def identity_token_match(product: dict[str, object], candidate_text: object) -> bool:
    source_tokens = identity_tokens(
        product.get("title"),
        product.get("sku"),
        product.get("mpn"),
        product.get("gtin"),
    )
    source_tokens |= style_code_tokens(
        product.get("style_code"),
        manufacturer_style_code(
            product.get("sku"),
            product.get("style"),
            product.get("mpn"),
            gtin_value=product.get("gtin"),
        ),
    )
    if not source_tokens:
        return False
    candidate_tokens = identity_tokens(candidate_text)
    candidate_tokens |= style_code_tokens(manufacturer_style_code(candidate_text))
    return bool(source_tokens & candidate_tokens)


def style_code_tokens(*values: object) -> set[str]:
    return {
        token
        for value in values
        for token in str(value or "").casefold().split()
        if token
    }


def has_conflicting_numeric_identity(
    product: dict[str, object], candidate_text: object
) -> bool:
    source_tokens = identity_tokens(
        product.get("title"),
        product.get("sku"),
        product.get("mpn"),
        product.get("gtin"),
    )
    candidate_tokens = identity_tokens(candidate_text)
    return bool(
        source_tokens and candidate_tokens and not source_tokens & candidate_tokens
    )


def identity_tokens(*values: object) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        raw = str(value or "").casefold()
        parts = [token for token in re.split(r"[^a-z0-9]+", raw) if token]
        compact = re.sub(r"[^a-z0-9]+", "", raw)
        if (
            1 < len(parts) <= 3
            and len(compact) >= 5
            and any(char.isdigit() for char in compact)
        ):
            tokens.add(compact)
        tokens.update(
            token
            for token in parts
            if len(token) >= 3 and any(char.isdigit() for char in token)
        )
    return tokens


def title_mismatch(product: dict[str, object], candidate_text: object) -> bool:
    source_tokens = distinctive_title_tokens(product.get("title"), product.get("brand"))
    candidate_tokens = distinctive_title_tokens(candidate_text, product.get("brand"))
    minimum = int(DISCOVERY_TITLE_MISMATCH_MIN_DISTINCTIVE_TOKENS)
    if len(source_tokens) < minimum or len(candidate_tokens) < minimum:
        return False
    overlap = len(source_tokens & candidate_tokens) / max(
        min(len(source_tokens), len(candidate_tokens)), 1
    )
    return overlap < float(DISCOVERY_TITLE_MISMATCH_MIN_OVERLAP_RATIO)


def distinctive_title_tokens(title: object, brand: object) -> set[str]:
    brand_tokens = text_tokens(normalize_brand(brand))
    return {
        token
        for token in text_tokens(title)
        if token not in brand_tokens and token not in DISCOVERY_GENERIC_PRODUCT_TOKENS
    }


def text_tokens(value: object) -> set[str]:
    tokens: set[str] = set()
    for token in re.split(r"[^a-z0-9]+", str(value or "").casefold()):
        if len(token) > 1:
            normalized = token[:-1] if token.endswith("s") and len(token) > 3 else token
            if normalized:
                tokens.add(normalized)
    return tokens


def domain_allowed(
    domain: str,
    allowed_domains: list[str],
    excluded_domains: list[str],
    source_domains: set[str],
) -> bool:
    normalized = domain.removeprefix("www.").lower()
    if not normalized:
        return False
    excluded = _normalized_domains([*excluded_domains, *source_domains])
    if any(domain_matches(normalized, item) for item in excluded):
        return False
    allowed = _normalized_domains(allowed_domains)
    return not allowed or any(domain_matches(normalized, item) for item in allowed)


def _normalized_domains(values) -> set[str]:
    return {str(item).removeprefix("www.").lower() for item in values if item}


def source_excluded_domains(
    product: dict[str, object], source_domain_value: str
) -> set[str]:
    domains = {str(source_domain_value or "").removeprefix("www.").lower()}
    domains.update(source_domain(url) for url in source_url_values(product))
    return {domain for domain in domains if domain}


def source_excluded_urls(product: dict[str, object]) -> set[str]:
    return {
        normalized
        for url in source_url_values(product)
        if (normalized := normalized_compare_url(url))
    }


def source_url_values(product: dict[str, object]) -> list[object]:
    values: list[object] = [
        product.get("url"),
        product.get("source_url"),
        product.get("canonical_url"),
        product.get("product_url"),
    ]
    if isinstance(raw := product.get("raw"), dict):
        values.extend(
            raw.get(key)
            for key in ("url", "source_url", "canonical_url", "product_url")
        )
    return values


def same_source_url(candidate_url: str, source_urls: set[str]) -> bool:
    return bool(source_urls and normalized_compare_url(candidate_url) in source_urls)


def domain_matches(normalized_domain: str, target: str) -> bool:
    normalized_target = str(target or "").removeprefix("www.").lower()
    return bool(
        normalized_target
        and (
            normalized_domain == normalized_target
            or normalized_domain.endswith(f".{normalized_target}")
        )
    )


def candidate_rank_text(candidate: RankedCandidate) -> str:
    return " ".join(
        part for part in (search_result_text(candidate.payload), candidate.url) if part
    )


def candidate_has_shopping_group(candidate: RankedCandidate) -> bool:
    payload = candidate.payload if isinstance(candidate.payload, dict) else {}
    provider = str(payload.get("provider") or "").casefold()
    return provider in {"serpapi_shopping", "serpapi_immersive"} and bool(
        payload.get("product_id") or payload.get("product_link")
    )


def candidate_title_overlap(
    product: dict[str, object], candidate: RankedCandidate
) -> float:
    source_tokens = distinctive_title_tokens(product.get("title"), product.get("brand"))
    candidate_tokens = distinctive_title_tokens(
        candidate_rank_text(candidate), product.get("brand")
    )
    if not source_tokens or not candidate_tokens:
        return 0.0
    return len(source_tokens & candidate_tokens) / max(
        min(len(source_tokens), len(candidate_tokens)), 1
    )


def candidate_model_token_match(
    product: dict[str, object], candidate: RankedCandidate
) -> bool:
    source_tokens = distinctive_title_tokens(product.get("title"), product.get("brand"))
    candidate_tokens = distinctive_title_tokens(
        candidate_rank_text(candidate), product.get("brand")
    )
    return bool(source_tokens and candidate_tokens and source_tokens & candidate_tokens)

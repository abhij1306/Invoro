from __future__ import annotations

from app.services.config.data_enrichment import (
    DATA_ENRICHMENT_SHOPIFY_ATTRIBUTE_CRAWL_FIELDS,
)


def repository_terms(repository: dict[str, object]) -> dict[str, object]:
    terms = repository.get("normalization_terms")
    return dict(terms) if isinstance(terms, dict) else {}


def term_dict(terms: dict[str, object], key: str) -> dict[str, object]:
    value = terms.get(key)
    return dict(value) if isinstance(value, dict) else {}


def attribute_lookup_keys(attribute: str) -> tuple[str, ...]:
    normalized = str(attribute or "").strip().replace("-", "_")
    explicit = DATA_ENRICHMENT_SHOPIFY_ATTRIBUTE_CRAWL_FIELDS.get(normalized)
    if explicit:
        return tuple(str(item) for item in explicit)
    variants = [normalized]
    if normalized.endswith("_type"):
        variants.append(normalized[:-5])
    if normalized.startswith("target_"):
        variants.append(normalized.replace("target_", "", 1))
    return tuple(dict.fromkeys(item for item in variants if item))

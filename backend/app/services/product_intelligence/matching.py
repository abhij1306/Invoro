from __future__ import annotations

import re
from difflib import SequenceMatcher
from urllib.parse import urlsplit

from app.services.shared.field_coerce import infer_brand_from_product_url, infer_brand_from_title_marker
from app.services.config.product_intelligence import (
    BRAND_ALIAS_MAP,
    BRAND_DOMAIN_MAP,
    DEFAULT_SCORE_LABEL_HIGH,
    DEFAULT_SCORE_LABEL_LOW,
    DEFAULT_SCORE_LABEL_MEDIUM,
    DEFAULT_SCORE_LABEL_UNCERTAIN,
    MATCH_DTC_MIN_TITLE_SIM,
    MATCH_SCORE_FLOOR_BRAND_DTC,
    MATCH_SCORE_FLOOR_BRAND_TITLE_HIGH,
    MATCH_SCORE_FLOOR_BRAND_TITLE_MEDIUM,
    MATCH_SCORE_FLOOR_BRAND_TITLE_PRICE_HIGH,
    MATCH_SCORE_FLOOR_GTIN,
    MATCH_SCORE_WEIGHTS,
    MATCH_TITLE_SIM_HIGH,
    MATCH_TITLE_SIM_MEDIUM,
    MATCH_VARIANT_MISMATCH_PENALTY,
    MATCH_VARIANT_MISMATCH_SCORE_CAP,
    PRIVATE_LABEL_BRANDS,
    SOURCE_AVAILABILITY_FIELDS,
    SOURCE_BRAND_FIELDS,
    SOURCE_CURRENCY_FIELDS,
    SOURCE_GTIN_FIELDS,
    SOURCE_IMAGE_FIELDS,
    SOURCE_MPN_FIELDS,
    SOURCE_PRICE_FIELDS,
    SOURCE_SKU_FIELDS,
    SOURCE_STYLE_FIELDS,
    SOURCE_TITLE_FIELDS,
    SOURCE_TYPE_AUTHORITY_BONUS,
    SOURCE_TYPE_BRAND_DTC,
    SOURCE_URL_FIELDS,
    VARIANT_SPEC_N_IN_ONE_PATTERN,
    VARIANT_SPEC_NUMBER_UNIT_PATTERN,
    VARIANT_SPEC_UNIT_ALIASES,
    product_intelligence_settings,
)
from app.services.product_intelligence.brand_registry import (
    infer_belk_brand,
    infer_belk_brand_prefix,
    is_belk_exclusive_brand,
)


def normalize_brand(value: object) -> str:
    text = _normalize_text(value)
    normalized = re.sub(r"[^a-z0-9]+", " ", text).strip()
    return BRAND_ALIAS_MAP.get(normalized, normalized)


def is_private_label(brand: object) -> bool:
    return normalize_brand(brand) in PRIVATE_LABEL_BRANDS or is_belk_exclusive_brand(brand)


def source_domain(url: object) -> str:
    try:
        host = urlsplit(str(url or "")).hostname or ""
    except ValueError:
        return ""
    return host.removeprefix("www.").lower()


def extract_product_snapshot(record: object) -> dict[str, object]:
    data = dict(record or {}) if isinstance(record, dict) else {}
    source_url = _first_present(data, SOURCE_URL_FIELDS)
    brand = _first_present(data, SOURCE_BRAND_FIELDS)
    title = _first_present(data, SOURCE_TITLE_FIELDS)
    price_value = _first_present(data, SOURCE_PRICE_FIELDS)
    if str(brand or "").strip():
        brand = _canonical_source_brand(brand, source_url=source_url, title=title)
    else:
        brand = _infer_brand(source_url=source_url, title=title)
    price = _as_float(price_value)
    return {
        "title": str(title or "").strip(),
        "brand": str(brand or "").strip(),
        "normalized_brand": normalize_brand(brand),
        "price": price,
        "currency": str(_first_present(data, SOURCE_CURRENCY_FIELDS) or _currency_from_price(price_value) or "").strip(),
        "image_url": str(_first_present(data, SOURCE_IMAGE_FIELDS) or "").strip(),
        "url": str(source_url or "").strip(),
        "sku": str(_first_present(data, SOURCE_SKU_FIELDS) or "").strip(),
        "mpn": str(_first_present(data, SOURCE_MPN_FIELDS) or "").strip(),
        "gtin": str(_first_present(data, SOURCE_GTIN_FIELDS) or "").strip(),
        "style": str(_first_present(data, SOURCE_STYLE_FIELDS) or "").strip(),
        "availability": str(_first_present(data, SOURCE_AVAILABILITY_FIELDS) or "").strip(),
        "raw": data,
    }


def score_candidate(
    *,
    source: dict[str, object],
    candidate: dict[str, object],
    source_type: str,
) -> dict[str, object]:
    reasons: dict[str, object] = {}
    score = 0.0
    source_title = str(source.get("title") or "")
    candidate_title = str(candidate.get("title") or "")
    title_similarity = _title_similarity(source_title, candidate_title)
    score += title_similarity * MATCH_SCORE_WEIGHTS["title_similarity"]
    reasons["title_similarity"] = round(title_similarity, 4)

    source_brand = normalize_brand(source.get("brand"))
    candidate_brand = normalize_brand(candidate.get("brand"))
    brand_match = bool(source_brand and candidate_brand and source_brand == candidate_brand)
    if brand_match:
        score += MATCH_SCORE_WEIGHTS["brand_match"]
    reasons["brand_match"] = brand_match

    gtin_match = _gtin_match(source, candidate)
    if gtin_match:
        score += MATCH_SCORE_WEIGHTS["gtin_match"]
    reasons["gtin_match"] = gtin_match

    # Belk SKU/style/product_id are internal identifiers with no relevance to external
    # retailers or Google/SerpAPI, so they are intentionally not scored. Confidence is
    # driven by brand-exact + title similarity, price band, and source authority.
    shopping_product_group = _shopping_product_group(candidate)
    if shopping_product_group:
        score += MATCH_SCORE_WEIGHTS["shopping_product_group"]
    reasons["shopping_product_group"] = shopping_product_group
    reasons["identifier_match"] = bool(gtin_match)

    price_match = _price_within_band(source.get("price"), candidate.get("price"))
    if price_match:
        score += MATCH_SCORE_WEIGHTS["price_band"]
    reasons["price_band_match"] = price_match

    raw_authority_bonus = float(SOURCE_TYPE_AUTHORITY_BONUS.get(str(source_type or ""), 0.0))
    if source_type == SOURCE_TYPE_BRAND_DTC:
        authority_bonus = raw_authority_bonus
    else:
        authority_bonus = min(
            raw_authority_bonus,
            MATCH_SCORE_WEIGHTS["source_authority"],
        )
    score += authority_bonus
    reasons["source_authority_bonus"] = round(authority_bonus, 4)

    variant_mismatch = _variant_spec_mismatch(source_title, candidate_title)
    if variant_mismatch:
        score -= MATCH_VARIANT_MISMATCH_PENALTY
    reasons["variant_mismatch"] = variant_mismatch

    # Confidence floors. Search results almost never expose a UPC, so a brand-exact
    # match with strong title similarity is the real high-confidence signal.
    if gtin_match and brand_match and title_similarity >= 0.45:
        score = max(score, MATCH_SCORE_FLOOR_GTIN)
    elif source_type == SOURCE_TYPE_BRAND_DTC and brand_match and title_similarity >= MATCH_DTC_MIN_TITLE_SIM:
        # Brand's own listing always ranks highest.
        score = max(score, MATCH_SCORE_FLOOR_BRAND_DTC)
    elif not variant_mismatch and brand_match and title_similarity >= MATCH_TITLE_SIM_HIGH:
        floor = (
            MATCH_SCORE_FLOOR_BRAND_TITLE_PRICE_HIGH
            if price_match
            else MATCH_SCORE_FLOOR_BRAND_TITLE_HIGH
        )
        score = max(score, floor)
    elif not variant_mismatch and brand_match and title_similarity >= MATCH_TITLE_SIM_MEDIUM:
        score = max(score, MATCH_SCORE_FLOOR_BRAND_TITLE_MEDIUM)

    # A detected wrong-variant match must not sit in the auto-accept band.
    if variant_mismatch:
        score = min(score, MATCH_VARIANT_MISMATCH_SCORE_CAP)

    final_score = round(min(max(score, 0.0), 1.0), 4)
    return {
        "score": final_score,
        "label": score_label(final_score),
        "reasons": reasons,
    }


def extract_search_result_snapshot(
    payload: dict[str, object] | None,
    *,
    url: str,
    domain: str,
) -> dict[str, object]:
    data = dict(payload or {})
    raw_value = data.get("raw")
    raw_data = raw_value if isinstance(raw_value, dict) else {}
    merged = {**raw_data, **data}
    price_value = _first_present(merged, ("extracted_price", "price"))
    description = _first_present(merged, ("description", "snippet"))
    brand = _infer_brand(
        source_url=url,
        title=merged.get("title"),
        domain=domain,
        snippet=merged.get("snippet"),
        source=merged.get("source"),
    )
    return {
        "title": str(merged.get("title") or "").strip(),
        "brand": brand,
        "normalized_brand": normalize_brand(brand),
        "price": _as_float(price_value),
        "currency": _currency_from_price(price_value),
        "description": str(description or "").strip(),
        "image_url": str(_first_present(merged, ("thumbnail", "image", "favicon")) or "").strip(),
        "url": str(url or merged.get("link") or "").strip(),
        "sku": str(_first_present(merged, ("sku",)) or "").strip(),
        "mpn": str(_first_present(merged, ("mpn", "model", "model_number", "part_number")) or "").strip(),
        "gtin": str(_first_present(merged, ("gtin", "barcode", "sku_upc", "upc", "ean")) or "").strip(),
        # "product_id" is intentionally included as a fallback for style identification
        # and is distinct from the standalone "product_id" metadata field extracted below.
        "style": str(_first_present(merged, ("style", "style_id", "product_id")) or "").strip(),
        "availability": str(merged.get("availability") or "").strip(),
        "snippet": str(merged.get("snippet") or "").strip(),
        "source": str(merged.get("source") or merged.get("displayed_link") or domain or "").strip(),
        "product_id": str(merged.get("product_id") or "").strip(),
        "product_link": str(merged.get("product_link") or "").strip(),
        "provider": str(merged.get("provider") or "").strip(),
        "raw": data,
    }


def _canonical_source_brand(
    brand: object,
    *,
    source_url: object,
    title: object,
) -> object:
    normalized = normalize_brand(brand)
    if normalized in BRAND_DOMAIN_MAP:
        return brand
    known_brand = _infer_known_brand(brand, title, source_url)
    if known_brand and normalize_brand(known_brand) in BRAND_DOMAIN_MAP:
        return known_brand
    return brand


def build_search_result_intelligence(
    *,
    source: dict[str, object],
    candidate_payload: dict[str, object] | None,
    candidate_url: str,
    candidate_domain: str,
    source_type: str,
) -> dict[str, object]:
    canonical = extract_search_result_snapshot(
        candidate_payload,
        url=candidate_url,
        domain=candidate_domain,
    )
    if not normalize_brand(canonical.get("brand")) and _candidate_mentions_source_brand(source, canonical):
        canonical["brand"] = str(source.get("brand") or "").strip()
        canonical["normalized_brand"] = normalize_brand(canonical["brand"])
    deterministic = score_candidate(source=source, candidate=canonical, source_type=source_type)
    provider = str((candidate_payload or {}).get("provider") or "search").strip().lower() or "search"
    return {
        "canonical_record": canonical,
        "confidence_score": deterministic["score"],
        "confidence_label": deterministic["label"],
        "score_reasons": deterministic["reasons"],
        "cleanup_source": f"deterministic_{provider}",
        "llm_enrichment": {"requested": False, "applied": False},
    }


def score_label(score: float) -> str:
    if score >= 0.85:
        return DEFAULT_SCORE_LABEL_HIGH
    if score >= 0.60:
        return DEFAULT_SCORE_LABEL_MEDIUM
    if score >= 0.40:
        return DEFAULT_SCORE_LABEL_LOW
    return DEFAULT_SCORE_LABEL_UNCERTAIN


def _first_present(data: dict[str, object], fields: tuple[str, ...]) -> object:
    for field in fields:
        value = data.get(field)
        if value not in (None, "", [], {}):
            return value
    return None


def _normalize_text(value: object) -> str:
    return " ".join(str(value or "").casefold().split())


def _infer_brand(
    *,
    source_url: object,
    title: object,
    domain: object = "",
    snippet: object = "",
    source: object = "",
) -> str:
    known_brand = _infer_known_brand(domain, source_url, title, snippet, source)
    if known_brand:
        return known_brand
    marker_brand = infer_brand_from_title_marker(title)
    if marker_brand:
        return marker_brand
    registry_prefix_brand = infer_belk_brand_prefix(title)
    if registry_prefix_brand:
        return registry_prefix_brand
    if _is_belk_source(source_url, domain, source):
        belk_brand = infer_belk_brand(_url_path_text(source_url), title, snippet, source)
        if belk_brand:
            return belk_brand
    return infer_brand_from_product_url(url=str(source_url or ""), title=title) or ""


def _is_belk_source(*values: object) -> bool:
    return "belk.com" in " ".join(str(value or "") for value in values).casefold()


def _url_path_text(value: object) -> str:
    try:
        parsed = urlsplit(str(value or ""))
    except ValueError:
        return str(value or "")
    return " ".join(part for part in (parsed.path, parsed.query) if part)


def _infer_known_brand(*values: object) -> str:
    haystack = " ".join(str(value or "") for value in values).casefold().replace("-", " ")
    normalized = re.sub(r"[^a-z0-9]+", " ", haystack)
    compact = re.sub(r"[^a-z0-9]+", "", haystack)
    known_brands = {*BRAND_ALIAS_MAP.values(), *BRAND_ALIAS_MAP.keys(), *BRAND_DOMAIN_MAP.keys()}
    for brand in sorted(known_brands, key=len, reverse=True):
        normalized_brand = brand.replace("-", " ")
        compact_brand = re.sub(r"[^a-z0-9]+", "", normalized_brand)
        if re.search(rf"\b{re.escape(normalized_brand)}\b", normalized) or (
            len(compact_brand) >= 5 and compact_brand in compact
        ):
            return BRAND_ALIAS_MAP.get(brand, brand)
    return ""


def _candidate_mentions_source_brand(
    source: dict[str, object],
    candidate: dict[str, object],
) -> bool:
    source_brand = normalize_brand(source.get("brand"))
    if not source_brand:
        return False
    haystack = " ".join(
        str(candidate.get(key) or "")
        for key in ("title", "description", "snippet", "source", "url")
    )
    tokens = _token_set(haystack)
    brand_tokens = _token_set(source_brand)
    return bool(brand_tokens and brand_tokens.issubset(tokens))


def _title_similarity(left: str, right: str) -> float:
    left_tokens = _token_set(left)
    right_tokens = _token_set(right)
    if not left_tokens or not right_tokens:
        return 0.0

    intersection = left_tokens & right_tokens
    smaller_size = min(len(left_tokens), len(right_tokens))
    larger_size = max(len(left_tokens), len(right_tokens))
    union_size = len(left_tokens | right_tokens)

    # Keep the baseline symmetric so short generic subsets do not look exact.
    overlap = len(intersection) / union_size if union_size > 0 else 0.0
    containment = len(intersection) / smaller_size if smaller_size > 0 else 0.0
    larger_coverage = len(intersection) / larger_size if larger_size > 0 else 0.0
    size_balance = smaller_size / larger_size if larger_size > 0 else 0.0

    sequence = SequenceMatcher(
        None,
        " ".join(sorted(left_tokens)),
        " ".join(sorted(right_tokens))
    ).ratio() * size_balance

    # Reward near-complete descriptive expansions, but only when the larger title is
    # also mostly covered and the overlap carries real specificity.
    if containment >= 0.85 and larger_coverage >= 0.60 and len(intersection) >= 3:
        return max(0.80 * containment + 0.20 * larger_coverage, sequence)

    return max(overlap, sequence)


def _token_set(value: object) -> set[str]:
    return {
        token
        for token in re.split(r"[^a-z0-9]+", str(value or "").casefold())
        if len(token) > 1
    }


def _gtin_match(source: dict[str, object], candidate: dict[str, object]) -> bool:
    keys = ("gtin", "barcode", "sku_upc", "upc", "ean")
    source_values = {_identity_value(source.get(key)) for key in keys}
    candidate_values = {_identity_value(candidate.get(key)) for key in keys}
    source_values.discard("")
    candidate_values.discard("")
    return bool(source_values and candidate_values and source_values & candidate_values)


_VARIANT_SPEC_NUMBER_UNIT_RE = re.compile(VARIANT_SPEC_NUMBER_UNIT_PATTERN, re.I)
_VARIANT_SPEC_N_IN_ONE_RE = re.compile(VARIANT_SPEC_N_IN_ONE_PATTERN, re.I)


def _variant_specs(title: object) -> tuple[set[tuple[str, str]], set[str]]:
    text = str(title or "").casefold()
    unit_specs: set[tuple[str, str]] = set()
    for number, unit in _VARIANT_SPEC_NUMBER_UNIT_RE.findall(text):
        canonical_unit = VARIANT_SPEC_UNIT_ALIASES.get(unit, unit)
        normalized_number = number.rstrip("0").rstrip(".") if "." in number else number
        unit_specs.add((normalized_number, canonical_unit))
    n_in_one = {match for match in _VARIANT_SPEC_N_IN_ONE_RE.findall(text)}
    return unit_specs, n_in_one


def _variant_spec_mismatch(source_title: object, candidate_title: object) -> bool:
    """Deterministic variant guard.

    When both titles explicitly state the same spec dimension (a capacity unit such
    as oz/qt/cup, or an "N-in-1" descriptor) and the stated values differ, the
    candidate is a different variant of the product. Only fires when both sides
    declare the dimension, so a silent candidate is never penalized.
    """
    source_units, source_n = _variant_specs(source_title)
    candidate_units, candidate_n = _variant_specs(candidate_title)

    source_unit_by_kind = {unit: number for number, unit in source_units}
    candidate_unit_by_kind = {unit: number for number, unit in candidate_units}
    for unit, source_number in source_unit_by_kind.items():
        candidate_number = candidate_unit_by_kind.get(unit)
        if candidate_number is not None and candidate_number != source_number:
            return True

    if source_n and candidate_n and not (source_n & candidate_n):
        return True
    return False


def _shopping_product_group(candidate: dict[str, object]) -> bool:
    provider = str(candidate.get("provider") or "").strip().casefold()
    product_id = str(candidate.get("product_id") or "").strip()
    product_link = str(candidate.get("product_link") or "").strip()
    return provider in {"serpapi_shopping", "serpapi_immersive"} and bool(
        product_id or product_link
    )


def _identity_value(value: object) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(value or "").casefold())


def _price_within_band(left: object, right: object) -> bool:
    left_price = _as_float(left)
    right_price = _as_float(right)
    if left_price is None or right_price is None or left_price <= 0 or right_price <= 0:
        return False
    return abs(left_price - right_price) / left_price <= product_intelligence_settings.price_band_ratio


def _as_float(value: object) -> float | None:
    if value in (None, "", [], {}):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = re.sub(r"[^0-9.,]+", "", str(value))
    if "." in text and "," in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        head, _, tail = text.rpartition(",")
        text = f"{head}.{tail}" if 1 <= len(tail) <= 3 else text.replace(",", "")
    text = re.sub(r"[^0-9.]+", "", text)
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _currency_from_price(value: object) -> str:
    text = str(value or "")
    if "$" in text:
        return "USD"
    if "€" in text:
        return "EUR"
    if "£" in text:
        return "GBP"
    return ""

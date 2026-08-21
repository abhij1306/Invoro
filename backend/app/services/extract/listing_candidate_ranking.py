# ruff: noqa: E402, F401, F821, F822
from __future__ import annotations

__all__ = (
    "best_listing_candidate_set",
    "listing_record_supported",
    "job_listing_url_looks_like_posting",
    "job_listing_title_is_hub",
    "job_listing_url_is_hub",
    "job_listing_url_is_utility",
    "looks_like_utility_title",
    "looks_like_utility_url",
    "looks_like_utility_record",
    "title_contains_token_phrase",
    "utility_url_token_matches",
    "unsupported_non_detail_ecommerce_merchandise_hint",
)

import re
from collections import Counter
from typing import Any, Callable
from urllib.parse import parse_qsl, urlsplit

from app.services.config.extraction_rules import (
    DETAIL_COLLECTION_PATH_TOKENS,
    DETAIL_PRODUCT_PATH_TOKENS,
    JOB_POSTING_PATH_MARKERS,
    JOB_LISTING_HUB_TERMINAL_SUFFIXES,
    JOB_LISTING_HUB_TITLE_PREFIXES,
    JOB_LISTING_HUB_TITLE_SUFFIXES,
    JOB_UTILITY_URL_TOKENS,
    LISTING_EDITORIAL_PATH_SEGMENTS,
    LISTING_EDITORIAL_TITLE_PATTERNS,
    LISTING_EDITORIAL_URL_TOKENS,
    LISTING_NON_LISTING_PATH_TOKENS,
    LISTING_PRODUCT_DETAIL_ID_RE,
    LISTING_UTILITY_TITLE_TOKENS,
    LISTING_UTILITY_URL_TOKENS,
    PRODUCT_SLUG_MIN_TERMINAL_TOKENS,
    YEAR_SLUG_PATTERN,
)
from app.services.config.surface_hints import detail_path_hints
from app.services.config.runtime_settings import crawler_runtime_settings
from app.services.extract.listing_card_fragments import listing_signature_url_shape
from app.services.shared.field_coerce import LISTING_UTILITY_TITLE_REGEXES, clean_text

_LOWER_NON_ALNUM_SPLIT_RE = re.compile(r"[^a-z0-9]+")

def _metric_int(metrics: dict[str, object], key: str) -> int:
    value = metrics.get(key)
    return int(value) if isinstance(value, int | bool) else 0

def _record_url_signature(url: str) -> str:
    """Compute a URL-shape signature for cohort homogeneity comparison.

    Uses the same URL-shape dimensions as
    :func:`listing_fragment_structural_signature`: category-prefix bucket and
    detail-marker boolean, plus path-depth bucket and path-prefix shape.
    """
    raw = str(url or "").strip()
    if not raw:
        return "0|0|0"
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return "0|0|0"
    prefix_bucket, detail_marker = listing_signature_url_shape(raw)
    path = str(parsed.path or "").lower()
    segments = [s for s in path.split("/") if s]
    depth = len(segments)
    if depth <= 1:
        depth_bucket = "1"
    elif depth <= 3:
        depth_bucket = "2_3"
    else:
        depth_bucket = "4_plus"
    return f"{prefix_bucket}|{detail_marker}|{depth_bucket}"

def _listing_url_path_tokens(url: str) -> set[str]:
    try:
        parsed = urlsplit(str(url or "").strip())
    except ValueError:
        return set()
    return {token for token in _LOWER_NON_ALNUM_SPLIT_RE.split(str(parsed.path or "").lower()) if token}

def _listing_url_is_collection_like(url: str) -> bool:
    path_tokens = _listing_url_path_tokens(url)
    if any(token in path_tokens for token in DETAIL_PRODUCT_PATH_TOKENS):
        return False
    return any(token in path_tokens for token in DETAIL_COLLECTION_PATH_TOKENS)

def _set_cohort_homogeneity(records: list[dict[str, Any]], *, page_url: str) -> float:
    """Return dominant_signature_count / len(records). Empty set returns 1.0."""
    _ = page_url
    if not records:
        return 1.0
    signatures: list[str] = []
    for record in records:
        url = str(record.get("url") or "").strip()
        sig = _record_url_signature(url)
        signatures.append(sig)
    if not signatures:
        return 1.0
    counts = Counter(signatures)
    dominant_count = counts.most_common(1)[0][1]
    return dominant_count / len(signatures)

def best_listing_candidate_set(
    candidate_sets: list[tuple[str, list[dict[str, Any]]]],
    *,
    page_url: str,
    surface: str,
    max_records: int,
    title_is_noise: Callable[[str], bool],
    url_is_structural: Callable[[str, str], bool],
    detail_like_url: Callable[[str], bool] | None = None,
    diagnostics_sink: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    best_records: list[dict[str, Any]] = []
    best_score: tuple[bool, int, int, int, int, int, int, int] | None = None
    for set_name, records in candidate_sets:
        limited = [record for record in records or [] if isinstance(record, dict)]
        prepared = _prepare_listing_candidate_set(
            limited,
            page_url=page_url,
            surface=surface,
            title_is_noise=title_is_noise,
            url_is_structural=url_is_structural,
            detail_like_url=detail_like_url,
        )
        score = _listing_record_set_score(
            prepared,
            page_url=page_url,
            surface=surface,
            title_is_noise=title_is_noise,
            url_is_structural=url_is_structural,
            detail_like_url=detail_like_url,
        )
        # Emit cohort_penalty_applied diagnostic when penalty is active
        if diagnostics_sink is not None and prepared and not score[0]:
            homogeneity = _set_cohort_homogeneity(prepared, page_url=page_url)
            signatures = Counter(_record_url_signature(str(r.get("url") or "").strip()) for r in prepared)
            dominant_count = signatures.most_common(1)[0][1] if signatures else 0
            diagnostics_sink.append(
                {
                    "type": "cohort_penalty_applied",
                    "set_name": set_name,
                    "record_count": len(prepared),
                    "dominant_signature_count": dominant_count,
                    "cohort_homogeneity_ratio": homogeneity,
                }
            )
        if best_score is None or score > best_score:
            best_score = score
            best_records = prepared
    return best_records

def _prepare_listing_candidate_set(
    records: list[dict[str, Any]],
    *,
    page_url: str,
    surface: str,
    title_is_noise: Callable[[str], bool],
    url_is_structural: Callable[[str, str], bool],
    detail_like_url: Callable[[str], bool] | None,
) -> list[dict[str, Any]]:
    best_by_key: dict[str, tuple[int, int, dict[str, Any]]] = {}
    prepared: list[tuple[int, int, dict[str, Any]]] = []
    for order, record in enumerate(records):
        metrics = _listing_record_quality_metrics(
            record,
            page_url=page_url,
            surface=surface,
            title_is_noise=title_is_noise,
            url_is_structural=url_is_structural,
            detail_like_url=detail_like_url,
        )
        if _should_drop_record(metrics, surface=surface):
            continue
        score = _metric_int(metrics, "score")
        url = str(record.get("url") or "").strip()
        dedupe_key = _listing_record_dedupe_key(
            record,
            url=url,
            detail_like_url=detail_like_url,
        )
        if dedupe_key:
            existing = best_by_key.get(dedupe_key)
            candidate = (score, order, record)
            if existing is None or (score, -order) > (existing[0], -existing[1]):
                best_by_key[dedupe_key] = candidate
            continue
        prepared.append((score, order, record))
    prepared.extend(best_by_key.values())
    prepared.sort(key=lambda row: (-row[0], row[1]))
    return [record for _score, _order, record in prepared]

def _listing_record_dedupe_key(
    record: dict[str, Any],
    *,
    url: str,
    detail_like_url: Callable[[str], bool] | None,
) -> str:
    if not url:
        return _record_id_dedupe_key(record)
    if detail_like_url is not None and detail_like_url(url):
        parsed = urlsplit(url)
        host = str(parsed.hostname or "").lower()
        path = str(parsed.path or "").rstrip("/").lower()
        query_identity = _job_detail_query_identity(parsed.query)
        if host and path and query_identity:
            return f"path:{host}{path}?{query_identity}"
        if host and path:
            return f"path:{host}{path}"
    return f"url:{url}"

def _record_id_dedupe_key(record: dict[str, Any]) -> str:
    product_id = clean_text(record.get("product_id") or record.get("productId") or record.get("sku"))
    if product_id:
        return f"id:{product_id.lower()}"
    job_id = clean_text(record.get("job_id") or record.get("requisition_id"))
    return f"job:{job_id.lower()}" if job_id else ""

def _listing_record_set_score(
    records: list[dict[str, Any]],
    *,
    page_url: str,
    surface: str,
    title_is_noise: Callable[[str], bool],
    url_is_structural: Callable[[str, str], bool],
    detail_like_url: Callable[[str], bool] | None,
) -> tuple[bool, int, int, int, int, int, int, int]:
    if not records:
        return (False, -1, -1, -1, -1, -1, -1, -1)
    quality_metrics = [
        _listing_record_quality_metrics(
            record,
            page_url=page_url,
            surface=surface,
            title_is_noise=title_is_noise,
            url_is_structural=url_is_structural,
            detail_like_url=detail_like_url,
        )
        for record in records
        if isinstance(record, dict)
    ]
    if not quality_metrics:
        return (False, -1, -1, -1, -1, -1, -1, -1)
    # Cohort homogeneity is a penalty, not a pre-gate drop. The integrity gate
    # still needs the best available set to explain/retry bad cohorts.
    threshold = crawler_runtime_settings.listing_cohort_homogeneity_min_ratio
    homogeneity = _set_cohort_homogeneity(records, page_url=page_url)
    cohort_pass = homogeneity >= threshold
    quality_scores = [_metric_int(metrics, "score") for metrics in quality_metrics]
    strong_records = sum(score >= crawler_runtime_settings.listing_candidate_strong_score_threshold for score in quality_scores)
    supported_records = sum(bool(metrics["supported"]) for metrics in quality_metrics)
    # Support-signal override: when the set is large enough and a majority of
    # records carry support signals, treat cohort as passing. This prevents a
    # few navigation links from penalizing an otherwise valid product grid.
    if not cohort_pass and len(quality_metrics) >= 5 and supported_records >= max(1, len(quality_metrics) // 2):
        cohort_pass = True
    detail_like_records = sum(bool(metrics["detail_like"]) for metrics in quality_metrics)
    utility_records = sum(bool(metrics["utility"]) for metrics in quality_metrics)
    clean_records = len(quality_metrics) - utility_records
    avg_quality = int(round(sum(quality_scores) / max(1, len(quality_scores)) * 100))
    # Intentional priority: average quality outranks raw strong-record count so
    # richer product cohorts beat thinner promo-heavy sets in `score > best_score`.
    return (
        cohort_pass,
        avg_quality,
        strong_records,
        supported_records,
        detail_like_records,
        clean_records,
        -utility_records,
        sum(quality_scores),
    )

def _listing_record_quality_metrics(
    record: dict[str, Any],
    *,
    page_url: str,
    surface: str,
    title_is_noise: Callable[[str], bool],
    url_is_structural: Callable[[str, str], bool],
    detail_like_url: Callable[[str], bool] | None,
) -> dict[str, object]:
    title = clean_text(record.get("title"))
    url = str(record.get("url") or "").strip()
    is_job_surface = str(surface or "").startswith("job_")
    detail_like = bool(detail_like_url(url)) if url and detail_like_url is not None else False
    utility = looks_like_utility_record(title=title, url=url)
    supported = _record_has_supporting_signals(
        record,
        detail_like=detail_like,
        job_surface=is_job_surface,
        surface=surface,
    )
    score = _listing_identity_score(
        title,
        url,
        page_url,
        is_job_surface,
        detail_like,
        title_is_noise,
        url_is_structural,
    )
    score += _listing_support_field_score(record)
    score += _listing_source_score(record)
    fallback_merchandise = False
    detail_like_merchandise = False
    if not supported and detail_like and not is_job_surface:
        detail_like_merchandise = _unsupported_detail_like_ecommerce_merchandise_hint(
            title=title,
            url=url,
        )
        score += -4 if detail_like_merchandise else -14
    elif not supported and not detail_like and not is_job_surface:
        fallback_merchandise = _unsupported_non_detail_ecommerce_merchandise_hint(
            title=title,
            url=url,
        )
        if fallback_merchandise:
            score += 2
        else:
            score -= 12
    elif not supported and not detail_like:
        score -= 7
    score += _utility_score_adjustment(utility)
    return {
        "score": score,
        "detail_like": detail_like,
        "detail_like_merchandise": detail_like_merchandise,
        "fallback_merchandise": fallback_merchandise,
        "supported": supported,
        "utility": utility,
    }

def _utility_score_adjustment(utility: bool) -> int:
    return -16 if utility else 0

def _listing_identity_score(
    title: str,
    url: str,
    page_url: str,
    is_job_surface: bool,
    detail_like: bool,
    title_is_noise: Callable[[str], bool],
    url_is_structural: Callable[[str, str], bool],
) -> int:
    score = 6 + (1 if len(title) >= 12 else 0) if title else -10
    if title and title_is_noise(title):
        score -= 8
    score += 8 if url and not url_is_structural(url, page_url) else -12
    if not is_job_surface and not detail_like and _listing_url_is_collection_like(url):
        score -= 12
    return score + (5 if detail_like else 0)

def _listing_support_field_score(record: dict[str, Any]) -> int:
    weights = {
        "price": 6,
        "image_url": 4,
        "brand": 2,
        "rating": 1,
        "review_count": 1,
    }
    score = sum(weight for field_name, weight in weights.items() if record.get(field_name) not in (None, "", [], {}))
    description = clean_text(record.get("description"))
    return score + (1 if isinstance(description, str) and len(description) >= 24 else 0)

def _listing_source_score(record: dict[str, Any]) -> int:
    return {
        "visual_listing": -6,
        "structured_listing": 3,
        "rendered_listing": 2,
        "dom_listing": 2,
    }.get(str(record.get("_source") or ""), 0)

def _record_has_supporting_signals(
    record: dict[str, Any],
    *,
    detail_like: bool,
    job_surface: bool,
    surface: str,
) -> bool:
    normalized_surface = str(surface or "").strip().lower()
    if normalized_surface == "content_listing":
        return True
    if normalized_surface == "article_listing":
        return _record_has_article_signals(record)
    if detail_like and job_surface:
        return True
    url = str(record.get("url") or "").strip()
    explicit_detail_tokens = set(DETAIL_PRODUCT_PATH_TOKENS) - {"product", "products"}
    if detail_like and any(token in _listing_url_path_tokens(url) for token in explicit_detail_tokens):
        return True
    if _record_has_merchandise_signals(record):
        return True
    if record.get("price") in (None, "", [], {}):
        return False
    if detail_like:
        return True
    if any(token in _listing_url_path_tokens(url) for token in DETAIL_PRODUCT_PATH_TOKENS):
        return True
    title = clean_text(record.get("title"))
    return _unsupported_non_detail_ecommerce_merchandise_hint(title=title, url=url)

def _record_has_article_signals(record: dict[str, Any]) -> bool:
    return any(record.get(field_name) not in (None, "", [], {}) for field_name in ("publication_date", "author", "summary"))

def _record_has_merchandise_signals(record: dict[str, Any]) -> bool:
    return any(
        record.get(field_name) not in (None, "", [], {})
        for field_name in (
            "image_url",
            "rating",
            "review_count",
            "brand",
            "description",
        )
    )

from . import listing_admission as _split_owner
globals().update({
    name: value
    for name, value in vars(_split_owner).items()
    if not name.startswith("__") and name != "_owner"
})

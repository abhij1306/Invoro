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
    return {
        token
        for token in _LOWER_NON_ALNUM_SPLIT_RE.split(str(parsed.path or "").lower())
        if token
    }


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
            signatures = Counter(
                _record_url_signature(str(r.get("url") or "").strip()) for r in prepared
            )
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
    product_id = clean_text(
        record.get("product_id") or record.get("productId") or record.get("sku")
    )
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
    strong_records = sum(
        score >= crawler_runtime_settings.listing_candidate_strong_score_threshold
        for score in quality_scores
    )
    supported_records = sum(bool(metrics["supported"]) for metrics in quality_metrics)
    # Support-signal override: when the set is large enough and a majority of
    # records carry support signals, treat cohort as passing. This prevents a
    # few navigation links from penalizing an otherwise valid product grid.
    if (
        not cohort_pass
        and len(quality_metrics) >= 5
        and supported_records >= max(1, len(quality_metrics) // 2)
    ):
        cohort_pass = True
    detail_like_records = sum(
        bool(metrics["detail_like"]) for metrics in quality_metrics
    )
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
    detail_like = (
        bool(detail_like_url(url)) if url and detail_like_url is not None else False
    )
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
    score = sum(
        weight
        for field_name, weight in weights.items()
        if record.get(field_name) not in (None, "", [], {})
    )
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
    if detail_like and any(
        token in _listing_url_path_tokens(url) for token in explicit_detail_tokens
    ):
        return True
    if _record_has_merchandise_signals(record):
        return True
    if record.get("price") in (None, "", [], {}):
        return False
    if detail_like:
        return True
    if any(
        token in _listing_url_path_tokens(url) for token in DETAIL_PRODUCT_PATH_TOKENS
    ):
        return True
    title = clean_text(record.get("title"))
    return _unsupported_non_detail_ecommerce_merchandise_hint(title=title, url=url)


def _record_has_article_signals(record: dict[str, Any]) -> bool:
    return any(
        record.get(field_name) not in (None, "", [], {})
        for field_name in ("publication_date", "author", "summary")
    )


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


def listing_record_supported(
    record: dict[str, Any],
    *,
    page_url: str,
    surface: str,
    title_is_noise: Callable[[str], bool],
    url_is_structural: Callable[[str, str], bool],
    detail_like_url: Callable[[str], bool],
) -> bool:
    title = clean_text(record.get("title"))
    url = str(record.get("url") or "").strip()
    source_kind = str(record.get("_source") or "").strip().lower()
    if _listing_identity_is_rejected(
        title, url, page_url, title_is_noise, url_is_structural
    ):
        return False
    is_job_surface = surface.startswith("job_")
    detail_like = detail_like_url(url)
    if is_job_surface and _job_listing_identity_is_utility(title, url, detail_like):
        return False
    if detail_like:
        return True
    if _record_has_supporting_listing_signals(record, surface=surface):
        return True
    if surface == "content_listing":
        return True
    if surface == "article_listing":
        return _record_has_article_signals(record)
    if is_job_surface and job_listing_url_looks_like_posting(url):
        return True
    return (
        not is_job_surface and source_kind == "structured_listing" and len(title) >= 12
    )


def _listing_identity_is_rejected(
    title: str,
    url: str,
    page_url: str,
    title_is_noise: Callable[[str], bool],
    url_is_structural: Callable[[str, str], bool],
) -> bool:
    if not title or not url or title_is_noise(title):
        return True
    if re.search(r"\.(?:pdf|docx?|pptx?)(?:$|[?#])", url, flags=re.I):
        return True
    return url_is_structural(url, page_url) or looks_like_utility_record(
        title=title, url=url
    )


def _job_listing_identity_is_utility(title: str, url: str, detail_like: bool) -> bool:
    return bool(
        job_listing_url_is_utility(url)
        or job_listing_url_is_hub(url)
        or (job_listing_title_is_hub(title) and not detail_like)
    )


def _record_has_supporting_listing_signals(
    record: dict[str, Any],
    *,
    surface: str,
) -> bool:
    if any(
        record.get(field_name) not in (None, "", [], {})
        for field_name in ("image_url", "price", "rating", "review_count")
    ):
        return True
    if surface.startswith("job_"):
        return any(
            record.get(field_name) not in (None, "", [], {})
            for field_name in ("company", "location", "salary", "job_type")
        )
    return record.get("brand") not in (None, "", [], {})


def job_listing_url_looks_like_posting(url: str) -> bool:
    parsed = urlsplit(url.lower())
    segments = [
        segment.strip().lower() for segment in parsed.path.split("/") if segment.strip()
    ]
    if not segments:
        return False
    terminal = segments[-1]
    leading_tokens = [_path_segment_tokens(segment) for segment in segments[:-1]]
    if any(tokens & set(LISTING_NON_LISTING_PATH_TOKENS) for tokens in leading_tokens):
        return False
    terminal_tokens = _path_segment_tokens(terminal)
    if terminal_tokens & set(LISTING_NON_LISTING_PATH_TOKENS):
        return False
    if re.fullmatch(r"(?:19|20)\d{2}", terminal):
        return False
    if not re.search(r"\d{4,}", terminal):
        return False
    if any(marker in parsed.path for marker in JOB_POSTING_PATH_MARKERS):
        return True
    terminal_words = [
        token
        for token in re.split(r"[^a-z0-9]+", terminal)
        if len(token) >= 3 and not token.isdigit()
    ]
    return len(terminal_words) >= 2


def job_listing_title_is_hub(title: str) -> bool:
    lowered = clean_text(title).lower()
    if not lowered:
        return False
    if lowered in {"jobs", "careers", "openings"}:
        return True
    if lowered.endswith(tuple(JOB_LISTING_HUB_TITLE_SUFFIXES)) and (
        lowered.startswith(tuple(JOB_LISTING_HUB_TITLE_PREFIXES))
        or len([token for token in re.split(r"[^a-z0-9]+", lowered) if token]) <= 4
    ):
        return True
    return lowered.startswith(
        (
            "jobs in ",
            "jobs near ",
            "careers in ",
            "roles in ",
            "openings in ",
        )
    )


def job_listing_url_is_hub(url: str) -> bool:
    parsed = urlsplit(url.lower())
    segments = [segment for segment in parsed.path.split("/") if segment]
    terminal = segments[-1] if segments else ""
    if terminal in {
        "careers",
        "jobs",
        "openings",
        "search",
        "search-jobs",
        "search-results",
    }:
        return True
    if terminal.startswith(
        (
            "jobs-in-",
            "careers-in-",
            "openings-in-",
            "search-jobs",
            "job-search",
        )
    ):
        return True
    if terminal.endswith(tuple(JOB_LISTING_HUB_TERMINAL_SUFFIXES)) and not re.search(
        r"\d{4,}", terminal
    ):
        return True
    return False


def job_listing_url_is_utility(url: str) -> bool:
    return any(
        _utility_url_token_matches(str(url or "").strip().lower(), token)
        for token in JOB_UTILITY_URL_TOKENS
    )


def _job_detail_query_identity(query: str) -> str:
    for key, value in parse_qsl(str(query or ""), keep_blank_values=True):
        normalized_key = str(key or "").strip().lower()
        normalized_value = str(value or "").strip().lower()
        if (
            normalized_key in {"showjob", "jobid", "job_id", "gh_jid"}
            and normalized_value
        ):
            return f"{normalized_key}={normalized_value}"
    return ""


def _path_segment_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.split(r"[\-\.]+", str(value or "").strip().lower())
        if token
    }


def _should_drop_record(metrics: dict[str, object], *, surface: str) -> bool:
    score = _metric_int(metrics, "score")
    detail_like = bool(metrics.get("detail_like"))
    detail_like_merchandise = bool(metrics.get("detail_like_merchandise"))
    fallback_merchandise = bool(metrics.get("fallback_merchandise"))
    supported = bool(metrics.get("supported"))
    utility = bool(metrics.get("utility"))
    is_job_surface = str(surface or "").startswith("job_")
    if utility and not detail_like:
        return True
    if utility and score < 10:
        return True
    if _unsupported_detail_record(
        supported, detail_like, is_job_surface, detail_like_merchandise
    ):
        return True
    if _unsupported_fallback_record(
        supported, detail_like, is_job_surface, fallback_merchandise
    ):
        return True
    if not supported and not detail_like and score < 10:
        return True
    return score < 0


def _unsupported_detail_record(
    supported: bool,
    detail_like: bool,
    is_job_surface: bool,
    merchandise_hint: bool,
) -> bool:
    return not supported and detail_like and not is_job_surface and not merchandise_hint


def _unsupported_fallback_record(
    supported: bool,
    detail_like: bool,
    is_job_surface: bool,
    merchandise_hint: bool,
) -> bool:
    return (
        not supported
        and not detail_like
        and not is_job_surface
        and not merchandise_hint
    )


def looks_like_utility_title(title: str) -> bool:
    """Title-only utility check. Used by visual cluster scoring and adapter title gating."""
    normalized_title = " ".join(str(title or "").strip().lower().split())
    if not normalized_title:
        return False
    if any(
        pattern.search(normalized_title) for pattern in LISTING_UTILITY_TITLE_REGEXES
    ):
        return True
    return any(
        title_contains_token_phrase(normalized_title, token)
        for token in LISTING_UTILITY_TITLE_TOKENS
    )


def looks_like_utility_url(url: str) -> bool:
    """URL-only utility check. Catches utility/help/account/legal anchors and disallowed path segments."""
    normalized_url = str(url or "").strip().lower()
    if not normalized_url:
        return False
    parsed = urlsplit(normalized_url)
    segments = [
        segment.strip().lower() for segment in parsed.path.split("/") if segment.strip()
    ]
    if len(segments) >= 3 and (
        LISTING_PRODUCT_DETAIL_ID_RE.search(normalized_url) is not None
        or any(
            marker in normalized_url for marker in detail_path_hints("ecommerce_detail")
        )
    ):
        return False
    # A path segment that matches a structural/utility token makes the URL
    # utility UNLESS the terminal segment looks like a product slug (>=3
    # hyphen-separated alphanumeric tokens). Without the exemption, sites
    # like Tire Rack that mount products under `/accessories/<slug>` would
    # lose every product anchor.
    terminal_is_product_slug = _terminal_is_product_slug(segments)
    if (
        not parsed.query
        and segments
        and any(segment in LISTING_NON_LISTING_PATH_TOKENS for segment in segments)
        and not terminal_is_product_slug
    ):
        return True
    return any(
        _utility_url_token_matches(normalized_url, token)
        for token in LISTING_UTILITY_URL_TOKENS
    )


def _terminal_is_product_slug(segments: list[str]) -> bool:
    terminal = segments[-1] if segments else ""
    tokens = [token for token in re.split(r"[-.]+", terminal) if token]
    year_led = bool(tokens and re.fullmatch(YEAR_SLUG_PATTERN, tokens[0]))
    return bool(
        len(tokens) >= PRODUCT_SLUG_MIN_TERMINAL_TOKENS
        and any(re.search(r"[a-z]", token) for token in tokens)
        and "-" in terminal
        and not year_led
    )


def looks_like_utility_record(*, title: str, url: str) -> bool:
    """Single canonical utility-record check. Title or URL signals are sufficient."""
    return looks_like_utility_title(title) or looks_like_utility_url(url)


def _utility_url_token_matches(normalized_url: str, token: str) -> bool:
    normalized_token = str(token or "").strip().lower()
    if not normalized_url or not normalized_token:
        return False
    if normalized_token.startswith("/"):
        parsed = urlsplit(normalized_url)
        path = str(parsed.path or "").lower()
        token_segment = normalized_token.strip("/")
        if not token_segment:
            return normalized_token in normalized_url
        if "/" in token_segment:
            return normalized_token in path
        return any(
            segment == token_segment
            or (
                token_segment in {"privacy", "returns", "shipping", "terms"}
                and segment.startswith(f"{token_segment}-")
            )
            for segment in path.strip("/").split("/")
        )
    pattern = rf"(?:^|[-_/?#]){re.escape(normalized_token)}(?:[-_/?#]|$)"
    return re.search(pattern, normalized_url) is not None


utility_url_token_matches = _utility_url_token_matches


def title_contains_token_phrase(title: str, token: str) -> bool:
    normalized_title = " ".join(str(title or "").strip().lower().split())
    normalized_token = " ".join(str(token or "").strip().lower().split())
    if not normalized_token or not normalized_title:
        return False
    pattern = rf"(^|[^a-z0-9]){re.escape(normalized_token)}([^a-z0-9]|$)"
    return re.search(pattern, normalized_title) is not None


def _unsupported_non_detail_ecommerce_merchandise_hint(*, title: str, url: str) -> bool:
    normalized_title = " ".join(str(title or "").strip().lower().split())
    normalized_url = str(url or "").strip().lower()
    if not normalized_title or not normalized_url:
        return False
    if _listing_identity_is_editorial(normalized_title, normalized_url):
        return False
    parsed = urlsplit(normalized_url)
    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) < 2:
        return False
    normalized_segments = [segment.strip().lower() for segment in segments]
    if _listing_path_is_non_merchandise(normalized_segments):
        return False
    return _title_matches_merchandise_slug(normalized_title, segments[-1])


def _title_matches_merchandise_slug(title: str, terminal: str) -> bool:
    terminal_tokens = [
        token for token in re.split(r"[^a-z0-9]+", terminal) if len(token) >= 3
    ]
    if len(terminal_tokens) < 2:
        return False
    if any(token in LISTING_NON_LISTING_PATH_TOKENS for token in terminal_tokens):
        return False
    title_tokens = {
        token for token in re.split(r"[^a-z0-9]+", title) if len(token) >= 3
    }
    overlap = sum(token in title_tokens for token in terminal_tokens)
    return overlap >= min(2, len(terminal_tokens))


def _listing_identity_is_editorial(title: str, url: str) -> bool:
    return any(
        pattern.search(title) for pattern in LISTING_EDITORIAL_TITLE_PATTERNS
    ) or any(token in url for token in LISTING_EDITORIAL_URL_TOKENS)


def _listing_path_is_non_merchandise(segments: list[str]) -> bool:
    return bool(
        "categories" in segments[:-1]
        or any(segment in LISTING_NON_LISTING_PATH_TOKENS for segment in segments)
        or any(segment in LISTING_EDITORIAL_PATH_SEGMENTS for segment in segments[:-1])
    )


def _unsupported_detail_like_ecommerce_merchandise_hint(
    *, title: str, url: str
) -> bool:
    normalized_title = " ".join(str(title or "").strip().lower().split())
    normalized_url = str(url or "").strip().lower()
    if not normalized_title or not normalized_url:
        return False
    parsed = urlsplit(normalized_url)
    segments = [segment for segment in parsed.path.split("/") if segment]
    if len(segments) < 2:
        return False
    if segments[-1].isdigit() and len(segments) >= 4:
        return False
    terminal = segments[-1]
    terminal_tokens = [
        token for token in re.split(r"[^a-z0-9]+", terminal) if len(token) >= 3
    ]
    if not terminal_tokens:
        return False
    title_tokens = {
        token for token in re.split(r"[^a-z0-9]+", normalized_title) if len(token) >= 3
    }
    return bool(title_tokens & set(terminal_tokens))


unsupported_non_detail_ecommerce_merchandise_hint = (
    _unsupported_non_detail_ecommerce_merchandise_hint
)

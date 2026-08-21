# ruff: noqa: F401, F821
from __future__ import annotations

__all__ = (
    "listing_record_supported", "job_listing_url_looks_like_posting",
    "job_listing_title_is_hub", "job_listing_url_is_hub",
    "job_listing_url_is_utility", "looks_like_utility_title",
    "looks_like_utility_url", "looks_like_utility_record",
    "title_contains_token_phrase",
)

from . import listing_candidate_ranking as _owner

globals().update({name: value for name, value in vars(_owner).items() if not name.startswith("__")})

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
    if _listing_identity_is_rejected(title, url, page_url, title_is_noise, url_is_structural):
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
    return not is_job_surface and source_kind == "structured_listing" and len(title) >= 12

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
    return url_is_structural(url, page_url) or looks_like_utility_record(title=title, url=url)

def _job_listing_identity_is_utility(title: str, url: str, detail_like: bool) -> bool:
    return bool(job_listing_url_is_utility(url) or job_listing_url_is_hub(url) or (job_listing_title_is_hub(title) and not detail_like))

def _record_has_supporting_listing_signals(
    record: dict[str, Any],
    *,
    surface: str,
) -> bool:
    if any(record.get(field_name) not in (None, "", [], {}) for field_name in ("image_url", "price", "rating", "review_count")):
        return True
    if surface.startswith("job_"):
        return any(record.get(field_name) not in (None, "", [], {}) for field_name in ("company", "location", "salary", "job_type"))
    return record.get("brand") not in (None, "", [], {})

def job_listing_url_looks_like_posting(url: str) -> bool:
    parsed = urlsplit(url.lower())
    segments = [segment.strip().lower() for segment in parsed.path.split("/") if segment.strip()]
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
    terminal_words = [token for token in re.split(r"[^a-z0-9]+", terminal) if len(token) >= 3 and not token.isdigit()]
    return len(terminal_words) >= 2

def job_listing_title_is_hub(title: str) -> bool:
    lowered = clean_text(title).lower()
    if not lowered:
        return False
    if lowered in {"jobs", "careers", "openings"}:
        return True
    if lowered.endswith(tuple(JOB_LISTING_HUB_TITLE_SUFFIXES)) and (
        lowered.startswith(tuple(JOB_LISTING_HUB_TITLE_PREFIXES)) or len([token for token in re.split(r"[^a-z0-9]+", lowered) if token]) <= 4
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
    if terminal.endswith(tuple(JOB_LISTING_HUB_TERMINAL_SUFFIXES)) and not re.search(r"\d{4,}", terminal):
        return True
    return False

def job_listing_url_is_utility(url: str) -> bool:
    return any(_utility_url_token_matches(str(url or "").strip().lower(), token) for token in JOB_UTILITY_URL_TOKENS)

def _job_detail_query_identity(query: str) -> str:
    for key, value in parse_qsl(str(query or ""), keep_blank_values=True):
        normalized_key = str(key or "").strip().lower()
        normalized_value = str(value or "").strip().lower()
        if normalized_key in {"showjob", "jobid", "job_id", "gh_jid"} and normalized_value:
            return f"{normalized_key}={normalized_value}"
    return ""

def _path_segment_tokens(value: str) -> set[str]:
    return {token for token in re.split(r"[\-\.]+", str(value or "").strip().lower()) if token}

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
    if _unsupported_detail_record(supported, detail_like, is_job_surface, detail_like_merchandise):
        return True
    if _unsupported_fallback_record(supported, detail_like, is_job_surface, fallback_merchandise):
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
    return not supported and not detail_like and not is_job_surface and not merchandise_hint

def looks_like_utility_title(title: str) -> bool:
    """Title-only utility check. Used by visual cluster scoring and adapter title gating."""
    normalized_title = " ".join(str(title or "").strip().lower().split())
    if not normalized_title:
        return False
    if any(pattern.search(normalized_title) for pattern in LISTING_UTILITY_TITLE_REGEXES):
        return True
    return any(title_contains_token_phrase(normalized_title, token) for token in LISTING_UTILITY_TITLE_TOKENS)

def looks_like_utility_url(url: str) -> bool:
    """URL-only utility check. Catches utility/help/account/legal anchors and disallowed path segments."""
    normalized_url = str(url or "").strip().lower()
    if not normalized_url:
        return False
    parsed = urlsplit(normalized_url)
    segments = [segment.strip().lower() for segment in parsed.path.split("/") if segment.strip()]
    if len(segments) >= 3 and (
        LISTING_PRODUCT_DETAIL_ID_RE.search(normalized_url) is not None or any(marker in normalized_url for marker in detail_path_hints("ecommerce_detail"))
    ):
        return False
    # A path segment that matches a structural/utility token makes the URL
    # utility UNLESS the terminal segment looks like a product slug (>=3
    # hyphen-separated alphanumeric tokens). Without the exemption, sites
    # like Tire Rack that mount products under `/accessories/<slug>` would
    # lose every product anchor.
    terminal_is_product_slug = _terminal_is_product_slug(segments)
    if not parsed.query and segments and any(segment in LISTING_NON_LISTING_PATH_TOKENS for segment in segments) and not terminal_is_product_slug:
        return True
    return any(_utility_url_token_matches(normalized_url, token) for token in LISTING_UTILITY_URL_TOKENS)

def _terminal_is_product_slug(segments: list[str]) -> bool:
    terminal = segments[-1] if segments else ""
    tokens = [token for token in re.split(r"[-.]+", terminal) if token]
    year_led = bool(tokens and re.fullmatch(YEAR_SLUG_PATTERN, tokens[0]))
    return bool(len(tokens) >= PRODUCT_SLUG_MIN_TERMINAL_TOKENS and any(re.search(r"[a-z]", token) for token in tokens) and "-" in terminal and not year_led)

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
            segment == token_segment or (token_segment in {"privacy", "returns", "shipping", "terms"} and segment.startswith(f"{token_segment}-"))
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
    terminal_tokens = [token for token in re.split(r"[^a-z0-9]+", terminal) if len(token) >= 3]
    if len(terminal_tokens) < 2:
        return False
    if any(token in LISTING_NON_LISTING_PATH_TOKENS for token in terminal_tokens):
        return False
    title_tokens = {token for token in re.split(r"[^a-z0-9]+", title) if len(token) >= 3}
    overlap = sum(token in title_tokens for token in terminal_tokens)
    return overlap >= min(2, len(terminal_tokens))

def _listing_identity_is_editorial(title: str, url: str) -> bool:
    return any(pattern.search(title) for pattern in LISTING_EDITORIAL_TITLE_PATTERNS) or any(token in url for token in LISTING_EDITORIAL_URL_TOKENS)

def _listing_path_is_non_merchandise(segments: list[str]) -> bool:
    return bool(
        "categories" in segments[:-1]
        or any(segment in LISTING_NON_LISTING_PATH_TOKENS for segment in segments)
        or any(segment in LISTING_EDITORIAL_PATH_SEGMENTS for segment in segments[:-1])
    )

def _unsupported_detail_like_ecommerce_merchandise_hint(*, title: str, url: str) -> bool:
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
    terminal_tokens = [token for token in re.split(r"[^a-z0-9]+", terminal) if len(token) >= 3]
    if not terminal_tokens:
        return False
    title_tokens = {token for token in re.split(r"[^a-z0-9]+", normalized_title) if len(token) >= 3}
    return bool(title_tokens & set(terminal_tokens))

unsupported_non_detail_ecommerce_merchandise_hint = _unsupported_non_detail_ecommerce_merchandise_hint

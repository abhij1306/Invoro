from __future__ import annotations

__all__ = (
    "looks_like_utility_record",
    "looks_like_utility_title",
    "looks_like_utility_url",
    "title_contains_token_phrase",
    "unsupported_detail_like_ecommerce_merchandise_hint",
    "unsupported_non_detail_ecommerce_merchandise_hint",
    "utility_url_token_matches",
)

import re
from urllib.parse import urlsplit

from app.services.config.extraction_rules import (
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
from app.services.shared.field_coerce import LISTING_UTILITY_TITLE_REGEXES


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


def unsupported_non_detail_ecommerce_merchandise_hint(*, title: str, url: str) -> bool:
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


def unsupported_detail_like_ecommerce_merchandise_hint(*, title: str, url: str) -> bool:
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

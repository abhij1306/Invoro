from __future__ import annotations

__all__ = (
    "detail_identity_codes_from_record_fields",
    "detail_identity_codes_from_url",
    "detail_identity_codes_match",
    "detail_identity_tokens",
    "detail_query_identity_codes_from_url",
    "detail_segment_code",
    "detail_segment_looks_like_identity_code",
    "detail_url_path_segments",
    "normalized_detail_identity_code",
    "semantic_detail_identity_tokens",
)

import re
from urllib.parse import parse_qsl, urlparse

from app.services.config.extraction_rules import (
    DETAIL_IDENTITY_CODE_MIN_LENGTH,
    DETAIL_IDENTITY_STOPWORDS,
)
from app.services.config.public_record_policy import (
    PUBLIC_RECORD_DETAIL_CANONICAL_QUERY_KEYS,
    PUBLIC_RECORD_DETAIL_CANONICAL_QUERY_PREFIXES,
)
from app.services.shared.field_coerce import clean_text, text_or_none

DETAIL_IDENTITY_QUERY_KEYS = frozenset(
    str(value).strip().lower()
    for value in tuple(PUBLIC_RECORD_DETAIL_CANONICAL_QUERY_KEYS or ())
    if str(value).strip()
)
DETAIL_IDENTITY_QUERY_PREFIXES = tuple(
    str(value).strip().lower()
    for value in tuple(PUBLIC_RECORD_DETAIL_CANONICAL_QUERY_PREFIXES or ())
    if str(value).strip()
)
LOWER_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")
MIXED_NON_ALNUM_RE = re.compile(r"[^A-Za-z0-9]+")
HTML_SUFFIX_RE = re.compile(r"\.htm(?:l)?$", re.IGNORECASE)


def detail_url_path_segments(url: str) -> list[str]:
    parsed = urlparse(str(url or ""))
    segments = [
        segment for segment in str(parsed.path or "").strip("/").split("/") if segment
    ]
    fragment = str(parsed.fragment or "").strip()
    if fragment:
        fragment_path = fragment.split("?", 1)[0].split("&", 1)[0].strip()
        if "/" in fragment_path:
            segments.extend(
                segment for segment in fragment_path.strip("!/").split("/") if segment
            )
    return segments


def detail_identity_tokens(value: object) -> set[str]:
    cleaned = clean_text(value).lower()
    return {
        token
        for token in LOWER_NON_ALNUM_RE.split(cleaned)
        if len(token) >= 3 and token not in DETAIL_IDENTITY_STOPWORDS
    }


def semantic_detail_identity_tokens(value: object) -> set[str]:
    return {
        token
        for token in detail_identity_tokens(value)
        if re.search(r"[a-z]", token) and not re.search(r"\d", token)
    }


def detail_identity_codes_from_url(url: object) -> set[str]:
    text = text_or_none(url)
    if not text:
        return set()
    parsed = urlparse(text)
    codes: set[str] = set()
    segments = detail_url_path_segments(text)
    terminal = HTML_SUFFIX_RE.sub("", segments[-1]) if segments else ""
    code_like_terminal = detail_segment_code(terminal)
    if code_like_terminal:
        codes.add(code_like_terminal)
    # Embedded URL identity is authoritative only for numeric product codes in
    # the terminal segment (for example ``productpage.1317259001.html``).
    # Mixed slug tokens such as ``widget2025`` are descriptive, not identifiers.
    for match in re.findall(rf"\d{{{DETAIL_IDENTITY_CODE_MIN_LENGTH},}}", terminal):
        normalized = normalized_detail_identity_code(match)
        if normalized:
            codes.add(normalized)
    for key, _value in parse_qsl(parsed.query, keep_blank_values=True):
        match = re.match(
            r"dwvar_([A-Za-z0-9][A-Za-z0-9_-]{6,}[A-Za-z0-9])_",
            str(key or ""),
            flags=re.I,
        )
        if match is None:
            continue
        normalized = detail_segment_code(match.group(1))
        if normalized:
            codes.add(normalized)
    codes.update(detail_query_identity_codes_from_url(text))
    return codes


def detail_query_identity_codes_from_url(url: object) -> set[str]:
    text = text_or_none(url)
    if not text:
        return set()
    parsed = urlparse(text)
    codes: set[str] = set()
    for key, value in parse_qsl(parsed.query, keep_blank_values=False):
        normalized_key = str(key or "").strip().lower()
        if not normalized_key:
            continue
        if normalized_key in DETAIL_IDENTITY_QUERY_KEYS or any(
            normalized_key.startswith(prefix)
            for prefix in DETAIL_IDENTITY_QUERY_PREFIXES
        ):
            normalized_value = detail_segment_code(value)
            if normalized_value:
                codes.add(normalized_value)
    return codes


def detail_identity_codes_from_record_fields(record: dict[str, object]) -> set[str]:
    codes: set[str] = set()
    for field_name in ("sku", "product_id", "variant_id", "part_number", "barcode"):
        normalized = normalized_detail_identity_code(record.get(field_name))
        if normalized:
            codes.add(normalized)
    return codes


def detail_segment_looks_like_identity_code(value: object) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if re.fullmatch(r"[A-Za-z0-9]+(?:[-_][A-Za-z0-9]+){0,2}", text) is None:
        return False
    return normalized_detail_identity_code(text) is not None


def detail_segment_code(value: object) -> str | None:
    text = str(value or "").strip()
    if not detail_segment_looks_like_identity_code(text):
        return None
    return normalized_detail_identity_code(text)


def normalized_detail_identity_code(value: object) -> str | None:
    text = MIXED_NON_ALNUM_RE.sub("", str(value or "")).upper()
    if len(text) < DETAIL_IDENTITY_CODE_MIN_LENGTH:
        return None
    if not re.search(r"\d", text):
        return None
    return text


def detail_identity_codes_match(
    expected_codes: set[str],
    candidate_codes: set[str],
) -> bool:
    if not expected_codes or not candidate_codes:
        return False
    return not expected_codes.isdisjoint(candidate_codes)

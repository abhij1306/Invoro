from __future__ import annotations

__all__ = (
    "clean_materials_pollution",
    "cookie_disclosure_text_patterns",
    "cross_product_text_generic_tokens",
    "cross_product_text_type_tokens",
    "detail_long_text_chunk_has_product_name_shape",
    "detail_long_text_chunk_is_document_label",
    "detail_long_text_chunk_is_legal_tail",
    "detail_long_text_chunk_is_other_product",
    "detail_long_text_chunk_is_variant_title",
    "detail_long_text_is_cookie_disclosure_dump",
    "detail_long_text_is_document_label_cluster",
    "detail_long_text_is_fulfillment_only",
    "detail_long_text_is_guide_or_glossary_dump",
    "detail_long_text_is_numeric_sequence",
    "detail_product_text_tokens",
    "document_link_label_patterns",
    "fulfillment_long_text_patterns",
    "fulfillment_only_long_text_phrases",
    "guide_glossary_heading_tokens",
    "guide_glossary_text_patterns",
    "materials_pollution_tokens",
    "text_is_structured_json_array",
)

import json
import re
from collections.abc import Iterable

from app.services.config.extraction_rules import (
    DETAIL_COOKIE_DISCLOSURE_TEXT_PATTERNS,
    DETAIL_CROSS_PRODUCT_TEXT_GENERIC_TOKENS,
    DETAIL_CROSS_PRODUCT_TEXT_TYPE_TOKENS,
    DETAIL_DOCUMENT_LINK_LABEL_PATTERNS,
    DETAIL_FULFILLMENT_ONLY_LONG_TEXT_PHRASES,
    DETAIL_FULFILLMENT_LONG_TEXT_PATTERNS,
    DETAIL_GUIDE_GLOSSARY_HEADING_MIN_HITS,
    DETAIL_GUIDE_GLOSSARY_HEADING_TOKENS,
    DETAIL_GUIDE_GLOSSARY_TEXT_PATTERNS,
    DETAIL_LEGAL_TAIL_PATTERNS,
    DETAIL_LONG_TEXT_DISCLAIMER_PATTERNS,
    DETAIL_MATERIALS_COMPOSITION_PATTERN,
    DETAIL_MATERIALS_EDITORIAL_HEAD_THRESHOLD,
    DETAIL_MATERIALS_EDITORIAL_LENGTH_THRESHOLD,
    DETAIL_MATERIALS_POLLUTION_TOKENS,
    DETAIL_MATERIALS_ZERO_PERCENT_PATTERN,
    LONG_TEXT_MAX_WORDS,
    LONG_TEXT_MIN_WORDS,
    LONG_TEXT_PREFIXES,
    TOKEN_MIN_LEN_CHUNK,
    TOKEN_MIN_LEN_DISTINCTIVE,
)
from app.services.shared.field_coerce import clean_text
from app.services.shared.regex_patterns import compile_regex_patterns

document_link_label_patterns = compile_regex_patterns(
    DETAIL_DOCUMENT_LINK_LABEL_PATTERNS or ()
)
fulfillment_only_long_text_phrases = frozenset(
    clean_text(phrase).lower()
    for phrase in tuple(DETAIL_FULFILLMENT_ONLY_LONG_TEXT_PHRASES or ())
    if clean_text(phrase)
)
fulfillment_long_text_patterns = compile_regex_patterns(
    DETAIL_FULFILLMENT_LONG_TEXT_PATTERNS or ()
)
guide_glossary_text_patterns = compile_regex_patterns(
    DETAIL_GUIDE_GLOSSARY_TEXT_PATTERNS or ()
)
guide_glossary_heading_tokens = frozenset(
    clean_text(value).lower()
    for value in tuple(DETAIL_GUIDE_GLOSSARY_HEADING_TOKENS or ())
    if clean_text(value)
)
materials_pollution_tokens = frozenset(
    clean_text(token).casefold()
    for token in tuple(DETAIL_MATERIALS_POLLUTION_TOKENS or ())
    if clean_text(token)
)
_MATERIALS_ZERO_PERCENT_PATTERN = re.compile(
    str(DETAIL_MATERIALS_ZERO_PERCENT_PATTERN or ""), re.I
)
cross_product_text_type_tokens = frozenset(
    clean_text(value).lower()
    for value in tuple(DETAIL_CROSS_PRODUCT_TEXT_TYPE_TOKENS or ())
    if clean_text(value)
)
cross_product_text_generic_tokens = frozenset(
    clean_text(value).lower()
    for value in tuple(DETAIL_CROSS_PRODUCT_TEXT_GENERIC_TOKENS or ())
    if clean_text(value)
)
cookie_disclosure_text_patterns = compile_regex_patterns(
    DETAIL_COOKIE_DISCLOSURE_TEXT_PATTERNS or ()
)
long_text_disclaimer_patterns = compile_regex_patterns(
    DETAIL_LONG_TEXT_DISCLAIMER_PATTERNS or ()
)
_guide_glossary_heading_min_hits = int(DETAIL_GUIDE_GLOSSARY_HEADING_MIN_HITS)
_long_text_min_words = int(LONG_TEXT_MIN_WORDS)
_long_text_max_words = int(LONG_TEXT_MAX_WORDS)
_long_text_prefixes = tuple(
    clean_text(prefix).lower()
    for prefix in tuple(LONG_TEXT_PREFIXES or ())
    if clean_text(prefix)
)
_token_min_len_distinctive = int(TOKEN_MIN_LEN_DISTINCTIVE)
_token_min_len_chunk = int(TOKEN_MIN_LEN_CHUNK)
_legal_tail_patterns = DETAIL_LEGAL_TAIL_PATTERNS or {}
_legal_tail_contains = tuple(
    str(value) for value in _legal_tail_patterns.get("contains", ())
)
_legal_tail_digit_contains = tuple(
    str(value) for value in _legal_tail_patterns.get("digit_contains", ())
)
_legal_tail_exact = frozenset(
    str(value) for value in _legal_tail_patterns.get("exact", ())
)


def _normalize_legal_tail_all_contains(value: object) -> tuple[tuple[str, ...], ...]:
    if isinstance(value, str):
        return ((value,),)
    if not isinstance(value, Iterable):
        return ()
    groups: list[tuple[str, ...]] = []
    for group in tuple(value):
        if isinstance(group, str):
            items = (group,)
        elif isinstance(group, Iterable):
            try:
                items = tuple(group)
            except TypeError as exc:
                raise ValueError(
                    "DETAIL_LEGAL_TAIL_PATTERNS all_contains must be strings"
                ) from exc
        else:
            raise ValueError("DETAIL_LEGAL_TAIL_PATTERNS all_contains must be strings")
        if not all(isinstance(item, str) for item in items):
            raise ValueError("DETAIL_LEGAL_TAIL_PATTERNS all_contains must be strings")
        groups.append(items)
    return tuple(groups)


_legal_tail_all_contains = _normalize_legal_tail_all_contains(
    _legal_tail_patterns.get("all_contains", ())
)


def clean_materials_pollution(value: object) -> str:
    text = clean_text(value)
    if not text:
        return ""
    stripped = text.lstrip()
    if _materials_text_is_rejected(text, stripped):
        return ""
    # Editorial / glossary blocks (e.g. Todd Snyder seersucker page) sneak
    # into materials when the DOM selector pulls a description accordion.
    # Real fabric composition leads with a percent token within the first
    # ~200 characters. When the head of a long string lacks a composition
    # pattern but the tail contains one, keep only the trailing composition.
    composition_repaired = _materials_extract_trailing_composition(text)
    if composition_repaired is not None:
        text = composition_repaired
    text = _materials_trim_to_first_specifics(text)
    chunks = [
        clean_text(chunk)
        for chunk in re.split(r"(?<=[.!?])\s+|\s+:\s+|\n+", text)
        if clean_text(chunk)
    ]
    kept = [chunk for chunk in chunks if _materials_chunk_is_usable(chunk)]
    cleaned = _dedupe_adjacent_material_chunks(" ".join(kept).strip())
    while True:
        parts = cleaned.split(maxsplit=1)
        if (
            not parts
            or parts[0].casefold().strip(":") not in materials_pollution_tokens
        ):
            return _dedupe_adjacent_material_chunks(cleaned)
        cleaned = parts[1] if len(parts) > 1 else ""


def _materials_text_is_rejected(text: str, stripped: str) -> bool:
    return bool(
        stripped.startswith("{")
        or text_is_structured_json_array(stripped)
        or detail_long_text_is_fulfillment_only(text)
        or any(pattern.search(text) for pattern in long_text_disclaimer_patterns)
    )


def _materials_chunk_is_usable(chunk: str) -> bool:
    return clean_text(chunk).casefold() not in materials_pollution_tokens and not bool(
        _MATERIALS_ZERO_PERCENT_PATTERN.search(chunk)
    )


_MATERIALS_COMPOSITION_PATTERN = re.compile(
    str(DETAIL_MATERIALS_COMPOSITION_PATTERN or ""),
    re.I,
)
_materials_editorial_head_len = int(DETAIL_MATERIALS_EDITORIAL_HEAD_THRESHOLD)
_materials_editorial_min_len = int(DETAIL_MATERIALS_EDITORIAL_LENGTH_THRESHOLD)


def _materials_extract_trailing_composition(text: str) -> str | None:
    """Salvage trailing fabric composition from an editorial-prefixed block.

    Real composition starts with a percent token (``97% Cotton, 3% Elastane``).
    When the first ~200 chars lack any composition pattern but the full
    string is long and ends with one or more composition entries, replace
    the value with just the trailing composition slice.

    Returns the trimmed composition text, ``""`` when an editorial block
    should be discarded, or ``None`` when no salvage is needed because the
    head already has composition.
    """
    if len(text) <= _materials_editorial_min_len:
        return None
    head = text[:_materials_editorial_head_len]
    if _MATERIALS_COMPOSITION_PATTERN.search(head):
        return None
    matches = list(_MATERIALS_COMPOSITION_PATTERN.finditer(text))
    if not matches:
        # Empty string means discard this editorial block; None means keep original.
        return ""
    first = matches[0]
    return text[first.start() :].strip() or ""


_MATERIALS_HEAD_TRIM_TERMINATORS_RE = re.compile(
    r"\b(?:Made\s+in|Garment\s+Made\s+in|Fabric\s+(?:From|Made\s+in)|"
    r"Dry\s+Clean(?:\s+Only)?|Machine\s+Wash|Hand\s+Wash|Wash\s+Cold|"
    r"Tumble\s+Dry|Do\s+Not\s+Bleach)\b[^.]{0,80}\.",
    re.I,
)


def _materials_trim_to_first_specifics(text: str) -> str:
    """When a long materials field starts with composition + care/origin
    info but trails into a glossary of unrelated fabrics, keep only the
    first composition+origin sentences.

    Heuristic: locate the FIRST occurrence of a care/origin terminator
    (``Made in X.``, ``Dry Clean Only.``, ``Machine Wash.`` etc.); cut
    just after that period. If none is found within the first 400 chars,
    fall back to the original text.
    """
    if len(text) <= 200:
        return text
    if not _MATERIALS_COMPOSITION_PATTERN.match(text):
        return text
    match = _MATERIALS_HEAD_TRIM_TERMINATORS_RE.search(text[:400])
    if match is None:
        return text
    if any(
        item.start() > match.end()
        for item in _MATERIALS_COMPOSITION_PATTERN.finditer(text)
    ):
        return text
    cut = text[: match.end()].strip()
    return cut or text


def _dedupe_adjacent_material_chunks(text: str) -> str:
    cleaned = clean_text(text)
    if not cleaned:
        return ""
    chunks = [
        clean_text(chunk)
        for chunk in re.split(r"(?<=[.;!?])\s+", cleaned)
        if clean_text(chunk)
    ]
    if len(chunks) < 2:
        return cleaned
    deduped: list[str] = []
    for chunk in chunks:
        if deduped and chunk.casefold() == deduped[-1].casefold():
            continue
        deduped.append(chunk)
    return " ".join(deduped)


def detail_long_text_is_numeric_sequence(text: str) -> bool:
    tokens = text.split()
    if len(tokens) < 5 or any(not token.isdigit() for token in tokens):
        return False
    numbers = [int(token) for token in tokens]
    return numbers == list(range(numbers[0], numbers[0] + len(numbers)))


def detail_long_text_is_fulfillment_only(text: str) -> bool:
    lowered = clean_text(text).lower().strip(" .;:")
    if lowered in fulfillment_only_long_text_phrases:
        return True
    return any(pattern.search(lowered) for pattern in fulfillment_long_text_patterns)


def detail_long_text_is_guide_or_glossary_dump(text: str) -> bool:
    cleaned = clean_text(text)
    if not cleaned:
        return False
    if any(pattern.search(cleaned) for pattern in guide_glossary_text_patterns):
        return True
    lowered = cleaned.lower()
    words = set(re.findall(r"\w+", lowered))
    heading_hits = sum(1 for token in guide_glossary_heading_tokens if token in words)
    return heading_hits >= _guide_glossary_heading_min_hits


def text_is_structured_json_array(text: str) -> bool:
    if not text.startswith("["):
        return False
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        return False
    return isinstance(parsed, list)


def detail_long_text_is_cookie_disclosure_dump(text: str) -> bool:
    cleaned = clean_text(text)
    return bool(
        cleaned
        and any(pattern.search(cleaned) for pattern in cookie_disclosure_text_patterns)
    )


def detail_long_text_chunk_is_legal_tail(chunk: str) -> bool:
    lowered = chunk.lower()
    return (
        any(pattern in lowered for pattern in _legal_tail_contains)
        or (
            any(pattern in lowered for pattern in _legal_tail_digit_contains)
            and any(char.isdigit() for char in chunk)
        )
        or any(
            all(pattern in lowered for pattern in group)
            for group in _legal_tail_all_contains
        )
        or lowered in _legal_tail_exact
    )


def detail_long_text_chunk_is_document_label(chunk: str) -> bool:
    normalized = clean_text(chunk)
    if not normalized:
        return False
    return any(
        pattern.fullmatch(normalized) for pattern in document_link_label_patterns
    )


def detail_long_text_is_document_label_cluster(text: str) -> bool:
    normalized = clean_text(text)
    if not normalized:
        return False
    normalized = re.sub(r"\b(guide|label|manual)\b\s+", r"\1\n", normalized, flags=re.I)
    parts = [clean_text(part) for part in normalized.splitlines() if clean_text(part)]
    return len(parts) >= 2 and all(
        detail_long_text_chunk_is_document_label(part) for part in parts
    )


def detail_long_text_chunk_is_variant_title(chunk: str, *, title: str) -> bool:
    if not title:
        return False
    normalized_chunk = clean_text(chunk)
    if len(normalized_chunk.split()) > 16:
        return False
    if " - " not in normalized_chunk:
        return False
    title_tokens = detail_product_text_tokens(title)
    chunk_tokens = detail_product_text_tokens(normalized_chunk)
    return bool(title_tokens) and len(title_tokens & chunk_tokens) >= max(
        1,
        min(2, len(title_tokens)),
    )


def detail_long_text_chunk_is_other_product(chunk: str, *, title: str) -> bool:
    if not title:
        return False
    normalized_chunk = clean_text(chunk)
    words = normalized_chunk.split()
    if len(words) < _long_text_min_words or len(words) > _long_text_max_words:
        return False
    if not detail_long_text_chunk_has_product_name_shape(chunk):
        return False
    chunk_tokens = detail_product_text_tokens(normalized_chunk)
    if not (chunk_tokens & cross_product_text_type_tokens):
        return False
    title_tokens = detail_product_text_tokens(title)
    distinctive_title_tokens = _distinctive_product_tokens(
        title_tokens, _token_min_len_distinctive
    )
    lowered_chunk = normalized_chunk.lower()
    if chunk_tokens & distinctive_title_tokens and lowered_chunk.startswith(
        _long_text_prefixes
    ):
        return False
    if not distinctive_title_tokens or chunk_tokens & distinctive_title_tokens:
        distinctive_chunk_tokens = _distinctive_product_tokens(
            chunk_tokens, _token_min_len_chunk
        )
        return bool(
            distinctive_chunk_tokens - title_tokens
            and not distinctive_title_tokens <= chunk_tokens
        )
    distinctive_chunk_tokens = _distinctive_product_tokens(
        chunk_tokens, _token_min_len_chunk
    )
    return bool(distinctive_chunk_tokens - title_tokens)


def _distinctive_product_tokens(tokens: set[str], minimum_length: int) -> set[str]:
    return {
        token
        for token in tokens
        if len(token) >= minimum_length
        and token not in cross_product_text_generic_tokens
    }


def detail_product_text_tokens(value: str) -> set[str]:
    tokens = {
        token
        for token in re.split(r"[^a-z0-9]+", clean_text(value).lower())
        if token and not token.isdigit()
    }
    tokens.update(
        token[:-1] for token in list(tokens) if len(token) > 4 and token.endswith("s")
    )
    return tokens


def detail_long_text_chunk_has_product_name_shape(chunk: str) -> bool:
    words = re.findall(r"[A-Za-z][A-Za-z'’-]*", str(chunk or ""))
    if not words:
        return False
    capitalized = [word for word in words if word[:1].isupper()]
    non_initial_capitalized = [word for word in words[1:] if word[:1].isupper()]
    if len(capitalized) >= 2 or non_initial_capitalized:
        return True
    return bool(
        words
        and words[0].lower() == "the"
        and len(words) > 1
        and words[1][:1].isupper()
    )

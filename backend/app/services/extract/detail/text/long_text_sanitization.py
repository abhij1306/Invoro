# ruff: noqa: F401, F821
from __future__ import annotations

__all__ = (
    "sanitize_detail_long_text", "sanitize_detail_features",
    "detail_long_text_chunk_looks_truncated",
    "detail_long_text_chunk_is_variant_size_sequence",
    "detail_long_text_is_numeric_sequence", "detail_long_text_is_fulfillment_only",
    "detail_long_text_is_guide_or_glossary_dump",
)

from . import sanitizer as _owner

globals().update({name: value for name, value in vars(_owner).items() if not name.startswith("__")})

def sanitize_detail_long_text(
    text: str,
    *,
    title: str,
    protected_identity_tokens: set[str] | None = None,
) -> str:
    cleaned_text = _strip_long_text_ui_tail(_strip_leading_attribute_blob(_strip_bracket_artifact_noise(clean_text(text))))
    cleaned_text = _strip_long_text_substring_noise(cleaned_text)
    cleaned_text = _trim_repeated_title_lead(cleaned_text, title=title)
    if _detail_long_text_is_rejected(cleaned_text, text):
        return ""
    chunks = [clean_text(chunk) for chunk in re.split(r"(?<=[.!?])\s+|\s+:\s+|\n+", cleaned_text) if clean_text(chunk)]
    seen: set[str] = set()
    kept: list[str] = []
    protected_tokens = protected_identity_tokens or set()
    for chunk in chunks:
        chunk = _kept_detail_long_text_chunk(chunk, title, protected_tokens, seen)
        if not chunk:
            continue
        seen.add(chunk.lower())
        kept.append(chunk)
    if kept and all(detail_long_text_chunk_is_document_label(chunk) for chunk in kept):
        return ""
    return " ".join(kept).strip()

def _detail_long_text_is_rejected(cleaned: str, original: str) -> bool:
    return bool(
        _text_is_structured_object_repr(cleaned)
        or _text_is_structured_json_array(cleaned)
        or cleaned.lower() in low_signal_long_text_values
        or detail_long_text_is_numeric_sequence(cleaned)
        or detail_long_text_is_fulfillment_only(cleaned)
        or detail_long_text_is_guide_or_glossary_dump(cleaned)
        or detail_long_text_is_cookie_disclosure_dump(cleaned)
        or detail_long_text_is_document_label_cluster(original)
    )

def _detail_long_text_chunk_is_rejected(chunk: str) -> bool:
    return detail_long_text_chunk_is_legal_tail(chunk) or any(pattern.search(chunk) for pattern in long_text_disclaimer_patterns)

def _kept_detail_long_text_chunk(chunk: str, title: str, protected_tokens: set[str], seen: set[str]) -> str:
    cleaned = _strip_repeated_prompt_text(chunk)
    if not cleaned or cleaned.lower() in seen or _detail_long_text_chunk_is_rejected(cleaned):
        return ""
    protected = bool(protected_tokens & detail_product_text_tokens(cleaned))
    if not protected and (detail_long_text_chunk_is_variant_title(cleaned, title=title) or detail_long_text_chunk_is_other_product(cleaned, title=title)):
        return ""
    if detail_long_text_chunk_is_variant_size_sequence(cleaned) or detail_long_text_chunk_looks_truncated(cleaned):
        return ""
    return cleaned

def _strip_long_text_substring_noise(text: str) -> str:
    cleaned = clean_text(text)
    if not cleaned:
        return ""
    for pattern in long_text_substring_remove_patterns:
        cleaned = clean_text(pattern.sub("", cleaned))
    return cleaned

def _strip_repeated_prompt_text(text: str) -> str:
    cleaned = clean_text(text)
    for prompt in long_text_repeated_prompts:
        if cleaned.count(prompt) >= 2:
            first_end = cleaned.find(prompt) + len(prompt)
            cleaned = clean_text(cleaned[:first_end] + cleaned[first_end:].replace(prompt, ""))
    return cleaned

def _trim_repeated_title_lead(text: str, *, title: str) -> str:
    cleaned = clean_text(text)
    title_lead = clean_text(str(title or "").split("|", 1)[0])
    if len(title_lead.split()) < 3:
        return cleaned
    lowered = cleaned.casefold()
    needle = title_lead.casefold()
    first = lowered.find(needle)
    if first != 0:
        return cleaned
    second = lowered.find(needle, first + len(needle))
    if second <= first:
        return cleaned
    if re.search(r"[.!?]", cleaned[len(title_lead) : second]):
        return cleaned
    return clean_text(cleaned[:second])

def sanitize_detail_features(value: object, *, title: str) -> list[str]:
    rows = value if isinstance(value, list) else [value]
    seen: set[str] = set()
    cleaned_rows: list[str] = []
    for row in rows:
        text = text_or_none(row)
        if not text:
            continue
        cleaned = sanitize_detail_long_text(text, title=title)
        lowered = cleaned.lower()
        if not cleaned or any(pattern.search(cleaned) for pattern in long_text_disclaimer_patterns):
            continue
        if any(pattern.fullmatch(cleaned) for pattern in feature_row_noise_patterns):
            continue
        if lowered in seen:
            continue
        seen.add(lowered)
        cleaned_rows.append(cleaned)
    return cleaned_rows

def detail_long_text_chunk_looks_truncated(text: str) -> bool:
    cleaned = clean_text(text).rstrip()
    if not cleaned:
        return False
    if cleaned.endswith(("...", "…")):
        return True
    if cleaned[-1] in ".!?":
        return False
    tokens = re.findall(r"[A-Za-z0-9']+", cleaned.casefold())
    return bool(tokens) and tokens[-1] in DETAIL_LONG_TEXT_TRUNCATED_TAIL_TOKENS

def detail_long_text_chunk_is_variant_size_sequence(text: str) -> bool:
    tokens = clean_text(text).split()
    if len(tokens) < DETAIL_VARIANT_SIZE_SEQUENCE_MIN_COUNT:
        return False
    values: list[float] = []
    for token in tokens:
        if not re.fullmatch(r"\d+(?:\.5)?", token):
            return False
        values.append(float(token))
    return values == sorted(values) and len(set(values)) >= DETAIL_VARIANT_SIZE_SEQUENCE_MIN_COUNT

_BRACKET_RUN_RE = re.compile(r"(?:\[\s*){2,}|(?:\]\s*){2,}")
_BRACKETS_RE = re.compile(r"[\[\]]+")
_LEADING_ATTRIBUTE_BLOB_RE = re.compile(str(DETAIL_LONG_TEXT_LEADING_ATTRIBUTE_BLOB_PATTERN), re.I)

def _text_is_structured_object_repr(text: str) -> bool:
    if len(text) > MAX_STRUCTURED_TEXT_LENGTH:
        return False
    cleaned = text.strip()
    if not (cleaned.startswith("{") and cleaned.endswith("}")):
        return False
    try:
        parsed = ast.literal_eval(cleaned)
    except (ValueError, SyntaxError):
        try:
            parsed = json.loads(cleaned)
        except (TypeError, ValueError):
            return False
    return isinstance(parsed, dict)

def _strip_bracket_artifact_noise(text: str) -> str:
    """Recover prose from Vans/Brinkhaus-style `[[[Style]] [[SKU]] [prose]` artifacts."""
    if not text or not _BRACKET_RUN_RE.search(text):
        return text
    # Recursive strip for extreme nesting like [ [ [ ... ] ] ]
    current = text
    while _BRACKET_RUN_RE.search(current):
        stripped = _BRACKETS_RE.sub(" ", current)
        if stripped == current:
            break
        current = stripped
    candidates: list[tuple[int, int, str]] = []
    for source in (text, current):
        for index, part in enumerate(_BRACKETS_RE.split(source)):
            cleaned = clean_text(part)
            if not cleaned:
                continue
            word_count = len(cleaned.split())
            if word_count >= _bracket_prose_min_words:
                candidates.append((word_count, index, cleaned))
        if candidates:
            break
    if candidates:
        candidates.sort(key=lambda item: (-item[0], item[1]))
        return candidates[0][2]
    return clean_text(current)

def _strip_leading_attribute_blob(text: str) -> str:
    cleaned = clean_text(text)
    if not cleaned:
        return ""
    stripped = clean_text(_LEADING_ATTRIBUTE_BLOB_RE.sub("", cleaned, count=1))
    return stripped or cleaned

def _strip_long_text_ui_tail(text: str) -> str:
    cleaned = clean_text(text)
    lowered = cleaned.lower()
    for phrase in _long_text_ui_tail_phrases:
        if lowered == phrase:
            return ""
        suffix = f" {phrase}"
        if lowered.endswith(suffix):
            return clean_text(cleaned[: -len(suffix)])
    return cleaned

def _clean_materials_pollution(value: object) -> str:
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
    chunks = [clean_text(chunk) for chunk in re.split(r"(?<=[.!?])\s+|\s+:\s+|\n+", text) if clean_text(chunk)]
    kept = [chunk for chunk in chunks if _materials_chunk_is_usable(chunk)]
    cleaned = _dedupe_adjacent_material_chunks(" ".join(kept).strip())
    while True:
        parts = cleaned.split(maxsplit=1)
        if not parts or parts[0].casefold().strip(":") not in materials_pollution_tokens:
            return _dedupe_adjacent_material_chunks(cleaned)
        cleaned = parts[1] if len(parts) > 1 else ""

def _materials_text_is_rejected(text: str, stripped: str) -> bool:
    return bool(
        stripped.startswith("{")
        or _text_is_structured_json_array(stripped)
        or detail_long_text_is_fulfillment_only(text)
        or any(pattern.search(text) for pattern in long_text_disclaimer_patterns)
    )

def _materials_chunk_is_usable(chunk: str) -> bool:
    return clean_text(chunk).casefold() not in materials_pollution_tokens and not bool(_MATERIALS_ZERO_PERCENT_PATTERN.search(chunk))

_MATERIALS_COMPOSITION_PATTERN = re.compile(
    str(DETAIL_MATERIALS_COMPOSITION_PATTERN),
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
    if any(item.start() > match.end() for item in _MATERIALS_COMPOSITION_PATTERN.finditer(text)):
        return text
    cut = text[: match.end()].strip()
    return cut or text

def _dedupe_adjacent_material_chunks(text: str) -> str:
    cleaned = clean_text(text)
    if not cleaned:
        return ""
    chunks = [clean_text(chunk) for chunk in re.split(r"(?<=[.;!?])\s+", cleaned) if clean_text(chunk)]
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

def _text_is_structured_json_array(text: str) -> bool:
    if not text.startswith("["):
        return False
    try:
        parsed = json.loads(text)
    except (TypeError, ValueError):
        return False
    return isinstance(parsed, list)

def detail_long_text_is_cookie_disclosure_dump(text: str) -> bool:
    cleaned = clean_text(text)
    return bool(cleaned and any(pattern.search(cleaned) for pattern in cookie_disclosure_text_patterns))

def detail_long_text_chunk_is_legal_tail(chunk: str) -> bool:
    lowered = chunk.lower()
    return (
        any(pattern in lowered for pattern in _legal_tail_contains)
        or (any(pattern in lowered for pattern in _legal_tail_digit_contains) and any(char.isdigit() for char in chunk))
        or any(all(pattern in lowered for pattern in group) for group in _legal_tail_all_contains)
        or lowered in _legal_tail_exact
    )

def detail_long_text_chunk_is_document_label(chunk: str) -> bool:
    normalized = clean_text(chunk)
    if not normalized:
        return False
    return any(pattern.fullmatch(normalized) for pattern in document_link_label_patterns)

def detail_long_text_is_document_label_cluster(text: str) -> bool:
    normalized = clean_text(text)
    if not normalized:
        return False
    normalized = re.sub(r"\b(guide|label|manual)\b\s+", r"\1\n", normalized, flags=re.I)
    parts = [clean_text(part) for part in normalized.splitlines() if clean_text(part)]
    return len(parts) >= 2 and all(detail_long_text_chunk_is_document_label(part) for part in parts)

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
    distinctive_title_tokens = _distinctive_product_tokens(title_tokens, _token_min_len_distinctive)
    lowered_chunk = normalized_chunk.lower()
    if chunk_tokens & distinctive_title_tokens and lowered_chunk.startswith(_long_text_prefixes):
        return False
    if not distinctive_title_tokens or chunk_tokens & distinctive_title_tokens:
        distinctive_chunk_tokens = _distinctive_product_tokens(chunk_tokens, _token_min_len_chunk)
        return bool(distinctive_chunk_tokens - title_tokens and not distinctive_title_tokens <= chunk_tokens)
    distinctive_chunk_tokens = _distinctive_product_tokens(chunk_tokens, _token_min_len_chunk)
    return bool(distinctive_chunk_tokens - title_tokens)

def _distinctive_product_tokens(tokens: set[str], minimum_length: int) -> set[str]:
    return {token for token in tokens if len(token) >= minimum_length and token not in cross_product_text_generic_tokens}

def detail_product_text_tokens(value: str) -> set[str]:
    tokens = {token for token in re.split(r"[^a-z0-9]+", clean_text(value).lower()) if token and not token.isdigit()}
    tokens.update(token[:-1] for token in list(tokens) if len(token) > 4 and token.endswith("s"))
    return tokens

def detail_long_text_chunk_has_product_name_shape(chunk: str) -> bool:
    words = re.findall(r"[A-Za-z][A-Za-z'’-]*", str(chunk or ""))
    if not words:
        return False
    capitalized = [word for word in words if word[:1].isupper()]
    non_initial_capitalized = [word for word in words[1:] if word[:1].isupper()]
    if len(capitalized) >= 2 or non_initial_capitalized:
        return True
    return bool(words and words[0].lower() == "the" and len(words) > 1 and words[1][:1].isupper())

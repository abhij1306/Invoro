# ruff: noqa: F401, F821
from __future__ import annotations

__all__ = (
    "detail_identity_codes_from_record_fields", "detail_identity_codes_from_url",
    "detail_query_identity_codes_from_url", "detail_identity_tokens",
    "detail_redirect_identity_is_mismatched", "detail_slug_title_fallback_from_url",
    "detail_title_from_url", "detail_url_candidate_is_low_signal",
    "detail_url_is_collection_like", "detail_url_is_utility",
    "detail_url_looks_like_product", "detail_url_matches_requested_identity",
    "preferred_detail_identity_url", "record_matches_requested_detail_identity",
    "semantic_detail_identity_tokens",
)

from . import core as _owner

globals().update({
    name: value
    for name, value in vars(_owner).items()
    if not name.startswith("__")
})

def _detail_title_from_url(page_url: str) -> str | None:
    path_segments = _detail_url_path_segments(page_url)
    if not path_segments:
        return None
    generic_terminal_tokens = set(DETAIL_GENERIC_TERMINAL_TOKENS)
    for index in range(len(path_segments) - 1, -1, -1):
        segment = path_segments[index]
        terminal = _HTML_SUFFIX_RE.sub("", segment)
        if _detail_segment_is_shop_merchant_namespace(path_segments, index):
            continue
        if _detail_terminal_is_ignored(
            terminal,
            generic_terminal_tokens=generic_terminal_tokens,
        ):
            continue
        if _detail_segment_looks_like_identity_code(terminal):
            if _detail_terminal_parent_is_collection(path_segments, index):
                return None
            continue
        title = clean_text(_SLUG_SEPARATOR_RE.sub(" ", terminal))
        if title and not is_title_noise(title):
            return title
    return None

def _detail_terminal_embedded_codes_are_generic(
    terminal: str,
    *,
    generic_terminal_tokens: set[str],
) -> bool:
    embedded_codes = [normalized for match in re.findall(rf"[A-Za-z0-9]{{{DETAIL_IDENTITY_CODE_MIN_LENGTH},}}", terminal) if (normalized := _normalized_detail_identity_code(match))]
    if not embedded_codes:
        return False
    alpha_chunks = [chunk.lower() for chunk in re.findall(r"[A-Za-z]+", terminal)]
    return not alpha_chunks or all(set(_path_segment_tokens(chunk)) <= generic_terminal_tokens for chunk in alpha_chunks)

def _detail_terminal_is_generic(
    terminal: str,
    *,
    generic_terminal_tokens: set[str],
) -> bool:
    terminal_tokens = _path_segment_tokens(terminal)
    return terminal in generic_terminal_tokens or bool(terminal_tokens and terminal_tokens <= generic_terminal_tokens)

def _detail_terminal_is_ignored(
    terminal: str,
    *,
    generic_terminal_tokens: set[str],
) -> bool:
    if not terminal or terminal.isdigit():
        return True
    if re.fullmatch(r"[a-z]{2}(?:[_-][a-z]{2})?", terminal, re.I):
        return True
    if _detail_terminal_embedded_codes_are_generic(
        terminal,
        generic_terminal_tokens=generic_terminal_tokens,
    ):
        return True
    if re.fullmatch(r"[a-f0-9]{8,}(?:-[a-f0-9]{4,}){2,}", terminal, re.I):
        return True
    return _detail_terminal_is_generic(
        terminal,
        generic_terminal_tokens=generic_terminal_tokens,
    )

def _detail_terminal_parent_is_collection(
    path_segments: list[str],
    index: int,
) -> bool:
    parent_segment = str(path_segments[index - 1]).strip().lower() if index > 0 else ""
    return parent_segment in {"product", "products", "item", "items"}

def _detail_segment_is_shop_merchant_namespace(
    path_segments: list[str],
    index: int,
) -> bool:
    if index <= 0 or index + 1 >= len(path_segments):
        return False
    previous_segment = str(path_segments[index - 1]).strip().lower()
    next_segment = str(path_segments[index + 1]).strip().lower()
    return previous_segment == "shop" and next_segment in {"p", "product", "products"}

def _detail_url_candidate_is_low_signal(candidate_url: object, *, page_url: str) -> bool:
    candidate = text_or_none(candidate_url)
    if not candidate:
        return False
    candidate_parsed = urlparse(candidate)
    page_parsed = urlparse(page_url)
    if candidate_parsed.hostname and page_parsed.hostname and not same_site(page_url, candidate):
        return True
    candidate_path = str(candidate_parsed.path or "").strip()
    page_path = str(page_parsed.path or "").strip()
    if any(candidate_path.lower().endswith(ext) for ext in DETAIL_NON_PAGE_FILE_EXTENSIONS):
        return True
    candidate_segments = {segment.strip().lower() for segment in candidate_path.split("/") if segment.strip()}
    if candidate_segments & _DETAIL_URL_PLACEHOLDER_SEGMENTS:
        return True
    if same_site(page_url, candidate) and _detail_url_is_utility(candidate):
        return True
    return page_path not in {"", "/"} and candidate_path in {"", "/"}

def _preferred_detail_identity_url(
    *,
    surface: str,
    page_url: str,
    requested_page_url: str | None,
) -> str:
    if str(surface or "").strip().lower() != "ecommerce_detail":
        return page_url
    requested = text_or_none(requested_page_url) or text_or_none(page_url)
    current = text_or_none(page_url)
    if not requested or not current or requested == current:
        return current or requested or page_url
    if not same_site(requested, current):
        return current
    if not _detail_url_looks_like_product(requested):
        return current
    if not _detail_url_is_utility(current):
        return current
    return requested

def _detail_url_looks_like_product(url: str) -> bool:
    path_segments = _detail_url_path_segments(url)
    path = f"/{'/'.join(path_segments)}".lower() if path_segments else ""
    if any(hint in path for hint in PRODUCT_URL_HINTS):
        return True
    segments = [segment for segment in path.split("/") if segment]
    if not segments:
        return False
    terminal = _detail_product_terminal(segments)
    if not terminal:
        return False
    if _detail_url_is_utility(url):
        return False
    if _detail_url_is_collection_like(url):
        return False
    if any(token in terminal for token in ("category", "collections", "search", "sale")):
        return False
    return any(separator in terminal for separator in ("-", "_"))

def _detail_product_terminal(segments: list[str]) -> str:
    terminal = next(
        (segment.strip().lower() for segment in reversed(segments) if segment.strip()),
        "",
    )
    if terminal and not terminal.isdigit():
        return terminal
    return next(
        (segment.strip().lower() for segment in reversed(segments[:-1]) if segment.strip() and not segment.strip().isdigit()),
        "",
    )

def _detail_url_is_utility(url: str) -> bool:
    path_tokens = _detail_url_path_tokens(url)
    if any(token in path_tokens for token in DETAIL_PRODUCT_PATH_TOKENS):
        return False
    if any(token in path_tokens for token in DETAIL_UTILITY_PATH_TOKENS):
        return True
    query_keys = {str(key).strip().lower() for key, value in parse_qsl(str(urlparse(url).query or ""), keep_blank_values=False) if str(key).strip() and str(value).strip()}
    if not query_keys:
        return False
    return any(str(key).strip().lower() in query_keys for key in DETAIL_SEARCH_QUERY_KEYS)

def _detail_url_is_collection_like(url: str) -> bool:
    path_tokens = _detail_url_path_tokens(url)
    if any(token in path_tokens for token in DETAIL_PRODUCT_PATH_TOKENS):
        return False
    return any(token in path_tokens for token in DETAIL_COLLECTION_PATH_TOKENS)

def _detail_url_path_tokens(url: str) -> set[str]:
    return {token for token in _LOWER_NON_ALNUM_RE.split("/".join(_detail_url_path_segments(url)).lower()) if token}

def _record_matches_requested_detail_identity(
    record: dict[str, object],
    *,
    requested_page_url: str,
) -> bool:
    requested_codes = _detail_identity_codes_from_url(requested_page_url)
    requested_query_codes = _detail_query_identity_codes_from_url(requested_page_url)
    record_field_codes = _detail_identity_codes_from_record_fields(record)
    if requested_query_codes and detail_identity_codes_match(
        requested_query_codes,
        record_field_codes,
    ):
        return True
    if detail_identity_codes_match(requested_codes, record_field_codes):
        return True
    record_url_codes = _detail_identity_codes_from_url(record.get("url"))
    record_query_codes = _detail_query_identity_codes_from_url(record.get("url"))
    if requested_query_codes and detail_identity_codes_match(
        requested_query_codes,
        record_query_codes,
    ):
        return True
    if requested_query_codes and record_query_codes:
        return False
    requested_title = _detail_title_from_url(requested_page_url)
    requested_tokens = _detail_identity_tokens(requested_title)
    candidate_tokens = _detail_identity_tokens(record.get("title"))
    if not candidate_tokens:
        candidate_tokens = _detail_identity_tokens(record.get("description"))
    title_matches = _detail_token_overlap_matches(requested_tokens, candidate_tokens)
    if not title_matches and requested_tokens:
        supplemental_tokens = _detail_identity_record_tokens(record)
        title_matches = _detail_token_overlap_matches(
            requested_tokens,
            supplemental_tokens,
        )
    if title_matches:
        return True
    return bool(requested_codes and not requested_tokens and detail_identity_codes_match(requested_codes, record_url_codes))

def _detail_identity_record_tokens(record: dict[str, object]) -> set[str]:
    tokens: set[str] = set()
    for field_name in ("title", "brand", "color", "size", "description"):
        tokens.update(_detail_identity_tokens(record.get(field_name)))
    return tokens

def _detail_token_overlap_matches(
    requested_tokens: set[str],
    candidate_tokens: set[str],
) -> bool:
    if not requested_tokens or not candidate_tokens:
        return False
    overlap = requested_tokens & candidate_tokens
    if len(requested_tokens) == 1:
        return bool(overlap)
    return len(overlap) >= min(2, len(requested_tokens))

def _detail_requested_identity_text(page_url: object) -> str:
    raw_url = str(page_url or "")
    title = _detail_title_from_url(raw_url)
    if title:
        return title
    generic_terminal_tokens = set(DETAIL_GENERIC_TERMINAL_TOKENS)
    path_segments = _detail_url_path_segments(raw_url)
    for index in range(len(path_segments) - 1, -1, -1):
        if _detail_segment_is_shop_merchant_namespace(path_segments, index):
            continue
        segment = path_segments[index]
        terminal = _HTML_SUFFIX_RE.sub("", segment)
        if not terminal or terminal.isdigit():
            continue
        terminal_tokens = _path_segment_tokens(terminal)
        if terminal_tokens and terminal_tokens <= generic_terminal_tokens:
            continue
        title = clean_text(_SLUG_SEPARATOR_RE.sub(" ", terminal))
        semantic_tokens = _semantic_detail_identity_tokens(title)
        if _detail_segment_looks_like_identity_code(terminal) and len(semantic_tokens) < 2:
            continue
        if semantic_tokens:
            return title
    return ""

def _detail_model_numbers_conflict(
    requested_title: object,
    candidate_title: object,
    *,
    record: dict[str, object] | None = None,
) -> bool:
    requested_numbers = detail_model_number_tokens(requested_title)
    candidate_numbers = detail_model_number_tokens(candidate_title)
    if not requested_numbers or not candidate_numbers:
        requested_numbers = detail_small_numeric_model_tokens(requested_title)
        candidate_numbers = detail_small_numeric_model_tokens(candidate_title)
        if not (requested_numbers and candidate_numbers and _detail_has_sku_evidence(record or {}, tokens=requested_numbers | candidate_numbers)):
            return False
    if not requested_numbers or not candidate_numbers:
        return False
    if detail_model_number_sets_compatible(requested_numbers, candidate_numbers):
        return False
    requested_words = _semantic_detail_identity_tokens(requested_title)
    candidate_words = _semantic_detail_identity_tokens(candidate_title)
    shared_words = requested_words & candidate_words
    required_shared_words = min(
        int(DETAIL_MODEL_CONFLICT_MIN_SHARED_WORDS),
        len(requested_words),
        len(candidate_words),
    )
    return required_shared_words > 0 and len(shared_words) >= required_shared_words

def _detail_has_sku_evidence(
    record: dict[str, object],
    *,
    tokens: set[str],
) -> bool:
    if not tokens:
        return False
    for field_name in ("sku", "product_id", "variant_id", "part_number", "barcode"):
        normalized = normalized_model_token(record.get(field_name))
        if normalized and any(token in normalized for token in tokens):
            return True
    return False

def _record_has_strong_requested_identity_code(
    record: dict[str, object],
    *,
    requested_codes: set[str],
) -> bool:
    if not requested_codes:
        return False
    for field_name in ("product_id", "variant_id", "part_number", "barcode"):
        normalized = _normalized_detail_identity_code(record.get(field_name))
        if normalized and detail_identity_codes_match(requested_codes, {normalized}):
            return True
    return False

def _record_has_detail_product_evidence(record: dict[str, object]) -> bool:
    return any(
        record.get(field_name) not in (None, "", [], {})
        for field_name in (
            "title",
            "price",
            "original_price",
            "currency",
            "image_url",
            "description",
            "brand",
            "sku",
            "product_id",
            "part_number",
            "barcode",
            "variants",
        )
    )

def _detail_slug_title_fallback_from_url(identity_url: str) -> str | None:
    generic_terminal_tokens = set(DETAIL_GENERIC_TERMINAL_TOKENS)
    path_segments = _detail_url_path_segments(identity_url)
    for index in range(len(path_segments) - 1, -1, -1):
        if _detail_segment_is_shop_merchant_namespace(path_segments, index):
            continue
        segment = path_segments[index]
        terminal = _HTML_SUFFIX_RE.sub("", segment)
        if not terminal:
            continue
        title = clean_text(_SLUG_SEPARATOR_RE.sub(" ", terminal))
        semantic_tokens = _semantic_detail_identity_tokens(title)
        if _detail_title_fallback_looks_like_code(terminal) and (len(semantic_tokens) < int(DETAIL_TITLE_FALLBACK_MIN_SEMANTIC_TOKENS)):
            continue
        terminal_tokens = _path_segment_tokens(terminal)
        if terminal_tokens and terminal_tokens <= generic_terminal_tokens:
            continue
        if len(semantic_tokens) >= int(DETAIL_TITLE_FALLBACK_MIN_SEMANTIC_TOKENS):
            return title
    return None

def _detail_title_fallback_looks_like_code(value: object) -> bool:
    terminal = str(value or "").strip()
    if not terminal:
        return False
    if _MIXED_NON_ALNUM_RE.search(terminal):
        return False
    text = clean_text(value)
    if not text:
        return False
    compact = _MIXED_NON_ALNUM_RE.sub("", text)
    pattern = str(DETAIL_TITLE_FALLBACK_CODE_PATTERN or "").strip()
    return bool(compact and re.search(r"\d", compact) and re.fullmatch(pattern, compact))

detail_title_fallback_looks_like_code = _detail_title_fallback_looks_like_code

def _detail_url_matches_requested_identity(
    candidate_url: str,
    *,
    requested_page_url: str,
) -> bool:
    requested_codes = _detail_identity_codes_from_url(requested_page_url)
    candidate_codes = _detail_identity_codes_from_url(candidate_url)
    requested_query_codes = _detail_query_identity_codes_from_url(requested_page_url)
    candidate_query_codes = _detail_query_identity_codes_from_url(candidate_url)
    if requested_query_codes:
        if detail_identity_codes_match(requested_query_codes, candidate_query_codes):
            return True
        if candidate_query_codes:
            return False
    if detail_identity_codes_match(requested_codes, candidate_codes):
        return True
    requested_title = _detail_title_from_url(requested_page_url)
    requested_tokens = _detail_identity_tokens(requested_title)
    if not requested_tokens:
        return False
    candidate_title = _detail_title_from_url(candidate_url) or candidate_url
    candidate_tokens = _detail_identity_tokens(candidate_title)
    if not candidate_tokens:
        return False
    overlap = requested_tokens & candidate_tokens
    if len(requested_tokens) == 1:
        return bool(overlap)
    return len(overlap) >= min(2, len(requested_tokens))

def _detail_identity_tokens(value: object) -> set[str]:
    cleaned = clean_text(value).lower()
    return {token for token in _LOWER_NON_ALNUM_RE.split(cleaned) if len(token) >= 3 and token not in DETAIL_IDENTITY_STOPWORDS}

def _semantic_detail_identity_tokens(value: object) -> set[str]:
    return {token for token in _detail_identity_tokens(value) if re.search(r"[a-z]", token) and not re.search(r"\d", token)}

def _detail_identity_codes_from_url(url: object) -> set[str]:
    text = text_or_none(url)
    if not text:
        return set()
    parsed = urlparse(text)
    codes: set[str] = set()
    for segment in _detail_url_path_segments(text):
        terminal = _HTML_SUFFIX_RE.sub("", segment)
        code_like_terminal = _detail_segment_code(terminal)
        if code_like_terminal:
            codes.add(code_like_terminal)
        for match in re.findall(rf"[A-Za-z0-9]{{{DETAIL_IDENTITY_CODE_MIN_LENGTH},}}", terminal):
            normalized = _normalized_detail_identity_code(match)
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
        normalized = _detail_segment_code(match.group(1))
        if normalized:
            codes.add(normalized)
    codes.update(_detail_query_identity_codes_from_url(text))
    return codes

def _detail_query_identity_codes_from_url(url: object) -> set[str]:
    text = text_or_none(url)
    if not text:
        return set()
    parsed = urlparse(text)
    codes: set[str] = set()
    for key, value in parse_qsl(parsed.query, keep_blank_values=False):
        normalized_key = str(key or "").strip().lower()
        if not normalized_key:
            continue
        if normalized_key in _DETAIL_IDENTITY_QUERY_KEYS or any(normalized_key.startswith(prefix) for prefix in _DETAIL_IDENTITY_QUERY_PREFIXES):
            normalized_value = _detail_segment_code(value)
            if normalized_value:
                codes.add(normalized_value)
    return codes

def _detail_identity_codes_from_record_fields(record: dict[str, object]) -> set[str]:
    codes: set[str] = set()
    for field_name in ("sku", "product_id", "variant_id", "part_number"):
        normalized = _normalized_detail_identity_code(record.get(field_name))
        if normalized:
            codes.add(normalized)
    return codes

def _detail_segment_looks_like_identity_code(value: object) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    if re.fullmatch(r"[A-Za-z0-9]+(?:[-_][A-Za-z0-9]+){0,2}", text) is None:
        return False
    return _normalized_detail_identity_code(text) is not None

def _detail_segment_code(value: object) -> str | None:
    text = str(value or "").strip()
    if not _detail_segment_looks_like_identity_code(text):
        return None
    return _normalized_detail_identity_code(text)

def _normalized_detail_identity_code(value: object) -> str | None:
    text = _MIXED_NON_ALNUM_RE.sub("", str(value or "")).upper()
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

def _same_url_identity_is_mismatched(record: dict[str, object], *, requested: str) -> bool:
    candidate_url = text_or_none(record.get("url"))
    if candidate_url and candidate_url != requested and same_site(requested, candidate_url) and not _detail_url_matches_requested_identity(candidate_url, requested_page_url=requested):
        return True
    requested_title = _detail_requested_identity_text(requested)
    candidate_title = record.get("title")
    requested_codes = _detail_identity_codes_from_url(requested)
    record_codes = _detail_identity_codes_from_record_fields(record)
    matching_codes = detail_identity_codes_match(requested_codes, record_codes)
    matching_strong_code = _record_has_strong_requested_identity_code(record, requested_codes=requested_codes)
    matching_small_number = bool(detail_small_numeric_model_tokens(requested_title) & detail_small_numeric_model_tokens(candidate_title))
    if _detail_model_numbers_conflict(requested_title, candidate_title, record=record) and not (matching_small_number or (matching_codes and matching_strong_code)):
        return True
    return _same_url_text_identity_is_mismatched(
        record,
        requested=requested,
        requested_title=requested_title,
        candidate_title=candidate_title,
    )

def _same_url_text_identity_is_mismatched(
    record: dict[str, object],
    *,
    requested: str,
    requested_title: object,
    candidate_title: object,
) -> bool:
    strong = any(
        record.get(field) not in (None, "", [], {})
        for field in (
            "sku",
            "product_id",
            "part_number",
            "barcode",
            "description",
            "brand",
            "product_details",
            "variants",
        )
    )
    availability = text_or_none(record.get("availability"))
    strong = strong or bool(availability and availability != AVAILABILITY_UNKNOWN)
    if strong:
        return False
    requested_tokens = _detail_identity_tokens(requested_title)
    candidate_tokens = _detail_identity_tokens(candidate_title)
    mismatch_evidence = any(record.get(field) not in (None, "", [], {}) for field in ("price", "original_price", "currency", "image_url")) or len(candidate_tokens) >= 4
    weak_overlap = len(requested_tokens & candidate_tokens) < min(2, len(requested_tokens))
    return all(
        (
            mismatch_evidence,
            len(requested_tokens) >= 2,
            len(candidate_tokens) >= 2,
            weak_overlap,
            not _record_matches_requested_detail_identity(record, requested_page_url=requested),
        )
    )

def _redirect_codes_conflict(record: dict[str, object], *, requested: str, current: str | None) -> bool:
    requested_codes = _detail_identity_codes_from_url(requested)
    record_codes = _detail_identity_codes_from_record_fields(record)
    if not requested_codes or not record_codes or detail_identity_codes_match(requested_codes, record_codes):
        return False
    candidate_url = text_or_none(record.get("url")) or current
    return not (
        candidate_url and _detail_url_matches_requested_identity(candidate_url, requested_page_url=requested) and _record_matches_requested_detail_identity(record, requested_page_url=requested)
    )

def _redirect_candidate_is_mismatched(record: dict[str, object], *, requested: str, current: str | None) -> bool | None:
    candidate_url = text_or_none(record.get("url")) or current
    if not candidate_url or candidate_url == requested or not same_site(requested, candidate_url):
        return None
    if not _detail_url_matches_requested_identity(candidate_url, requested_page_url=requested):
        return True
    if _record_has_detail_product_evidence(record):
        return False
    return not _record_matches_requested_detail_identity(record, requested_page_url=requested)

def _detail_redirect_identity_is_mismatched(
    record: dict[str, object],
    *,
    page_url: str,
    requested_page_url: str | None,
) -> bool:
    requested = text_or_none(requested_page_url) or text_or_none(page_url)
    current = text_or_none(page_url)
    if not requested:
        return False
    if not _detail_url_looks_like_product(requested):
        return False

    if current and requested == current:
        return _same_url_identity_is_mismatched(record, requested=requested)
    if _redirect_codes_conflict(record, requested=requested, current=current):
        return True
    candidate_mismatch = _redirect_candidate_is_mismatched(record, requested=requested, current=current)
    if candidate_mismatch is not None:
        return candidate_mismatch

    if not current:
        return False
    if not same_site(requested, current):
        return False
    if not _detail_url_is_utility(current):
        return False
    return not _record_matches_requested_detail_identity(
        record,
        requested_page_url=requested,
    )

(
    detail_identity_codes_from_record_fields,
    detail_identity_codes_from_url,
    detail_query_identity_codes_from_url,
    detail_identity_tokens,
    detail_redirect_identity_is_mismatched,
    detail_slug_title_fallback_from_url,
    detail_title_from_url,
    detail_url_candidate_is_low_signal,
    detail_url_is_collection_like,
    detail_url_is_utility,
    detail_url_looks_like_product,
    detail_url_matches_requested_identity,
    preferred_detail_identity_url,
    record_matches_requested_detail_identity,
    semantic_detail_identity_tokens,
) = (
    _detail_identity_codes_from_record_fields,
    _detail_identity_codes_from_url,
    _detail_query_identity_codes_from_url,
    _detail_identity_tokens,
    _detail_redirect_identity_is_mismatched,
    _detail_slug_title_fallback_from_url,
    _detail_title_from_url,
    _detail_url_candidate_is_low_signal,
    _detail_url_is_collection_like,
    _detail_url_is_utility,
    _detail_url_looks_like_product,
    _detail_url_matches_requested_identity,
    _preferred_detail_identity_url,
    _record_matches_requested_detail_identity,
    _semantic_detail_identity_tokens,
)

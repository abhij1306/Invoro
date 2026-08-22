from __future__ import annotations

__all__ = (
    "document_link_label_patterns",
    "fulfillment_only_long_text_phrases",
    "fulfillment_long_text_patterns",
    "guide_glossary_text_patterns",
    "guide_glossary_heading_tokens",
    "long_text_disclaimer_patterns",
    "low_signal_title_values",
    "low_signal_long_text_values",
    "materials_pollution_tokens",
    "low_signal_product_type_values",
    "detail_artifact_product_type_patterns",
    "cross_product_text_type_tokens",
    "cross_product_text_generic_tokens",
    "title_dimension_size_re",
    "tracking_token_re",
    "cookie_disclosure_text_patterns",
    "low_signal_numeric_size_max",
    "artifact_price_values",
    "feature_row_noise_patterns",
    "detail_title_value_is_low_signal",
    "detail_product_type_is_low_signal",
    "detail_scalar_size_is_low_signal",
    "detail_candidate_is_valid",
    "sanitize_detail_long_text_fields",
    "sanitize_detail_long_text",
    "sanitize_detail_features",
    "detail_long_text_chunk_looks_truncated",
    "detail_long_text_chunk_is_variant_size_sequence",
    "detail_long_text_is_numeric_sequence",
    "detail_long_text_is_fulfillment_only",
    "detail_long_text_is_guide_or_glossary_dump",
    "detail_long_text_is_cookie_disclosure_dump",
    "detail_long_text_chunk_is_legal_tail",
    "detail_long_text_chunk_is_document_label",
    "detail_long_text_is_document_label_cluster",
    "detail_long_text_chunk_is_variant_title",
    "detail_long_text_chunk_is_other_product",
    "detail_product_text_tokens",
    "detail_long_text_chunk_has_product_name_shape",
)

import ast
import json
import re
from typing import Any

from app.services.config.extraction_rules import (
    DETAIL_ARTIFACT_IDENTIFIER_VALUES,
    DETAIL_ARTIFACT_PRICE_VALUES,
    DETAIL_ARTIFACT_PRODUCT_TYPE_PATTERNS,
    DETAIL_ARTIFACT_PRODUCT_TYPE_VALUES,
    DETAIL_ARTIFACT_SKU_PREFIXES,
    DETAIL_BRACKET_PROSE_MIN_WORDS,
    DETAIL_CATEGORY_UI_TOKENS,
    DETAIL_LOW_SIGNAL_LONG_TEXT_VALUES,
    DETAIL_LOW_SIGNAL_NUMERIC_SIZE_MAX,
    DETAIL_LOW_SIGNAL_PRODUCT_TYPE_VALUES,
    DETAIL_LOW_SIGNAL_TITLE_VALUES,
    DETAIL_LONG_TEXT_DISCLAIMER_PATTERNS,
    DETAIL_LONG_TEXT_LEADING_ATTRIBUTE_BLOB_PATTERN,
    DETAIL_LONG_TEXT_REPEATED_PROMPTS,
    DETAIL_LONG_TEXT_SUBSTRING_REMOVE_PATTERNS,
    DETAIL_LONG_TEXT_TRUNCATED_TAIL_TOKENS,
    DETAIL_LONG_TEXT_UI_TAIL_MIN_PRODUCT_WORDS,
    DETAIL_LONG_TEXT_UI_TAIL_PHRASES,
    DETAIL_NOISE_PREFIXES,
    DETAIL_TITLE_DIMENSION_SIZE_PATTERN,
    DETAIL_TRACKING_TOKEN_PATTERN,
    DETAIL_VARIANT_ARTIFACT_VALUE_TOKENS,
    DETAIL_VARIANT_SIZE_SEQUENCE_MIN_COUNT,
    FEATURE_ROW_NOISE_PATTERNS,
    LONG_TEXT_MAX_WORDS,
    LONG_TEXT_MIN_WORDS,
    LONG_TEXT_PREFIXES,
    TOKEN_MIN_LEN_CHUNK,
)
from app.services.config.detail_extraction_constants import MAX_STRUCTURED_TEXT_LENGTH
from app.services.shared.field_coerce import LONG_TEXT_FIELDS, clean_text, text_or_none
from app.services.shared.regex_patterns import compile_regex_patterns
from app.services.extract.detail.text.long_text_guards import (
    clean_materials_pollution,
    cookie_disclosure_text_patterns,
    cross_product_text_generic_tokens,
    cross_product_text_type_tokens,
    detail_long_text_chunk_has_product_name_shape,
    detail_long_text_chunk_is_document_label,
    detail_long_text_chunk_is_legal_tail,
    detail_long_text_chunk_is_other_product,
    detail_long_text_chunk_is_variant_title,
    detail_long_text_is_cookie_disclosure_dump,
    detail_long_text_is_document_label_cluster,
    detail_long_text_is_fulfillment_only,
    detail_long_text_is_guide_or_glossary_dump,
    detail_long_text_is_numeric_sequence,
    detail_product_text_tokens,
    document_link_label_patterns,
    fulfillment_long_text_patterns,
    fulfillment_only_long_text_phrases,
    guide_glossary_heading_tokens,
    guide_glossary_text_patterns,
    materials_pollution_tokens,
    text_is_structured_json_array,
)

long_text_disclaimer_patterns = compile_regex_patterns(
    DETAIL_LONG_TEXT_DISCLAIMER_PATTERNS or ()
)
long_text_substring_remove_patterns = compile_regex_patterns(
    DETAIL_LONG_TEXT_SUBSTRING_REMOVE_PATTERNS or ()
)
long_text_repeated_prompts = tuple(
    clean_text(prompt)
    for prompt in tuple(DETAIL_LONG_TEXT_REPEATED_PROMPTS or ())
    if clean_text(prompt)
)
low_signal_title_values = frozenset(
    clean_text(value).lower()
    for value in tuple(DETAIL_LOW_SIGNAL_TITLE_VALUES or ())
    if clean_text(value)
)
low_signal_long_text_values = frozenset(
    clean_text(value).lower()
    for value in tuple(DETAIL_LOW_SIGNAL_LONG_TEXT_VALUES or ())
    if clean_text(value)
)
low_signal_product_type_values = frozenset(
    clean_text(value).lower()
    for value in tuple(DETAIL_LOW_SIGNAL_PRODUCT_TYPE_VALUES or ())
    if clean_text(value)
)
detail_artifact_product_type_patterns = compile_regex_patterns(
    DETAIL_ARTIFACT_PRODUCT_TYPE_PATTERNS or ()
)
title_dimension_size_re = re.compile(str(DETAIL_TITLE_DIMENSION_SIZE_PATTERN), re.I)
tracking_token_re = re.compile(str(DETAIL_TRACKING_TOKEN_PATTERN), re.I)
low_signal_numeric_size_max = int(DETAIL_LOW_SIGNAL_NUMERIC_SIZE_MAX)
_detail_noise_prefixes = tuple(
    clean_text(prefix).lower()
    for prefix in tuple(DETAIL_NOISE_PREFIXES or ())
    if clean_text(prefix)
)
_DESCRIPTION_REPAIRED_FROM_PRODUCT_DETAILS = (
    "_description_repaired_from_product_details"
)
_long_text_ui_tail_phrases = tuple(
    clean_text(phrase).lower()
    for phrase in tuple(DETAIL_LONG_TEXT_UI_TAIL_PHRASES or ())
    if clean_text(phrase)
)
_long_text_ui_tail_min_product_words = int(DETAIL_LONG_TEXT_UI_TAIL_MIN_PRODUCT_WORDS)
_bracket_prose_min_words = int(DETAIL_BRACKET_PROSE_MIN_WORDS)
_long_text_min_words = int(LONG_TEXT_MIN_WORDS)
_long_text_max_words = int(LONG_TEXT_MAX_WORDS)
_token_min_len_chunk = int(TOKEN_MIN_LEN_CHUNK)
_long_text_prefixes = tuple(
    clean_text(prefix).lower()
    for prefix in tuple(LONG_TEXT_PREFIXES or ())
    if clean_text(prefix)
)
artifact_price_values = frozenset(
    clean_text(v).lower()
    for v in tuple(DETAIL_ARTIFACT_PRICE_VALUES or ())
    if clean_text(v)
)
feature_row_noise_patterns = compile_regex_patterns(FEATURE_ROW_NOISE_PATTERNS or ())


def detail_title_value_is_low_signal(value: object) -> bool:
    text = clean_text(value)
    return bool(text and text.lower() in low_signal_title_values)


def detail_product_type_is_low_signal(value: object) -> bool:
    text = clean_text(value)
    lowered = text.lower()
    return bool(
        lowered
        and (
            lowered in low_signal_product_type_values
            or lowered in DETAIL_ARTIFACT_PRODUCT_TYPE_VALUES
            or any(
                pattern.fullmatch(lowered)
                for pattern in detail_artifact_product_type_patterns
            )
        )
    )


def detail_scalar_size_is_low_signal(value: str, *, title: object) -> bool:
    if not value or not value.isdigit():
        return False
    try:
        numeric_value = int(value)
    except ValueError:
        return False
    return numeric_value <= low_signal_numeric_size_max and bool(
        title_dimension_size_re.search(clean_text(title))
    )


def detail_candidate_is_valid(
    field_name: str,
    value: object,
    *,
    source: str | None = None,
) -> bool:
    return not (
        _long_text_candidate_is_noise(field_name, value, source=source)
        or _title_candidate_is_artifact(field_name, value)
        or _category_candidate_is_noise(field_name, value)
        or _sku_candidate_is_artifact(field_name, value)
        or _identifier_candidate_is_artifact(field_name, value)
        or _product_type_candidate_is_artifact(field_name, value)
        or _price_candidate_is_artifact(field_name, value)
        or _variant_candidate_is_artifact(field_name, value)
    )


def _title_candidate_is_artifact(field_name: str, value: object) -> bool:
    return field_name == "title" and bool(
        tracking_token_re.fullmatch(clean_text(value))
    )


def _category_candidate_is_noise(field_name: str, value: object) -> bool:
    if field_name != "category":
        return False
    cleaned = clean_text(value)
    if not cleaned:
        return True
    parts = [
        clean_text(part).lower()
        for part in re.split(r">\s*|/+", cleaned)
        if clean_text(part)
    ]
    if not parts or any(part in DETAIL_CATEGORY_UI_TOKENS for part in parts):
        return True
    lowered = f" {cleaned.lower()} "
    return any(
        f" {token} " in lowered
        for token in DETAIL_CATEGORY_UI_TOKENS
        if token != "..."  # nosec B105
    )


def _sku_candidate_is_artifact(field_name: str, value: object) -> bool:
    if field_name not in {"sku", "part_number", "product_id"}:
        return False
    cleaned = clean_text(value).lower()
    return bool(
        cleaned
        and any(cleaned.startswith(prefix) for prefix in DETAIL_ARTIFACT_SKU_PREFIXES)
    )


def _identifier_candidate_is_artifact(field_name: str, value: object) -> bool:
    if field_name not in {"product_id", "part_number"}:
        return False
    cleaned = clean_text(value).lower()
    return bool(cleaned and cleaned in DETAIL_ARTIFACT_IDENTIFIER_VALUES)


def _product_type_candidate_is_artifact(field_name: str, value: object) -> bool:
    if field_name != "product_type":
        return False
    cleaned = clean_text(value).lower()
    return bool(
        cleaned
        and (
            cleaned in DETAIL_ARTIFACT_PRODUCT_TYPE_VALUES
            or any(
                pattern.fullmatch(cleaned)
                for pattern in detail_artifact_product_type_patterns
            )
        )
    )


def _price_candidate_is_artifact(field_name: str, value: object) -> bool:
    if field_name not in {"price", "sale_price", "original_price"}:
        return False
    cleaned = clean_text(value).lower()
    if cleaned in artifact_price_values:
        return True
    if re.search(r"(^|[^\d])-\s*\d", cleaned):
        return True
    normalized = re.sub(r"[^0-9.]+", "", cleaned)
    if not normalized:
        return True
    try:
        return float(normalized) < 0
    except ValueError:
        return True


def _variant_candidate_is_artifact(field_name: str, value: object) -> bool:
    if field_name not in {"variants", "selected_variant", "variant_axes"}:
        return False
    return any(
        _variant_artifact_token_seen(item) for item in _walk_variant_values(value)
    )


def _walk_variant_values(value: object) -> list[object]:
    if isinstance(value, dict):
        values: list[object] = list(value.keys())
        for item in value.values():
            values.extend(_walk_variant_values(item))
        return values
    if isinstance(value, list):
        return [nested for item in value for nested in _walk_variant_values(item)]
    return [value]


def _variant_artifact_token_seen(value: object) -> bool:
    text = clean_text(value).lower()
    return bool(
        text
        and (
            text in DETAIL_VARIANT_ARTIFACT_VALUE_TOKENS
            or re.fullmatch(r"\d+\s*%", text)
        )
    )


def _long_text_candidate_is_noise(
    field_name: str, value: object, *, source: str | None = None
) -> bool:
    if field_name not in LONG_TEXT_FIELDS:
        return False
    cleaned = clean_text(value)
    lowered = cleaned.lower()
    if not lowered or lowered in low_signal_long_text_values:
        return True
    if field_name in {"description", "specifications"} and lowered.startswith(
        _detail_noise_prefixes
    ):
        return True
    tail_stripped = _strip_long_text_ui_tail(cleaned)
    if tail_stripped != cleaned:
        return len(tail_stripped.split()) < _long_text_ui_tail_min_product_words
    if (
        source == "dom_sections"
        and field_name in {"description", "specifications", "product_details"}
        and len(cleaned.split()) <= 4
        and not any(token in cleaned for token in ".:;!?\n")
    ):
        return True
    if any(pattern.search(cleaned) for pattern in guide_glossary_text_patterns):
        return True
    if detail_long_text_is_cookie_disclosure_dump(cleaned):
        return True
    return len(cleaned.split()) < 2


def sanitize_detail_long_text_fields(
    record: dict[str, Any],
    *,
    title_hint: str | None = None,
) -> None:
    record_title = clean_text(
        " ".join(
            value
            for value in (clean_text(record.get("title")), clean_text(title_hint))
            if value
        )
    )
    title_tokens = set(detail_product_text_tokens(clean_text(record.get("title"))))
    protected_identity_tokens = {
        token
        for token in detail_product_text_tokens(clean_text(title_hint))
        if len(token) >= _token_min_len_chunk and token not in title_tokens
    }
    for field_name in LONG_TEXT_FIELDS:
        text = text_or_none(record.get(field_name))
        if not text:
            continue
        cleaned = sanitize_detail_long_text(
            text,
            title=record_title,
            protected_identity_tokens=protected_identity_tokens,
        )
        if cleaned:
            record[field_name] = cleaned
        else:
            record.pop(field_name, None)
    _trim_description_to_identity_hint(
        record,
        protected_identity_tokens=protected_identity_tokens,
    )
    description = clean_text(record.get("description")).casefold()
    specifications = clean_text(record.get("specifications")).casefold()
    if description and specifications and description == specifications:
        record.pop("specifications", None)
    materials = clean_materials_pollution(record.get("materials"))
    if materials:
        record["materials"] = materials
    else:
        record.pop("materials", None)
    features = sanitize_detail_features(record.get("features"), title=record_title)
    if features:
        record["features"] = features
    else:
        record.pop("features", None)
    _repair_description_feature_duplicate(record)
    _drop_redundant_product_details(record)
    _promote_product_details_description(record)


def _repair_description_feature_duplicate(record: dict[str, Any]) -> None:
    description = clean_text(record.get("description"))
    raw_features_value = record.get("features")
    raw_features: list[Any] = (
        raw_features_value if isinstance(raw_features_value, list) else []
    )
    features = []
    for row in raw_features:
        cleaned = clean_text(row)
        if cleaned:
            features.append(cleaned)
    if not description or not features:
        return
    feature_text = clean_text(" ".join(features))
    if description.casefold() != feature_text.casefold():
        return
    product_details = sanitize_detail_long_text(
        clean_text(record.get("product_details")),
        title=clean_text(record.get("title")),
    )
    if product_details and product_details.casefold() != description.casefold():
        record["description"] = product_details
        record[_DESCRIPTION_REPAIRED_FROM_PRODUCT_DETAILS] = True
        return
    record.pop("description", None)


def _trim_description_to_identity_hint(
    record: dict[str, Any],
    *,
    protected_identity_tokens: set[str],
) -> None:
    description = clean_text(record.get("description"))
    if not description or not protected_identity_tokens:
        return
    chunks = [
        clean_text(chunk)
        for chunk in re.split(r"(?<=[.!?])\s+|\s+:\s+|\n+", description)
        if clean_text(chunk)
    ]
    if not chunks:
        return
    kept: list[str] = []
    seen_identity = False
    for chunk in chunks:
        chunk_tokens = detail_product_text_tokens(chunk)
        has_identity = bool(protected_identity_tokens & chunk_tokens)
        if has_identity:
            seen_identity = True
            kept.append(chunk)
            continue
        if not seen_identity:
            continue
        if detail_long_text_chunk_has_product_name_shape(
            chunk
        ) and _chunk_has_named_product_signal(chunk):
            break
        kept.append(chunk)
    if kept and len(kept) < len(chunks):
        record["description"] = " ".join(kept)


def _chunk_has_named_product_signal(chunk: str) -> bool:
    words = re.findall(r"[A-Za-z][A-Za-z'’-]*", str(chunk or ""))
    capitalized = [
        word
        for word in words[1:]
        if len(word) > 1 and word[:1].isupper() and word.casefold() not in {"this"}
    ]
    return len(capitalized) >= 2


def _promote_product_details_description(record: dict[str, Any]) -> None:
    description = clean_text(record.get("description"))
    product_details = sanitize_detail_long_text(
        clean_text(record.get("product_details")),
        title=clean_text(record.get("title")),
    )
    if not product_details:
        return
    if not description:
        record["description"] = product_details
        return
    if product_details.casefold() == description.casefold():
        return
    product_word_count = len(product_details.split())
    description_word_count = len(description.split())
    if product_word_count <= description_word_count:
        return
    if description_word_count >= _long_text_min_words:
        return
    record["description"] = product_details


def _drop_redundant_product_details(record: dict[str, Any]) -> None:
    description = clean_text(record.get("description"))
    product_details = sanitize_detail_long_text(
        clean_text(record.get("product_details")),
        title=clean_text(record.get("title")),
    )
    if not description or not product_details:
        return
    if record.get(_DESCRIPTION_REPAIRED_FROM_PRODUCT_DETAILS) is True:
        return
    if description.casefold() != product_details.casefold():
        return
    record.pop("product_details", None)
    field_sources = record.get("_field_sources")
    if isinstance(field_sources, dict):
        field_sources.pop("product_details", None)


# skipcq: PY-R1000


def sanitize_detail_long_text(
    text: str,
    *,
    title: str,
    protected_identity_tokens: set[str] | None = None,
) -> str:
    cleaned_text = _strip_long_text_ui_tail(
        _strip_leading_attribute_blob(_strip_bracket_artifact_noise(clean_text(text)))
    )
    cleaned_text = _strip_long_text_substring_noise(cleaned_text)
    cleaned_text = _trim_repeated_title_lead(cleaned_text, title=title)
    if _detail_long_text_is_rejected(cleaned_text, text):
        return ""
    chunks = [
        clean_text(chunk)
        for chunk in re.split(r"(?<=[.!?])\s+|\s+:\s+|\n+", cleaned_text)
        if clean_text(chunk)
    ]
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
        or text_is_structured_json_array(cleaned)
        or cleaned.lower() in low_signal_long_text_values
        or detail_long_text_is_numeric_sequence(cleaned)
        or detail_long_text_is_fulfillment_only(cleaned)
        or detail_long_text_is_guide_or_glossary_dump(cleaned)
        or detail_long_text_is_cookie_disclosure_dump(cleaned)
        or detail_long_text_is_document_label_cluster(original)
    )


def _detail_long_text_chunk_is_rejected(chunk: str) -> bool:
    return detail_long_text_chunk_is_legal_tail(chunk) or any(
        pattern.search(chunk) for pattern in long_text_disclaimer_patterns
    )


def _kept_detail_long_text_chunk(
    chunk: str, title: str, protected_tokens: set[str], seen: set[str]
) -> str:
    cleaned = _strip_repeated_prompt_text(chunk)
    if (
        not cleaned
        or cleaned.lower() in seen
        or _detail_long_text_chunk_is_rejected(cleaned)
    ):
        return ""
    protected = bool(protected_tokens & detail_product_text_tokens(cleaned))
    if not protected and (
        detail_long_text_chunk_is_variant_title(cleaned, title=title)
        or detail_long_text_chunk_is_other_product(cleaned, title=title)
    ):
        return ""
    if detail_long_text_chunk_is_variant_size_sequence(
        cleaned
    ) or detail_long_text_chunk_looks_truncated(cleaned):
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
            cleaned = clean_text(
                cleaned[:first_end] + cleaned[first_end:].replace(prompt, "")
            )
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
        if not cleaned or any(
            pattern.search(cleaned) for pattern in long_text_disclaimer_patterns
        ):
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
    return (
        values == sorted(values)
        and len(set(values)) >= DETAIL_VARIANT_SIZE_SEQUENCE_MIN_COUNT
    )


_BRACKET_RUN_RE = re.compile(r"(?:\[\s*){2,}|(?:\]\s*){2,}")
_BRACKETS_RE = re.compile(r"[\[\]]+")
_LEADING_ATTRIBUTE_BLOB_RE = re.compile(
    str(DETAIL_LONG_TEXT_LEADING_ATTRIBUTE_BLOB_PATTERN), re.I
)


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

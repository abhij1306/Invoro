from __future__ import annotations

from app.services.extract.variant_normalization.common import (
    Any,
    adult_size_context_tokens as _ADULT_SIZE_CONTEXT_TOKENS,
    clean_text,
    common_word_size_values as _COMMON_WORD_SIZE_VALUES,
    gender_artifact_pattern as _GENDER_ARTIFACT_PATTERN,
    gender_keyword_tokens_set as _GENDER_KEYWORD_TOKENS_SET,
    normalized_variant_axis_key,
    re,
    standard_size_values as _STANDARD_SIZE_VALUES,
    url_terminal_text as _url_terminal_text,
    variant_child_size_patterns as _VARIANT_CHILD_SIZE_PATTERNS,
    variant_color_hint_words as _VARIANT_COLOR_HINT_WORDS,
    variant_condition_header_prefixes as _VARIANT_CONDITION_HEADER_PREFIXES,
    variant_axis_value_exceeds_word_limit,
    variant_option_label_max_words as _VARIANT_OPTION_LABEL_MAX_WORDS,
    variant_option_value_suffix_noise_patterns_normalized as _VARIANT_OPTION_VALUE_SUFFIX_NOISE_PATTERNS,
    variant_option_value_is_noise,
    variant_placeholder_prefixes_lower as _VARIANT_PLACEHOLDER_PREFIXES_LOWER,
    variant_placeholder_values_set as _VARIANT_PLACEHOLDER_VALUES_SET,
    variant_size_quantity_control_values as _VARIANT_SIZE_QUANTITY_CONTROL_VALUES,
    variant_size_value_extract_patterns as _VARIANT_SIZE_VALUE_EXTRACT_PATTERNS,
    variant_size_value_patterns as _VARIANT_SIZE_VALUE_PATTERNS,
    variant_title_tokens as _variant_title_tokens,
)

__all__ = (
    "_normalize_variant_axis_value",
    "_variant_size_axis_value_is_quantity_control",
    "_strip_variant_option_suffix_noise",
    "_value_is_placeholder",
    "_value_is_ui_noise",
    "_extract_size_value",
    "_size_value_is_recognized",
    "_size_value_is_child_specific",
    "_record_targets_adult_sizes",
    "_value_is_axis_header_noise",
    "_variant_axis_value_is_header",
    "_variant_color_from_title_or_url",
    "_extract_color_value",
    "_extract_trailing_color_phrase",
    "_title_preserving_acronyms",
)


def _normalize_variant_axis_value(field_name: str, value: object) -> str:
    cleaned = _strip_variant_option_suffix_noise(value)
    if not cleaned:
        return ""
    if variant_axis_value_exceeds_word_limit(
        normalized_variant_axis_key(field_name),
        cleaned,
        max_words=_VARIANT_OPTION_LABEL_MAX_WORDS,
        color_extractor=_extract_color_value,
    ):
        return ""
    if (
        _value_is_placeholder(cleaned)
        or _value_is_ui_noise(cleaned)
        or _value_is_axis_header_noise(field_name, cleaned)
        or _variant_axis_value_is_header(field_name, cleaned)
    ):
        return ""
    return cleaned


def _variant_size_axis_value_is_quantity_control(
    field_name: str,
    value: object,
) -> bool:
    return (
        normalized_variant_axis_key(field_name) == "size"
        and clean_text(value).lower() in _VARIANT_SIZE_QUANTITY_CONTROL_VALUES
    )


def _strip_variant_option_suffix_noise(value: object) -> str:
    cleaned = clean_text(value)
    if not cleaned:
        return ""
    stripped = cleaned
    for pattern in _VARIANT_OPTION_VALUE_SUFFIX_NOISE_PATTERNS:
        stripped = clean_text(pattern.sub("", stripped))
    return stripped or cleaned


def _value_is_placeholder(value: str) -> bool:
    lowered = clean_text(value).lower()
    if not lowered:
        return True
    return lowered in _VARIANT_PLACEHOLDER_VALUES_SET or any(
        lowered.startswith(prefix) for prefix in _VARIANT_PLACEHOLDER_PREFIXES_LOWER
    )


def _value_is_ui_noise(value: str) -> bool:
    return variant_option_value_is_noise(value)


def _extract_size_value(value: object) -> str:
    text = clean_text(value)
    if not text:
        return ""
    lowered_text = text.lower()

    def _size_candidate_is_gender_artifact(candidate: str) -> bool:
        if len(candidate) != 1 or not _GENDER_ARTIFACT_PATTERN:
            return False
        pattern = _GENDER_ARTIFACT_PATTERN.format(
            candidate=re.escape(candidate.lower())
        )
        return re.search(pattern, lowered_text) is not None

    for pattern in _VARIANT_SIZE_VALUE_EXTRACT_PATTERNS:
        match = pattern.search(text)
        if match is not None:
            candidate = clean_text(match.group(0))
            if len(candidate) == 1 and (
                (match.start() > 0 and text[match.start() - 1] in {"'", "’"})
                or _size_candidate_is_gender_artifact(candidate)
            ):
                continue
            # Numeric values <4 are usually counts like 2-pack, not child sizes.
            if candidate.isdigit() and int(candidate) < 4:
                continue
            return candidate
    tokens = [token for token in re.split(r"[^a-z0-9.]+", text, flags=re.I) if token]
    for width in range(min(3, len(tokens)), 0, -1):
        for index in range(0, len(tokens) - width + 1):
            candidate = clean_text(" ".join(tokens[index : index + width]))
            if not candidate:
                continue
            if _size_candidate_is_gender_artifact(candidate):
                continue
            # Numeric values <4 are usually counts like 2-pack, not child sizes.
            if candidate.isdigit() and int(candidate) < 4:
                continue
            if any(
                pattern.fullmatch(candidate) for pattern in _VARIANT_SIZE_VALUE_PATTERNS
            ):
                return candidate
    return ""


def _size_value_is_recognized(value: object) -> bool:
    cleaned = clean_text(value)
    if not cleaned:
        return False
    lowered = cleaned.casefold()
    if lowered in _COMMON_WORD_SIZE_VALUES:
        return True
    if any(pattern.fullmatch(cleaned) for pattern in _VARIANT_SIZE_VALUE_PATTERNS):
        return True
    extracted = _extract_size_value(cleaned)
    return bool(extracted) and extracted.casefold() == lowered


def _size_value_is_child_specific(value: object) -> bool:
    cleaned = clean_text(value)
    return bool(
        cleaned
        and any(pattern.fullmatch(cleaned) for pattern in _VARIANT_CHILD_SIZE_PATTERNS)
    )


def _record_targets_adult_sizes(record: dict[str, Any]) -> bool:
    probes = (
        record.get("title"),
        record.get("gender"),
        record.get("category"),
    )
    tokens: set[str] = set()
    for value in probes:
        tokens.update(_variant_title_tokens(value))
    return bool(tokens & _ADULT_SIZE_CONTEXT_TOKENS)


def _variant_color_from_title_or_url(
    variant: dict[str, Any],
    *,
    record: dict[str, Any],
) -> str:
    for candidate in (
        variant.get("title"),
        variant.get("name"),
        record.get("title"),
        _url_terminal_text(variant.get("url")),
        _url_terminal_text(record.get("url")),
    ):
        if color_value := _extract_color_value(candidate):
            return color_value
    return ""


def _extract_color_value(value: object) -> str:
    text = clean_text(value)
    if not text:
        return ""
    for chunk in reversed(
        [
            part
            for part in re.split(r"\s+[|/]\s+|\s+[–—-]\s+|\(", text)
            if clean_text(part)
        ]
    ):
        if color_value := _extract_trailing_color_phrase(chunk):
            return color_value
    return _extract_trailing_color_phrase(text)


def _extract_trailing_color_phrase(value: str) -> str:
    tokens = [
        token
        for token in re.findall(r"[A-Za-z0-9]+", clean_text(value))
        if token and not token.isdigit()
    ]
    if not tokens:
        return ""
    color_indexes = [
        index
        for index, token in enumerate(tokens)
        if token.lower() in _VARIANT_COLOR_HINT_WORDS
    ]
    if not color_indexes:
        return ""
    start = color_indexes[-1]
    while start > 0 and tokens[start - 1].lower() in _VARIANT_COLOR_HINT_WORDS:
        start -= 1
    if start > 0:
        previous = tokens[start - 1].lower()
        if (
            previous not in _STANDARD_SIZE_VALUES
            and previous not in _GENDER_KEYWORD_TOKENS_SET
        ):
            start -= 1
    end = color_indexes[-1] + 1
    while end < len(tokens) and tokens[end].lower() in _VARIANT_COLOR_HINT_WORDS:
        end += 1
    phrase = clean_text(" ".join(tokens[start:end]))
    if not phrase or len(phrase.split()) > 4:
        return ""
    return _title_preserving_acronyms(phrase)


def _title_preserving_acronyms(phrase: str) -> str:
    return " ".join(
        token if token.isupper() else token.capitalize() for token in phrase.split()
    )


def _value_is_axis_header_noise(field_name: str, value: str) -> bool:
    axis_name = normalized_variant_axis_key(field_name)
    lowered = clean_text(value).casefold()
    if axis_name not in {"condition", "state"}:
        return False
    return any(
        prefix and re.fullmatch(rf"{re.escape(prefix)}\s*\(\d+\)", lowered) is not None
        for prefix in _VARIANT_CONDITION_HEADER_PREFIXES
    )


def _variant_axis_value_is_header(field_name: str, value: str) -> bool:
    axis_name = clean_text(field_name).casefold()
    lowered_value = clean_text(value).casefold()
    axis_forms = {
        axis_name,
        f"{axis_name}s",
    }
    return lowered_value in axis_forms or any(
        form and lowered_value.startswith(f"{form}:") for form in axis_forms
    )

from __future__ import annotations

from ._support_shared import *  # noqa: F403


def _looks_like_utility_record(*, title: object, url: object) -> bool:
    return looks_like_utility_record(title=str(title or ""), url=str(url or ""))


def _identity_path(url: str) -> str:
    parsed = urlsplit(str(url or "").strip())
    path = str(parsed.path or "").strip()
    if path in {"", "/"} and str(parsed.fragment or "").strip():
        fragment = str(parsed.fragment or "").strip()
        return fragment if fragment.startswith("/") else f"/{fragment}"
    return path


def _summary_value(summary: dict[str, object], key: str) -> str | None:
    values = _object_dict(summary.get("acquisition_summary")).get(key)
    return str(next(iter(values))) if isinstance(values, dict) and values else None

def _primary_identity_tokens(value: str) -> set[str]:
    raw_value = str(value or "").strip()
    if not raw_value:
        return set()
    parsed = urlsplit(raw_value)
    if parsed.scheme or parsed.netloc or raw_value.startswith("/"):
        path = unquote(str(parsed.path or "").strip())
        segments = [segment for segment in path.split("/") if segment]
        for segment in reversed(segments):
            cleaned = re.sub(r"\.html?$", "", segment.strip().lower())
            if not cleaned or cleaned.isdigit() or cleaned in _IDENTITY_SEGMENT_SKIP:
                continue
            return _identity_tokens(cleaned)
        return set()
    return _identity_tokens(unquote(raw_value.lower()))

def _identity_tokens(value: str) -> set[str]:
    return {
        token
        for token in re.split(r"[^a-z0-9]+", str(value or "").strip().lower())
        if len(token) >= 2 and not token.isdigit() and token not in _IDENTITY_TOKEN_SKIP
    }

def _identity_overlap_count(left: set[str], right: set[str]) -> int:
    if not left or not right:
        return 0
    return len(left & right)

def _required_identity_overlap(token_count: int) -> int:
    if token_count <= 2:
        return token_count
    if token_count == 3:
        return 2
    return max(2, (token_count * 3 + 4) // 5)

def _looks_like_real_listing_row(row: object) -> bool:
    if not isinstance(row, dict):
        return False
    title = row.get("title")
    url = row.get("url")
    populated_fields = _safe_int(row.get("populated_fields"))
    return (
        bool(str(title or "").strip())
        and bool(str(url or "").strip())
        and (bool(row.get("price_present")) or populated_fields >= 3)
        and not _looks_like_utility_record(title=title, url=url)
    )

def _safe_int(value: object) -> int:
    try:
        return 0 if value in (None, "") else int(str(value))
    except (TypeError, ValueError):
        return 0

def _object_list(value: object) -> list[object]:
    return list(value) if isinstance(value, list) else []

def _object_dict(value: object) -> dict[str, object]:
    return dict(value) if isinstance(value, dict) else {}

def _looks_numeric_price(value: object) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    normalized = text
    if "." in text and "," in text:
        if text.rfind(",") > text.rfind("."):
            normalized = text.replace(".", "").replace(",", ".")
        else:
            normalized = text.replace(",", "")
    elif "," in text and re.fullmatch(r"^\d+,\d+$", text):
        normalized = text.replace(",", ".")
    elif "." in text and re.fullmatch(r"^\d{1,3}(?:\.\d{3})+$", text):
        normalized = text.replace(".", "")
    return bool(re.fullmatch(r"^\d+(?:\.\d+)?$", normalized))

def _price_number(value: object) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    normalized = re.sub(r"[^0-9.,]+", "", text)
    if "." in normalized and "," in normalized:
        decimal_separator = (
            "." if normalized.rfind(".") > normalized.rfind(",") else ","
        )
        thousands_separator = "," if decimal_separator == "." else "."
        normalized = normalized.replace(thousands_separator, "")
        normalized = normalized.replace(decimal_separator, ".")
    elif "," in normalized and re.fullmatch(r"\d+,\d{1,2}", normalized):
        normalized = normalized.replace(",", ".")
    else:
        normalized = normalized.replace(",", "")
    try:
        return float(normalized)
    except ValueError:
        return None

def _variant_row_has_axis(row: dict[str, object]) -> bool:
    axis_values = [
        str(row.get(field_name) or "").strip() for field_name in _VARIANT_AXIS_FIELDS
    ]
    return any(axis_values)

def _normalized_space(value: object) -> str:
    return " ".join(str(value or "").strip().split())

__all__ = tuple(
    name for name in globals() if not name.startswith("__")
)

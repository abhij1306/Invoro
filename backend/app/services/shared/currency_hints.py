from __future__ import annotations

from urllib.parse import urlparse

from app.services.config.extraction_rules import PAGE_URL_CURRENCY_HINTS_RAW


def currency_hint_from_page_url(page_url: object) -> str | None:
    code, _is_host_level = _currency_hint_from_page_url(page_url)
    return code


def detail_currency_hint_is_host_level(
    page_url: str,
    *,
    expected_currency: str,
) -> bool:
    code, is_host_level = _currency_hint_from_page_url(page_url)
    return code == expected_currency and is_host_level


def _currency_hint_from_page_url(page_url: object) -> tuple[str | None, bool]:
    parsed = urlparse(str(page_url or "").strip())
    hostname = str(parsed.hostname or "").strip().lower()
    path_segments = {
        segment.strip().lower()
        for segment in str(parsed.path or "").split("/")
        if segment.strip()
    }
    if not hostname and not path_segments:
        return None, False
    for token, code in dict(PAGE_URL_CURRENCY_HINTS_RAW or {}).items():
        match = _currency_token_match(
            token, code=code, hostname=hostname, path_segments=path_segments
        )
        if match is not None:
            return match
    return None, False


def _currency_token_match(
    token: object, *, code: object, hostname: str, path_segments: set[str]
) -> tuple[str, bool] | None:
    normalized = str(token).strip().lower()
    if not normalized:
        return None
    if normalized.startswith("/"):
        required_path = {part for part in normalized.split("/") if part}
        return (
            (str(code), False)
            if required_path and required_path <= path_segments
            else None
        )
    host_token, _, raw_path = normalized.partition("/")
    required_path = {part for part in raw_path.split("/") if part}
    host_matches = hostname == host_token or hostname.endswith(f".{host_token}")
    path_matches = not required_path or required_path <= path_segments
    return (str(code), True) if host_matches and path_matches else None

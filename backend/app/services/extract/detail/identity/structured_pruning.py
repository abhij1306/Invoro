from __future__ import annotations

__all__ = (
    "_structured_payload_is_breadcrumb_list",
    "_prune_irrelevant_detail_structured_payload",
    "_detail_structured_payload_is_irrelevant_product",
    "_preferred_structured_payload_url",
    "_structured_variant_leaf_conflicts_with_base_request",
)

from collections.abc import Callable
from functools import partial
from urllib.parse import urlparse

from app.services.config.extraction_rules import (
    DETAIL_PAYLOAD_LIST_LIMIT,
    DETAIL_PAYLOAD_MAX_DEPTH,
)
from app.services.extract.detail.identity.core import (
    detail_identity_codes_from_record_fields as _detail_identity_codes_from_record_fields,
    detail_identity_codes_from_url as _detail_identity_codes_from_url,
    detail_identity_tokens as _detail_identity_tokens,
    detail_query_identity_codes_from_url as _detail_query_identity_codes_from_url,
    detail_title_from_url as _detail_title_from_url,
    detail_url_is_utility as _detail_url_is_utility,
    detail_url_matches_requested_identity as _detail_url_matches_requested_identity,
    record_matches_requested_detail_identity as _record_matches_requested_detail_identity,
)
from app.services.field_url_normalization import same_site
from app.services.shared.field_coerce import clean_text, extract_urls, text_or_none

try:
    DETAIL_PAYLOAD_MAX_DEPTH_INT = int(DETAIL_PAYLOAD_MAX_DEPTH)
except (TypeError, ValueError):
    DETAIL_PAYLOAD_MAX_DEPTH_INT = 10


def _structured_payload_is_breadcrumb_list(payload: object) -> bool:
    if not isinstance(payload, dict):
        return False
    raw_type = payload.get("@type")
    type_values = raw_type if isinstance(raw_type, list) else [raw_type]
    return any(
        str(value or "").strip().lower() in {"breadcrumblist", "breadcrumb_list"}
        for value in type_values
    )


def _prune_irrelevant_detail_structured_payload(
    payload: object,
    *,
    page_url: str,
    requested_page_url: str,
    depth: int = 0,
    requested_title: str | None = None,
    requested_tokens: set[str] | None = None,
    requested_codes: set[str] | None = None,
    detail_title_from_url: Callable[[str], str | None] | None = None,
    detail_identity_tokens: Callable[[object], set[str]] | None = None,
    detail_identity_codes_from_url: Callable[[str], set[str]] | None = None,
) -> object | None:
    detail_title_from_url = detail_title_from_url or _detail_title_from_url
    detail_identity_tokens = detail_identity_tokens or _detail_identity_tokens
    detail_identity_codes_from_url = (
        detail_identity_codes_from_url or _detail_identity_codes_from_url
    )
    requested_title, requested_tokens, requested_codes = _requested_identity_context(
        depth,
        requested_page_url,
        requested_title,
        requested_tokens,
        requested_codes,
        detail_title_from_url,
        detail_identity_tokens,
        detail_identity_codes_from_url,
    )
    if depth >= DETAIL_PAYLOAD_MAX_DEPTH_INT:
        return None
    recurse = partial(
        _prune_irrelevant_detail_structured_payload,
        page_url=page_url,
        requested_page_url=requested_page_url,
        depth=depth + 1,
        requested_title=requested_title,
        requested_tokens=requested_tokens,
        requested_codes=requested_codes,
        detail_title_from_url=detail_title_from_url,
        detail_identity_tokens=detail_identity_tokens,
        detail_identity_codes_from_url=detail_identity_codes_from_url,
    )
    if isinstance(payload, list):
        cleaned_items = [
            recurse(item) for item in payload[: int(DETAIL_PAYLOAD_LIST_LIMIT or 50)]
        ]
        return [item for item in cleaned_items if item not in (None, "", [], {})]
    if not isinstance(payload, dict):
        return payload
    if _detail_structured_payload_is_irrelevant_product(
        payload,
        page_url=page_url,
        requested_page_url=requested_page_url,
        requested_title=requested_title,
        requested_tokens=requested_tokens,
        requested_codes=requested_codes,
        detail_identity_tokens=detail_identity_tokens,
    ):
        return None
    cleaned: dict[str, object] = {}
    for key, value in payload.items():
        cleaned_value = recurse(value)
        if cleaned_value in (None, "", [], {}):
            continue
        cleaned[str(key)] = cleaned_value
    return cleaned or None


def _requested_identity_context(
    depth: int,
    page_url: str,
    title: str | None,
    tokens: set[str] | None,
    codes: set[str] | None,
    title_from_url: Callable[[str], str | None],
    identity_tokens: Callable[[object], set[str]],
    identity_codes: Callable[[str], set[str]],
) -> tuple[str | None, set[str] | None, set[str] | None]:
    if depth != 0:
        return title, tokens, codes
    resolved_title = title or title_from_url(page_url)
    resolved_tokens = tokens or identity_tokens(resolved_title)
    resolved_codes = codes or identity_codes(page_url)
    return resolved_title, resolved_tokens, resolved_codes


def _detail_structured_payload_is_irrelevant_product(
    payload: dict[str, object],
    *,
    page_url: str,
    requested_page_url: str,
    requested_title: str | None = None,
    requested_tokens: set[str] | None = None,
    requested_codes: set[str] | None = None,
    detail_identity_tokens: Callable[[object], set[str]] | None = None,
) -> bool:
    detail_identity_tokens = detail_identity_tokens or _detail_identity_tokens
    if not _structured_payload_looks_product_like(payload):
        return False
    raw_candidate_url = payload.get("url") or payload.get("@id")
    candidate_urls = extract_urls(raw_candidate_url, page_url)
    candidate_url = _preferred_structured_payload_url(
        candidate_urls,
        requested_page_url=requested_page_url,
    )
    candidate_record = _structured_candidate_record(payload, candidate_url)
    if _structured_variant_leaf_conflicts_with_base_request(
        candidate_urls=candidate_urls,
        candidate_record=candidate_record,
        requested_page_url=requested_page_url,
        requested_codes=requested_codes,
    ):
        return True
    url_decision = _structured_candidate_url_irrelevance(
        candidate_url, candidate_record, requested_page_url
    )
    if url_decision is not None:
        return url_decision
    if not text_or_none(raw_candidate_url):
        candidate_title = clean_text(candidate_record.get("title"))
        if not candidate_title:
            return False
        requested_tokens = requested_tokens or detail_identity_tokens(requested_title)
        candidate_tokens = detail_identity_tokens(candidate_title)
        if (
            requested_tokens
            and candidate_tokens
            and requested_tokens.isdisjoint(candidate_tokens)
        ):
            return True
        return False
    candidate_codes = _detail_identity_codes_from_record_fields(candidate_record)
    if (
        requested_codes
        and candidate_codes
        and requested_codes.isdisjoint(candidate_codes)
    ):
        return True
    return False


def _structured_payload_looks_product_like(payload: dict[str, object]) -> bool:
    raw_type = payload.get("@type")
    normalized_type = (
        " ".join(raw_type) if isinstance(raw_type, list) else str(raw_type or "")
    )
    keys = {str(key).lower() for key in payload}
    strong_keys = {"sku", "mpn", "productid", "offers", "price", "image", "url"}
    descriptive_product = {"name", "description"} <= keys and bool(
        {"offers", "price", "image", "url"} & keys
    )
    return (
        "product" in normalized_type.lower()
        or bool(strong_keys & keys)
        or descriptive_product
    )


def _structured_candidate_record(
    payload: dict[str, object], candidate_url: str
) -> dict[str, object]:
    return {
        "title": payload.get("name") or payload.get("title"),
        "description": payload.get("description"),
        "url": candidate_url,
        "sku": payload.get("sku")
        or payload.get("productId")
        or payload.get("productID"),
        "part_number": payload.get("mpn"),
    }


def _structured_candidate_url_irrelevance(
    candidate_url: str,
    candidate_record: dict[str, object],
    requested_page_url: str,
) -> bool | None:
    if _record_matches_requested_detail_identity(
        candidate_record, requested_page_url=requested_page_url
    ):
        return False
    if not candidate_url:
        return None
    if _detail_url_matches_requested_identity(
        candidate_url, requested_page_url=requested_page_url
    ):
        return False
    if not same_site(candidate_url, requested_page_url):
        return None
    candidate_path = urlparse(candidate_url).path.rstrip("/")
    requested_path = urlparse(requested_page_url).path.rstrip("/")
    return bool(candidate_path and requested_path and candidate_path != requested_path)


def _preferred_structured_payload_url(
    candidate_urls: list[str],
    *,
    requested_page_url: str,
) -> str:
    if not candidate_urls:
        return ""
    requested_query_codes = _detail_query_identity_codes_from_url(requested_page_url)
    if requested_query_codes:
        for candidate_url in candidate_urls:
            if (
                _detail_query_identity_codes_from_url(candidate_url)
                & requested_query_codes
            ):
                return candidate_url
    for candidate_url in candidate_urls:
        if _detail_url_matches_requested_identity(
            candidate_url,
            requested_page_url=requested_page_url,
        ):
            return candidate_url
    for candidate_url in candidate_urls:
        if same_site(requested_page_url, candidate_url) and not _detail_url_is_utility(
            candidate_url
        ):
            return candidate_url
    return candidate_urls[0]


def _structured_variant_leaf_conflicts_with_base_request(
    *,
    candidate_urls: list[str],
    candidate_record: dict[str, object],
    requested_page_url: str,
    requested_codes: set[str] | None,
) -> bool:
    if len(candidate_urls) < 2:
        return False
    if _detail_query_identity_codes_from_url(requested_page_url):
        return False
    has_base_like_url = any(
        _detail_url_matches_requested_identity(
            candidate_url,
            requested_page_url=requested_page_url,
        )
        and not _detail_query_identity_codes_from_url(candidate_url)
        for candidate_url in candidate_urls
    )
    has_variant_specific_url = any(
        _detail_query_identity_codes_from_url(candidate_url)
        for candidate_url in candidate_urls
    )
    if not has_base_like_url or not has_variant_specific_url:
        return False
    return True

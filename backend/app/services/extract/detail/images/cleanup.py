from __future__ import annotations

__all__ = (
    "backfill_parent_image_from_variants",
    "sanitize_detail_images",
    "backfill_detail_image_from_html",
    "detail_image_matches_primary_family",
)

import logging
import re
from typing import Any
from urllib.parse import unquote, urlparse


from app.services.config.extraction_rules import (
    BROKEN_FETCH_IMAGE_PATH_PATTERN,
    DETAIL_IMAGE_COLORWAY_CODE_PATTERN,
    DETAIL_IMAGE_PRODUCT_CODE_PATTERN,
    DETAIL_IMAGE_VIEW_CODE_PATTERN,
    IMAGE_FAMILY_NOISE_TOKENS,
    IMAGE_PATH_TOKENS,
    LOW_RES_SWATCH_IMAGE_PATH_PATTERN,
)
from app.services.shared.field_coerce import (
    absolute_url,
    clean_text,
    extract_urls,
    text_or_none,
)
from app.services.shared.image_utils import query_dimension_is_tiny
from app.services.field_url_normalization import same_site
from app.services.dom.selector_engine import (
    dedupe_image_urls,
    upgrade_low_resolution_image_url,
)
from app.services.extract.detail.identity.core import (
    detail_identity_codes_match,
    detail_identity_codes_from_record_fields as _detail_identity_codes_from_record_fields,
    detail_identity_codes_from_url as _detail_identity_codes_from_url,
    detail_identity_tokens as _detail_identity_tokens,
    detail_title_from_url as _detail_title_from_url,
    detail_url_looks_like_product as _detail_url_looks_like_product,
    semantic_detail_identity_tokens as _semantic_detail_identity_tokens,
)
from app.services.config.detail_extraction_constants import (
    NON_PRODUCT_IMAGE_HINTS_LOWER as _NON_PRODUCT_IMAGE_HINTS_LOWER,
    PLACEHOLDER_IMAGE_URL_PATTERNS_LOWER as _PLACEHOLDER_IMAGE_URL_PATTERNS_LOWER,
)

logger = logging.getLogger(__name__)
_BROKEN_FETCH_IMAGE_PATH_RE = re.compile(
    getattr(
        BROKEN_FETCH_IMAGE_PATH_PATTERN, "pattern", BROKEN_FETCH_IMAGE_PATH_PATTERN
    ),
    re.I,
)
_LOW_RES_SWATCH_IMAGE_PATH_RE = re.compile(
    getattr(
        LOW_RES_SWATCH_IMAGE_PATH_PATTERN, "pattern", LOW_RES_SWATCH_IMAGE_PATH_PATTERN
    ),
    re.I,
)
_DETAIL_IMAGE_PRODUCT_CODE_RE = re.compile(
    getattr(
        DETAIL_IMAGE_PRODUCT_CODE_PATTERN, "pattern", DETAIL_IMAGE_PRODUCT_CODE_PATTERN
    )
)
_DETAIL_IMAGE_COLORWAY_CODE_RE = re.compile(
    getattr(
        DETAIL_IMAGE_COLORWAY_CODE_PATTERN,
        "pattern",
        DETAIL_IMAGE_COLORWAY_CODE_PATTERN,
    )
)
_DETAIL_IMAGE_VIEW_CODE_RE = re.compile(
    getattr(DETAIL_IMAGE_VIEW_CODE_PATTERN, "pattern", DETAIL_IMAGE_VIEW_CODE_PATTERN),
    re.I,
)
_title_primary_overlap_min = 4


def backfill_parent_image_from_variants(record: dict[str, Any]) -> None:
    if text_or_none(record.get("image_url")):
        return
    for variant in record.get("variants") or []:
        if not isinstance(variant, dict):
            continue
        image_url = text_or_none(variant.get("image_url"))
        if image_url:
            record["image_url"] = image_url
            return


def _sanitize_detail_images(record: dict[str, Any], *, identity_url: str) -> None:
    raw_images = [
        text_or_none(record.get("image_url")),
        *[text_or_none(value) for value in record.get("additional_images") or []],
    ]
    images = [upgrade_low_resolution_image_url(image) for image in raw_images if image]
    if not images:
        return
    cleaned = _usable_detail_images(images, identity_url)
    if not cleaned:
        record.pop("image_url", None)
        record.pop("additional_images", None)
        return
    primary_image = _preferred_primary_image(cleaned, record=record) or cleaned[0]
    ordered_cleaned = [
        primary_image,
        *[image for image in cleaned if image != primary_image],
    ]
    family_cleaned = [
        image
        for image in ordered_cleaned
        if detail_image_matches_primary_family(
            image, primary_image=primary_image, title=record.get("title")
        )
    ]
    merged = dedupe_image_urls(family_cleaned) or _dedupe_cleaned_detail_images(
        family_cleaned
    )
    if not merged:
        record.pop("image_url", None)
        record.pop("additional_images", None)
        return
    record["image_url"] = merged[0]
    if len(merged) > 1:
        record["additional_images"] = merged[1:]
    else:
        record.pop("additional_images", None)


def _usable_detail_images(images: list[str], identity_url: str) -> list[str]:
    usable: list[str] = []
    for image in images:
        normalized = (
            "https://" + image[7:] if image.lower().startswith("http://") else image
        )
        if _detail_image_candidate_is_usable(normalized, identity_url=identity_url):
            usable.append(normalized)
    return usable


def sanitize_detail_images(record: dict[str, Any], *, identity_url: str) -> None:
    _sanitize_detail_images(record, identity_url=identity_url)


def _backfill_detail_image_from_html(
    record: dict[str, Any],
    *,
    soup: Any,
    identity_url: str,
) -> None:
    if text_or_none(record.get("image_url")):
        return
    candidates: list[str] = []
    for node in soup.select(
        "meta[property='og:image'], meta[name='twitter:image'], "
        "link[rel='preload'][as='image'], main img, [role='main'] img"
    ):
        raw = node.get("content") or node.get("href") or node.get("src")
        if not raw:
            continue
        urls = extract_urls(raw, identity_url)
        candidates.extend(urls or [absolute_url(identity_url, raw)])
    for url in _dedupe_cleaned_detail_images(candidates):
        if _detail_image_candidate_is_usable(url, identity_url=identity_url):
            record["image_url"] = url
            field_sources = record.setdefault("_field_sources", {})
            if isinstance(field_sources, dict):
                field_sources.setdefault("image_url", []).append("html_image")
            return


def backfill_detail_image_from_html(
    record: dict[str, Any],
    *,
    soup: Any,
    identity_url: str,
) -> None:
    _backfill_detail_image_from_html(record, soup=soup, identity_url=identity_url)


def _dedupe_cleaned_detail_images(urls: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for url in urls:
        cleaned = text_or_none(url)
        if not cleaned:
            continue
        key = cleaned.casefold()
        if key in seen:
            continue
        seen.add(key)
        merged.append(cleaned)
    return merged


def _detail_image_candidate_is_usable(url: str, *, identity_url: str) -> bool:
    parsed = urlparse(url)
    path = str(parsed.path or "").strip()
    if _detail_image_url_shape_is_rejected(url, parsed, path):
        return False
    lowered = url.lower()
    if _detail_image_url_content_is_rejected(path, lowered):
        return False
    if (
        same_site(identity_url, url)
        and _detail_url_looks_like_product(url)
        and not _detail_path_looks_like_image_asset(path, lowered)
    ):
        return False
    if re.search(r"/products?/[\d?=&-]*$", lowered):
        return False
    return not _detail_image_identity_is_rejected(url, identity_url)


def _detail_image_url_shape_is_rejected(url: str, parsed: Any, path: str) -> bool:
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return True
    if not path or path == "/" or _BROKEN_FETCH_IMAGE_PATH_RE.fullmatch(path):
        return True
    return bool(
        _LOW_RES_SWATCH_IMAGE_PATH_RE.search(url)
        and query_dimension_is_tiny(parsed.query)
    )


def _detail_image_url_content_is_rejected(path: str, lowered: str) -> bool:
    return bool(
        "base64," in lowered
        or lowered.startswith("data:")
        or any(pattern in lowered for pattern in _PLACEHOLDER_IMAGE_URL_PATTERNS_LOWER)
        or any(pattern in lowered for pattern in _NON_PRODUCT_IMAGE_HINTS_LOWER)
        or _detail_image_url_is_extensionless_transform(path)
        or _detail_image_url_looks_like_pdp_link(path, lowered)
    )


def _detail_image_identity_is_rejected(url: str, identity_url: str) -> bool:
    title = _detail_image_title_from_url(url)
    if not title or not _detail_image_title_has_identity_signal(title):
        return False
    candidate_codes = _detail_identity_codes_from_url(url)
    if candidate_codes and detail_identity_codes_match(
        _detail_identity_codes_from_url(identity_url), candidate_codes
    ):
        return False
    return not _detail_image_title_matches_requested_identity(
        title, requested_page_url=identity_url
    )


_PDP_PATH_SEGMENT_RE = re.compile(
    r"/(?:ip|p|pd|dp|product|products|item|items|itm|shop)(?:/|$)",
    re.I,
)


def _detail_image_url_looks_like_pdp_link(path: str, lowered_url: str) -> bool:
    """A URL with no image extension whose path includes a PDP segment is a
    page link, not an image asset.

    Examples flagged:
      ``https://www.walmart.com/ip/Apple-AirPods-…/HEX``  → /ip/ + no extension
      ``https://example.com/products/widget``             → /products/ + no extension
    Examples NOT flagged:
      ``https://i5.walmartimages.com/asr/…jpeg``           → has .jpeg
      ``https://example.com/cdn/products/widget.jpg``     → image-asset path token
    """
    if re.search(r"\.(?:avif|gif|jpe?g|png|svg|tiff?|webp)(?:$|\?)", lowered_url):
        return False
    if _detail_path_looks_like_image_asset(path, lowered_url):
        return False
    return _PDP_PATH_SEGMENT_RE.search(path) is not None


def _detail_image_url_is_extensionless_transform(path: str) -> bool:
    filename = unquote(str(path or "").rsplit("/", 1)[-1])
    if re.search(r"\.(?:avif|gif|jpe?g|png|svg|tiff?|webp)$", filename, re.I):
        return False
    return re.search(r"\._[A-Z]+_[A-Z]{2}\d+\s*$", filename, re.I) is not None


def _detail_path_looks_like_image_asset(path: str, lowered_url: str) -> bool:
    lowered_path = str(path or "").lower()
    if re.search(r"\.(?:avif|gif|jpe?g|png|svg|tiff?|webp)(?:$|\?)", lowered_url):
        return True
    return any(token in lowered_path for token in IMAGE_PATH_TOKENS)


# skipcq: PY-R1000
def detail_image_matches_primary_family(
    url: str,
    *,
    primary_image: str,
    title: object,
) -> bool:
    if url == primary_image:
        return True
    primary_product_code = _detail_image_product_code(primary_image)
    candidate_product_code = _detail_image_product_code(url)
    if _detail_image_product_codes_conflict(
        primary_product_code, candidate_product_code
    ):
        return False
    primary_color_code = _detail_image_colorway_code(primary_image)
    candidate_color_code = _detail_image_colorway_code(url)
    if _detail_image_color_codes_conflict(
        primary_color_code,
        candidate_color_code,
        primary_product_code,
        candidate_product_code,
    ):
        return False
    primary_tokens = _detail_image_family_tokens(primary_image)
    candidate_tokens = _detail_image_family_tokens(url)
    title_tokens = _semantic_detail_identity_tokens(title)
    if (
        primary_product_code
        and not candidate_product_code
        and _tokens_support_same_image(title_tokens, candidate_tokens)
    ):
        return True
    # Reject when both filenames carry long alphabetic distinguishing tokens
    # that share a prefix but disagree on the tail (different colorway slugs
    # under the same family code, e.g. ``therockerjetblack`` vs
    # ``therockerfalcon``).
    if _detail_image_family_tokens_disagree_on_colorway(
        primary_tokens, candidate_tokens
    ):
        return False
    if _candidate_loses_primary_title_overlap(
        primary_tokens, candidate_tokens, title_tokens
    ):
        return False
    if _image_family_tokens_match(
        primary_tokens, candidate_tokens, primary_product_code, candidate_product_code
    ):
        return True
    if _tokens_support_same_image(title_tokens, candidate_tokens):
        return True
    if _detail_image_media_codes_match(primary_image, url):
        return True
    return not primary_tokens and not title_tokens


def _detail_image_product_codes_conflict(
    primary: str | None, candidate: str | None
) -> bool:
    return bool(primary and candidate and primary != candidate)


def _detail_image_color_codes_conflict(
    primary_color: str | None,
    candidate_color: str | None,
    primary_product: str | None,
    candidate_product: str | None,
) -> bool:
    same_product = bool(
        primary_product and candidate_product and primary_product == candidate_product
    )
    return bool(
        primary_color
        and candidate_color
        and primary_color != candidate_color
        and not same_product
    )


def _tokens_support_same_image(reference: set[str], candidate: set[str]) -> bool:
    return bool(
        reference and candidate and len(reference & candidate) >= min(2, len(reference))
    )


def _image_family_tokens_match(
    primary: set[str],
    candidate: set[str],
    primary_code: str | None,
    candidate_code: str | None,
) -> bool:
    return bool(
        primary
        and candidate
        and primary & candidate
        and not (primary_code and not candidate_code)
    )


def _detail_image_media_codes_match(primary_url: str, candidate_url: str) -> bool:
    primary = _detail_image_media_code(primary_url)
    candidate = _detail_image_media_code(candidate_url)
    return bool(primary and candidate and primary == candidate)


def _candidate_loses_primary_title_overlap(
    primary: set[str], candidate: set[str], title: set[str]
) -> bool:
    overlap = primary & title
    return bool(
        overlap
        and candidate
        and len(overlap) >= _title_primary_overlap_min
        and len(candidate & overlap) < min(_title_primary_overlap_min, len(overlap))
    )


def _detail_image_family_tokens_disagree_on_colorway(
    primary_tokens: set[str],
    candidate_tokens: set[str],
) -> bool:
    """Detect distinct colorway slugs sharing a common model prefix.

    Kith / Shopify product image filenames use ``ST40002-02000TheRockerJetBlack``
    vs ``ST40002-91000TheRockerFalcon``. Tokenization yields long alphabetic
    fragments (``02000therockerjetblack`` / ``91000therockerfalcon``) that
    share a prefix (``therockerjetblack`` / ``therockerfalcon`` share
    ``therocker``) but disagree on the tail. Treat such pairs as cross-
    colorway leakage.
    """
    if not primary_tokens or not candidate_tokens:
        return False
    primary_long = {token for token in primary_tokens if len(token) >= 10}
    candidate_long = {token for token in candidate_tokens if len(token) >= 10}
    if not primary_long or not candidate_long:
        return False
    # Skip when there is a literal long-token match — same colorway.
    if primary_long & candidate_long:
        return False
    for primary_token in primary_long:
        primary_alpha_tail = _image_colorway_alpha_tail(primary_token)
        if not primary_alpha_tail:
            continue
        for candidate_token in candidate_long:
            candidate_alpha_tail = _image_colorway_alpha_tail(candidate_token)
            if not candidate_alpha_tail:
                continue
            if _colorway_tails_conflict(primary_alpha_tail, candidate_alpha_tail):
                return True
    return False


def _image_colorway_alpha_tail(token: str) -> str:
    if not token.isalnum() or not any(character.isalpha() for character in token):
        return ""
    tail = token.lstrip("0123456789")
    return tail if len(tail) >= 6 else ""


def _colorway_tails_conflict(primary: str, candidate: str) -> bool:
    shared = _shared_prefix_length(primary, candidate)
    return shared >= 6 and shared < min(len(primary), len(candidate))


def _shared_prefix_length(left: str, right: str) -> int:
    limit = min(len(left), len(right))
    index = 0
    while index < limit and left[index] == right[index]:
        index += 1
    return index


def _detail_image_title_from_url(url: str) -> str | None:
    path = unquote(urlparse(url).path)
    filename = path.rsplit("/", 1)[-1]
    stem = re.sub(r"\.(?:avif|gif|jpe?g|png|svg|tiff?|webp)$", "", filename, flags=re.I)
    if not stem or re.fullmatch(r"img\d+", stem, re.I):
        return None
    if _detail_image_stem_looks_encoded(stem):
        return None
    normalized = clean_text(
        re.sub(
            r"[_-]+",
            " ",
            re.sub(r"(?<=[a-z])(?=[A-Z])", " ", stem),
        )
    )
    return normalized or None


# skipcq: PY-R1000
def _detail_image_stem_looks_encoded(stem: str) -> bool:
    readable_tokens = [
        token for token in re.split(r"[^A-Za-z]+", str(stem or "")) if len(token) >= 4
    ]
    if len(readable_tokens) >= 2 and re.search(r"[-_]", str(stem or "")):
        return False
    compact = re.sub(r"[^A-Za-z0-9_-]+", "", str(stem or ""))
    alpha = re.sub(r"[^A-Za-z]+", "", compact)
    if _short_image_stem_looks_encoded(compact, alpha):
        return True
    if len(compact) < 24:
        return False
    if not re.fullmatch(r"[A-Za-z0-9_-]+", compact):
        return False
    if not (re.search(r"[A-Z]", compact) and re.search(r"[a-z]", compact)):
        return False
    return (
        len(re.findall(r"[A-Z]", compact)) >= 3 and len(re.findall(r"\d", compact)) >= 2
    )


def _short_image_stem_looks_encoded(compact: str, alpha: str) -> bool:
    return bool(
        6 <= len(compact) < 24
        and re.search(r"[A-Z]", compact)
        and re.search(r"[a-z]", compact)
        and not re.search(r"[aeiou]{2,}", alpha, re.I)
    )


def _detail_image_title_has_identity_signal(title: str) -> bool:
    return bool(
        len(_semantic_detail_identity_tokens(title)) >= 2
        or _detail_identity_codes_from_record_fields({"title": title})
    )


# skipcq: PY-R1000
def _detail_image_title_matches_requested_identity(
    title: str,
    *,
    requested_page_url: str,
) -> bool:
    requested_codes = _detail_identity_codes_from_url(requested_page_url)
    candidate_codes = _detail_identity_codes_from_record_fields({"title": title})
    if _detail_image_identity_codes_match(requested_codes, candidate_codes):
        return True
    requested_title = _detail_title_from_url(requested_page_url)
    normalized_requested_title = clean_text(requested_title)
    normalized_candidate_title = clean_text(title)
    if _detail_image_title_prefix_matches(
        normalized_requested_title, normalized_candidate_title
    ):
        return True
    requested_path = str(urlparse(requested_page_url).path or "")
    requested_slug = _detail_requested_slug(requested_path)
    if _detail_image_title_prefix_matches(requested_slug, normalized_candidate_title):
        return True
    requested_semantic_tokens = _semantic_detail_identity_tokens(
        requested_title or requested_page_url
    )
    if not requested_semantic_tokens and requested_title:
        requested_semantic_tokens = _semantic_detail_identity_tokens(requested_page_url)
    candidate_semantic_tokens = _semantic_detail_identity_tokens(title)
    if requested_semantic_tokens and candidate_semantic_tokens:
        semantic_overlap = requested_semantic_tokens & candidate_semantic_tokens
        if len(semantic_overlap) >= min(2, len(requested_semantic_tokens)):
            return True
    requested_tokens = _detail_identity_tokens(requested_title or requested_page_url)
    candidate_tokens = _detail_identity_tokens(title)
    if not requested_tokens or not candidate_tokens:
        return False
    overlap = requested_tokens & candidate_tokens
    minimum_overlap = 2 if min(len(requested_tokens), len(candidate_tokens)) <= 4 else 4
    return len(overlap) >= min(minimum_overlap, len(requested_tokens))


def _detail_image_identity_codes_match(
    requested: set[str], candidate: set[str]
) -> bool:
    return bool(
        requested and candidate and detail_identity_codes_match(requested, candidate)
    )


def _detail_image_title_prefix_matches(requested: str, candidate: str) -> bool:
    return bool(
        requested and candidate and candidate.lower().startswith(requested.lower())
    )


def _detail_requested_slug(path: str) -> str:
    segments = [
        clean_text(re.sub(r"[_-]+", " ", segment))
        for segment in path.split("/")
        if clean_text(re.sub(r"[_-]+", " ", segment))
    ]
    return next(
        (
            segment
            for segment in reversed(segments)
            if segment.lower() not in {"product", "products", "p", "pd", "dp"}
        ),
        "",
    )


def _detail_image_family_tokens(url: str) -> set[str]:
    parts = [
        segment
        for segment in re.split(r"[^a-z0-9]+", unquote(urlparse(url).path).lower())
        if len(segment) >= 4
    ]
    return {part for part in parts if part not in IMAGE_FAMILY_NOISE_TOKENS}


def _detail_image_media_code(url: str) -> str | None:
    match = re.search(r"/([a-z]\d{5,})/", urlparse(url).path.lower())
    if match is not None:
        return match.group(1)
    return None


def _detail_image_product_code(url: str) -> str | None:
    path = unquote(urlparse(str(url or "")).path)
    match = _DETAIL_IMAGE_PRODUCT_CODE_RE.search(path)
    if match is not None:
        return match.group(1).upper()
    return None


def _detail_image_colorway_code(url: str) -> str | None:
    path = unquote(urlparse(str(url or "")).path)
    filename = path.rsplit("/", 1)[-1]
    match = _DETAIL_IMAGE_COLORWAY_CODE_RE.search(filename)
    if match is None:
        return None
    code = match.group(1).upper()
    if _DETAIL_IMAGE_VIEW_CODE_RE.fullmatch(code):
        return None
    return code


def _preferred_primary_image(
    images: list[str],
    *,
    record: dict[str, Any],
) -> str | None:
    color = clean_text(record.get("color"))
    if not color:
        return None
    candidates = _color_code_candidates(color)
    if not candidates:
        return None
    for image in images:
        path = unquote(urlparse(image).path).upper()
        if any(
            re.search(rf"(?:^|[_\-/]){re.escape(code)}(?:[_\-.]|$)", path)
            for code in candidates
        ):
            return image
    return None


def _color_code_candidates(color: str) -> tuple[str, ...]:
    codes: list[str] = []
    words = re.findall(r"[A-Za-z]+", color)
    for word in words:
        upper = word.upper()
        if len(upper) >= 3:
            codes.append(upper[:3])
        consonants = re.sub(r"[AEIOU]", "", upper[1:])
        if len(upper) >= 2 and consonants:
            codes.append((upper[0] + consonants)[:3])
    initials = "".join(word[0].upper() for word in words)
    if len(initials) >= 2:
        codes.append(initials[:4])
    seen: set[str] = set()
    merged: list[str] = []
    for code in codes:
        if len(code) < 2 or code in seen:
            continue
        seen.add(code)
        merged.append(code)
    return tuple(merged)

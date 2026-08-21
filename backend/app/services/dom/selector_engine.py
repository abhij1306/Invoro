# ruff: noqa: E402, F401, F821, F822
"""Shared DOM field recovery, DOM text cleanup, and image/section normalization."""

from __future__ import annotations

import logging
import re
import regex as regex_lib
from collections.abc import Callable
from typing import cast
from urllib.parse import urlparse

from app.services.dom.html_parser import BeautifulSoup, NavigableString, Tag
from lxml import (
    etree,
)  # skipcq: BAN-B410 - lxml is used in HTML parsing mode for sanitized DOM recovery, not arbitrary XML.
from lxml import (
    html as lxml_html,
)  # skipcq: BAN-B410 - lxml.html.fromstring parses sanitized HTML snippets, not arbitrary XML.

from app.services.config.extraction_rules import (
    CROSS_LINK_CONTAINER_HINTS,
    DETAIL_CROSS_PRODUCT_CONTAINER_TOKENS,
    DETAIL_IMAGE_URL_ATTRS,
    DETAIL_LONG_TEXT_RANK_FIELDS,
    DETAIL_PRIMARY_DOM_CONTEXT_SELECTOR,
    DETAIL_TEXT_HIDDEN_STYLE_TOKENS,
    DETAIL_TEXT_SCOPE_EXCLUDE_TOKENS,
    DETAIL_TEXT_SCOPE_PRIORITY_TOKENS,
    DETAIL_TEXT_SCOPE_SELECTORS,
    EXTRACTION_RULES,
    MAX_SELECTOR_MATCHES,
    VARIANT_OPTION_TEXT_CHILD_DROP_PATTERNS,
    VARIANT_OPTION_TEXT_FIELDS,
    SCOPE_PRODUCT_CONTEXT_TOKENS,
    SCOPE_SCORE_MAIN_WEIGHT,
    SCOPE_SCORE_PRIORITY_WEIGHT,
    SCOPE_SCORE_PRODUCT_CONTEXT_WEIGHT,
)
from app.services.config.surface_hints import detail_path_hints
from app.services.dom.image_extraction import (
    candidate_image_urls_from_node,  # noqa: F401 - public compatibility export
    canonical_image_url,  # noqa: F401 - public compatibility export
    dedupe_image_urls,  # noqa: F401 - public compatibility export
    extract_page_images as extract_page_images_impl,
    image_candidate_score,  # noqa: F401 - public compatibility export
    is_garbage_image_candidate,  # noqa: F401 - public compatibility export
    is_in_product_gallery_context,
    looks_like_image_asset_url,
    srcset_urls,
    upgrade_low_resolution_image_url,  # noqa: F401 - public compatibility export
)
from app.services.dom.section_extraction import (
    extract_feature_rows,  # noqa: F401 - public compatibility export
    extract_heading_sections,
    extract_label_value_pairs,
    section_text_is_meaningful,
)
from app.services.config.runtime_settings import crawler_runtime_settings
from app.services.config.field_mappings import ADDITIONAL_IMAGES_FIELD
from app.services.dom.content_extractability import (
    requested_content_extractability_impl,
)
from app.services.dom.query import safe_select, walk_ancestors
from app.services.extraction_html_helpers import html_to_text
from app.services.field_policy import (
    normalize_field_key,
    normalize_requested_field,
)
from app.services.extract.field_candidates import add_candidate
from app.services.shared.field_coerce import (
    IMAGE_FIELDS,
    LONG_TEXT_FIELDS,
    URL_FIELDS,
    absolute_url,
    clean_text,
    coerce_field_value,
    extract_urls,
    surface_alias_lookup,
    surface_fields,
)
from app.services.shared.coerce_primitives import safe_int as _safe_int
from app.services.shared.regex_patterns import compile_regex_patterns
from app.services.dom.xpath_service import validate_xpath_syntax

logger = logging.getLogger(__name__)

__all__ = [
    "candidate_image_urls_from_node",
    "canonical_image_url",
    "dedupe_image_urls",
    "extract_feature_rows",
    "image_candidate_score",
    "is_garbage_image_candidate",
    "safe_select",
    "upgrade_low_resolution_image_url",
]

_cross_product_container_tokens = tuple(clean_text(token).lower() for token in tuple(DETAIL_CROSS_PRODUCT_CONTAINER_TOKENS or ()) if clean_text(token))
_scope_product_context_tokens = tuple(clean_text(token).lower() for token in tuple(SCOPE_PRODUCT_CONTEXT_TOKENS or ()) if clean_text(token))
_max_selector_matches = _safe_int(MAX_SELECTOR_MATCHES, default=12) or 12
_scope_score_main_weight = _safe_int(SCOPE_SCORE_MAIN_WEIGHT, default=4000) or 4000
_scope_score_priority_weight = _safe_int(SCOPE_SCORE_PRIORITY_WEIGHT, default=2000) or 2000
_scope_score_product_context_weight = _safe_int(SCOPE_SCORE_PRODUCT_CONTEXT_WEIGHT, default=1000) or 1000

def _compile_variant_option_child_drop_patterns() -> tuple[re.Pattern[str], ...]:
    return compile_regex_patterns(
        tuple(VARIANT_OPTION_TEXT_CHILD_DROP_PATTERNS or ()),
        logger=logger,
        warning_message="Skipping invalid variant option child-drop pattern: %r",
    )

_VARIANT_OPTION_CHILD_DROP_RE = _compile_variant_option_child_drop_patterns()

_PAGE_FILE_EXTENSIONS = (".asp", ".aspx", ".htm", ".html", ".jsp", ".php")

def _selector_regex_timeout_seconds() -> float | None:
    try:
        timeout = float(crawler_runtime_settings.selector_regex_timeout_seconds)
    except (TypeError, ValueError):
        logger.warning(
            "Invalid selector_regex_timeout_seconds=%r; disabling selector regex timeout",
            crawler_runtime_settings.selector_regex_timeout_seconds,
        )
        return None
    return timeout if timeout > 0 else None

_detail_text_scope_selectors = tuple(selector for selector in tuple(DETAIL_TEXT_SCOPE_SELECTORS or ()) if str(selector).strip())
_detail_text_scope_priority_tokens = tuple(str(token).lower() for token in tuple(DETAIL_TEXT_SCOPE_PRIORITY_TOKENS or ()) if str(token).strip())
_detail_text_scope_exclude_tokens = tuple(str(token).lower() for token in tuple(DETAIL_TEXT_SCOPE_EXCLUDE_TOKENS or ()) if str(token).strip())
_detail_text_hidden_style_tokens = tuple(str(token).lower() for token in tuple(DETAIL_TEXT_HIDDEN_STYLE_TOKENS or ()) if str(token).strip())

def _node_attr_text(node: Tag, *, max_depth: int = 6) -> str:
    parts: list[str] = []
    current: Tag | None = node
    depth = 0
    while isinstance(current, Tag) and depth < max_depth:
        for attr_name in (
            "id",
            "class",
            "data-component",
            "data-qa",
            "data-section",
            "data-section-id",
            "data-section-type",
            "data-testid",
            "aria-label",
        ):
            value = current.get(attr_name)
            if isinstance(value, list):
                parts.extend(str(item) for item in value if item)
            elif value not in (None, "", [], {}):
                parts.append(str(value))
        parent = current.parent
        current = parent if isinstance(parent, Tag) else None
        depth += 1
    return " ".join(parts).lower()

def _field_uses_scoped_text(field_name: str) -> bool:
    return field_name in DETAIL_LONG_TEXT_RANK_FIELDS

def _node_within_scope(node: Tag, scope: Tag) -> bool:
    current: Tag | None = node
    while isinstance(current, Tag):
        if current == scope:
            return True
        parent = current.parent
        current = parent if isinstance(parent, Tag) else None
    return False

def _node_style_is_hidden(node: Tag) -> bool:
    style = str(node.get("style") or "").strip().lower()
    return bool(style) and any(token in style for token in _detail_text_hidden_style_tokens)

def _node_is_hidden_or_auxiliary(node: Tag) -> bool:
    current: Tag | None = node
    depth = 0
    while isinstance(current, Tag) and depth < 8:
        attrs = getattr(current, "attrs", None)
        if not isinstance(attrs, dict):
            parent = current.parent
            current = parent if isinstance(parent, Tag) else None
            depth += 1
            continue
        if _node_attributes_are_hidden(current, attrs):
            return True
        context = _node_attr_text(current, max_depth=1)
        if any(token in context for token in _detail_text_scope_exclude_tokens):
            return True
        parent = current.parent
        current = parent if isinstance(parent, Tag) else None
        depth += 1
    return False

def _node_attributes_are_hidden(node: Tag, attrs: dict[object, object]) -> bool:
    if "hidden" in attrs:
        return True
    if str(attrs.get("aria-hidden") or "").strip().lower() == "true":
        return True
    if str(attrs.get("aria-modal") or "").strip().lower() == "true":
        return True
    role = str(attrs.get("role") or "").strip().lower()
    return role in {"dialog", "alertdialog"} or _node_style_is_hidden(node)

def _node_has_cross_product_cluster(node: Tag, *, page_url: str = "") -> bool:
    if not isinstance(getattr(node, "attrs", None), dict):
        return False
    links: list[str] = []
    for link in node.select("a[href]")[:_max_selector_matches]:
        link_text = clean_text(link.get_text(" ", strip=True) or link.get("aria-label"))
        if not link_text:
            continue
        resolved = absolute_url(page_url, str(link.get("href") or ""))
        if resolved:
            links.append(resolved)
    product_links = [link for link in links if any(marker in urlparse(link).path.lower() for marker in detail_path_hints("ecommerce_detail"))]
    if len(set(product_links)) >= 2:
        return True
    context = _node_attr_text(node, max_depth=1)
    return any(token in context for token in _cross_product_container_tokens)

def _candidate_text_scope_nodes(root: BeautifulSoup | Tag) -> list[Tag]:
    candidates: list[Tag] = []
    seen: set[int] = set()
    for selector in _detail_text_scope_selectors:
        for node in safe_select(root, selector):
            if id(node) in seen or _node_is_hidden_or_auxiliary(node):
                continue
            seen.add(id(node))
            candidates.append(node)
    return candidates

def _scope_score(node: Tag) -> tuple[int, int]:
    context = _node_attr_text(node, max_depth=2)
    text_len = len(clean_text(node.get_text(" ", strip=True)))
    score = text_len
    if node.name in {"main", "article"} or str(node.get("role") or "").strip().lower() == "main":
        score += _scope_score_main_weight
    if any(token in context for token in _detail_text_scope_priority_tokens):
        score += _scope_score_priority_weight
    if DETAIL_PRIMARY_DOM_CONTEXT_SELECTOR and (
        node.select_one(DETAIL_PRIMARY_DOM_CONTEXT_SELECTOR) is not None or any(token in context for token in _scope_product_context_tokens)
    ):
        score += _scope_score_product_context_weight
    return score, text_len

def _scope_is_product_like(node: Tag) -> bool:
    context = _node_attr_text(node, max_depth=2)
    if any(token in context for token in _scope_product_context_tokens):
        return True
    return bool(DETAIL_PRIMARY_DOM_CONTEXT_SELECTOR and node.select_one(DETAIL_PRIMARY_DOM_CONTEXT_SELECTOR) is not None)

def _best_text_scope(root: BeautifulSoup | Tag) -> Tag | None:
    candidates = _candidate_text_scope_nodes(root)
    if not candidates:
        return None
    best = max(candidates, key=_scope_score)
    return best if _scope_is_product_like(best) else None

def _clone_visible_only(
    node: Tag | NavigableString,
    *,
    remaining_depth: int = 50,
    _soup: BeautifulSoup | None = None,
) -> Tag | NavigableString | None:
    if remaining_depth <= 0:
        return None
    if not isinstance(node, Tag):
        return NavigableString(str(node)) if isinstance(node, NavigableString) else None
    if _node_is_hidden_or_auxiliary(node):
        return None
    _soup = _soup or BeautifulSoup("", "html.parser")
    clone = _soup.new_tag(node.name, attrs=dict(getattr(node, "attrs", {}) or {}))
    for child in node.children:
        if (
            child_clone := _clone_visible_only(
                cast(Tag | NavigableString, child),
                remaining_depth=remaining_depth - 1,
                _soup=_soup,
            )
        ) is not None:
            clone.append(child_clone)
    return clone

def _pruned_text_scope_root(root: BeautifulSoup | Tag) -> BeautifulSoup | Tag:
    scope = _best_text_scope(root)
    if scope is None:
        return root
    cloned_scope = _clone_visible_only(scope)
    return cloned_scope if isinstance(cloned_scope, Tag) else root

def _is_other_detail_link(
    url: str,
    page_url: str,
    *,
    surface: str | None = None,
    link_node: Tag | None = None,
) -> bool:
    candidate = clean_text(url)
    if not candidate:
        return False
    if _detail_link_candidate_is_ignored(candidate):
        return False
    page_parts = urlparse(page_url)
    candidate_parts = urlparse(candidate)
    same_host, same_path = _url_host_path_matches(page_parts, candidate_parts)
    if same_host and same_path:
        return False
    is_detail_surface = "detail" in str(surface or "").lower()
    if _detail_link_is_gallery_media(is_detail_surface, link_node):
        return False
    return _different_detail_link_signal(
        candidate_parts.path or "",
        surface,
        is_detail_surface,
        same_host,
        same_path,
        link_node,
    )

def _detail_link_candidate_is_ignored(candidate: str) -> bool:
    return candidate.lower().startswith(("#", "javascript:", "mailto:")) or looks_like_image_asset_url(candidate)

def _detail_link_is_gallery_media(is_detail_surface: bool, link_node: Tag | None) -> bool:
    return bool(is_detail_surface and link_node is not None and is_in_product_gallery_context(link_node))

def _url_host_path_matches(page_parts: object, candidate_parts: object) -> tuple[bool, bool]:
    page_host = str(getattr(page_parts, "hostname", "") or "").lower()
    candidate_host = str(getattr(candidate_parts, "hostname", "") or "").lower()
    page_path = str(getattr(page_parts, "path", "") or "").rstrip("/") or "/"
    candidate_path = str(getattr(candidate_parts, "path", "") or "").rstrip("/") or "/"
    return page_host == candidate_host, page_path == candidate_path

from . import selector_values as _split_owner
globals().update({
    name: value
    for name, value in vars(_split_owner).items()
    if not name.startswith("__") and name != "_owner"
})

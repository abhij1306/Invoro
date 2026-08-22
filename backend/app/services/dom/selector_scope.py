from __future__ import annotations

from typing import cast
from urllib.parse import urlparse

from app.services.config.extraction_rules import (
    CROSS_LINK_CONTAINER_HINTS,
    DETAIL_CROSS_PRODUCT_CONTAINER_TOKENS,
    DETAIL_LONG_TEXT_RANK_FIELDS,
    DETAIL_PRIMARY_DOM_CONTEXT_SELECTOR,
    DETAIL_TEXT_HIDDEN_STYLE_TOKENS,
    DETAIL_TEXT_SCOPE_EXCLUDE_TOKENS,
    DETAIL_TEXT_SCOPE_PRIORITY_TOKENS,
    DETAIL_TEXT_SCOPE_SELECTORS,
    MAX_SELECTOR_MATCHES,
    SCOPE_PRODUCT_CONTEXT_TOKENS,
    SCOPE_SCORE_MAIN_WEIGHT,
    SCOPE_SCORE_PRIORITY_WEIGHT,
    SCOPE_SCORE_PRODUCT_CONTEXT_WEIGHT,
)
from app.services.config.surface_hints import detail_path_hints
from app.services.dom.html_parser import BeautifulSoup, NavigableString, Tag
from app.services.dom.image_extraction import (
    is_in_product_gallery_context,
    looks_like_image_asset_url,
)
from app.services.dom.query import safe_select, walk_ancestors
from app.services.shared.coerce_primitives import safe_int
from app.services.shared.field_coerce import absolute_url, clean_text

_PAGE_FILE_EXTENSIONS = (".asp", ".aspx", ".htm", ".html", ".jsp", ".php")
_detail_text_scope_selectors = tuple(DETAIL_TEXT_SCOPE_SELECTORS or ())
_detail_text_scope_priority_tokens = tuple(
    clean_text(token).lower()
    for token in tuple(DETAIL_TEXT_SCOPE_PRIORITY_TOKENS or ())
    if clean_text(token)
)
_detail_text_scope_exclude_tokens = tuple(
    clean_text(token).lower()
    for token in tuple(DETAIL_TEXT_SCOPE_EXCLUDE_TOKENS or ())
    if clean_text(token)
)
_detail_text_hidden_style_tokens = tuple(
    clean_text(token).lower()
    for token in tuple(DETAIL_TEXT_HIDDEN_STYLE_TOKENS or ())
    if clean_text(token)
)

_cross_product_container_tokens = tuple(
    clean_text(token).lower()
    for token in tuple(DETAIL_CROSS_PRODUCT_CONTAINER_TOKENS or ())
    if clean_text(token)
)
_scope_product_context_tokens = tuple(
    clean_text(token).lower()
    for token in tuple(SCOPE_PRODUCT_CONTEXT_TOKENS or ())
    if clean_text(token)
)
_max_selector_matches = safe_int(MAX_SELECTOR_MATCHES, default=12) or 12
_scope_score_main_weight = safe_int(SCOPE_SCORE_MAIN_WEIGHT, default=4000) or 4000
_scope_score_priority_weight = (
    safe_int(SCOPE_SCORE_PRIORITY_WEIGHT, default=2000) or 2000
)
_scope_score_product_context_weight = (
    safe_int(SCOPE_SCORE_PRODUCT_CONTEXT_WEIGHT, default=1000) or 1000
)


def node_attr_text(node: Tag, *, max_depth: int = 6) -> str:
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


def field_uses_scoped_text(field_name: str) -> bool:
    return field_name in DETAIL_LONG_TEXT_RANK_FIELDS


def node_within_scope(node: Tag, scope: Tag) -> bool:
    current: Tag | None = node
    while isinstance(current, Tag):
        if current is scope or current.node.mem_id == scope.node.mem_id:
            return True
        parent = current.parent
        current = parent if isinstance(parent, Tag) else None
    return False


def _node_style_is_hidden(node: Tag) -> bool:
    style = str(node.get("style") or "").strip().lower()
    return bool(style) and any(
        token in style for token in _detail_text_hidden_style_tokens
    )


def node_is_hidden_or_auxiliary(node: Tag) -> bool:
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
        context = node_attr_text(current, max_depth=1)
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
    product_links = [
        link
        for link in links
        if any(
            marker in urlparse(link).path.lower()
            for marker in detail_path_hints("ecommerce_detail")
        )
    ]
    if len(set(product_links)) >= 2:
        return True
    context = node_attr_text(node, max_depth=1)
    return any(token in context for token in _cross_product_container_tokens)


def _candidate_text_scope_nodes(root: BeautifulSoup | Tag) -> list[Tag]:
    candidates: list[Tag] = []
    seen: set[int] = set()
    for selector in _detail_text_scope_selectors:
        for node in safe_select(root, selector):
            if id(node) in seen or node_is_hidden_or_auxiliary(node):
                continue
            seen.add(id(node))
            candidates.append(node)
    return candidates


def _scope_score(node: Tag) -> tuple[int, int]:
    context = node_attr_text(node, max_depth=2)
    text_len = len(clean_text(node.get_text(" ", strip=True)))
    score = text_len
    if (
        node.name in {"main", "article"}
        or str(node.get("role") or "").strip().lower() == "main"
    ):
        score += _scope_score_main_weight
    if any(token in context for token in _detail_text_scope_priority_tokens):
        score += _scope_score_priority_weight
    if DETAIL_PRIMARY_DOM_CONTEXT_SELECTOR and (
        node.select_one(DETAIL_PRIMARY_DOM_CONTEXT_SELECTOR) is not None
        or any(token in context for token in _scope_product_context_tokens)
    ):
        score += _scope_score_product_context_weight
    return score, text_len


def _scope_is_product_like(node: Tag) -> bool:
    context = node_attr_text(node, max_depth=2)
    if any(token in context for token in _scope_product_context_tokens):
        return True
    return bool(
        DETAIL_PRIMARY_DOM_CONTEXT_SELECTOR
        and node.select_one(DETAIL_PRIMARY_DOM_CONTEXT_SELECTOR) is not None
    )


def best_text_scope(root: BeautifulSoup | Tag) -> Tag | None:
    candidates = _candidate_text_scope_nodes(root)
    if not candidates:
        return None
    best = max(candidates, key=_scope_score)
    return best if _scope_is_product_like(best) else None


def clone_visible_only(
    node: Tag | NavigableString,
    *,
    remaining_depth: int = 50,
    _soup: BeautifulSoup | None = None,
) -> Tag | NavigableString | None:
    if remaining_depth <= 0:
        return None
    if not isinstance(node, Tag):
        return NavigableString(str(node)) if isinstance(node, NavigableString) else None
    if node_is_hidden_or_auxiliary(node):
        return None
    _soup = _soup or BeautifulSoup("", "html.parser")
    clone = _soup.new_tag(node.name, attrs=dict(getattr(node, "attrs", {}) or {}))
    for child in node.children:
        if (
            child_clone := clone_visible_only(
                cast(Tag | NavigableString, child),
                remaining_depth=remaining_depth - 1,
                _soup=_soup,
            )
        ) is not None:
            clone.append(child_clone)
    return clone


def pruned_text_scope_root(root: BeautifulSoup | Tag) -> BeautifulSoup | Tag:
    scope = best_text_scope(root)
    if scope is None:
        return root
    cloned_scope = clone_visible_only(scope)
    return cloned_scope if isinstance(cloned_scope, Tag) else root


def is_other_detail_link(
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
    candidate_parts = urlparse(absolute_url(page_url, candidate))
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
    return candidate.lower().startswith(
        ("#", "javascript:", "mailto:")
    ) or looks_like_image_asset_url(candidate)


def _detail_link_is_gallery_media(
    is_detail_surface: bool, link_node: Tag | None
) -> bool:
    return bool(
        is_detail_surface
        and link_node is not None
        and is_in_product_gallery_context(link_node)
    )


def _url_host_path_matches(
    page_parts: object, candidate_parts: object
) -> tuple[bool, bool]:
    page_host = str(getattr(page_parts, "hostname", "") or "").lower()
    candidate_host = str(getattr(candidate_parts, "hostname", "") or "").lower()
    page_path = str(getattr(page_parts, "path", "") or "").rstrip("/") or "/"
    candidate_path = str(getattr(candidate_parts, "path", "") or "").rstrip("/") or "/"
    return page_host == candidate_host, page_path == candidate_path


def _different_detail_link_signal(
    raw_path: str,
    surface: str | None,
    is_detail_surface: bool,
    same_host: bool,
    same_path: bool,
    link_node: Tag | None,
) -> bool:
    path = raw_path.lower()
    if any(path.endswith(ext) for ext in _PAGE_FILE_EXTENSIONS):
        return True
    if any(marker in path for marker in detail_path_hints(surface)):
        return True
    if is_detail_surface and same_host and not same_path:
        return True
    return link_node is not None and is_in_cross_link_container(link_node)


def is_in_cross_link_container(node: Tag, *, max_depth: int = 6) -> bool:
    return (
        walk_ancestors(
            node,
            lambda current, _depth: any(
                hint in node_attr_text(current) for hint in CROSS_LINK_CONTAINER_HINTS
            ),
            max_depth=max_depth,
        )
        is not None
    )

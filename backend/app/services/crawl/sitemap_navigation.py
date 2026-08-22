from collections.abc import Mapping
from urllib.parse import urlsplit, urlunsplit

from app.services.dom.html_parser import Tag
from app.services.config.sitemap import (
    SITEMAP_CATEGORY_ANCHOR_TEXT_EXCLUDED_TOKENS,
    SITEMAP_CATEGORY_ANCHOR_TEXT_TOKENS,
    SITEMAP_CATEGORY_EXCLUDED_PATH_TOKENS,
    SITEMAP_CATEGORY_PATH_TOKENS,
    SITEMAP_HOMEPAGE_CATEGORY_PATH_SCORE_BOOST,
    SITEMAP_HOMEPAGE_FALLBACK_EXCLUDED_EXTENSIONS,
    SITEMAP_HOMEPAGE_FALLBACK_EXCLUDED_PATH_TOKENS,
    SITEMAP_HOMEPAGE_FALLBACK_MAX_LINK_TEXT_WORDS,
)
from app.services.crawl.utils import text_has_token
from app.services.surface_resolver import resolve_auto_surface


def build_nav_tree(
    urls: list[str], *, labels_by_url: Mapping[str, str | None] | None = None
) -> list[dict[str, object]]:
    labels = {
        url_key(url): label for url, label in (labels_by_url or {}).items() if label
    }
    url_by_key = {url_key(url): url for url in urls}
    roots: list[dict[str, object]] = []
    child_maps: dict[int, dict[str, dict[str, object]]] = {}
    for raw_url in urls:
        parsed = urlsplit(raw_url)
        segments = [segment for segment in parsed.path.split("/") if segment]
        if not segments:
            continue
        _append_nav_path(
            parsed=parsed,
            segments=segments,
            roots=roots,
            child_maps=child_maps,
            labels=labels,
            url_by_key=url_by_key,
        )
    return roots


def _append_nav_path(
    *, parsed, segments, roots, child_maps, labels, url_by_key
) -> None:
    parent_children = roots
    current_path: list[str] = []
    for segment in segments:
        current_path.append(segment)
        prefix_url = urlunsplit(
            (parsed.scheme, parsed.netloc, "/" + "/".join(current_path), "", "")
        )
        prefix_key = url_key(prefix_url)
        siblings = child_maps.setdefault(id(parent_children), {})
        node = siblings.get(segment.lower())
        if node is None:
            node = {
                "label": labels.get(prefix_key) or label_from_path_segment(segment),
                "children": [],
            }
            siblings[segment.lower()] = node
            parent_children.append(node)
        if prefix_key in url_by_key:
            node["url"] = url_by_key[prefix_key]
            if prefix_key in labels:
                node["label"] = labels[prefix_key]
        parent_children = _node_children(node)


def _node_children(node: dict[str, object]) -> list[dict[str, object]]:
    children = node.setdefault("children", [])
    if not isinstance(children, list):
        children = []
        node["children"] = children
    return children


def labels_by_url_from_tree(tree: list[dict[str, object]]) -> dict[str, str]:
    labels: dict[str, str] = {}
    stack = list(tree)
    while stack:
        node = stack.pop()
        url = node.get("url")
        label = node.get("label")
        if isinstance(url, str) and isinstance(label, str):
            labels[url_key(url)] = label
        children = node.get("children")
        if isinstance(children, list):
            stack.extend(child for child in children if isinstance(child, dict))
    return labels


def classify_homepage_candidate(
    *, candidate_url: str, keyword: str, anchor: Tag
) -> tuple[str, int]:
    resolution = resolve_auto_surface(url=candidate_url)
    path = urlsplit(candidate_url).path.lower().rstrip("/")
    depth = path_depth(path)
    anchor_words = len(
        [word for word in " ".join(anchor.stripped_strings).split() if word]
    )
    keyword_hit = _keyword_hit(keyword, candidate_url=candidate_url, anchor=anchor)
    boosts = _candidate_boosts(path, keyword_hit=keyword_hit, anchor=anchor)
    if resolution.surface.endswith("_listing"):
        return "listing", 300 + int(resolution.confidence * 100) + boosts
    if resolution.surface == "content_detail" and resolution.confidence <= 0.4:
        if looks_like_listing_link(path, depth=depth, anchor_words=anchor_words):
            return "listing", 180 + boosts
    if resolution.surface.endswith("_detail"):
        return "detail", 220 + int(resolution.confidence * 100) + (
            25 if keyword_hit else 0
        )
    slug = path.rsplit("/", 1)[-1]
    if looks_like_detail_link(slug, depth=depth, anchor_words=anchor_words):
        return "detail", 120 + (25 if keyword_hit else 0)
    return "", 0


def _keyword_hit(keyword: str, *, candidate_url: str, anchor: Tag) -> bool:
    anchor_text = " ".join(anchor.stripped_strings).strip().lower()
    return bool(keyword) and (
        keyword in candidate_url.lower() or keyword in anchor_text
    )


def _candidate_boosts(path: str, *, keyword_hit: bool, anchor: Tag) -> int:
    nav_boost = 12 if anchor.find_parent(("nav", "header")) is not None else 0
    return nav_boost + category_path_score_boost(path) + (25 if keyword_hit else 0)


def category_path_score_boost(path: str) -> int:
    return (
        SITEMAP_HOMEPAGE_CATEGORY_PATH_SCORE_BOOST
        if any(token in path for token in SITEMAP_CATEGORY_PATH_TOKENS)
        else 0
    )


def looks_like_listing_link(path: str, *, depth: int, anchor_words: int) -> bool:
    if depth == 0 or depth > 2:
        return False
    if (
        anchor_words == 0
        or anchor_words > SITEMAP_HOMEPAGE_FALLBACK_MAX_LINK_TEXT_WORDS
    ):
        return False
    terminal = path.rsplit("/", 1)[-1]
    return not terminal.isdigit() and not looks_like_locale_segment(terminal)


def looks_like_detail_link(slug: str, *, depth: int, anchor_words: int) -> bool:
    if depth < 2 or anchor_words == 0 or anchor_words > 12:
        return False
    return (
        any(char.isdigit() for char in slug)
        or slug.count("-") >= 2
        or slug.count("_") >= 2
    )


def looks_like_category_url(url: str) -> bool:
    path = urlsplit(url).path.lower()
    if any(token in path for token in SITEMAP_CATEGORY_EXCLUDED_PATH_TOKENS):
        return False
    if any(token in path for token in SITEMAP_CATEGORY_PATH_TOKENS):
        return True
    segments = [segment for segment in path.split("/") if segment]
    if not _category_segments_are_plausible(segments):
        return False
    segment_text = " ".join(segment.replace("-", " ") for segment in segments)
    if any(
        token in segment_text for token in SITEMAP_CATEGORY_ANCHOR_TEXT_EXCLUDED_TOKENS
    ):
        return False
    category_segments = {
        token
        for token in SITEMAP_CATEGORY_ANCHOR_TEXT_TOKENS
        if token and " " not in token
    }
    return any(segment.replace("-", " ") in category_segments for segment in segments)


def _category_segments_are_plausible(segments: list[str]) -> bool:
    return (
        1 <= len(segments) <= 3
        and all(len(segment) >= 2 for segment in segments)
        and not any(
            looks_like_locale_segment(segment) or segment.isdigit()
            for segment in segments
        )
    )


def has_category_homepage_signal(url: str, anchor: Tag) -> bool:
    if looks_like_category_url(url):
        return True
    path = urlsplit(url).path.lower().strip("/")
    text = " ".join(anchor.stripped_strings).strip().lower()
    if not path or looks_like_locale_path(path) or not text:
        return False
    if any(
        text_has_token(text, token)
        for token in SITEMAP_CATEGORY_ANCHOR_TEXT_EXCLUDED_TOKENS
    ):
        return False
    return any(
        text_has_token(text, token) for token in SITEMAP_CATEGORY_ANCHOR_TEXT_TOKENS
    )


def looks_like_locale_path(path: str) -> bool:
    parts = [part for part in path.split("/") if part]
    return (
        bool(parts)
        and len(parts) <= 2
        and all(looks_like_locale_segment(part.replace("_", "-")) for part in parts)
    )


def reject_homepage_candidate(candidate_url: str) -> bool:
    parsed = urlsplit(candidate_url)
    path = parsed.path.lower()
    if parsed.scheme not in {"http", "https"} or not path or path == "/":
        return True
    if any(path.endswith(ext) for ext in SITEMAP_HOMEPAGE_FALLBACK_EXCLUDED_EXTENSIONS):
        return True
    return any(
        token in path for token in SITEMAP_HOMEPAGE_FALLBACK_EXCLUDED_PATH_TOKENS
    )


def path_depth(path: str) -> int:
    return len(
        [
            part
            for part in path.split("/")
            if part and not looks_like_locale_segment(part)
        ]
    )


def looks_like_locale_segment(value: str) -> bool:
    cleaned = str(value or "").strip().lower()
    if len(cleaned) == 2 and cleaned.isalpha():
        return True
    return (
        len(cleaned) == 5
        and cleaned[2] == "-"
        and cleaned[:2].isalpha()
        and cleaned[3:].isalpha()
    )


def strip_fragment(value: str) -> str:
    parsed = urlsplit(value)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, parsed.query, ""))


def origin_key(value: str) -> tuple[str, str, int]:
    parsed = urlsplit(value)
    scheme = str(parsed.scheme or "").lower()
    return (
        scheme,
        str(parsed.hostname or "").lower(),
        parsed.port or (443 if scheme == "https" else 80),
    )


def url_key(url: str) -> str:
    return strip_fragment(url).rstrip("/").lower()


def label_from_path_segment(segment: str) -> str:
    cleaned = segment.replace("-", " ").replace("_", " ").strip()
    return (
        " ".join(word.capitalize() for word in cleaned.split()) if cleaned else segment
    )

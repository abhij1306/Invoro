import re
from collections.abc import Iterable, Mapping
from typing import Any, cast

from app.services.acquisition.browser_readiness import HtmlAnalysis, analyze_html
from app.services.config.block_signatures import BLOCK_SIGNATURES
from app.services.config.extraction_rules import (
    ACTION_BUY_NOW,
    BROWSER_DETAIL_READINESS_HINTS,
    CONTENT_DETAIL_MIN_BODY_TEXT_LENGTH,
    CONTENT_SURFACE_FORUM_BODY_SELECTORS,
    CONTENT_SURFACE_PROTECTED_DESCENDANT_SELECTORS,
    DETAIL_SHELL_FRAMEWORK_TOKENS,
    DETAIL_SHELL_PRODUCT_DATA_TOKENS,
    DETAIL_SHELL_STATE_TOKENS,
    JS_REQUIRED_PLACEHOLDER_PHRASES,
    LISTING_CLIENT_RENDERED_SHELL_HINTS,
    LISTING_DETAIL_URL_MARKERS,
    LISTING_SHELL_FRAMEWORK_TOKENS,
)
from app.services.config.runtime_settings import crawler_runtime_settings
from app.services.db_utils import mapping_or_empty
from app.services.dom.html_parser import BeautifulSoup
from app.services.shared.field_coerce import clean_text
from app.services.structured_sources import harvest_js_state_objects, parse_json_ld

_ECOMMERCE_DETAIL_READINESS_HINTS = tuple(
    str(item).strip().lower()
    for item in (
        (
            BROWSER_DETAIL_READINESS_HINTS.get("ecommerce")
            if isinstance(BROWSER_DETAIL_READINESS_HINTS, Mapping)
            else []
        )
        or []
    )
    if str(item).strip()
)


def looks_like_js_shell(html: str, *, analysis: HtmlAnalysis | None = None) -> bool:
    parsed = analysis or analyze_html(html)
    if looks_like_js_required_placeholder(parsed):
        return True
    if len(parsed.visible_text) > 120:
        return False
    root = parsed.soup.find(id=re.compile(r"root|app|__next", re.I))
    return root is not None and len(parsed.soup.find_all("script")) >= 3


def has_extractable_detail_signals(
    html: str, *, analysis: HtmlAnalysis | None = None
) -> bool:
    parsed = analysis or analyze_html(html)
    if not parsed.html or looks_like_js_required_placeholder(parsed):
        return False
    checks = (
        _structured_detail_present(parsed),
        _js_state_detail_present(parsed),
        has_extractable_dom_detail_signals(parsed),
        has_extractable_dom_content_detail_signals_from_analysis(parsed),
        any(token in parsed.lowered_html for token in DETAIL_SHELL_STATE_TOKENS),
        _framework_product_data_present(parsed.lowered_html),
    )
    return any(checks)


def _structured_detail_present(parsed: HtmlAnalysis) -> bool:
    for payload in parse_json_ld(parsed.soup):
        if not isinstance(payload, dict):
            continue
        raw_type = payload.get("@type")
        normalized_type = (
            " ".join(raw_type) if isinstance(raw_type, list) else str(raw_type or "")
        ).lower()
        if any(
            token in normalized_type
            for token in (
                "product",
                "productgroup",
                "jobposting",
                "article",
                "newsarticle",
                "blogposting",
                "discussionforumposting",
            )
        ):
            return True
    return False


def _js_state_detail_present(parsed: HtmlAnalysis) -> bool:
    states = harvest_js_state_objects(parsed.soup, parsed.html)
    return any(state_payload_has_content(payload) for payload in states.values())


def _framework_product_data_present(lowered_html: str) -> bool:
    return any(
        token in lowered_html for token in DETAIL_SHELL_FRAMEWORK_TOKENS
    ) and any(token in lowered_html for token in DETAIL_SHELL_PRODUCT_DATA_TOKENS)


def has_extractable_dom_detail_signals(analysis: HtmlAnalysis) -> bool:
    if not analysis.h1_present:
        return False
    lowered_text = analysis.normalized_text.lower()
    detail_hint_hits = sum(
        1 for hint in _ECOMMERCE_DETAIL_READINESS_HINTS if hint in lowered_text
    )
    if ACTION_BUY_NOW.strip().lower() in lowered_text:
        detail_hint_hits += 1
    has_product_anchor = bool(
        analysis.soup.find(
            attrs=cast(
                Any,
                {
                    "content": re.compile(r"\bproduct\b", re.I),
                    "property": re.compile(r"og:type", re.I),
                },
            )
        )
    )
    has_price_anchor = _has_price_anchor(analysis)
    if _app_load_shell(lowered_text) and not (has_product_anchor or has_price_anchor):
        return False
    threshold = int(crawler_runtime_settings.detail_field_signal_min_count)
    if detail_hint_hits >= threshold:
        main_heading = analysis.soup.select_one("main h1, article h1, [role='main'] h1")
        return bool(main_heading or has_product_anchor or has_price_anchor)
    return detail_hint_hits > 0 and has_product_anchor


def _has_price_anchor(analysis: HtmlAnalysis) -> bool:
    price_pattern = re.compile(
        r"(?:[$€£₹]\s*)?\d{1,3}(?:,\d{3})*(?:[.,]\d{1,2})?|(?:[$€£₹]\s*)?\d+(?:[.,]\d{1,2})?",
        re.I,
    )
    return bool(
        analysis.soup.find(
            attrs=cast(
                Any,
                {
                    "content": price_pattern,
                    "property": re.compile(r"(?:product:)?price", re.I),
                },
            )
        )
        or analysis.soup.find(attrs=cast(Any, {"itemprop": re.compile(r"price", re.I)}))
        or re.search(r"(?:[$€£₹]\s*)\d+(?:[.,]\d{2})?", analysis.normalized_text)
    )


def _app_load_shell(text: str) -> bool:
    return "load in the app" in text or "loads in the app" in text


def has_extractable_dom_content_detail_signals_from_analysis(
    analysis: HtmlAnalysis,
) -> bool:
    if not analysis.h1_present:
        return False
    heading = analysis.soup.select_one("main h1, article h1, [role='main'] h1, h1")
    heading_text = clean_text(heading.get_text(" ", strip=True)) if heading else ""
    if not heading_text:
        return False
    for selector in (
        *CONTENT_SURFACE_FORUM_BODY_SELECTORS,
        *CONTENT_SURFACE_PROTECTED_DESCENDANT_SELECTORS,
    ):
        try:
            nodes: Iterable[Any] = analysis.soup.select(selector)
        except Exception:
            nodes = []
        if any(_content_node_is_extractable(node, heading_text) for node in nodes):
            return True
    return False


def _content_node_is_extractable(node: Any, heading_text: str) -> bool:
    body_text = clean_text(node.get_text(" ", strip=True))
    if not body_text or body_text == heading_text:
        return False
    body_without_heading = clean_text(
        re.sub(re.escape(heading_text), " ", body_text, flags=re.I)
    )
    if not body_without_heading or _app_load_shell(body_without_heading.lower()):
        return False
    return bool(
        node.find(("p", "div", "li", "article", "section", "span")) is not None
        or len(body_without_heading) >= CONTENT_DETAIL_MIN_BODY_TEXT_LENGTH
    )


def has_extractable_listing_signals(
    html: str, *, analysis: HtmlAnalysis | None = None
) -> bool:
    parsed = analysis or analyze_html(html)
    if not parsed.html or looks_like_js_required_placeholder(parsed):
        return False
    structured_result = _structured_listing_signal(parsed)
    if structured_result is not None:
        return structured_result
    return _detail_like_anchor_count(parsed) >= 3


def _structured_listing_signal(parsed: HtmlAnalysis) -> bool | None:
    typed_listing_count = 0
    for payload in parse_json_ld(parsed.soup):
        if not isinstance(payload, dict):
            continue
        raw_type = payload.get("@type")
        normalized_type = (
            " ".join(raw_type) if isinstance(raw_type, list) else str(raw_type or "")
        ).lower()
        if "itemlist" in normalized_type or "listitem" in normalized_type:
            return True
        if "product" in normalized_type or "jobposting" in normalized_type:
            typed_listing_count += 1
    threshold = max(2, int(crawler_runtime_settings.listing_min_items))
    return True if typed_listing_count >= threshold else None


def _detail_like_anchor_count(parsed: HtmlAnalysis) -> int:
    count = 0
    for anchor in parsed.soup.find_all("a", href=True):
        href = str(anchor.get("href") or "").strip().lower()
        if any(marker in href for marker in LISTING_DETAIL_URL_MARKERS):
            count += 1
            if count >= 3:
                break
    return count


def looks_like_listing_shell(
    result: Any, *, analysis: HtmlAnalysis | None = None
) -> bool:
    parsed = analysis or analyze_html(result.html)
    if looks_like_js_required_placeholder(parsed):
        return True
    lowered_surface = str(result.final_url or result.url or "").strip().lower()
    if "#/" in lowered_surface or int(result.status_code or 0) == 202:
        return True
    if len(parsed.visible_text) > 400:
        return any(
            token in parsed.lowered_html
            for token in LISTING_CLIENT_RENDERED_SHELL_HINTS
        )
    root = parsed.soup.find(id=re.compile(r"root|app|__next", re.I))
    if root is None and len(parsed.soup.find_all("script")) < 3:
        return False
    return any(token in parsed.lowered_html for token in LISTING_SHELL_FRAMEWORK_TOKENS)


def looks_like_js_required_placeholder(parsed: HtmlAnalysis) -> bool:
    combined_text = clean_text(f"{parsed.title_text} {parsed.visible_text}").lower()
    if not combined_text:
        return False
    if not any(phrase in combined_text for phrase in JS_REQUIRED_PLACEHOLDER_PHRASES):
        return False
    return bool(parsed.soup.find("noscript")) or len(parsed.visible_text) <= 400


def state_payload_has_content(payload: Any) -> bool:
    if isinstance(payload, dict):
        if not payload:
            return False
        meaningful_keys = {
            key
            for key, value in payload.items()
            if value not in (None, "", [], {})
            and str(key or "").strip().lower() not in {"config", "env", "locale"}
        }
        return bool(meaningful_keys) or any(
            state_payload_has_content(value) for value in payload.values()
        )
    if isinstance(payload, list):
        return any(state_payload_has_content(item) for item in payload[:10])
    return payload not in (None, "")


def challenge_element_hits(
    soup: BeautifulSoup,
    lowered_html: str,
    *,
    block_signatures: Mapping[str, object] = BLOCK_SIGNATURES,
) -> list[str]:
    challenge_elements = mapping_or_empty(block_signatures.get("challenge_elements"))
    hits = _tag_marker_hits(
        soup.find_all("iframe"),
        attribute="src",
        markers=_marker_map(challenge_elements, "iframe_src_markers"),
    )
    hits.extend(
        _tag_marker_hits(
            soup.find_all("iframe"),
            attribute="title",
            markers=_marker_map(challenge_elements, "iframe_title_markers"),
        )
    )
    hits.extend(
        _tag_marker_hits(
            soup.find_all("script"),
            attribute="src",
            markers=_marker_map(challenge_elements, "script_src_markers"),
        )
    )
    hits.extend(
        hit
        for marker, hit in _marker_map(challenge_elements, "html_markers").items()
        if marker in lowered_html
    )
    return hits


def _tag_marker_hits(
    tags: Iterable[Any], *, attribute: str, markers: dict[str, str]
) -> list[str]:
    hits: list[str] = []
    for tag in tags:
        value = str(tag.get(attribute) or "").strip().lower()
        hits.extend(hit for marker, hit in markers.items() if marker in value)
    return hits


def _marker_map(source: Mapping[str, object], key: str) -> dict[str, str]:
    return {
        str(marker or "").strip().lower(): str(hit or "").strip()
        for marker, hit in mapping_or_empty(source.get(key)).items()
        if str(marker or "").strip() and str(hit or "").strip()
    }


def has_extractable_dom_content_detail_signals(
    value: HtmlAnalysis | str | object, *, analysis: HtmlAnalysis | None = None
) -> bool:
    if analysis is not None:
        parsed = analysis
    elif isinstance(value, HtmlAnalysis):
        parsed = value
    else:
        parsed = analyze_html(str(value or ""))
    return has_extractable_dom_content_detail_signals_from_analysis(parsed)

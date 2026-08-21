from __future__ import annotations
import re
import logging
from typing import Any
from app.services.dom.html_parser import BeautifulSoup

from app.services.config.extraction_rules import (
    EXTRACTION_RULES,
)
from app.services.extract.article_card_parser import (
    article_card_date,
    article_card_summary,
    article_card_text,
)
from app.services.extract.listing_candidate_ranking import (
    listing_record_supported,
    looks_like_utility_record,
)
from app.services.extract.listing_signals import (
    card_title_node,
    card_title_score,
    extract_brand_signal_from_card,
    extract_image_title_hint,
    extract_label_value_pairs_from_node,
    extract_page_images_from_node,
    extract_price_signal_from_card,
    normalize_listing_title,
    same_url_anchor_text_candidates,
    select_primary_anchor,
    select_primary_card_url,
    should_replace_title_with_image_hint,
    title_token_overlap,
    title_from_url,
)
from app.services.extract.detail.identity.core import (
    listing_detail_like_path,
    listing_url_is_structural,
)
from app.services.extract.listing_card_fragments import (
    listing_fragment_structural_signature,
    listing_node_attr,
    listing_node_text,
)
from app.services.field_policy import normalize_requested_field
from app.services.shared.currency_hints import currency_hint_from_page_url
from app.services.shared.field_coerce import (
    PRICE_RE,
    RATING_RE,
    REVIEW_COUNT_RE,
    clean_text,
    coerce_field_value,
    extract_currency_code,
    finalize_record,
    is_title_noise,
    surface_alias_lookup,
    surface_fields,
)
from app.services.extract.field_candidates import (
    add_candidate,
    finalize_candidate_value,
)
from app.services.dom.selector_engine import apply_selector_fallbacks

logger = logging.getLogger(__name__)
_alnum_word_pattern = re.compile(r"[a-z0-9]+", re.I)

def _alnum_token_count(text: str) -> int:
    return len(_alnum_word_pattern.findall(text))

def _resolve_selector_trace(
    field_name: str,
    finalized_value: object,
    selector_trace_candidates: dict[str, list[dict[str, object]]],
) -> dict[str, object] | None:
    traces = list(selector_trace_candidates.get(field_name) or [])
    for trace in traces:
        if not isinstance(trace, dict):
            continue
        if trace.get("_candidate_value") == finalized_value:
            return {key: value for key, value in trace.items() if not str(key).startswith("_")}
    trace = next((row for row in traces if isinstance(row, dict)), {})
    if not isinstance(trace, dict):
        return None
    return {key: value for key, value in trace.items() if not str(key).startswith("_")}

def _is_title_only_candidate_allowed(
    *,
    is_job: bool,
    anchor_score: int,
    title_score: int,
    cleaned_title: str,
    cleaned_url: str,
    page_url: str,
) -> bool:
    return (
        not is_job
        and anchor_score >= 10
        and title_score >= 10
        and _alnum_token_count(cleaned_title) >= 3
        and not listing_url_is_structural(cleaned_url, page_url)
        and not looks_like_utility_record(
            title=cleaned_title,
            url=cleaned_url,
        )
        and not re.match(r"^(?:article|flyer|guide|manual|resource)\s*:", cleaned_title, flags=re.I)
        and not re.search(r"\.(?:pdf|docx?|pptx?)(?:$|[?#])", cleaned_url, flags=re.I)
        and not any(
            token in cleaned_url.lower()
            for token in (
                "/article/",
                "/articles/",
                "/assets/",
                "/deepweb/",
                "/technical-documents/",
                "/technical-article/",
            )
        )
        and title_token_overlap(cleaned_title, title_from_url(cleaned_url) or "") >= 2
    )

def _surface_has_dom_fallback_patterns(surface: str) -> bool:
    dom_patterns_raw = EXTRACTION_RULES.get("dom_patterns")
    dom_patterns = dict(dom_patterns_raw) if isinstance(dom_patterns_raw, dict) else {}
    return any(str(dom_patterns.get(field_name) or "").strip() for field_name in surface_fields(surface, None))

def _build_card_candidates(
    card,
    *,
    page_url: str,
    surface: str,
    is_job: bool,
    title: str,
    url: str,
    selector_rules: list[dict[str, object]] | None,
    image_urls: list[str],
    best_same_url_text: str | None,
    same_url_texts: list[str],
    card_text: str,
    record_dom_observed_selectors: bool,
) -> tuple[dict[str, list[object]], dict[str, list[dict[str, object]]]]:
    alias_lookup = surface_alias_lookup(surface, None)
    candidates: dict[str, list[object]] = {"title": [title], "url": [url]}
    selector_trace_candidates: dict[str, list[dict[str, object]]] = {}
    card_soup: BeautifulSoup | None = None
    needs_card_soup = bool(selector_rules) or surface in {"article_listing", "content_listing"} or _surface_has_dom_fallback_patterns(surface)
    if needs_card_soup:
        card_soup = BeautifulSoup(str(getattr(card, "html", "") or ""), "html.parser")
    if card_soup is not None:
        apply_selector_fallbacks(
            card_soup,
            page_url,
            surface,
            None,
            candidates,
            selector_rules=selector_rules,
            selector_trace_candidates=selector_trace_candidates,
            record_dom_observed_selectors=record_dom_observed_selectors,
        )
    _add_card_content_fields(candidates, surface, card_soup, title)
    _add_card_identity_fields(candidates, card, title, is_job, image_urls)
    _add_card_description(candidates, title, best_same_url_text, same_url_texts)
    _add_card_label_values(candidates, card, alias_lookup, page_url)
    _add_card_commerce_fields(candidates, card, page_url, is_job)
    _add_card_text_metrics(candidates, card_text, is_job)
    return candidates, selector_trace_candidates

def _add_card_content_fields(
    candidates: dict[str, list[object]],
    surface: str,
    card_soup: BeautifulSoup | None,
    title: str,
) -> None:
    if surface == "article_listing" and card_soup is not None:
        author = article_card_text(card_soup, [".author", ".byline", "[rel='author']", "[itemprop='author']"])
        if author:
            add_candidate(candidates, "author", author)
        publication_date = article_card_date(card_soup)
        if publication_date:
            add_candidate(candidates, "publication_date", publication_date)
        summary = article_card_summary(card_soup, title)
        if summary:
            add_candidate(candidates, "summary", summary)
    elif surface == "content_listing" and card_soup is not None:
        summary = article_card_summary(card_soup, title)
        if summary:
            add_candidate(candidates, "summary", summary)

def _add_card_identity_fields(
    candidates: dict[str, list[object]],
    card,
    title: str,
    is_job: bool,
    image_urls: list[str],
) -> None:
    if not is_job and not candidates.get("brand"):
        brand_text = extract_brand_signal_from_card(card, title)
        if brand_text:
            add_candidate(candidates, "brand", brand_text)
    if image_urls and not candidates.get("image_url"):
        add_candidate(candidates, "image_url", image_urls[0])

def _add_card_description(
    candidates: dict[str, list[object]],
    title: str,
    best_same_url_text: str | None,
    same_url_texts: list[str],
) -> None:
    if best_same_url_text and not candidates.get("description"):
        description_text = next(
            (
                text
                for text in same_url_texts
                if text != title
                and len(text) >= 20
                and _alnum_token_count(text) >= 3
                and not PRICE_RE.search(text)
                and not is_title_noise(text)
                and (title_token_overlap(text, title) >= 2 or _alnum_token_count(text) >= 5)
            ),
            None,
        )
        if description_text:
            add_candidate(candidates, "description", description_text)

def _add_card_label_values(
    candidates: dict[str, list[object]],
    card,
    alias_lookup: dict[str, str],
    page_url: str,
) -> None:
    for label, value in extract_label_value_pairs_from_node(card):
        normalized_label = normalize_requested_field(label)
        if not normalized_label:
            normalized_label = clean_text(label).lower().replace(" ", "_")
        canonical = alias_lookup.get(normalized_label)
        if canonical:
            add_candidate(
                candidates,
                canonical,
                coerce_field_value(canonical, value, page_url),
            )

def _add_card_commerce_fields(candidates: dict[str, list[object]], card, page_url: str, is_job: bool) -> None:
    if not is_job and not candidates.get("price"):
        price_text = extract_price_signal_from_card(card)
        if price_text:
            add_candidate(candidates, "price", price_text)
    if not is_job and not candidates.get("currency"):
        for price_value in candidates.get("price") or []:
            currency_code = extract_currency_code(price_value)
            if currency_code:
                add_candidate(candidates, "currency", currency_code)
                break
        else:
            inferred_currency = currency_hint_from_page_url(page_url)
            if inferred_currency and candidates.get("price"):
                add_candidate(candidates, "currency", inferred_currency)

def _add_card_text_metrics(candidates: dict[str, list[object]], card_text: str, is_job: bool) -> None:
    if is_job and not candidates.get("salary"):
        salary_match = PRICE_RE.search(card_text)
        if salary_match:
            add_candidate(candidates, "salary", salary_match.group(0))
    if not candidates.get("rating"):
        rating_match = RATING_RE.search(card_text)
        if rating_match:
            add_candidate(candidates, "rating", rating_match.group(1))
    if not candidates.get("review_count"):
        review_match = REVIEW_COUNT_RE.search(card_text)
        if review_match:
            add_candidate(candidates, "review_count", review_match.group(1))

def listing_record_from_card(
    card,
    page_url: str,
    surface: str,
    *,
    selector_rules: list[dict[str, object]] | None = None,
    record_dom_observed_selectors: bool = False,
) -> dict[str, Any] | None:
    is_job = surface.startswith("job_")
    title_node = card_title_node(card)
    primary_anchor = _resolve_card_anchor(card, page_url, surface, title_node)
    if primary_anchor is None:
        return None
    anchor_node, url, anchor_text, anchor_score = primary_anchor
    title_node = title_node or anchor_node
    title_score = card_title_score(title_node)
    same_url_texts = same_url_anchor_text_candidates(card, url)
    title, best_same_url_text = _resolve_card_title(card, title_node, anchor_text, same_url_texts, page_url)
    if len(title) < 4 or is_title_noise(title):
        return None
    if anchor_score < 4 and title_score < 8:
        return None
    card_text = listing_node_text(card)
    image_urls = extract_page_images_from_node(card, page_url)
    if not _card_path_is_supported(
        url=url,
        is_job=is_job,
        anchor_score=anchor_score,
        title_score=title_score,
        card_text=card_text,
        image_urls=image_urls,
    ):
        return None
    candidates, selector_trace_candidates = _build_card_candidates(
        card,
        page_url=page_url,
        surface=surface,
        is_job=is_job,
        title=title,
        url=url,
        selector_rules=selector_rules,
        image_urls=image_urls,
        best_same_url_text=best_same_url_text,
        same_url_texts=same_url_texts,
        card_text=card_text,
        record_dom_observed_selectors=record_dom_observed_selectors,
    )
    cleaned = _materialize_card_record(
        candidates,
        selector_trace_candidates,
        surface=surface,
        page_url=page_url,
    )
    if cleaned is None:
        return None
    cleaned_title = clean_text(cleaned.get("title"))
    cleaned_url = str(cleaned.get("url") or "").strip()
    allow_title_only_dom_candidate = _is_title_only_candidate_allowed(
        is_job=is_job,
        anchor_score=anchor_score,
        title_score=title_score,
        cleaned_title=cleaned_title,
        cleaned_url=cleaned_url,
        page_url=page_url,
    )
    supported = listing_record_supported(
        cleaned,
        page_url=page_url,
        surface=surface,
        title_is_noise=is_title_noise,
        url_is_structural=listing_url_is_structural,
        detail_like_url=lambda value: listing_detail_like_path(value, is_job=is_job),
    )
    if not supported and not allow_title_only_dom_candidate:
        return None
    cleaned["_structural_signature"] = listing_fragment_structural_signature(card, url=cleaned_url)
    return cleaned

def _resolve_card_anchor(card, page_url: str, surface: str, title_node):
    primary = select_primary_anchor(card, page_url, surface=surface, title_node=title_node)
    if primary is not None:
        return primary
    fallback_url = select_primary_card_url(card, page_url)
    if not fallback_url or title_node is None:
        return None
    return (
        title_node,
        fallback_url,
        clean_text(listing_node_text(title_node)),
        max(10, card_title_score(title_node) + 4),
    )

def _resolve_card_title(card, title_node, anchor_text: str, same_url_texts: list[str], page_url: str) -> tuple[str, str | None]:
    title = clean_text(listing_node_attr(title_node, "title") or listing_node_attr(title_node, "alt") or listing_node_text(title_node) or anchor_text)
    best_same_url_text = next(
        (
            text
            for text in sorted(same_url_texts, key=len, reverse=True)
            if _alnum_token_count(text) >= 3 and not PRICE_RE.search(text) and not is_title_noise(text)
        ),
        None,
    )
    if best_same_url_text and (_alnum_token_count(title) < 3 or is_title_noise(title)):
        title = best_same_url_text
    image_hint = extract_image_title_hint(card, page_url=page_url)
    if should_replace_title_with_image_hint(title, image_hint):
        title = clean_text(image_hint)
    return normalize_listing_title(title), best_same_url_text

def _card_path_is_supported(
    *,
    url: str,
    is_job: bool,
    anchor_score: int,
    title_score: int,
    card_text: str,
    image_urls: list[str],
) -> bool:
    if listing_detail_like_path(url, is_job=is_job):
        return True
    if is_job:
        job_signal = any(token in card_text.lower() for token in ("salary", "remote", "location", "apply"))
        return anchor_score >= 8 or job_signal
    supporting = any(
        (
            PRICE_RE.search(card_text),
            RATING_RE.search(card_text),
            REVIEW_COUNT_RE.search(card_text),
            image_urls,
        )
    )
    return anchor_score >= 8 or supporting or title_score >= 8

def _materialize_card_record(
    candidates: dict[str, list[object]],
    selector_trace_candidates: dict[str, list[dict[str, object]]],
    *,
    surface: str,
    page_url: str,
) -> dict[str, Any] | None:
    record: dict[str, Any] = {"source_url": page_url, "_source": "dom_listing"}
    selected_selector_traces: dict[str, dict[str, object]] = {}
    for field_name in surface_fields(surface, None):
        finalized = finalize_candidate_value(field_name, candidates.get(field_name, []))
        if finalized not in (None, "", [], {}):
            record[field_name] = finalized
            selector_trace = _resolve_selector_trace(
                field_name,
                finalized,
                selector_trace_candidates,
            )
            if selector_trace:
                selected_selector_traces[field_name] = selector_trace
    if selected_selector_traces:
        record["_selector_traces"] = selected_selector_traces
    cleaned = finalize_record(record, surface=surface)
    if not cleaned.get("url") or not cleaned.get("title"):
        return None
    return cleaned



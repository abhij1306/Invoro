# ruff: noqa: F401, F821
from __future__ import annotations

from . import listing_extractor as _owner

globals().update({name: value for name, value in vars(_owner).items() if not name.startswith("__")})

def _detail_anchor_count(
    parser: LexborHTMLParser,
    *,
    page_url: str,
    surface: str,
    fallback_fragment_limit: int,
) -> int:
    is_job = surface.startswith("job_")
    seen_urls: set[str] = set()
    count = 0
    for card in listing_card_html_fragments(
        parser,
        is_job=is_job,
        fallback_fragment_limit=fallback_fragment_limit,
    ):
        primary_anchor = select_primary_anchor(card, page_url, surface=surface)
        if primary_anchor is None:
            continue
        url = str(primary_anchor[1] or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        if listing_detail_like_path(url, is_job=is_job):
            count += 1
    return count

def _attach_gate_decision_to_artifacts(
    artifacts: dict[str, object] | None,
    decision: IntegrityDecision | None,
) -> None:
    """Attach the integrity gate decision to the artifacts dict under key ``listing_integrity``."""
    if artifacts is None:
        return
    if decision is None or not isinstance(decision, IntegrityDecision):
        artifacts["listing_integrity"] = {
            "outcome": "unknown",
            "reason": "invalid_decision",
            "metrics": {},
        }
        return
    artifacts["listing_integrity"] = {
        "outcome": decision.outcome,
        "reason": decision.reason,
        "metrics": decision.metrics,
    }

def apply_listing_integrity_gate(
    records: list[dict[str, Any]],
    *,
    page_url: str,
    surface: str,
    artifacts: dict[str, object] | None = None,
) -> list[dict[str, Any]]:
    if not records:
        _attach_gate_decision_to_artifacts(artifacts, None)
        return []
    try:
        decision = evaluate_listing_integrity(records, page_url=page_url, surface=surface)
    except (KeyError, RuntimeError, TypeError, ValueError):
        logger.exception(
            "evaluate_listing_integrity failed for page_url=%s surface=%s records=%d",
            page_url,
            surface,
            len(records),
        )
        decision = None
    _attach_gate_decision_to_artifacts(artifacts, decision)
    if decision is not None and decision.outcome == "promo_only_cluster":
        return []
    return [_strip_listing_integrity_internals(record) for record in records]

def _strip_listing_integrity_internals(record: dict[str, Any]) -> dict[str, Any]:
    if "_structural_signature" not in record:
        return record
    cleaned = dict(record)
    cleaned.pop("_structural_signature", None)
    return cleaned

def _structured_listing_stage(
    context: Any,
    *,
    page_url: str,
    surface: str,
    max_records: int,
    listing_min_items: int,
) -> list[dict[str, Any]]:
    payloads: list[dict[str, Any]] = []
    for source_name, source_payloads in collect_structured_source_payloads(
        context,
        page_url=page_url,
        surface=surface,
    ):
        if source_name == "js_state":
            continue
        payload_list = [payload for payload in source_payloads if isinstance(payload, dict)]
        if source_name == "embedded_json" and not allow_embedded_json_listing_payloads(
            payload_list,
            listing_min_items=listing_min_items,
        ):
            continue
        payloads.extend(payload_list)
    return extract_structured_listing(
        payloads,
        page_url,
        surface,
        max_records=max_records,
        listing_min_items=listing_min_items,
    )

def _dom_listing_stage(
    parser: LexborHTMLParser,
    *,
    page_url: str,
    surface: str,
    is_job_surface: bool,
    max_records: int,
    fallback_fragment_limit: int,
    selector_rules: list[dict[str, object]] | None,
    record_dom_observed_selectors: bool,
    seed_urls: set[str] | None = None,
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    skipped_urls: set[str] = set(seed_urls or ())
    records_by_url: dict[str, dict[str, Any]] = {}
    for card in listing_card_html_fragments(
        parser,
        is_job=is_job_surface,
        fallback_fragment_limit=fallback_fragment_limit,
        limit=max_records,
    ):
        record = _listing_record_from_card(
            card,
            page_url,
            surface,
            selector_rules=selector_rules,
            record_dom_observed_selectors=record_dom_observed_selectors,
        )
        if record is None:
            continue
        url = str(record.get("url") or "")
        if not url:
            continue
        existing = records_by_url.get(url)
        if existing is not None:
            for key, value in record.items():
                if key not in existing or existing.get(key) in (None, "", [], {}):
                    existing[key] = value
            continue
        if url in skipped_urls:
            continue
        skipped_urls.add(url)
        records_by_url[url] = record
        records.append(record)
    return records

def extract_listing_records(
    html: str,
    page_url: str,
    surface: str,
    *,
    max_records: int,
    artifacts: dict[str, object] | None = None,
    selector_rules: list[dict[str, object]] | None = None,
    network_payloads: list[dict[str, object]] | None = None,
    record_dom_observed_selectors: bool = False,
    context: ExtractionContext | None = None,
) -> list[dict[str, Any]]:
    del network_payloads
    if surface == "content_listing":
        table_records = table_row_records(html, page_url, max_records=max_records)
        if table_records:
            return table_records
        # Table intent prevents falling back to unrelated DOM cards when table parsing finds no records.
        table_row_intent = has_table_row_intent(html)
    else:
        table_row_intent = False
    context = context or prepare_extraction_context(html)
    dom_parser = context.dom_parser
    is_job_surface = surface.startswith("job_")
    listing_fallback_fragment_limit = int(crawler_runtime_settings.listing_fallback_fragment_limit)
    listing_min_items = int(crawler_runtime_settings.listing_min_items)
    dom_parser = _preferred_listing_parser(
        context,
        dom_parser,
        is_job_surface,
        listing_fallback_fragment_limit,
        max_records,
        page_url,
    )

    structured_records = _structured_listing_stage(
        context,
        page_url=page_url,
        surface=surface,
        max_records=max_records,
        listing_min_items=listing_min_items,
    )
    dom_records = _dom_listing_stage(
        dom_parser,
        page_url=page_url,
        surface=surface,
        is_job_surface=is_job_surface,
        max_records=max_records,
        fallback_fragment_limit=listing_fallback_fragment_limit,
        selector_rules=selector_rules,
        record_dom_observed_selectors=record_dom_observed_selectors,
    )
    original_dom_records = _original_dom_listing_records(
        context,
        dom_parser,
        page_url,
        surface,
        is_job_surface,
        max_records,
        listing_fallback_fragment_limit,
        selector_rules,
        record_dom_observed_selectors,
    )
    rendered_dom_records, rendered_original_dom_records = _rendered_listing_records(
        artifacts,
        page_url,
        surface,
        is_job_surface,
        max_records,
        listing_fallback_fragment_limit,
        selector_rules,
        record_dom_observed_selectors,
    )
    visual_records = _supported_visual_listing_records(artifacts, page_url, surface, max_records)
    candidate_sets: list[tuple[str, list[dict[str, Any]]]] = [
        ("structured", structured_records),
        ("dom", dom_records),
        ("structured_plus_dom", [*dom_records, *structured_records]),
    ]
    if original_dom_records:
        candidate_sets.append(("original_dom", original_dom_records))
    if rendered_dom_records:
        candidate_sets.append(("rendered_dom", rendered_dom_records))
    if rendered_original_dom_records:
        candidate_sets.append(("rendered_original_dom", rendered_original_dom_records))
    if visual_records:
        candidate_sets.append(("visual", visual_records))
    best_records = best_listing_candidate_set(
        candidate_sets,
        page_url=page_url,
        surface=surface,
        max_records=max_records,
        title_is_noise=is_title_noise,
        url_is_structural=listing_url_is_structural,
        detail_like_url=lambda candidate_url: listing_detail_like_path(
            candidate_url,
            is_job=is_job_surface,
        ),
    )
    if table_row_intent and not best_records:
        # Preserve empty table-listing results instead of substituting non-table card records.
        return []
    return apply_listing_integrity_gate(
        best_records,
        page_url=page_url,
        surface=surface,
        artifacts=artifacts,
    )

def _preferred_listing_parser(
    context: ExtractionContext,
    parser: LexborHTMLParser,
    is_job: bool,
    fragment_limit: int,
    max_records: int,
    page_url: str,
) -> LexborHTMLParser:
    if listing_card_html_fragments(parser, is_job=is_job, fallback_fragment_limit=fragment_limit, limit=max_records):
        return parser
    original = context.original_dom_parser
    if listing_card_html_fragments(
        original,
        is_job=is_job,
        fallback_fragment_limit=fragment_limit,
        limit=max_records,
    ):
        logger.debug(
            "Using original listing DOM after cleaned DOM lost card fragments for %s",
            page_url,
        )
        return original
    return parser

def _original_dom_listing_records(
    context: ExtractionContext,
    parser: LexborHTMLParser,
    page_url: str,
    surface: str,
    is_job: bool,
    max_records: int,
    fragment_limit: int,
    selector_rules: list[dict[str, object]] | None,
    record_observed: bool,
) -> list[dict[str, Any]]:
    if not context.original_html or context.original_html == context.cleaned_html:
        return []
    original = context.original_dom_parser
    cleaned_count = _detail_anchor_count(
        parser,
        page_url=page_url,
        surface=surface,
        fallback_fragment_limit=fragment_limit,
    )
    original_count = _detail_anchor_count(
        original,
        page_url=page_url,
        surface=surface,
        fallback_fragment_limit=fragment_limit,
    )
    if original_count < max(3, cleaned_count + 2):
        return []
    logger.debug(
        "Using original listing DOM after cleaned DOM lost detail-link evidence for %s",
        page_url,
    )
    return _dom_listing_stage(
        original,
        page_url=page_url,
        surface=surface,
        is_job_surface=is_job,
        max_records=max_records,
        fallback_fragment_limit=fragment_limit,
        selector_rules=selector_rules,
        record_dom_observed_selectors=record_observed,
    )

def _rendered_listing_records(
    artifacts: dict[str, object] | None,
    page_url: str,
    surface: str,
    is_job: bool,
    max_records: int,
    fragment_limit: int,
    selector_rules: list[dict[str, object]] | None,
    record_observed: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    fragments = artifacts.get("rendered_listing_fragments") if isinstance(artifacts, dict) else None
    if not isinstance(fragments, list):
        return [], []
    fragment_html = "\n".join(filter(None, (str(item or "").strip() for item in fragments)))
    if not fragment_html:
        return [], []
    context = prepare_extraction_context(f"<html><body>{fragment_html}</body></html>")
    records = _dom_listing_stage(
        context.dom_parser,
        page_url=page_url,
        surface=surface,
        is_job_surface=is_job,
        max_records=max_records,
        fallback_fragment_limit=fragment_limit,
        selector_rules=selector_rules,
        record_dom_observed_selectors=record_observed,
    )
    if not _rendered_original_is_needed(context, records, page_url, surface, fragment_limit):
        return records, []
    original_records = _dom_listing_stage(
        context.original_dom_parser,
        page_url=page_url,
        surface=surface,
        is_job_surface=is_job,
        max_records=max_records,
        fallback_fragment_limit=fragment_limit,
        selector_rules=selector_rules,
        record_dom_observed_selectors=record_observed,
    )
    return records, original_records

def _rendered_original_is_needed(
    context: ExtractionContext,
    records: list[dict[str, Any]],
    page_url: str,
    surface: str,
    fragment_limit: int,
) -> bool:
    if not context.noise_removed:
        return not records
    cleaned = _detail_anchor_count(
        context.dom_parser,
        page_url=page_url,
        surface=surface,
        fallback_fragment_limit=fragment_limit,
    )
    original = _detail_anchor_count(
        context.original_dom_parser,
        page_url=page_url,
        surface=surface,
        fallback_fragment_limit=fragment_limit,
    )
    return not records or original >= max(3, cleaned + 2)

def _supported_visual_listing_records(artifacts: dict[str, object] | None, page_url: str, surface: str, max_records: int) -> list[dict[str, Any]]:
    elements = artifacts.get("listing_visual_elements") if isinstance(artifacts, dict) else None
    records = visual_listing_records(
        elements if isinstance(elements, list) else None,
        page_url=page_url,
        surface=surface,
        max_records=max_records,
        title_is_noise=is_title_noise,
        url_is_structural=listing_url_is_structural,
    )
    return [
        record
        for record in records
        if listing_record_supported(
            record,
            page_url=page_url,
            surface=surface,
            title_is_noise=is_title_noise,
            url_is_structural=listing_url_is_structural,
            detail_like_url=lambda url: listing_detail_like_path(url, is_job=surface.startswith("job_")),
        )
    ]

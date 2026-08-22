from __future__ import annotations

import asyncio
from copy import deepcopy

from app.services.dom.html_parser import BeautifulSoup
from app.services.dom.html_parser import NavigableString, Tag
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.crawl_run import CrawlRun
from app.services.config.selectors import (
    SELECTOR_SYNTHESIS_ALLOWED_ATTRS,
    SELECTOR_SELF_HEAL_DEFAULT_MIN_CONFIDENCE,
    SELECTOR_SELF_HEAL_TARGET_LIMIT,
    SELECTOR_SYNTHESIS_DROP_TAGS,
    SELECTOR_SYNTHESIS_KEEP_ATTRS,
    SELECTOR_SYNTHESIS_KEEP_TOKENS,
    SELECTOR_SYNTHESIS_KEEP_WORTHY_TAGS,
    SELECTOR_SYNTHESIS_LOW_VALUE_TAGS,
)
from app.services.config.runtime_settings import crawler_runtime_settings
from app.services.db_utils import mapping_or_empty
from app.services.pipeline.extract_records import extract_records
from app.services.domain_memory_service import (
    load_domain_memory,
    save_domain_memory,
    selector_payload_from_rules,
    selector_rules_from_memory,
)
from app.services.domain_utils import normalize_domain
from app.services.field_policy import (
    field_allowed_for_surface,
    repair_target_fields_for_surface,
)
from app.services.shared.field_coerce import safe_int as _safe_int
from app.services.extraction_html_helpers import prune_html_tree
from app.services.llm.runtime import discover_xpath_candidates
from app.services.dom.xpath_service import (
    extract_selector_value,
    validate_or_convert_xpath,
)


def reduce_html_for_selector_synthesis(html: str) -> str:
    soup = prune_html_tree(
        BeautifulSoup(str(html or ""), "html.parser"),
        drop_tags=tuple(SELECTOR_SYNTHESIS_DROP_TAGS),
        allowed_attrs=set(SELECTOR_SYNTHESIS_ALLOWED_ATTRS),
    )
    _remove_low_value_nodes(soup)
    reduced = BeautifulSoup("<html><body></body></html>", "html.parser")
    source_root = soup.body or soup
    target_root = reduced.body or reduced
    _append_reduced_children(
        reduced,
        target_root,
        list(source_root.children),
        crawler_runtime_settings.selector_synthesis_max_html_chars - len(str(reduced)),
    )
    return str(reduced)


def _append_reduced_children(
    output_soup: BeautifulSoup,
    target_parent: Tag | BeautifulSoup,
    children: list[object],
    budget: int,
) -> int:
    used = 0
    for child in children:
        remaining = budget - used
        if remaining <= 0:
            break
        used += _append_reduced_node(output_soup, target_parent, child, remaining)
    return used


def _append_reduced_node(
    output_soup: BeautifulSoup,
    target_parent: Tag | BeautifulSoup,
    node: object,
    budget: int,
) -> int:
    if budget <= 0:
        return 0
    if isinstance(node, NavigableString):
        return _append_reduced_text(target_parent, node, budget)
    if not isinstance(node, Tag) or not _reduced_tag_is_allowed(node):
        return 0
    serialized = str(node)
    contains_declarative_shadow_dom = (
        node.name != "template"
        and "<template" in serialized.lower()
        and "shadowrootmode=" in serialized.lower()
    )
    if len(serialized) <= budget and not contains_declarative_shadow_dom:
        target_parent.append(deepcopy(node))
        return len(serialized)
    clone = output_soup.new_tag(node.name, attrs=_reduced_tag_attrs(node))
    empty_size = len(str(clone))
    if empty_size >= budget:
        return 0
    used = _append_reduced_children(
        output_soup,
        clone,
        list(node.children),
        budget - empty_size,
    )
    if used <= 0 and not clone.attrs:
        return 0
    target_parent.append(clone)
    return len(str(clone))


def _append_reduced_text(
    target_parent: Tag | BeautifulSoup, node: NavigableString, budget: int
) -> int:
    text = str(node)
    if not text.strip():
        return 0
    chunk = text[:budget]
    target_parent.append(chunk)
    return len(chunk)


def _reduced_tag_is_allowed(node: Tag) -> bool:
    if node.name in SELECTOR_SYNTHESIS_LOW_VALUE_TAGS and not _keep_low_value_node(
        node
    ):
        return False
    return node.name != "template" or node.has_attr("shadowrootmode")


def _reduced_tag_attrs(node: Tag) -> dict[str, str]:
    return {
        str(key): " ".join(str(item) for item in value)
        if isinstance(value, (list, tuple))
        else str(value or "")
        for key, value in dict(node.attrs).items()
    }


def _remove_low_value_nodes(soup: BeautifulSoup) -> None:
    for node in list(soup.find_all(True)):
        if node.name in SELECTOR_SYNTHESIS_LOW_VALUE_TAGS and not _keep_low_value_node(
            node
        ):
            node.decompose()


def _keep_low_value_node(node: Tag) -> bool:
    if node.name not in SELECTOR_SYNTHESIS_KEEP_WORTHY_TAGS:
        return False
    attrs = dict(node.attrs)
    if (
        not any(
            attrs.get(attr_name) not in (None, "", [], {})
            for attr_name in SELECTOR_SYNTHESIS_KEEP_ATTRS
        )
        and not str(attrs.get("aria-label") or "").strip()
    ):
        return False
    current: Tag | None = node
    while isinstance(current, Tag):
        probe = " ".join(
            str(part)
            for part in (
                current.name,
                current.get("id"),
                current.get("class"),
                current.get("data-testid"),
            )
            if part
        ).lower()
        if any(token in probe for token in SELECTOR_SYNTHESIS_KEEP_TOKENS):
            return True
        current = current.parent if isinstance(current.parent, Tag) else None
    return False


def selector_self_heal_enabled(run: CrawlRun) -> tuple[bool, float]:
    snapshot = run.settings_view.extraction_runtime_snapshot()
    selector_self_heal = (
        snapshot.get("selector_self_heal") if isinstance(snapshot, dict) else None
    )
    enabled = bool(
        selector_self_heal.get("enabled")
        if isinstance(selector_self_heal, dict)
        else False
    )
    threshold = _safe_float(
        (
            selector_self_heal.get("min_confidence")
            if isinstance(selector_self_heal, dict)
            else None
        ),
        default=float(SELECTOR_SELF_HEAL_DEFAULT_MIN_CONFIDENCE),
    )
    return enabled, threshold


def selector_self_heal_targets(
    *,
    run: CrawlRun,
    record: dict[str, object],
) -> list[str]:
    confidence = mapping_or_empty(record.get("_confidence"))
    target_limit = max(1, _safe_int(SELECTOR_SELF_HEAL_TARGET_LIMIT, default=6) or 6)
    requested_fields = repair_target_fields_for_surface(
        run.surface,
        run.requested_fields or [],
    )
    targets: list[str] = []
    for field_name in requested_fields:
        if (
            field_allowed_for_surface(run.surface, field_name)
            and record.get(field_name) in (None, "", [], {})
            and field_name not in targets
        ):
            targets.append(field_name)
    if targets:
        return targets[:target_limit]
    for missing_field in _list_or_empty(confidence.get("missing_fields")):
        normalized = str(missing_field or "").strip().lower()
        if (
            normalized
            and field_allowed_for_surface(run.surface, normalized)
            and normalized not in targets
        ):
            targets.append(normalized)
    return targets[:target_limit]


async def apply_selector_self_heal(
    session: AsyncSession,
    *,
    run: CrawlRun,
    page_url: str,
    html: str,
    records: list[dict[str, object]],
    adapter_records: list[dict[str, object]] | None,
    network_payloads: list[dict[str, object]] | None,
    selector_rules: list[dict[str, object]],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    enabled, threshold = selector_self_heal_enabled(run)
    if (
        not enabled
        or not run.settings_view.llm_enabled()
        or "detail" not in run.surface
    ):
        return records, selector_rules

    domain = normalize_domain(page_url)
    updated_records: list[dict[str, object]] = []
    current_rules = list(selector_rules or [])
    memory = await load_domain_memory(session, domain=domain, surface=run.surface)
    existing_rule_count = len(selector_rules_from_memory(memory))
    reduced_html = reduce_html_for_selector_synthesis(html)

    persisted_rules = False
    for record in records:
        next_record, current_rules, added_rules, persisted = await _heal_one_record(
            session,
            run=run,
            domain=domain,
            html=html,
            page_url=page_url,
            reduced_html=reduced_html,
            record=record,
            threshold=threshold,
            existing_rule_count=existing_rule_count,
            current_rules=current_rules,
            adapter_records=adapter_records,
            network_payloads=network_payloads,
        )
        updated_records.append(next_record)
        existing_rule_count += added_rules
        persisted_rules = persisted_rules or persisted
    if persisted_rules:
        await session.flush()
    return updated_records, current_rules


async def _heal_one_record(
    session: AsyncSession,
    *,
    run: CrawlRun,
    domain: str,
    html: str,
    page_url: str,
    reduced_html: str,
    record: dict[str, object],
    threshold: float,
    existing_rule_count: int,
    current_rules: list[dict[str, object]],
    adapter_records: list[dict[str, object]] | None,
    network_payloads: list[dict[str, object]] | None,
) -> tuple[dict[str, object], list[dict[str, object]], int, bool]:
    next_record = dict(record)
    requested_fields = repair_target_fields_for_surface(
        run.surface, run.requested_fields or []
    )
    missing_fields = _missing_requested_fields(next_record, requested_fields)
    confidence = mapping_or_empty(next_record.get("_confidence"))
    score = _safe_float(confidence.get("score"), default=1.0)
    if not missing_fields and (existing_rule_count > 0 or score >= threshold):
        return next_record, current_rules, 0, False
    target_fields = selector_self_heal_targets(run=run, record=next_record)
    if not target_fields:
        return next_record, current_rules, 0, False
    candidates, error_message = await discover_xpath_candidates(
        session,
        run_id=run.id,
        domain=domain,
        url=page_url,
        html_text=reduced_html,
        missing_fields=target_fields,
        existing_values=_public_record_values(next_record),
    )
    synthesized_rules = _validated_xpath_rules(
        html=html, candidates=candidates, target_fields=target_fields
    )
    if not synthesized_rules:
        next_record["_self_heal"] = _self_heal_diagnostics(
            threshold=threshold,
            cache_hit=False,
            error=error_message or "no_valid_selectors",
        )
        return next_record, current_rules, 0, False
    candidate_rules = _merge_selector_rules(current_rules, synthesized_rules)
    rerun_records = await asyncio.to_thread(
        extract_records,
        html,
        page_url,
        run.surface,
        max_records=1,
        requested_fields=requested_fields,
        adapter_records=adapter_records,
        network_payloads=network_payloads,
        selector_rules=candidate_rules,
        extraction_runtime_snapshot=run.settings_view.extraction_runtime_snapshot(),
    )
    rerun_record = _first_rerun_record(rerun_records, fallback=next_record)
    improved = _selector_heal_improved_record(
        before_record=next_record,
        after_record=rerun_record,
        target_fields=target_fields,
    )
    if improved:
        await save_domain_memory(
            session,
            domain=domain,
            surface=run.surface,
            selectors=selector_payload_from_rules(candidate_rules),
        )
    rerun_record["_self_heal"] = _self_heal_diagnostics(
        threshold=threshold,
        cache_hit=existing_rule_count > 0,
        synthesized_rules=synthesized_rules,
        persisted=improved,
        error=_selector_heal_error(error_message, improved=improved),
    )
    return _selector_heal_result(
        rerun_record,
        current_rules=current_rules,
        candidate_rules=candidate_rules,
        synthesized_rules=synthesized_rules,
        improved=improved,
    )


def _missing_requested_fields(
    record: dict[str, object], requested_fields: list[str]
) -> list[str]:
    return [
        field_name
        for field_name in requested_fields
        if record.get(field_name) in (None, "", [], {})
    ]


def _public_record_values(record: dict[str, object]) -> dict[str, object]:
    return {key: value for key, value in record.items() if not str(key).startswith("_")}


def _first_rerun_record(
    records: list[dict[str, object]], *, fallback: dict[str, object]
) -> dict[str, object]:
    return dict(records[0]) if records else fallback


def _selector_heal_error(error_message: str | None, *, improved: bool) -> str | None:
    if error_message:
        return error_message
    return None if improved else "no_quality_improvement"


def _selector_heal_result(
    record: dict[str, object],
    *,
    current_rules: list[dict[str, object]],
    candidate_rules: list[dict[str, object]],
    synthesized_rules: list[dict[str, object]],
    improved: bool,
) -> tuple[dict[str, object], list[dict[str, object]], int, bool]:
    if not improved:
        return record, current_rules, 0, False
    return record, candidate_rules, len(synthesized_rules), True


def _self_heal_diagnostics(
    *,
    threshold: float,
    cache_hit: bool,
    error: str | None,
    synthesized_rules: list[dict[str, object]] | None = None,
    persisted: bool = False,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "enabled": True,
        "triggered": True,
        "threshold": threshold,
        "mode": "selector_synthesis",
        "cache_hit": cache_hit,
        "error": error,
    }
    if synthesized_rules is not None:
        payload["synthesized_fields"] = [
            str(row.get("field_name") or "").strip().lower()
            for row in synthesized_rules
        ]
        payload["persisted"] = persisted
    return payload


def _validated_xpath_rules(
    *,
    html: str,
    candidates: object,
    target_fields: list[str],
) -> list[dict[str, object]]:
    rules: list[dict[str, object]] = []
    allowed_fields = {
        str(field_name or "").strip().lower() for field_name in target_fields
    }
    for row in _list_or_empty(candidates):
        rule = _validated_selector_rule(html, row, allowed_fields=allowed_fields)
        if rule is not None:
            rules.append(rule)
    return rules


def _validated_selector_rule(
    html: str, row: object, *, allowed_fields: set[str]
) -> dict[str, object] | None:
    if not isinstance(row, dict):
        return None
    field_name = str(row.get("field_name") or "").strip().lower()
    xpath = str(row.get("xpath") or "").strip()
    css_selector = str(row.get("css_selector") or "").strip()
    if (
        not field_name
        or field_name not in allowed_fields
        or not (xpath or css_selector)
    ):
        return None
    if xpath and (rule := _validated_xpath_rule(html, field_name, xpath)) is not None:
        return rule
    return _validated_css_rule(html, field_name, css_selector) if css_selector else None


def _validated_xpath_rule(
    html: str, field_name: str, xpath: str
) -> dict[str, object] | None:
    validated_xpath, _ = validate_or_convert_xpath(xpath)
    if not validated_xpath:
        return None
    sample_value, count, selector_used = extract_selector_value(
        html, xpath=validated_xpath
    )
    if count <= 0 or sample_value in (None, ""):
        return None
    return _selector_rule_payload(
        field_name, xpath=selector_used or validated_xpath, sample_value=sample_value
    )


def _validated_css_rule(
    html: str, field_name: str, css_selector: str
) -> dict[str, object] | None:
    sample_value, count, selector_used = extract_selector_value(
        html, css_selector=css_selector
    )
    if count <= 0 or sample_value in (None, ""):
        return None
    return _selector_rule_payload(
        field_name,
        css_selector=selector_used or css_selector,
        sample_value=sample_value,
    )


def _selector_rule_payload(
    field_name: str,
    *,
    xpath: str | None = None,
    css_selector: str | None = None,
    sample_value: object,
) -> dict[str, object]:
    return {
        "field_name": field_name,
        "css_selector": css_selector,
        "xpath": xpath,
        "regex": None,
        "sample_value": sample_value,
        "source": "selector_self_heal",
        "status": "validated",
        "is_active": True,
    }


def _merge_selector_rules(
    existing_rules: list[dict[str, object]],
    new_rules: list[dict[str, object]],
) -> list[dict[str, object]]:
    merged = list(existing_rules or [])
    seen = {_selector_rule_key(row) for row in merged if isinstance(row, dict)}
    next_id = _next_selector_rule_id(merged)
    for row in new_rules:
        key = _selector_rule_key(row)
        if key in seen:
            continue
        seen.add(key)
        merged.append({"id": next_id, **row})
        next_id += 1
    return merged


def _selector_rule_key(row: dict[str, object]) -> tuple[str, str, str, str]:
    return (
        str(row.get("field_name") or "").strip().lower(),
        str(row.get("css_selector") or "").strip(),
        str(row.get("xpath") or "").strip(),
        str(row.get("regex") or "").strip(),
    )


def _next_selector_rule_id(rules: list[dict[str, object]]) -> int:
    ids = (
        parsed_id
        for row in rules
        if isinstance(row, dict)
        for parsed_id in [_safe_int(row.get("id"), default=None)]
        if parsed_id is not None
    )
    return max(ids, default=0) + 1


def _selector_heal_improved_record(
    *,
    before_record: dict[str, object],
    after_record: dict[str, object],
    target_fields: list[str],
) -> bool:
    for field_name in target_fields:
        before_value = before_record.get(field_name)
        after_value = after_record.get(field_name)
        if before_value in (None, "", [], {}) and after_value not in (None, "", [], {}):
            return True
        if before_value != after_value and after_value not in (None, "", [], {}):
            return True
    return False


def _safe_float(value: object, *, default: float) -> float:
    try:
        if value is None:
            return default
        return float(str(value))
    except (TypeError, ValueError):
        return default


def _list_or_empty(value: object) -> list[object]:
    return list(value) if isinstance(value, list) else []


validated_xpath_rules = _validated_xpath_rules
selector_heal_improved_record = _selector_heal_improved_record

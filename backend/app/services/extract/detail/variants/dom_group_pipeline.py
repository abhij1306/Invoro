from __future__ import annotations

from copy import deepcopy
from itertools import product
from typing import Any

from app.services.dom.html_parser import BeautifulSoup
from app.services.config.extraction_rules import (
    DOM_VARIANT_CARTESIAN_COMBO_LIMIT,
    DOM_VARIANT_GROUP_LIMIT,
)
from app.services.extract.detail.variants.dom_merge import (
    dom_variants_add_missing_existing_axis,
    expand_existing_variants_with_dom_axes,
)
from app.services.extract.detail.variants.dom_options import (
    node_attr_is_truthy,
    variant_option_availability,
)
from app.services.extract.detail.variants.state_targets import state_variant_targets
from app.services.extract.variant_choice_collection import (
    iter_variant_choice_groups,
    iter_variant_select_groups,
)
from app.services.extract.variant_choice_traversal import (
    infer_variant_group_name_from_values,
    resolve_variant_group_name,
    variant_dom_cues_present,
)
from app.services.extract.variant_dom_provenance import (
    build_variant_candidate_group,
    variant_option_node_types,
)
from app.services.extract.variant_group_validator import VariantGroupValidator
from app.services.extract.variant_identity_merge import (
    merge_variant_pair,
    resolve_variants,
    split_variant_axes,
)
from app.services.extract.variant_normalization.contract import (
    flatten_variants_for_public_output,
)
from app.services.js_state.helpers import select_variant
from app.services.shared.field_coerce import object_dict, object_list

from . import dom_variant_support as core

__all__ = ("extract_variants_from_dom", "backfill_variants_from_dom_if_missing")


def _collect_select_candidate_groups(
    soup: BeautifulSoup,
    *,
    page_url: str,
) -> list[Any]:
    candidate_groups: list[Any] = []
    for select in iter_variant_select_groups(soup):
        raw_option_values = [
            core.clean_text(option.get_text(" ", strip=True))
            for option in select.find_all("option")
            if core.clean_text(option.get_text(" ", strip=True))
        ]
        cleaned_name = resolve_variant_group_name(
            select
        ) or infer_variant_group_name_from_values(raw_option_values)
        cleaned_name = core._prefer_axis_inferred_from_values(
            cleaned_name,
            raw_option_values,
        )
        if not cleaned_name:
            continue
        component_style = core._component_size_style_from_group_name(
            cleaned_name
        ) or core._component_size_style_from_group_name(
            next(iter(raw_option_values), "")
        )
        if component_style:
            cleaned_name = "size"
        if not core._dom_variant_group_name_allowed(cleaned_name):
            continue
        axis_key = core.normalized_variant_axis_key(cleaned_name)
        option_entries = [
            entry
            for option in select.find_all("option")
            if (
                entry := _select_option_entry(
                    select,
                    option,
                    axis_key=axis_key,
                    component_style=component_style,
                    page_url=page_url,
                )
            )
        ]
        deduped_values = list(
            dict.fromkeys(
                str(entry["value"])
                for entry in option_entries
                if core.text_or_none(entry.get("value"))
            )
        )
        if len(deduped_values) >= 2:
            candidate_groups.append(
                build_variant_candidate_group(
                    select,
                    name=cleaned_name,
                    values=deduped_values,
                    entries=option_entries,
                    extractor_path="select",
                )
            )
    return candidate_groups


def _select_option_entry(
    select: Any,
    option: Any,
    *,
    axis_key: str,
    component_style: str,
    page_url: str,
) -> dict[str, object] | None:
    raw_value_attr = core.text_or_none(option.get("value"))
    option_text = option.get_text(" ", strip=True)
    cleaned_value = core._resolved_variant_option_value(
        axis_key,
        option_text or raw_value_attr,
        page_url=page_url,
    ) or core.clean_text(option_text)
    cleaned_value = core._strip_variant_option_value_suffix_noise(cleaned_value)
    if (
        not cleaned_value
        or core.variant_option_value_is_noise(cleaned_value)
        or (
            raw_value_attr is not None
            and raw_value_attr.lower() in {"select", "choose"}
        )
    ):
        return None
    entry: dict[str, object] = {"value": cleaned_value}
    if node_attr_is_truthy(option, "selected", "aria-selected"):
        entry["selected"] = True
    availability, stock_quantity = variant_option_availability(
        node=option,
        label_node=None,
    )
    if availability:
        entry["availability"] = availability
    if stock_quantity is not None:
        entry["stock_quantity"] = stock_quantity
    variant_url = core.variant_option_url(
        container=select,
        node=option,
        label_node=None,
        page_url=page_url,
    )
    if variant_url:
        entry["url"] = variant_url
    if component_style:
        entry["style"] = component_style
    return entry


def _collect_choice_candidate_groups(
    soup: BeautifulSoup,
    *,
    page_url: str,
    title_hint: str,
) -> list[Any]:
    candidate_groups: list[Any] = []
    for container in iter_variant_choice_groups(soup):
        cleaned_name = core._resolve_dom_variant_group_name(container)
        if not cleaned_name:
            continue
        option_entries = core._collect_variant_choice_entries(
            container,
            page_url=page_url,
            title_hint=title_hint,
        )
        values = [
            str(entry["value"])
            for entry in option_entries
            if core.text_or_none(entry.get("value"))
        ]
        cleaned_name = core._prefer_axis_inferred_from_values(cleaned_name, values)
        if len(values) < 2:
            continue
        option_node_types = variant_option_node_types(
            container,
            extractor_path="choice",
        )
        extractor_path = (
            "choice_radio"
            if any(item in {"input_radio", "role_radio"} for item in option_node_types)
            else "choice_button"
        )
        candidate_groups.append(
            build_variant_candidate_group(
                container,
                name=cleaned_name,
                values=values,
                entries=option_entries,
                extractor_path=extractor_path,
            )
        )
    return candidate_groups


def _validated_dom_option_groups(
    candidate_groups: list[Any],
    *,
    page_url: str,
) -> list[dict[str, object]]:
    validator = VariantGroupValidator()
    option_groups = [
        group.as_option_group()
        for group in candidate_groups
        if validator.validate(group, page_url=page_url)
    ]
    expanded_groups: list[dict[str, object]] = []
    for group in option_groups:
        compound_groups = core._expand_compound_option_group(group)
        expanded_groups.extend(compound_groups or [group])
    return _merge_dom_option_groups(expanded_groups)


def _merge_dom_option_groups(
    groups: list[dict[str, object]],
) -> list[dict[str, object]]:
    merged_groups: dict[str, dict[str, object]] = {}
    for group in groups:
        values = [
            core.clean_text(value)
            for value in object_list(group.get("values"))
            if core.clean_text(value)
        ]
        name = core.clean_text(group.get("name"))
        axis_key = core.normalized_variant_axis_key(name)
        if len(values) < 2 or not axis_key:
            continue
        merged = merged_groups.setdefault(
            axis_key,
            {"name": name or axis_key, "values": [], "entries": {}},
        )
        if len(name) > len(str(merged.get("name") or "")):
            merged["name"] = name
        merged["values"] = list(
            dict.fromkeys([*object_list(merged.get("values")), *values])
        )
        merged_entries = merged.setdefault("entries", {})
        if not isinstance(merged_entries, dict):
            merged_entries = {}
            merged["entries"] = merged_entries
        for group_entry in object_list(group.get("entries")):
            if isinstance(group_entry, dict):
                _merge_dom_option_entry(merged_entries, group_entry)
    return _limited_dom_option_groups(merged_groups)


def _merge_dom_option_entry(
    merged_entries: dict[str, object],
    group_entry: dict[str, object],
) -> None:
    value = core.clean_text(group_entry.get("value"))
    if not value:
        return
    existing = object_dict(merged_entries.get(value, {"value": value}))
    availability = core.text_or_none(group_entry.get("availability"))
    if availability and existing.get("availability") in (None, "", [], {}):
        existing["availability"] = availability
    if group_entry.get("stock_quantity") not in (None, "", [], {}):
        existing["stock_quantity"] = group_entry.get("stock_quantity")
    for key in ("style", "url", "variant_id", "image_url"):
        if group_entry.get(key) not in (None, "", [], {}) and existing.get(key) in (
            None,
            "",
            [],
            {},
        ):
            existing[key] = group_entry.get(key)
    if group_entry.get("selected"):
        existing["selected"] = True
    merged_entries[value] = existing


def _limited_dom_option_groups(
    merged_groups: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
    group_limit = core._safe_int_config(
        DOM_VARIANT_GROUP_LIMIT,
        1,
        "DOM_VARIANT_GROUP_LIMIT",
    )
    groups: list[dict[str, object]] = []
    for group in merged_groups.values():
        values = [
            core.clean_text(value)
            for value in object_list(group.get("values"))
            if core.clean_text(value)
        ]
        if len(values) < 2:
            continue
        groups.append(
            {
                "name": core.clean_text(group.get("name")),
                "values": values,
                "entries": list(object_dict(group.get("entries")).values()),
            }
        )
        if len(groups) >= group_limit:
            break
    return groups


def _build_dom_variant_axes(
    groups: list[dict[str, object]],
    *,
    state_axis_targets: dict[str, Any],
) -> tuple[
    dict[str, list[str]],
    dict[str, dict[str, dict[str, object]]],
    list[tuple[str, str, list[str]]],
]:
    axis_values_by_name: dict[str, list[str]] = {}
    axis_option_metadata: dict[str, dict[str, dict[str, object]]] = {}
    axis_order: list[tuple[str, str, list[str]]] = []
    for group in groups:
        name = core.clean_text(group.get("name"))
        values = [str(value) for value in object_list(group.get("values"))]
        axis_key = core.normalized_variant_axis_key(name)
        if not core._dom_variant_axis_allowed(axis_key):
            continue
        axis_values_by_name[axis_key] = values
        axis_option_metadata[axis_key] = _axis_group_metadata(group)
        _merge_state_axis_metadata(
            axis_option_metadata[axis_key],
            dict(state_axis_targets.get(axis_key) or {}),
        )
        axis_order.append((axis_key, name, values))
    return axis_values_by_name, axis_option_metadata, axis_order


def _axis_group_metadata(
    group: dict[str, object],
) -> dict[str, dict[str, object]]:
    return {
        core.clean_text(entry.get("value")): {
            key: entry.get(key)
            for key in (
                "availability",
                "selected",
                "style",
                "stock_quantity",
                "url",
                "variant_id",
                "image_url",
            )
            if entry.get(key) not in (None, "", [], {})
        }
        for entry in object_list(group.get("entries"))
        if isinstance(entry, dict)
        if core.clean_text(entry.get("value"))
    }


def _merge_state_axis_metadata(
    axis_metadata: dict[str, dict[str, object]],
    state_targets: dict[str, Any],
) -> None:
    for option_value, state_metadata in state_targets.items():
        normalized_option_value = core.clean_text(option_value)
        if not normalized_option_value:
            continue
        merged_metadata = axis_metadata.setdefault(normalized_option_value, {})
        for key in ("url", "variant_id", "image_url"):
            if state_metadata.get(key) not in (
                None,
                "",
                [],
                {},
            ) and merged_metadata.get(key) in (None, "", [], {}):
                merged_metadata[key] = state_metadata[key]


def _assemble_dom_variant_rows(
    axis_order: list[tuple[str, str, list[str]]],
    axis_option_metadata: dict[str, dict[str, dict[str, object]]],
    *,
    state_combo_targets: dict[tuple[tuple[str, str], ...], dict[str, object]],
) -> list[dict[str, object]]:
    axis_names = [axis_key for axis_key, _label, _values in axis_order]
    axis_value_lists = [values for _axis_key, _label, values in axis_order]
    combo_limit = core._safe_int_config(
        DOM_VARIANT_CARTESIAN_COMBO_LIMIT,
        1000,
        "DOM_VARIANT_CARTESIAN_COMBO_LIMIT",
    )
    if _dom_variant_combo_count(axis_value_lists) > combo_limit:
        return _axis_only_dom_variants(axis_order, axis_option_metadata)
    rows: list[dict[str, object]] = []
    for combo in product(*axis_value_lists):
        option_values = {
            axis_name: value
            for axis_name, value in zip(axis_names, combo, strict=False)
            if core.clean_text(value)
        }
        if option_values:
            rows.append(
                _assemble_dom_variant_row(
                    option_values,
                    combo=combo,
                    axis_names=axis_names,
                    axis_option_metadata=axis_option_metadata,
                    state_combo_targets=state_combo_targets,
                )
            )
    return rows


def _assemble_dom_variant_row(
    option_values: dict[str, str],
    *,
    combo: tuple[str, ...],
    axis_names: list[str],
    axis_option_metadata: dict[str, dict[str, dict[str, object]]],
    state_combo_targets: dict[tuple[tuple[str, str], ...], dict[str, object]],
) -> dict[str, object]:
    variant: dict[str, object] = {
        "option_values": option_values,
        **option_values,
    }
    selected_metadata = core._selected_option_metadata(
        axis_option_metadata,
        option_values,
    )
    availability = core._availability_from_selected_options(selected_metadata)
    if availability:
        variant["availability"] = availability
    stock_quantity = core._stock_quantity_from_selected_options(selected_metadata)
    if stock_quantity is not None:
        variant["stock_quantity"] = stock_quantity
    combo_metadata = state_combo_targets.get(tuple(sorted(option_values.items())), {})
    for key in ("url", "variant_id", "image_url"):
        if combo_metadata.get(key) not in (None, "", [], {}):
            variant[key] = combo_metadata[key]
    if len(axis_names) == 1:
        option_metadata = axis_option_metadata.get(axis_names[0], {}).get(
            str(combo[0]),
            {},
        )
        if option_metadata.get("style") not in (None, "", [], {}):
            variant["style"] = option_metadata.get("style")
        for key in ("url", "variant_id", "image_url"):
            if option_metadata.get(key) not in (None, "", [], {}):
                variant[key] = option_metadata.get(key)
    return variant


def _materialize_dom_variant_record(
    axis_values_by_name: dict[str, list[str]],
    axis_option_metadata: dict[str, dict[str, dict[str, object]]],
    axis_order: list[tuple[str, str, list[str]]],
    variants: list[dict[str, object]],
    *,
    page_url: str,
) -> dict[str, object]:
    record: dict[str, object] = {}
    selectable_axes, single_value_attributes = split_variant_axes(
        axis_values_by_name,
        always_selectable_axes=frozenset({"size"}),
    )
    resolved_variants = (
        resolve_variants(selectable_axes or axis_values_by_name, variants)
        if variants
        else []
    )
    active_variant = select_variant(resolved_variants, page_url=page_url)
    selected_option_values = _selected_dom_option_values(
        [axis_key for axis_key, _label, _values in axis_order],
        axis_option_metadata,
    )
    if selected_option_values:
        active_variant = next(
            (
                variant
                for variant in resolved_variants
                if variant.get("option_values") == selected_option_values
            ),
            active_variant,
        )
    for axis_name, value in single_value_attributes.items():
        record.setdefault(axis_name, value)
    flat_variants = (
        flatten_variants_for_public_output(
            resolved_variants,
            page_url=page_url,
        )
        or []
    )
    if flat_variants:
        for variant in flat_variants:
            variant["_validated"] = True
        record["variants"] = flat_variants
        record["variant_count"] = len(flat_variants)
    if active_variant and record.get("availability") in (None, "", [], {}):
        selected_availability = core.text_or_none(active_variant.get("availability"))
        if selected_availability:
            record["availability"] = selected_availability
    return record


def _selected_dom_option_values(
    axis_names: list[str],
    axis_option_metadata: dict[str, dict[str, dict[str, object]]],
) -> dict[str, str]:
    selected: dict[str, str] = {}
    for axis_name in axis_names:
        option_value = next(
            (
                value
                for value, metadata in axis_option_metadata.get(axis_name, {}).items()
                if metadata.get("selected")
            ),
            None,
        )
        if option_value:
            selected[axis_name] = option_value
    return selected


def extract_variants_from_dom(
    soup: BeautifulSoup,
    *,
    page_url: str,
    js_state_objects: dict[str, Any] | None = None,
) -> dict[str, object]:
    cache_key = (str(page_url or ""), id(js_state_objects), id(soup))
    cached = _cached_dom_variant_record(soup, cache_key)
    if cached is not None:
        return cached
    title_hint = core.clean_text(soup.h1.get_text(" ", strip=True) if soup.h1 else "")
    candidate_groups = [
        *_collect_select_candidate_groups(soup, page_url=page_url),
        *_collect_choice_candidate_groups(
            soup,
            page_url=page_url,
            title_hint=title_hint,
        ),
    ]
    groups = _validated_dom_option_groups(candidate_groups, page_url=page_url)
    if not groups:
        return _cache_dom_variant_record(soup, cache_key, {})
    state_axis_targets, state_combo_targets = state_variant_targets(
        js_state_objects,
        page_url=page_url,
    )
    axis_values, axis_metadata, axis_order = _build_dom_variant_axes(
        groups,
        state_axis_targets=state_axis_targets,
    )
    if not axis_values:
        return _cache_dom_variant_record(soup, cache_key, {})
    variants = _assemble_dom_variant_rows(
        axis_order,
        axis_metadata,
        state_combo_targets=state_combo_targets,
    )
    record = _materialize_dom_variant_record(
        axis_values,
        axis_metadata,
        axis_order,
        variants,
        page_url=page_url,
    )
    return _cache_dom_variant_record(soup, cache_key, record)


def _cached_dom_variant_record(
    soup: BeautifulSoup,
    cache_key: tuple[str, int, int],
) -> dict[str, object] | None:
    cache = getattr(soup, core._DOM_VARIANT_CACHE_ATTR, None)
    if not isinstance(cache, dict):
        return None
    cached = cache.get(cache_key)
    return deepcopy(cached) if isinstance(cached, dict) else None


def _cache_dom_variant_record(
    soup: BeautifulSoup,
    cache_key: tuple[str, int, int],
    record: dict[str, object],
) -> dict[str, object]:
    cache = getattr(soup, core._DOM_VARIANT_CACHE_ATTR, None)
    if not isinstance(cache, dict):
        cache = {}
        try:
            setattr(soup, core._DOM_VARIANT_CACHE_ATTR, cache)
        except Exception:
            return record
    cache[cache_key] = deepcopy(record)
    return record


def _dom_variant_combo_count(axis_value_lists: list[list[str]]) -> int:
    count = 1
    for values in axis_value_lists:
        count *= max(1, len(values))
    return count


def _axis_only_dom_variants(
    axis_order: list[tuple[str, str, list[str]]],
    axis_option_metadata: dict[str, dict[str, dict[str, object]]],
) -> list[dict[str, object]]:
    variants: list[dict[str, object]] = []
    for axis_key, _name, values in axis_order:
        for value in values:
            cleaned_value = core.clean_text(value)
            if not cleaned_value:
                continue
            option_values = {axis_key: cleaned_value}
            variant: dict[str, object] = {
                "option_values": option_values,
                axis_key: cleaned_value,
            }
            metadata = axis_option_metadata.get(axis_key, {}).get(cleaned_value, {})
            for key in (
                "availability",
                "selected",
                "style",
                "stock_quantity",
                "url",
                "variant_id",
                "image_url",
            ):
                if metadata.get(key) not in (None, "", [], {}):
                    variant[key] = metadata[key]
            variants.append(variant)
    return variants


def backfill_variants_from_dom_if_missing(
    record: dict[str, Any],
    *,
    soup: BeautifulSoup,
    page_url: str,
    js_state_objects: dict[str, Any] | None = None,
) -> None:
    existing_variants = [
        row for row in record.get("variants") or [] if isinstance(row, dict)
    ]
    if not variant_dom_cues_present(soup):
        return
    dom_variants = extract_variants_from_dom(
        soup,
        page_url=page_url,
        js_state_objects=js_state_objects,
    )
    dom_variant_rows = [
        row
        for row in object_list(dom_variants.get("variants"))
        if isinstance(row, dict)
    ]
    if not dom_variant_rows:
        return
    if (
        core.record_has_rich_existing_variants(record)
        or core.existing_variant_cluster_has_transport_signal(existing_variants)
    ) and not dom_variants_add_missing_existing_axis(
        existing_variants, dom_variant_rows
    ):
        return
    merged_rows = _merge_dom_variant_rows(existing_variants, dom_variant_rows)
    record["variants"] = merged_rows
    record["variant_count"] = len(merged_rows)
    _backfill_dom_variant_shared_fields(record)


def _merge_dom_variant_rows(
    existing_variants: list[dict[str, Any]], dom_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    expanded = expand_existing_variants_with_dom_axes(existing_variants, dom_rows)
    if expanded:
        return expanded
    existing_by_key: dict[str, dict[str, Any]] = {}
    for row in existing_variants:
        row_key = core.text_or_none(row.get("variant_id")) or core.text_or_none(
            row.get("url")
        )
        if row_key:
            existing_by_key.setdefault(row_key, row)
    merged_rows: list[dict[str, Any]] = []
    for dom_row in dom_rows:
        dom_key = core.text_or_none(dom_row.get("variant_id")) or core.text_or_none(
            dom_row.get("url")
        )
        existing_row = existing_by_key.get(dom_key or "") if dom_key else None
        merged_rows.append(
            merge_variant_pair(existing_row, dom_row)
            if isinstance(existing_row, dict)
            else dom_row
        )
    return merged_rows


def _backfill_dom_variant_shared_fields(record: dict[str, Any]) -> None:
    currency = core.text_or_none(record.get("currency"))
    price = core.text_or_none(record.get("price"))
    parent_availability = core.text_or_none(record.get("availability"))
    variants = record.get("variants")
    if not isinstance(variants, list) or not variants:
        return
    if any(
        isinstance(variant, dict) and variant.get("price") not in (None, "", [], {})
        for variant in variants
    ):
        return
    for variant in variants:
        if not isinstance(variant, dict):
            continue
        if (
            parent_availability == "in_stock"
            and variant.get("availability") in (None, "", [], {})
            and variant.get("stock_quantity") in (None, "", [], {})
        ):
            variant["availability"] = parent_availability
        if price:
            variant["price"] = price
        if currency and variant.get("currency") in (None, "", [], {}):
            variant["currency"] = currency

from __future__ import annotations

import re

from app.services.config.data_enrichment import DATA_ENRICHMENT_COLOR_FAMILY_ALIASES
from app.services.shared.field_coerce import clean_text


def object_list(value: object) -> list[object]:
    return list(value) if isinstance(value, (list, tuple)) else []


def attribute_by_name(
    attributes: list[dict[str, object]], name: str
) -> dict[str, object]:
    normalized_name = str(name or "").strip().casefold()
    for item in attributes:
        if str(item.get("name") or "").strip().casefold() == normalized_name:
            return {
                "name": str(item.get("name") or ""),
                "handle": str(item.get("handle") or ""),
                "values": _attribute_values(item),
            }
    return {}


def merged_attribute_by_name(
    attributes: list[dict[str, object]], name: str
) -> dict[str, object]:
    matches = [
        item
        for item in attributes
        if str(item.get("name") or "").strip().casefold()
        == str(name or "").strip().casefold()
    ]
    values: list[str] = []
    seen: set[str] = set()
    for item in matches:
        for value in _attribute_values(item):
            if value.casefold() not in seen:
                seen.add(value.casefold())
                values.append(value)
    if not values:
        return {}
    handle = next(
        (str(item.get("handle") or "") for item in matches if item.get("handle")), ""
    )
    return {"name": str(name or ""), "handle": handle, "values": values}


def shopify_material_terms(
    attributes: list[dict[str, object]], *names: str
) -> dict[str, list[str]]:
    values: dict[str, list[str]] = {}
    for name in names:
        for value in object_list(attribute_by_name(attributes, name).get("values")):
            if cleaned := clean_text(value).casefold():
                values.setdefault(cleaned, [cleaned])
    return values


def shopify_attribute_terms(attribute: dict[str, object]) -> dict[str, list[str]]:
    return {
        cleaned: [cleaned]
        for value in object_list(attribute.get("values"))
        if (cleaned := clean_text(value).casefold())
    }


def shopify_color_family_terms(
    attribute: dict[str, object], attributes: list[dict[str, object]]
) -> dict[str, list[str]]:
    source_values = set(shopify_attribute_terms(attribute))
    source_values.update(
        cleaned
        for item in attributes
        for value in object_list(item.get("values"))
        if isinstance(value, dict)
        if (cleaned := clean_text(value.get("name")).casefold())
    )
    if not source_values:
        return {}
    return {
        canonical: _allowed_color_aliases(canonical, aliases, source_values)
        for canonical, aliases in DATA_ENRICHMENT_COLOR_FAMILY_ALIASES.items()
        if _allowed_color_aliases(canonical, aliases, source_values)
    }


def _allowed_color_aliases(
    canonical: str, aliases: list[str] | tuple[str, ...], source_values: set[str]
) -> list[str]:
    allowed = [
        alias for alias in aliases if clean_text(alias).casefold() in source_values
    ]
    if clean_text(canonical).casefold() in source_values and canonical not in allowed:
        allowed.insert(0, canonical)
    return list(dict.fromkeys(allowed))


def shopify_size_systems(attribute: dict[str, object]) -> dict[str, object]:
    aliases: dict[str, str] = {}
    alpha_values: set[str] = set()
    numeric_values: set[str] = set()
    for value in object_list(attribute.get("values")):
        _add_size_value(clean_text(value), aliases, alpha_values, numeric_values)
    return {
        "aliases": aliases,
        "systems": {"alpha": sorted(alpha_values), "numeric": sorted(numeric_values)},
    }


def _add_size_value(
    cleaned: str,
    aliases: dict[str, str],
    alpha_values: set[str],
    numeric_values: set[str],
) -> None:
    if not cleaned:
        return
    match = re.search(r"\(([A-Za-z0-9]+)\)\s*$", cleaned)
    canonical = match.group(1).upper() if match else ""
    if canonical:
        aliases[cleaned.casefold()] = canonical
        base_name = clean_text(re.sub(r"\s*\([A-Za-z0-9]+\)\s*$", "", cleaned))
        if base_name:
            aliases[base_name.casefold()] = canonical
        target = (
            alpha_values
            if re.fullmatch(r"[A-Z]{1,4}|\d+XL", canonical)
            else numeric_values
        )
        if canonical.isdigit() or target is alpha_values:
            target.add(canonical.casefold())
    if cleaned.casefold() == "one size":
        aliases[cleaned.casefold()] = "OS"
        alpha_values.add("os")
    if cleaned.isdigit():
        numeric_values.add(cleaned.casefold())


def _attribute_values(item: dict[str, object]) -> list[str]:
    return [
        str(value.get("name") or "")
        for value in object_list(item.get("values"))
        if isinstance(value, dict) and str(value.get("name") or "").strip()
    ]

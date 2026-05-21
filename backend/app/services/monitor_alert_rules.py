from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from app.services.config.monitor_settings import (
    ALERT_RULE_LABEL_KEY,
    ALERT_RULE_OPERATOR_CHANGED,
    ALERT_RULE_OPERATOR_EQUALS,
    ALERT_RULE_OPERATOR_GREATER_THAN,
    ALERT_RULE_OPERATOR_GREATER_THAN_OR_EQUALS,
    ALERT_RULE_OPERATOR_KEY,
    ALERT_RULE_OPERATOR_LESS_THAN,
    ALERT_RULE_OPERATOR_LESS_THAN_OR_EQUALS,
    ALERT_RULE_OPERATOR_MISSING,
    ALERT_RULE_OPERATOR_NOT_EQUALS,
    ALERT_RULE_OPERATOR_EXISTS,
    ALERT_RULE_PATH_KEY,
    ALERT_RULE_VALUE_KEY,
    ALERT_RULE_VARIANT_MATCH_KEY,
    ALERT_VARIANT_COLLECTION_FIELD,
    ALERT_VARIANT_IDENTITY_FIELDS,
    ALERT_VARIANT_WILDCARD_PATH_PREFIX,
    TRACKED_FIELD_ALIASES,
)

_FIELD_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_PRICE_RE = re.compile(r"-?\d+(?:\.\d+)?")


def alert_rule_key(rule: dict[str, Any], index: int) -> str:
    label = str(rule.get(ALERT_RULE_LABEL_KEY) or "").strip()
    path = str(rule.get(ALERT_RULE_PATH_KEY) or "").strip()
    return label or path or f"rule_{index + 1}"


def alert_rule_requested_fields(rules: list[dict[str, Any]]) -> list[str]:
    fields: list[str] = []
    for rule in rules:
        path = str(rule.get(ALERT_RULE_PATH_KEY) or "").strip()
        if path.startswith(ALERT_VARIANT_WILDCARD_PATH_PREFIX):
            fields.append(ALERT_VARIANT_COLLECTION_FIELD)
            continue
        root = path.split(".", 1)[0]
        if root:
            fields.append(TRACKED_FIELD_ALIASES.get(root, root))
    return _dedupe(fields)


def alert_rule_tracked_values(data: dict[str, Any], rules: list[dict[str, Any]]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for index, rule in enumerate(rules):
        values[alert_rule_key(rule, index)] = alert_rule_value(data, rule)
    return values


def alert_rule_value(data: dict[str, Any], rule: dict[str, Any]) -> Any:
    path = str(rule.get(ALERT_RULE_PATH_KEY) or "").strip()
    if path.startswith(ALERT_VARIANT_WILDCARD_PATH_PREFIX):
        field = path.removeprefix(ALERT_VARIANT_WILDCARD_PATH_PREFIX)
        if not _FIELD_RE.match(field):
            return None
        variants = data.get(ALERT_VARIANT_COLLECTION_FIELD)
        if not isinstance(variants, list):
            return None
        match = rule.get(ALERT_RULE_VARIANT_MATCH_KEY)
        matched_rows = [
            row
            for row in variants
            if isinstance(row, dict)
            and (not isinstance(match, dict) or _variant_matches(row, match))
        ]
        if isinstance(match, dict):
            row = matched_rows[0] if matched_rows else None
            return _field_value(row, field) if isinstance(row, dict) else None
        return {
            _variant_identity(row, index): _field_value(row, field)
            for index, row in enumerate(matched_rows)
        }
    if "." in path or not _FIELD_RE.match(path):
        return None
    return _field_value(data, path)


def alert_rule_condition_met(rule: dict[str, Any], value: Any) -> bool:
    operator = str(rule.get(ALERT_RULE_OPERATOR_KEY) or ALERT_RULE_OPERATOR_CHANGED)
    expected = rule.get(ALERT_RULE_VALUE_KEY)
    if operator == ALERT_RULE_OPERATOR_CHANGED:
        return True
    if operator == ALERT_RULE_OPERATOR_EXISTS:
        return not _empty(value)
    if operator == ALERT_RULE_OPERATOR_MISSING:
        return _empty(value)
    if operator in {
        ALERT_RULE_OPERATOR_LESS_THAN,
        ALERT_RULE_OPERATOR_GREATER_THAN,
        ALERT_RULE_OPERATOR_LESS_THAN_OR_EQUALS,
        ALERT_RULE_OPERATOR_GREATER_THAN_OR_EQUALS,
    }:
        return _any_value_matches(value, lambda item: _compare_numbers(item, expected, operator))
    if operator == ALERT_RULE_OPERATOR_EQUALS:
        return _any_value_matches(value, lambda item: _normalize_text(item) == _normalize_text(expected))
    if operator == ALERT_RULE_OPERATOR_NOT_EQUALS:
        return _any_value_matches(value, lambda item: _normalize_text(item) != _normalize_text(expected))
    return False


def _field_value(data: dict[str, Any], field: str) -> Any:
    if field in data and not _empty(data[field]):
        return data[field]
    for key, value in data.items():
        if TRACKED_FIELD_ALIASES.get(key) == field and not _empty(value):
            return value
    return data.get(field)


def _variant_matches(row: dict[str, Any], match: dict[str, Any]) -> bool:
    for key, expected in match.items():
        if _normalize_text(_field_value(row, str(key))) != _normalize_text(expected):
            return False
    return True


def _variant_identity(row: dict[str, Any], index: int) -> str:
    for field in ALERT_VARIANT_IDENTITY_FIELDS:
        value = _field_value(row, field)
        if not _empty(value):
            return f"{field}:{_normalize_text(value)}"
    return f"variant:{index + 1}"


def _any_value_matches(value: Any, predicate) -> bool:
    if isinstance(value, dict):
        return any(predicate(item) for item in value.values())
    return predicate(value)


def _compare_numbers(actual: Any, expected: Any, operator: str) -> bool:
    actual_decimal = _decimal_value(actual)
    expected_decimal = _decimal_value(expected)
    if actual_decimal is None or expected_decimal is None:
        return False
    if operator == ALERT_RULE_OPERATOR_LESS_THAN:
        return actual_decimal < expected_decimal
    if operator == ALERT_RULE_OPERATOR_GREATER_THAN:
        return actual_decimal > expected_decimal
    if operator == ALERT_RULE_OPERATOR_LESS_THAN_OR_EQUALS:
        return actual_decimal <= expected_decimal
    if operator == ALERT_RULE_OPERATOR_GREATER_THAN_OR_EQUALS:
        return actual_decimal >= expected_decimal
    return False


def _decimal_value(value: Any) -> Decimal | None:
    if _empty(value):
        return None
    match = _PRICE_RE.search(str(value))
    if not match:
        return None
    try:
        return Decimal(match.group(0))
    except InvalidOperation:
        return None


def _normalize_text(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _empty(value: Any) -> bool:
    return value in (None, "", [], {})


def _dedupe(values: list[str]) -> list[str]:
    output: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            output.append(value)
            seen.add(value)
    return output

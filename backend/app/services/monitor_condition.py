from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation
from typing import Any

from app.services.config.monitor_settings import (
    ALERT_CONDITION_FIELDS,
    ALERT_CONDITION_OPERATORS,
)

_CLAUSE_RE = re.compile(
    r"^\s*(?P<field>[A-Za-z_][A-Za-z0-9_]*)\s*(?P<operator><=|>=|==|!=|<|>)\s*(?P<value>\"[^\"]*\"|'[^']*'|-?\d+(?:\.\d+)?|[A-Za-z_][A-Za-z0-9_]*)\s*$"
)


def condition_matches(condition: str | None, values: dict[str, Any]) -> bool:
    if not condition or not condition.strip():
        return True
    clauses = re.split(r"\s+AND\s+", condition.strip(), flags=re.IGNORECASE)
    if not clauses:
        raise ValueError("Condition is empty")
    return all(_evaluate_clause(clause, values) for clause in clauses)


def validate_condition(condition: str | None) -> None:
    if not condition or not condition.strip():
        return
    condition_matches(condition, {})


def _evaluate_clause(clause: str, values: dict[str, Any]) -> bool:
    match = _CLAUSE_RE.match(clause)
    if match is None:
        raise ValueError("Unsupported condition syntax")
    field = match.group("field")
    operator = match.group("operator")
    raw_expected = match.group("value")
    if field not in ALERT_CONDITION_FIELDS:
        raise ValueError(f"Unsupported condition field: {field}")
    if operator not in ALERT_CONDITION_OPERATORS:
        raise ValueError(f"Unsupported condition operator: {operator}")
    actual = values.get(field)
    if field == "price":
        return _compare_numbers(_decimal_value(actual), _decimal_value(raw_expected), operator)
    return _compare_strings(_text_value(actual), _text_value(raw_expected), operator)


def _decimal_value(value: Any) -> Decimal | None:
    if value in (None, "", [], {}):
        return None
    text = str(value).strip().strip("\"'")
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return Decimal(match.group(0))
    except InvalidOperation:
        return None


def _text_value(value: Any) -> str:
    return " ".join(str(value or "").strip().strip("\"'").lower().split())


def _compare_numbers(actual: Decimal | None, expected: Decimal | None, operator: str) -> bool:
    if actual is None or expected is None:
        return False
    if operator == "<":
        return actual < expected
    if operator == ">":
        return actual > expected
    if operator == "<=":
        return actual <= expected
    if operator == ">=":
        return actual >= expected
    if operator == "==":
        return actual == expected
    if operator == "!=":
        return actual != expected
    return False


def _compare_strings(actual: str, expected: str, operator: str) -> bool:
    if operator == "==":
        return actual == expected
    if operator == "!=":
        return actual != expected
    raise ValueError("String conditions only support == and !=")

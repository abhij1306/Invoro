from __future__ import annotations

from typing import Any


def assert_equal(actual: Any, expected: Any) -> None:
    assert actual == expected


def assert_not_equal(actual: Any, expected: Any) -> None:
    assert actual != expected


def assert_is(actual: Any, expected: Any) -> None:
    assert actual is expected


def assert_is_not(actual: Any, expected: Any) -> None:
    assert actual is not expected


def assert_not_in(member: Any, container: Any) -> None:
    assert member not in container


def assert_greater_than(actual: Any, expected: Any) -> None:
    assert actual > expected


def assert_true(value: Any) -> None:
    assert value

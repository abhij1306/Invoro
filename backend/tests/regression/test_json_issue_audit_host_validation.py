from __future__ import annotations

import sys
from importlib import import_module
from pathlib import Path

import pytest


_REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT))
try:
    audit_record = import_module("agent_debug.json_issue_audit_core").audit_record
finally:
    sys.path.remove(str(_REPO_ROOT))


def _issue_fields(url: str) -> set[str]:
    result = audit_record(
        {
            "url": url,
            "title": "Cotton Shirt",
            "tags": ["labelrelationship: Example Records"],
        }
    )
    return {str(issue["field"]) for issue in result["issues"]}


def _issue_messages(record: dict[str, object]) -> set[str]:
    result = audit_record(record)
    return {str(issue["message"]) for issue in result["issues"]}


@pytest.mark.regression
@pytest.mark.parametrize(
    "url",
    [
        "https://discogs.com/release/1",
        "https://www.discogs.com/release/1",
        "https://www.discogs.com./release/1",
    ],
)
def test_json_audit_applies_discogs_rules_to_domain_and_subdomains(url: str) -> None:
    fields = _issue_fields(url)

    assert "url/tags" in fields
    assert "variants" not in fields


@pytest.mark.regression
@pytest.mark.parametrize(
    "url",
    [
        "https://discogs.com.evil.example/shoe/1",
        "https://evil-discogs.com/shoe/1",
        "https://discogs.com@evil.example/shoe/1",
    ],
)
def test_json_audit_rejects_discogs_hostname_substring_bypasses(url: str) -> None:
    fields = _issue_fields(url)

    assert "url/tags" not in fields
    assert "variants" in fields


@pytest.mark.regression
def test_json_audit_keeps_variant_validation_contract() -> None:
    messages = _issue_messages(
        {
            "url": "https://example.com/products/shoe",
            "title": "Running Shoe",
            "price": "49.99",
            "currency": "USD",
            "variant_count": 3,
            "variants": [
                {"url": "bad", "price": "oops", "size": "8"},
                {"url": "bad", "price": "oops", "size": "9"},
            ],
        }
    )

    assert "variant_count mismatches variants length" in messages
    assert "variant url not http/https" in messages
    assert "variant price not numeric" in messages


@pytest.mark.regression
def test_json_audit_keeps_pollution_validation_contract() -> None:
    messages = _issue_messages(
        {
            "url": "https://example.com/products/widget",
            "title": "Widget",
            "price": "10",
            "currency": "USD",
            "features": [
                "One",
                "Two",
                "Three",
                "Four",
                "Five",
                "Six",
                "Seven",
                "Eight",
            ],
            "tags": [
                "clearance_a",
                "dropship_a",
                "size_a",
                "stock_a",
                "sale_a",
                "promoexclude_a",
                "/shop/product/one",
                "https://x.test/a",
                "/shop/product/two",
            ],
            "description": "Read reviews and buy Widget at Target. Choose from colors",
        }
    )

    assert "features list dominated by tiny/noisy tokens" in messages
    assert "tags polluted by internal metadata tokens" in messages
    assert "tags contain related-product URLs or links" in messages

from __future__ import annotations

import pytest

from app.services.shared.url_utils import (
    ensure_scheme,
    identity_token,
    is_placeholder_image_url,
    absolute_url,
    extract_urls,
    same_host,
)


@pytest.mark.unit
def test_absolute_url_repairs_relative_and_bare_host_values() -> None:
    assert absolute_url("https://example.com/a/page", "../p") == "https://example.com/p"
    assert absolute_url("https://example.com/a/page", "?q=1") == (
        "https://example.com/a/page?q=1"
    )
    assert absolute_url("https://example.com/a/page", "#details") == (
        "https://example.com/a/page#details"
    )
    assert absolute_url("https://example.com", "cdn.example.com") == (
        "https://cdn.example.com"
    )
    assert absolute_url("https://example.com", "") == ""


@pytest.mark.unit
def test_ensure_scheme_preserves_relative_and_existing_scheme() -> None:
    assert ensure_scheme("example.com") == "https://example.com"
    assert ensure_scheme("/path") == "/path"
    assert ensure_scheme("javascript:void(0)") == "javascript:void(0)"
    assert ensure_scheme("http://example.com") == "http://example.com"


@pytest.mark.unit
def test_same_host_and_extract_urls_trim_malformed_candidates() -> None:
    assert same_host("https://example.com/a", "https://example.com/b")
    assert not same_host("https://example.com/a", "https://other.test/b")
    assert extract_urls(
        "See https://example.com/a), https://example.com/b.",
        "https://example.com",
    ) == ["https://example.com/a", "https://example.com/b"]
    assert extract_urls("https://example.com/ahttps://example.com/b", "https://x") == []
    assert extract_urls(
        {"image": {"url": "/img.png"}},
        "https://example.com/p",
    ) == ["https://example.com/img.png"]
    assert extract_urls(["/a", "/a", "/B"], "https://example.com") == [
        "https://example.com/a",
        "https://example.com/B",
    ]


@pytest.mark.unit
def test_placeholder_images_are_rejected() -> None:
    assert is_placeholder_image_url("https://via.placeholder.com/100")
    assert extract_urls("https://via.placeholder.com/100", "https://example.com") == []


@pytest.mark.unit
def test_identity_token_does_not_singularize_double_s_words() -> None:
    assert identity_token("dress") == "dress"
    assert identity_token("glass") == "glass"
    assert identity_token("shoes") == "shoe"

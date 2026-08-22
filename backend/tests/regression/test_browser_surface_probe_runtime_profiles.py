from __future__ import annotations

import json

import pytest

from browser_surface_probe.baseline import _country_code_from_value
from browser_surface_probe.runtime_source import (
    _load_explicit_runtime_source,
    _masked_proxy_profile,
)
from browser_surface_probe.target_diagnostics import _capture_probe_artifacts


@pytest.mark.regression
def test_country_code_prefers_longest_token_bounded_alias() -> None:
    assert _country_code_from_value("British Indian Ocean Territory") == "IO"
    assert _country_code_from_value("origin: India") == "IN"


@pytest.mark.regression
def test_explicit_runtime_source_preserves_profile_proxies(tmp_path) -> None:
    profile_path = tmp_path / "proxy-profile.json"
    profile_path.write_text(
        json.dumps(
            {
                "enabled": True,
                "rotation": "sticky",
                "proxy_list": ["http://user:secret@proxy.example:8080"],
            }
        ),
        encoding="utf-8",
    )

    source = _load_explicit_runtime_source(
        proxies=[],
        proxy_profile_path=str(profile_path),
        locality_profile={},
        browser_engine="chromium",
    )

    assert source.proxy_list == ["http://user:secret@proxy.example:8080"]
    assert source.selected_proxy == source.proxy_list[0]
    assert source.proxy_profile["rotation"] == "sticky"


@pytest.mark.regression
def test_proxy_profile_masking_preserves_non_proxy_fields() -> None:
    sanitized = _masked_proxy_profile(
        {
            "enabled": True,
            "rotation": "sticky",
            "proxy_list": ["http://user:secret@proxy.example:8080"],
        }
    )

    assert sanitized["rotation"] == "sticky"
    assert sanitized["proxy_list"] == ["http://***:***@proxy.example:8080"]


@pytest.mark.asyncio
@pytest.mark.regression
async def test_probe_artifacts_report_only_successful_writes(tmp_path) -> None:
    class FakePage:
        async def screenshot(self, **_kwargs) -> None:
            raise RuntimeError("capture unavailable")

        async def content(self) -> str:
            return "<html><body>ok</body></html>"

    created = await _capture_probe_artifacts(
        FakePage(),
        {
            "screenshot": tmp_path / "shot.png",
            "html": tmp_path / "page.html",
            "body": tmp_path / "body.txt",
        },
    )

    assert created == {"html": "page.html", "body": "body.txt"}

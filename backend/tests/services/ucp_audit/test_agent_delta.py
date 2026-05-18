from __future__ import annotations

from dataclasses import dataclass

import pytest

from app.services.ucp_audit.agent_delta import build_agent_view_delta


@dataclass(slots=True)
class DummyAcquisition:
    html: str
    final_url: str = "https://example.com/p/1"


@pytest.mark.asyncio
async def test_agent_mode_uses_http_only_and_human_mode_uses_browser(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def fake_acquire_url(url: str, *, mode: str):
        calls.append(mode)
        html = (
            "<script type='application/ld+json'>"
            '{"@type":"Product","name":"Agent Product"}'
            "</script>"
            if mode == "http_only"
            else "<html><h1>Human Product</h1><p>$10 USD</p></html>"
        )
        return DummyAcquisition(html=html)

    def fake_extract_human(html: str, url: str) -> dict[str, object]:
        return {"name": "Human Product", "price": "10"}

    monkeypatch.setattr("app.services.ucp_audit.agent_delta.acquire_url", fake_acquire_url)
    monkeypatch.setattr(
        "app.services.ucp_audit.agent_delta.extract_human_view",
        fake_extract_human,
    )

    result = await build_agent_view_delta("https://example.com/p/1")

    assert calls == ["http_only", "browser_only"]
    assert result.agent_extracted == {"name": "Agent Product"}
    assert result.human_visible == {"name": "Human Product", "price": "10"}
    assert result.missing_in_agent_view == ["price"]


def test_fidelity_score_uses_field_overlap() -> None:
    from app.services.ucp_audit.agent_delta import compute_fidelity_score

    assert compute_fidelity_score({"name": "A"}, {"name": "A", "price": "10"}) == 0.5
    assert compute_fidelity_score({}, {"name": "A"}) == 0.0
    assert compute_fidelity_score({}, {}) == 1.0

from __future__ import annotations

import pytest
from types import SimpleNamespace
from app.models.crawl_run import CrawlRecord
from app.services import design_system
from app.services.design_system import (
    build_design_markdown,
    build_design_tokens,
    process_design_system_run,
    design_markdown_for_run,
    sample_design_system_urls,
)
from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = pytest.mark.component


@pytest.mark.asyncio
async def test_design_sampler_uses_same_domain_sitemap_urls(monkeypatch) -> None:
    async def _fake_resolver(domain: str, filter_keyword: str, max_urls: int) -> list[str]:
        assert domain == "https://example.com"
        assert filter_keyword == ""
        assert max_urls >= 6
        return [
            "https://example.com/about",
            "https://cdn.example.net/asset",
            "https://example.com/pricing",
        ]

    monkeypatch.setattr(design_system, "resolve_category_urls_from_sitemap", _fake_resolver)

    urls = await sample_design_system_urls("https://example.com/")

    assert urls == [
        "https://example.com/",
        "https://example.com/about",
        "https://example.com/pricing",
    ]


@pytest.mark.asyncio
async def test_design_sampler_falls_back_to_single_url(monkeypatch) -> None:
    async def _fake_resolver(*_args, **_kwargs) -> list[str]:
        raise ValueError("missing sitemap")

    monkeypatch.setattr(design_system, "resolve_category_urls_from_sitemap", _fake_resolver)

    assert await sample_design_system_urls("https://example.com/page") == [
        "https://example.com/page"
    ]


def test_design_tokens_and_markdown_are_deterministic() -> None:
    tokens = build_design_tokens(
        [
            {
                "title": "Example",
                "css_variables": {"--brand": "#123456", "--tw-bg-opacity": "1"},
                "values": {
                    "colors": ["rgb(18, 52, 86)", "rgb(18, 52, 86)"],
                    "fonts": ["Inter"],
                    "fontSizes": ["16px"],
                    "fontWeights": ["600"],
                    "lineHeights": ["24px"],
                    "spacing": ["12px"],
                    "radius": ["8px"],
                    "shadows": ["0 1px 2px rgba(0, 0, 0, 0.12)"],
                },
                "components": [
                    {
                        "kind": "button",
                        "font_size": "16px",
                        "font_weight": "600",
                        "color": "rgb(255, 255, 255)",
                        "background": "rgb(18, 52, 86)",
                        "radius": "8px",
                        "padding": "8px 12px 8px 12px",
                        "shadow": "none",
                    }
                ],
            }
        ]
    )
    markdown = build_design_markdown(
        tokens=tokens,
        source_urls=["https://example.com/"],
        llm_sections={"overview": "Use the fake color #ffffff everywhere."},
    )

    assert "#123456" in markdown
    assert "`rgb(18, 52, 86)`" not in markdown
    assert "--brand" not in markdown
    assert "Count |" not in markdown
    assert "Observed Evidence" not in markdown
    assert "--tw-bg-opacity" not in markdown
    assert "Use the fake color #ffffff everywhere." not in markdown
    assert markdown.startswith("---\nversion: alpha")
    assert "colors:" in markdown


@pytest.mark.asyncio
async def test_design_markdown_for_run_reads_raw_markdown(
    db_session: AsyncSession,
    create_test_run,
) -> None:
    run = await create_test_run(
        url="https://example.com/",
        surface="design_system",
        settings={"respect_robots_txt": False},
    )
    db_session.add(
        CrawlRecord(
            run_id=run.id,
            source_url=run.url,
            data={"title": "Design System", "url": run.url},
            raw_data={"markdown": "# Design System\n"},
            discovered_data={},
            source_trace={},
        )
    )
    await db_session.commit()

    assert await design_markdown_for_run(db_session, run.id) == "# Design System\n"


@pytest.mark.asyncio
async def test_design_run_logs_with_append_log_event_signature(
    db_session: AsyncSession,
    create_test_run,
    monkeypatch,
) -> None:
    run = await create_test_run(
        url="https://example.com/",
        surface="design_system",
        settings={"respect_robots_txt": False, "llm_enabled": False},
    )

    async def _sample_urls(_url: str) -> list[str]:
        return ["https://example.com/"]

    async def _acquire(_request):
        return SimpleNamespace(
            final_url="https://example.com/",
            method="browser",
            status_code=200,
            content_type="text/html",
            blocked=False,
            browser_diagnostics={},
            network_payloads=[],
            adapter_name=None,
            platform_family=None,
            artifacts={
                "design_system_snapshot": {
                    "title": "Example",
                    "css_variables": {"--brand": "#123456"},
                    "values": {"colors": ["rgb(18, 52, 86)"]},
                    "components": [],
                }
            },
        )

    monkeypatch.setattr(design_system, "sample_design_system_urls", _sample_urls)
    monkeypatch.setattr(design_system, "acquire", _acquire)

    await process_design_system_run(db_session, run)

    assert run.status == "completed"
    assert await design_markdown_for_run(db_session, run.id)

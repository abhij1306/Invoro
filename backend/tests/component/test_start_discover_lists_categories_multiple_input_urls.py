from __future__ import annotations

from .test_playground_service import *  # noqa: F403


@pytest.mark.asyncio
@pytest.mark.component
async def test_start_discover_lists_categories_for_multiple_input_urls(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    playground = PlaygroundSession(
        user_id=test_user.id,
        input_url="https://brand-a.example",
        state="created",
        step_data={
            "input_urls": [
                "https://brand-a.example",
                "https://brand-b.example",
            ],
            "category_limit": 1,
        },
    )
    db_session.add(playground)
    await db_session.flush()

    async def _fake_discover_category_urls(urls: list[str], **kwargs: object):
        assert urls == ["https://brand-a.example", "https://brand-b.example"]
        assert kwargs["limit"] == 1
        trees = {
            domain: [
                {
                    "label": "Collections",
                    "children": [
                        {
                            "label": "Women",
                            "url": f"{domain}/collections/women",
                            "children": [],
                        }
                    ],
                }
            ]
            for domain in urls
        }
        groups = {
            domain: [f"{domain}/collections/women", f"{domain}/collections/men"][:1]
            for domain in urls
        }
        return {
            "status": "completed",
            "source": "sitemap",
            "sources": {domain: "sitemap" for domain in urls},
            "urls": ["https://brand-a.example/collections/women"],
            "groups": groups,
            "trees": trees,
            "errors": {},
            "diagnostics": {},
            "total_found": 2,
            "limit": 1,
        }

    monkeypatch.setattr(
        "app.services.playground_service.discover_category_urls",
        _fake_discover_category_urls,
    )

    result = await start_discover(
        db_session,
        playground=playground,
        user=test_user,
    )

    assert result == {"stage": "sitemap", "url_count": 2}
    assert playground.state == "sitemap_listed"
    assert playground.step_data["sitemap"]["urls"] == [
        "https://brand-a.example/collections/women",
    ]
    assert playground.step_data["sitemap"]["limit"] == 1
    assert playground.step_data["sitemap"]["groups"] == {
        "https://brand-a.example": ["https://brand-a.example/collections/women"],
        "https://brand-b.example": ["https://brand-b.example/collections/women"],
    }
    assert playground.step_data["sitemap"]["trees"] == {
        "https://brand-a.example": [
            {
                "label": "Collections",
                "children": [
                    {
                        "label": "Women",
                        "url": "https://brand-a.example/collections/women",
                        "children": [],
                    }
                ],
            }
        ],
        "https://brand-b.example": [
            {
                "label": "Collections",
                "children": [
                    {
                        "label": "Women",
                        "url": "https://brand-b.example/collections/women",
                        "children": [],
                    }
                ],
            }
        ],
    }

@pytest.mark.asyncio
@pytest.mark.component
async def test_start_discover_does_not_block_remaining_urls_on_slow_first_input(
    db_session: AsyncSession,
    test_user,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    playground = PlaygroundSession(
        user_id=test_user.id,
        input_url="https://slow-brand.example",
        state="created",
        step_data={
            "input_urls": [
                "https://slow-brand.example",
                "https://fast-brand.example",
            ],
            "category_limit": 10,
        },
    )
    db_session.add(playground)
    await db_session.flush()

    async def _fake_discover_category_urls(urls: list[str], **kwargs: object):
        assert urls == ["https://slow-brand.example", "https://fast-brand.example"]
        return {
            "status": "completed",
            "source": "multi",
            "sources": {
                "https://slow-brand.example": "timeout",
                "https://fast-brand.example": "sitemap",
            },
            "urls": ["https://fast-brand.example/collections/women"],
            "groups": {
                "https://slow-brand.example": [],
                "https://fast-brand.example": [
                    "https://fast-brand.example/collections/women"
                ],
            },
            "trees": {},
            "errors": {"https://slow-brand.example": "TimeoutError"},
            "diagnostics": {},
            "total_found": 1,
            "limit": 10,
        }

    monkeypatch.setattr(
        "app.services.playground_service.discover_category_urls",
        _fake_discover_category_urls,
    )

    result = await start_discover(db_session, playground=playground, user=test_user)

    assert result == {"stage": "sitemap", "url_count": 1}
    assert playground.step_data["sitemap"]["urls"] == [
        "https://fast-brand.example/collections/women"
    ]
    assert (
        playground.step_data["sitemap"]["sources"]["https://slow-brand.example"]
        == "timeout"
    )
    assert (
        playground.step_data["sitemap"]["errors"]["https://slow-brand.example"]
        == "TimeoutError"
    )

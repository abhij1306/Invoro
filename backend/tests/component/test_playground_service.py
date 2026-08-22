from __future__ import annotations

from datetime import UTC, datetime

from types import SimpleNamespace

import pytest

import pytest_asyncio

from httpx import ASGITransport, AsyncClient

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db

from app.main import app

from app.models.crawl_run import CrawlRecord

from app.models.playground import PlaygroundSession

from app.schemas.playground import PlaygroundSessionCreate

from app.services.playground_service import _classify_input_url, _merge_seed_detail_products, create_session, get_session, get_results, select_category, start_discover, start_pipeline  # fmt: skip

async def _seed_extract_run(
    db_session: AsyncSession,
    create_test_run,
    *,
    url: str,
    title: str,
    price: str,
) -> tuple[int, int]:
    run = await create_test_run(url=url, surface="ecommerce_detail")
    run.status = "completed"
    run.completed_at = datetime.now(UTC)
    record = CrawlRecord(
        run_id=run.id,
        source_url=url,
        data={"title": title, "price": price, "url": url},
        raw_data={},
        discovered_data={},
        source_trace={},
    )
    db_session.add(record)
    await db_session.flush()
    return int(run.id), int(record.id)

def _playground_session(
    test_user,
    *,
    selected_urls: list[str],
    run_ids: list[int],
) -> PlaygroundSession:
    return PlaygroundSession(
        user_id=test_user.id,
        input_url="https://www.wrangler.com/",
        state="extracted",
        step_data={
            "selected_urls": selected_urls,
            "extract": {
                "run_id": run_ids[0],
                "run_ids": run_ids,
                "status": "completed",
                "url_count": len(selected_urls),
            },
        },
    )

@pytest_asyncio.fixture
async def playground_api_client(db_session: AsyncSession, test_user):
    async def _override_db():
        yield db_session

    async def _override_user():
        return test_user

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as client:
        yield client
    app.dependency_overrides.clear()


__all__ = ['ASGITransport', 'AsyncClient', 'AsyncSession', 'CrawlRecord', 'PlaygroundSession', 'PlaygroundSessionCreate', 'SimpleNamespace', 'UTC', '_classify_input_url', '_merge_seed_detail_products', '_playground_session', '_seed_extract_run', 'annotations', 'app', 'create_session', 'datetime', 'get_current_user', 'get_db', 'get_results', 'get_session', 'playground_api_client', 'pytest', 'pytest_asyncio', 'select_category', 'start_discover', 'start_pipeline']  # fmt: skip

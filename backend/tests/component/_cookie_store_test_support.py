from __future__ import annotations

import pytest_asyncio

from app.services.acquisition import cookie_store


@pytest_asyncio.fixture(autouse=True)
async def clear_cookie_store_cache_after_test():
    yield
    await cookie_store.clear_cookie_store_cache()

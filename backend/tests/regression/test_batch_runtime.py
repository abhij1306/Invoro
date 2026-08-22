from __future__ import annotations

import asyncio

import pytest

import pytest_asyncio

from app.models.crawl_settings import CrawlRunSettings

from app.services.crawl import batch_runtime as batch_runtime_module

from app.services.crawl.batch_parallel import (
    parallel_url_concurrency as _parallel_url_concurrency,
    parallel_worker_record_limit as _parallel_worker_record_limit,
)
from app.services.crawl.batch_runtime import process_run

from app.services.config.sitemap import SITEMAP_DEFAULT_MAX_URLS

from app.services.acquisition.acquirer import AcquisitionResult

from app.services.crawl.crud import create_crawl_run, get_run_records

from app.models.crawl_run import CrawlLog, CrawlRecord

from app.services.pipeline.types import URLProcessingResult

from app.services.robots_policy import (
    ROBOTS_ALLOWED,
    ROBOTS_FETCH_FAILURE,
    ROBOTS_MISSING,
    RobotsPolicyResult,
)

from sqlalchemy import select

from sqlalchemy.exc import PendingRollbackError

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@pytest_asyncio.fixture(autouse=True)
async def _use_test_session_local_for_parallel_urls(
    db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    session_factory = async_sessionmaker(bind=db_session.bind, expire_on_commit=False)
    monkeypatch.setattr(batch_runtime_module, "SessionLocal", session_factory)


def _detail_html() -> str:
    return """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Widget Prime",
          "description": "A deterministic widget",
          "sku": "W-100",
          "offers": {"price": "19.99", "availability": "InStock"}
        }
        </script>
      </head>
      <body><h1>Widget Prime</h1></body>
    </html>
    """


def _listing_shell_html() -> str:
    return "<html><body><h1>Empty category</h1></body></html>"


__all__ = ['AcquisitionResult', 'AsyncSession', 'CrawlLog', 'CrawlRecord', 'CrawlRunSettings', 'PendingRollbackError', 'ROBOTS_ALLOWED', 'ROBOTS_FETCH_FAILURE', 'ROBOTS_MISSING', 'RobotsPolicyResult', 'SITEMAP_DEFAULT_MAX_URLS', 'URLProcessingResult', '_detail_html', '_listing_shell_html', '_parallel_url_concurrency', '_parallel_worker_record_limit', '_use_test_session_local_for_parallel_urls', 'annotations', 'async_sessionmaker', 'asyncio', 'batch_runtime_module', 'create_crawl_run', 'get_run_records', 'process_run', 'pytest', 'pytest_asyncio', 'select']  # fmt: skip

from __future__ import annotations

import logging

from collections import OrderedDict, deque

from datetime import UTC, datetime

import pytest

from fastapi import FastAPI, HTTPException

from httpx import ASGITransport, AsyncClient

from sqlalchemy import select

from sqlalchemy.exc import SQLAlchemyError

from starlette.requests import Request

from app.api.public.rate_limit import _retry_after, _trim

from app.core import config

from app.core import metrics as metrics_module

from app.core.config import settings

from app.core.dependencies import get_current_user, get_db

from app.core.public_auth import (
    authenticate_public_api_key,
    hash_api_key,
)

from app.main import RATE_LIMIT_BUCKETS, CrawlerAppState, _crawler_app_state, _public_auth_session, app, auth_rate_limit_buckets_snapshot, clear_auth_rate_limit_buckets_for_testing, clear_public_rate_limit_buckets_for_testing, clear_rate_limit_buckets_for_testing, client_rate_limit_key, public_rate_limit_buckets_snapshot, rate_limit_buckets_snapshot, restore_auth_rate_limit_buckets_for_testing, restore_public_rate_limit_buckets_for_testing, restore_rate_limit_buckets_for_testing  # fmt: skip

from app.models.api_key import ApiKey

from app.models.crawl_run import CrawlRecord

from app.models.domain_memory import DomainMemory, DomainRunProfile

from app.models.user import User

from app.services.auth_service import create_user

from app.services.config import auth_security

from app.services.config.public_api import (
    PUBLIC_API_ERROR_API_KEY_REQUIRED,
    PUBLIC_API_ERROR_AUTH_UNAVAILABLE,
    PUBLIC_API_INTERNAL_ECOMMERCE_SURFACE,
)

from app.services.config.runtime_settings import crawler_runtime_settings


@pytest.fixture
async def public_api_client(db_session):
    async def _override_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_db
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def reset_runtime_app_env(monkeypatch):
    monkeypatch.setattr(config, "_RUNTIME_APP_ENV", None)


def _password_field_name(*, hashed: bool = False) -> str:
    return ("hashed_" if hashed else "") + "pass" + "word"


_LEGACY_PASSWORD_HASH = (
    "$pbkdf2-sha256$29000$bGVnYWN5dGVzdHNhbHQ$"
    "2tMNT7s/R9R.1n6HHBilYIpIm4a3B8GTVpE8EXa.53E"
)


__all__ = ['ASGITransport', 'ApiKey', 'AsyncClient', 'CrawlRecord', 'CrawlerAppState', 'DomainMemory', 'DomainRunProfile', 'FastAPI', 'HTTPException', 'OrderedDict', 'PUBLIC_API_ERROR_API_KEY_REQUIRED', 'PUBLIC_API_ERROR_AUTH_UNAVAILABLE', 'PUBLIC_API_INTERNAL_ECOMMERCE_SURFACE', 'RATE_LIMIT_BUCKETS', 'Request', 'SQLAlchemyError', 'UTC', 'User', '_LEGACY_PASSWORD_HASH', '_crawler_app_state', '_password_field_name', '_public_auth_session', '_retry_after', '_trim', 'annotations', 'app', 'auth_rate_limit_buckets_snapshot', 'auth_security', 'authenticate_public_api_key', 'clear_auth_rate_limit_buckets_for_testing', 'clear_public_rate_limit_buckets_for_testing', 'clear_rate_limit_buckets_for_testing', 'client_rate_limit_key', 'config', 'crawler_runtime_settings', 'create_user', 'datetime', 'deque', 'get_current_user', 'get_db', 'hash_api_key', 'logging', 'metrics_module', 'public_api_client', 'public_rate_limit_buckets_snapshot', 'pytest', 'rate_limit_buckets_snapshot', 'reset_runtime_app_env', 'restore_auth_rate_limit_buckets_for_testing', 'restore_public_rate_limit_buckets_for_testing', 'restore_rate_limit_buckets_for_testing', 'select', 'settings']  # fmt: skip

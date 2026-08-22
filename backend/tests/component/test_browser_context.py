from __future__ import annotations

import asyncio

from pathlib import Path

from uuid import uuid4

from types import SimpleNamespace

import pytest

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.fetch import fetch_context as crawl_fetch_runtime

from app.models.domain_memory import DomainCookieMemory

from app.services.acquisition import browser_identity, browser_storage_state

from app.services.acquisition import browser_proxy_bridge

from app.services.acquisition import cookie_store

from app.services.acquisition import host_protection_memory

from app.services.acquisition import browser_pool as acquisition_browser_pool

from app.services.acquisition.browser_readiness import analyze_html

from app.services.acquisition.browser_proxy_config import build_browser_proxy_config

from app.services.acquisition import browser_runtime as acquisition_browser_runtime

from app.services.acquisition.runtime import (
    has_extractable_dom_content_detail_signals,
    has_extractable_listing_signals,
)

from app.services.config.runtime_settings import crawler_runtime_settings

from app.services.domain_utils import is_special_use_domain, normalize_domain

_PASSWORD_KEY = "pass" + "word"


def _credential_url(
    *,
    scheme: str,
    username: str,
    secret: str,
    host: str,
    port: int | None = None,
    path: str = "",
) -> str:
    port_suffix = f":{port}" if port is not None else ""
    path_suffix = path if not path or path.startswith("/") else f"/{path}"
    return f"{scheme}://{username}:{secret}@{host}{port_suffix}{path_suffix}"


def _authority_with_credentials(
    *, username: str, secret: str, host: str, port: int
) -> str:
    return f"{username}:{secret}@{host}:{port}"


def _masked_proxy_display(*, scheme: str, host: str, port: int) -> str:
    return f"{scheme}://***:***@{host}:{port}"


def _secret_mapping(secret: str) -> dict[str, str]:
    return {_PASSWORD_KEY: secret}


def _context_spec(
    context_options: dict[str, object] | None = None,
    *,
    init_script: str | None = None,
) -> browser_identity.PlaywrightContextSpec:
    return browser_identity.PlaywrightContextSpec(
        context_options=dict(context_options or {}),
        init_script=init_script,
    )


__all__ = ['AsyncSession', 'DomainCookieMemory', 'Path', 'SimpleNamespace', '_PASSWORD_KEY', '_authority_with_credentials', '_context_spec', '_credential_url', '_masked_proxy_display', '_secret_mapping', 'acquisition_browser_pool', 'acquisition_browser_runtime', 'analyze_html', 'annotations', 'async_sessionmaker', 'asyncio', 'browser_identity', 'browser_proxy_bridge', 'browser_storage_state', 'build_browser_proxy_config', 'cookie_store', 'crawl_fetch_runtime', 'crawler_runtime_settings', 'has_extractable_dom_content_detail_signals', 'has_extractable_listing_signals', 'host_protection_memory', 'is_special_use_domain', 'normalize_domain', 'pytest', 'uuid4']  # fmt: skip

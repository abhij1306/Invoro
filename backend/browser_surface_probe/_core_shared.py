from __future__ import annotations

import argparse

import asyncio

import json

import logging

import re

import time

from dataclasses import dataclass

from datetime import UTC, datetime

from ipaddress import ip_address

from pathlib import Path

from typing import Any, Sequence

from urllib.parse import urlparse

import pytz  # type: ignore[import-untyped]

from app.core.database import SessionLocal

from app.services.acquisition.runtime import (
    classify_block_from_headers,
    classify_blocked_page,
    copy_headers,
    curl_fetch,
    http_fetch,
)

from app.services.acquisition.browser_runtime import (
    SharedBrowserRuntime,
    _display_proxy,
    get_browser_runtime,
    shutdown_browser_runtime,
)

from app.services.config.browser_surface_probe import (
    BROWSER_SURFACE_PROBE_CREEPJS_LABELS,
    BROWSER_SURFACE_PROBE_FONT_TEST_STRINGS,
    BROWSER_SURFACE_PROBE_HIGH_ENTROPY_HINTS,
    BROWSER_SURFACE_PROBE_KEYWORD_GROUPS,
    BROWSER_SURFACE_PROBE_NEIGHBOR_LINE_WINDOW,
    BROWSER_SURFACE_PROBE_PIXELSCAN_LABELS,
    BROWSER_SURFACE_PROBE_POST_NAVIGATION_WAIT_MS,
    BROWSER_SURFACE_PROBE_REQUEST_DELAY_MS,
    BROWSER_SURFACE_PROBE_RETRY_BACKOFF_MS,
    BROWSER_SURFACE_PROBE_SITE_MAX_RETRIES,
    BROWSER_SURFACE_PROBE_RISK_TOKENS,
    BROWSER_SURFACE_PROBE_SAFE_TOKENS,
    BROWSER_SURFACE_PROBE_SANNYSOFT_LABELS,
    BROWSER_SURFACE_PROBE_TABLE_ROW_LIMIT,
    BROWSER_SURFACE_PROBE_TARGETS,
    BROWSER_SURFACE_PROBE_TARGET_BODY_ARTIFACT_LIMIT,
    BROWSER_SURFACE_PROBE_TARGET_CHALLENGE_COOKIE_TOKENS,
    BROWSER_SURFACE_PROBE_TARGET_COOKIE_NAME_LIMIT,
    BROWSER_SURFACE_PROBE_TARGET_GEO_ENDPOINTS,
    BROWSER_SURFACE_PROBE_TARGET_HTTP_TIMEOUT_SECONDS,
    BROWSER_SURFACE_PROBE_TARGET_NAVIGATION_TIMEOUT_MS,
    BROWSER_SURFACE_PROBE_TARGET_RESPONSE_HEADER_ALLOWLIST,
    BROWSER_SURFACE_PROBE_TARGET_VISIBLE_TEXT_SNIPPET_LIMIT,
    BROWSER_SURFACE_PROBE_TIMEZONE_ALIASES,
    BROWSER_SURFACE_PROBE_VISIBLE_TEXT_LIMIT,
    BROWSER_SURFACE_PROBE_WEBRTC_GATHER_TIMEOUT_MS,
)

from app.services.crawl.crud import get_run

from browser_surface_probe.report_rendering import (
    build_agent_summary,
    render_markdown,
)

from browser_surface_probe.value_coercion import (
    BROWSER_VERSION_RE,
    object_dict,
    object_list,
    string_list,
)

_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

_WHITESPACE_RE = re.compile(r"\s+")

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

_COUNTRY_CODE_BY_NAME = {
    _NON_ALNUM_RE.sub(" ", name.lower()).strip(): code
    for code, name in pytz.country_names.items()
}

_COUNTRY_CODE_BY_NAME.update(
    {
        "uk": "GB",
        "united kingdom": "GB",
        "usa": "US",
        "u s a": "US",
        "united states": "US",
        "united states of america": "US",
    }
)

_BUNDLE_DIRNAME = "browser_surface_probe"

_BASELINE_PROBE_SCRIPT_PATH = Path(__file__).resolve().with_name("baseline_probe.js")

logger = logging.getLogger(__name__)

_object_dict = object_dict

_object_list = object_list

_string_list = string_list

if __name__ == "__main__":
    raise SystemExit(main())

__all__ = tuple(
    name for name in globals() if not name.startswith("__")
)

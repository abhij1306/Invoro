from __future__ import annotations

import asyncio
import inspect
from collections.abc import Mapping
from dataclasses import dataclass, field
import logging
import re
from typing import Any, cast

import httpx

from app.services.acquisition.browser_readiness import HtmlAnalysis, analyze_html
from app.services.acquisition.content_signals import (
    challenge_element_hits,
    has_extractable_detail_signals as _has_extractable_detail_signals,
    has_extractable_dom_content_detail_signals,
    has_extractable_listing_signals,
    has_extractable_listing_signals as _has_extractable_listing_signals,
    looks_like_js_shell as _looks_like_js_shell,
    looks_like_listing_shell as _looks_like_listing_shell,
)
from app.core.config import settings
from app.services.config.block_signatures import BLOCK_SIGNATURES, CAPTCHA_MARKER
from app.services.config.content_types import HTML_CONTENT_TYPE
from app.services.config.extraction_rules import (
    BROWSER_DETAIL_READINESS_HINTS,
)
from app.services.config.runtime_settings import crawler_runtime_settings
from app.services.db_utils import mapping_or_empty
from app.services.network_resolution import (
    address_family_preference,
    build_async_http_client,
    default_request_headers,
)
from app.services.platform_policy import resolve_platform_runtime_policy

logger = logging.getLogger(__name__)


def _challenge_element_hits(soup: Any, lowered_html: str) -> list[str]:
    return challenge_element_hits(soup, lowered_html, block_signatures=BLOCK_SIGNATURES)


_SHARED_HTTP_CLIENTS: dict[tuple[str | None, str], httpx.AsyncClient] = {}
_SHARED_HTTP_CLIENT_LOCK = asyncio.Lock()
_ECOMMERCE_DETAIL_READINESS_HINTS = tuple(
    str(item).strip().lower()
    for item in (
        (BROWSER_DETAIL_READINESS_HINTS.get("ecommerce") if isinstance(BROWSER_DETAIL_READINESS_HINTS, Mapping) else [])
        or []
    )
    if str(item).strip()
)


@dataclass(slots=True)
class PageFetchResult:
    url: str
    final_url: str
    html: str
    status_code: int
    method: str
    content_type: str = HTML_CONTENT_TYPE
    blocked: bool = False
    platform_family: str | None = None
    headers: httpx.Headers = field(default_factory=httpx.Headers)
    network_payloads: list[dict[str, object]] = field(default_factory=list)
    browser_diagnostics: dict[str, object] = field(default_factory=dict)
    artifacts: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class NetworkPayloadReadResult:
    body: bytes | None
    outcome: str
    error: str | None = None


@dataclass(frozen=True, slots=True)
class BlockPageClassification:
    blocked: bool
    outcome: str
    evidence: list[str] = field(default_factory=list)
    provider_hits: list[str] = field(default_factory=list)
    active_provider_hits: list[str] = field(default_factory=list)
    strong_hits: list[str] = field(default_factory=list)
    weak_hits: list[str] = field(default_factory=list)
    title_matches: list[str] = field(default_factory=list)
    challenge_element_hits: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class _BlockPageEvidence:
    title_matches: list[str]
    strong_hits: set[str]
    weak_hits: set[str]
    provider_hits: set[str]
    active_provider_hits: set[str]
    challenge_element_hits: set[str]
    hard_strong_hits: set[str]
    has_extractable_content: bool


_BOT_VENDOR_HEADER_MARKERS: tuple[tuple[str, str, str], ...] = (
    ("x-datadome", "", "datadome"),
    ("x-datadome-cid", "", "datadome"),
    ("server", "datadome", "datadome"),
    ("cf-mitigated", "challenge", "cloudflare"),  # only when value = "challenge"
    ("x-sucuri-id", "", "sucuri"),
    ("x-sucuri-cache", "", "sucuri"),
    ("x-akamai-transformed", "", "akamai"),
    ("akamai-grn", "", "akamai"),
    ("x-px-block", "", "perimeterx"),
)


def is_retryable_http_status(status_code: int) -> bool:
    code = int(status_code or 0)
    configured_retry_statuses = {int(item) for item in list(crawler_runtime_settings.http_retry_status_codes or [])}
    return code in configured_retry_statuses or 500 <= code <= 599


def is_non_retryable_http_status(status_code: int) -> bool:
    code = int(status_code or 0)
    if code == 401:
        return True
    configured_retry_statuses = {int(item) for item in list(crawler_runtime_settings.http_retry_status_codes or [])}
    return 400 <= code <= 499 and code not in configured_retry_statuses


def is_blocked_html(html: str, status_code: int) -> bool:
    return classify_blocked_page(html, status_code).blocked


def classify_block_from_headers(headers: Any) -> str | None:
    if not headers:
        return None
    try:
        items = list(headers.items()) if hasattr(headers, "items") else list(headers)
    except Exception:
        return None
    normalized: dict[str, str] = {}
    for key, value in items:
        normalized[str(key or "").strip().lower()] = str(value or "").strip().lower()
    for header_name, must_contain, vendor in _BOT_VENDOR_HEADER_MARKERS:
        value = normalized.get(header_name)
        if value is None:
            continue
        if must_contain and must_contain not in value:
            continue
        return vendor
    return None


def classify_blocked_page(
    html: str,
    status_code: int,
    *,
    analysis: HtmlAnalysis | None = None,
) -> BlockPageClassification:
    code = int(status_code or 0)
    if code == 401:
        return BlockPageClassification(
            blocked=False,
            outcome="auth_wall",
            evidence=[f"http_status:{code}"],
        )
    forced_blocked, forced_outcome, base_evidence = _forced_block_status(code)
    lowered = str(html or "").lower()
    if not lowered.strip():
        if forced_blocked:
            return BlockPageClassification(
                blocked=True,
                outcome=forced_outcome,
                evidence=base_evidence,
            )
        return BlockPageClassification(blocked=False, outcome="empty")

    analysis = analysis or analyze_html(html)
    block_evidence = _collect_block_page_evidence(
        html,
        lowered=lowered,
        analysis=analysis,
    )
    blocked = forced_blocked or _block_evidence_indicates_block(block_evidence)
    if _usable_content_overrides_block(blocked, block_evidence):
        blocked = False
    return _build_block_page_classification(
        blocked=blocked,
        forced_blocked=forced_blocked,
        forced_outcome=forced_outcome,
        base_evidence=base_evidence,
        block_evidence=block_evidence,
    )


def _forced_block_status(code: int) -> tuple[bool, str, list[str]]:
    if code == 429:
        return True, "rate_limited", [f"http_status:{code}"]
    if code == 403:
        return True, "challenge_page", [f"http_status:{code}"]
    return False, "", []


def _collect_block_page_evidence(
    html: str,
    *,
    lowered: str,
    analysis: HtmlAnalysis,
) -> _BlockPageEvidence:
    visible_text = analysis.visible_text.lower()
    title_text = analysis.title_text.lower()
    strong_markers = _normalized_mapping_keys("browser_challenge_strong_markers")
    weak_markers = _normalized_mapping_keys("browser_challenge_weak_markers")
    provider_markers = _normalized_signature_strings("provider_markers")
    content_tolerant_strong_markers = set(_normalized_signature_strings("content_tolerant_strong_markers"))
    strong_hits = {marker for marker in strong_markers if marker in visible_text or marker in title_text}
    return _BlockPageEvidence(
        title_matches=_block_title_matches(title_text),
        strong_hits=strong_hits,
        weak_hits={marker for marker in weak_markers if marker in visible_text or marker in title_text},
        provider_hits={marker for marker in provider_markers if marker in lowered},
        active_provider_hits=_active_provider_hits(lowered),
        challenge_element_hits=set(_challenge_element_hits(analysis.soup, lowered)),
        hard_strong_hits=strong_hits - content_tolerant_strong_markers,
        has_extractable_content=(
            _has_extractable_detail_signals(html, analysis=analysis)
            or _has_extractable_listing_signals(html, analysis=analysis)
        ),
    )


def _normalized_mapping_keys(signature_name: str) -> list[str]:
    return [
        normalized
        for marker in mapping_or_empty(BLOCK_SIGNATURES.get(signature_name)).keys()
        if (normalized := str(marker or "").strip().lower())
    ]


def _active_provider_hits(lowered: str) -> set[str]:
    return {
        marker
        for item in _mapping_sequence(BLOCK_SIGNATURES.get("active_provider_markers"))
        if (marker := str(item.get("marker") or "").strip().lower()) and marker in lowered
    }


def _normalized_signature_strings(signature_name: str) -> list[str]:
    return [
        normalized
        for marker in _string_sequence(BLOCK_SIGNATURES.get(signature_name))
        if (normalized := str(marker or "").strip().lower())
    ]


def _block_title_matches(title_text: str) -> list[str]:
    matches: list[str] = []
    for pattern in _string_sequence(BLOCK_SIGNATURES.get("title_regexes")):
        raw_pattern = str(pattern or "").strip()
        if not raw_pattern:
            continue
        try:
            if re.search(raw_pattern, title_text, re.IGNORECASE):
                matches.append(raw_pattern)
        except re.error as exc:
            logger.warning(
                "Skipping invalid block signature title regex %r: %s",
                raw_pattern,
                exc,
            )
    return matches


def _block_evidence_indicates_block(evidence: _BlockPageEvidence) -> bool:
    return _strong_block_evidence(evidence) or _combined_block_evidence(evidence)


def _strong_block_evidence(evidence: _BlockPageEvidence) -> bool:
    hard_strong_hits = evidence.hard_strong_hits
    strong_hits = evidence.strong_hits
    provider_hits = evidence.provider_hits
    active_provider_hits = evidence.active_provider_hits
    challenge_element_hits = evidence.challenge_element_hits
    title_matches = evidence.title_matches
    return bool(
        len(hard_strong_hits) >= 2
        or (hard_strong_hits and (provider_hits or active_provider_hits or challenge_element_hits or title_matches))
        or "access denied" in strong_hits
        or (
            "just a moment" in strong_hits
            and (
                "cloudflare" in provider_hits
                or "cf-challenge" in provider_hits
                or "cf-browser-verification" in active_provider_hits
            )
        )
    )


def _combined_block_evidence(evidence: _BlockPageEvidence) -> bool:
    return bool(
        (evidence.challenge_element_hits and (evidence.provider_hits or evidence.active_provider_hits))
        or (evidence.title_matches and evidence.challenge_element_hits)
        or (evidence.hard_strong_hits and evidence.weak_hits and evidence.provider_hits)
        or (
            CAPTCHA_MARKER in evidence.strong_hits
            and evidence.provider_hits
            and (not evidence.has_extractable_content or bool(evidence.title_matches))
        )
    )


def _usable_content_overrides_block(
    blocked: bool,
    evidence: _BlockPageEvidence,
) -> bool:
    return bool(
        blocked and evidence.has_extractable_content and not evidence.title_matches and not evidence.hard_strong_hits
    )


def _build_block_page_classification(
    *,
    blocked: bool,
    forced_blocked: bool,
    forced_outcome: str,
    base_evidence: list[str],
    block_evidence: _BlockPageEvidence,
) -> BlockPageClassification:
    evidence = [
        *base_evidence,
        *sorted(f"title:{pattern}" for pattern in block_evidence.title_matches),
        *sorted(f"strong:{marker}" for marker in block_evidence.strong_hits),
        *sorted(f"weak:{marker}" for marker in block_evidence.weak_hits),
        *sorted(f"provider:{marker}" for marker in block_evidence.provider_hits),
        *sorted(f"active_provider:{marker}" for marker in block_evidence.active_provider_hits),
        *sorted(f"challenge_element:{marker}" for marker in block_evidence.challenge_element_hits),
    ]
    outcome = forced_outcome if blocked and forced_blocked else "challenge_page" if blocked else "ok"
    return BlockPageClassification(
        blocked=blocked,
        outcome=outcome,
        evidence=evidence,
        provider_hits=sorted(block_evidence.provider_hits),
        active_provider_hits=sorted(block_evidence.active_provider_hits),
        strong_hits=sorted(block_evidence.strong_hits),
        weak_hits=sorted(block_evidence.weak_hits),
        title_matches=block_evidence.title_matches,
        challenge_element_hits=sorted(block_evidence.challenge_element_hits),
    )


def _http_content_is_extractable(
    html: str,
    *,
    analysis: HtmlAnalysis | None = None,
) -> bool:
    parsed = analysis or analyze_html(html)
    return _has_extractable_detail_signals(
        html,
        analysis=parsed,
    ) or _has_extractable_listing_signals(
        html,
        analysis=parsed,
    )


def _content_aware_http_blocked(
    headers: Any,
    html: str,
    status_code: int,
) -> bool:
    analysis = analyze_html(html)
    blocked_page = classify_blocked_page(
        html,
        status_code,
        analysis=analysis,
    )
    if blocked_page.blocked:
        return True
    if not classify_block_from_headers(headers):
        return False
    return not _http_content_is_extractable(
        html,
        analysis=analysis,
    )


def should_escalate_to_browser(
    result: PageFetchResult,
    *,
    surface: str | None = None,
    runtime_policy: Mapping[str, Any] | None = None,
) -> bool:
    non_retryable_http_status = is_non_retryable_http_status(result.status_code)
    if result.blocked or is_retryable_http_status(result.status_code):
        return True
    if non_retryable_http_status:
        return False
    resolved_policy = (
        runtime_policy
        if runtime_policy is not None
        else resolve_platform_runtime_policy(
            result.final_url or result.url,
            result.html,
            surface=surface,
        )
    )
    escalation_policy = resolved_policy.get("http_browser_escalation")
    if not isinstance(escalation_policy, Mapping):
        escalation_policy = {}
    analysis = analyze_html(result.html)
    has_detail_signals = _has_extractable_detail_signals(result.html, analysis=analysis)
    has_listing_signals = _has_extractable_listing_signals(result.html, analysis=analysis)
    if (
        bool(escalation_policy.get("js_shell_without_detail_signals", True))
        and _looks_like_js_shell(result.html, analysis=analysis)
        and not has_detail_signals
    ):
        return True
    if (
        bool(escalation_policy.get("listing_shell_without_listing_signals"))
        and not has_listing_signals
        and _looks_like_listing_shell(result, analysis=analysis)
    ):
        return True
    if bool(escalation_policy.get("missing_detail_signals")) and not has_detail_signals:
        return True
    return False


async def is_blocked_html_async(html: str, status_code: int) -> bool:
    return await asyncio.to_thread(is_blocked_html, html, status_code)


async def classify_blocked_page_async(
    html: str,
    status_code: int,
) -> BlockPageClassification:
    return await asyncio.to_thread(classify_blocked_page, html, status_code)


async def should_escalate_to_browser_async(
    result: PageFetchResult,
    *,
    surface: str | None = None,
    runtime_policy: Mapping[str, Any] | None = None,
) -> bool:
    return await asyncio.to_thread(
        should_escalate_to_browser,
        result,
        surface=surface,
        runtime_policy=runtime_policy,
    )


async def get_shared_http_client(
    *,
    proxy: str | None = None,
) -> httpx.AsyncClient:
    family_preference = address_family_preference()
    key = (str(proxy or "").strip() or None, family_preference)
    client = _SHARED_HTTP_CLIENTS.get(key)
    if client is not None and not client.is_closed:
        return client
    async with _SHARED_HTTP_CLIENT_LOCK:
        client = _SHARED_HTTP_CLIENTS.get(key)
        if client is None or client.is_closed:
            client = build_async_http_client(
                follow_redirects=True,
                timeout=crawler_runtime_settings.http_timeout_seconds,
                limits=httpx.Limits(
                    max_connections=settings.http_max_connections,
                    max_keepalive_connections=settings.http_max_keepalive_connections,
                ),
                proxy=key[0],
            )
            _SHARED_HTTP_CLIENTS[key] = client
        return client


async def close_shared_http_client() -> None:
    async with _SHARED_HTTP_CLIENT_LOCK:
        clients = list(_SHARED_HTTP_CLIENTS.values())
        _SHARED_HTTP_CLIENTS.clear()
    for client in clients:
        if client is not None and not client.is_closed:
            await client.aclose()


def _clear_shared_clients_for_testing() -> None:
    _SHARED_HTTP_CLIENTS.clear()


async def http_fetch(
    url: str,
    timeout_seconds: float,
    *,
    proxy: str | None = None,
    get_client=get_shared_http_client,
    client_builder=None,
    blocked_html_checker=is_blocked_html_async,
) -> PageFetchResult:
    if client_builder is not None:
        get_client = client_builder
    client = await get_client(proxy=proxy)
    response = await client.get(url, timeout=timeout_seconds)
    html = response.text or ""
    headers = copy_headers(response.headers)
    blocked_result = blocked_html_checker(html, response.status_code)
    if inspect.isawaitable(blocked_result):
        blocked_result = await blocked_result
    blocked = bool(blocked_result) or _content_aware_http_blocked(
        headers,
        html,
        response.status_code,
    )
    runtime_policy = resolve_platform_runtime_policy(str(response.url), html)
    return PageFetchResult(
        url=url,
        final_url=str(response.url),
        html=html,
        status_code=response.status_code,
        method="httpx",
        content_type=response.headers.get("content-type", HTML_CONTENT_TYPE),
        blocked=blocked,
        platform_family=runtime_policy.get("family"),
        headers=headers,
    )


async def curl_fetch(
    url: str,
    timeout_seconds: float,
    *,
    proxy: str | None = None,
    cookie_header: str | None = None,
) -> PageFetchResult:
    return await asyncio.to_thread(
        _curl_fetch_sync,
        url,
        timeout_seconds,
        proxy=proxy,
        cookie_header=cookie_header,
    )


def copy_headers(headers: Any) -> httpx.Headers:
    if isinstance(headers, httpx.Headers):
        return httpx.Headers(list(headers.multi_items()))
    if hasattr(headers, "multi_items"):
        return httpx.Headers(list(headers.multi_items()))
    if isinstance(headers, dict):
        return httpx.Headers(headers)
    return httpx.Headers(list(getattr(headers, "items", lambda: [])()))


def _curl_fetch_sync(
    url: str,
    timeout_seconds: float,
    *,
    proxy: str | None = None,
    cookie_header: str | None = None,
) -> PageFetchResult:
    from curl_cffi import requests as curl_requests

    raw_impersonate_target = str(
        ""
        if crawler_runtime_settings.curl_impersonate_target is None
        else crawler_runtime_settings.curl_impersonate_target
    ).strip()
    impersonate_target = cast(Any, raw_impersonate_target or None)
    request_headers = default_request_headers()
    normalized_cookie_header = str(cookie_header or "").strip()
    if normalized_cookie_header:
        request_headers["Cookie"] = normalized_cookie_header
    response = curl_requests.get(
        url,
        impersonate=impersonate_target,
        allow_redirects=True,
        timeout=timeout_seconds,
        proxy=proxy,
        headers=request_headers,
    )
    html = response.text or ""
    response_headers = copy_headers(response.headers)
    blocked = _content_aware_http_blocked(
        response_headers,
        html,
        response.status_code,
    )
    runtime_policy = resolve_platform_runtime_policy(str(response.url), html)
    return PageFetchResult(
        url=url,
        final_url=str(response.url),
        html=html,
        status_code=response.status_code,
        method="curl_cffi",
        content_type=response.headers.get("content-type", HTML_CONTENT_TYPE),
        blocked=blocked,
        platform_family=runtime_policy.get("family"),
        headers=response_headers,
    )


def _mapping_sequence(value: object) -> list[dict[object, object]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _string_sequence(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


__all__ = [
    "BlockPageClassification",
    "NetworkPayloadReadResult",
    "classify_block_from_headers",
    "classify_blocked_page",
    "classify_blocked_page_async",
    "PageFetchResult",
    "close_shared_http_client",
    "copy_headers",
    "curl_fetch",
    "get_shared_http_client",
    "http_fetch",
    "is_blocked_html",
    "is_blocked_html_async",
    "is_non_retryable_http_status",
    "is_retryable_http_status",
    "has_extractable_dom_content_detail_signals",
    "has_extractable_listing_signals",
    "should_escalate_to_browser",
    "should_escalate_to_browser_async",
]

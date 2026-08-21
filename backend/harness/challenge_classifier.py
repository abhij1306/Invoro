from __future__ import annotations

from ._support_shared import *  # noqa: F403
from .record_signals import (
    _identity_overlap_count,
    _identity_path,
    _identity_tokens,
    _looks_like_utility_record,
    _object_dict,
    _object_list,
    _primary_identity_tokens,
    _required_identity_overlap,
    _safe_int,
)
from .site_sets import unavailable_configured_adapters


def classify_failure_mode(result: dict[str, object]) -> str:
    diagnostics = _object_dict(result.get("browser_diagnostics"))
    for classifier in (
        _successful_content_mode,
        _runtime_failure_mode,
        _verdict_failure_mode,
        _adapter_failure_mode,
    ):
        failure_mode = classifier(result, diagnostics)
        if failure_mode:
            return failure_mode
    return "unknown_failure"


def _successful_content_mode(
    result: dict[str, object], diagnostics: dict[str, object]
) -> str | None:
    verdict = str(result.get("verdict") or "").strip().lower()
    if verdict not in _SUCCESS_VERDICTS:
        return None
    if _looks_like_detail_identity_mismatch(result):
        return "detail_identity_mismatch"
    if not _looks_like_placeholder_or_wrong_content(result, diagnostics):
        return "success"
    return None


def _runtime_failure_mode(
    result: dict[str, object], diagnostics: dict[str, object]
) -> str | None:
    error_text = str(result.get("error") or "").lower()
    browser_outcome = str(diagnostics.get("browser_outcome") or "").strip().lower()
    failure_kind = str(diagnostics.get("failure_kind") or "").strip().lower()
    status_code = _safe_int(result.get("status_code"))
    if diagnostics.get("networkidle_timed_out"):
        return "spa_readiness_timeout"
    if browser_outcome == "low_content_shell" and status_code in {404, 410}:
        return "spa_shell_404"
    if browser_outcome == "low_content_shell":
        return "spa_shell_low_content"
    if failure_kind in {"unsupported_proxy", "proxy_error"}:
        return "proxy_failure"
    if failure_kind == "engine_unavailable":
        return "engine_failure"
    if "timeout" in error_text:
        return "timeout"
    if "getaddrinfo failed" in error_text:
        return "dns_or_network_failure"
    if "chrome-error://chromewebdata/" in error_text:
        return "browser_navigation_failure"
    return None


def _verdict_failure_mode(
    result: dict[str, object], diagnostics: dict[str, object]
) -> str | None:
    verdict = str(result.get("verdict") or "").strip().lower()
    if verdict == "blocked":
        return "blocked"
    if (
        result.get("blocked")
        or _diagnostics_indicate_challenge(diagnostics)
        or _diagnostics_contain_strong_challenge_evidence(diagnostics)
    ):
        return "blocked"
    if verdict == "listing_detection_failed":
        return "listing_extraction_empty"
    if verdict == "empty":
        return "detail_extraction_empty"
    if verdict == "error":
        return "error"
    if _looks_like_placeholder_or_wrong_content(result, diagnostics):
        return "wrong_content_or_placeholder"
    return None


def _adapter_failure_mode(
    result: dict[str, object], diagnostics: dict[str, object]
) -> str | None:
    del diagnostics
    family = str(result.get("platform_family") or "").strip().lower()
    platform_config = platform_config_for_family(family) if family else None
    expected_adapters = {
        str(name).strip().lower()
        for name in (
            platform_config.adapter_names if platform_config is not None else []
        )
        if str(name or "").strip()
    }
    missing_registrations = unavailable_configured_adapters()
    if expected_adapters and expected_adapters.issubset(missing_registrations):
        return "adapter_not_registered"
    if expected_adapters and not result.get("adapter_name"):
        return "adapter_not_matched"
    if (
        family
        and not expected_adapters
        and str(result.get("surface") or "").startswith("job_")
    ):
        return "platform_family_without_adapter"
    if _safe_int(result.get("records")) == 0:
        return (
            "listing_extraction_empty"
            if str(result.get("surface") or "").endswith("_listing")
            else "detail_extraction_empty"
        )
    return None


def _diagnostics_indicate_challenge(diagnostics: dict[str, object]) -> bool:
    return diagnostics_indicate_block(diagnostics)


def _diagnostics_contain_strong_challenge_evidence(
    diagnostics: dict[str, object],
) -> bool:
    evidence = [
        str(item or "").strip().lower()
        for item in _object_list(diagnostics.get("challenge_evidence"))
        if str(item or "").strip()
    ]
    if any(
        item.startswith(("strong:", "title:", "active_provider:", "challenge_element:"))
        for item in evidence
    ):
        return True
    return bool(diagnostics.get("challenge_element_hits")) and bool(
        diagnostics.get("challenge_provider_hits")
    )


def _challenge_summary_from_diagnostics(
    diagnostics: dict[str, object],
) -> dict[str, object] | None:
    if not _diagnostics_indicate_challenge(diagnostics):
        return None
    provider_hits = [
        str(item or "").strip()
        for item in _object_list(diagnostics.get("challenge_provider_hits"))
        if str(item or "").strip()
    ]
    element_hits = [
        str(item or "").strip()
        for item in _object_list(diagnostics.get("challenge_element_hits"))
        if str(item or "").strip()
    ]
    evidence = [
        str(item or "").strip()
        for item in _object_list(diagnostics.get("challenge_evidence"))
        if str(item or "").strip()
    ]
    summary: dict[str, object] = {
        "browser_outcome": str(diagnostics.get("browser_outcome") or "").strip().lower()
        or None,
        "provider": provider_hits[0].lower() if provider_hits else None,
        "providers": [item.lower() for item in provider_hits],
        "elements": element_hits,
        "evidence": evidence[:5],
    }
    return summary


def _looks_like_placeholder_or_wrong_content(
    result: dict[str, object], diagnostics: dict[str, object]
) -> bool:
    sample_title = str(result.get("sample_title") or "").strip()
    return (
        str(diagnostics.get("browser_outcome") or "").strip().lower()
        == "low_content_shell"
        or (
            _safe_int(result.get("records")) > 0
            and not sample_title
            and _safe_int(result.get("populated_fields")) <= 1
        )
        or _looks_like_placeholder_title(
            sample_title, populated_fields=_safe_int(result.get("populated_fields"))
        )
    )


def _looks_like_utility_chrome_success(result: dict[str, object]) -> bool:
    sample_records = result.get("sample_records")
    if isinstance(sample_records, list):
        for row in sample_records[:2]:
            if not isinstance(row, dict):
                continue
            if _looks_like_utility_record(
                title=row.get("title"),
                url=row.get("url"),
            ):
                return True
    if bool(result.get("sample_looks_like_utility_chrome")):
        return True
    return _looks_like_utility_record(
        title=result.get("sample_title"),
        url=result.get("sample_url"),
    )


def _looks_like_detail_identity_mismatch(result: dict[str, object]) -> bool:
    surface = str(result.get("surface") or "").strip().lower()
    if not surface.endswith("_detail"):
        return False
    requested_url = str(result.get("requested_url") or "").strip()
    if not requested_url:
        return False
    sample_url = str(result.get("sample_url") or "").strip()
    if not sample_url:
        return False
    sample_path = _identity_path(sample_url)
    requested_path = _identity_path(requested_url)
    if sample_path in {"", "/"} and requested_path not in {"", "/"}:
        return True
    requested_tokens = _primary_identity_tokens(requested_url)
    if len(requested_tokens) < 2:
        return False
    sample_url_tokens = _primary_identity_tokens(sample_url)
    sample_title = " ".join(
        str(result.get("sample_title") or "").strip().lower().split()
    )
    sample_title_tokens = _identity_tokens(sample_title)
    overlap = max(
        _identity_overlap_count(requested_tokens, sample_url_tokens),
        _identity_overlap_count(requested_tokens, sample_title_tokens),
    )
    required_overlap = _required_identity_overlap(len(requested_tokens))
    if sample_title in _GENERIC_DETAIL_SECTION_TITLES and overlap < required_overlap:
        return True
    return bool(
        (sample_url_tokens or sample_title_tokens) and overlap < required_overlap
    )


def _looks_like_placeholder_title(title: str, *, populated_fields: int) -> bool:
    normalized = " ".join(str(title or "").strip().lower().split())
    if "can't be found" in normalized or normalized.startswith("oops!"):
        return populated_fields <= 6
    if normalized not in _PLACEHOLDER_TITLES:
        return False
    return populated_fields <= 2


def _looks_like_site_shell_success(result: dict[str, object]) -> bool:
    surface = str(result.get("surface") or "").strip().lower()
    if not surface.endswith("_detail"):
        return False
    sample_title = " ".join(
        str(result.get("sample_title") or "").strip().lower().split()
    )
    if not sample_title:
        return True
    semantics = _object_dict(result.get("sample_semantics"))
    if (
        bool(semantics.get("price_present"))
        or _safe_int(semantics.get("variant_count")) >= 2
    ):
        return False
    title_tokens = {
        token for token in re.split(r"[^a-z0-9]+", sample_title) if len(token) >= 3
    }
    host = (
        str(
            urlsplit(
                str(result.get("requested_url") or result.get("url") or "")
            ).hostname
            or ""
        )
        .strip()
        .lower()
    )
    host_tokens = {
        token
        for token in re.split(r"[^a-z0-9]+", host.removeprefix("www."))
        if len(token) >= 3
    }
    return bool(
        host_tokens
        and host_tokens & title_tokens
        and _safe_int(result.get("populated_fields")) <= 6
    )


def _looks_like_promo_or_wrong_page(result: dict[str, object]) -> bool:
    sample_title = " ".join(
        str(result.get("sample_title") or "").strip().lower().split()
    )
    sample_url = str(result.get("sample_url") or "").strip().lower()
    promo_tokens = (
        "promo",
        "new arrivals",
        "sale",
        "shop all",
        "category",
        "categories",
    )
    return any(token in sample_title for token in promo_tokens) or any(
        token in sample_url
        for token in ("/promo", "promo-", "products=newarrival", "/sale", "/category")
    )


__all__ = tuple(name for name in globals() if not name.startswith("__"))

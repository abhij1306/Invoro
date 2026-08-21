from __future__ import annotations

from ._core_shared import *  # noqa: F403
from .baseline import _coalesce, _country_code_from_value, _locale_region, _timezone_matches_country
from .runtime_source import _int_list, _normalize_space
from .signal_extractor import _dedupe, _extract_versions, _looks_like_truthy_risk, _percent_value


def _target_identity_mismatch(
    *,
    locale: str,
    timezone_name: str,
    geo_country_code: str | None,
) -> dict[str, object]:
    locale_region = _locale_region(locale)
    timezone_match = _timezone_matches_country(timezone_name, geo_country_code)
    return {
        "geo_country_code": geo_country_code,
        "locale_region": locale_region,
        "locale_country_match": (
            locale_region == geo_country_code
            if locale_region and geo_country_code
            else None
        ),
        "timezone_country_match": timezone_match,
    }

def _target_path_state(diagnostic: dict[str, object]) -> dict[str, object]:
    transport = [
        _object_dict(diagnostic.get("httpx")),
        _object_dict(diagnostic.get("curl_cffi")),
    ]
    browser = _object_dict(diagnostic.get("browser"))
    return {
        "transport": transport,
        "browser": browser,
        "transport_blocked": [
            payload
            for payload in transport
            if payload.get("status") == "ok" and bool(payload.get("blocked"))
        ],
        "transport_ok": [
            payload
            for payload in transport
            if payload.get("status") == "ok" and not bool(payload.get("blocked"))
        ],
        "browser_blocked": (
            browser.get("status") == "ok" and bool(browser.get("blocked"))
        ),
        "browser_ok": (
            browser.get("status") == "ok" and not bool(browser.get("blocked"))
        ),
        "browser_classification": _object_dict(browser.get("classification")),
    }


def _target_vendor(state: dict[str, object]) -> object:
    browser = _object_dict(state.get("browser"))
    browser_classification = _object_dict(state.get("browser_classification"))
    transport = [_object_dict(item) for item in _object_list(state.get("transport"))]
    return (
        browser_classification.get("header_vendor")
        or _coalesce(
            [
                _object_dict(payload.get("classification")).get("header_vendor")
                for payload in transport
            ]
        )
        or _coalesce(
            [
                _coalesce(
                    _object_list(
                        _object_dict(payload.get("classification")).get("provider_hits")
                    )
                )
                for payload in [browser, *transport]
            ]
        )
    )


def _target_root_cause(
    *,
    consensus: dict[str, object],
    diagnostic: dict[str, object],
) -> dict[str, object]:
    geo = _object_dict(_object_dict(diagnostic.get("geo")).get("consensus"))
    mismatch = _target_identity_mismatch(
        locale=str(consensus.get("locale") or ""),
        timezone_name=str(consensus.get("timezone") or ""),
        geo_country_code=_country_code_from_value(str(geo.get("country") or "")),
    )
    state = _target_path_state(diagnostic)
    transport = [_object_dict(item) for item in _object_list(state["transport"])]
    browser = _object_dict(state["browser"])
    browser_classification = _object_dict(state["browser_classification"])
    vendor = _target_vendor(state)

    if state["transport_blocked"] and state["browser_blocked"]:
        return {
            "category": "target_precontent_block",
            "confidence": "high",
            "message": "HTTP and browser paths both blocked before usable content.",
            "evidence": {
                "vendor": vendor,
                "geo_identity": mismatch,
                "httpx": {
                    "status_code": transport[0].get("status_code"),
                    "outcome": _object_dict(
                        transport[0].get("classification")
                    ).get("outcome"),
                },
                "curl_cffi": {
                    "status_code": transport[1].get("status_code"),
                    "outcome": _object_dict(
                        transport[1].get("classification")
                    ).get("outcome"),
                },
                "browser": {
                    "status_code": browser.get("status_code"),
                    "outcome": browser_classification.get("outcome"),
                    "challenge_cookie_names": browser.get("challenge_cookie_names"),
                },
            },
        }
    if state["browser_blocked"] and state["transport_ok"]:
        geo_mismatch = (
            mismatch.get("timezone_country_match") is False
            or mismatch.get("locale_country_match") is False
        )
        if geo_mismatch:
            return {
                "category": "browser_geo_identity_mismatch",
                "confidence": "high",
                "message": "Browser path blocked while transport passes and browser geo identity drifts from observed egress country.",
                "evidence": {
                    "geo_identity": mismatch,
                    "browser": {
                        "status_code": browser.get("status_code"),
                        "outcome": browser_classification.get("outcome"),
                    },
                },
            }
        return {
            "category": "browser_session_or_fingerprint_block",
            "confidence": "high",
            "message": "Browser path blocked while transport passes; failure is browser session or browser-only fingerprint flow.",
            "evidence": {
                "vendor": vendor,
                "browser": {
                    "status_code": browser.get("status_code"),
                    "outcome": browser_classification.get("outcome"),
                    "challenge_cookie_names": browser.get("challenge_cookie_names"),
                },
            },
        }
    if state["browser_ok"] and state["transport_blocked"]:
        return {
            "category": "transport_only_block",
            "confidence": "high",
            "message": "Transport paths blocked while browser path stays usable.",
            "evidence": {
                "vendor": vendor,
                "httpx_status_code": transport[0].get("status_code"),
                "curl_status_code": transport[1].get("status_code"),
            },
        }
    if state["browser_ok"] or state["transport_ok"]:
        return {
            "category": "no_target_block_detected",
            "confidence": "high",
            "message": "At least one acquisition path reached usable content.",
            "evidence": {"geo_identity": mismatch},
        }
    return {
        "category": "target_diagnostic_inconclusive",
        "confidence": "low",
        "message": "Target diagnostics did not produce enough successful paths to classify the failure mechanically.",
        "evidence": {
            "geo_identity": mismatch,
            "browser_status": browser.get("status"),
            "httpx_status": transport[0].get("status"),
            "curl_status": transport[1].get("status"),
        },
    }
def _finding(
    severity: str,
    category: str,
    message: str,
    evidence: object,
) -> dict[str, object]:
    return {
        "severity": severity,
        "category": category,
        "message": message,
        "evidence": evidence,
    }


def _probe_status_findings(
    sites: dict[str, object],
) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    statuses = {
        status: [
            site_id
            for site_id, payload in sites.items()
            if _object_dict(payload).get("site_status") == status
        ]
        for status in ("failed", "degraded")
    }
    if statuses["failed"]:
        findings.append(
            _finding(
                "warn",
                "probe_site_failure",
                "One or more browser surface probe sites failed; report is partial.",
                statuses["failed"],
            )
        )
    if statuses["degraded"]:
        findings.append(
            _finding(
                "warn",
                "probe_site_degraded",
                "One or more browser surface probe extractors saw unexpected page structure.",
                statuses["degraded"],
            )
        )
    return findings


def _observed_geo_country(target_diagnostics: list[object]) -> str | None:
    for diagnostic in target_diagnostics:
        geo = _object_dict(
            _object_dict(_object_dict(diagnostic).get("geo")).get("consensus")
        )
        country = _country_code_from_value(str(geo.get("country") or ""))
        if country:
            return country
    return None


def _geo_findings(
    *,
    consensus: dict[str, object],
    pixelscan: dict[str, object],
    target_diagnostics: list[object],
) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    pixelscan_country = _coalesce(
        _string_list(_object_dict(pixelscan.get("extracted")).get("country_values"))
    )
    country_code = _country_code_from_value(str(pixelscan_country or ""))
    observed_country = _observed_geo_country(target_diagnostics)
    provider_drift = bool(
        country_code and observed_country and country_code != observed_country
    )
    if provider_drift:
        findings.append(
            _finding(
                "warn",
                "proxy_geo_provider_drift",
                (
                    f"Pixelscan geolocates the same exit IP as {country_code} "
                    f"while direct geo endpoints report {observed_country}."
                ),
                {
                    "pixelscan_country": pixelscan_country,
                    "observed_geo_country": observed_country,
                },
            )
        )
    timezone_value = str(consensus.get("timezone") or "")
    if (
        _timezone_matches_country(timezone_value, country_code) is False
        and not provider_drift
    ):
        findings.append(
            _finding(
                "fail",
                "timezone_country_mismatch",
                f"Timezone {timezone_value or 'unknown'} does not match Pixelscan country {pixelscan_country or 'unknown'}.",
                {"timezone": timezone_value, "pixelscan_country": pixelscan_country},
            )
        )
    locale_region = _locale_region(str(consensus.get("locale") or ""))
    if locale_region and country_code and locale_region != country_code and not provider_drift:
        findings.append(
            _finding(
                "warn",
                "locale_region_drift",
                f"Locale region {locale_region} drifts from Pixelscan country {country_code}.",
                {"locale": consensus.get("locale"), "country": pixelscan_country},
            )
        )
    return findings


def _version_findings(
    consensus: dict[str, object], sites: dict[str, object]
) -> list[dict[str, object]]:
    baseline_versions = _extract_versions([str(consensus.get("user_agent") or "")])
    extracted_versions = sorted(
        {
            version
            for site in sites.values()
            for version in _int_list(
                _object_dict(_object_dict(site).get("extracted")).get(
                    "signal_versions"
                )
            )
        }
    )
    if not baseline_versions or not extracted_versions:
        return []
    if all(version in baseline_versions for version in extracted_versions):
        return []
    return [
        _finding(
            "fail",
            "ua_version_drift",
            "Reported browser versions drift across baseline and public checkers.",
            {
                "baseline_versions": baseline_versions,
                "extracted_versions": extracted_versions,
            },
        )
    ]


def _webdriver_findings(
    consensus: dict[str, object],
    sannysoft: dict[str, object],
    creepjs: dict[str, object],
) -> list[dict[str, object]]:
    evidence = (
        ["baseline.navigator.webdriver=true"]
        if bool(consensus.get("webdriver"))
        else []
    )
    evidence.extend(
        _string_list(_object_dict(sannysoft.get("extracted")).get("webdriver_hits"))
    )
    keyword_hits = _object_dict(
        _object_dict(creepjs.get("extracted")).get("keyword_hits")
    )
    evidence.extend(_string_list(keyword_hits.get("webdriver")))
    evidence = [value for value in evidence if _looks_like_truthy_risk(value)]
    if not evidence:
        return []
    return [
        _finding(
            "fail",
            "webdriver_exposure",
            "Public checks still see webdriver or automation signals.",
            evidence[:10],
        )
    ]


def _headless_findings(creepjs: dict[str, object]) -> list[dict[str, object]]:
    extracted = _object_dict(creepjs.get("extracted"))
    evidence = _string_list(extracted.get("headless_hits"))
    evidence.extend(
        _string_list(_object_dict(extracted.get("keyword_hits")).get("headless"))
    )
    risky: list[str] = []
    for value in evidence:
        normalized = _normalize_space(value).lower()
        percent = _percent_value(value) if " like headless" in normalized else None
        if percent is not None and percent < 10:
            continue
        if _looks_like_truthy_risk(value):
            risky.append(value)
    if not risky:
        return []
    return [
        _finding(
            "fail",
            "headless_leakage",
            "Headless or stealth leakage is visible in public checks.",
            risky[:10],
        )
    ]


def _webrtc_findings(consensus: dict[str, object]) -> list[dict[str, object]]:
    public_ips: list[str] = []
    private_ips: list[str] = []
    for value in _object_list(consensus.get("webrtc_ips")):
        text = str(value)
        if not _normalize_space(text):
            continue
        try:
            parsed = ip_address(text)
        except ValueError:
            continue
        if parsed.is_loopback:
            continue
        (private_ips if parsed.is_private else public_ips).append(text)
    if public_ips:
        return [
            _finding(
                "fail",
                "webrtc_leakage",
                "WebRTC exposed public IPs from the page context.",
                public_ips,
            )
        ]
    if private_ips:
        return [
            _finding(
                "warn",
                "webrtc_private_ip_visibility",
                "WebRTC exposed private-network IPs from the page context.",
                private_ips,
            )
        ]
    return []


def _runtime_drift_findings(
    *,
    metadata: dict[str, object],
    consensus: dict[str, object],
    drift: dict[str, object],
) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    if "screen" in drift or "viewport" in drift:
        findings.append(
            _finding(
                "fail",
                "screen_viewport_drift",
                "Screen or viewport values changed across the three checker sites.",
                {"screen": drift.get("screen"), "viewport": drift.get("viewport")},
            )
        )
    automation_globals = [
        value
        for value in _string_list(consensus.get("automation_globals"))
        if value != "chrome.runtime.typeof=object"
    ]
    if automation_globals:
        findings.append(
            _finding(
                "fail",
                "automation_globals_exposure",
                "Automation framework globals are visible in the page context.",
                automation_globals[:10],
            )
        )
    iframe_leak = _object_dict(consensus.get("iframe_leak"))
    if iframe_leak.get("content_window_array_leak") is True:
        findings.append(
            _finding(
                "fail",
                "iframe_content_window_leak",
                "Iframe contentWindow array leak detected (automation marker).",
                iframe_leak,
            )
        )
    drift_specs = (
        ("canvas", "canvas_fingerprint_drift", "Canvas fingerprint values differ across probe sites."),
        ("audio", "audio_fingerprint_drift", "AudioContext fingerprint values differ across probe sites."),
    )
    for key, category, message in drift_specs:
        if key in drift:
            findings.append(_finding("warn", category, message, drift.get(key)))
    behavioral = _object_dict(consensus.get("behavioral_smoke"))
    if behavioral and (
        behavioral.get("mouse_isTrusted") is False
        or behavioral.get("click_isTrusted") is False
    ):
        findings.append(
            _finding(
                "warn",
                "synthetic_event_detection",
                "Playwright input did not produce trusted DOM events.",
                behavioral,
            )
        )
    if str(metadata.get("browser_engine") or "").strip().lower() == "chromium":
        findings.append(
            _finding(
                "info",
                "chromium_ja3_limitation",
                "Chromium engine still uses a Playwright Chromium TLS fingerprint; use real_chrome for native Chrome JA3 parity.",
                {"browser_engine": metadata.get("browser_engine")},
            )
        )
    return findings


def _cross_site_location_findings(
    sites: dict[str, object],
) -> list[dict[str, object]]:
    site_ips: list[str] = []
    site_countries: list[str] = []
    for payload in sites.values():
        extracted = _object_dict(_object_dict(payload).get("extracted"))
        site_ips.extend(_string_list(extracted.get("ip_values")))
        site_countries.extend(_string_list(extracted.get("country_values")))
    public_ips: set[str] = set()
    for value in site_ips:
        try:
            parsed = ip_address(value)
        except ValueError:
            continue
        if not (parsed.is_loopback or parsed.is_private or parsed.is_unspecified):
            public_ips.add(value)
    country_codes = {
        code
        for value in site_countries
        if (code := _country_code_from_value(value))
    }
    findings: list[dict[str, object]] = []
    if len(public_ips) > 1:
        findings.append(
            _finding(
                "warn",
                "cross_site_ip_drift",
                "Different public IPs were reported inside the same fingerprint run.",
                sorted(public_ips),
            )
        )
    if len(country_codes) > 1:
        findings.append(
            _finding(
                "warn",
                "cross_site_country_drift",
                "Different countries were reported inside the same fingerprint run.",
                _dedupe(site_countries),
            )
        )
    return findings


def _target_findings(
    consensus: dict[str, object], diagnostics: list[object]
) -> list[dict[str, object]]:
    findings: list[dict[str, object]] = []
    severity_by_category = {
        "target_precontent_block": "fail",
        "browser_geo_identity_mismatch": "fail",
        "browser_session_or_fingerprint_block": "fail",
        "transport_only_block": "warn",
        "target_diagnostic_inconclusive": "warn",
    }
    for diagnostic in diagnostics:
        payload = _object_dict(diagnostic)
        root_cause = _target_root_cause(consensus=consensus, diagnostic=payload)
        category = str(root_cause.get("category") or "")
        findings.append(
            _finding(
                severity_by_category.get(category, "info"),
                category,
                f"{str(payload.get('url') or 'target')}: {root_cause.get('message')}",
                root_cause.get("evidence"),
            )
        )
    return findings


def build_findings(report: dict[str, object]) -> list[dict[str, object]]:
    metadata = _object_dict(report.get("metadata"))
    baseline = _object_dict(report.get("baseline"))
    consensus = _object_dict(baseline.get("consensus"))
    drift = _object_dict(baseline.get("drift"))
    sites = _object_dict(report.get("sites"))
    diagnostics = _object_list(report.get("target_diagnostics"))
    pixelscan = _object_dict(sites.get("pixelscan"))
    sannysoft = _object_dict(sites.get("sannysoft"))
    creepjs = _object_dict(sites.get("creepjs"))

    findings = _probe_status_findings(sites)
    findings.extend(
        _geo_findings(
            consensus=consensus,
            pixelscan=pixelscan,
            target_diagnostics=diagnostics,
        )
    )
    findings.extend(_version_findings(consensus, sites))
    findings.extend(_webdriver_findings(consensus, sannysoft, creepjs))
    findings.extend(_headless_findings(creepjs))
    findings.extend(_webrtc_findings(consensus))
    findings.extend(
        _runtime_drift_findings(
            metadata=metadata,
            consensus=consensus,
            drift=drift,
        )
    )
    findings.extend(_cross_site_location_findings(sites))
    findings.extend(_target_findings(consensus, diagnostics))
    if findings:
        return findings
    return [
        _finding(
            "info",
            "no_risky_drift_detected",
            "No risky fingerprint drift was detected by current rules.",
            [],
        )
    ]
__all__ = tuple(
    name for name in globals() if not name.startswith("__")
)

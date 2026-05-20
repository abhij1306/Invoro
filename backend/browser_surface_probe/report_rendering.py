from __future__ import annotations

import re

_BROWSER_VERSION_RE = re.compile(
    r"(?:Chrome|Chromium|Edg|Firefox|Version)/(\d{2,3})", re.IGNORECASE
)


def _object_dict(value: object) -> dict[str, object]:
    return value if isinstance(value, dict) else {}


def _object_list(value: object) -> list[object]:
    return value if isinstance(value, list) else []


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item)]


def _ua_major(user_agent: object) -> int | None:
    match = _BROWSER_VERSION_RE.search(str(user_agent or ""))
    if match is None:
        return None
    try:
        return int(match.group(1))
    except ValueError:
        return None


def _build_agent_summary(report: dict[str, object]) -> dict[str, object]:
    metadata = _object_dict(report.get("metadata"))
    baseline = _object_dict(report.get("baseline"))
    consensus = _object_dict(baseline.get("consensus"))
    findings = _object_list(report.get("findings"))
    sites = _object_dict(report.get("sites"))
    target_diagnostics = _object_list(report.get("target_diagnostics"))
    severity_counts: dict[str, int] = {"fail": 0, "warn": 0, "info": 0}
    normalized_findings = [
        _object_dict(finding) for finding in findings if isinstance(finding, dict)
    ]
    for finding in normalized_findings:
        severity = str(finding.get("severity") or "").strip().lower()
        if severity in severity_counts:
            severity_counts[severity] += 1
    site_rows: list[dict[str, object]] = []
    for site_id, raw_site_payload in sorted(sites.items()):
        site_payload = _object_dict(raw_site_payload)
        snapshot_summary = _object_dict(site_payload.get("snapshot_summary"))
        site_rows.append(
            {
                "site_id": site_id,
                "label": site_payload.get("label"),
                "status": site_payload.get("site_status"),
                "attempts": site_payload.get("attempts"),
                "line_count": snapshot_summary.get("line_count"),
                "line_count_raw": snapshot_summary.get("line_count_raw"),
                "row_count": snapshot_summary.get("row_count"),
                "row_count_raw": snapshot_summary.get("row_count_raw"),
                "validation_warnings": _object_list(
                    site_payload.get("validation_warnings")
                ),
                "final_url": site_payload.get("final_url") or site_payload.get("url"),
                "error": site_payload.get("error"),
            }
        )
    target_rows: list[dict[str, object]] = []
    for raw_payload in target_diagnostics:
        if not isinstance(raw_payload, dict):
            continue
        payload = _object_dict(raw_payload)
        root_cause = _object_dict(payload.get("root_cause"))
        browser = _object_dict(payload.get("browser"))
        httpx_payload = _object_dict(payload.get("httpx"))
        curl_payload = _object_dict(payload.get("curl_cffi"))
        target_rows.append(
            {
                "url": payload.get("url"),
                "host": payload.get("host"),
                "root_cause_category": root_cause.get("category"),
                "root_cause_confidence": root_cause.get("confidence"),
                "browser_status": browser.get("status"),
                "browser_blocked": browser.get("blocked"),
                "httpx_status": httpx_payload.get("status"),
                "httpx_blocked": httpx_payload.get("blocked"),
                "curl_status": curl_payload.get("status"),
                "curl_blocked": curl_payload.get("blocked"),
            }
        )
    return {
        "generated_at": metadata.get("generated_at"),
        "engine": metadata.get("browser_engine"),
        "source_kind": metadata.get("source_kind"),
        "degraded": bool(metadata.get("degraded")),
        "selected_proxy_mask": metadata.get("selected_proxy_mask"),
        "severity_counts": severity_counts,
        "findings": [
            {
                "severity": str(finding.get("severity") or ""),
                "category": str(finding.get("category") or ""),
                "message": str(finding.get("message") or ""),
                "evidence": (
                    _object_list(finding.get("evidence"))[:5]
                    if isinstance(finding.get("evidence"), list)
                    else finding.get("evidence")
                ),
            }
            for finding in normalized_findings
        ],
        "baseline": {
            "user_agent_major": _ua_major(consensus.get("user_agent")),
            "locale": consensus.get("locale"),
            "timezone": consensus.get("timezone"),
            "webdriver": consensus.get("webdriver"),
            "webrtc_ip_count": len(_object_list(consensus.get("webrtc_ips"))),
            "automation_globals_count": len(
                _object_list(consensus.get("automation_globals"))
            ),
            "iframe_leak": _object_dict(consensus.get("iframe_leak")).get(
                "content_window_array_leak"
            ),
            "canvas_text_measure": _object_dict(consensus.get("canvas")).get(
                "text_measure"
            ),
            "canvas_image_data_hash": _object_dict(consensus.get("canvas")).get(
                "image_data_hash"
            ),
            "canvas_data_url_prefix": _object_dict(consensus.get("canvas")).get(
                "data_url_prefix"
            ),
            "audio_fingerprint": _object_dict(consensus.get("audio")).get(
                "fingerprint"
            ),
            "webgl_vendor": _object_dict(consensus.get("webgl")).get("vendor"),
            "webgl_renderer": _object_dict(consensus.get("webgl")).get("renderer"),
            "fonts_count": len(_object_list(consensus.get("fonts"))),
            "max_touch_points": consensus.get("max_touch_points"),
            "pdf_viewer_enabled": consensus.get("pdf_viewer_enabled"),
            "cookie_enabled": consensus.get("cookie_enabled"),
            "drift_keys": sorted(list(_object_dict(baseline.get("drift")).keys())),
        },
        "sites": site_rows,
        "target_diagnostics": target_rows,
    }


def _render_markdown(report: dict[str, object]) -> str:
    summary = _build_agent_summary(report)
    findings = _object_list(summary.get("findings"))
    sites = _object_list(summary.get("sites"))
    target_diagnostics = _object_list(summary.get("target_diagnostics"))
    baseline = _object_dict(summary.get("baseline"))
    severity_counts = _object_dict(summary.get("severity_counts"))
    lines = [
        "# Browser Fingerprint Report",
        "",
        f"- Generated: {summary.get('generated_at')}",
        f"- Engine: {summary.get('engine')}",
        f"- Source: {summary.get('source_kind')}",
        f"- Degraded: {summary.get('degraded')}",
        f"- Proxy: {summary.get('selected_proxy_mask')}",
        f"- Findings: fail={severity_counts.get('fail', 0)}, warn={severity_counts.get('warn', 0)}, info={severity_counts.get('info', 0)}",
        "",
        "## Baseline",
        f"- UA major: {baseline.get('user_agent_major')}",
        f"- Locale: {baseline.get('locale')}",
        f"- Timezone: {baseline.get('timezone')}",
        f"- Webdriver: {baseline.get('webdriver')}",
        f"- WebRTC IP count: {baseline.get('webrtc_ip_count')}",
        f"- Automation globals count: {baseline.get('automation_globals_count')}",
        f"- Iframe leak: {baseline.get('iframe_leak')}",
        f"- Canvas text measure: {baseline.get('canvas_text_measure')}",
        f"- Canvas image-data hash: {baseline.get('canvas_image_data_hash')}",
        f"- Canvas data-url prefix: {baseline.get('canvas_data_url_prefix')}",
        f"- Audio fingerprint: {baseline.get('audio_fingerprint')}",
        f"- WebGL vendor: {baseline.get('webgl_vendor')}",
        f"- WebGL renderer: {baseline.get('webgl_renderer')}",
        f"- Fonts count: {baseline.get('fonts_count')}",
        f"- Max touch points: {baseline.get('max_touch_points')}",
        f"- PDF viewer enabled: {baseline.get('pdf_viewer_enabled')}",
        f"- Cookie enabled: {baseline.get('cookie_enabled')}",
        f"- Drift keys: {', '.join(_string_list(baseline.get('drift_keys'))) or 'none'}",
        "",
        "## Findings",
    ]
    if findings:
        for raw_finding in findings:
            finding = _object_dict(raw_finding)
            lines.append(
                f"- {str(finding.get('severity') or '').upper()} [{finding.get('category')}]: {finding.get('message')}"
            )
    else:
        lines.append("- INFO: no findings")
    lines.extend(["", "## Sites"])
    for raw_site in sites:
        site = _object_dict(raw_site)
        warnings = _string_list(site.get("validation_warnings"))
        warning_text = ",".join(warnings) if warnings else "none"
        lines.append(
            f"- {site.get('site_id')}: status={site.get('status')} attempts={site.get('attempts')} lines={site.get('line_count')}/{site.get('line_count_raw')} rows={site.get('row_count')}/{site.get('row_count_raw')} warnings={warning_text}"
        )
    if target_diagnostics:
        lines.extend(["", "## Target Diagnostics"])
        for raw_payload in target_diagnostics:
            payload = _object_dict(raw_payload)
            lines.append(
                f"- {payload.get('host') or payload.get('url')}: {payload.get('root_cause_category')} ({payload.get('root_cause_confidence')}) browser={payload.get('browser_status')}/{payload.get('browser_blocked')} httpx={payload.get('httpx_status')}/{payload.get('httpx_blocked')} curl={payload.get('curl_status')}/{payload.get('curl_blocked')}"
            )
    return "\n".join(lines).strip() + "\n"

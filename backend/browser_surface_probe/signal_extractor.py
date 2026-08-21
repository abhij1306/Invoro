from __future__ import annotations

from ._core_shared import _IP_RE, _object_dict, _object_list, _string_list  # fmt: skip
import re
from app.services.config.browser_surface_probe import BROWSER_SURFACE_PROBE_CREEPJS_LABELS, BROWSER_SURFACE_PROBE_KEYWORD_GROUPS, BROWSER_SURFACE_PROBE_NEIGHBOR_LINE_WINDOW, BROWSER_SURFACE_PROBE_PIXELSCAN_LABELS, BROWSER_SURFACE_PROBE_RISK_TOKENS, BROWSER_SURFACE_PROBE_SAFE_TOKENS, BROWSER_SURFACE_PROBE_SANNYSOFT_LABELS  # fmt: skip
from browser_surface_probe.value_coercion import BROWSER_VERSION_RE  # fmt: skip
from ipaddress import ip_address  # fmt: skip
from .runtime_source import _int_list, _normalize_key, _normalize_space


def _extract_versions(values: list[str]) -> list[int]:
    versions: list[int] = []
    for value in values:
        for match in BROWSER_VERSION_RE.findall(str(value or "")):
            try:
                versions.append(int(match))
            except ValueError:
                continue
    return sorted(set(versions))


def _extract_ip_values(values: list[str]) -> list[str]:
    ips: list[str] = []
    for value in values:
        for match in _IP_RE.findall(str(value or "")):
            try:
                parsed = ip_address(match)
            except ValueError:
                continue
            if parsed.version == 4:
                ips.append(match)
    return sorted(set(ips))


def _looks_like_networkish_ipv4(value: str) -> bool:
    octets = str(value or "").split(".")
    if len(octets) != 4:
        return False
    try:
        numbers = [int(item) for item in octets]
    except ValueError:
        return False
    if any(number < 0 or number > 255 for number in numbers):
        return True
    if numbers[1:] in ([0, 0, 0], [255, 255, 255]):
        return True
    if numbers[2:] in ([0, 0], [255, 255]):
        return True
    if numbers[3] in {0, 255}:
        return True
    return False


def _clean_ip_values(
    values: list[str], *, known_versions: list[int] | None = None
) -> list[str]:
    version_set = {int(value) for value in (known_versions or [])}
    cleaned: list[str] = []
    for value in values:
        if _looks_like_networkish_ipv4(value):
            continue
        octets = str(value).split(".")
        if len(octets) == 4 and octets[1:] == ["0", "0", "0"]:
            try:
                if int(octets[0]) in version_set:
                    continue
            except ValueError:
                # Non-numeric leading octet: keep value as-is.
                pass
        cleaned.append(value)
    return sorted(set(cleaned))


def _looks_like_truthy_risk(value: str) -> bool:
    lowered = _normalize_space(value).lower()
    if not lowered:
        return False
    if any(token in lowered for token in BROWSER_SURFACE_PROBE_SAFE_TOKENS):
        return False
    if any(token in lowered for token in BROWSER_SURFACE_PROBE_RISK_TOKENS):
        return True
    percent_matches = re.findall(r"(\d+(?:\.\d+)?)%", lowered)
    for match in percent_matches:
        try:
            if float(match) > 0:
                return True
        except ValueError:
            continue
    return False


def _percent_value(value: object) -> float | None:
    match = re.search(r"(\d+(?:\.\d+)?)%", str(value or ""))
    if match is None:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        normalized = _normalize_space(value)
        if not normalized:
            continue
        lowered = normalized.casefold()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(normalized)
    return deduped


def _normalize_snapshot_row(row: object) -> dict[str, object] | None:
    if not isinstance(row, dict):
        return None
    raw_cells = row.get("cells")
    cells = (
        [
            _normalize_space(value)
            for value in list(raw_cells)
            if _normalize_space(value)
        ]
        if isinstance(raw_cells, list)
        else []
    )
    label = _normalize_space(row.get("label")) or (cells[0] if cells else "")
    value = _normalize_space(row.get("value")) or " | ".join(cells[1:])
    if not (label or value or cells):
        return None
    return {
        "cells": cells,
        "label": label,
        "value": value,
    }


def _dedupe_snapshot_rows(rows: list[object]) -> tuple[list[dict[str, object]], int]:
    normalized_rows = [
        normalized
        for row in rows
        if (normalized := _normalize_snapshot_row(row)) is not None
    ]
    seen: set[tuple[tuple[str, ...], str, str]] = set()
    deduped: list[dict[str, object]] = []
    for row in normalized_rows:
        marker = (
            tuple(str(value).casefold() for value in _object_list(row.get("cells"))),
            _normalize_space(row.get("label")).casefold(),
            _normalize_space(row.get("value")).casefold(),
        )
        if marker in seen:
            continue
        seen.add(marker)
        deduped.append(row)
    return deduped, len(normalized_rows)


def _flatten_signal_values(payload: object) -> list[str]:
    if isinstance(payload, str):
        normalized = _normalize_space(payload)
        return [normalized] if normalized else []
    if isinstance(payload, dict):
        flattened: list[str] = []
        for value in payload.values():
            flattened.extend(_flatten_signal_values(value))
        return flattened
    if isinstance(payload, list):
        flattened = []
        for value in payload:
            flattened.extend(_flatten_signal_values(value))
        return flattened
    return []


def _label_alias_set(label_map: dict[str, tuple[str, ...]]) -> set[str]:
    aliases: set[str] = set()
    for values in label_map.values():
        aliases.update(_normalize_key(value) for value in values)
    return aliases


def _extract_labeled_values(
    lines: list[str],
    label_map: dict[str, tuple[str, ...]],
) -> dict[str, list[str]]:
    normalized_lines = [
        _normalize_space(value) for value in lines if _normalize_space(value)
    ]
    aliases = _label_alias_set(label_map)
    extracted: dict[str, list[str]] = {}
    for key, raw_aliases in label_map.items():
        values: list[str] = []
        aliases_for_key = [_normalize_key(value) for value in raw_aliases]
        for index, line in enumerate(normalized_lines):
            normalized_line = _normalize_key(line)
            if not any(alias and alias in normalized_line for alias in aliases_for_key):
                continue
            if ":" in line:
                _, raw_value = line.split(":", 1)
                normalized_value = _normalize_space(raw_value)
                if normalized_value:
                    values.append(normalized_value)
                    continue
            upper_bound = min(
                len(normalized_lines),
                index + 1 + int(BROWSER_SURFACE_PROBE_NEIGHBOR_LINE_WINDOW),
            )
            for candidate in normalized_lines[index + 1 : upper_bound]:
                candidate_key = _normalize_key(candidate)
                if not candidate_key or candidate_key in aliases:
                    continue
                values.append(candidate)
                break
        if values:
            extracted[key] = _dedupe(values)
    return extracted


def _extract_keyword_hits(lines: list[str], keyword_group: str) -> list[str]:
    keywords = BROWSER_SURFACE_PROBE_KEYWORD_GROUPS.get(keyword_group, ())
    hits = [
        _normalize_space(line)
        for line in lines
        if any(keyword in _normalize_space(line).lower() for keyword in keywords)
    ]
    return _dedupe(hits)


def _sannysoft_signal_rows(rows: list[dict[str, object]]) -> dict[str, object]:
    categorized: dict[str, list[dict[str, str]]] = {}
    failed_rows: list[dict[str, str]] = []
    for row in rows:
        label = _normalize_space(row.get("label"))
        value = _normalize_space(row.get("value"))
        row_payload = {"label": label, "value": value}
        normalized_label = _normalize_key(label)
        for key, aliases in BROWSER_SURFACE_PROBE_SANNYSOFT_LABELS.items():
            if any(_normalize_key(alias) in normalized_label for alias in aliases):
                categorized.setdefault(key, []).append(row_payload)
        if _looks_like_truthy_risk(value):
            failed_rows.append(row_payload)
    signal_values = _flatten_signal_values(categorized) + _flatten_signal_values(
        failed_rows
    )
    return {
        "matched_rows": categorized,
        "failed_rows": failed_rows,
        "signal_versions": _extract_versions(signal_values),
        "webdriver_hits": _flatten_signal_values(categorized.get("webdriver")),
        "headless_hits": [],
        "webrtc_hits": [],
        "screen_hits": _flatten_signal_values(categorized.get("screen")),
        "language_hits": _flatten_signal_values(categorized.get("languages")),
        "webgl_hits": _flatten_signal_values(categorized.get("webgl")),
    }


def _generic_line_signals(
    *,
    lines: list[str],
    label_map: dict[str, tuple[str, ...]],
) -> dict[str, object]:
    labeled = _extract_labeled_values(lines, label_map)
    all_values = _flatten_signal_values(labeled)
    return {
        "labeled_values": labeled,
        "keyword_hits": {
            key: _extract_keyword_hits(lines, key)
            for key in BROWSER_SURFACE_PROBE_KEYWORD_GROUPS
        },
        "signal_versions": _extract_versions(all_values),
        "ip_values": [],
    }


def _extract_pixelscan(snapshot: dict[str, object]) -> dict[str, object]:
    lines = [str(value) for value in _object_list(snapshot.get("lines"))]
    payload = _generic_line_signals(
        lines=lines, label_map=BROWSER_SURFACE_PROBE_PIXELSCAN_LABELS
    )
    labeled_values = _object_dict(payload.get("labeled_values"))
    payload["country_values"] = _flatten_signal_values(labeled_values.get("country"))
    payload["ip_values"] = _clean_ip_values(
        _extract_ip_values(_flatten_signal_values(labeled_values.get("ip"))),
        known_versions=_int_list(payload.get("signal_versions")),
    )
    payload["timezone_values"] = _flatten_signal_values(
        {
            "js_timezone": labeled_values.get("js_timezone"),
            "ip_time": labeled_values.get("ip_time"),
        }
    )
    payload["proxy_values"] = _flatten_signal_values(
        labeled_values.get("proxy_verdict")
    )
    payload["language_values"] = _flatten_signal_values(
        labeled_values.get("language_headers")
    )
    payload["screen_values"] = _flatten_signal_values(labeled_values.get("screen_size"))
    payload["webgl_values"] = _flatten_signal_values(labeled_values.get("webgl"))
    return payload


def _extract_creepjs(snapshot: dict[str, object]) -> dict[str, object]:
    lines = [str(value) for value in _object_list(snapshot.get("lines"))]
    payload = _generic_line_signals(
        lines=lines, label_map=BROWSER_SURFACE_PROBE_CREEPJS_LABELS
    )
    labeled_values = _object_dict(payload.get("labeled_values"))
    payload["fp_id_values"] = _flatten_signal_values(labeled_values.get("fp_id"))
    payload["fuzzy_fp_id_values"] = _flatten_signal_values(
        labeled_values.get("fuzzy_fp_id")
    )
    keyword_hits = _object_dict(payload.get("keyword_hits"))
    payload["headless_hits"] = _object_list(keyword_hits.get("headless"))
    payload["webrtc_hits"] = _object_list(keyword_hits.get("webrtc"))
    payload["timezone_hits"] = _object_list(keyword_hits.get("timezone"))
    payload["screen_hits"] = _object_list(keyword_hits.get("screen"))
    payload["ip_values"] = _clean_ip_values(
        _extract_ip_values(_string_list(payload.get("webrtc_hits"))),
        known_versions=_int_list(payload.get("signal_versions")),
    )
    return payload


def _extract_generic_site(snapshot: dict[str, object]) -> dict[str, object]:
    lines = [str(value) for value in _object_list(snapshot.get("lines"))]
    payload = _generic_line_signals(lines=lines, label_map={})
    payload["ip_values"] = _clean_ip_values(
        _extract_ip_values(lines),
        known_versions=_int_list(payload.get("signal_versions")),
    )
    return payload


__all__ = ['BROWSER_SURFACE_PROBE_CREEPJS_LABELS', 'BROWSER_SURFACE_PROBE_KEYWORD_GROUPS', 'BROWSER_SURFACE_PROBE_NEIGHBOR_LINE_WINDOW', 'BROWSER_SURFACE_PROBE_PIXELSCAN_LABELS', 'BROWSER_SURFACE_PROBE_RISK_TOKENS', 'BROWSER_SURFACE_PROBE_SAFE_TOKENS', 'BROWSER_SURFACE_PROBE_SANNYSOFT_LABELS', 'BROWSER_VERSION_RE', '_IP_RE', '_clean_ip_values', '_dedupe', '_dedupe_snapshot_rows', '_extract_creepjs', '_extract_generic_site', '_extract_ip_values', '_extract_keyword_hits', '_extract_labeled_values', '_extract_pixelscan', '_extract_versions', '_flatten_signal_values', '_generic_line_signals', '_int_list', '_label_alias_set', '_looks_like_networkish_ipv4', '_looks_like_truthy_risk', '_normalize_key', '_normalize_snapshot_row', '_normalize_space', '_object_dict', '_object_list', '_percent_value', '_sannysoft_signal_rows', '_string_list', 'annotations', 'ip_address', 're']  # fmt: skip

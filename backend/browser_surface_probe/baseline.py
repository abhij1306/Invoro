from __future__ import annotations

from ._core_shared import *  # noqa: F403
from .runtime_source import _normalize_key, _normalize_space
from .signal_extractor import _dedupe, _dedupe_snapshot_rows


async def _collect_page_snapshot(page) -> dict[str, object]:
    raw_snapshot = await page.evaluate(
        """(limits) => {
            const normalize = (value) => (value || '').replace(/\\s+/g, ' ').trim();
            const rawBodyText = document.body ? (document.body.innerText || '') : '';
            const lines = rawBodyText
                .split(/\\n+/)
                .map((line) => normalize(line))
                .filter(Boolean)
                .slice(0, limits.textLineLimit);
            const rows = Array.from(document.querySelectorAll('tr'))
                .map((row) => {
                    const cells = Array.from(row.querySelectorAll('th, td'))
                        .map((cell) => normalize(cell.innerText || cell.textContent || ''))
                        .filter(Boolean);
                    if (!cells.length) {
                        return null;
                    }
                    return {
                        cells,
                        label: cells[0] || '',
                        value: cells.slice(1).join(' | '),
                    };
                })
                .filter(Boolean)
                .slice(0, limits.tableRowLimit);
            return {
                body_text: normalize(rawBodyText),
                lines,
                line_count: lines.length,
                rows,
                has_creep_object: typeof window.Creep !== 'undefined',
                has_fingerprint_object: typeof window.Fingerprint !== 'undefined',
            };
        }""",
        {
            "textLineLimit": int(BROWSER_SURFACE_PROBE_VISIBLE_TEXT_LIMIT),
            "tableRowLimit": int(BROWSER_SURFACE_PROBE_TABLE_ROW_LIMIT),
        },
    )
    snapshot_payload = dict(raw_snapshot) if isinstance(raw_snapshot, dict) else {}
    raw_lines = [
        _normalize_space(value)
        for value in list(snapshot_payload.get("lines") or [])
        if _normalize_space(value)
    ]
    deduped_lines = _dedupe(raw_lines)
    deduped_rows, raw_row_count = _dedupe_snapshot_rows(
        list(snapshot_payload.get("rows") or [])
    )
    return {
        "body_text": _normalize_space(snapshot_payload.get("body_text")),
        "lines": deduped_lines,
        "line_count": len(deduped_lines),
        "line_count_raw": len(raw_lines),
        "rows": deduped_rows,
        "row_count": len(deduped_rows),
        "row_count_raw": raw_row_count,
        "has_creep_object": bool(snapshot_payload.get("has_creep_object")),
        "has_fingerprint_object": bool(snapshot_payload.get("has_fingerprint_object")),
    }


async def _collect_behavioral_smoke(page) -> dict[str, object]:
    try:
        setup = await page.evaluate(
            """() => {
                const body = document.body;
                if (!body) {
                    return { ready: false, mouse_isTrusted: null, click_isTrusted: null };
                }
                const state = globalThis.__crawlerProbeBehavioralSmoke = {
                    mouse_isTrusted: null,
                    click_isTrusted: null,
                };
                let target = document.getElementById('__crawler_probe_mouse_target__');
                if (!target) {
                    target = document.createElement('div');
                    target.id = '__crawler_probe_mouse_target__';
                    target.setAttribute('aria-hidden', 'true');
                    target.style.cssText = [
                        'position:fixed',
                        'left:8px',
                        'top:8px',
                        'width:32px',
                        'height:32px',
                        'opacity:0.001',
                        'background:#000',
                        'pointer-events:auto',
                        'z-index:2147483647',
                    ].join(';');
                    body.appendChild(target);
                }
                target.addEventListener('mousemove', (event) => {
                    state.mouse_isTrusted = event.isTrusted;
                }, { once: true });
                target.addEventListener('click', (event) => {
                    state.click_isTrusted = event.isTrusted;
                }, { once: true });
                return { ready: true, x: 24, y: 24 };
            }"""
        )
    except Exception:
        return {"mouse_isTrusted": None, "click_isTrusted": None}
    if not _object_dict(setup).get("ready"):
        return {
            "mouse_isTrusted": _object_dict(setup).get("mouse_isTrusted"),
            "click_isTrusted": _object_dict(setup).get("click_isTrusted"),
        }
    try:
        await page.mouse.move(24, 24, steps=6)
        await page.wait_for_timeout(50)
        await page.mouse.click(24, 24, delay=50)
        await page.wait_for_timeout(50)
    except Exception:
        # Trust-probe input is best-effort; evaluation below reports actual state.
        pass
    try:
        return _object_dict(
            await page.evaluate(
                """() => {
                    const state = globalThis.__crawlerProbeBehavioralSmoke || {};
                    const target = document.getElementById('__crawler_probe_mouse_target__');
                    if (target && target.parentNode) {
                        target.parentNode.removeChild(target);
                    }
                    try {
                        delete globalThis.__crawlerProbeBehavioralSmoke;
                    } catch (_error) {}
                    return {
                        mouse_isTrusted: state.mouse_isTrusted ?? null,
                        click_isTrusted: state.click_isTrusted ?? null,
                    };
                }"""
            )
        )
    except Exception:
        return {"mouse_isTrusted": None, "click_isTrusted": None}


async def _collect_baseline(
    page,
    *,
    behavioral_smoke: dict[str, object] | None = None,
) -> dict[str, object]:
    baseline_probe_script = load_baseline_probe_script()
    return await page.evaluate(
        f"""async (input) => {{
{baseline_probe_script}
            return await globalThis.__crawlerProbeCollectBaseline(input);
        }}""",
        {
            "behavioralSmoke": dict(behavioral_smoke or {}),
            "highEntropyHints": list(BROWSER_SURFACE_PROBE_HIGH_ENTROPY_HINTS),
            "webrtcTimeoutMs": int(BROWSER_SURFACE_PROBE_WEBRTC_GATHER_TIMEOUT_MS),
            "fontTestStrings": list(BROWSER_SURFACE_PROBE_FONT_TEST_STRINGS),
        },
    )


def load_baseline_probe_script() -> str:
    return _BASELINE_PROBE_SCRIPT_PATH.read_text(encoding="utf-8")


def _country_code_from_value(value: str | None) -> str | None:
    normalized = _normalize_key(value)
    if not normalized:
        return None
    if len(normalized) == 2 and normalized.isalpha():
        return normalized.upper()
    if normalized in _COUNTRY_CODE_BY_NAME:
        return _COUNTRY_CODE_BY_NAME[normalized]
    for country_name, country_code in _COUNTRY_CODE_BY_NAME.items():
        if country_name and country_name in normalized:
            return country_code
    return None


def _timezone_matches_country(
    timezone_name: str | None, country_code: str | None
) -> bool | None:
    normalized_timezone = _normalize_space(timezone_name)
    normalized_timezone = str(
        BROWSER_SURFACE_PROBE_TIMEZONE_ALIASES.get(
            normalized_timezone,
            normalized_timezone,
        )
    )
    normalized_country = _normalize_space(country_code).upper()
    if not normalized_timezone or not normalized_country:
        return None
    timezone_list = tuple(pytz.country_timezones.get(normalized_country, ()))
    if not timezone_list:
        return None
    return normalized_timezone in timezone_list


def _locale_region(locale_value: str | None) -> str | None:
    normalized = _normalize_space(locale_value).replace("_", "-")
    if "-" not in normalized:
        return None
    _language, region = normalized.rsplit("-", 1)
    region = region.upper()
    return region if len(region) == 2 and region.isalpha() else None


def _coalesce(values: Sequence[object]) -> object | None:
    for value in values:
        if value not in (None, "", [], {}):
            return value
    return None


def _consensus_baseline(per_site: dict[str, dict[str, object]]) -> dict[str, object]:
    if not per_site:
        return {"consensus": {}, "drift": {}}
    keys = (
        "user_agent",
        "user_agent_data",
        "webdriver",
        "locale",
        "languages",
        "timezone",
        "platform",
        "vendor",
        "plugins_count",
        "plugin_names",
        "hardware_concurrency",
        "device_memory",
        "screen",
        "viewport",
        "webgl",
        "canvas",
        "audio",
        "fonts",
        "connection",
        "screen_orientation",
        "max_touch_points",
        "pdf_viewer_enabled",
        "cookie_enabled",
        "do_not_track",
        "automation_globals",
        "timing_jitter",
        "iframe_leak",
        "permissions",
        "behavioral_smoke",
        "webrtc_ips",
    )
    consensus: dict[str, object] = {}
    drift: dict[str, list[object]] = {}
    for key in keys:
        values = [payload.get(key) for payload in per_site.values()]
        normalized_values = [
            value for value in values if value not in (None, "", [], {})
        ]
        consensus[key] = _coalesce(normalized_values)
        unique_values = []
        seen_serialized: set[str] = set()
        for value in normalized_values:
            marker = json.dumps(value, sort_keys=True, default=str)
            if marker in seen_serialized:
                continue
            seen_serialized.add(marker)
            unique_values.append(value)
        if len(unique_values) > 1:
            drift[key] = unique_values
    return {
        "consensus": consensus,
        "drift": drift,
    }


__all__ = tuple(name for name in globals() if not name.startswith("__"))

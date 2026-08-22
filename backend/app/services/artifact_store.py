from pathlib import Path
from typing import Any

from app.core.config import settings
from app.services.acquisition.browser_diagnostics import normalize_browser_engine
from app.services.config.export_settings import (
    BROWSER_ARTIFACT_DERIVABLE_FIELDS,
    BROWSER_ARTIFACT_DROP_WHEN_EMPTY,
    BROWSER_ARTIFACT_HOST_OUTCOME_KEY,
    BROWSER_ARTIFACT_INTERSTITIAL_DISMISSAL_TIMING_KEY,
    BROWSER_ARTIFACT_INTERSTITIAL_PROBE_TIMING_KEY,
    BROWSER_ARTIFACT_LISTING_ONLY_FIELDS,
    BROWSER_ARTIFACT_LISTING_SURFACE_KEYWORD,
    BROWSER_ARTIFACT_PREFETCH_HOST_KEY,
)
from app.services.db_utils import mapping_or_empty
from app.services.storage.factory import get_artifact_storage


def shape_browser_artifact(
    diagnostics: dict[str, Any],
    *,
    surface: str | None,
    blocked: bool = False,
) -> dict[str, Any]:
    payload = dict(mapping_or_empty(diagnostics))
    payload.pop(BROWSER_ARTIFACT_PREFETCH_HOST_KEY, None)
    payload[BROWSER_ARTIFACT_HOST_OUTCOME_KEY] = _browser_host_outcome(
        payload, blocked=blocked
    )
    for key in BROWSER_ARTIFACT_DERIVABLE_FIELDS:
        payload.pop(key, None)
    if BROWSER_ARTIFACT_LISTING_SURFACE_KEYWORD not in str(surface or "").lower():
        for key in BROWSER_ARTIFACT_LISTING_ONLY_FIELDS:
            payload.pop(key, None)
    timings = _shaped_phase_timings(payload.get("phase_timings_ms"))
    timings = _relabel_interstitial_timing(timings, payload.get("interstitial"))
    if timings:
        payload["phase_timings_ms"] = timings
    else:
        payload.pop("phase_timings_ms", None)
    for key in BROWSER_ARTIFACT_DROP_WHEN_EMPTY:
        if payload.get(key) in ([], {}):
            payload.pop(key, None)
    return payload


def _browser_host_outcome(
    diagnostics: dict[str, Any], *, blocked: bool
) -> dict[str, Any]:
    engine = normalize_browser_engine(diagnostics.get("browser_engine"))
    outcome = str(diagnostics.get("browser_outcome") or "").strip().lower()
    succeeded = not blocked and outcome in {"usable_content", "ok"}
    result: dict[str, Any] = {
        "engine": engine,
        "browser_outcome": outcome or None,
        "blocked": bool(blocked),
        "result": "success" if succeeded else "blocked" if blocked else "incomplete",
    }
    for key in ("failure_reason", "escalation_lane"):
        if diagnostics.get(key):
            result[key] = diagnostics[key]
    return result


def _shaped_phase_timings(timings: object) -> dict[str, Any]:
    if not isinstance(timings, dict):
        return {}
    shaped: dict[str, Any] = {}
    for key, value in timings.items():
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            shaped[str(key)] = value
            continue
        if numeric != 0 or str(key) == "total":
            shaped[str(key)] = value
    return shaped


def _relabel_interstitial_timing(
    timings: dict[str, Any], interstitial: object
) -> dict[str, Any]:
    dismissal_key = BROWSER_ARTIFACT_INTERSTITIAL_DISMISSAL_TIMING_KEY
    if dismissal_key not in timings:
        return timings
    status = (
        str(interstitial.get("status") or "").strip().lower()
        if isinstance(interstitial, dict)
        else ""
    )
    if status == "dismissed":
        return timings
    relabeled = dict(timings)
    relabeled[BROWSER_ARTIFACT_INTERSTITIAL_PROBE_TIMING_KEY] = relabeled.pop(
        dismissal_key
    )
    return relabeled


def persist_html_artifact(*, run_id: int, source_url: str, html: str) -> str:
    return get_artifact_storage(root_dir=settings.artifacts_dir).persist_html_artifact(
        run_id=run_id, source_url=source_url, html=html
    )


def persist_json_artifact(
    *,
    run_id: int,
    source_url: str,
    suffix: str,
    payload: dict[str, Any],
) -> str:
    return get_artifact_storage(root_dir=settings.artifacts_dir).persist_json_artifact(
        run_id=run_id, source_url=source_url, suffix=suffix, payload=payload
    )


def persist_png_artifact(
    *,
    run_id: int,
    source_url: str,
    suffix: str,
    content: bytes,
) -> str:
    return get_artifact_storage(root_dir=settings.artifacts_dir).persist_png_artifact(
        run_id=run_id, source_url=source_url, suffix=suffix, content=content
    )


def persist_png_artifact_from_file(
    *,
    run_id: int,
    source_url: str,
    suffix: str,
    file_path: str | Path,
) -> str:
    return get_artifact_storage(
        root_dir=settings.artifacts_dir
    ).persist_png_artifact_from_file(
        run_id=run_id, source_url=source_url, suffix=suffix, file_path=file_path
    )

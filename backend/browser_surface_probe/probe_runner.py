from __future__ import annotations

from ._core_shared import *  # noqa: F403
from .baseline import _collect_baseline, _collect_behavioral_smoke, _collect_page_snapshot, _consensus_baseline
from .findings import _target_root_cause, build_findings
from .runtime_source import RuntimeSource, _json_dump, _masked_proxy_inventory, _normalize_space
from .target_diagnostics import _capture_probe_artifacts, _failed_target_diagnostic, _navigate_probe_target, _run_target_diagnostic, _site_artifacts, _site_signal_payload, _site_validation_warnings, _validated_target_url


def _failed_site_payload(
    *,
    site_id: str,
    site_label: str,
    url: str,
    artifacts: dict[str, Path],
    attempts: int,
    error: str,
) -> dict[str, object]:
    return {
        "site_id": site_id,
        "label": site_label,
        "url": url,
        "site_status": "failed",
        "attempts": attempts,
        "error": error,
        "error_message": error,
        "artifacts": {
            "screenshot": artifacts["screenshot"].name
            if artifacts["screenshot"].exists()
            else None,
            "html": artifacts["html"].name if artifacts["html"].exists() else None,
        },
        "baseline": {},
        "snapshot_summary": {},
        "extracted": {},
    }

async def _probe_site(
    runtime: SharedBrowserRuntime,
    *,
    site_id: str,
    site_label: str,
    url: str,
    run_id: int,
    locality_profile: dict[str, object],
    artifacts_dir: Path,
) -> dict[str, object]:
    artifacts = _site_artifacts(artifacts_dir, site_id)
    max_attempts = max(1, int(BROWSER_SURFACE_PROBE_SITE_MAX_RETRIES) + 1)
    last_error = ""
    for attempt in range(1, max_attempts + 1):
        try:
            async with runtime.page(
                run_id=run_id,
                locality_profile=locality_profile,
                allow_storage_state=False,
            ) as page:
                try:
                    await _navigate_probe_target(page, url)
                    behavioral_smoke = await _collect_behavioral_smoke(page)
                    baseline = await _collect_baseline(
                        page, behavioral_smoke=behavioral_smoke
                    )
                    snapshot = await _collect_page_snapshot(page)
                    html = await page.content()
                    await page.screenshot(
                        path=str(artifacts["screenshot"]), full_page=True
                    )
                    artifacts["html"].write_text(html, encoding="utf-8")
                    extracted = _site_signal_payload(site_id, snapshot)
                    validation_warnings = _site_validation_warnings(site_id, snapshot)
                    return {
                        "site_id": site_id,
                        "label": site_label,
                        "url": url,
                        "site_status": "degraded" if validation_warnings else "ok",
                        "attempts": attempt,
                        "validation_warnings": validation_warnings,
                        "final_url": _normalize_space(page.url),
                        "title": _normalize_space(await page.title()),
                        "artifacts": {
                            "screenshot": artifacts["screenshot"].name,
                            "html": artifacts["html"].name,
                        },
                        "baseline": baseline,
                        "snapshot_summary": {
                            "line_count": snapshot.get("line_count", 0),
                            "line_count_raw": snapshot.get(
                                "line_count_raw", snapshot.get("line_count", 0)
                            ),
                            "lines": _object_list(snapshot.get("lines")),
                            "row_count": snapshot.get("row_count", 0),
                            "row_count_raw": snapshot.get(
                                "row_count_raw", snapshot.get("row_count", 0)
                            ),
                            "rows": _object_list(snapshot.get("rows")),
                            "has_creep_object": bool(snapshot.get("has_creep_object")),
                            "has_fingerprint_object": bool(
                                snapshot.get("has_fingerprint_object")
                            ),
                        },
                        "extracted": extracted,
                    }
                except Exception:
                    await _capture_probe_artifacts(page, artifacts)
                    raise
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "Browser surface probe failed site=%s attempt=%s/%s: %s",
                site_id,
                attempt,
                max_attempts,
                last_error,
            )
            if attempt < max_attempts:
                backoff_ms = max(0, int(BROWSER_SURFACE_PROBE_RETRY_BACKOFF_MS))
                if backoff_ms:
                    await asyncio.sleep((backoff_ms * attempt) / 1000)
    return _failed_site_payload(
        site_id=site_id,
        site_label=site_label,
        url=url,
        artifacts=artifacts,
        attempts=max_attempts,
        error=last_error or "unknown probe failure",
    )

async def build_report(
    *,
    runtime_source: RuntimeSource,
    report_dir: Path,
    target_urls: list[str] | None = None,
    runtime_provider=get_browser_runtime,
) -> dict[str, object]:
    report_dir.mkdir(parents=True, exist_ok=True)
    runtime = await runtime_provider(
        proxy=runtime_source.selected_proxy,
        browser_engine=runtime_source.browser_engine,
    )
    sites: dict[str, dict[str, object]] = {}
    for index, target in enumerate(BROWSER_SURFACE_PROBE_TARGETS):
        site_payload = await _probe_site(
            runtime,
            site_id=str(target["id"]),
            site_label=str(target["label"]),
            url=str(target["url"]),
            run_id=runtime_source.identity_run_id,
            locality_profile=runtime_source.locality_profile,
            artifacts_dir=report_dir,
        )
        sites[str(target["id"])] = site_payload
        delay_ms = max(0, int(BROWSER_SURFACE_PROBE_REQUEST_DELAY_MS))
        if delay_ms and index < len(BROWSER_SURFACE_PROBE_TARGETS) - 1:
            await asyncio.sleep(delay_ms / 1000)
    baseline = _consensus_baseline(
        {
            site_id: _object_dict(site_payload.get("baseline"))
            for site_id, site_payload in sites.items()
            if isinstance(site_payload, dict)
        }
    )
    consensus = _object_dict(baseline.get("consensus"))
    target_diagnostics: list[dict[str, object]] = []
    for raw_url in list(target_urls or []):
        raw = _normalize_space(raw_url)
        if not raw:
            continue
        try:
            url = _validated_target_url(raw)
        except ValueError as exc:
            target_diagnostics.append(
                _failed_target_diagnostic(url=raw, error=f"{type(exc).__name__}: {exc}")
            )
            continue
        try:
            diagnostic = await _run_target_diagnostic(
                runtime,
                url=url,
                runtime_source=runtime_source,
                artifacts_dir=report_dir,
            )
        except Exception as exc:
            diagnostic = _failed_target_diagnostic(
                url=url,
                error=f"{type(exc).__name__}: {exc}",
            )
        diagnostic["root_cause"] = _target_root_cause(
            consensus=consensus,
            diagnostic=diagnostic,
        )
        target_diagnostics.append(diagnostic)
    site_statuses = {
        site_id: str(site_payload.get("site_status") or "unknown")
        for site_id, site_payload in sites.items()
    }
    metadata = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source_kind": runtime_source.source_kind,
        "source_run_id": runtime_source.run_id,
        "identity_run_id": runtime_source.identity_run_id,
        "browser_engine": runtime_source.browser_engine,
        "selected_proxy_mask": _display_proxy(runtime_source.selected_proxy),
        "selected_proxy_index": runtime_source.selected_proxy_index,
        "proxy_inventory_masked": _masked_proxy_inventory(runtime_source.proxy_list),
        "proxy_profile": runtime_source.proxy_profile,
        "locality_profile": runtime_source.locality_profile,
        "runtime_snapshot": runtime.snapshot(),
        "site_statuses": site_statuses,
        "degraded": any(status != "ok" for status in site_statuses.values()),
    }
    report: dict[str, object] = {
        "metadata": metadata,
        "connection_source": {
            "source_kind": runtime_source.source_kind,
            "run_id": runtime_source.run_id,
            "selected_proxy_mask": _display_proxy(runtime_source.selected_proxy),
            "proxy_inventory_masked": _masked_proxy_inventory(
                runtime_source.proxy_list
            ),
            "proxy_profile": runtime_source.proxy_profile,
            "locality_profile": runtime_source.locality_profile,
        },
        "baseline": baseline,
        "sites": sites,
        "target_diagnostics": target_diagnostics,
    }
    report["findings"] = build_findings(report)
    report["agent_summary"] = build_agent_summary(report)
    (report_dir / "report.json").write_text(_json_dump(report), encoding="utf-8")
    (report_dir / "report.md").write_text(render_markdown(report), encoding="utf-8")
    return report

__all__ = tuple(
    name for name in globals() if not name.startswith("__")
)

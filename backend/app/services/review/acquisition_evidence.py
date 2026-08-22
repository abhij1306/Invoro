from __future__ import annotations

from app.models.crawl_run import CrawlRecord, CrawlRun
from app.services.config.browser_fingerprint_profiles import BROWSER_REQUIRED_REASONS
from app.services.db_utils import mapping_or_empty
from app.services.shared.field_coerce import object_list


def derive_acquisition_info(
    records: list[CrawlRecord], *, run: CrawlRun
) -> dict[str, object]:
    actual_fetch_method, browser_reason = _fetch_method_and_reason(records)
    browser_required = any(_record_requires_browser(record) for record in records)
    affordance_candidates = _affordance_candidates(records)
    acquisition_summary = mapping_or_empty(
        mapping_or_empty(run.result_summary).get("acquisition_summary")
    )
    if actual_fetch_method is None and mapping_or_empty(
        acquisition_summary.get("methods")
    ).get("browser"):
        actual_fetch_method = "browser"
    if browser_reason is None and actual_fetch_method == "browser":
        browser_reason = "http-escalation"
    affordance_candidates["browser_required"] = browser_required
    return {
        "actual_fetch_method": actual_fetch_method,
        "browser_required": browser_required,
        "browser_reason": browser_reason,
        "acquisition_summary": acquisition_summary,
        "affordance_candidates": affordance_candidates,
    }


def _fetch_method_and_reason(
    records: list[CrawlRecord],
) -> tuple[str | None, str | None]:
    method = None
    reason = None
    for record in records:
        acquisition = _record_acquisition(record)
        diagnostics = mapping_or_empty(acquisition.get("browser_diagnostics"))
        method = method or str(acquisition.get("method") or "").strip() or None
        reason = (
            reason
            or str(diagnostics.get("browser_reason") or "").strip().lower()
            or None
        )
    return method, reason


def _record_requires_browser(record: CrawlRecord) -> bool:
    acquisition = _record_acquisition(record)
    diagnostics = mapping_or_empty(acquisition.get("browser_diagnostics"))
    return (
        str(acquisition.get("method") or "").strip().lower() == "browser"
        and str(diagnostics.get("browser_reason") or "").strip().lower()
        in BROWSER_REQUIRED_REASONS
    )


def _record_acquisition(record: CrawlRecord) -> dict[str, object]:
    return mapping_or_empty(mapping_or_empty(record.source_trace).get("acquisition"))


def _affordance_candidates(records: list[CrawlRecord]) -> dict[str, object]:
    candidates: dict[str, object] = {
        "accordions": [],
        "tabs": [],
        "carousels": [],
        "shadow_hosts": [],
        "iframe_promotion": None,
        "browser_required": False,
    }
    for record in records:
        acquisition = _record_acquisition(record)
        merge_affordance_candidates(
            candidates,
            acquisition=acquisition,
            browser_diagnostics=mapping_or_empty(
                acquisition.get("browser_diagnostics")
            ),
        )
    return candidates


def merge_affordance_candidates(
    candidates: dict[str, object],
    *,
    acquisition: dict[str, object],
    browser_diagnostics: dict[str, object],
) -> None:
    accordion_labels = object_list(candidates.get("accordions"))
    tab_labels = object_list(candidates.get("tabs"))
    if not candidates.get("iframe_promotion"):
        final_url = str(acquisition.get("final_url") or "").strip()
        requested_url = str(acquisition.get("requested_url") or "").strip()
        if final_url and final_url != requested_url:
            candidates["iframe_promotion"] = final_url
    detail_expansion = mapping_or_empty(browser_diagnostics.get("detail_expansion"))
    _append_unique(
        accordion_labels, string_values(detail_expansion.get("expanded_elements"))
    )
    _append_unique(
        tab_labels,
        string_values(
            mapping_or_empty(detail_expansion.get("aom")).get("expanded_elements")
        ),
    )
    candidates["accordions"] = accordion_labels
    candidates["tabs"] = tab_labels


def _append_unique(target: list[object], values: list[str]) -> None:
    target.extend(value for value in values if value not in target)


def string_values(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item or "").strip()]

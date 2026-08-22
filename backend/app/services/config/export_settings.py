from __future__ import annotations

MAX_RECORD_PAGE_SIZE = 1000
ARTIFACT_STORAGE_BACKEND = "local"
EXPORT_PAGING_HEADER = "X-Export-Paging"
EXPORT_TOTAL_HEADER = "X-Export-Total"
EXPORT_PARTIAL_HEADER = "X-Export-Partial"
EXPORT_QUALITY_GATE_HEADER = "X-Export-Quality-Gate"
EXPORT_QUALITY_REPORT_HEADER = "X-Export-Quality-Report"
EXPORT_REQUIRED_FIELD_MIN_FILL_RATE = 0.8

BROWSER_ARTIFACT_DERIVABLE_FIELDS = frozenset(
    {
        "browser_headless",
        "browser_launch_mode",
        "browser_profile",
        "browser_native_context",
        "browser_binary",
        "browser_stealth_enabled",
    }
)
BROWSER_ARTIFACT_LISTING_ONLY_FIELDS = frozenset(
    {
        "listing_readiness",
        "listing_recovery",
        "listing_artifact_capture",
        "extractable_listing_evidence",
        "rendered_listing_fragment_count",
        "listing_visual_element_count",
        "listing_visual_capture",
    }
)
BROWSER_ARTIFACT_DROP_WHEN_EMPTY = frozenset(
    {
        "challenge_evidence",
        "challenge_provider_hits",
        "challenge_element_hits",
        "behavior_realism",
        "policy_decisions",
        "host_outcome",
    }
)
BROWSER_ARTIFACT_LISTING_SURFACE_KEYWORD = "listing"
BROWSER_ARTIFACT_PREFETCH_HOST_KEY = "host_policy_snapshot"
BROWSER_ARTIFACT_HOST_OUTCOME_KEY = "host_outcome"
BROWSER_ARTIFACT_INTERSTITIAL_DISMISSAL_TIMING_KEY = "interstitial_dismissal"
BROWSER_ARTIFACT_INTERSTITIAL_PROBE_TIMING_KEY = "interstitial_probe"

"""Canonical config for the self-healing observability / run-audit layer.

All tunables for run tracing and auditing live here (INVARIANT Rule 1). Service
code in ``app/services/observability/*`` imports from this module and must not
define its own thresholds, artifact names, or token constants.
"""

from __future__ import annotations

# --- Master switch -----------------------------------------------------------
# When False, the RunTrace collector is a no-op and nothing is written. Kept as
# a plain module constant so it can be patched in tests and overridden via the
# settings layer without importing service code.
RUN_TRACE_ENABLED = True

# --- Artifact layout ---------------------------------------------------------
# Subdirectories under ``artifacts/runs/<run_id>/`` owned by this layer.
TRACE_ARTIFACT_SUBDIR = "trace"
AUDIT_ARTIFACT_SUBDIR = "audit"
RUN_TRACE_FILENAME = "run_trace.json"
FLAGS_FILENAME = "flags.json"
LLM_DIAGNOSIS_FILENAME = "llm_diagnosis.json"

# Schema version stamped into every run_trace.json so readers (audit engine,
# future frontend) can evolve safely.
RUN_TRACE_SCHEMA_VERSION = 1

# --- Trace tiers -------------------------------------------------------------
# Lightweight trace is always captured. Full candidate-competition detail (every
# losing candidate + reject reason for high-value fields) is captured only when
# the verdict is not in this success set, OR when an audit flag fires.
TRACE_TIER_LIGHT = "light"
TRACE_TIER_FULL = "full"

# Verdicts that are considered clean enough to skip full candidate-competition
# capture. Mirrors the publish verdict vocabulary; kept here so the trace layer
# does not import publish internals just for the string.
TRACE_SUCCESS_VERDICTS = frozenset({"success"})

# --- High-value field policy hook --------------------------------------------
# The high-value field set = union(run requested_fields, default canonical
# repair targets for the surface). The trace layer resolves this via
# ``app.services.field_policy.repair_target_fields_for_surface`` and must not
# hardcode a parallel list. This constant only bounds candidate capture when no
# requested/default fields resolve (defensive floor for ecommerce detail).
HIGH_VALUE_FIELD_FLOOR = ("price", "title", "image_url")

# Max losing candidates captured per field in full-tier traces. Bounds trace
# size on pathological pages with many rejected candidates.
MAX_CANDIDATE_LOSERS_PER_FIELD = 12

# --- Acquire-timeline event kinds --------------------------------------------
# Stable identifiers for ordered acquire-timeline events so the audit engine and
# frontend can match on kind rather than free text.
ACQUIRE_EVENT_NAVIGATION = "navigation"
ACQUIRE_EVENT_READINESS_PROBE = "readiness_probe"
ACQUIRE_EVENT_INTERSTITIAL = "interstitial"
ACQUIRE_EVENT_CHALLENGE = "challenge"
ACQUIRE_EVENT_ESCALATION = "escalation"
ACQUIRE_EVENT_POLICY_DECISION = "policy_decision"

# --- Extraction-trace stage names --------------------------------------------
EXTRACTION_TIER_AUTHORITATIVE = "authoritative"
EXTRACTION_TIER_STRUCTURED = "structured_data"
EXTRACTION_TIER_JS_STATE = "js_state"
EXTRACTION_TIER_DOM = "dom"

# --- Baseline drift thresholds (Slice 5) -------------------------------------
# Phase-timing band tolerance: a run's total acquire time breaches the baseline
# band when it exceeds baseline_mean * (1 + tolerance) and the absolute slack.
BASELINE_TIMING_TOLERANCE_RATIO = 0.5
BASELINE_TIMING_ABSOLUTE_SLACK_MS = 4000
# Minimum number of prior runs before a baseline is trusted enough to flag drift.
BASELINE_MIN_SAMPLES = 3

# --- Flag severities ---------------------------------------------------------
FLAG_SEVERITY_HIGH = "high"
FLAG_SEVERITY_MEDIUM = "medium"
FLAG_SEVERITY_LOW = "low"

__all__ = [
    "RUN_TRACE_ENABLED",
    "TRACE_ARTIFACT_SUBDIR",
    "AUDIT_ARTIFACT_SUBDIR",
    "RUN_TRACE_FILENAME",
    "FLAGS_FILENAME",
    "LLM_DIAGNOSIS_FILENAME",
    "RUN_TRACE_SCHEMA_VERSION",
    "TRACE_TIER_LIGHT",
    "TRACE_TIER_FULL",
    "TRACE_SUCCESS_VERDICTS",
    "HIGH_VALUE_FIELD_FLOOR",
    "MAX_CANDIDATE_LOSERS_PER_FIELD",
    "ACQUIRE_EVENT_NAVIGATION",
    "ACQUIRE_EVENT_READINESS_PROBE",
    "ACQUIRE_EVENT_INTERSTITIAL",
    "ACQUIRE_EVENT_CHALLENGE",
    "ACQUIRE_EVENT_ESCALATION",
    "ACQUIRE_EVENT_POLICY_DECISION",
    "EXTRACTION_TIER_AUTHORITATIVE",
    "EXTRACTION_TIER_STRUCTURED",
    "EXTRACTION_TIER_JS_STATE",
    "EXTRACTION_TIER_DOM",
    "BASELINE_TIMING_TOLERANCE_RATIO",
    "BASELINE_TIMING_ABSOLUTE_SLACK_MS",
    "BASELINE_MIN_SAMPLES",
    "FLAG_SEVERITY_HIGH",
    "FLAG_SEVERITY_MEDIUM",
    "FLAG_SEVERITY_LOW",
]

from app.services.config import observability as obs_config
from app.services.db_utils import mapping_or_empty
from app.services.shared.field_coerce import object_list


def record_acquire_timeline(context, acquisition_result) -> None:
    trace = context.trace
    if trace is None:
        return
    method = str(getattr(acquisition_result, "method", "") or "")
    diagnostics = mapping_or_empty(getattr(acquisition_result, "browser_diagnostics", {}))
    timings = mapping_or_empty(diagnostics.get("phase_timings_ms"))
    _record_policy_decisions(trace, diagnostics)
    host_outcome = mapping_or_empty(diagnostics.get("host_outcome"))
    if host_outcome:
        trace.record_host_outcome(host_outcome)
    if method != "browser":
        trace.record_acquire_event(
            obs_config.ACQUIRE_EVENT_HTTP_FETCH,
            detail={
                "method": method,
                "status_code": getattr(acquisition_result, "status_code", None),
                "blocked": bool(getattr(acquisition_result, "blocked", False)),
            },
        )
        return
    _record_browser_timeline(trace, diagnostics, timings=timings)


def _record_policy_decisions(trace, diagnostics: dict[str, object]) -> None:
    for decision in object_list(diagnostics.get("policy_decisions")):
        if isinstance(decision, dict):
            trace.record_acquire_event(
                obs_config.ACQUIRE_EVENT_POLICY_DECISION,
                detail={
                    "action": decision.get("action"),
                    "reason": decision.get("reason"),
                    "stage": decision.get("stage"),
                },
            )


def _record_browser_timeline(trace, diagnostics, *, timings) -> None:
    trace.record_acquire_event(
        obs_config.ACQUIRE_EVENT_NAVIGATION,
        detail={
            "engine": diagnostics.get("browser_engine"),
            "strategy": diagnostics.get("navigation_strategy"),
            "reason": diagnostics.get("browser_reason"),
        },
        duration_ms=_as_int(timings.get("navigation")),
    )
    for probe in object_list(diagnostics.get("readiness_probes")):
        if isinstance(probe, dict):
            trace.record_acquire_event(
                obs_config.ACQUIRE_EVENT_READINESS_PROBE,
                detail={
                    "stage": probe.get("stage"),
                    "is_ready": probe.get("is_ready"),
                    "visible_text_length": probe.get("visible_text_length"),
                    "detail_like": probe.get("detail_like"),
                    "listing_card_count": probe.get("listing_card_count"),
                },
            )
    _record_interstitial(trace, diagnostics, timings=timings)
    challenge_wait = _as_int(timings.get("challenge_wait"))
    if challenge_wait:
        trace.record_acquire_event(
            obs_config.ACQUIRE_EVENT_CHALLENGE,
            detail={"outcome": diagnostics.get("browser_outcome")},
            duration_ms=challenge_wait,
        )
    escalation_lane = diagnostics.get("escalation_lane")
    if escalation_lane:
        trace.record_acquire_event(
            obs_config.ACQUIRE_EVENT_ESCALATION,
            detail={
                "lane": escalation_lane,
                "engine": diagnostics.get("browser_engine"),
            },
        )


def _record_interstitial(trace, diagnostics, *, timings) -> None:
    interstitial = mapping_or_empty(diagnostics.get("interstitial"))
    if not interstitial:
        return
    dismissed = str(interstitial.get("status") or "").strip().lower() == "dismissed"
    timing_key = obs_config.INTERSTITIAL_DISMISSAL_TIMING_KEY if dismissed else obs_config.INTERSTITIAL_PROBE_TIMING_KEY
    trace.record_acquire_event(
        obs_config.ACQUIRE_EVENT_INTERSTITIAL,
        detail={"status": interstitial.get("status")},
        duration_ms=_as_int(timings.get(timing_key)),
    )


def _as_int(value: object) -> int | None:
    try:
        return None if value in (None, "") else int(float(value))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None

from app.services.config import observability as obs_config
from app.services.db_utils import mapping_or_empty


def record_extraction_trace(context, records: list[dict[str, object]]) -> None:
    trace = getattr(context, "trace", None)
    primary = next((record for record in records if isinstance(record, dict)), None)
    if trace is None or primary is None:
        return
    field_sources = mapping_or_empty(primary.get("_field_sources"))
    completed = mapping_or_empty(primary.get("_extraction_tiers")).get("completed")
    if isinstance(completed, list):
        trace.record_completed_tiers([str(item) for item in completed])
    _record_dom_skip(trace, primary, completed=completed)
    _record_winning_sources(trace, primary, field_sources)
    _record_field_states(trace, primary, field_sources)


def _record_dom_skip(trace, primary: dict[str, object], *, completed: object) -> None:
    dom_completed = isinstance(completed, list) and any(
        str(item).strip().lower() == obs_config.EXTRACTION_TIER_DOM for item in completed
    )
    decision = mapping_or_empty(primary.get("_dom_skip_decision"))
    if decision:
        trace.record_skip_dom_decision(
            dom_skipped=bool(decision.get("dom_skipped", not dom_completed)),
            confidence=_as_float(decision.get("confidence")),
            threshold=_as_float(decision.get("threshold")),
            dom_completion_reason=str(decision.get("reason") or "") or None,
        )


def _record_winning_sources(trace, primary, field_sources) -> None:
    for field_name, sources in field_sources.items():
        source_list = sources if isinstance(sources, list) else [sources]
        winner = next((str(item) for item in source_list if str(item or "").strip()), "")
        if not winner:
            continue
        value = primary.get(field_name)
        trace.record_field_candidate(
            str(field_name),
            source=winner,
            won=True,
            value_preview=_field_value_preview(str(field_name), value),
        )


def _record_field_states(trace, primary, field_sources) -> None:
    trace_fields = set(field_sources)
    trace_field_names = getattr(trace, "trace_field_names", None)
    if callable(trace_field_names):
        trace_fields.update(str(field_name) for field_name in trace_field_names())
    for field_name in sorted(trace_fields):
        values = field_sources.get(field_name)
        source_list = values if isinstance(values, list) else [values]
        trace.record_field_state(
            str(field_name),
            value=primary.get(field_name),
            candidate_sources=[str(item) for item in source_list if str(item or "").strip()],
        )


def _as_float(value: object) -> float | None:
    try:
        return None if value in (None, "") else float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _field_value_preview(field_name: str, value: object) -> str:
    if value in (None, "", [], {}):
        return ""
    normalized = str(field_name or "").strip().lower()
    if any(token in normalized for token in obs_config.TRACE_REDACTED_FIELD_TOKENS):
        return obs_config.TRACE_REDACTED_VALUE
    return str(value)

from __future__ import annotations

from ._run_json_issue_audit_shared import UTC, Any, Counter, Path, argparse, datetime, json  # fmt: skip
from .json_issue_audit_core import audit_record
from .json_issue_audit_triage import (
    ROOT_CAUSE_RULES,
    _build_host_summary,
    _build_root_cause_groups,
    _build_triage_section,
)


def _to_records(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        if isinstance(payload.get("results"), list):
            return [row for row in payload["results"] if isinstance(row, dict)]
        if isinstance(payload.get("records"), list):
            return [row for row in payload["records"] if isinstance(row, dict)]
        return [payload]
    return []


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit crawler JSON output and emit agent-ready issue report."
    )
    parser.add_argument("--input", required=True, help="Path to JSON file.")
    parser.add_argument(
        "--output-dir",
        default="",
        help="Output directory for reports. Default: same dir as input.",
    )
    parser.add_argument(
        "--fail-on",
        choices=["none", "low", "medium", "high"],
        default="none",
        help="Exit non-zero if any record has severity >= fail-on.",
    )
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"input not found: {input_path}")

    payload = json.loads(input_path.read_text(encoding="utf-8"))
    records = _to_records(payload)
    if not records:
        raise ValueError("no object records found in json")

    audited = [audit_record(record) for record in records]

    # --- Build agent-optimized output ---
    root_cause_groups = _build_root_cause_groups(audited)
    host_summary = _build_host_summary(audited)
    triage = _build_triage_section(root_cause_groups, audited)

    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out_dir = (
        Path(args.output_dir).resolve()
        if str(args.output_dir or "").strip()
        else input_path.parent.resolve()
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / f"{stamp}__{input_path.stem}__issue_audit.json"

    # Build static reference lookup — agent reads this once to understand how to fix each root cause
    reference: dict[str, dict[str, Any]] = {}
    for rule in ROOT_CAUSE_RULES:
        reference[rule["id"]] = {
            "code_targets": rule.get("code_targets", []),
            "debug_steps": rule.get("debug_steps", []),
            "do_not": rule.get("do_not", ""),
        }

    weighted_category_counts: Counter[str] = Counter()
    for row in audited:
        for key, value in dict(row["category_counts"]).items():
            weighted_category_counts[str(key)] += int(value)

    records_with_issues = sum(1 for r in audited if r["issue_count"] > 0)

    report = {
        "_schema": "agent_issue_audit_v2",
        "_usage": (
            "1. Read triage.fix_order top-to-bottom. "
            "2. For each id, look up reference[id] for code_targets and debug_steps. "
            "3. Skip ids in triage.do_not_fix. "
            "4. If triage.secondary_on_blocked_hosts > 0, fix acquisition first. "
            "5. Use host_breakdown to see which hosts are affected."
        ),
        "stats": {
            "total": len(audited),
            "with_issues": records_with_issues,
            "clean": len(audited) - records_with_issues,
            "severity": dict(
                sorted(Counter(row["max_severity"] for row in audited).items())
            ),
            "categories": dict(sorted(weighted_category_counts.items())),
        },
        "triage": triage,
        "issues": root_cause_groups,
        "host_breakdown": host_summary,
        "reference": reference,
    }

    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # --- Console output ---
    print(f"Input: {input_path}")
    print(
        f"Records: {len(audited)} total | {records_with_issues} with issues | {len(audited) - records_with_issues} clean"
    )
    print()
    print(
        f"TRIAGE: {triage['action_required']} actionable | {triage['skip_count']} skip"
    )
    if triage["note"]:
        print(f"  NOTE: {triage['note']}")
    print()
    if triage["fix_order"]:
        print("FIX ORDER:")
        for item in triage["fix_order"]:
            target = item["file"] or "—"
            print(
                f"  #{item['priority']} [{item['fix_layer']:11}] {item['id']:35} x{item['count']:3}  -> {target}"
            )
    if triage["do_not_fix"]:
        print(f"\nSKIP: {', '.join(triage['do_not_fix'])}")
    print(f"\nReport: {json_path}")

    threshold_rank = {"none": 0, "low": 1, "medium": 2, "high": 3}
    hit_rank = max(threshold_rank.get(row["max_severity"], 0) for row in audited)
    if hit_rank >= threshold_rank.get(args.fail_on, 0) and args.fail_on != "none":
        return 1
    return 0


__all__ = ['ROOT_CAUSE_RULES', 'UTC', 'Any', 'Counter', 'Path', '_build_host_summary', '_build_root_cause_groups', '_build_triage_section', '_to_records', 'annotations', 'argparse', 'audit_record', 'datetime', 'json', 'main']  # fmt: skip

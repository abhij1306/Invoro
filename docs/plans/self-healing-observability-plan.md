# Plan: Self-Healing Observability & Run-Audit Layer

**Created:** 2026-05-30
**Agent:** Claude (Opus 4.8)
**Status:** IN PROGRESS
**Touches buckets:** Bucket 2 (pipeline orchestration), Bucket 3 (acquisition/browser runtime),
Bucket 4 (extraction tiers), Bucket 5 (persistence/artifacts), Bucket 6 (domain memory). New
read-only audit subsystem. Frontend deferred to Phase 2.

## Goal

Make every crawl run self-auditing. Today the agent debugs by the user pasting logs and JSON by
hand, and there is no record of *where* a field was extracted from. Two blackholes exist:
(1) browser launch -> page rendered is opaque (only "Launched browser" + "Page loaded in Xms");
(2) the extraction pipeline is completely dark — tier execution, the skip-DOM decision, and
per-field candidate competition are never persisted. The saved `browser.json` is also bloated and
dishonest (pre-fetch host snapshot read back as a per-run result, listing fields on detail runs,
5 derivable fields, all-zero timings).

Done looks like: every run emits a single honest `run_trace.json` (the causal chain across
acquire -> extract -> normalize -> persist, including per-tier execution and high-value field
provenance), a from-scratch audit reads that trace + a learned `(domain, surface)` baseline and
emits `flags.json` where each flag maps symptom -> violated INVARIANT rule -> owning file from
CODEBASE_MAP -> evidence span. The agent reads `flags.json`; the user pastes nothing. The audit
runs automatically on every finished run via `on_run_complete`. No auto-repair. The baseline lives
in existing `DomainRunProfile` memory so each audited run sharpens the next ("learn once, reuse").

Phase 1 (Slices 1–5) delivers trace + honest artifacts + audit + baseline. Phase 2 (Slices 6–8)
adds the LLM page-rebuild/explain diagnosis (observe-only) and the frontend "Run Trace" tab, then
full verification. `run_json_issue_audit.py` is NOT extended — the new audit is written from
scratch; the old script is at most a secondary record-quality input and is otherwise retired.

## Acceptance Criteria

- [ ] Every finished run (HTTP-only and browser, all surfaces) writes exactly one
      `artifacts/runs/<id>/trace/run_trace.json` capturing acquire timeline, extraction tier
      execution, the skip-DOM decision, and high-value-field provenance (winner + losers + reject
      reasons for requested + default canonical fields only).
- [ ] `browser.json` is rebuilt: no derivable fields, no all-zero timings, no empty-array padding,
      no listing-only fields on non-listing surfaces, and the pre-fetch `host_policy_snapshot` is
      replaced by an honest post-fetch host outcome. Every remaining key is meaningful for the run
      that produced it.
- [ ] The launch->rendered blackhole is closed: the acquire timeline is an ordered event list
      (nav strategy, each readiness poll, interstitial action with real cost attribution, challenge
      iterations, escalation decision + reason), not just summed `phase_timings_ms`.
- [ ] The extraction blackhole is closed: `completed_tiers`, the `_can_skip_dom_tier` decision
      (confidence vs threshold + DOM-completion reason), and per-high-value-field candidate
      competition are persisted.
- [ ] Trace capture is tiered: lightweight trace always; full candidate-competition detail only
      when verdict != success OR a flag fires.
- [ ] A new audit subsystem runs at `on_run_complete` for every run and writes
      `artifacts/runs/<id>/audit/flags.json`. Each flag includes: symptom, violated INVARIANT rule
      id, owning file (from CODEBASE_MAP), severity, and an evidence reference into `run_trace.json`.
- [ ] A learned execution baseline per `(domain, surface)` is stored in `DomainRunProfile` and
      updated after each audited run; drift from baseline (lost field, changed engine, skipped tier,
      timing-band breach, verdict regression) produces a flag.
- [ ] Audit + trace are read-only: no mutation of `CrawlRecord.data`, surface, selector memory,
      verdicts, or extraction ranking.
- [ ] (Phase 2) On flagged runs with `llm_enabled` + active config, an observe-only LLM diagnosis
      explains field provenance / missing-field cause and is referenced from `flags.json`; it never
      writes extraction fields, verdicts, or baseline.
- [ ] (Phase 2) A read-only frontend "Run Trace" tab renders the trace graph + flags (+ diagnosis
      when present).
- [ ] (Phase 2) Full gates pass: `ruff check app tests`, `mypy app`, `pytest tests -q`,
      frontend `npm run lint`, `npm run format:check`, `npm run test` all exit 0.

## Do Not Touch

- `backend/agent_debug/*` — legacy paste-driven flow; superseded, left in place, not extended.
- `backend/run_json_issue_audit.py` — not the architecture; do not build on it. At most consumed as
  one optional record-quality input node.
- Extraction ranking / candidate selection (`_winning_candidates_for_field`, `SOURCE_PRIORITY`) —
  trace observes it, never changes it (INVARIANT Rule 3).
- `publish/*` cleanup and verdict logic — audit reads verdicts, does not alter them (Rule 2/4).
- LLM runtime (`llm/*`) — untouched this phase; diagnosis layer is Phase 2 and must stay
  observe-only when built (Rule 10).
- Frontend — Phase 2.

## Slices

### Slice 1: RunTrace collector + typed trace contract
**Status:** DONE
**Files:**
- new `backend/app/services/observability/run_trace.py` (collector + typed trace objects)
- new `backend/app/services/config/observability.py` (trace tiers, high-value field policy hook,
  artifact subdir names, baseline thresholds, flag severities — all tunables live here per Rule 1)
- `backend/app/services/pipeline/url_processing_context.py` (carry an optional `RunTrace` handle)
**What:** Define a per-URL/per-run trace structure: nodes (run, url, stage, tier, field, source) and
ordered events with reasons. Collector is opt-in/no-op when disabled so hot paths are unaffected.
High-value field set = union of run `requested_fields` + default canonical fields for the surface
(reuse existing field-policy helpers; do not redefine). No instrumentation wired yet — just the
contract + config.
**Verify:** DONE — `pytest tests/services/observability -q` = 12 passed; ruff + mypy clean on new
files; pipeline tests (`-k "extraction_loop or process_single_url or pipeline"`) = 19 passed with
the new `trace` field on `URLProcessingContext`.
**Done notes:** `new_run_trace()` returns `NullRunTrace` (no-op) when `RUN_TRACE_ENABLED` is False or
no run is attached; real collector otherwise. High-value resolution reuses
`field_policy.repair_target_fields_for_surface` (no parallel list). Tiering implemented in
`RunTrace.to_dict(flagged=...)`: light tier drops losing-candidate lists, full tier kept on
non-success verdict or when a flag fires. Candidate capture is high-value-field-only and capped by
`MAX_CANDIDATE_LOSERS_PER_FIELD`. Tests must carry `pytest.mark.unit` (pytest.ini runs only
`unit or component`).

### Slice 2: Rebuild `browser.json` (honest, lean) + close the launch->rendered blackhole
**Status:** TODO
**Files:**
- `backend/app/services/acquisition/browser_diagnostics.py`
- `backend/app/services/acquisition/browser_result_builder.py` (`build_browser_diagnostics`)
- `backend/app/services/acquisition/browser_interstitial.py` (attribute real interstitial cost;
  fix the "not_found yet 3873ms" mislabel)
- `backend/app/services/pipeline/persistence.py` (`_persist_browser_artifacts` payload shaping)
- `backend/app/services/config/observability.py` / `config/runtime_settings.py` as needed
**What:**
- Drop derivable fields (`browser_headless`, `browser_launch_mode`, `browser_profile`,
  `browser_native_context`, `browser_binary`) from stored payload; they are pure functions of
  `browser_engine` and can be recomputed on read.
- Drop all-zero `phase_timings_ms` entries and empty-array/empty-dict padding
  (`challenge_element_hits: []`, `challenge_evidence: []`, `behavior_realism: {}`, etc.) — emit a
  key only when it carries signal.
- Gate listing-only diagnostics (`listing_readiness`, `listing_recovery`,
  `listing_artifact_capture`, `extractable_listing_evidence`, `rendered_listing_fragment_count`,
  `listing_visual_element_count`) to listing surfaces only. Detail runs must not carry them.
- Replace pre-fetch `host_policy_snapshot` with an honest post-fetch host outcome
  (engine attempted, result, whether success/block was written back). Move the pre-fetch policy
  read into the acquire timeline as a labeled *input decision*, not a result field.
- Emit an ordered acquire timeline (nav strategy chosen, each readiness probe result, interstitial
  action + true cost, challenge iterations, escalation decision + reason) feeding the RunTrace.
**Verify:** Re-run a detail fetch smoke; new `browser.json` has zero listing fields, zero derivable
fields, zero all-zero timings; interstitial cost is correctly attributed;
`pytest tests/services/acquisition -q`.

### Slice 3: Instrument the extraction pipeline (close the dark blackhole)
**Status:** TODO
**Files:**
- `backend/app/services/extract/detail/assembly/tiers.py` (surface `completed_tiers` +
  `_can_skip_dom_tier` decision with confidence/threshold/DOM-completion reason)
- `backend/app/services/extract/field_candidates/*` (emit per-high-value-field candidate
  competition: each candidate value, source tier, winner/loser, reject reason — high-value fields
  only, tiered detail)
- `backend/app/services/pipeline/extraction_loop.py` (thread RunTrace through extract/normalize)
- `backend/app/services/pipeline/persistence.py` (write `run_trace.json`; fold acquire timeline +
  extraction trace + normalize edits + verdict into it)
**What:** Capture which tiers ran, whether DOM was skipped and exactly why (the INVARIANT Rule 3
root cause), and where each high-value field's value came from including the losing candidates and
why they lost. Respect tiering: lightweight always, full candidate competition only on
non-success verdicts or when a flag fires. Observe only — no change to selection logic.
**Verify:** Run extraction smoke on a detail PDP and a listing; confirm `run_trace.json` shows
`completed_tiers`, skip-DOM decision, and price/title/image/variants provenance with losers;
`pytest tests/services/extract -q` + `pytest tests/services/pipeline -q`.

### Slice 4: From-scratch audit engine + flags.json (auto, every run)
**Status:** TODO
**Files:**
- new `backend/app/services/observability/run_audit.py` (anomaly -> root-cause -> owner mapping)
- new `backend/app/services/config/audit_rules.py` (symptom->INVARIANT-rule->owning-file table,
  severities; sourced from INVARIANTS.md + CODEBASE_MAP — config, not service code, per Rule 1)
- `backend/app/services/pipeline/run_complete_callbacks.py` is unchanged; register the auditor like
  monitors do (new `register_*` call from the audit module)
**What:** New auditor reads `run_trace.json` (+ optionally record-quality signals) and emits
`artifacts/runs/<id>/audit/flags.json`. Each flag: symptom, violated INVARIANT rule id, owning file
from CODEBASE_MAP, severity, evidence ref into the trace. Deterministic rules first (e.g. "price
missing + variant DOM cues present + DOM tier skipped at confidence X < threshold Y -> INVARIANT
Rule 3 -> `extract/detail/assembly/tiers.py`"; "usable_content but blocked=true -> Rule 6";
"listing run, 1 record of page metadata -> Rule 7"). Registered at `on_run_complete`; runs for
every finished run. Read-only.
**Verify:** Replay a known-bad run (e.g. run 33 family) and a known-good run; bad run produces
actionable flags with correct owner files, good run produces none; `pytest tests/services/observability -q`.

### Slice 5: Execution baseline in DomainRunProfile (self-healing loop)
**Status:** TODO
**Files:**
- `backend/app/services/crawl/profile/*` (extend run-profile normalize/merge/persist)
- `backend/app/models/domain_memory.py` (only if a new JSON column/sub-key is needed; prefer
  reusing existing profile JSON)
- `backend/app/services/observability/run_audit.py` (compare current run vs baseline; emit drift flags)
- `backend/app/services/config/observability.py` (drift thresholds, timing-band tolerance)
**What:** Store the expected execution signature per normalized `(domain, surface)`: tiers used,
high-value fields normally found, engine, phase-timing band, normal verdict. Update it after each
audited run. Drift (lost field, engine change, newly-skipped tier, timing breach, verdict
regression) becomes a flag. Scoped strictly by `(domain, surface)` per INVARIANT Rule 9. Read/write
of baseline only; never rewrites acquisition contracts or selectors.
**Verify:** Two runs same domain/surface: first seeds baseline, second with an injected regression
flags drift; `pytest tests/services/crawl/profile -q` + `pytest tests/services/observability -q`.

> Slices 1–5 are Phase 1 (trace + honest artifacts + audit + baseline). Slices 6–8 are Phase 2
> (LLM diagnosis, frontend, full verification). Phase 2 starts only after Phase 1 is verified.

### Slice 6 (Phase 2): LLM page-rebuild / "explain this run" diagnosis — observe-only
**Status:** TODO
**Files:**
- new `backend/app/services/observability/run_llm_diagnosis.py`
- `backend/app/services/observability/run_audit.py` (invoke diagnosis only on flagged runs)
- `backend/app/services/config/observability.py` (diagnosis gating, token budget, prompt-task id)
- reuse `backend/app/services/llm/*` task + prompt + cost-logging plumbing; do not fork it
**What:** On flagged runs only, and only when `llm_enabled=True` AND active config allows it, feed
the RunTrace + relevant HTML/artifact slices to an LLM "rebuild the page / explain provenance" task
that returns a human-readable account: where each high-value field came from, why a field is
missing, and which flagged root cause is most likely. Output is attached to the run's audit folder
(e.g. `audit/llm_diagnosis.json`) and referenced from `flags.json`. This is the underutilized-LLM
ask. Hard constraint (INVARIANT Rule 6 + Rule 10): diagnosis is observe-only — it must not write
extraction fields, change verdicts, mutate `CrawlRecord.data`, selector memory, or the baseline.
LLM failure/disabled is recorded as a diagnostic, never a hard error.
**Verify:** Flagged run with `llm_enabled=True` produces `llm_diagnosis.json` referenced from flags;
with `llm_enabled=False` it records "diagnosis skipped: llm_disabled" and emits nothing else;
`pytest tests/services/observability -q` + `pytest tests/services/llm -q`.

### Slice 7 (Phase 2): Frontend "Run Trace" tab (trace graph + flags)
**Status:** TODO
**Files:**
- `frontend/app/*` (new run-trace route/tab) + `frontend/components/*` local components
- `frontend/lib/api/*` (read-only client methods for trace/flags/diagnosis)
- new read-only backend route under `backend/app/api/*` to serve `run_trace.json` / `flags.json` /
  `llm_diagnosis.json` for a run (owner: route handler only, per CODEBASE_MAP api/ rules)
**What:** Visualize the run as a graph (url -> stage -> tier -> field -> source) with flags overlaid
and the LLM diagnosis (when present) shown inline. Read-only view; no controls that mutate runs.
Follow existing UI primitive/pattern owners; respect the token-escape and crawl-architecture lint
guards.
**Verify:** `cd frontend; npm run lint; npm run test`; Playwright smoke renders the new tab for a
run that has flags.

### Slice 8 (Phase 2): Full-suite verification — tests + mypy + ruff + prettier
**Status:** TODO
**Files:** docs + any test/type/lint gaps surfaced
**What:** Ensure `flags.json` is the single stable thing the agent reads (stable path + schema).
Optionally add a `userTriggered`/`postTaskExecution` hook that surfaces the latest run's flags into
agent context. Then run the complete backend + frontend gates exactly as CI runs them.
**Verify:**
```
# Backend (from backend/, PYTHONPATH=.)
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m mypy app
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe run_extraction_smoke.py
.\.venv\Scripts\python.exe run_acquire_smoke.py commerce

# Frontend (from frontend/)
npm run lint
npm run format:check
npm run test
```
All must exit 0 (ruff clean, mypy clean, pytest green, eslint + token/architecture guards clean,
prettier check clean, vitest green).

## Doc Updates Required

- [ ] `docs/CODEBASE_MAP.md` — add `services/observability/*`, new config files, trace/audit artifact paths.
- [ ] `docs/INVARIANTS.md` — add the observability contract: trace/audit are read-only; trace must
      not change extraction/verdict behavior; baseline scoped by `(domain, surface)`.
- [ ] `docs/backend-architecture.md` — document RunTrace, the rebuilt `browser.json` schema, and the audit flow.
- [ ] `docs/ENGINEERING_STRATEGY.md` — note the "diagnostics must be honest and signal-only"
      anti-pattern (no derivable/zero/pre-fetch-as-result fields).

## Notes

- Confirmed contradictions in run 33 `browser.json` driving Slice 2:
  1. `host_policy_snapshot` is captured pre-fetch in `fetch_context.py`; `patchright_success:false`
     on a `usable_content` run because this run's own success wasn't written yet. `*_blocked` and
     `*_success` are independent TTL-windowed derivations (both false = cold host memory), so it's
     not a logic bug — but storing a pre-fetch snapshot as a per-run result is dishonest. Replace
     with post-fetch host outcome.
  2. `interstitial.status: not_found` but `phase_timings_ms.interstitial_dismissal: 3873` — ~3.8s
     spent on a no-op dismissal; cost attribution is wrong or the work is wasteful. Fix attribution
     in Slice 2.
  3. Listing-only diagnostics populate on an `ecommerce_detail` run (always emitted in
     `build_browser_diagnostics`). Gate to listing surfaces.
  4. 5 derivable fields + many all-zero `phase_timings_ms` keys + empty arrays = pure padding.
- StableBrowse framing: persistent site memory + reusable execution graph ("learn once, reuse").
  This codebase already has the substrate (`DomainRunProfile`/`DomainMemory`, `source_trace`,
  `browser_diagnostics`, `on_run_complete`); the gap is assembling a per-run trace, comparing to a
  learned baseline, and emitting honest flagged output — not new capture infrastructure.

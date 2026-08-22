# Plan: Productionization 03 — Acquisition and Orchestration Debt Reduction

**Created:** 2026-08-21
**Agent:** Codex
**Status:** COMPLETE
**PR boundary:** One independent PR. Acquisition, fetch, crawl, and pipeline orchestration only.
**Touches buckets:** Acquisition + browser runtime, fetch, crawl orchestration, pipeline orchestration

## Goal

Reduce acquisition and orchestration debt while preserving runtime policy and failure semantics. Every maintained file in scope must be `<=800` physical lines. Every scoped callable must have cyclomatic complexity `<=15`. Total scoped LOC must decrease. Fetch modes, proxies, traversal, retries, browser diagnostics, host memory, persistence boundaries, and per-URL failure isolation must remain stable.

## Context for a Fresh Session

The 2026-08-21 audit found eight oversized production files in this scope and many CC violations. High-risk callables include browser attempt orchestration, warm-origin navigation, traversal loops, batch processing, persistence staging, and retry decisions. Current code wins over audit counts.

Before code:

1. Read `AGENTS.md`.
2. Read `docs/INVARIANTS.md` Rules 1, 2, 4–9 and all acquisition/browser/pipeline contracts.
3. Read `docs/ENGINEERING_STRATEGY.md` AP-1, AP-2, AP-4, AP-5, AP-13, AP-15, AP-16, and AP-17.
4. Read Acquisition and Crawl/Pipeline ownership in `docs/CODEBASE_MAP.md` and `docs/backend-architecture.md`.
5. Grep call sites before moving or creating any symbol.

Hard behavior constraints:

- Acquisition returns observations. It never fabricates logical fields.
- Explicit `surface`, traversal intent, proxy settings, engine settings, diagnostics flags, and `llm_enabled` remain authoritative.
- Preserve bounded challenge recovery, usable-content precedence, engine escalation, origin-warmup rules, and per-URL browser failure isolation.
- Preserve `fetch_page` and pipeline public contracts.
- Do not move extraction repair into pipeline/persistence.
- If a simplification changes retry count, deadline allocation, blocked verdict, learned host policy, run state, or persisted result, stop and ask the user.

## Scope

Oversized files that must be reduced below 800 physical lines:

- `backend/app/services/acquisition/browser_detail.py` (audit: 1100)
- `backend/app/services/acquisition/browser_pool.py` (1095)
- `backend/app/services/acquisition/browser_runtime.py` (1068)
- `backend/app/services/fetch/fetch_context.py` (1013)
- `backend/app/services/acquisition/runtime.py` (977)
- `backend/app/services/pipeline/extraction_loop.py` (915)
- `backend/app/services/crawl/sitemap_resolver.py` (912)
- `backend/app/services/crawl/batch_runtime.py` (898)

Complexity scope includes every maintained Python callable under:

- `backend/app/services/acquisition/**`
- `backend/app/services/fetch/**`
- `backend/app/services/crawl/**`
- `backend/app/services/pipeline/**`
- directly owned acquisition helpers such as `robots_policy.py`, `url_safety.py`, and browser diagnostics/readiness/result modules

Priority hotspots from the audit include `_run_browser_attempts`, `_maybe_warm_origin_before_navigation`, `expand_interactive_elements_via_accessibility_impl`, `probe_browser_readiness_impl`, traversal loops, `fetch_page`, `_process_run_with_span`, persistence-stage orchestration, and listing-integrity retry.

## Acceptance Criteria

- [x] Record starting commit, dirty state, scoped LOC, files over 800, and all scoped CC violations in Notes.
- [x] Every maintained scoped source file is `<=800` physical lines.
- [x] Every scoped callable has Radon CC `<=15`.
- [x] Scoped physical LOC is lower than baseline.
- [x] Public fetch, crawl, pipeline, diagnostics, and state-transition contracts remain stable.
- [x] No user control is silently rewritten.
- [x] No runtime tunable moves outside existing `app/services/config/*` ownership.
- [x] No new cross-cutting layer or private cross-module reach-in exists.
- [x] Scoped Vulture/jscpd/search candidates are validated; confirmed dead/duplicate code is deleted.
- [x] Focused acquisition/crawl/pipeline tests, acquisition smoke, and backend safe suite pass.
- [x] No dependency, workflow, frontend, extraction-rule, persistence-schema, or migration changes are included.

## Do Not Touch

- Deterministic extraction internals and adapters — Plan 02.
- Product workflows, review/selectors, audits, monitors, API/bootstrap — Plan 04.
- `pipeline/persistence.py` semantics and publish/export cleanup — preserve current trusted boundary.
- Test-suite structural splitting — Plan 01. Focused test edits are allowed only for moved public ownership.
- `frontend/**`, manifests/lockfiles, `.github/workflows/**` — Plans 05–07.

## Slices

### Slice 1: Baseline and Runtime Contract Map

**Status:** DONE
**Files:** full scope; focused tests read-only
**What:** Record exact LOC and numeric CC. Run scoped Vulture/jscpd as leads. Map shared deadlines, browser lifecycle, host memory, navigation, traversal, retry, run state, and persistence handoffs before editing. Identify deletions and existing owners.
**Verify:** Run current acquisition/fetch/crawl/pipeline focused tests before edits. Stop if baseline fails.

### Slice 2: Browser Pool, Runtime, and Detail Expansion

**Status:** DONE
**Files:** `acquisition/browser_pool.py`, `browser_runtime.py`, `browser_detail.py`, `runtime.py`, existing focused acquisition modules and tests
**What:** Split lifecycle, navigation, observation assembly, and expansion responsibilities only into existing acquisition owners. Keep public interfaces thin. Delete repeated readiness/diagnostic translations. Preserve resource teardown and AP-16 chrome-click protections.
**Verify:** Run browser-context, browser-expansion, traversal, readiness, challenge, and structure tests located by `rg`.

### Slice 3: Fetch Attempt Orchestration

**Status:** DONE
**Files:** `fetch/fetch_context.py`, existing `fetch/**` owners, focused fetch tests
**What:** Keep `fetch_page` as facade. Reduce branch complexity in HTTP result handling, browser attempt planning, handoff, diagnostics, and host policy through named stage functions owned by `fetch/**`. Do not add compatibility shims. Delete redundant policy translations.
**Verify:** Run crawl fetch runtime, block detection, host policy, browser diagnostics, and structure tests.

### Slice 4: Crawl, Sitemap, Batch, and Pipeline Orchestration

**Status:** DONE
**Files:** `crawl/sitemap_resolver.py`, `crawl/batch_runtime.py`, `pipeline/extraction_loop.py`, other scoped CC violators and focused tests
**What:** Keep orchestration facades explicit. Separate URL-loop, progress/state, failure handling, category resolution, extraction-stage calls, and retry-stage calls using existing owners. Preserve idempotency, state transitions, cancellation, and per-URL isolation. Delete duplicate flow branches.
**Verify:** Run batch runtime, sitemap, pipeline core, crawl service, retry, persistence, and structure tests.

### Slice 5: Scoped Metrics, Smoke, and Full Verification

**Status:** DONE
**Files:** all touched scope; owner docs where required
**What:** Re-run exact LOC, numeric Radon, Vulture 100%, and jscpd. Prove LOC decreased and all limits pass. Run acquisition smoke and safe suite.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe run_acquire_smoke.py commerce`; then `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests -q -m "unit or component or regression"`

## Doc Updates Required

- [x] `docs/CODEBASE_MAP.md` — stable moved ownership.
- [x] `docs/backend-architecture.md` — changed acquisition/fetch/crawl/pipeline layout.
- [x] `docs/INVARIANTS.md` — no change required; runtime contracts are unchanged.
- [x] `docs/ENGINEERING_STRATEGY.md` — no new recurring anti-pattern.
- [x] `docs/plans/ACTIVE.md` — active pointer and closeout.

## Notes

- Source evidence: `docs/audits/productionization-evidence-report-2026-08-21.md`, sections 4–7.
- Plan 01 may move test paths. Locate current contract tests with `rg`.
- A network/DNS/browser smoke failure is not permission to weaken acceptance. Record external failure separately from deterministic test results.
- Baseline commit: `f82c969` (`fix: make variant option mapping explicit (#99)`).
- Baseline dirty state: generated `frontend/next-env.d.ts` only; user confirmed it regenerates automatically. It is excluded from this PR.
- Baseline scope: 83 Python files, 26,719 physical LOC, eight files over 800 lines, and 57 distinct Radon callable violations above CC 15.
- Baseline oversized files: `browser_detail.py` 1,100; `browser_pool.py` 1,095; `browser_runtime.py` 1,068; `fetch_context.py` 1,013; `acquisition/runtime.py` 977; `pipeline/extraction_loop.py` 915; `crawl/sitemap_resolver.py` 912; `crawl/batch_runtime.py` 898.
- Baseline Vulture at 100% confidence: no candidates. Scoped jscpd: eight clone leads, 102 duplicated lines (0.46%); leads are in pipeline retry/staging, batch runtime, traversal, acquisition policy/profile normalization, and host protection memory.
- Contract map: config remains in `services/config`; `fetch_context` owns attempt I/O/state and `fetch/browser_policy` owns pure attempt policy; browser pool owns lifecycle; browser runtime/page flow/recovery own navigation and bounded challenge handling; traversal stays explicit; batch runtime owns per-URL isolation and run progress; extraction loop owns stage order; persistence remains the trusted write boundary.
- Pre-edit focused verification: 391 acquisition/fetch/crawl/pipeline and structure tests pass. The isolated-worktree run produced 379 passes plus 12 path/import-state failures; rerunning its 30 structure tests in the primary checkout passed, proving the same 391-test baseline green before edits.
- Final scope: 92 Python files and 26,710 physical LOC (nine lines below baseline); zero maintained files over 800 lines and zero Radon callables above CC 15.
- Final ownership split keeps facades stable while moving pool lifecycle, accessibility expansion, origin warmup, content signals, browser attempts, host memory, sitemap navigation, parallel batching, and trace projection to explicit subsystem owners.
- Final Vulture at 100% confidence: no candidates. Scoped jscpd: eight clone leads, 92 duplicated lines (0.33%), down from 102 lines; review found no further behavior-safe exact duplicate to delete.
- Final focused verification: acquisition 119 passed, fetch 83 passed, crawl 35 passed, and the broad browser/traversal/pipeline selection passed after fixing its one discovered heuristic-fallback regression (350 unaffected passes plus 19/19 owning-file rerun). Commerce acquisition smoke passed 6/6 targets.

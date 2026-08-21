# Plan: Productionization 03 — Acquisition and Orchestration Debt Reduction

**Created:** 2026-08-21
**Agent:** Codex
**Status:** QUEUED — set to `IN PROGRESS` only when this plan is assigned
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

- [ ] Record starting commit, dirty state, scoped LOC, files over 800, and all scoped CC violations in Notes.
- [ ] Every maintained scoped source file is `<=800` physical lines.
- [ ] Every scoped callable has Radon CC `<=15`.
- [ ] Scoped physical LOC is lower than baseline.
- [ ] Public fetch, crawl, pipeline, diagnostics, and state-transition contracts remain stable.
- [ ] No user control is silently rewritten.
- [ ] No runtime tunable moves outside existing `app/services/config/*` ownership.
- [ ] No new cross-cutting layer or private cross-module reach-in exists.
- [ ] Scoped Vulture/jscpd/search candidates are validated; confirmed dead/duplicate code is deleted.
- [ ] Focused acquisition/crawl/pipeline tests, acquisition smoke, and backend safe suite pass.
- [ ] No dependency, workflow, frontend, extraction-rule, persistence-schema, or migration changes are included.

## Do Not Touch

- Deterministic extraction internals and adapters — Plan 02.
- Product workflows, review/selectors, audits, monitors, API/bootstrap — Plan 04.
- `pipeline/persistence.py` semantics and publish/export cleanup — preserve current trusted boundary.
- Test-suite structural splitting — Plan 01. Focused test edits are allowed only for moved public ownership.
- `frontend/**`, manifests/lockfiles, `.github/workflows/**` — Plans 05–07.

## Slices

### Slice 1: Baseline and Runtime Contract Map

**Status:** TODO
**Files:** full scope; focused tests read-only
**What:** Record exact LOC and numeric CC. Run scoped Vulture/jscpd as leads. Map shared deadlines, browser lifecycle, host memory, navigation, traversal, retry, run state, and persistence handoffs before editing. Identify deletions and existing owners.
**Verify:** Run current acquisition/fetch/crawl/pipeline focused tests before edits. Stop if baseline fails.

### Slice 2: Browser Pool, Runtime, and Detail Expansion

**Status:** TODO
**Files:** `acquisition/browser_pool.py`, `browser_runtime.py`, `browser_detail.py`, `runtime.py`, existing focused acquisition modules and tests
**What:** Split lifecycle, navigation, observation assembly, and expansion responsibilities only into existing acquisition owners. Keep public interfaces thin. Delete repeated readiness/diagnostic translations. Preserve resource teardown and AP-16 chrome-click protections.
**Verify:** Run browser-context, browser-expansion, traversal, readiness, challenge, and structure tests located by `rg`.

### Slice 3: Fetch Attempt Orchestration

**Status:** TODO
**Files:** `fetch/fetch_context.py`, existing `fetch/**` owners, focused fetch tests
**What:** Keep `fetch_page` as facade. Reduce branch complexity in HTTP result handling, browser attempt planning, handoff, diagnostics, and host policy through named stage functions owned by `fetch/**`. Do not add compatibility shims. Delete redundant policy translations.
**Verify:** Run crawl fetch runtime, block detection, host policy, browser diagnostics, and structure tests.

### Slice 4: Crawl, Sitemap, Batch, and Pipeline Orchestration

**Status:** TODO
**Files:** `crawl/sitemap_resolver.py`, `crawl/batch_runtime.py`, `pipeline/extraction_loop.py`, other scoped CC violators and focused tests
**What:** Keep orchestration facades explicit. Separate URL-loop, progress/state, failure handling, category resolution, extraction-stage calls, and retry-stage calls using existing owners. Preserve idempotency, state transitions, cancellation, and per-URL isolation. Delete duplicate flow branches.
**Verify:** Run batch runtime, sitemap, pipeline core, crawl service, retry, persistence, and structure tests.

### Slice 5: Scoped Metrics, Smoke, and Full Verification

**Status:** TODO
**Files:** all touched scope; owner docs where required
**What:** Re-run exact LOC, numeric Radon, Vulture 100%, and jscpd. Prove LOC decreased and all limits pass. Run acquisition smoke and safe suite.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe run_acquire_smoke.py commerce`; then `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests -q -m "unit or component or regression"`

## Doc Updates Required

- [ ] `docs/CODEBASE_MAP.md` — stable moved ownership.
- [ ] `docs/backend-architecture.md` — changed acquisition/fetch/crawl/pipeline layout.
- [ ] `docs/INVARIANTS.md` — no change unless the user approves a runtime-contract decision.
- [ ] `docs/ENGINEERING_STRATEGY.md` — only for a new recurring anti-pattern.
- [ ] `docs/plans/ACTIVE.md` — active pointer and closeout.

## Notes

- Source evidence: `docs/audits/productionization-evidence-report-2026-08-21.md`, sections 4–7.
- Plan 01 may move test paths. Locate current contract tests with `rg`.
- A network/DNS/browser smoke failure is not permission to weaken acceptance. Record external failure separately from deterministic test results.


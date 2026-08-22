# Plan: Productionization 04 — Backend Application Services Debt Reduction

**Created:** 2026-08-21
**Agent:** Codex
**Status:** QUEUED — set to `IN PROGRESS` only when this plan is assigned
**PR boundary:** One independent PR. Remaining backend production owners not covered by extraction or acquisition plans.
**Touches buckets:** Product Intelligence, data enrichment, UCP/page audit, Playground, review/selectors, monitors/alerts, API/bootstrap, LLM, design-system service

## Goal

Reduce debt across remaining backend application services without changing public behavior. Every maintained backend production file in scope must be `<=800` physical lines. Every scoped callable must have cyclomatic complexity `<=15`. Total scoped LOC must decrease. API contracts, workspace/user isolation, persistence ownership, workflow transitions, reports, and deterministic scoring must stay stable.

## Context for a Fresh Session

Plans 02 and 03 own extraction and acquisition/orchestration. This plan owns all remaining backend production complexity, so no CC violation is left unassigned. The 2026-08-21 audit found nine oversized files here. It also found complex functions in Product Intelligence, UCP/page audit, enrichment, Playground, review/selectors, monitors, API, LLM, config validation, and report builders. Current code wins over audit counts.

Before code:

1. Read `AGENTS.md`.
2. Read relevant rules in `docs/INVARIANTS.md` for config, user controls, review/domain memory, enrichment, audits, LLM, public APIs, and persistence.
3. Read `docs/BUSINESS_LOGIC.md` for every workflow touched.
4. Read `docs/ENGINEERING_STRATEGY.md` AP-1, AP-2, AP-5, AP-7, AP-13, AP-15, AP-17, AP-18, AP-19, and AP-22.
5. Read owners in `docs/CODEBASE_MAP.md` and relevant sections in `docs/backend-architecture.md`.
6. Grep concept, route, job, schema, and test call sites before moving code.

Hard behavior constraints:

- This is behavior-preserving. Do not change routes, response fields, scoring, workflow states, authorization, audit semantics, report output, selector memory, or LLM activation.
- UCP and page audits remain observational and report-only.
- Enrichment consumes extraction output. Do not add extraction cleanup there.
- Shopify taxonomy/attributes remain the enrichment source of truth.
- Product Intelligence scoring remains deterministic and explainable.
- Runtime tunables stay in existing `app/services/config/*` owners.
- If simplification requires changing a public contract or product workflow, stop and ask the user.

## Scope

Oversized files that must be reduced below 800 physical lines:

- `backend/app/services/product_intelligence/discovery.py` (audit: 1291)
- `backend/app/services/page_audit/analysis.py` (1207)
- `backend/app/services/product_intelligence/service.py` (1154)
- `backend/app/services/design_system.py` (1051)
- `backend/app/services/playground_service.py` (1018)
- `backend/app/services/ucp_audit/protocol_checks.py` (1012)
- `backend/app/services/review/__init__.py` (952)
- `backend/app/services/data_enrichment/shopify_catalog.py` (925)
- `backend/app/services/data_enrichment/deterministic.py` (882)

Complexity scope is all maintained backend production Python not owned by Plans 02 or 03, including:

- `backend/app/api/**`, `backend/app/core/**`, `backend/app/models/**`, `backend/app/schemas/**`, `backend/app/main.py`
- `backend/app/services/product_intelligence/**`
- `backend/app/services/data_enrichment/**`
- `backend/app/services/ucp_audit/**`, `backend/app/services/page_audit/**`
- `backend/app/services/review/**`, `selectors_runtime.py`, selector/domain-memory owners
- Playground, monitor, alert, notification, public API, LLM, reporting, and design-system service owners

Priority hotspots include `_dom_checks` CC 60, `_persist_discovery_job` CC 38, `score_candidate` CC 37, `_apply_llm_payload` CC 35, `_auto_advance` CC 33, `_parse_serpapi_immersive_results` CC 33, selector suggestion/review assembly above 40, taxonomy loading/matching, monitor change detection, report builders, public record shaping, and config default validation.

## Acceptance Criteria

- [ ] Record starting commit, dirty state, scoped LOC, files over 800, and all scoped CC violations in Notes.
- [ ] Every maintained scoped production file is `<=800` physical lines.
- [ ] Every scoped callable has Radon CC `<=15`.
- [ ] Scoped physical LOC is lower than baseline.
- [ ] No route, schema, authorization, persistence, workflow, report, scoring, or user-visible output contract changes.
- [ ] No new cross-cutting layer, parallel config, product taxonomy, private reach-in, or downstream compensation exists.
- [ ] Vulture/jscpd/search leads are validated; confirmed dead/duplicate code is deleted.
- [ ] Focused tests pass per owner and backend safe suite passes.
- [ ] No dependency, workflow, broad-formatting, frontend, extraction, acquisition, or migration changes are included.

## Do Not Touch

- Extraction/adapters/field coercion — Plan 02.
- Acquisition/fetch/crawl/pipeline — Plan 03.
- Backend test-suite decomposition — Plan 01; focused assertions may change only for public ownership moves.
- Frontend — Plan 05.
- Manifests, lockfiles, README package setup, CI workflows — Plans 06–07.
- Database schema or migrations — not needed for structural debt reduction.

## Slices

### Slice 1: Baseline and Owner Partition

**Status:** TODO
**Files:** full scope; canonical docs and tests read-only
**What:** Record exact LOC and numeric Radon CC. Run scoped Vulture/jscpd as leads. Assign every violation to an existing owner. Identify deletions, duplicate transformations, stale compatibility paths, and facade seams. Do not create files until grep proves ownership.
**Verify:** Run current focused tests for every owner selected for editing. Stop if baseline failures prevent comparison.

### Slice 2: Product Intelligence and Enrichment

**Status:** TODO
**Files:** `product_intelligence/**`, `data_enrichment/**`, focused tests
**What:** Separate provider parsing, candidate admission, persistence/orchestration, scoring, taxonomy loading, matching, and attribute diagnostics along existing owners. Delete duplicated parsing/normalization. Preserve deterministic scores, Shopify taxonomy authority, job state, and persistence contracts.
**Verify:** Run Product Intelligence and data-enrichment component/regression tests plus structure tests.

### Slice 3: UCP Audit, Page Audit, and Design-System Service

**Status:** TODO
**Files:** `ucp_audit/**`, `page_audit/**`, `design_system.py`, focused tests
**What:** Convert large check/report functions into small same-owner checks assembled explicitly. Split transport/schema/dimension checks and DOM/source checks by existing concepts. Preserve exact scoring, evidence, report schemas, and report-only isolation.
**Verify:** Run UCP, page-audit, design-system, report-rendering, API, and structure tests.

### Slice 4: Playground, Review, Selectors, Monitors, API, and Remaining Owners

**Status:** TODO
**Files:** remaining scoped CC violators and oversized `playground_service.py` / `review/__init__.py`; focused tests
**What:** Thin workflow and route facades. Move behavior only to existing service owners. Replace large branch sets with explicit same-domain predicates/stages. Delete stale wrappers and duplicate shaping. Preserve authorization, state transitions, selector memory, notifications, webhook behavior, and LLM gating.
**Verify:** Run focused Playground, review, selector, domain-memory, monitor/alert, public API, auth, LLM, and structure tests for touched owners.

### Slice 5: Scoped Metrics and Full Verification

**Status:** TODO
**Files:** all touched files; canonical docs if ownership moved
**What:** Re-run exact LOC, numeric Radon, Vulture 100%, and jscpd. Prove scoped LOC decreased and no violation remains. Run safe suite.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests -q -m "unit or component or regression"`

## Doc Updates Required

- [ ] `docs/CODEBASE_MAP.md` — stable file/owner changes.
- [ ] `docs/backend-architecture.md` — changed subsystem layout.
- [ ] `docs/BUSINESS_LOGIC.md` — only if an approved product decision changes ownership or behavior.
- [ ] `docs/INVARIANTS.md` — only for an explicitly approved contract change.
- [ ] `docs/ENGINEERING_STRATEGY.md` — only for a new recurring anti-pattern.
- [ ] `docs/plans/ACTIVE.md` — active pointer and closeout.

## Notes

- Source evidence: `docs/audits/productionization-evidence-report-2026-08-21.md`, sections 4–7.
- If scope reveals a security/authorization defect, report it. Do not silently mix a behavior-changing security fix into this refactor PR.
- Plan 01 may move tests. Locate current tests with `rg`.


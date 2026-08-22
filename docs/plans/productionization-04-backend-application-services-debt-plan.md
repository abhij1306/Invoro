# Plan: Productionization 04 — Backend Application Services Debt Reduction

**Created:** 2026-08-21
**Agent:** Codex
**Status:** COMPLETE
**PR boundary:** One independent PR. Remaining backend production owners not covered by extraction or acquisition plans.
**Touches buckets:** Product Intelligence, data enrichment, Playground, review/selectors, monitors/alerts, API/bootstrap, LLM, plus complete removal of Design System, UCP Audit, AI Observability, and Page Audit

## Goal

Remove the Design System, UCP Audit, AI Observability, and Page Audit features completely, then reduce debt across remaining backend application services without changing surviving public behavior. Every maintained backend production file in scope must be `<=800` physical lines. Every scoped callable must have cyclomatic complexity `<=15`. Total scoped LOC must decrease. Surviving API contracts, workspace/user isolation, persistence ownership, workflow transitions, reports, and deterministic scoring must stay stable.

## Context for a Fresh Session

Plans 02 and 03 own extraction and acquisition/orchestration. This plan owns all remaining backend production complexity, so no CC violation is left unassigned. The 2026-08-21 audit found nine oversized files here. It also found complex functions in Product Intelligence, enrichment, Playground, review/selectors, monitors, API, LLM, config validation, and report builders. Current code wins over audit counts.

Before code:

1. Read `AGENTS.md`.
2. Read relevant rules in `docs/INVARIANTS.md` for config, user controls, review/domain memory, enrichment, audits, LLM, public APIs, and persistence.
3. Read `docs/BUSINESS_LOGIC.md` for every workflow touched.
4. Read `docs/ENGINEERING_STRATEGY.md` AP-1, AP-2, AP-5, AP-7, AP-13, AP-15, AP-17, AP-18, AP-19, and AP-22.
5. Read owners in `docs/CODEBASE_MAP.md` and relevant sections in `docs/backend-architecture.md`.
6. Grep concept, route, job, schema, and test call sites before moving code.

Hard behavior constraints:

- This is behavior-preserving. Do not change routes, response fields, scoring, workflow states, authorization, audit semantics, report output, selector memory, or LLM activation.
- Design System, UCP Audit, AI Observability, and Page Audit contracts are intentionally removed by explicit user direction.
- Enrichment consumes extraction output. Do not add extraction cleanup there.
- Shopify taxonomy/attributes remain the enrichment source of truth.
- Product Intelligence scoring remains deterministic and explainable.
- Runtime tunables stay in existing `app/services/config/*` owners.
- If simplification requires changing a public contract or product workflow, stop and ask the user.

## Scope

Oversized files that must be reduced below 800 physical lines:

- `backend/app/services/product_intelligence/discovery.py` (audit: 1291)
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
- removed `backend/app/services/ucp_audit/**` and `backend/app/services/page_audit/**`
- `backend/app/services/review/**`, `selectors_runtime.py`, selector/domain-memory owners
- Playground, monitor, alert, notification, public API, LLM, reporting, and design-system service owners

Priority hotspots include `_dom_checks` CC 60, `_persist_discovery_job` CC 38, `score_candidate` CC 37, `_apply_llm_payload` CC 35, `_auto_advance` CC 33, `_parse_serpapi_immersive_results` CC 33, selector suggestion/review assembly above 40, taxonomy loading/matching, monitor change detection, report builders, public record shaping, and config default validation.

## Acceptance Criteria

- [x] Design System is removed from backend and frontend surfaces, runtime/config, prompts, tests, and docs.
- [x] UCP Audit and AI Observability are removed from backend and frontend surfaces, runtime/config, prompts, tests, and docs.
- [x] Page Audit is removed from backend and frontend surfaces, runtime/config, tests, and docs.
- [x] A forward migration removes UCP- and Page-Audit-owned database tables while migration history remains valid.
- [x] Record starting commit, dirty state, scoped LOC, files over 800, and all scoped CC violations in Notes.
- [x] Every maintained scoped production file is `<=800` physical lines.
- [x] Every scoped callable has Radon CC `<=15`.
- [x] Scoped physical LOC is lower than baseline.
- [x] No surviving route, schema, authorization, persistence, workflow, report, scoring, or user-visible output contract changes.
- [x] No new cross-cutting layer, parallel config, product taxonomy, private reach-in, or downstream compensation exists.
- [x] Vulture/jscpd/search leads are validated; confirmed dead/duplicate code is deleted.
- [x] Focused tests pass per owner and backend safe suite passes.
- [x] Only explicit feature-removal frontend/migration changes and the two mypy unblockers (`types-pytz`, test package markers) extend the backend refactor scope.

## Do Not Touch

- Extraction/adapters/field coercion — Plan 02.
- Acquisition/fetch/crawl/pipeline — Plan 03.
- Backend test-suite decomposition — Plan 01; focused assertions may change only for public ownership moves.
- Frontend except references required to remove Design System, UCP Audit, AI Observability, and Page Audit — remaining frontend debt belongs to Plan 05.
- Manifests, lockfiles, README package setup, CI workflows — Plans 06–07.
- Database schema except the forward migration required to remove UCP- and Page-Audit-owned tables.

## Slices

### Slice 0: Remove Design System, UCP Audit, and AI Observability

**Status:** DONE
**Files:** feature-owned backend/frontend modules, integrations, tests, docs, and one forward migration
**What:** Delete all three feature implementations and remove their route, runtime, config, prompt, navigation, client, schema, persistence, and test references. Preserve generic crawl diagnostics needed by surviving runtime behavior; remove only observability-owned trace/audit behavior. Keep historical migrations and add a forward drop migration for UCP tables.
**Verify:** Repository search has no live feature references; focused backend and frontend structure/type tests pass.

### Slice 1: Baseline and Owner Partition

**Status:** DONE
**Files:** full scope; canonical docs and tests read-only
**What:** Record exact LOC and numeric Radon CC. Run scoped Vulture/jscpd as leads. Assign every violation to an existing owner. Identify deletions, duplicate transformations, stale compatibility paths, and facade seams. Do not create files until grep proves ownership.
**Verify:** Run current focused tests for every owner selected for editing. Stop if baseline failures prevent comparison.

### Slice 2: Product Intelligence and Enrichment

**Status:** DONE
**Files:** `product_intelligence/**`, `data_enrichment/**`, focused tests
**What:** Separate provider parsing, candidate admission, persistence/orchestration, scoring, taxonomy loading, matching, and attribute diagnostics along existing owners. Delete duplicated parsing/normalization. Preserve deterministic scores, Shopify taxonomy authority, job state, and persistence contracts.
**Verify:** Run Product Intelligence and data-enrichment component/regression tests plus structure tests.

### Slice 3: Removed-Feature Follow-up

**Status:** DONE
**Files:** Page Audit backend/frontend modules, integrations, tests, docs, and the forward removal migration
**What:** Remove Page Audit after the user added it to the explicit removal scope. Keep historical migrations and extend the forward removal migration to drop Page Audit tables.
**Verify:** Repository search has no live Page Audit references; backend structure and frontend type tests pass.

### Slice 4: Playground, Review, Selectors, Monitors, API, and Remaining Owners

**Status:** DONE
**Files:** remaining scoped CC violators and oversized `playground_service.py` / `review/__init__.py`; focused tests
**What:** Thin workflow and route facades. Move behavior only to existing service owners. Replace large branch sets with explicit same-domain predicates/stages. Delete stale wrappers and duplicate shaping. Preserve authorization, state transitions, selector memory, notifications, webhook behavior, and LLM gating.
**Verify:** Run focused Playground, review, selector, domain-memory, monitor/alert, public API, auth, LLM, and structure tests for touched owners.

### Slice 5: Scoped Metrics and Full Verification

**Status:** DONE
**Files:** all touched files; canonical docs if ownership moved
**What:** Re-run exact LOC, numeric Radon, Vulture 100%, and jscpd. Prove scoped LOC decreased and no violation remains. Run safe suite.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests -q -m "unit or component or regression"`

## Doc Updates Required

- [x] `docs/CODEBASE_MAP.md` — stable file/owner changes.
- [x] `docs/backend-architecture.md` — changed subsystem layout.
- [x] `docs/BUSINESS_LOGIC.md` — removed deleted feature behavior.
- [x] `docs/INVARIANTS.md` — removed deleted feature contracts.
- [x] `docs/ENGINEERING_STRATEGY.md` — no update required; no new recurring anti-pattern.
- [x] `docs/plans/ACTIVE.md` — active pointer and closeout.

## Notes

- Source evidence: `docs/audits/productionization-evidence-report-2026-08-21.md`, sections 4–7.
- If scope reveals a security/authorization defect, report it. Do not silently mix a behavior-changing security fix into this refactor PR.
- Plan 01 may move tests. Locate current tests with `rg`.
- Started 2026-08-22 at commit `4b81812e5620c923c55d9d52e0acaab3ec64560c`; working tree clean.
- Baseline scope: 193 production Python files, 42,978 physical lines, 9 files over 800 physical lines, and 57 callable Radon CC violations above 15. Baseline includes the three user-directed removal features.
- Baseline Vulture 100% lead: unused `__context` in `app/services/export/schema.py`; validate before deletion.
- Slice 0 done 2026-08-22. Removed Design Crawl/Design System, UCP Audit/AI Discoverability, and Run Trace/AI Observability across backend, frontend, prompts, config, tests, and canonical docs. Preserved generic browser diagnostic artifacts under `artifact_store.py`. Added Alembic head `20260822_0010` to drop UCP tables. Backend focused verification passed 41 tests; frontend focused verification passed 49 tests; frontend typecheck passed.
- Slice 1 done 2026-08-22. Owner baseline recorded above. Vulture lead recorded. Post-removal jscpd lead scan analyzed 425 files / 108,681 lines and found 0 clones.
- User expanded removal scope on 2026-08-22. Slice 3 removed Page Audit across backend, frontend, config, models, schemas, tests, and canonical docs; migration `20260822_0010` now drops both UCP Audit and Page Audit tables.
- Slices 2 and 4 completed 2026-08-22. Product Intelligence, enrichment, Playground, review, selectors, monitors, public shaping, LLM, export, and shared-policy hotspots were split along existing ownership seams. Deterministic scoring, persistence, authorization, workflow transitions, and surviving API contracts remain covered by focused and full-suite tests.
- Final scope: 138 production Python files and 27,843 physical lines, down 55 files and 15,135 lines from baseline. Zero maintained scoped files exceed 800 physical lines; the largest is `product_intelligence/matching.py` at 799. Numeric Radon reports zero scoped callables above CC 15. Vulture at 100% reports no confirmed dead code; duplicate-code leads were reviewed as structural/mechanical rather than competing owners.
- Verification: backend focused owner tests passed (226); backend structure tests passed (29); backend safe suite passed (2,296 passed, 19 skipped, 12 deselected); Ruff and mypy passed across 494 source files; frontend Vitest passed (170), typecheck passed, and full lint/architecture checks passed. Alembic reports `20260822_0010` as the single head.

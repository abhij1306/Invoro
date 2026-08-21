# Plan: Productionization 02 — Extraction Debt Reduction

**Created:** 2026-08-21
**Agent:** Codex
**Status:** QUEUED — set to `IN PROGRESS` only when this plan is assigned
**PR boundary:** One independent PR. Deterministic extraction and canonical field normalization only.
**Touches buckets:** Extraction, adapters, DOM/selector extraction, JS state, field coercion

## Goal

Reduce deterministic extraction debt without changing observable extraction behavior. Every maintained file in this ownership scope must be `<=800` physical lines. Every scoped callable must have cyclomatic complexity `<=15`. Total scoped LOC must decrease. Existing extraction priority, provenance, flat public variants, field-quality rules, and LLM gating must remain unchanged.

## Context for a Fresh Session

The 2026-08-21 audit found 11 oversized extraction files and the largest backend complexity hotspots. High-risk examples include `coerce_field_value` CC 96, `looks_like_site_shell_record` CC 86, `collect_structured_candidates` CC 85, `apply_dom_fallbacks` CC 68, and `iter_variant_choice_groups` CC 63. Current code wins over audit counts. Re-measure only this scope before editing.

Before code:

1. Read `AGENTS.md`.
2. Read `docs/INVARIANTS.md` Rules 1–5 and 7, plus all extraction/variant/public-record rules.
3. Read `docs/ENGINEERING_STRATEGY.md` AP-2, AP-5, AP-7, AP-9, AP-12, AP-13, AP-15, AP-17, AP-19, and AP-20.
4. Read the Extraction bucket in `docs/CODEBASE_MAP.md` and the extraction section in `docs/backend-architecture.md`.
5. Grep each concept and call site before creating or moving a symbol.

Hard behavior constraints:

- Keep source order: adapter -> structured/network/JS evidence -> DOM -> explicit LLM gap fill.
- Keep field-by-field candidate arbitration. Do not create record-level winner logic.
- Preserve all explicit user controls and `llm_enabled` gating.
- Keep extraction fixes upstream. Do not touch publish, persistence, export, or UI.
- Preserve flat public variant output and field provenance.
- Do not add site-specific branches to generic paths.
- Move runtime config only to an existing owner under `app/services/config/*`.
- If simplification changes which value wins, whether a record is admitted, or public output shape, stop and ask the user. That is a product decision.

## Scope

Oversized files that must be reduced below 800 physical lines:

- `backend/app/services/extract/detail/identity/core.py` (audit: 1286)
- `backend/app/services/extract/detail/variants/dom_extraction.py` (1185)
- `backend/app/services/extract/detail/text/sanitizer.py` (1123)
- `backend/app/services/shared/field_coerce.py` (1052)
- `backend/app/services/extract/detail/price/core.py` (1029)
- `backend/app/services/adapters/belk.py` (1021)
- `backend/app/services/adapters/shopify.py` (974)
- `backend/app/services/extract/variant_choice_traversal.py` (925)
- `backend/app/services/dom/selector_engine.py` (826)
- `backend/app/services/listing_extractor.py` (820)
- `backend/app/services/extract/listing_candidate_ranking.py` (808)

Complexity scope includes all maintained Python under:

- `backend/app/services/extract/**`
- `backend/app/services/adapters/**`
- `backend/app/services/js_state/**`
- `backend/app/services/dom/**`
- extraction-facing modules such as `listing_extractor.py`, `detail_extractor.py`, `crawl_engine.py`, `structured_sources.py`, `network_payload_mapper.py`, and `content_surface_extractor.py`
- canonical public-field coercion modules under `backend/app/services/shared/field_coerce*`

Priority non-oversized hotspots include `extract/field_candidates/structured_payloads.py`, `extract/detail/identity/shell_filter.py`, `extract/detail/assembly/dom_fallbacks.py`, `extract/field_candidates/variant_rows.py`, `extract/detail/variants/state_targets.py`, and `js_state/variant_options.py`.

## Acceptance Criteria

- [ ] Record starting commit, dirty state, scoped physical LOC, files over 800, and all scoped CC violations in Notes.
- [ ] Every maintained scoped source file is `<=800` physical lines.
- [ ] Every scoped callable has Radon CC `<=15`.
- [ ] Scoped physical LOC is lower than baseline.
- [ ] Existing public facades and import paths stay stable unless all callers move in the same slice and stale shims are deleted.
- [ ] No new cross-cutting helper layer, parallel config source, private cross-module reach-in, or downstream compensation exists.
- [ ] Confirmed dead code and exact duplicate logic found by scoped Vulture/jscpd/search are deleted after call-site validation.
- [ ] Focused contract tests pass after each slice.
- [ ] Extraction smoke and backend safe suite pass before PR readiness.
- [ ] No dependency, workflow, broad formatting, frontend, persistence, or migration changes are included.

## Do Not Touch

- `backend/app/services/acquisition/**`, `fetch/**`, `crawl/**`, `pipeline/**` — Plan 03.
- Product Intelligence, enrichment, audits, Playground, review, monitors, API/bootstrap — Plan 04.
- `backend/tests/**` structural decomposition — Plan 01. Focused assertion edits are allowed only when required by moved public ownership.
- `backend/app/services/publish/**`, `pipeline/persistence.py`, exports — no downstream compensation.
- `frontend/**`, dependency manifests/lockfiles, `.github/workflows/**` — Plans 05–07.

## Slices

### Slice 1: Baseline, Contracts, and Deletion Map

**Status:** TODO
**Files:** scope above; relevant tests read-only
**What:** Capture exact LOC and numeric Radon CC. Run Vulture at 100% confidence and scoped jscpd as leads. Grep every candidate before deletion. Map each oversized file into existing domain concepts and list lines expected to be deleted, not merely moved.
**Verify:** Run current focused extraction tests before edits and record results. If baseline fails, stop and document it.

### Slice 2: Canonical Field Coercion and Detail Identity

**Status:** TODO
**Files:** `shared/field_coerce*`, `extract/detail/identity/**`, public facades, focused field/identity tests
**What:** Keep dispatcher and public boundary stable. Move per-field branches only into existing field-coercion owners. Split identity by established concepts. Replace giant predicate chains with named same-package predicates. Delete duplicated cleanup and private reach-ins. Preserve rejection/admission results.
**Verify:** Run field-value, listing-identity, structured-source, crawl-engine, and structure regression tests located by `rg`.

### Slice 3: Detail Variants, Price, and Text

**Status:** TODO
**Files:** `extract/detail/variants/**`, `extract/variant_choice_traversal.py`, `extract/detail/price/**`, `extract/detail/text/**`, candidate/assembly modules, focused tests
**What:** Split DOM variant axis discovery, target selection, option walking, backfill, price reconciliation, and long-text policy along existing package owners. Preserve per-field arbitration, source priority, DOM completion, flat variants, and public-field rules. Delete duplicate normalization rather than wrapping it.
**Verify:** Run variant, price, long-text, structured-source, expansion, and extraction structure tests.

### Slice 4: Structured Candidates, Listing, DOM, and Adapters

**Status:** TODO
**Files:** field-candidate modules, `listing_extractor.py`, listing ranking, DOM selector engine, `belk.py`, `shopify.py`, JS-state modules, focused tests
**What:** Separate payload-shape collectors and listing admission/ranking predicates inside their current owners. Keep adapters site-specific and generic paths generic. Thin adapter entry points by reusing canonical normalization; delete duplicate adapter cleanup. Preserve selector and adapter behavior.
**Verify:** Run listing, adapter, JS-state, Selectolax, selector, and crawl-engine focused suites.

### Slice 5: Scoped Metrics and Full Verification

**Status:** TODO
**Files:** all touched extraction files; owner docs if file ownership moved
**What:** Re-run exact LOC, numeric Radon CC, Vulture 100%, and jscpd. Validate every deletion. Prove scoped LOC decreased and no file/callable violates the target. Run smoke and safe suite.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe run_extraction_smoke.py`; then `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests -q -m "unit or component or regression"`

## Doc Updates Required

- [ ] `docs/CODEBASE_MAP.md` — update stable file ownership for moved responsibilities.
- [ ] `docs/backend-architecture.md` — update extraction module layout only where ownership changed.
- [ ] `docs/INVARIANTS.md` — no change unless a product decision is explicitly approved.
- [ ] `docs/ENGINEERING_STRATEGY.md` — only for a newly confirmed recurring anti-pattern.
- [ ] `docs/plans/ACTIVE.md` — set active at start; clear/advance after all verification passes.

## Notes

- Source evidence: `docs/audits/productionization-evidence-report-2026-08-21.md`, especially sections 4–7.
- Plan 01 may move test paths. Use `rg` to find the current public-contract tests; do not restore superseded test files.
- Do not expand browser interaction to simplify extraction. Browser behavior is outside this PR.


# Plan: Productionization 01 — Backend Test and Tooling Debt

**Created:** 2026-08-21
**Agent:** Codex
**Status:** IN PROGRESS
**PR boundary:** One independent PR. Test and diagnostic-tooling structure only.
**Touches buckets:** Backend tests, browser-surface probe, acceptance harness, JSON audit tooling

## Goal

Make first-party backend tests and diagnostic tools comply with physical LOC `<=800` and per-callable cyclomatic complexity `<=15`. Reduce total scoped LOC. Preserve test coverage, collection, marker behavior, CLI behavior, and production code. This is debt removal, not a test rewrite or product change.

## Context for a Fresh Session

The 2026-08-21 productionization audit found 21 backend test files and 4 backend/tooling files above 800 physical lines. Radon also found complexity above 15 in tests and tooling. The audit did not run the full test suite. Current repository evidence wins over these counts. Re-measure this scope before editing.

Required rules:

- Read `AGENTS.md`, `docs/ENGINEERING_STRATEGY.md` AP-7/AP-14/AP-15 and Testing Rules, then this plan.
- Tests must assert public behavior. Delete private-function coupling when equivalent public-contract coverage exists.
- Split by behavior/source family. Never create `_misc`, `_helpers2`, or numbered dump modules.
- Shared fixtures are allowed only for identical setup. Do not hide scenario intent behind a test framework.
- Do not change application behavior to make tests easier.
- Do not change dependencies, workflows, lint config, or production modules in this PR.
- Physical LOC across scoped `.py` files must be lower after the PR. Moving lines without deletion is insufficient.

## Oversized Inventory to Eliminate

All listed files must end at 800 physical lines or fewer. New files must also stay at 800 or fewer.

| Area | Files |
|---|---|
| Extraction regression | `backend/tests/regression/test_detail_extractor_structured_sources.py` (9379), `test_crawl_engine.py` (6753), `test_selectolax_css_migration.py` (2723), `test_detail_extractor_priority_and_selector_self_heal.py` (933) |
| Acquisition/fetch | `backend/tests/regression/test_browser_expansion_runtime.py` (6245), `backend/tests/component/test_crawl_fetch_runtime.py` (3753), `test_browser_context.py` (3322), `test_traversal_runtime.py` (1970) |
| Pipeline/crawl | `backend/tests/regression/test_pipeline_core.py` (4032), `test_batch_runtime.py` (1570), `backend/tests/component/test_crawl_service.py` (1304), `test_sitemap_resolver.py` (923) |
| Product workflows/API | `backend/tests/component/test_product_intelligence.py` (3211), `test_public_api.py` (1096), `backend/tests/regression/test_data_enrichment.py` (1052), `backend/tests/component/test_playground_service.py` (957) |
| Extraction unit | `backend/tests/unit/test_state_mappers.py` (2028), `test_normalizers.py` (1636), `test_field_value_core.py` (1153), `test_shared_variant_logic.py` (1125) |
| Harness | `backend/tests/regression/test_harness_support.py` (1290) |
| Tooling | `backend/browser_surface_probe/core.py` (2178), `backend/harness/support.py` (1658), `agent_debug/run_json_issue_audit.py` (1497), `backend/run_json_issue_audit.py` (827) |

The two JSON audit scripts appear duplicative. Grep both call sites and imports. Consolidate to one canonical implementation and keep only a thin entry point if two invocation paths are required. Delete redundant logic.

## Acceptance Criteria

- [x] Record starting commit, dirty state, scoped physical LOC, files over 800, and Radon callables over 15 in Notes.
- [x] Every maintained backend test/tooling `.py` file is `<=800` physical lines.
- [x] Every callable in `backend/tests`, `backend/browser_surface_probe`, `backend/harness`, `backend/run_*.py`, and `agent_debug/*.py` has Radon CC `<=15`.
- [x] Scoped physical LOC is lower than the recorded baseline.
- [x] No test is duplicated into multiple files merely to satisfy the gate.
- [x] Public-contract coverage remains; obsolete and private-coupled assertions are deleted where safe.
- [x] Existing pytest markers, fixture discovery, CLI arguments, output contracts, and exit codes remain stable.
- [x] No production file under `backend/app` changes.
- [x] Focused verification passes after each slice.
- [ ] Backend safe suite exits 0 before the PR is ready.

## Do Not Touch

- `backend/app/**` — production behavior belongs to Plans 02–04.
- `frontend/**` — frontend debt belongs to Plan 05.
- `backend/pyproject.toml`, lockfiles, `.github/workflows/**` — dependencies and gates belong to Plans 06–07.
- `backend/tests/regression/test_structure.py` budget policy — absolute gate ownership belongs to Plan 07. It may be run, not weakened.
- Product behavior, public schemas, persistence, migrations, extraction priority, browser policy — out of scope.

## Slices

### Slice 1: Baseline and Collection Contract

**Status:** DONE
**Files:** scoped files above; pytest configuration read-only
**What:** Capture exact physical LOC and numeric Radon CC. Run pytest collection and record collected counts by relevant path. Grep private imports and repeated fixture/helper bodies. Define destination modules by behavior family before moving code.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest --collect-only -q`

### Slice 2: Extraction Test Decomposition

**Status:** DONE
**Files:** extraction regression/unit files from the inventory; new focused test modules under the same test tier
**What:** Split by JSON-LD, JS state, network, DOM, adapters, selectors, identity, variant, price, and normalizer contracts. Keep test tier and markers. Delete assertions tied only to private implementation order. Remove repeated payload builders only when they are truly identical.
**Verify:** Run the moved extraction test directories/files plus `tests/regression/test_structure.py`; compare collection counts and meaningful scenario coverage with Slice 1.

### Slice 3: Acquisition, Crawl, Pipeline, and Workflow Test Decomposition

**Status:** DONE
**Files:** acquisition/fetch, pipeline/crawl, Product Intelligence, public API, enrichment, Playground, and sitemap test files from the inventory
**What:** Split by observable contract and owner. Keep component/regression tier unchanged. Reduce monolithic end-to-end test complexity using named scenario steps only when failure locality improves.
**Verify:** Run every destination module created in this slice plus its original owning test path where still present.

### Slice 4: Diagnostic Tooling Consolidation

**Status:** DONE
**Files:** `backend/browser_surface_probe/**`, `backend/harness/**`, both JSON audit entry points, their tests
**What:** Keep CLI entry points thin. Move probe finding construction, harness parsing/classification, and JSON audit scanners to existing owning packages. Consolidate the duplicate JSON audit implementation. Preserve flags, report schemas, and exit behavior. Reduce every callable to CC 15 or less.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/regression/test_harness_support.py -q -m regression`; run each touched CLI with `--help` and its smallest offline fixture path.

### Slice 5: Scoped Gates and Full Verification

**Status:** IN PROGRESS
**Files:** all touched test/tooling files; plan Notes
**What:** Re-run physical LOC and Radon using the same baseline method. Prove scoped LOC decreased. Run collection comparison, structure regression, and safe suite. Do not add permanent CI gates here.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/regression/test_structure.py -q -m regression`; then `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests -q -m "unit or component or regression"`

## Doc Updates Required

- [ ] `docs/CODEBASE_MAP.md` — only if a first-party diagnostic-tool owner moves; test-only moves need no map entry.
- [ ] `docs/ENGINEERING_STRATEGY.md` — only if a new recurring test anti-pattern is confirmed.
- [ ] `docs/INVARIANTS.md` — no change expected; this plan cannot change runtime contracts.
- [ ] `docs/plans/ACTIVE.md` — set this plan active at start and clear/advance it only after verification.

## Notes

- Source evidence: `docs/audits/productionization-evidence-report-2026-08-21.md`, sections 4–6. It is forensic input, not authority over current code.
- If a production defect is exposed, record it and stop. Do not fix production code in this PR.
- If another plan already split a named test, locate the replacement with `rg`; enforce the same scope outcomes without restoring old files.
- 2026-08-21 baseline: commit `133ecfb`; worktree clean; branch `chore/test-tooling-debt` created from `main`.
- Baseline scope: 173 Python files, 90,633 physical LOC, 25 files over 800 lines.
- Baseline collection: 2,452 items collected; 17 deselected; 2,435 selected; exit 0.
- Baseline Radon `-n D`: 11 callables above CC 15. Tests: `test_crawls_domain_recipe_routes_round_trip` (50), `test_split_reset_crawl_data_and_domain_memory_preserve_the_other_scope` (25), `test_monitor_api_end_to_end_with_monitor_form_settings` (62), `test_extract_ecommerce_detail_returns_normalized_record` (23), and `test_map_js_state_to_fields_recovers_next_data_shopify_product_fields` (23). Tooling: `build_findings` (78), `_target_root_cause` (26), `infer_surface` (45), `classify_failure_mode` (43), `_observed_quality_failure_mode` (37), and `load_site_set` (29).
- Slice 1 collection contract preserved at 2,452 items before the AP-7 deletion.
- Slice 2 focused extraction/unit verification: 1,104 passed, 19 artifact-dependent skips, 7 deselected. One private-helper test was deleted; equivalent public DOM variant behavior remains covered.
- Slice 3 focused acquisition/crawl/pipeline/workflow verification: 711 passed, 13 deselected. High-CC API scenarios also passed in the focused tooling run.
- Slice 4 focused browser/harness verification: 66 passed. Browser probe, acceptance harness, and JSON audit `--help` commands passed; JSON audit also completed against a minimal offline record with exit 0.
- Final local gates: structure regression 30 passed; collection 2,459 items, 11 deselected, 2,448 selected; scoped LOC 89,553 across 277 files (down 1,080 from baseline); zero files over 800; zero Radon callables over 15; targeted Ruff and compile checks passed. The 14 additional selected tests are six repaired test names/markers and eight new tooling regressions.
- Follow-up review findings were verified. Two assertion-only requests were not applied: current extraction does not retain adapter `variant_axes`/`selected_variant` in the named deep-merge scenarios, so those assertions would require an out-of-scope `backend/app` behavior fix. All other still-valid findings were fixed in test/tooling scope.
- The backend safe suite remains for required CI per the `ship-main` workflow.

# Plan: God Module Consolidation & Dead Code Reduction

**Created:** 2026-05-12
**Revised:** 2026-05-12
**Status:** PAUSED / NEXT QUEUED
**Touches buckets:** Acquisition (3), Extraction (4), Shared field coercion, Config, Structure tests

## Goal

Reduce god modules and dead compatibility surfaces without changing behavior.

This is an incremental refactor plan. Each slice is one structural transformation, verified before the next slice starts. If a slice cannot be verified cleanly, stop and shrink the slice.

Current large-file pressure:

- **Acquisition cluster:** `browser_runtime.py` (1853), `traversal.py` (1790), `browser_page_flow.py` (1709), `browser_identity.py` (1529)
- **Extraction/config cluster:** `shared_variant_logic.py` (1443), `detail_dom_extractor.py` (1355), `detail_materializer.py` (1301), `config/extraction_rules.py` (1759)
- **Facade shims:** `crawl_fetch_runtime.py`, `field_value_core.py`, `field_value_dom.py`, `js_state_mapper.py` are `sys.modules` redirects from an old migration

Current facade caller counts from `rg`:

- `app.services.crawl_fetch_runtime`: 5 files
- `app.services.field_value_core`: 72 files
- `app.services.field_value_dom`: 11 files
- `app.services.js_state_mapper`: 3 files

## Done Looks Like

- Net deleted LOC >= 400 across `backend/app/services`
- God-module LOC moved or reduced >= 1,300 from the listed large files
- Each extracted module has one obvious responsibility and stays below 300 LOC unless justified
- Dead facades deleted or explicitly retained with current ownership documented
- `backend/tests/services/test_structure.py` budgets ratcheted to new baselines
- `docs/CODEBASE_MAP.md` matches actual ownership and import rules
- Smallest relevant verify passes after every slice; broad `pytest tests -q` passes before marking plan done

## Refactoring Rules

- No behavior changes. No extraction logic changes. No new features.
- One transformation per slice: remove dead code, inline, move function, extract function/module, or rename ownership.
- Grep before adding or moving code.
- Prefer deleting or inlining before extracting.
- Do not create `_helpers.py`, `_utils.py`, `_v2.py`, or broad shared layers.
- Do not import private underscore names across modules. If moved code needs callers, expose a real public API.
- If a planned extraction no longer looks high-value after inspection, skip it and record why.
- If new ownership is unclear, stop and update the plan before editing code.

## Do Not Touch

- `detail_extractor.py` candidate system.
- `config/platforms.json`.
- Frontend code.
- Runtime behavior, crawl semantics, selector semantics, LLM gating, persistence, or export contracts.

## Baseline Slice: Re-measure and Ratchet Plan Facts

**Status:** TODO
**Files:** `docs/plans/god-module-consolidation-plan.md`, no service code

**What:**
- Re-run LOC and caller-count commands.
- Confirm each proposed slice still targets a real high-impact smell.
- Update this plan if current code differs from assumptions.

**Verify:**
```powershell
rg "app\.services\.(crawl_fetch_runtime|field_value_core|field_value_dom|js_state_mapper)" backend
Get-ChildItem backend\app\services -Recurse -Filter *.py | % { "$($_.FullName):$((Get-Content $_.FullName | Measure-Object -Line).Lines)" }
```

## Slice 1: Delete `js_state_mapper.py` facade

**Status:** TODO
**Transformation:** Rename/move public import path callers, then remove dead facade.
**Files:** `js_state_mapper.py`, callers, `docs/CODEBASE_MAP.md`, `test_structure.py`

**What:**
- Rewrite 3 current callers to `app.services.js_state.state_normalizer`.
- Delete `backend/app/services/js_state_mapper.py`.
- Remove stale code map ownership for `js_state_mapper.py`.
- Remove related budget or facade allowlist entries.

**Verify:**
```powershell
cd backend
$env:PYTHONPATH='.'
.\.venv\Scripts\python.exe -m pytest tests\services\test_state_mappers.py tests\services\test_crawl_engine.py tests\services\test_structure.py -q
rg "app\.services\.js_state_mapper" .
```

## Slice 2: Delete `crawl_fetch_runtime.py` facade only if ownership moves cleanly

**Status:** TODO
**Transformation:** Rename/move public import path callers, then remove dead facade.
**Files:** `crawl_fetch_runtime.py`, `fetch/fetch_context.py`, callers, `docs/CODEBASE_MAP.md`, `test_structure.py`

**What:**
- Inspect `fetch_context.py` public API first.
- Rewrite 5 current callers to the real owner if the API is stable.
- Delete `backend/app/services/crawl_fetch_runtime.py`.
- Update `docs/CODEBASE_MAP.md`: remove old import rule or replace it with the real fetch-context owner.
- If fetch behavior still needs a stable top-level facade, stop and mark this facade retained instead of forcing deletion.

**Verify:**
```powershell
cd backend
$env:PYTHONPATH='.'
.\.venv\Scripts\python.exe -m pytest tests\services\test_block_detection.py tests\services\test_structure.py -q
rg "app\.services\.crawl_fetch_runtime" .
```

## Slice 3: Delete `field_value_dom.py` facade

**Status:** TODO
**Transformation:** Rename/move public import path callers, then remove dead facade.
**Files:** `field_value_dom.py`, `dom/selector_engine.py`, callers, `docs/CODEBASE_MAP.md`, `test_structure.py`

**What:**
- Rewrite 11 current callers to `app.services.dom.selector_engine`.
- Delete `backend/app/services/field_value_dom.py`.
- Update code map ownership so DOM selector/extractability APIs point at `dom/selector_engine.py`.

**Verify:**
```powershell
cd backend
$env:PYTHONPATH='.'
.\.venv\Scripts\python.exe -m pytest tests\services\test_field_value_dom.py tests\services\test_field_value_dom_regressions.py tests\services\test_normalizers.py tests\services\test_structure.py -q
rg "app\.services\.field_value_dom" .
```

## Slice 4: Delete `field_value_core.py` facade in batches

**Status:** TODO
**Transformation:** Rename/move public import path callers, then remove dead facade.
**Files:** `field_value_core.py`, `shared/field_coerce.py`, callers, `docs/CODEBASE_MAP.md`, `test_structure.py`

**What:**
- Rewrite current 72 caller files to `app.services.shared.field_coerce`.
- Do this as mechanical import-only batches by bucket: acquisition, adapters, extraction, pipeline/publish, tests.
- Run focused tests after each batch.
- Delete `backend/app/services/field_value_core.py` only after `rg` shows zero callers.
- Update code map: canonical public field coercion owner is `shared/field_coerce.py`.

**Verify:**
```powershell
cd backend
$env:PYTHONPATH='.'
.\.venv\Scripts\python.exe -m pytest tests\services\test_field_value_core.py tests\services\test_normalizers.py tests\services\test_structure.py -q
rg "app\.services\.field_value_core" .
```

## Slice 5: `browser_runtime.py` storage-state extraction

**Status:** TODO
**Transformation:** Move cohesive functions to one owner module.
**Files:** `acquisition/browser_runtime.py` -> `acquisition/browser_storage_state.py`

**What:**
- Before editing, grep storage-state function names and read all callers.
- Move only the storage-state concern:
  `_persist_context_storage_state`, `_load_storage_state_for_run`, `_load_storage_state_for_domain`, `_persist_storage_state_for_run`, `_persist_storage_state_for_domain`, `_mark_storage_state_persist_policy`.
- Expose non-underscore APIs only if cross-module callers need them.
- Keep runtime policy/config imports unchanged.

**Verify:**
```powershell
cd backend
$env:PYTHONPATH='.'
.\.venv\Scripts\python.exe -m pytest tests\services\test_structure.py -q
.\.venv\Scripts\python.exe -m pytest tests -q
```

## Slice 6: `browser_runtime.py` readiness/classification move

**Status:** TODO
**Transformation:** Move cohesive functions to existing owner.
**Files:** `acquisition/browser_runtime.py`, `acquisition/browser_readiness.py`

**What:**
- Move browser readiness and low-content classification only if they fit `browser_readiness.py`.
- Do not mix popup guard, storage state, or identity logic into this slice.
- Avoid private cross-module imports; promote needed calls to public names.

**Candidate functions:**
- `wait_for_listing_readiness`
- `_wait_for_listing_readiness`
- `probe_browser_readiness`
- `listing_card_signal_count`
- `detail_readiness_hint_count`
- `classify_browser_outcome`
- `looks_like_low_content_shell`
- `classify_low_content_reason`

**Verify:**
```powershell
cd backend
$env:PYTHONPATH='.'
.\.venv\Scripts\python.exe -m pytest tests\services\test_structure.py -q
.\.venv\Scripts\python.exe run_acquire_smoke.py commerce
```

## Slice 7: `browser_runtime.py` popup guard cleanup

**Status:** TODO
**Transformation:** Remove dead code or move cohesive functions.
**Files:** `acquisition/browser_runtime.py`, maybe `acquisition/browser_page_flow.py`

**What:**
- Grep every popup helper first.
- Delete unused helpers.
- Move popup guard only if consumed by page-flow code and ownership is clearer there.
- Inline trivial single-use utilities where it reduces indirection.

**Candidate functions:**
- `_install_popup_guard`
- `_remove_popup_guard`
- `_schedule_popup_close`
- `_close_unexpected_popup`
- `_elapsed_ms`
- `_emit_browser_event`
- `_normalize_surface`
- `_mapping_value`
- `_snapshot_count`
- `_int_or_zero`

**Verify:**
```powershell
cd backend
$env:PYTHONPATH='.'
.\.venv\Scripts\python.exe -m pytest tests\services\test_structure.py -q
.\.venv\Scripts\python.exe run_acquire_smoke.py commerce
```

## Slice 8: `traversal.py` card-counting/progress extraction

**Status:** TODO
**Transformation:** Move cohesive functions to one owner module.
**Files:** `acquisition/traversal.py` -> `acquisition/traversal_card_counting.py`

**What:**
- Extract only card-counting and progress-snapshot logic.
- Keep traversal orchestration in `traversal.py`.
- Keep listing fragment rules in `extract/listing_card_fragments.py`; do not duplicate them.

**Candidate functions:**
- `count_listing_cards`
- `_card_count`
- `_heuristic_card_count`
- `_unique_listing_card_identity_count_from_html`
- `_listing_card_identity`
- `_page_snapshot`
- `_snapshot_progressed`
- `_paginate_snapshot_progressed`
- `_is_marginal_card_gain`
- `_paginate_fragment_budget_reached`
- `_target_record_limit_reached`
- `_content_signature`

**Verify:**
```powershell
cd backend
$env:PYTHONPATH='.'
.\.venv\Scripts\python.exe -m pytest tests\services\test_structure.py -q
.\.venv\Scripts\python.exe run_acquire_smoke.py commerce
```

## Slice 9: `browser_page_flow.py` interstitial extraction

**Status:** TODO
**Transformation:** Move cohesive functions to one owner module.
**Files:** `acquisition/browser_page_flow.py` -> `acquisition/browser_interstitial.py`

**What:**
- Extract location interstitial detection/dismissal only.
- Keep page navigation flow in `browser_page_flow.py`.
- Do not add new browser interaction behavior.

**Candidate functions:**
- `location_interstitial_detected`
- `_page_might_have_location_interstitial`
- `dismiss_safe_location_interstitial`
- `_dismiss_location_interstitial_by_text`

**Verify:**
```powershell
cd backend
$env:PYTHONPATH='.'
.\.venv\Scripts\python.exe -m pytest tests\services\test_structure.py -q
.\.venv\Scripts\python.exe run_acquire_smoke.py commerce
```

## Slice 10: `browser_identity.py` client-hint consolidation

**Status:** TODO
**Transformation:** Inline/remove/consolidate duplicate functions.
**Files:** `acquisition/browser_identity.py`

**What:**
- Grep each client-hint helper and identify public behavior boundaries.
- Inline single-use helpers only where the body is clearer at call site.
- Consolidate only duplicated rules, not merely similar-looking logic.
- Add/adjust focused tests if behavior is not already pinned.

**Candidate functions:**
- `_repair_incoherent_client_hints`
- `_strip_incoherent_client_hints`
- `_coherent_client_hints_from_user_agent`
- `_coherent_sec_ch_headers`
- `_should_replace_client_hint_headers`
- `_sec_ch_ua_major_versions`
- `_drop_sec_ch_headers`

**Verify:**
```powershell
cd backend
$env:PYTHONPATH='.'
.\.venv\Scripts\python.exe -m pytest tests\services\test_structure.py -q
.\.venv\Scripts\python.exe run_acquire_smoke.py commerce
```

## Slice 11: `shared_variant_logic.py` dead code and duplicate-rule audit

**Status:** TODO
**Transformation:** Remove dead code, inline single-use helpers, consolidate duplicate conditions.
**Files:** `extract/shared_variant_logic.py`

**What:**
- Audit all exported names and private helpers with `rg`.
- Delete truly unreferenced private helpers.
- Keep behavior identical. Add characterization tests before any non-obvious simplification.
- Do not redesign detail candidate arbitration or variant DOM cue collection.

**Candidate checks:**
- `_is_sequential_integer_run`
- `_select_option_values_are_noise`
- `_variant_group_has_multiple_options`
- `_value_looks_like_color`

**Verify:**
```powershell
cd backend
$env:PYTHONPATH='.'
.\.venv\Scripts\python.exe -m pytest tests\services -q
.\.venv\Scripts\python.exe run_extraction_smoke.py
```

## Slice 12: `config/extraction_rules.py` dead constant audit

**Status:** TODO
**Transformation:** Remove dead code and consolidate duplicate constants.
**Files:** `config/extraction_rules.py`

**What:**
- Grep every exported constant against `backend/app` and `backend/tests`.
- Delete unreferenced constants.
- Consolidate duplicate token sets only when they represent the same runtime rule.
- Do not move runtime tunables out of `app/services/config/*`.

**Verify:**
```powershell
cd backend
$env:PYTHONPATH='.'
.\.venv\Scripts\python.exe -m pytest tests\services -q
.\.venv\Scripts\python.exe run_extraction_smoke.py
```

## Slice 13: Ratchet architecture gates

**Status:** TODO
**Transformation:** Update tests/docs to match completed ownership changes.
**Files:** `backend/tests/services/test_structure.py`, `docs/CODEBASE_MAP.md`

**What:**
- Re-measure LOC after completed slices.
- Set explicit budgets to current LOC plus the project policy margin used in `test_structure.py`.
- Remove deleted files from budget dicts and facade allowlists.
- Add budgets for new extracted modules.
- Update `docs/CODEBASE_MAP.md` with actual owners and import rules.
- Do not update `docs/ENGINEERING_STRATEGY.md` unless this work discovers a new recurring anti-pattern.

**Verify:**
```powershell
cd backend
$env:PYTHONPATH='.'
.\.venv\Scripts\python.exe -m pytest tests\services\test_structure.py -q
.\.venv\Scripts\python.exe -m pytest tests -q
```

## Completion Verification

Run before marking this plan DONE:

```powershell
cd backend
$env:PYTHONPATH='.'
.\.venv\Scripts\python.exe -m pytest tests -q
.\.venv\Scripts\python.exe run_acquire_smoke.py commerce
.\.venv\Scripts\python.exe run_extraction_smoke.py
.\.venv\Scripts\python.exe run_test_sites_acceptance.py
```

## Estimated Impact

| Bucket | Expected impact |
|---|---:|
| Facade deletion | ~30 deleted LOC plus cleaner import graph |
| Acquisition god-module extraction | ~850 LOC moved out of god modules |
| Acquisition cleanup/consolidation | ~180 deleted LOC |
| Extraction/config dead code cleanup | ~250 deleted LOC |
| Structure ratchet | prevents drift |

Expected deleted LOC: ~400-500.
Expected god-module LOC moved/reduced: ~1,300+.

## Notes

- Execute slices sequentially.
- After each slice, update its status and verification result in this file.
- If a slice grows beyond one transformation, split it.
- If a candidate has no high-value improvement after grep and local read, mark it skipped with the reason.
- The `llm_runtime.py` facade is intentionally out of scope.

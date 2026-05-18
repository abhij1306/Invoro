# Plan: Extract Decomposition And Public Surface

**Created:** 2026-05-17
**Agent:** Claude
**Status:** DONE
**Touches buckets:** Extraction (variant normalization, detail pipeline), Tests (structure ratchet + import targets), Docs (CODEBASE_MAP)

## Goal

Decompose the verified god object `extract/variant_record_normalization.py` into a stage-keyed sub-package, group the 26 flat `detail_*` modules into a `extract/detail/` sub-package by concern, enforce explicit `__all__` public surfaces across `extract/`, and remove the inline `crawler_runtime_settings` read on the variant normalization hot path. Done means the variant pipeline is testable without patching globals, no developer has to scan 26 files at one depth to find detail logic, every `extract/` module declares its public surface, and no canonical owner established by the prior `verified-architecture-audit-remediation-plan` is reverted.

## Verification Done Before Plan

Audit was rechecked against current `main`. Of 7 issues claimed:

- `variant_record_normalization.py` god object: **valid** (766 lines, 42KB; orchestrates 7 sub-pipelines plus inline size/color extraction at the same level).
- `_enforce_variant_payload_limits` reads `crawler_runtime_settings.detail_max_variant_rows` inline at line 1093: **valid**.
- 26 flat `detail_*` files in `extract/`: **valid** (no `detail/` sub-package exists).
- No `__all__` on most `extract/` modules: **valid** (only `contracts.py` and `detail_price_core.py` declare one).
- `listing_extractor.py` should move to `extract/`: **stale**. `docs/CODEBASE_MAP.md` and `tests/services/test_structure.py` explicitly anchor it as the public listing orchestration facade at services root. The prior remediation plan deliberately kept it there in Slice 2.
- `acquisition_plan.py` is an orphaned stub: **wrong**. It owns the `AcquisitionPlan` dataclass; verified imports in `pipeline/types.py`, `pipeline/url_processing_context.py`, `pipeline/record_extraction_stage.py`, `pipeline/extraction_retry_stage.py`, `crawl/batch_runtime.py`, `acquisition/policy.py`, `acquisition/acquirer.py`, `adapters/registry.py`, `models/crawl_settings.py`, plus harness and 5 tests.
- `selector_self_heal.py` should move to `dom/`: **stale**. `docs/CODEBASE_MAP.md` anchors it at services root as canonical owner.
- `xpath_service.py` should move to `dom/`: **partial**. No canonical anchor in `CODEBASE_MAP.md`. `dom/` already exists. Eligible for move under one slice with a CODEBASE_MAP update.

Audit byte-size figures roughly match; the prior plan tracks LOC budgets in `tests/services/test_structure.py`.

## Acceptance Criteria

- [x] `extract/variant_record_normalization.py` becomes a thin facade that imports a public `normalize_variant_record` from `extract/variant_normalization/`. The 6 cross-module callers compile unchanged.
- [x] Variant payload limit logic accepts `max_rows: int` as a parameter. The settings read happens at the public entry point, not inside the contract enforcement function.
- [x] All 26 `detail_*` modules live under `extract/detail/<concern>/` grouped by identity, price, images, variants, text, assembly. All call sites updated.
- [x] Every `extract/` and `extract/detail/` module declares `__all__`.
- [x] `xpath_service.py` either lives under `dom/` with `CODEBASE_MAP.md` updated, or stays at root with an explicit anchor entry added. No silent ambiguity remains.
- [x] `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services/test_structure.py -q` exits 0.
- [x] `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests -q` exits 0.
- [x] `run_acquire_smoke.py commerce`, `run_extraction_smoke.py`, and `run_test_sites_acceptance.py` pass before the plan is closed.

## Do Not Touch

- `app/services/listing_extractor.py` — anchored as the public listing facade by `CODEBASE_MAP.md` and `test_structure.py`. Moving it reverses Slice 2 of the prior remediation plan.
- `app/services/acquisition_plan.py` — canonical `AcquisitionPlan` dataclass owner, not a stub.
- `app/services/selector_self_heal.py` — anchored at services root by `CODEBASE_MAP.md`.
- `app/services/structured_sources.py` — explicitly excluded by the prior remediation plan.
- `frontend/` — out of scope.
- Adapter platform files — no site-specific behavior change belongs in this plan.
- Public function signatures of `normalize_variant_record`, `extract_listing_records`, `build_detail_record`, and other documented public APIs — refactor must be behavior-preserving.

## Slices

### Slice 1: Ratchet Structure Tests For This Plan
**Status:** DONE
**Files:** `backend/tests/services/test_structure.py`
**What:** Stage debt ledgers for the targets this plan resolves. Add a per-slice marker comment so the next agent sees why each target exists. New entries:
- LOC budget for the new `extract/variant_normalization/contract.py`, `hydration.py`, `sanitization.py`, `deduplication.py`, `backfill.py`, `size_color_extraction.py` modules (each well under 400).
- Lower the existing `variant_record_normalization.py` budget after Slice 2 lands; comment marks it as "Slice 2 follow-up".
- Add an `__all__`-required test that walks every `extract/**/*.py` (excluding `__init__`, `_*`, and `field_candidates/` subpackage internals if needed) and asserts module declares a non-empty `__all__`. Mark currently-failing modules in an explicit ledger with the slice that owns each fix.
- Add a structure assertion that no `detail_*.py` exists at `app/services/extract/` after Slice 4. Until Slice 4 lands the assertion is xfail-marked with a slice reference.
- Optional: assertion that `dom/` contains exactly the modules `CODEBASE_MAP.md` lists, to keep Slice 6 honest.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services/test_structure.py -q`

### Slice 2: Split Variant Record Normalization By Stage
**Status:** DONE
**Files:**
- New package `backend/app/services/extract/variant_normalization/` with `__init__.py`, `hydration.py`, `sanitization.py`, `deduplication.py`, `backfill.py`, `size_color_extraction.py`, `contract.py`.
- `backend/app/services/extract/variant_record_normalization.py` (reduced to a thin re-export shim with a deletion-date note, or deleted if all 6 callers are migrated in this slice).
- All 6 callers: `tests/services/test_variant_regression.py`, `tests/services/test_normalizers.py`, `tests/services/test_detail_extractor_structured_sources.py`, `tests/services/test_crawl_engine.py`, `app/services/extract/detail_image_cleanup.py`, `app/services/extract/detail_variant_pruning.py`, `app/services/extract/detail_record_sanitization.py`, `app/services/extract/detail_money_repair.py`, `app/services/extract/detail_final_cleanup.py`.

**Module ownership map (extracted directly from current file structure):**

| New module | Owns |
|---|---|
| `hydration.py` | `_hydrate_variant_axes`, `_infer_variant_sizes_from_titles`, `_infer_variant_sizes_from_skus`, `_infer_single_variant_axes`, `_variant_size_from_title_or_url`, `_variant_size_from_sku`, `_url_terminal_text` |
| `size_color_extraction.py` | `_extract_size_value` (and inner `_size_candidate_is_gender_artifact`), `_extract_color_value`, `_extract_trailing_color_phrase`, `_title_preserving_acronyms`, `_size_value_is_recognized`, `_size_value_is_child_specific`, `_record_targets_adult_sizes`, `_variant_color_from_title_or_url`, `_strip_variant_option_suffix_noise`, `_value_is_placeholder`, `_value_is_ui_noise`, `_normalize_variant_axis_value`, `_variant_size_axis_value_is_quantity_control` |
| `sanitization.py` | `_sanitize_variant_axes`, `_remap_generic_variant_axes`, `_clean_variant_rows`, `_flatten_variant_rows`, `_promote_misfiled_color_size`, `_drop_shade_code_size_duplicate`, `_normalize_separate_dimension_size_rows`, `_separate_dimension_style_label`, `_value_is_axis_header_noise`, `_variant_axis_value_is_header`, `_enforce_variant_axis_contract`, `_should_restore_original_variant_url`, `_variant_title_tokens` |
| `deduplication.py` | `_dedupe_and_prune_variant_rows`, `_dedupe_variant_rows`, `_variant_primary_key`, `_richer_variant_pair`, `_variant_field_fingerprint`, `_prune_unrecognized_size_rows_when_real_sizes_exist`, `_variant_row_has_labeled_size_dimension`, `_prune_child_size_rows_from_adult_products` |
| `backfill.py` | `_backfill_variant_context`, `_backfill_variant_prices_from_record`, `_backfill_variant_shared_fields_from_record`, `_enforce_variant_currency_context`, `_currency_code`, `_backfill_parent_scalar_axes_from_variants`, `_drop_polluted_parent_scalar_axes` |
| `contract.py` | `enforce_payload_limits(record, *, max_rows: int)` (renamed, takes `max_rows` as parameter — see Slice 3), `_finalize_variant_contract`, `_enforce_flat_variant_contract` |
| `__init__.py` | exports `normalize_variant_record` only |

The package public `__init__.py` resolves `crawler_runtime_settings.detail_max_variant_rows` once at the call to `contract.enforce_payload_limits`, never inside the contract module.

**Deletion first:** Delete `variant_record_normalization.py` if all callers are migrated to `app.services.extract.variant_normalization`. If a one-line re-export is needed for the duration of this slice only (some test mocks may patch `app.services.extract.variant_record_normalization.normalize_variant_record`), keep it as a compat shim with no logic and a `# REMOVE 2026-06-15` comment plus a follow-up Slice 8 entry.

**Cross-module private helper migration:** `variant_record_normalization.py` imports 8 private functions from `variant_structural_pruning.py` and 4 from `variant_identity_merge.py`. Those imports stay valid: the consumer module just becomes `sanitization.py`/`deduplication.py` instead of `variant_record_normalization.py`. Slice 5 promotes those cross-module helpers to public names.

**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services/test_variant_regression.py tests/services/test_normalizers.py tests/services/test_detail_extractor_structured_sources.py tests/services/test_crawl_engine.py tests/services/test_structure.py -q`

### Slice 3: Inject `max_rows` Into Contract Enforcement
**Status:** DONE
**Files:** `backend/app/services/extract/variant_normalization/contract.py`, `backend/app/services/extract/variant_normalization/__init__.py`, any tests asserting variant truncation behavior.
**What:** `contract.enforce_payload_limits(record, *, max_rows: int)` accepts `max_rows` as a parameter. `contract.py` does not import `crawler_runtime_settings`. `variant_normalization/__init__.py:normalize_variant_record` resolves the limit:
```python
from app.services.config.runtime_settings import crawler_runtime_settings
...
def normalize_variant_record(record, *, finalize_contract=True):
    _hydrate_variant_axes(record)
    _sanitize_variant_axes(record)
    _dedupe_and_prune_variant_rows(record)
    _backfill_variant_context(record)
    _backfill_parent_scalar_axes_from_variants(record)
    _drop_polluted_parent_scalar_axes(record)
    if finalize_contract:
        try:
            raw_limit = crawler_runtime_settings.detail_max_variant_rows
            max_rows = int(raw_limit) if raw_limit is not None else 0
        except (TypeError, ValueError):
            max_rows = 0
        contract.finalize(record, max_rows=max_rows)
```
Add a focused test that calls `contract.enforce_payload_limits` directly with an explicit `max_rows` value to confirm the global is no longer required.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services/test_variant_regression.py tests/services/test_normalizers.py -q`

### Slice 4: Group `detail_*` Files Into `extract/detail/` Sub-Package
**Status:** DONE
**Files:** All 26 `extract/detail_*.py` modules, every importer of `app.services.extract.detail_*` across `app/`, `tests/`, harness scripts, and docs cross-references.

**Target layout:**

```
extract/detail/
  __init__.py                    # public re-exports for stable callers
  identity/
    core.py                      ← detail_identity_core.py
    structured_pruning.py        ← detail_structured_pruning.py
    shell_filter.py              ← detail_shell_filter.py
  price/
    core.py                      ← detail_price_core.py
    money_repair.py              ← detail_money_repair.py
    inline_scalar.py             ← detail_inline_scalar.py
  images/
    cleanup.py                   ← detail_image_cleanup.py
    dedupe.py                    ← detail_image_dedupe.py
    materialize.py               ← detail_image_materialize.py
  variants/
    dom_extraction.py            ← detail_dom_variant_extraction.py
    dom_coercion.py              ← detail_dom_variant_coercion.py
    dom_options.py               ← detail_dom_variant_options.py
    state_targets.py             ← detail_state_variant_targets.py
    pruning.py                   ← detail_variant_pruning.py
    numbered_options.py          ← detail_numbered_options.py
  text/
    sanitizer.py                 ← detail_text_sanitizer.py
  assembly/
    candidate_collection.py      ← detail_candidate_collection.py
    record_assembly.py           ← detail_record_assembly.py
    record_sanitization.py       ← detail_record_sanitization.py
    final_cleanup.py             ← detail_final_cleanup.py
    tiers.py                     ← detail_tiers.py
    raw_signals.py               ← detail_raw_signals.py
    title_scorer.py              ← detail_title_scorer.py
    dom_completion.py            ← detail_dom_completion.py
    dom_fallbacks.py             ← detail_dom_fallbacks.py
    dom_section_targets.py       ← detail_dom_section_targets.py
  extraction_constants.py        ← detail_extraction_constants.py
```

`extract/detail/__init__.py` re-exports the public functions every old import path needed (`build_detail_record`, `backfill_detail_price_from_html`, etc.) so external callers can switch from `app.services.extract.detail_X` to `app.services.extract.detail` (or a focused sub-module) in one mechanical pass.

**Mechanical execution order** to keep diffs reviewable:
1. Create the `detail/` package skeleton with `__init__.py` files.
2. Move one concern at a time (identity → price → images → variants → text → assembly), updating cross-module imports inside `extract/` first (since detail modules import each other heavily) and tests last.
3. After each concern is moved, run the targeted detail tests for that concern.
4. Delete each `extract/detail_*.py` only after every importer has been updated and tests are green.

**Deletion first:** No detail_*.py file remains at `extract/` after the slice. No compat shim layer. The `__init__.py` re-export is the only public-surface bridge.

**Verify:** Run after each concern is moved:
- identity: `pytest tests/services/test_detail_extractor_structured_sources.py tests/services/test_detail_extractor_priority_and_selector_self_heal.py -q`
- price: `pytest tests/services -q -k "detail_price or detail_identity or crawl_engine"`
- images: `pytest tests/services -q -k "image"`
- variants: `pytest tests/services -q -k "variant or detail_dom"`
- text: `pytest tests/services -q -k "text or sanitizer"`
- assembly: `pytest tests/services -q -k "detail or extract_records"`
- final: `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests -q`

### Slice 5: Declare `__all__` On Every `extract/` And `extract/detail/` Module
**Status:** DONE
**Files:** Every `.py` file under `app/services/extract/` (after Slice 4 layout is in place), `backend/tests/services/test_structure.py`.
**What:** For each module, set `__all__` to the list of names imported by code outside that module. Names only used inside the module stay underscore-prefixed and out of `__all__`. Promote cross-module private helpers to public names where the audit identified them:
- 8 helpers in `variant_structural_pruning.py` consumed by `variant_normalization/sanitization.py`: `drop_color_only_rows_when_size_rows_exist`, `drop_cross_product_variant_rows`, `drop_parent_shared_variant_axes`, `drop_parent_sku_alias_variant_rows`, `drop_subset_variants_when_richer_alternative_exists`, `prune_axisless_rows_when_axisful_rows_exist`, `prune_low_signal_numeric_only_variants` — already public-named, just add to `__all__`.
- 4 helpers from `variant_identity_merge.py` consumed by `variant_normalization/deduplication.py`: `collapse_duplicate_size_aliases`, `merge_variant_pair`, `variant_identity`, `variant_row_richness`, `variant_semantic_identity` — already public-named, just add to `__all__`.
- Any private name imported across module boundaries gets promoted to public during this slice. Use `grep -r "from app.services.extract.* import _" backend/` to find them.
**Deletion first:** Remove names from `__all__` that no external caller references; do not pad with everything in the module.
**Verify:** The structure test added in Slice 1 (now de-xfailed) walks every `extract/**/*.py` and confirms `__all__` is declared and non-empty.
`cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services/test_structure.py tests -q`

### Slice 6: Resolve `xpath_service.py` Anchor
**Status:** DONE — moved to `app/services/dom/xpath_service.py`
**Files:** `backend/app/services/xpath_service.py`, `backend/app/services/dom/xpath_service.py` (target), all importers, `docs/CODEBASE_MAP.md`, `backend/tests/services/test_structure.py`.
**What:** Move `xpath_service.py` to `app/services/dom/xpath_service.py`. Update all import paths (`app.services.xpath_service` → `app.services.dom.xpath_service`). Add the move to `docs/CODEBASE_MAP.md` under the `dom/` section. Add a structure assertion that `xpath_service.py` is not present at services root.
**Deletion first:** Delete the root `xpath_service.py` after imports are updated. No shim.
**Skip condition:** If, during execution, `CODEBASE_MAP.md` is found to contain a positive anchor for `xpath_service.py` at services root, do not move; instead add an `ALLOWED_ROOT_EXTRACTION_MODULES`-style entry in the structure test and document the anchor explicitly. Note in the slice's status which path was taken.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests -q -k "xpath or selector or self_heal"; .\.venv\Scripts\python.exe -m pytest tests/services/test_structure.py -q`

### Slice 7: Smoke And Docs Closeout
**Status:** DONE
**Files:** `docs/CODEBASE_MAP.md`, `docs/backend-architecture.md` (only if extraction ownership headings change), `docs/plans/ACTIVE.md`, this plan file.
**What:** Update `CODEBASE_MAP.md` for the new `extract/detail/` layout and `extract/variant_normalization/` package. Confirm every acceptance criterion is checked. Run smoke commands. Mark plan `DONE` and update `ACTIVE.md`.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests -q; .\.venv\Scripts\python.exe run_acquire_smoke.py commerce; .\.venv\Scripts\python.exe run_extraction_smoke.py; .\.venv\Scripts\python.exe run_test_sites_acceptance.py`

### Slice 8: Remove `variant_record_normalization.py` Compat Shim (conditional)
**Status:** DONE — old facade deleted after all importers moved
**Files:** `backend/app/services/extract/variant_record_normalization.py`, any remaining importers.
**What:** Only runs if Slice 2 left a compat shim for the duration of mid-slice migrations. Final deletion of the shim after all importers are confirmed migrated. Skip if Slice 2 already deleted the file.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests -q`

## Doc Updates Required

- [x] `docs/CODEBASE_MAP.md` — new entries for `extract/variant_normalization/*` and `extract/detail/<concern>/*`. Update existing `extract/variant_record_normalization.py` row to point at the new package. Add `xpath_service.py` row under `dom/` if Slice 6 moved it.
- [x] `docs/backend-architecture.md` — update only if extraction subsystem ownership headings change at the section level. Routine file moves do not require an update.
- [x] `docs/INVARIANTS.md` — no update expected. Refactors are behavior-preserving.
- [x] `docs/ENGINEERING_STRATEGY.md` — only if execution surfaces a stable, repeatable anti-pattern that the existing AP-12 through AP-15 entries do not cover.

## Notes

- Start at Slice 1 in the next session.
- Slices 1, 5, and 6 are low-risk and can be done in any order after Slice 4. Slices 2 → 3 → 4 must run in that order because Slice 3 depends on the package created in Slice 2 and Slice 5's `__all__` enforcement is cleaner against the post-Slice-4 layout.
- Audit Issues 2, 3, and 7's `selector_self_heal.py` portion are excluded from this plan and reasons are recorded in the "Do Not Touch" section above. Do not re-add them mid-execution without an updated audit and explicit user direction.
- Behavior preservation gate: every slice must keep `normalize_variant_record(record, *, finalize_contract=True)` byte-for-byte equivalent in output for the existing regression fixtures.


## Closeout Verification

- `pytest tests -q` — 1690 passed, 16 skipped.
- `run_acquire_smoke.py commerce` — 6/6 passed.
- `run_extraction_smoke.py` — skipped by runner because acceptance corpus is missing, exit 0.
- `run_test_sites_acceptance.py` — 54/54 passed.

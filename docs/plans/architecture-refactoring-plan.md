# Plan: Architecture Refactoring — God Functions, Frontend Split, Coupling Reduction

**Created:** 2026-05-15
**Agent:** Opus
**Status:** IN PROGRESS
**Touches buckets:** 2 (Orchestration), 3 (Acquisition/Browser), 4 (Extraction), 6 (Review/Selectors), Frontend

## Goal

Decompose verified god functions (>300 LOC), split the 2356-LOC frontend `shared.tsx` utility dump, split `field_coerce.py` (1281 LOC, 67 dependents), audit variant logic proliferation, and reduce private cross-module import debt. Improve testability, reduce shotgun surgery risk, and lower cognitive load without changing any runtime behavior.

## Acceptance Criteria

- [ ] No function exceeds 300 LOC in touched files
- [ ] Frontend `shared.tsx` reduced below 800 LOC with focused modules
- [ ] `field_coerce.py` split into focused coercion owners
- [ ] Private import allowlist in `test_structure.py` shrinks by at least 4 entries
- [ ] `python -m pytest tests -q` exits 0
- [ ] Frontend build passes
- [ ] No LOC budget in `test_structure.py` needs raising (budgets should shrink or stay)

## Do Not Touch

- `extract/detail_materializer.py` candidate system — documented as correct architecture
- `config/extraction_rules.py` — data file, not logic; size is acceptable
- `acquisition/browser_identity.py` — coherent single responsibility despite size
- Adapter files (`adapters/*.py`) — isolated, rarely co-change
- The `test_structure.py` enforcement model itself — extend it, don't replace it

## Slices

### Slice 1.1: Decompose `traversal.py::should_run_traversal` (1224 LOC)
**Status:** TODO
**Files:** `app/services/acquisition/traversal.py`
**What:** Extract decision predicates into named functions: `_traversal_readiness_check`, `_traversal_card_evidence_check`, `_traversal_expansion_decision`. Keep orchestration in parent function.
**Verify:** `pytest tests -q -k traversal`

### Slice 1.2: Decompose `browser_page_flow.py::_urls_match_for_navigation` (537 LOC)
**Status:** TODO
**Files:** `app/services/acquisition/browser_page_flow.py`
**What:** Extract URL comparison strategies into focused matchers. The function handles many URL normalization edge cases that should be named predicates.
**Verify:** `pytest tests -q -k browser_page_flow`

### Slice 1.3: Decompose `browser_page_flow.py::__init__` (383 LOC)
**Status:** TODO
**Files:** `app/services/acquisition/browser_page_flow.py`
**What:** Extract initialization phases into `_configure_readiness`, `_configure_navigation`, `_configure_expansion`.
**Verify:** `pytest tests -q -k browser_page_flow`

### Slice 1.4: Decompose `browser_runtime.py::_resolve_proxied_page_factory` (575 LOC)
**Status:** TODO
**Files:** `app/services/acquisition/browser_runtime.py`
**What:** Split proxy resolution from page factory creation. Two clear responsibilities.
**Verify:** `pytest tests -q -k browser_runtime`

### Slice 1.5: Decompose `browser_detail.py::_finish_expansion_diagnostics` (407 LOC)
**Status:** TODO
**Files:** `app/services/acquisition/browser_detail.py`
**What:** Extract diagnostic assembly from expansion control flow. Diagnostics are a separate concern from expansion decisions.
**Verify:** `pytest tests -q -k browser_detail`

### Slice 1.6: Decompose `extraction_loop.py::_apply_detail_rejection_guard` (361 LOC)
**Status:** TODO
**Files:** `app/services/pipeline/extraction_loop.py`
**What:** Decompose into a chain of focused guard predicates with early returns.
**Verify:** `pytest tests -q -k extraction_loop`

### Slice 1.7: Decompose `data_enrichment/service.py::_resolved_source_url` (890 LOC)
**Status:** TODO
**Files:** `app/services/data_enrichment/service.py`
**What:** Split URL resolution phases into named stages.
**Verify:** `pytest tests -q -k data_enrichment`

### Slice 2.1: Extract frontend quality scoring utilities
**Status:** TODO
**Files:** `frontend/components/crawl/shared.tsx` → `frontend/lib/crawl/quality.ts`
**What:** Move `scoreRecordQuality`, `scoreFieldQuality`, `estimateDataQuality`, `qualityTone`, `humanizeQuality`, `qualityLevelFromScore` to focused module.
**Verify:** Frontend build + Playwright smoke

### Slice 2.2: Extract frontend log parsing utilities
**Status:** TODO
**Files:** `frontend/components/crawl/shared.tsx` → `frontend/lib/crawl/log-parsing.ts`
**What:** Move `getLogStage`, `getLogIcon`, `getLogIconStyle`, `logMessageIsError`, `buildLogSiteGroups`, `severityTone`, `severityLabel`, `payloadSnapshot`, `parseStartingLog`, `isWarningLog`, `isHiddenLogMessage`, `sanitizeLogMessage`, `renderLogContent`.
**Verify:** Frontend build + Playwright smoke

### Slice 2.3: Extract frontend formatting utilities
**Status:** TODO
**Files:** `frontend/components/crawl/shared.tsx` → `frontend/lib/crawl/format.ts`
**What:** Move `formatDuration`, `formatDurationMs`, `formatShortUrlLabel`, `decodeUrlForDisplay`, `formatCellDisplay`, `stringifyCell`, `humanizeFieldName`, `presentCandidateValue`.
**Verify:** Frontend build + Playwright smoke

### Slice 2.4: Extract frontend record utilities
**Status:** TODO
**Files:** `frontend/components/crawl/shared.tsx` → `frontend/lib/crawl/record-utils.ts`
**What:** Move `extractRecordUrl`, `readRecordValue`, `publicFieldNames`, `recordConfidence`, `cleanRecord`, `cleanRecordForDisplay`, `copyJson`, `isIdentityField`, `isInformativeValue`.
**Verify:** Frontend build + Playwright smoke

### Slice 2.5: Extract frontend form field components
**Status:** TODO
**Files:** `frontend/components/crawl/shared.tsx` → `frontend/components/crawl/form-fields.tsx`
**What:** Move `SettingSection`, `SliderRow`, `AdditionalFieldInput`, `ManualFieldEditor`, `FieldEditorHeader`, `ValidatedField`.
**Verify:** Frontend build + Playwright smoke

### Slice 2.6: Extract frontend record thumbnail component
**Status:** TODO
**Files:** `frontend/components/crawl/shared.tsx` → `frontend/components/crawl/record-thumbnail.tsx`
**What:** Move `RecordThumbnail`, `loadBrokenThumbnailCache`, `persistBrokenThumbnailCache`, `thumbnailHost`.
**Verify:** Frontend build + Playwright smoke

### Slice 3.1: Split `field_coerce.py` — URL coercion
**Status:** TODO
**Files:** `app/services/shared/field_coerce.py` → `app/services/shared/field_coerce_url.py`
**What:** Extract URL field coercion (image URLs, detail URLs, tracking cleanup).
**Verify:** `pytest tests -q`

### Slice 3.2: Split `field_coerce.py` — Price coercion
**Status:** TODO
**Files:** `app/services/shared/field_coerce.py` → `app/services/shared/field_coerce_price.py`
**What:** Extract price/currency coercion and validation.
**Verify:** `pytest tests -q`

### Slice 3.3: Split `field_coerce.py` — Text coercion
**Status:** TODO
**Files:** `app/services/shared/field_coerce.py` → `app/services/shared/field_coerce_text.py`
**What:** Extract text field coercion (title, description, brand cleanup).
**Verify:** `pytest tests -q`

### Slice 3.4: Reduce `field_coerce.py` to dispatch entry
**Status:** TODO
**Files:** `app/services/shared/field_coerce.py`
**What:** Keep as dispatch entry point + availability/stock coercion. Update `test_structure.py` LOC budget downward.
**Verify:** `pytest tests -q`, all 67 importers still resolve

### Slice 4.1: Variant function ownership audit
**Status:** TODO
**Files:** All `extract/variant_*.py`, `extract/shared_variant_logic.py`, `extract/detail_dom_extractor.py`
**What:** Map every variant function to its single canonical responsibility. Identify functions called from only one site that could be inlined. Identify duplicate logic between `variant_record_normalization.py` (37 funcs) and `shared_variant_logic.py` (33 funcs).
**Verify:** Document findings, no code changes in this slice

### Slice 4.2: Consolidate duplicate variant logic
**Status:** TODO
**Files:** Based on 4.1 findings
**What:** Consolidate where the same rule is expressed twice. Move pure variant-value logic from `detail_dom_extractor.py` to `shared_variant_logic.py` where it belongs.
**Verify:** `pytest tests -q`

### Slice 5.1: Promote `_aggregate_verdict` to public API
**Status:** TODO
**Files:** `app/services/publish/__init__.py`, `app/services/publish/verdict.py`, `app/services/_batch_runtime.py`
**What:** Rename `_aggregate_verdict` → `aggregate_verdict`, update import in `_batch_runtime.py`, remove from allowlist.
**Verify:** `test_private_service_imports_do_not_drift` passes with smaller allowlist

### Slice 5.2: Move capture constants to config
**Status:** TODO
**Files:** `app/services/acquisition/browser_capture.py`, `app/services/config/runtime_settings.py`, `app/services/acquisition/browser_runtime.py`
**What:** Move `_MAX_CAPTURED_NETWORK_PAYLOADS`, `_MAX_CAPTURED_NETWORK_PAYLOAD_BYTES`, `_NETWORK_CAPTURE_QUEUE_SIZE`, `_NETWORK_CAPTURE_WORKERS` to `config/runtime_settings.py`. Remove 4 entries from allowlist.
**Verify:** `test_private_service_imports_do_not_drift` passes with smaller allowlist

### Slice 5.3: Promote `_accept_language_for_locale` to public API
**Status:** TODO
**Files:** `app/services/network_resolution.py`, `app/services/acquisition/browser_identity.py`
**What:** Rename to `accept_language_for_locale`, update import, remove from allowlist.
**Verify:** `test_private_service_imports_do_not_drift` passes with smaller allowlist

### Slice 5.4: Promote `_settings_config` to public accessor
**Status:** TODO
**Files:** `app/services/config/runtime_settings.py`, consumers
**What:** Expose as `settings_config` or a public getter. Remove 3 entries from allowlist.
**Verify:** `test_private_service_imports_do_not_drift` passes with smaller allowlist

### Slice 6.1: Flatten nesting in `shared_variant_logic.py`
**Status:** TODO
**Files:** `app/services/extract/shared_variant_logic.py`
**What:** Early returns to flatten nested conditionals (currently 9 levels deep).
**Verify:** `pytest tests -q -k variant`

### Slice 6.2: Flatten nesting in `fetch_context.py`
**Status:** TODO
**Files:** `app/services/fetch/fetch_context.py`
**What:** Extract nested decision branches into named predicates. Guard clauses at function entry.
**Verify:** `pytest tests -q -k fetch`

## Doc Updates Required

- [ ] `docs/CODEBASE_MAP.md` — if new files added during field_coerce split or frontend split
- [ ] `docs/ENGINEERING_STRATEGY.md` — update LOC budgets section if budgets change
- [ ] `test_structure.py` — update LOC budgets downward, shrink private import allowlist

## Notes

- The previous "God Module Consolidation" plan (completed 2026-05-13) already reduced some modules. This plan targets the remaining god *functions* within those modules.
- `extraction_rules.py` 1742 LOC is 90% a single frozenset constant — data, not logic. Not worth splitting.
- `browser_identity.py` 1529 LOC is coherent fingerprint generation. Single responsibility despite size.
- Phase execution order: 1 → 2 → 3 → 5 → 4 → 6 (by impact/effort ratio).

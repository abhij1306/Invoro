# Plan: Verified Architecture Audit Remediation

**Created:** 2026-05-17
**Agent:** Codex
**Status:** IN PROGRESS
**Touches buckets:** Extraction, Crawl Ingestion + Orchestration, Acquisition + Browser Runtime, API + Bootstrap, Review + Selectors + Domain Memory, LLM Admin + Runtime, Product/Data Enrichment, Tests, Docs

## Goal

Turn the valid findings from `docs/reviews/2026-05-17-architecture-audit.md` into executable refactor slices. Done means oversized modules are split by real ownership, root-service drift is removed or documented by canonical owner, legacy runtime/shim paths have explicit removal, tests stop reaching into private service internals, and structure tests ratchet the new shape so the same drift cannot return.

## Verification Done Before Plan

Claims were verified against current `main` on 2026-05-17 before this plan was written.

- Active prior plan is `COMPLETE`, so this new plan can become active.
- Current large-file evidence:
  `shared_variant_logic.py` 1443 LOC, `detail_dom_extractor.py` 1394 LOC, `detail_materializer.py` 1338 LOC, `detail_record_finalizer.py` 1217 LOC, `listing_extractor.py` 1195 LOC, `detail_price_extractor.py` 879 LOC, `detail_identity.py` 879 LOC, `extraction_runtime.py` 813 LOC, `detail_text_sanitizer.py` 744 LOC, `selectors_runtime.py` 711 LOC, `browser_runtime.py` 1637 LOC, `selector_engine.py` 1534 LOC, `traversal.py` 1544 LOC, `browser_page_flow.py` 1501 LOC, `extraction_loop.py` 1437 LOC, `fetch_context.py` 1296 LOC, `data_enrichment/service.py` 1262 LOC, `api/crawls.py` 619 LOC.
- `listing_extractor.py` still owns card/title/image/label/brand helpers inline: `_extract_price_signal_from_card`, `_card_title_node`, `_card_title_score`, `_fallback_card_title_candidates`, `_select_primary_anchor`, `_select_primary_card_url`, `_extract_page_images_from_node`, `_listing_image_candidate_is_noise`, `_extract_image_title_hint`, `_normalize_listing_title`, `_title_token_overlap`, `_should_replace_title_with_image_hint`, `_extract_label_value_pairs_from_node`, `_label_value_pair_is_noise`, `_extract_brand_signal_from_card`, plus listing stages and integrity gate.
- `extraction_runtime.py` still owns `extract_records`, listing-integrity propagation, sitemap XML extraction, raw JSON extraction, listing row finalization, and detail post-processing.
- Dual dispatcher drift exists: `celery_dispatch_enabled=False`, `legacy_inprocess_runner_enabled=True`, and both `LocalRunDispatcher` and `CeleryRunDispatcher` are imported and selected at runtime.
- Legacy shims exist: `_LEGACY_PROMPTS_DIR`, `legacy_keys` / `legacy_aliases` in crawl profile merge, and `_legacy_artifact_paths`.
- Private test imports exist beyond the audit's sample list. These include private names from `app.main`, acquisition runtime, data enrichment service, detail materializer, selector self-heal, extraction runtime, field coercion, selector engine, listing ranking, listing integrity gate, network payload mapper, pipeline extraction loop, product intelligence, selectors runtime, shared URL utils, and shared variant logic.
- `run_summary.py` and `product_intelligence/matching.py` contain dict-spread merges. Verified as non-public-record merges; keep out of remediation unless future behavior changes.
- No `os.environ` / `os.getenv` was found outside `app/core`.
- No `requests.Session` or direct `httpx.Client(...)` was found in `backend/app`.
- LLM gates and selector self-heal LLM gate were found at `pipeline/extraction_loop.py` and `selector_self_heal.py`.
- Shared browser launch still centralizes at `acquisition/browser_runtime.py`.
- HTTP retry backoff still uses `crawler_runtime_settings.http_retry_backoff_*`.

## Audit Claims Excluded

These audit items are not included as remediation because current code did not support them.

- `backend/.pytest-tmp/` accumulation: path is missing in this workspace.
- `services/llm/circuit_breaker.py` `_DEFAULT_FAILURE_THRESHOLD`: symbol is absent; default is already `services/config/llm_runtime.py:circuit_failure_threshold = 5`.
- Redis TTL defect: only direct Redis writes found were LLM cache `redis.set(..., ex=ttl_seconds)` and circuit breaker stats `hset` followed by `expire`.
- `structured_sources.py` move/absorb: `docs/CODEBASE_MAP.md` already names it as the canonical multi-surface structured-source owner, and imports confirm it is shared by adapters, acquisition, extraction, and LLM prompt rendering.
- File line counts from the audit are stale. The current verified counts above replace them.

## Acceptance Criteria

- [ ] `listing_extractor.py` is an orchestration facade with card/title/image/brand helpers moved to extraction-owned modules.
- [ ] `extraction_runtime.py` is deleted or reduced to a temporary public import shim with a dated deletion note and no business logic.
- [ ] `shared_variant_logic.py` is deleted or reduced to a small temporary public import shim with a dated deletion note and no mixed-concern logic.
- [ ] Oversized detail modules are split by concern and ratcheted in `backend/tests/services/test_structure.py`.
- [ ] Dispatcher selection has one production path. `legacy_inprocess_runner_enabled` is removed or converted to an explicit dev-only path with no production ambiguity.
- [ ] Legacy prompt/profile/dashboard shims have either been deleted or have a dated removal gate and regression coverage.
- [ ] Tests no longer import private service names except for an explicit, shrinking allowlist in `test_structure.py`.
- [ ] `python -m pytest tests/services/test_structure.py -q` exits 0.
- [ ] `python -m pytest tests -q` exits 0.
- [ ] `run_acquire_smoke.py commerce`, `run_extraction_smoke.py`, and `run_test_sites_acceptance.py` pass before closing the plan.

## Do Not Touch

- `frontend/` - out of scope; current worktree has an unrelated `frontend/next-env.d.ts` change.
- `publish/*` - audit found no publish-layer compensators; keep remediation upstream.
- `structured_sources.py` - do not move in this plan unless new evidence contradicts `CODEBASE_MAP.md`.
- `run_summary.py` and `product_intelligence/matching.py` dict-spread merges - verified non-public-record merges.
- Adapter platform files - no site-specific behavior change belongs in this plan.

## Slices

### Slice 1: Ratchet The Audit Into Structure Tests
**Status:** DONE
**Files:** `backend/tests/services/test_structure.py`
**What:** Add explicit debt ledgers for large-file budgets, root-service extraction modules, and private test imports. Do not create a blanket allowlist. For each module scheduled in this plan, set a target budget that the matching slice must satisfy. Keep currently failing targets marked by slice name in comments so the next agent knows why the test is allowed to fail until that slice lands, or stage the ratchet at the end of each slice if the team wants green tests between slices.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services/test_structure.py -q`

### Slice 2: Hollow Listing Extraction
**Status:** DONE
**Files:** `backend/app/services/listing_extractor.py`, `backend/app/services/extract/listing_card_fragments.py`, optional `backend/app/services/extract/listing_signals.py`, `backend/tests/services/test_crawl_engine.py`, `backend/tests/services/test_selectolax_css_migration.py`, `backend/tests/services/test_structure.py`
**What:** Move listing card/title/image/label/brand signal helpers out of `listing_extractor.py`. Prefer extending `listing_card_fragments.py` if the helper is fragment discovery/scoring. Create `listing_signals.py` only for signal extraction that does not fit fragment ownership. Keep `listing_extractor.py` responsible for stage orchestration, selector trace assembly, listing integrity attachment, and public `extract_listing_records`.
**Deletion first:** Remove moved helpers from `listing_extractor.py`; update imports; remove duplicate definitions if found.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services/test_crawl_engine.py tests/services/test_selectolax_css_migration.py tests/services/test_structure.py -q`

### Slice 3: Move Extraction Runtime Into Pipeline Owners
**Status:** DONE
**Files:** `backend/app/services/extraction_runtime.py`, new `backend/app/services/pipeline/extract_records.py`, new `backend/app/services/pipeline/sitemap.py`, new `backend/app/services/pipeline/raw_json.py`, new `backend/app/services/pipeline/listing_integrity.py`, `backend/app/services/pipeline/extraction_loop.py`, `backend/app/services/selector_self_heal.py`, tests importing `app.services.extraction_runtime`
**What:** Move `extract_records` orchestration under `pipeline/extract_records.py`. Move XML sitemap extraction to `pipeline/sitemap.py`, raw JSON extraction to `pipeline/raw_json.py`, and listing-integrity diagnostic propagation to `pipeline/listing_integrity.py`. Update app and test imports to the new public owners.
**Deletion first:** Delete root `extraction_runtime.py` after imports are updated. If a short shim is unavoidable for one session, it must contain no logic and include a deletion date in `Notes`.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services -q -k "extraction_runtime or crawl_engine or listing_integrity or raw_json or article_forum"`

### Slice 4: Split Shared Variant Logic By Concern
**Status:** DONE
**Files:** `backend/app/services/extract/shared_variant_logic.py`, `variant_dom_cues.py`, `variant_group_validator.py`, `variant_record_normalization.py`, `variant_structural_pruning.py`, `variant_value_guards.py`, optional new `variant_identity.py`, optional new `variant_grouping.py`, `backend/tests/services/test_shared_variant_logic.py`, `backend/tests/services/test_variant_regression.py`, `backend/tests/services/test_variant_group_validator.py`
**What:** Move axis/group detection, DOM cue helpers, identity helpers, row richness, row merging, and size alias collapse to focused owners. Use existing variant files first. Add `variant_identity.py` or `variant_grouping.py` only when no existing owner fits.
**Deletion first:** Shrink or delete `shared_variant_logic.py`; do not leave a mixed shared bucket. Any remaining shim must be public re-exports only with a deletion date.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services/test_shared_variant_logic.py tests/services/test_variant_regression.py tests/services/test_variant_group_validator.py tests/services/test_structure.py -q`

### Slice 5: Split Detail DOM Extraction
**Status:** DONE
**Files:** `backend/app/services/extract/detail_dom_extractor.py`, optional new `detail_dom_context.py`, optional new `detail_dom_variant_recovery.py`, `backend/tests/services/test_detail_extractor_structured_sources.py`, `backend/tests/services/test_detail_extractor_priority_and_selector_self_heal.py`
**What:** Separate primary DOM context selection, DOM fallback field extraction, and DOM variant recovery. Keep `detail_dom_extractor.py` as the public detail DOM facade only if callers need one import.
**Deletion first:** Move cohesive helper clusters; delete moved definitions from the original file.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services/test_detail_extractor_structured_sources.py tests/services/test_detail_extractor_priority_and_selector_self_heal.py tests/services/test_structure.py -q`

### Slice 6: Split Detail Materialization
**Status:** DONE
**Files:** `backend/app/services/extract/detail_materializer.py`, optional new `detail_rejection.py`, optional new `detail_candidate_collection.py`, optional new `detail_dom_requirements.py`, related tests
**What:** Keep materialization focused on candidate collection, candidate ranking, record assembly, and public `build_detail_record`. Move detail rejection/failure inference, DOM completion requirements, and structured-payload pruning to focused owners.
**Deletion first:** Remove moved helpers from `detail_materializer.py`; expose public helper names only where there are real external callers.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services/test_detail_extractor_structured_sources.py tests/services/test_detail_extractor_priority_and_selector_self_heal.py tests/services/test_structure.py -q`

### Slice 7: Split Detail Finalization
**Status:** DONE
**Files:** `backend/app/services/extract/detail_record_finalizer.py`, existing variant modules, optional new `detail_image_cleanup.py`, optional new `detail_money_repair.py`, related tests
**What:** Keep finalizer focused on final public detail cleanup. Move variant price/identity repair into variant owners, image cleanup into a detail image owner, and money precision/original-price repair into a money owner.
**Deletion first:** Delete moved helper clusters from `detail_record_finalizer.py`; remove duplicate variant repair paths.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services -q -k "detail or variant or price"; .\.venv\Scripts\python.exe -m pytest tests/services/test_structure.py -q`

### Slice 8: Split Price And Identity Companions
**Status:** DONE
**Files:** `backend/app/services/extract/detail_price_extractor.py`, optional new `detail_currency_reconciliation.py`, optional new `detail_price_magnitude.py`, `backend/app/services/extract/detail_identity.py`, optional new `detail_url_shape.py`, related tests
**What:** Move currency reconciliation and price magnitude/cents-copy repair out of the selector-facing price extractor. Move URL-shape, structural listing URL checks, utility/collection checks, and redirect identity checks out of detail identity.
**Deletion first:** Keep public imports stable only through real owner APIs, not private cross-module reach-ins.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services -q -k "detail_identity or detail_price or crawl_engine"; .\.venv\Scripts\python.exe -m pytest tests/services/test_structure.py -q`

### Slice 9: Resolve Dispatcher Runtime Drift
**Status:** DONE
**Files:** `backend/app/core/config.py`, `backend/app/core/dependencies.py`, `backend/app/services/crawl/service.py`, `backend/app/services/dispatch/*`, `backend/app/tasks.py`, `backend/tests/services/test_crawl_service.py`, docs as needed
**What:** Pick one production dispatcher path. Preferred production target is Celery. Keep in-process dispatch only as an explicit dev/test path if needed, named as such, with no `legacy_inprocess_runner_enabled` production flag. Update tests to assert the selected policy.
**Deletion first:** Remove `legacy_inprocess_runner_enabled`. Delete `LocalRunDispatcher` if no dev/test owner remains.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services/test_crawl_service.py tests/services/test_batch_runtime.py tests/services/test_structure.py -q`

### Slice 10: Retire Or Date Legacy Shims
**Status:** DONE
**Files:** `backend/app/services/llm/config_service.py`, `backend/app/services/crawl/profile/merge.py`, `backend/app/services/dashboard_service.py`, related tests
**What:** Remove `_LEGACY_PROMPTS_DIR` after confirming prompt files exist in `data/prompts`. For crawl profile merge aliases and legacy dashboard artifact paths, either delete if unused or add dated deprecation with a warning and a follow-up deletion slice. Prefer deletion if tests can be updated cleanly.
**Deletion first:** Delete shim paths before adding compatibility logic.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services -q -k "llm or profile or dashboard"; .\.venv\Scripts\python.exe -m pytest tests/services/test_structure.py -q`

### Slice 11: Convert Private-Import Tests To Public Contracts
**Status:** DONE
**Files:** tests under `backend/tests/`, `backend/tests/services/test_structure.py`
**What:** Replace direct imports of underscore-prefixed service names with public API tests. Where a helper is truly public behavior, promote it to a non-underscore owner API and test that. Keep only a small explicit allowlist for unavoidable transitional cases.
**Verified private imports to address:** `app.main`, `acquisition.runtime`, `data_enrichment.service`, `extract.detail_materializer`, `selector_self_heal`, `extraction_runtime`, `shared.field_coerce`, `dom.selector_engine`, `extract.listing_candidate_ranking`, `extract.listing_integrity_gate`, `network_payload_mapper`, `pipeline.extraction_loop`, `product_intelligence.discovery`, `product_intelligence.service`, `selectors_runtime`, `shared.url_utils`, `extract.shared_variant_logic`.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services/test_structure.py -q; .\.venv\Scripts\python.exe -m pytest tests -q`

### Slice 12: Split Remaining Oversized Owners By Blast Radius
**Status:** DONE
**Files:** `backend/app/services/selectors_runtime.py`, `backend/app/services/pipeline/extraction_loop.py`, `backend/app/services/dom/selector_engine.py`, `backend/app/services/acquisition/browser_runtime.py`, `backend/app/services/acquisition/traversal.py`, `backend/app/services/acquisition/browser_page_flow.py`, `backend/app/services/fetch/fetch_context.py`, `backend/app/services/data_enrichment/service.py`, `backend/app/api/crawls.py`
**What:** Execute only after Slices 2-11 are green. Split by existing responsibilities:
`selectors_runtime.py` into selector CRUD/runtime lookup/scoring;
`extraction_loop.py` into URL runner, retry families, post-processing, contract memory;
`selector_engine.py` into CSS, XPath, regex, images, text scope, sections;
`browser_runtime.py` into pool/context/limits/fetch orchestration;
`traversal.py` into pagination/load-more/card recovery;
`browser_page_flow.py` into navigation/readiness/artifact finalization;
`fetch_context.py` into decision/escalation/block detection/handoff;
`data_enrichment/service.py` into job orchestration/deterministic enrichment/LLM enrichment/persistence;
`api/crawls.py` into crawls, crawl profiles, domain recipe/feedback, logs websocket routes.
**Deletion first:** Each sub-slice must delete moved code from the old owner and ratchet LOC in `test_structure.py`.
**Progress:**
- DONE: Split selector suggestion assembly from `selectors_runtime.py` into `selector_suggestions.py`; ratcheted selector runtime LOC.
- DONE: Split domain recipe/profile/feedback/cookie-memory crawl routes from `api/crawls.py` into `api/crawl_domain.py`; added API LOC ratchet.
- DONE: Split deterministic product normalization/taxonomy matching from `data_enrichment/service.py` into `data_enrichment/deterministic.py`; ratcheted enrichment service LOC.
- DONE: Split DOM image extraction from `dom/selector_engine.py` into `dom/image_extraction.py`; ratcheted selector engine LOC.
- DONE: Split DOM section/feature extraction from `dom/selector_engine.py` into `dom/section_extraction.py`; kept selector engine as selector/value facade.
- DONE: Split fetch proxy/browser policy and HTTP retry policy from `fetch/fetch_context.py` into `fetch/browser_policy.py` and `fetch/retry_policy.py`; ratcheted fetch context LOC.
- DONE: Split browser pool/context lifecycle from `acquisition/browser_runtime.py` into `acquisition/browser_pool.py`; kept runtime as browser-fetch orchestration facade with compatibility exports.
- DONE: Split browser page helper/probe/result shaping from `acquisition/browser_page_flow.py` into `browser_page_helpers.py` and `browser_result_builder.py`.
- DONE: Split traversal helper/recovery mechanics from `acquisition/traversal.py` into `traversal_helpers.py` and `traversal_recovery.py`.
- DONE: Split record extraction and retry families from `pipeline/extraction_loop.py` into `record_extraction_stage.py` and `extraction_retry_stage.py`.
- DONE: Ratcheted remaining Slice 12 files to the 1000 LOC target in `test_structure.py`.
**Verify:** Run the narrow tests for each moved owner, then `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests -q`

### Slice 13: Final Smoke And Docs Closeout
**Status:** IN PROGRESS
**Files:** `docs/CODEBASE_MAP.md`, `docs/backend-architecture.md`, `docs/ENGINEERING_STRATEGY.md`, `docs/plans/ACTIVE.md`, this plan
**What:** Update canonical docs for moved files and ownership. Add any new anti-pattern found during execution to `ENGINEERING_STRATEGY.md` only if it is stable and enforceable. Mark all acceptance criteria complete only after full tests and smoke commands pass.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests -q; .\.venv\Scripts\python.exe run_acquire_smoke.py commerce; .\.venv\Scripts\python.exe run_extraction_smoke.py; .\.venv\Scripts\python.exe run_test_sites_acceptance.py`

## Doc Updates Required

- [ ] `docs/CODEBASE_MAP.md` - update when files move or new owner modules are created.
- [ ] `docs/backend-architecture.md` - update extraction, dispatch, acquisition, selectors, and API ownership after relevant slices.
- [ ] `docs/ENGINEERING_STRATEGY.md` - update only if execution finds a new repeatable anti-pattern or structure gate.
- [ ] `docs/INVARIANTS.md` - update only if a runtime contract changes. Refactors alone should not touch it.

## Notes

- Start next session at Slice 1.
- Do not implement from the stale audit line numbers. Use the verified counts in this plan.
- Keep each slice behavior-preserving unless that slice explicitly says otherwise.
- Existing worktree note from plan creation: `frontend/next-env.d.ts` was already modified and `docs/reviews/` was untracked. Do not treat those as remediation edits unless the user asks.

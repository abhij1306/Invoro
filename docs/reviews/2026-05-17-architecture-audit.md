# CrawlerAI Architecture Review — Full Repo — 2026-05-17

## Executive Summary

Hard invariants are intact. Pipeline order, LLM gating, surface scoping, browser pool, retry backoff are all compliant. **No 🔴 invariant blockers.** The real cost is structural drift created by the recent listing/LLM refactor:

- Several first-pass splits left **shell modules at the services root with most logic still inline** (`listing_extractor.py`, `extraction_runtime.py`, `network_payload_mapper.py`, `extraction_context.py`).
- The split **created or kept four ≥35 KB detail modules** under `extract/` plus a 60 KB `shared_variant_logic.py`.
- A **dual-runtime drift** persists: `LocalRunDispatcher` is the default (`legacy_inprocess_runner_enabled=True`) while Celery is opt-in.

**First action:** finish the hollowing pass on `listing_extractor.py`, `extraction_runtime.py`, and `shared_variant_logic.py`. Pick one runtime and retire the other. Then resume splitting the detail family.

Counts: 0 🔴 invariant blockers · 7 🔴 structural blockers · 6 🟠 critical · 10 🟡 important · 4 💡 suggestions

File-size verification (HEAD, bytes / lines):

| File | Bytes | Lines |
|---|---:|---:|
| `extract/shared_variant_logic.py` | 60 461 | 1 546 |
| `extract/detail_dom_extractor.py` | 53 452 | 1 470 |
| `extract/detail_materializer.py` | 51 804 | 1 425 |
| `extract/detail_record_finalizer.py` | 48 786 | 1 334 |
| `listing_extractor.py` | 43 811 | 1 258 |
| `extract/detail_price_extractor.py` | 36 567 | 985 |
| `extract/detail_identity.py` | 36 465 | 958 |
| `extraction_runtime.py` | 30 941 | 867 |
| `extract/detail_text_sanitizer.py` | 29 267 | 829 |
| `selectors_runtime.py` | 27 514 | 775 |
| `network_payload_mapper.py` | 22 408 | 643 |
| `structured_sources.py` | 21 082 | 634 |
| `dashboard_service.py` | 17 858 | 522 |
| `extract/listing_card_fragments.py` | 17 640 | 514 |
| `extract/network_listing_mapper.py` | 14 326 | 390 |
| `extraction_context.py` | 11 713 | 309 |

---

## What Was Completed ✅

- **LLM consolidation done.** All `llm/*` files moved into `services/llm/` as a bounded module with `__init__.py` (`budget`, `cache`, `circuit_breaker`, `config_service`, `cost_logging`, `errors`, `payloads`, `prompt_rendering`, `provider_client`, `runtime`, `tasks`, `types`).
- **`extract/` subpackage populated.** 30+ focused files now exist: listing signal modules (`listing_card_fragments`, `listing_visual`, `listing_integrity_gate`, `listing_candidate_ranking`), structured handling (`structured_listing_handler`, `network_listing_mapper`), detail pipeline split (`detail_dom_extractor`, `detail_price_extractor`, `detail_identity`, `detail_materializer`, `detail_record_finalizer`, `detail_text_sanitizer`), variant logic (`variant_record_normalization`, `variant_structural_pruning`, `variant_dom_cues`, `variant_group_validator`), plus `contracts.py` interface and a `field_candidates/` nested package.
- **Domain boundaries created.** `crawl/`, `dispatch/`, `dom/`, `js_state/`, `pipeline/`, `fetch/`, `publish/`, `review/`, `data_enrichment/`, `product_intelligence/` directories exist as proper modules.
- **Invariant compliance confirmed by spot checks:**
  - LLM gate at `pipeline/extraction_loop.py:1116` and `selector_self_heal.py:230`.
  - Domain memory scoped by `(domain, surface)` everywhere checked.
  - Single shared `chromium.launch` in `acquisition/browser_runtime.py:354`. No per-URL Playwright spawn.
  - HTTP retry uses exponential backoff + jitter (`fetch_context.py:1130–1152`, `runtime_settings.http_retry_backoff_*`).
  - `_curl_fetch_sync` and `_write_storage_state_file` correctly run via `asyncio.to_thread`.
  - No site sniffing in generic paths. Adapter dispatch is registry-based.
  - No `os.environ` / `os.getenv` outside `app/core`.
  - No raw `requests.Session` / `httpx.Client(...)` in services.

---

## Findings

### [D1] Pipeline Integrity

- 💡 Tier order honored end-to-end. Detail tier gating via `_can_skip_dom_tier` checks `requires_dom_completion`, so variant DOM cues do not silently early-exit (INV-3 honored).
- 💡 No publish-layer compensators detected. `publish/{verdict,metrics,metadata}.py` are observation-only.

### [D2] Invariant Compliance

- 💡 INV-08 LLM gating, INV-09 domain memory scoping, INV-22 shared browser pool, INV-26 no per-resource DNS — all verified.
- 🟡 Two dict-spread merges sit outside the per-field candidate path: `run_summary.py:57` (`{**summary, **patch}`) and `product_intelligence/matching.py:130` (`{**raw_data, **data}`). Neither is a public-record merge — first is run-summary state, second is search-result raw merge. Not violations of Rule 3, but worth a comment to keep them from drifting.

### [D3] SOLID / DRY / KISS — Structural Blockers

The post-refactor first pass left files that are too large for SRP. Treat each as a 🔴 structural blocker for the next feature work.

| File | Bytes / Lines | Concern | Action |
|---|---:|---|---|
| `extract/shared_variant_logic.py` | 60 461 / 1 546 | `shared_*` filename is a logical-cohesion red flag. Holds identity, merge, richness, grouping, axis helpers. Several concerns already have dedicated files (`variant_record_normalization`, `variant_structural_pruning`, `variant_dom_cues`, `variant_value_guards`). | Split by concern; treat this file as the undecomposed remainder. |
| `extract/detail_dom_extractor.py` | 53 452 / 1 470 | DOM context selection + DOM fallback fields + DOM variant recovery. | Three responsibilities → three files. |
| `extract/detail_materializer.py` | 51 804 / 1 425 | Materialization + rejection + failure inference + `_add_sourced_candidate`. | Pull rejection/failure inference out; keep materializer focused. |
| `extract/detail_record_finalizer.py` | 48 786 / 1 334 | Cleanup + variant backfill sequencing + repair + final normalization. | Split. |
| `listing_extractor.py` | 43 811 / 1 258 | Imports many `extract/*` modules but still hosts ~28 inline helpers (`_extract_price_signal_from_card`, `_card_title_score`, `_extract_brand_signal_from_card`, etc.). Hollowing pass incomplete. | Move card-signal helpers into `extract/listing_card_fragments.py` or a new `extract/listing_signals.py`; keep `listing_extractor.py` as orchestrator only. |
| `extract/detail_price_extractor.py` | 36 567 / 985 | Price + currency reconciliation + visible PDP price backfill. | Split price vs currency reconciliation. |
| `extract/detail_identity.py` | 36 465 / 958 | Identity codes + URL-shape rules + listing-detail boundary checks. | Split URL-shape rules into a small companion. |
| `extraction_runtime.py` | 30 941 / 867 | Mega-dispatcher: `extract_records`, sitemap XML extraction, raw JSON fallback, listing-integrity propagation, listing post-processing. Still at services root. | Move into `pipeline/`. Split into `extract_records` + `pipeline/sitemap.py` + `pipeline/raw_json.py` + `pipeline/listing_integrity.py`. |
| `extract/detail_text_sanitizer.py` | 29 267 / 829 | Long-text pollution + fulfillment cleanup + low-signal scalar checks. | Split when next touched. |
| `selectors_runtime.py` | 27 514 / 775 | Selector CRUD + runtime lookup + scoring/fallback. | Split execution vs scoring. |

Plus the existing godness already named in the prior audit, still applicable:

- 🟠 `acquisition/browser_runtime.py` (1 764 LoC) — split pool / context / limits / diagnostics.
- 🟠 `dom/selector_engine.py` (1 686 LoC) — split css / xpath / regex / images / sections / scope.
- 🟠 `acquisition/traversal.py` (1 635 LoC) — split listing pagination vs load-more vs card counting.
- 🟠 `acquisition/browser_page_flow.py` (1 571 LoC) — split nav vs readiness vs DOM probes.
- 🟠 `pipeline/extraction_loop.py` (1 548 LoC) — split retry families and contract memory.
- 🟠 `fetch/fetch_context.py` (1 410 LoC) — split decision/escalation/block-detection/handoff.
- 🟠 `data_enrichment/service.py` (1 388 LoC) — split job orchestration vs per-product enrichment.
- 🟠 `api/crawls.py` (696 LoC) — split into `crawls`, `crawl_recipes`, `crawl_profiles`, `crawl_feedback`, `crawl_websocket`.

### [D4] Codex Drift

- 🟠 [DRIFT] **Dual run dispatcher with default-on legacy.** `core/config.py:43` sets `legacy_inprocess_runner_enabled=True`, `celery_dispatch_enabled=False`. `LocalRunDispatcher` is the default; Celery exists but is opt-in. `tasks.py` and `celery_dispatcher.py` both pay the cost.
- 🟠 [DRIFT] Misplaced files at `services/` root after the refactor:
  - `extraction_runtime.py` → belongs in `pipeline/` (or split across `pipeline/` and `extract/`).
  - `extraction_context.py` (309 LoC) → belongs in `extract/` or `pipeline/`. The boundary between root and `extract/` stays porous while it lives at root.
  - `network_payload_mapper.py` (643 LoC) vs `extract/network_listing_mapper.py` (390 LoC) → both handle network-to-record mapping. Confirmed disjoint imports today, but the names invite future divergence. Audit and consolidate intent: payload-spec → fields belongs at root if it serves both surfaces; listing-row mapping belongs in `extract/`.
  - `structured_sources.py` (634 LoC) → either absorb into `extract/structured_listing_handler.py` or rename to make the root vs extract split obvious.
  - `dashboard_service.py` (522 LoC) → likely belongs under `crawl/` or a new `reporting/` boundary.
- 🟡 [DRIFT] `services/llm/config_service.py:19` — `_LEGACY_PROMPTS_DIR` fallback (`data/knowledge_base/prompts`) read alongside primary `data/prompts`. Compat shim with no migration deadline.
- 🟡 [DRIFT] `services/crawl/profile/merge.py` carries `legacy_keys` / `legacy_aliases` for `fetch_profile`, `locality_profile`, `diagnostics_profile`. Fine if migration is planned. Record the shim removal date.
- 🟡 [DRIFT] `services/dashboard_service.py:_legacy_artifact_paths` cleans `backend/backend/artifacts` etc. One-time cleanup with no flag.
- 🟡 [HOUSEKEEPING] `backend/.pytest-tmp/` has 1 977 case dirs locally. Gitignored, so not a commit risk, but slows IDE and grep. Add a session-scoped finalizer in `conftest.py`.

### [D5] Config & Secret Hygiene

- 💡 Excellent baseline. No env reads outside `core`, no raw clients in services.
- 🟡 `services/llm/circuit_breaker.py:24` — `_DEFAULT_FAILURE_THRESHOLD = 5` is a module-level fallback used when `llm_runtime_settings.circuit_failure_threshold` is unset. Move to `config/llm_runtime.py` so there is one owner of the default.
- 💡 Adapter base URLs are inline in `adapters/greenhouse.py`, `indeed.py`, etc. Adapters are platform-specific so this is acceptable today. If the count grows, push the API host base into `config/platforms.json`.

### [D6] Scalability & Resilience

- 💡 Browser pool is process-singleton. HTTP retry has backoff + jitter. Sync IO is wrapped in `asyncio.to_thread`. `process_run_task` is idempotent.
- 🟠 With `legacy_inprocess_runner_enabled=True`, long crawls run inside the FastAPI process. Single Uvicorn worker means one big crawl can starve API requests. Resilience risk for any deployment that has not flipped to Celery.
- 🟡 No exhaustive Redis TTL audit done. Spot checks (`llm/cache.py:128`, circuit breaker Lua TTL) are clean. Enumerate all Redis writes once and document TTLs.

### [D7] Test Coverage

- 70 backend pytest files; ~14 frontend unit suites + 1 Playwright smoke.
- 🟡 Private-import tests (rewrite to public surface):
  - `tests/services/test_extraction_runtime_listing_integrity.py:13` → `_propagate_listing_integrity_to_diagnostics`.
  - `tests/services/test_health_api.py:9` → `_RATE_LIMIT_BUCKETS`, `_client_rate_limit_key`.
  - `tests/services/test_config_imports.py:16` and `tests/services/test_detail_extractor_priority_and_selector_self_heal.py:15` → `_export_data`.
  - `tests/services/test_selectors_runtime.py:8` → `_coerce_int`.
  - `tests/services/test_detail_extractor_priority_and_selector_self_heal.py` → `_prune_irrelevant_detail_structured_payload`, `_validated_xpath_rules`, `_requires_dom_completion`.
- 💡 Acceptance runners exist as required by AGENTS.md (`run_acquire_smoke.py`, `run_extraction_smoke.py`, `run_test_sites_acceptance.py`).

### [D8] Dead Code & Lava Flow

- 🟠 Possible duplicate sources of truth between `listing_extractor.py` (still hosts inline card-signal helpers) and `extract/listing_card_fragments.py` / `extract/listing_visual.py` / `extract/listing_candidate_ranking.py`. Confirm whether anything is duplicated or merely complementary. If duplicated, the new files are dead until the orchestrator hollows out.
- 🟡 Legacy ring (`_legacy_artifact_paths`, `legacy_inprocess_runner`, `_LEGACY_PROMPTS_DIR`, `_LEGACY_VARIANT_KEYS`) is small but visible. Schedule shim removal.
- 💡 No empty middleware or stale-plan-as-active-constraint detected.

---

## Confirmed Progress vs. Remaining Work

| Area | Status | Action |
|---|---|---|
| LLM module consolidation | ✅ Complete | Done |
| `extract/` subpackage creation | ✅ Structural shell done | Content audit ongoing |
| `listing_extractor.py` hollowing | 🔴 Incomplete (1 258 LoC) | Move card-signal helpers into `extract/`; keep root file as orchestrator |
| `extraction_runtime.py` reduction | 🔴 Incomplete (867 LoC) | Move into `pipeline/`; split sitemap / raw-json / listing-integrity helpers |
| `shared_variant_logic.py` | 🔴 New god module (1 546 LoC) | Split by variant concern |
| Detail family (`detail_dom_extractor`, `detail_materializer`, `detail_record_finalizer`, `detail_identity`, `detail_price_extractor`, `detail_text_sanitizer`) | 🔴 Six oversized files (829–1 470 LoC each) | Second-pass split |
| `dashboard_service.py` | 🟡 Untouched (522 LoC) | Move to `crawl/` or new `reporting/` |
| `selectors_runtime.py` | 🟡 Untouched (775 LoC) | Split execution vs scoring |
| `extraction_context.py` | 🟡 Misplaced (309 LoC at services root) | Move into `extract/` or `pipeline/` |
| `structured_sources.py` | 🟡 Untouched (634 LoC at services root) | Confirm boundary with `extract/structured_listing_handler.py` |
| `network_payload_mapper.py` vs `extract/network_listing_mapper.py` | 🟡 Possible duplication | Audit and consolidate |
| Dual runtime (Local vs Celery) | 🟠 Drift | Pick one, deprecate the other |
| Private-import tests | 🟡 Brittle | Rewrite to public API |
| Pytest tmp accumulation | 🟡 1 977 dirs | Add cleanup finalizer |

---

## Phase-Wise Refactoring Plan

Sequenced correctness → drift removal → hollowing → structure → resilience → cleanup. Each slice has deletion-first acceptance criteria to keep net line count flat or negative.

### Phase 1 — Hollow the orchestrators [Week 1]

Goal: stop the copy-paste risk between root files and `extract/`.

#### Slice 1.1 — Hollow `listing_extractor.py`

- **Scope:** `services/listing_extractor.py`, `services/extract/listing_card_fragments.py`, possibly new `services/extract/listing_signals.py`
- **Dimension:** D3 / D8
- **Severity:** 🔴
- **Problem:** File still hosts ~28 inline card-signal helpers (`_extract_price_signal_from_card`, `_card_title_score`, `_card_title_node`, `_extract_brand_signal_from_card`, image and label-value helpers, etc.). The new `extract/listing_card_fragments.py` exists but the helpers were not moved.
- **Deletion first:** Move every `_*_from_card` / `_card_title_*` / `_select_primary_*` / `_extract_*_signal_from_card` helper out of `listing_extractor.py`. Confirm no duplicate definition remains anywhere.
- **New code:** Either extend `extract/listing_card_fragments.py` or add `extract/listing_signals.py` for the signal helpers.
- **Acceptance criteria:**
  - `wc -l backend/app/services/listing_extractor.py` ≤ 350
  - `grep -r "_extract_price_signal_from_card\|_card_title_score\|_select_primary_anchor" backend/app | wc -l` matches single owner
  - Net line count for the slice ≤ 0
- **Verify:** `pytest tests/services/test_crawl_engine.py tests/services/test_detail_extractor_structured_sources.py -q` then `run_extraction_smoke.py`.

#### Slice 1.2 — Move and split `extraction_runtime.py`

- **Scope:** `services/extraction_runtime.py` → `services/pipeline/extract_records.py` + `services/pipeline/sitemap.py` + `services/pipeline/raw_json.py` + `services/pipeline/listing_integrity.py`
- **Dimension:** D3 / D4
- **Severity:** 🔴
- **Deletion first:** Delete the root file once moves are complete.
- **Acceptance criteria:**
  - `grep -r "from app.services.extraction_runtime" backend/` → 0 (or temporary re-export shim with deletion deadline)
  - No new file > 350 LoC
  - Public function `extract_records` keeps the same signature
- **Verify:** `pytest tests/services -q -k 'extraction\|listing_integrity\|raw_json'`.

#### Slice 1.3 — Audit and consolidate network mapping

- **Scope:** `services/network_payload_mapper.py`, `services/extract/network_listing_mapper.py`
- **Dimension:** D8
- **Severity:** 🟡
- **Problem:** Two files at different paths handle network-to-record mapping. Today disjoint, but names invite drift.
- **Deletion first:** Decide ownership. If root file serves both surfaces, document that and shrink listing mapper. If listing mapper subsumes payload mapping for listing surfaces, fold the listing portion of the root file into `extract/`.
- **Acceptance criteria:**
  - One file owns network → listing rows
  - One file owns payload-spec → fields, with a one-line module docstring stating its scope
- **Verify:** `pytest tests/services -q -k 'network\|payload'`.

### Phase 2 — Drift Removal & Misplaced Files [Week 1–2]

#### Slice 2.1 — Pick one runtime: Celery or in-process

- **Scope:** `core/config.py`, `services/dispatch/*`, `tasks.py`, `core/dependencies.py`
- **Dimension:** D4 / D6
- **Severity:** 🟠
- **Deletion first:** Decide. If Celery is the target, delete `LocalRunDispatcher` and `legacy_inprocess_runner_enabled`. If staying in-process for dev only, gate Local behind `ENV=dev` and remove the runtime flag.
- **Acceptance criteria:**
  - One of: `grep -r "LocalRunDispatcher" backend/app` → 0 OR `grep -r "CeleryRunDispatcher" backend/app` → 0
  - `grep -r "legacy_inprocess_runner_enabled" backend/` → 0
- **Verify:** `pytest tests -q` plus `run_acquire_smoke.py commerce`.

#### Slice 2.2 — Move `extraction_context.py` into `extract/`

- **Scope:** `services/extraction_context.py` → `services/extract/extraction_context.py`
- **Dimension:** D4
- **Severity:** 🟡
- **Deletion first:** Update imports; delete the root file.
- **Acceptance criteria:** `grep -r "from app.services.extraction_context" backend/` → 0; new path imported instead.
- **Verify:** `pytest tests -q`.

#### Slice 2.3 — Decide `structured_sources.py` boundary

- **Scope:** `services/structured_sources.py`, `services/extract/structured_listing_handler.py`
- **Dimension:** D4
- **Severity:** 🟡
- **Action:** Either fold into `extract/structured_listing_handler.py` if scope overlaps, or keep at root with a clear docstring stating it owns the multi-surface structured harvesting (JSON-LD, microdata, OG, Nuxt, harvested JS state) shared by listing and detail.

#### Slice 2.4 — Move `dashboard_service.py`

- **Scope:** `services/dashboard_service.py` → `services/reporting/dashboard.py` (or under `crawl/`)
- **Dimension:** D4
- **Severity:** 🟡

#### Slice 2.5 — Retire `_LEGACY_PROMPTS_DIR`

- **Scope:** `services/llm/config_service.py`, prompts data files
- **Dimension:** D4
- **Severity:** 🟡
- **Deletion first:** Move any remaining files in `data/knowledge_base/prompts` to `data/prompts`. Remove `_LEGACY_PROMPTS_DIR`.
- **Acceptance criteria:** `grep -r "_LEGACY_PROMPTS_DIR\|knowledge_base/prompts" backend/` → 0.
- **Verify:** `pytest tests -q -k llm`.

#### Slice 2.6 — Move LLM circuit threshold default into config

- **Scope:** `services/llm/circuit_breaker.py`, `services/config/llm_runtime.py`
- **Dimension:** D5
- **Severity:** 🟡
- **Deletion first:** Delete `_DEFAULT_FAILURE_THRESHOLD` from `circuit_breaker.py`; move default to `llm_runtime_settings.circuit_failure_threshold` and remove the fallback branch.
- **Verify:** `pytest tests/services/test_llm_circuit_breaker.py -q`.

### Phase 3 — Detail family second pass [Week 2–3]

Each slice ≤ 0 net lines. Order by dependency.

#### Slice 3.1 — Split `extract/shared_variant_logic.py`

- **Scope:** `extract/shared_variant_logic.py` → split by concern
- **Dimension:** D3
- **Severity:** 🔴
- **Deletion first:** Identify each helper's true owner. Move identity, merge, richness, grouping, axis helpers into the existing dedicated files: `variant_record_normalization.py`, `variant_structural_pruning.py`, `variant_dom_cues.py`, `variant_value_guards.py`, `variant_group_validator.py`, or new `variant_identity.py` / `variant_grouping.py` if no existing owner fits.
- **Acceptance criteria:**
  - `extract/shared_variant_logic.py` deleted or reduced to ≤ 200 LoC of pure re-exports (with a deletion deadline)
  - No file with `shared_*` in its name remains under `extract/`
- **Verify:** `pytest tests/services -q -k 'variant'`.

#### Slice 3.2 — Split `extract/detail_dom_extractor.py`

- **Scope:** `extract/detail_dom_extractor.py`
- **Dimension:** D3
- **Severity:** 🔴
- **Deletion first:** Pull DOM context selection and DOM variant recovery into `extract/detail_dom_context.py` and `extract/detail_dom_variant_recovery.py`. Keep `detail_dom_extractor.py` for DOM fallback fields only.
- **Acceptance:** No new file > 500 LoC.
- **Verify:** `pytest tests/services/test_detail_extractor_structured_sources.py tests/services/test_detail_extractor_priority_and_selector_self_heal.py -q`.

#### Slice 3.3 — Split `extract/detail_materializer.py`

- **Scope:** `extract/detail_materializer.py`
- **Dimension:** D3
- **Severity:** 🔴
- **Deletion first:** Move rejection-reason helpers and failure-inference helpers into `extract/detail_rejection.py`. Keep materializer as record assembly + `_add_sourced_candidate` host.
- **Acceptance:** Materializer ≤ 700 LoC.

#### Slice 3.4 — Split `extract/detail_record_finalizer.py`

- **Scope:** `extract/detail_record_finalizer.py`
- **Dimension:** D3
- **Severity:** 🔴
- **Deletion first:** Move variant-backfill sequencing and variant-row repair into existing variant files. Keep finalizer for cleanup + final normalization.

#### Slice 3.5 — Split `extract/detail_price_extractor.py`

- **Scope:** `extract/detail_price_extractor.py`
- **Dimension:** D3
- **Severity:** 🔴
- **Deletion first:** Pull currency reconciliation into `extract/detail_currency_reconciliation.py`.

#### Slice 3.6 — Split `extract/detail_identity.py`

- **Scope:** `extract/detail_identity.py`
- **Dimension:** D3
- **Severity:** 🔴
- **Deletion first:** Pull URL-shape and listing-detail boundary checks into `extract/detail_url_shape.py`.

#### Slice 3.7 — Split `extract/detail_text_sanitizer.py`

- **Scope:** `extract/detail_text_sanitizer.py`
- **Dimension:** D3
- **Severity:** 🟠
- **Deletion first:** Pull fulfillment-copy cleanup into a separate file.

### Phase 4 — Pre-existing god modules [Week 3–4]

Same plan as the prior audit. Order by blast radius.

#### Slice 4.1 — Split `pipeline/extraction_loop.py`

- **Scope:** `services/pipeline/extraction_loop.py`
- **Dimension:** D3
- **Severity:** 🟠
- **Layout:**
  - `pipeline/url_runner.py` — `process_single_url` only
  - `pipeline/retries/{empty,low_quality,listing_integrity,patchright_real_chrome}.py`
  - `pipeline/extraction_post_processing.py`
  - `pipeline/contract_memory.py`
- **Acceptance:** `wc -l pipeline/url_runner.py` < 400; no retry helper > 250 LoC.

#### Slice 4.2 — Split `dom/selector_engine.py`

- **Scope:** `services/dom/selector_engine.py`
- **Layout:** `dom/selectors/{css,xpath,regex}.py`, `dom/text_scope.py`, `dom/images.py`, `dom/sections.py`.

#### Slice 4.3 — Split `acquisition/browser_runtime.py`

- **Scope:** `services/acquisition/browser_runtime.py`
- **Layout:** `browser_pool.py`, `browser_context.py`, `browser_limits.py`, plus existing `browser_diagnostics.py` absorbing diagnostics builders.

#### Slice 4.4 — Split `acquisition/traversal.py`

- **Scope:** `services/acquisition/traversal.py`
- **Layout:** pagination vs load-more vs card counting (latter already partially split into `traversal_card_counting.py`).

#### Slice 4.5 — Split `acquisition/browser_page_flow.py`

- **Scope:** `services/acquisition/browser_page_flow.py`
- **Layout:** navigation vs readiness vs DOM probes.

#### Slice 4.6 — Split `fetch/fetch_context.py`

- **Scope:** `services/fetch/fetch_context.py`
- **Layout:** decision vs escalation vs block-detection vs handoff.

#### Slice 4.7 — Slim `api/crawls.py`

- **Scope:** `api/crawls.py`
- **Layout:** `api/{crawls,crawl_recipes,crawl_profiles,crawl_feedback,crawl_websocket}.py`. Each ≤ 250 LoC. URL paths unchanged.

#### Slice 4.8 — Split `selectors_runtime.py`

- **Scope:** `services/selectors_runtime.py`
- **Layout:** execution vs scoring/fallback.

#### Slice 4.9 — Split `data_enrichment/service.py`

- **Scope:** `services/data_enrichment/service.py`
- **Layout:** job orchestration vs per-product enrichment vs LLM enrichment vs persistence.

### Phase 5 — Resilience & Test Quality [Week 4]

#### Slice 5.1 — Document and audit Redis TTL coverage

- **Scope:** `services/llm/cache.py`, `services/llm/circuit_breaker.py`, `services/acquisition/host_protection_memory.py`, `core/redis.py`
- **Action:** Add `docs/redis-ttls.md` listing every Redis key prefix and TTL. Add explicit setters where missing.

#### Slice 5.2 — Lock Celery as the production path

- **Scope:** Deployment config + docs
- **Depends on:** Slice 2.1 chose a path.

#### Slice 5.3 — Convert private-import tests to public-API tests

- **Scope:** Files listed in D7
- **Deletion first:** Delete each `from app.services.X import _Y` line.
- **Acceptance:** `grep -rE "import _\\w+" backend/tests` → only allowed shims.

### Phase 6 — Dead Code Elimination [Week 5]

#### Slice 6.1 — Add pytest tmp cleanup

- **Scope:** `backend/conftest.py`
- **Action:** session-scoped finalizer to prune `.pytest-tmp/case-*` older than N days.

#### Slice 6.2 — Retire `_legacy_artifact_paths`

- **Scope:** `services/dashboard_service.py` (or wherever it lives after Slice 2.4)
- **Action:** Add a 1-release deprecation, then delete.

#### Slice 6.3 — Retire `legacy_keys` / `legacy_aliases` in profile merge

- **Scope:** `services/crawl/profile/merge.py`
- **Action:** Set a sunset date, log a warning when legacy keys are encountered, then remove.

---

## Skipped or Out-of-Scope

- **Frontend deep dive** — not requested. Headlines: ~14 unit suites; Playwright smoke. No findings warranting blocking work.
- **Detailed jscpd run** — not executed. Spot checks (`_request_json` across adapters) show shared base class properly used. Worth running once after Phase 1 to confirm hollowing did not leave duplicates.

---

## Reviewer Integrity Notes

- All file sizes verified at HEAD via direct `os.path.getsize` and line counts on 2026-05-17.
- Invariant-compliance claims are grep- and code-confirmed where cited; where not cited, treat as `[NEEDS GREP]` for any future re-audit.
- No 🔴 invariant blockers found; the seven 🔴 in this report are all structural (D3/D4) and gate the next feature work, not crawler correctness.

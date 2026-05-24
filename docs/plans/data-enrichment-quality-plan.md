# Plan: Data Enrichment Quality Improvements

**Created:** 2026-05-24
**Agent:** Codex
**Status:** DONE
**Touches buckets:** data enrichment service, deterministic enrichment, Shopify catalog matching, backend docs

## Goal

Improve ecommerce enrichment fill-rate and precision without changing crawl output. Done means LLM prompt/context is explicit and bounded, deterministic normalization covers the audited misses, Shopify taxonomy matching stays deterministic, and enrichment tests verify the behavior.

## Acceptance Criteria

- [x] LLM enrichment prompt has explicit schema, field limits, Shopify taxonomy rule, and missing-fields-only rule.
- [x] LLM context includes 600-character description excerpt and structured taxonomy candidates.
- [x] Deterministic fixes cover material percentages, department gender, size delimiters/context, price sale/original, color aliases, and SEO brand phrase.
- [x] Semantic taxonomy rerank removed from the live path; deterministic Shopify taxonomy matching remains primary.
- [x] `ai_discovery_tags` are selected from generated allowed tags, not arbitrary freeform output.
- [x] Existing enrichment public API/storage shapes remain compatible.
- [x] `.\.venv\Scripts\python.exe -m pytest tests\services\test_data_enrichment.py -q` exits 0.
- [x] `.\.venv\Scripts\python.exe -m pytest tests -q` exits 0, or blocker is recorded.

## Do Not Touch

- `publish/*`, `pipeline/*`, exports — enrichment must not hide upstream extraction pollution.
- Raw `CrawlRecord.data` persistence — enrichment reads source data only.
- Frontend — audit scope is backend enrichment.
- Cross-product bundle inference — deferred P3.
- pgvector or database migrations — deferred unless taxonomy scale changes.

## Slices

### Slice 1: Prompt And LLM Context
**Status:** DONE
**Files:** `backend/app/data/prompts/data_enrichment_semantic.system.txt`, `backend/app/data/prompts/data_enrichment_semantic.user.txt`, `backend/app/services/data_enrichment/service.py`, `backend/app/services/config/data_enrichment.py`
**What:** Rewrite the system prompt, increase excerpt length, expose structured taxonomy candidates, and add allowed discovery tags to prompt context.
**Verify:** Focused prompt-context tests cover missing fields, 600-character excerpt, structured taxonomy candidates, and no raw artifacts.

### Slice 2: Deterministic Normalizers
**Status:** DONE
**Files:** `backend/app/services/data_enrichment/deterministic.py`, `backend/app/services/config/data_enrichment.py`
**What:** Implement gender department source, color aliases, size delimiters/context relaxation, material percentage-first parsing, sale/original price shape, brand phrase SEO, and suffix-key dedupe.
**Verify:** Unit tests cover each audited normalizer fix and existing deterministic tests still pass.

### Slice 3: Deterministic Taxonomy Matching
**Status:** DONE
**Files:** `backend/app/services/data_enrichment/shopify_catalog.py`, `backend/app/services/data_enrichment/deterministic.py`, `backend/app/services/config/data_enrichment.py`, `backend/pyproject.toml`
**What:** Keep Shopify exact path/leaf matching and deterministic token scoring; remove local embedding rerank from live enrichment.
**Verify:** Tests cover exact match precedence, token fallback, low-confidence null category, and no non-Shopify category output.

### Slice 4: LLM Payload Validation
**Status:** DONE
**Files:** `backend/app/services/data_enrichment/service.py`, `backend/app/services/data_enrichment/deterministic.py`, `backend/app/services/config/data_enrichment.py`
**What:** Enforce 80-character semantic list limits, controlled `ai_discovery_tags`, unchanged non-overwrite behavior, and Shopify taxonomy validation.
**Verify:** LLM backfill tests cover valid controlled tags, rejected unknown tags, no deterministic overwrite, and existing diagnostics.

### Slice 5: Docs And Full Verify
**Status:** DONE
**Files:** `docs/backend-architecture.md`, `docs/plans/ACTIVE.md`, `docs/plans/data-enrichment-quality-plan.md`
**What:** Document deterministic Shopify taxonomy matching and update plan status as slices complete.
**Verify:** Run focused enrichment tests, then full backend test suite.

## Doc Updates Required

- [x] `docs/backend-architecture.md` — document deterministic Shopify taxonomy matching.
- [ ] `docs/CODEBASE_MAP.md` — not needed unless new files are added.
- [ ] `docs/INVARIANTS.md` — not needed unless enrichment contract changes.
- [ ] `docs/ENGINEERING_STRATEGY.md` — not needed.

## Notes

- Scope is P0-P2 only.
- Semantic rerank was removed after it caused live enrichment to hang during optional model import/load.
- No local category synonym maps are added.
- Shopify taxonomy and Shopify attributes remain source of truth for category and normalized attributes.
- 2026-05-24: Focused enrichment suite passed: `.\.venv\Scripts\python.exe -m pytest tests\services\test_data_enrichment.py -q` reported 46 passed, 11 warnings.
- 2026-05-24: Targeted regression check passed: `.\.venv\Scripts\python.exe -m pytest tests\services\test_llm_runtime.py::test_load_prompt_file_reads_canonical_prompt_directory tests\services\test_structure.py::test_service_files_stay_under_loc_budget tests\services\test_data_enrichment.py -q` reported 48 passed, 11 warnings.
- 2026-05-24: Full backend suite passed after one timeout retry: `.\.venv\Scripts\python.exe -m pytest tests -q` reported 1950 passed, 15 skipped, 16 warnings.
- 2026-05-24: `uv lock` refreshed `backend/uv.lock` for the optional `enrichment` extra. Post-lock focused check passed: `.\.venv\Scripts\python.exe -m pytest tests\services\test_data_enrichment.py -q` reported 46 passed, 11 warnings.

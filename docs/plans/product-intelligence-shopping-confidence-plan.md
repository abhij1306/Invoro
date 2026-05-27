# Plan: Product Intelligence Shopping Confidence

**Created:** 2026-05-27
**Agent:** Codex
**Status:** DONE
**Touches buckets:** product intelligence backend, product intelligence config/data, frontend Product Intelligence UI, API types, docs

## Goal

Improve Belk category-crawl product discovery for the client presentation by making SerpAPI discovery shopping-aware, loading Belk brand and exclusive-brand knowledge from a maintained registry, improving deterministic confidence evidence from fields already present in category/listing records, and improving the Product Intelligence page so comparison confidence and match evidence are easy to see.

Phase 1 deliberately does not depend on Belk detail crawl enrichment or image matching. Phase 2 will add richer Belk detail extraction (`sku_upc`/barcode-like fields) and a Product Intelligence launch path from detail crawl records.

## Acceptance Criteria

- [x] SerpAPI discovery queries Google Shopping first and keeps organic search as fallback.
- [x] Shopping candidates include product URL, merchant/source, price, thumbnail, `product_id`/page token when present, and evidence explaining why the URL was selected.
- [x] Phase 1 source snapshot extraction preserves existing category/listing identifiers already present in records, especially `sku`, `style`, `style_id`, `mpn`, and `product_id`, without assuming barcode/UPC exists.
- [x] Match confidence separates available identifier evidence, title similarity, brand match, Shopping result evidence, price band, and source authority.
- [x] Belk brand registry is loaded from project data, deduped, and used for source-brand inference from Belk title/URL before generic guessing.
- [x] Belk exclusive brands listed after `Belk Exclusive:` in `belk.md` are added to the private-label/exclusion set used by `private_label_mode="exclude"`.
- [x] Product Intelligence UI shows source-vs-candidate comparison, confidence reason chips, source type/provider, price delta, and clearer selected/batch-crawl state.
- [x] Phase 2 plan is captured for Belk detail `sku_upc` extraction and Product Intelligence entry point from detail crawl.
- [x] Focused backend and frontend tests pass.

## Do Not Touch

- `publish/*` and export cleanup paths — discovery/matching issues belong upstream in Product Intelligence.
- Extraction candidate architecture in `detail_extractor.py` and `extract/detail/*` — this work consumes existing crawl records only.
- Archived audits or old abandoned plans — not needed for this feature.
- Global frontend theme tokens except where existing Product Intelligence components need tokenized classes.

## Slices

### Slice 1: Belk Registry and Exclusive Brands
**Status:** DONE
**Files:** `belk.md`, `backend/app/services/config/product_intelligence.py`, `backend/app/services/product_intelligence/matching.py`, new `backend/app/data/product_intelligence/*`, `backend/tests/component/test_product_intelligence.py`
**What:** Move the Belk brand list and exclusive section into backend data files or a generated data artifact. Add a small loader owned by Product Intelligence. Use the full brand set for longest-match inference from Belk URLs/titles. Add exclusive brands to private-label detection so `private_label_mode="exclude"` removes Belk-owned/private-label products.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/component/test_product_intelligence.py -q`

### Slice 2: SerpAPI Shopping Discovery
**Status:** DONE
**Files:** `backend/app/services/config/product_intelligence.py`, `backend/app/services/product_intelligence/discovery.py`, `backend/app/services/product_intelligence/matching.py`, `backend/tests/component/test_product_intelligence.py`
**What:** Keep `search_provider="serpapi"` but make it Shopping-first. Query `engine=google_shopping` with natural query text, parse `shopping_results`, clean direct merchant URLs where available, retain `product_id`, `product_link`, `serpapi_immersive_product_api`, merchant/source, price, extracted price, rating/reviews, delivery, and thumbnail in payload. Fall back to current organic results when Shopping has no acceptable PDP candidate.
**Verify:** Focused discovery tests prove shopping-first order, organic fallback, URL cleaning, payload preservation, and domain/source-type ranking.

### Slice 3: Confidence Evidence and Scoring
**Status:** DONE
**Files:** `backend/app/services/config/product_intelligence.py`, `backend/app/services/product_intelligence/matching.py`, `backend/app/services/product_intelligence/discovery.py`, `backend/tests/component/test_product_intelligence.py`
**What:** Replace the single identifier boolean with evidence buckets for data available in category/listing records: `sku_match` when both sides expose the same SKU, `mpn_or_style_match`, `shopping_product_group`, `brand_match`, `title_similarity`, `price_band_match`, and `source_authority_bonus`. Keep weights in config. Do not add image/Lens logic in this phase. Prevent weak identifiers from producing high confidence unless brand/title or Shopping evidence also agree.
**Verify:** Tests cover medium/high confidence for matching SKU/style when supported by brand/title, low/uncertain for title-only, Shopping evidence boosts, and downrank for conflicting numeric identifiers.

### Slice 4: Product Intelligence UI Presentation
**Status:** DONE
**Files:** `frontend/app/product-intelligence/product-intelligence-results.tsx`, `frontend/app/product-intelligence/product-intelligence-candidate-card.tsx`, `frontend/app/product-intelligence/product-intelligence-utils.ts`, `frontend/lib/api/types.ts`, related local tests if present
**What:** Redesign the result area into a clearer operator comparison view. Each source group should show source brand/title/price/identity. Each candidate should show candidate title/domain/provider/source type, confidence percent, reason chips, price delta, image, query used, rank, and obvious actions. Add a compact comparison strip so the client can see why one URL is better than another.
**Verify:** Frontend typecheck/lint or the smallest available Product Intelligence UI test command; visually inspect the page in browser if dev server is available.

### Slice 5: Phase 2 Backlog Capture
**Status:** DONE
**Files:** this plan, optionally new follow-up plan under `docs/plans/`
**What:** Capture second-phase work without implementing it in this phase: improve Belk detail crawl extraction for `sku_upc`/UPC/barcode-like fields, map valid UPC/barcode through existing public identity validation, preserve retailer SKU separately from UPC, and add a Product Intelligence action/button from detail crawl records so operators can send richer PDP records into Product Intelligence.
**Verify:** Phase 2 scope is explicit and not mixed into Phase 1 implementation.

### Slice 6: Docs and Final Verification
**Status:** DONE
**Files:** `docs/backend-architecture.md`, `docs/frontend-architecture.md`, `docs/plans/ACTIVE.md`, this plan
**What:** Document Shopping-first SerpAPI discovery, Belk registry ownership, confidence scoring behavior, frontend UI ownership changes, and the deferred Phase 2 detail-crawl integration. Mark acceptance criteria and close plan only after verification.
**Verify:** Run focused backend test, relevant frontend check, then broader backend verification if shared behavior changed.

## Doc Updates Required

- [x] `docs/backend-architecture.md` — Product Intelligence discovery/scoring now uses SerpAPI Shopping and Belk registry data.
- [x] `docs/frontend-architecture.md` — Product Intelligence UI presentation and evidence display changed.
- [x] `docs/CODEBASE_MAP.md` — only if new data loader/file ownership is not already obvious.
- [x] `docs/INVARIANTS.md` — not expected for Phase 1; Phase 2 must preserve barcode/public identity contract.

## Notes

- `docs/plans/ACTIVE.md` had a completed AI Discoverability plan; this is new active work by user request.
- `belk.md` currently has 2250 brand rows, 2235 unique normalized brands, and a trailing `Belk Exclusive:` section that should become private-label/exclude data.
- Current SerpAPI code only parses organic results, so Shopping support belongs in `product_intelligence/discovery.py`, not downstream exports.
- Google Product API is deprecated/shut down in SerpAPI docs; do not build on it. Use Shopping results and optionally Immersive Product tokens later.
- User clarified on 2026-05-27: category/listing data has `sku`, but richer `sku_upc` needs Belk detail crawl work. Phase 1 must not block on barcode/sku_upc. Phase 2 should add detail-crawl extraction and Product Intelligence button/action from detail records.
- Slice 1 verify passed: `tests/component/test_product_intelligence.py -q` -> 65 passed.
- Slice 2 verify passed: `tests/component/test_product_intelligence.py -q` -> 67 passed.
- Slice 3 verify passed: `tests/component/test_product_intelligence.py -q` -> 69 passed.
- Slice 4 verify passed: `npm run lint` from `frontend` exited 0.
- Slice 5 created queued follow-up plan: `docs/plans/product-intelligence-belk-detail-integration-plan.md`.
- Slice 6 verify passed: `tests/component/test_product_intelligence.py -q` -> 71 passed, 11 warnings; `npm run lint` from `frontend` exited 0.
- Live DB verification on existing Belk crawl data: local DB had 117 Belk records. Record 119 (`IZOD Comfort Stretch Blue Denim Jeans`, SKU `3203394I39JN16`) now uses natural Google Shopping query text (`izod comfort stretch blue denim jeans`) instead of the organic `site:` query, returning 40 Shopping rows and 13 Immersive store links for the first Shopping product. Full discovery returned 3 candidates including a `serpapi_immersive` store URL with `shopping_product_group=True`.

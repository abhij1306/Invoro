# Plan: Product Intelligence Belk Detail Integration

**Created:** 2026-05-27
**Agent:** Codex
**Status:** DONE
**Touches buckets:** Belk ecommerce detail extraction, Product Intelligence frontend entry point, Product Intelligence backend source snapshots

## Goal

Second-phase Product Intelligence improvement after Shopping-first discovery. Add richer Belk detail crawl identity extraction and make it easy to launch Product Intelligence from detail crawl records, so matching can use valid UPC/barcode-like identifiers when present while keeping retailer SKU separate.

## Acceptance Criteria

- [x] Belk detail extraction captures `sku_upc`/UPC-like values when present on PDPs.
- [x] Valid UPC/barcode-like values follow the existing public barcode contract: digits-only, lengths `8`, `12`, `13`, or `14`.
- [x] Retailer SKU remains separate from UPC/barcode identity; do not overwrite SKU with UPC or UPC with SKU.
- [x] Product Intelligence source snapshots can consume the richer detail fields without requiring them for category/listing discovery.
- [x] Detail crawl UI has a Product Intelligence action/button for selected PDP records.
- [x] Focused Belk detail and Product Intelligence tests pass.

## Do Not Touch

- Phase 1 SerpAPI Shopping discovery unless a test reveals a direct integration bug.
- Downstream publish/export cleanup paths.
- Generic extraction architecture outside the Belk/detail-owned field extraction path.

## Slices

### Slice 1: Belk Detail Identity Audit
**Status:** DONE
**Files:** Belk detail crawl fixtures/artifacts, extraction tests
**What:** Inspect existing Belk detail crawl records and HTML/artifacts to identify where `sku_upc`, UPC, barcode, SKU, and style identifiers appear.
**Verify:** Belk PDP state payload fields audited and covered by test: `sku_upc`/UPC-like values can appear directly or under nested variant/product objects and are coerced through public barcode rules.

### Slice 2: Detail Extraction
**Status:** DONE
**Files:** owning Belk/detail extraction modules and focused tests
**What:** Extract valid UPC/barcode-like values and preserve retailer SKU separately.
**Verify:** Focused Belk adapter regression test passes and proves `sku_upc`/`barcode` are present while SKU/product ID remains separate.

### Slice 3: Product Intelligence Detail Entry
**Status:** DONE
**Files:** crawl record UI, Product Intelligence prefill flow, API types as needed
**What:** Add a Product Intelligence action for detail crawl records so richer PDP records can be sent directly to Product Intelligence.
**Verify:** Frontend crawl-run screen test covers ecommerce detail record Product Intelligence prefill and route transition.

### Slice 4: Scoring Integration
**Status:** DONE
**Files:** Product Intelligence source snapshot/scoring tests
**What:** Consume valid UPC/barcode evidence in Product Intelligence scoring after detail extraction supplies it.
**Verify:** Product Intelligence component tests prove valid barcode/GTIN evidence can reach high confidence, SKU-supported evidence remains medium, Shopping store links rank before organic fallback, and natural Shopping-first queries run before brand-domain organic fallback.

## Doc Updates Required

- [x] `docs/backend-architecture.md` — Belk detail identity extraction and Product Intelligence detail flow.
- [x] `docs/frontend-architecture.md` — detail crawl Product Intelligence action.
- [x] `docs/INVARIANTS.md` — no change; public barcode contract unchanged.

## Notes

- Created as queued Phase 2 from `product-intelligence-shopping-confidence-plan.md`.
- Do not implement this until Phase 1 is closed and demo-critical Shopping-first discovery is verified.
- Implementation keeps discovery time bounded by reordering existing SerpAPI work: natural Shopping query first, Immersive Product stores before organic fallback, default 4 candidates/product with a larger result pool but no extra query family.
- Verification passed: `tests/component/test_product_intelligence.py -q` -> 77 passed; focused Belk adapter regression (`-m regression -k "detail_sku_upc or listing_brand_from_state"`) -> 2 passed; `npm test -- crawl-run-screen.test.tsx` -> 29 passed; `npm run lint` -> passed.

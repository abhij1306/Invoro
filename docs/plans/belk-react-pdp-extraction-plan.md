# Plan: Belk React PDP Extraction Fixes (Multi-Variant, No LLM)

**Created:** 2026-05-30
**Agent:** Claude
**Status:** COMPLETE
**Touches buckets:** Bucket 4 (Extraction: Belk adapter + extraction_rules config)

## Goal

Belk's newer React/Next PDP template (sneakers, run_id=6) carries full product data in the Tealium `utag_data` analytics object inside `__next_f`, but multi-variant products break extraction. Same `utag_data` schema as appliances, except per-SKU fields are **parallel arrays** (one entry per size/color variant), e.g. `sku_id[i]` ↔ `sku_upc[i]` ↔ `sku_price[i]`, while product-level fields stay length-1. Fix extraction so multi-variant Belk PDPs produce correct identity, UPC, and variant rows. Deterministic only, no LLM.

Done looks like: a multi-variant Belk sneaker PDP yields a record with the correct `barcode` (UPC), correct `product_id`, correct `color`, a sensible `title`, and variant rows that each carry their own UPC/size/color.

## Acceptance Criteria

- [ ] Multi-element `sku_upc` produces a product-level `barcode` (selected/first variant UPC) instead of dropping it.
- [ ] Each variant row maps to its own UPC via `sku_id[i] == variantId`.
- [ ] `product_id` no longer takes nav/breadcrumb junk like `"women"`; it uses the `utag_data` `product_id`.
- [ ] `color` holds a real color (not a size code); size and color axes are correctly separated.
- [ ] `title` is the real product name, not UI junk ("Mobile Users").
- [ ] `python -m pytest tests -q` passes (excluding the known unrelated fetch-timeout flake).

## Do Not Touch

- Discovery/matching scoring (closed plan `belk-product-discovery-recall-plan.md`).
- Generic JS-state variant mapping for non-Belk platforms — fix Belk in the adapter, do not regress shared mappers unless the change is provably generic.
- LLM paths.

## Slices

### Slice 1: Per-variant UPC mapping from parallel `utag_data` arrays
**Status:** DONE
**Files:** `backend/app/services/adapters/belk.py`, `backend/app/services/config/extraction_rules/_listing_structured.py`, `backend/app/services/config/variant_policy.py`, `backend/tests/regression/test_selectolax_css_migration.py`
**What:** In the Belk adapter, when the `utag_data` product object exposes parallel per-SKU arrays (`sku_id`, `sku_upc`, `sku_price`, `sku_inventory`, `sku_out_of_stock`, `sku_image_url`), zip them index-aligned into per-variant rows and join to the variant objects (`variantId == sku_id[i]`) for the size label. Each variant row carries its own `barcode` (UPC). Product-level `barcode` = first in-stock variant UPC (else first valid). Added `barcode` to `FLAT_VARIANT_KEYS` so per-variant UPC survives the public variant boundary (INVARIANTS Rule 3 variant contract extended — see Doc Updates).
**Done (2026-05-30):** Adapter-level output verified on the real capture (`53877075ebf7c5c8.html`, UA Charged Commit): product `barcode=0198633940142`, 40 variant rows each with `size`, `sku`, own `barcode`, `price`, `availability`, `stock_quantity`. New regression test `test_belk_adapter_maps_per_variant_upc_from_utag_sku_arrays` PASSED; existing Belk + config regression tests still green.
**Known remaining (handled in Slice 2):** when the adapter record merges with generic DOM variant extraction, the generic extractor mislabels Belk size radios as `color`, polluting the final merged variants (count inflated, color holds size codes). Adapter source is correct; the merge/axis bug is Slice 2.

### Slice 2: Fix product_id, color/size axis, and title source
**Status:** DONE (2026-05-30) — generic root cause fixed: unlabeled-axis misclassification + Cartesian merge guard
**Files:** `backend/app/services/config/extraction_rules/_listing_structured.py` (size value patterns), `backend/app/services/config/extraction_rules/_variants.py` (mislabeled-axis overlap threshold), `backend/app/services/extract/variant_identity_merge.py` (`axis_values_are_mislabeled_duplicate`, `resolve_variants` collapse guard), `backend/app/services/extract/detail/variants/dom_extraction.py` (`_real_new_dom_axes` guard on DOM backfill expansion), `backend/tests/unit/test_shared_variant_logic.py` (5 new tests).
**Root cause (verified BEFORE/AFTER on `53877075ebf7c5c8.html` via throwaway probe):**
- `product_id`/`title`/`color` are correct whenever the adapter wins (confirmed on the real capture). The `"women"`/`"Mobile Users"` rows came from captures where the adapter returned 0 — an adapter-coverage gap on incomplete snapshots, not a logic bug where data is present.
- The real defect was generic and reproduced without any Belk check: footwear sizes shaped `<number><width-letter>` (`10M`, `8.5M`, `11.5XW`) matched **no** `VARIANT_SIZE_VALUE_PATTERNS`, so value-based axis inference returned nothing and the unlabeled size radiogroup borrowed a `color` label from a neighbouring swatch block. A correct size source from another tier then merged as an independent axis → Cartesian product (15→225 / 40→225 garbled rows like `{"color":"10M","size":"10.5M"}`).
**Fix (generic, deterministic, no LLM, no host checks — INVARIANTS Rule 13):**
1. Extended `VARIANT_SIZE_VALUE_PATTERNS` (config, Rule 1) to recognise numeric footwear sizes with US/EU width codes (`AAAA..EEEE`, `[2-6]E`, N/M/W, band+cup `32A`/`34DD`) and waist×inseam (`32x30`). Unlabeled numeric/size groups now infer `size`; `color` only wins for recognised color tokens. Reused existing `variant_size_value_patterns` / `infer_variant_group_name_from_values`; no duplicate size logic added.
2. Added a generic merge guard: `axis_values_are_mislabeled_duplicate` (config-driven `VARIANT_MISLABELED_AXIS_MIN_OVERLAP_RATIO`). `resolve_variants` collapses a matrix axis that is the same single axis mislabeled under two names, and DOM backfill (`_real_new_dom_axes`) no longer treats a value-overlapping DOM axis as a new axis. A single-axis source can no longer be exploded by a conflicting mislabeled axis from another source.
- Kept the per-field candidate + `finalize_candidate_value` architecture (Rule 3); variants still finalize across all sources.
**Verify (DONE):** BEFORE probe = 15 rows all `{"color":"10M"...}`, count inflated; AFTER probe = single `size` axis, no cross-product, barcodes preserved. New unit tests in `test_shared_variant_logic.py` cover (a) unlabeled numeric/size group → `size` not `color`, and (b) single-axis source not exploded by a mislabeled axis. Full suite `pytest tests -q` = 1166 passed.

### Slice 3: Full verify
**Status:** DONE (2026-05-30)
**Verify:** `python -m pytest tests -q` → 1166 passed, 972 deselected (regression/live/integration/e2e markers), 0 failed. The known unrelated fetch-timeout flake did not recur in this run.

## Doc Updates Required

- [x] `docs/INVARIANTS.md` Rule 3 — variant transport contract extended: `barcode` added to `FLAT_VARIANT_KEYS` so per-variant UPC is a public variant transport field. (Pending: update the INVARIANTS text to list `barcode` among allowed variant row fields.)
- [ ] `docs/CODEBASE_MAP.md` — no new files; not required.

## Notes

- Evidence (run_id=6, `53877075ebf7c5c8.html`, UA Charged Commit): `product_name:["Charged Commit TR Sneakers"]`, `product_id:["39003106007140"]`, `product_color:["Blue"]`, `product_size:["8.5M"]`, `sku_id:[111]`, `sku_upc:[111]`. Variant objects: `{"variantId":"048006...","color":"289475425516","size":{"sizeName":"10M"}}` — `variantId` pairs to `sku_id` array.
- Same `utag_data` schema as appliances; appliances were length-1 arrays (Slice 1 of prior plan handled those). This plan handles the multi-element arrays.
- Buggy DB output before fix: `product_id="women"` (from nav `data-cgid`), `color` holding size codes (`{"color":"8M"}`), `title="Mobile Users"`, `barcode=null`.

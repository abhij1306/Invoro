# Plan: Belk Product Discovery Recall (UPC-First, No LLM)

**Created:** 2026-05-30
**Agent:** Claude
**Status:** DONE
**Touches buckets:** Bucket 4 (Extraction: Belk adapter + extraction_rules config), Bucket 2 (product_intelligence discovery + matching), config (`config/product_intelligence.py`), schemas (`schemas/product_intelligence.py`)

## Goal

Improve discovery recall for **BELK_BRAND (non-exclusive)** products on belk.com so the pipeline finds all major external listings for a Belk-listed product, using deterministic signals only (no LLM, no new external APIs). Two levers, matching the user's confirmed scope:

1. **UPC-first identity.** Belk PDP pages expose a UPC, but current crawls surface only `sku`. Fix extraction so the UPC is captured on `ecommerce_detail` Belk records, then make discovery query construction and matching prefer UPC over SKU as the primary identifier (matching already weights GTIN highest; queries currently append the SKU/MPN-like token instead of the UPC).
2. **Lift recall caps.** Today `max_urls_per_result_domain=1` and the per-product candidate ceiling is low, so multiple legitimate listings per retailer are discarded. Raise caps so breadth is bounded only by the user-supplied request options, not by hardcoded defaults.

Done looks like: a Belk PDP crawl emits a `barcode` (UPC) field; discovery for a Belk-brand source product issues UPC-leading queries and returns more than one listing per retailer domain when the user requests a higher cap; SerpAPI dispatch behavior is unchanged; `pytest tests -q` passes.

## Acceptance Criteria

- [x] Belk `ecommerce_detail` extraction emits the UPC as `barcode` (and it flows to the PI source snapshot `gtin`) when the PDP JS state carries a UPC/`sku_upc` value.
- [x] `build_search_queries` uses the UPC/GTIN as the primary appended identifier for brand+title queries instead of the SKU/MPN-like token, while keeping the standalone quoted-GTIN query first.
- [x] Matching treats a UPC match as the strongest signal AND, because search payloads lack UPC, brand-exact + strong-title reaches the auto-accept (high) band; SKU/style/product_id are no longer scored.
- [x] Per-domain throttle removed so multiple third-party-seller listings per marketplace survive; breadth is bounded by the user's `max_candidates_per_product` request option.
- [x] SerpAPI search dispatch (`_search_serpapi`, `_search_serpapi_engine`, engine order, immersive expansion) is unchanged in behavior.
- [x] `python -m pytest tests -q` (1151 passed; 1 unrelated pre-existing timing flake).

## Do Not Touch

- `_search_serpapi`, `_search_serpapi_engine`, `_shopping_query`, `_brand_scoped_query`, immersive expansion logic in `discovery.py` — user verified current SerpAPI dispatch matches results correctly; optimizing it previously broke matching. Recall changes must come from caps + query identifier choice, not dispatch rewrites.
- `google_native` session logic — out of scope for this slice.
- Image/pHash / Tier-4 visual match — investigation-only, explicitly deferred by user (item 6).
- BELK_EXCLUSIVE routing, `unauthorized_flag`, `alert_level`, evidence package, tiered cadence, output-schema changes — out of scope (user items 1, 7).
- LLM paths — must stay opt-in/disabled; no LLM added.

## Slices

### Slice 1: Capture Belk PDP UPC on ecommerce_detail
**Status:** DONE
**Files:** `backend/app/services/adapters/belk.py`, `backend/app/services/config/extraction_rules.exports.json`, `backend/tests/regression/test_selectolax_css_migration.py`
**Root cause (CONFIRMED against real artifact `artifacts/runs/2/pages/06c189b10504749e.html`):**
- Belk PDPs carry the UPC in a Tealium `utag_data` analytics object inside the Next.js `__next_f` RSC payload, where **every value is a single-element list**, e.g. `"product_name":["Egg Cooker"]`, `"product_url":["https://www.belk.com/p/.../8100339TM1ECBL.html"]`, `"sku_id":["0438684935095"]`, `"sku_upc":["0655772019097"]`.
- `_looks_like_product_payload(utag_data)` returns `False` because `coerce_field_value` does not unwrap the single-element lists: title coerces to the literal string `"['Egg Cooker']"` and brand/price/image coercion fail, so the object is rejected as a product.
- Result: the adapter recognizes only brand-navigation tiles (shop-by-brand) and returns 0 records for the PDP; generic detail extraction then derives `sku` from the URL slug and the UPC silently drops (`coerce_field_value("barcode", ["0655772019097"]) == None`).
- `sku_upc` is the UPC (distinct from `sku_id`); it is already first in `BELK_PRODUCT_BARCODE_KEYS`. The 13-digit length passes `coerce_barcode`; the only blocker is list-wrapping. `ROUTE_BARCODE_TO_SKU` / barcode-length set are NOT the cause — do not touch them.
**What:**
- In the Belk adapter, unwrap single-element-list values from the `utag_data`-style analytics payload before field coercion, and recognize that object as a product payload so its `sku_upc` → `barcode`, `product_name` → title, `product_url` → url, `product_brand` → brand, `product_id` → product_id flow through normally.
- Keep the change scoped to the adapter (Bucket 4, INVARIANTS Rule 3 — fix upstream, no downstream compensation). Keep `barcode` as canonical UPC output (already in the `ecommerce_detail` schema, not default-excluded).
- Prefer `sku_upc` as the UPC source; do not let `sku_id` overwrite it.
**Done (2026-05-30):**
- Added `_unwrap_single_element` in `belk.py`; applied it in `_first_payload_field` and the nested barcode walk so list-wrapped scalars coerce correctly.
- Added Belk analytics key aliases to the config tuples (`product_brand`, `product_price`, `product_original_price`, `product_image_url`) so `_looks_like_product_payload` recognizes the `utag_data` object. `product_name`/`product_url`/`sku_upc` were already present.
- Verified end-to-end against the captured real payload shape: adapter now returns 1 detail record with `title="Egg Cooker"` (no list literal), `barcode="0655772019097"` (the UPC, distinct from `sku_id`), and the UPC survives the public firewall on `ecommerce_detail`.
**Verify:** New regression test `test_belk_adapter_extracts_upc_from_listwrapped_utag_data_detail` in `backend/tests/regression/test_selectolax_css_migration.py`. PASSED with all 5 Belk regression tests and 39 config-import tests. Command: `.\.venv\Scripts\python.exe -m pytest tests/regression/test_selectolax_css_migration.py -m regression -k belk`.

### Slice 2: Prefer UPC over SKU in discovery query construction
**Status:** DONE
**Files:** `backend/app/services/product_intelligence/discovery.py` (`build_search_queries`), `backend/tests/component/test_product_intelligence.py`.
**What:**
- In `build_search_queries`, make the UPC/GTIN the primary identifier appended to brand+title and brand-site queries, falling back to MPN/style only when no UPC is present. Keep the existing standalone quoted-GTIN query as the first query.
- Do not change the SerpAPI dispatch or the query *count/order* contract beyond swapping which identifier token is appended. Keep stop-word stripping and existing dedupe.
**Done (2026-05-30):**
- Introduced `query_identifier = gtin or mpn` and used it where `mpn` was previously appended. Query count/order/dedupe unchanged; behavior identical when no UPC is present (so all existing query tests stay green).
**Verify:** New component test `test_product_intelligence_query_prefers_upc_over_mpn_as_identifier`. PASSED with all 14 `build_search_queries`/discovery query tests. Command: `.\.venv\Scripts\python.exe -m pytest tests/component/test_product_intelligence.py -m component -k query`.

### Slice 3: Lift recall caps + confidence recalibration (UPC-irrelevant scoring)
**Status:** DONE
**Files:** `backend/app/services/config/product_intelligence.py`, `backend/app/services/product_intelligence/matching.py`, `backend/app/schemas/product_intelligence.py`, `backend/tests/component/test_product_intelligence.py`
**Design (validated on real run_id=3 Belk products via live SerpAPI):**
- One product can be listed by multiple third-party sellers on a marketplace (Amazon/eBay), so the per-domain throttle had to go. Set `max_urls_per_result_domain = 25` and raised `max_candidates_per_product` default to 15 (schema ceiling `le=100`) and `discovery_pool_multiplier` to 4. Output = every match sorted by confidence descending, capped by the user's request.
- Live testing proved SerpAPI/Google result payloads never carry a UPC, and Belk SKU/style/product_id are meaningless to external retailers. So scoring now **drops SKU/MPN/style entirely** and is driven by brand-exact + title-similarity (+ price band + source authority). GTIN still scores/floors when present (e.g. after candidate crawl).
- Added confidence floors: brand-exact + title-sim ≥0.90 → 0.85 high (0.88 with price); brand-exact + title-sim ≥0.75 → 0.65 medium; brand-DTC + brand-exact → 0.90 (brand's own listing always ranks highest); GTIN match → 0.92.
- Added deterministic variant/spec mismatch guard (capacity unit + "N-in-1"): when both titles state the spec and values differ, penalize and cap below auto-accept (verified: Ninja Crispi 3-in-1 capped at 0.62 while true 4-in-1 matches reached 0.88).
**Verify (live + tests):**
- Live probe over the 4 run_id=3 Belk products: true same-product matches (macys/jcpenney/crateandbarrel/nfm/hsn/bloomingdales/ubereats) now reach 0.85–0.88 high; wrong-variant 3-in-1 listings correctly drop to ≤0.62; brand DTC floors at 0.90.
- `python -m pytest tests/component/test_product_intelligence.py -m component` → 95 passed (stale SKU-scoring and per-domain-diversity tests updated; added variant-mismatch, brand+title-high, and multi-listing-per-domain tests).

### Slice 4: Full verify
**Status:** DONE
**Verify:** `python -m pytest tests -q` → 1151 passed, 1 unrelated pre-existing flake (`test_crawl_fetch_runtime.py::test_fetch_page_uses_remaining_timeout_budget_across_http_and_browser_retries`, a timeout-budget timing test that passes in isolation; does not touch product intelligence). Belk + config regression suites green.

### Slice 4: Full verify
**Status:** TODO
**What:** Run the full backend suite and the relevant smoke step.
**Verify:**
```powershell
cd backend
$env:PYTHONPATH='.'
.\.venv\Scripts\python.exe -m pytest tests -q
```
Run `run_extraction_smoke.py` if Slice 1 changed shared extraction behavior.

## Doc Updates Required

- [ ] `docs/CODEBASE_MAP.md` — only if a new file is added (not expected; all changes extend existing owners).
- [ ] `docs/INVARIANTS.md` — only if the public barcode/identity contract changes (e.g., barcode length set widened). Document the reason if so.
- [ ] `docs/backend-architecture.md` — note UPC-first discovery identity if discovery behavior is described there.

## Notes

- Confirmed during planning:
  - Belk adapter already searches `BELK_PRODUCT_BARCODE_KEYS` (`sku_upc`, `upc`, `barcode`, `gtin*`, `ean`) incl. nested search, and writes both `sku_upc` and `barcode`.
  - PI source snapshot maps `barcode/sku_upc/upc/ean → gtin` via `SOURCE_GTIN_FIELDS`; queries already lead with a standalone quoted GTIN; matching already weights `gtin_match` highest (0.22) with score floors. So Slice 2 is a small identifier-preference change, not a rewrite.
- **Slice 1 root cause confirmed by live probe (2026-05-30)** against `artifacts/runs/2/pages/06c189b10504749e.html` (Toastmaster Egg Cooker, UPC `0655772019097`):
  - UPC sits in `utag_data` (Tealium) inside `__next_f`; all values are single-element lists.
  - Adapter rejects the object because `coerce_field_value` does not unwrap the lists, so it returns 0 product records and only sees shop-by-brand tiles; generic extraction then yields URL-slug `sku` and no UPC.
  - Earlier hypotheses (barcode-length gate, `ROUTE_BARCODE_TO_SKU`, missing key) are ruled out. Fix = unwrap single-element lists + recognize the analytics object as a product, scoped to the adapter.
- Scope confirmed by user: BELK_BRAND only; no external APIs; SerpAPI dispatch left as-is; image/pHash deferred; no new output schema.

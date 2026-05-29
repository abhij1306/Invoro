# Plan: Extraction Wrong-Data Fixes (94URLs Audit)

**Created:** 2026-05-28
**Agent:** Claude Opus 4.7
**Status:** IN PROGRESS
**Touches buckets:** extraction, shared/coerce, structured_payloads, image dedupe, brand normalization, materials selector

## Goal

Fix the wrong-data bugs surfaced by the 94URLS audit (`agent_debug/94URLS.json` +
`agent_debug/issues.md`). Scope is constrained to **wrong values**, not missing
values. Each slice has a confirmed root cause derived from the stored HTML
artifact under `backend/artifacts/runs/1/pages/` plus current code paths. Items
without artifacts (acquisition issues, blocked pages) and items judged invalid
(legitimate site behavior) are explicitly listed in **Do Not Touch / Reject**.

Done means: each enumerated wrong-value pattern no longer appears for the
recorded artifact, regression tests cover the scenario, and full backend unit
suite stays green.

## Acceptance Criteria

- [x] Slice 1 — URL-suffix-as-color hydration drops SKU/handle/`html` codes (already shipped in DEC-0001)
- [ ] Slice 2 — Brand value with marketing tagline strips trailing tagline ("Gymshark | We Do Gym" → "Gymshark")
- [ ] Slice 3 — JSON-LD opaque color codes (e.g. Patagonia `["SMDB","FGE",...]`) no longer leak into `color`
- [ ] Slice 4 — `og:title` trailing capitalised code (e.g. "- DIME2SP2542BLK") never becomes `color`
- [ ] Slice 5 — Shopify `no-image-*` placeholder URLs are rejected from `image_url`/`additional_images`
- [ ] Slice 6 — `additional_images` rejects URLs that lack an image extension and look like PDP/page URLs
- [ ] Slice 7 — DOM features rows preserve sentence/spec boundaries (no `noiseAvoid`, no `4320.590.4GT/s`)
- [ ] Slice 8 — `materials` does not absorb editorial/glossary text blocks
- [ ] `python -m pytest tests/unit -q` exits 0
- [ ] Decisions ledger updated for each fixed slice (`agent_debug/agent_debug.py decide …`)

## Do Not Touch / Reject

Out of scope for this plan, with reason:

- **Item 19 Macys Tommy Hilfiger** — artifact missing, audit suggests acquisition
  served wrong page. Acquisition concern, not extraction.
- **Item 28 Vans `B4 / W5.5`** — INVALID. HTML literally encodes
  `"B4 / W5.5","4.0 Boys = 5.5 Women"`. `B`=Boys is correct upstream data.
- **Item 30 Pura Vida `color="Bracelet"`** — artifact missing for
  `e13693dc0487b3b9.html`. Cannot confirm root cause without source HTML.
- **Item 33 Nike `/c_limit`** — record's `additional_images` are clean Nordstrom
  URLs in current artifact; the `/c_limit` snippet is not reproducible against
  this snapshot.
- **Item 34 Adidas EU sizes 20/21** — sizes injected via JS not present in
  static HTML; needs a rendered DOM snapshot to lock the source.
- **Item 40 Princess Polly variant images** and **Item 46 COS Cotton Utility** —
  records absent from `94URLS.json`; nothing to verify.
- **Item 22 Patagonia color/SKU mismatch (`SMDB` vs `84213-AQT`)** — mismatch
  is **a symptom** of Slice 3 (opaque-code color leak); fixing Slice 3 also
  drops the wrong color. Do not separately reconcile color↔sku pairing.
- **Pricing speculation (Items 17, 20, 53)** — Gemini's price-vs-price
  comparisons require source verification per item; not extraction logic bugs.

## Slices

### Slice 1: Reject non-color URL suffix in shared variant color inference
**Status:** DONE (DEC-0001, shipped before plan creation)
**Files:** `backend/app/services/extract/variant_normalization/hydration.py`,
`backend/tests/unit/test_normalizers.py`
**What:** `_record_url_suffix_after_title` now requires at least one
`VARIANT_COLOR_HINT_WORDS` token after `clean_color_tokens` filtering.
Eliminates Phase Eight `"10015500806 Html"` and Pavlova `"Cl28517"` paths.
**Verify:** `pytest tests/unit/test_normalizers.py -q` (passed 55/55)

### Slice 2: Strip marketing tagline from brand
**Status:** TODO
**Files:**
- `backend/app/services/shared/field_coerce_text.py` (extend `coerce_brand_text`)
- `backend/tests/unit/test_field_value_core.py` or
  `backend/tests/unit/test_shared_text_coerce.py` (new regression test)

**Confirmed root cause (Item 38 Gymshark):**
JSON-LD literally has `{"@type":"Brand","name":"Gymshark | We Do Gym"}`.
`og:site_name` is the clean form `"Gymshark"`. Existing
`_BRAND_REGION_SUFFIX_RE` only strips region/storefront tokens, not arbitrary
taglines.

**What:**
After the existing region-suffix strip, if the brand text still contains a
separator (`|`, ` - `, `–`, `—`) and the prefix:
- is 1–3 word tokens,
- is composed of letters/digits only (no URL/email shape),
- the suffix on the other side has 2+ word tokens (i.e. clearly a tagline),

then return only the prefix. Be conservative: keep the original when the prefix
is empty or fails the shape check. Do not split on every `-` (many real brands
use hyphens — e.g. "Nine West", "Tommy Hilfiger" with no separator at all,
"Mr. Porter" etc.).

**Verify:**
- New test asserts `coerce_brand_text("Gymshark | We Do Gym") == "Gymshark"`.
- Existing tests for `coerce_brand_text` and brand region-suffix still pass.
- `pytest tests/unit -q` exits 0.

### Slice 3: Reject opaque color codes from JSON-LD `color`
**Status:** TODO
**Files:**
- `backend/app/services/extract/field_candidates/structured_payloads.py`
  (only the `color` add_candidate call) OR
  `backend/app/services/shared/field_coerce.py::_sanitize_option_scalar`
  (extend the existing color sanitizer)
- new unit test in `backend/tests/unit/test_field_value_core.py`

**Confirmed root cause (Item 22 Patagonia):**
Patagonia structured payload exposes
`"color":["SMDB","FGE","OLGG","BLK","AQT",...]` — internal swatch codes, not
human-readable colors. `coerce_field_value("color", list)` iterates list items;
the first element ("SMDB") survives as a candidate, gets selected, and lands as
the canonical color. Human-readable values like `"Bobcat Brown"` exist
elsewhere on the page but are not produced by this candidate.

**What:**
Treat a color value as garbage when ALL of the following hold:
- length ≤ 5 AND made entirely of A-Z (no spaces, no separators)
- not in any allow-list of known short colors (e.g. `RED`, `BLK` is borderline
  but commonly internal — keep it rejected; users see "Black", not "BLK")
- has no vowels OR is purely consonants (`SMDB`, `BCBN`, `OLGG` — vowel-less
  shorthand is the strongest tell)

Apply at `_sanitize_option_scalar` for `color` so it covers all upstream tiers
(JSON-LD, JS state, DOM). Return `None` for these — let downstream candidate
scoring pick a better source if any.

Validate against artifact:
- Patagonia stored color today: `"SMDB"` → with fix: candidate dropped, leaving
  no color from this tier (acceptable per "missing > wrong" rule).
- Other vowel-less short codes in the wild (`FGE`, `BCBN`, `BLSG`) also dropped.
- Real short colors that should pass: `Tan`, `Red`, `Blue` (have vowels), `Khaki`
  (>5 chars), `Navy` (vowels). Confirm `BLK` is dropped — that is correct,
  product pages render "Black", not "BLK".

**Verify:**
- New test: `_sanitize_option_scalar("color", "SMDB")` → `None`,
  `_sanitize_option_scalar("color", "Bobcat Brown")` → `"Bobcat Brown"`,
  `_sanitize_option_scalar("color", "Tan")` → `"Tan"`,
  `_sanitize_option_scalar("color", "Red")` → `"Red"`.
- Re-run audit on Patagonia record: `color` field becomes empty (was `SMDB`).

### Slice 4: Drop `og:title` trailing all-caps code from color extraction
**Status:** TODO
**Files:** TBD — needs investigation step before code changes.

**Confirmed root cause (Item 3 Dime):**
JSON-LD has no `color`. Stored color `"Dime2sp2542blk"` is a `str.title()` of
`og:title` trailing chunk `DIME2SP2542BLK` (after the ` - ` separator in
`Dime Soft Rock Crewneck - DIME2SP2542BLK`).

**Investigation step:**
Run a focused trace at the start of this slice to find the exact extractor
call that emits a candidate of `"Dime2sp2542blk"` for color:
1. Add a temporary log in `_sanitize_option_scalar` for `color` printing
   the inbound `value`.
2. Re-run extraction against the Dime artifact via a small driver script.
3. Identify which candidate source name produced `"Dime2sp2542blk"`.
4. Fix at that source. Likely candidates:
   - `og:title` selector with an aggressive split being read into color.
   - LLM backfill on color (would only happen with `llm_enabled=true`).

Do not write the actual fix until the source is identified.

**What (after investigation):**
Tighten the offending source: a color value that contains the SKU as a
case-folded substring (e.g. `record.sku.lower()` ⊆ `value.lower()`) is rejected
as a self-reference. This is a strong signal: a "color" containing the full
SKU is never a real color.

**Verify:**
- New test forces a color candidate equal to a SKU title-cased — expect rejection.
- Re-run focused extraction on Dime artifact: top-level `color` is no longer
  `"Dime2sp2542blk"`.

### Slice 5: Reject Shopify `no-image-*` placeholder from image fields
**Status:** TODO
**Files:**
- `backend/app/services/config/extraction_rules/_variants.py`
  (extend `PLACEHOLDER_IMAGE_URL_PATTERNS`)
- new unit test under `backend/tests/unit/test_shared_url_utils.py`

**Confirmed root cause (Item 49 Glossier):**
JSON-LD has
`"image":"https://www.glossier.com/cdn/shopifycloud/storefront/assets/no-image-2048-a2addb12_348x.gif"`.
`og:image` has the real product image. The image candidate from JSON-LD wins
because it's not in `PLACEHOLDER_IMAGE_URL_PATTERNS`.

Current `PLACEHOLDER_IMAGE_URL_PATTERNS` does not include the Shopify
`/storefront/assets/no-image-` token. `_is_placeholder_image_url` matches
substrings; adding `"/storefront/assets/no-image-"` (and the simpler
`"shopifycloud/storefront/assets/no-image"`) catches every variant.

**What:**
Add Shopify no-image placeholder substrings to
`PLACEHOLDER_IMAGE_URL_PATTERNS`. Add to **both**
`config/extraction_rules/_variants.py` (used by url_utils) and confirm
`detail_extraction_constants.PLACEHOLDER_IMAGE_URL_PATTERNS_LOWER` reflects
it via the existing import chain.

Conservative — do not match generic `"no-image"` outside the Shopify
storefront-assets path.

**Verify:**
- New test: `_is_placeholder_image_url(url)` returns True for the Glossier
  no-image URL.
- Existing placeholder tests still pass.
- Manual check: Glossier record after re-extraction would prefer `og:image`.

### Slice 6: Filter PDP/page URLs from `additional_images`
**Status:** TODO
**Files:**
- `backend/app/services/extract/detail/images/cleanup.py` (likely owner) OR
  `backend/app/services/shared/field_coerce_url.py`
- new test in `backend/tests/unit/test_field_value_core.py` or image-specific test module

**Confirmed root cause (Item 13 Walmart):**
`additional_images` for Walmart AirPods record contains 5 entries shaped like:
```
https://www.walmart.com/ip/Apple-AirPods-with-Charging-Case-2nd-Generation/D88D543AD9E843C0A93F1A4DFE93BDF2
```
These are PDP URLs, not images — no image extension, no `i5.walmartimages.com`
host. Plus one off-product image
(`MEE-audio-M6-PRO`) which is a separate cleanup.

**What:**
Reject URLs added to `additional_images` (and `image_url`) when:
- URL has no image MIME extension (`.jpg`, `.jpeg`, `.png`, `.webp`, `.gif`,
  `.avif`, `.svg`) AND
- URL path matches a known PDP/page pattern (`/ip/`, `/product/`, `/products/`,
  `/p/`, `/dp/`, `/shop/`).

This is the inverse of the existing image-fields permissive coercion. Add a
narrow guard in image-specific cleanup (NOT in url coerce, since some non-image
fields legitimately accept PDP URLs).

**Verify:**
- New test: image cleanup drops `https://www.walmart.com/ip/.../HEX`, keeps
  `https://i5.walmartimages.com/asr/...jpeg`.
- Re-run extraction against Walmart artifact; `additional_images` no longer
  contains 5 PDP entries.

### Slice 7: Preserve sentence/spec boundaries in DOM-extracted features
**Status:** REJECTED — upstream data quality, not extraction bug
**Files:** none

**Confirmed root cause (Item 12 EVGA):**
The merged text exists literally in the Amazon source HTML for the EVGA RTX
3090 PDP:

- ``Digital Max Resolution:7680 x 4320.590.4GT/s Texture Fill Rate`` is a
  single ``<span class="a-list-item">`` text node.
- ``...quieter acoustic noiseAvoid using unofficial software`` has no space
  between the two adjacent sentences in the source HTML.

This is upstream Amazon data quality, not a DOM extraction concatenation bug.
The extractor faithfully reflects the page text. Heuristic word-boundary
re-injection (``[a-z][A-Z]`` split, decimal-period split) would risk
breaking legitimate technical text like ``GeForce RTX`` (camelCase) or
``2.4GHz`` (digit-letter).

Per AGENTS Rule 8 (LLM is opt-in backfill, not primary). A deterministic fix
is not safely possible. Skipping this slice.

### Slice 8: Tighten `materials` selector to avoid editorial/glossary blocks
**Status:** TODO
**Files:**
- `backend/app/services/extract/detail/text/sanitizer.py` (likely path that
  routes accordion blocks into `materials`)
- `backend/app/services/config/selectors.py` if a selector list owns this

**Confirmed root cause (Item 48 Todd Snyder):**
`materials` is a 2480-char string starting
`"The word "seersucker" originates from the Persian words…"`. The actual
fabric `"97% Cotton, 3% Elastane"` is buried at the end of the same DOM
accordion (`<div class="description bottom"> <div class="metafield-rich_text_field">…`).

The full editorial copy is being captured as `materials`. The right fabric
data exists at the end of the same block.

**What:**
Two-layer fix:
1. Reject any `materials` candidate text that is `>500 chars` AND lacks any
   percent-composition pattern (`\d{1,3}%\s*[A-Za-z]+`) in the **first 200
   chars**. Editorial copy never starts with composition; real composition
   leads with it.
2. When the candidate text contains a composition pattern but it sits at the
   end of a long editorial block, prefer the trailing composition slice as the
   `materials` value.

This is a generic guard, not site-specific. Per AGENTS Rule 6, no Todd-Snyder
adapter.

**Verify:**
- New test: a 2000-char string starting with editorial then ending with
  `"…97% Cotton, 3% Elastane"` reduces to `"97% Cotton, 3% Elastane"`.
- A normal `"100% Wool"` materials value passes through.
- Re-run extraction on Todd Snyder artifact; `materials` shows fabric
  composition only.

## Doc Updates Required

- [ ] `docs/INVARIANTS.md` — Rule 3: add note that wrong-data is worse than
  missing-data; opaque codes (vowel-less ≤5 char strings) are rejected for
  `color` field.
- [ ] None expected for CODEBASE_MAP, ENGINEERING_STRATEGY (no new files,
  no architectural changes).

## Notes

### Findings locked from artifacts (date 2026-05-28)

| Item | Wrong-value pattern | Source confirmed in artifact | Slice |
|------|---------------------|------------------------------|-------|
| 47 Phase Eight | variant.color = "10015500806 Html" | hydration._record_url_suffix_after_title | 1 ✅ |
| 32 Pavlova | color = "Cl28517s" | same path (no longer reachable) | 1 ✅ |
| 38 Gymshark | brand = "Gymshark | We Do Gym" | JSON-LD Brand.name literal | 2 |
| 22 Patagonia | color = "SMDB" | JSON-LD color array of swatch codes | 3 |
| 3 Dime | color = "Dime2sp2542blk" | unknown — need source trace | 4 (investigate first) |
| 49 Glossier | image_url = no-image placeholder | JSON-LD image = Shopify no-image GIF | 5 |
| 13 Walmart | additional_images contains PDP URLs | URL pattern (non-image extension) | 6 |
| 12 EVGA | features merged across nodes | DOM get_text without separator | 7 (investigate first) |
| 48 Todd Snyder | materials is editorial dump | DOM selector pulls accordion editorial block | 8 |

Slices 4 and 7 begin with a focused investigation step before code changes.
Both have a confirmed wrong-value pattern in the artifact but the exact
extractor responsible is unverified. Per AGENTS.md, do not patch downstream;
trace the source first.

### Order rationale

Run slices in priority of confidence + blast radius:
1. (done) Slice 1 — already shipped
2. Slice 5 — config-only, narrow
3. Slice 2 — narrow text helper change, narrow tests
4. Slice 3 — affects all sites with opaque color codes (Patagonia + similar)
5. Slice 6 — image cleanup
6. Slice 8 — materials guard
7. Slice 4 — needs investigation; could be deferred if scope creeps
8. Slice 7 — needs investigation; could be deferred if scope creeps

### Decisions ledger

After each slice fix lands, record via:

```
python .\agent_debug\agent_debug.py decide --source "94URLS audit slice N" --status fixed --note "<summary>" --files "<files>" --verify-cmd "<cmd>" --result "<result>"
```

# Plan: Product Discovery Identity-Anchor Rework (Deterministic, No LLM)

**Created:** 2026-05-30
**Agent:** Claude
**Status:** DONE (implemented + live-verified on the real Nike Promina product + full backend suite passed)
**Touches buckets:** Bucket 2 (product_intelligence discovery + matching + service), config (`config/product_intelligence.py`), schemas only if a new identity field is surfaced. Bucket 4 (Belk adapter) only to confirm the manufacturer style token is preserved on `ecommerce_detail`.

---

## TL;DR of the Audit

Discovery (the SerpAPI search) is **not** the bottleneck. On the exact product the user linked
(`belk.com/p/nike-mens-promina-sneakers/3900462FV5285.html`) the live search returns **119 unique real
candidates** across nike.com, dsw, dickssportinggoods, finishline, jdsports, goat, ebay, lyst, als, etc. —
all genuinely the Nike Promina shoe.

**The bottleneck is matching/scoring.** Current scoring rates 112 of 119 true matches as `low` and only 1 as
`high`. The single strongest cross-retailer identity signal that is sitting right there in the data — the
**manufacturer style number `FV5285`, embedded inside Belk's SKU `3900462FV5285`** — is explicitly thrown
away by the previous plan, which wrongly concluded "Belk SKU/style is meaningless to external retailers."
It is not meaningless: it is Nike's universal product number and appears verbatim in 18% of candidate titles
(`FV5285-002`, `FV5285-101`, ...) and is the colorway-root for the rest.

A deterministic identity-anchor rescoring (style-code exact + distinctive model token + brand), with **no
LLM and no new APIs**, lifts the same 119 candidates from `{high:1, medium:7, low:112}` to
`{high:22, medium:95, low:1}` — **109 true matches rescued** into the reviewable band.

**pHash (imagehash.md): NO-GO.** Evidence below. The cheaper text-identity signal already separates true
from false cleanly, and image hashing would actively reject same-model colorway matches.

---

## Evidence (all from live SerpAPI + real DB, 2026-05-30)

### The linked product (DB job_id=4, source_product id=12)
- `brand='Nike®'` → normalized `nike`, `gtin='0197600670150'`, `sku='3900462FV5285'`, `price=$49`,
  `title='Men's Promina Sneakers'`, image = belk scene7 layered composite.
- **Brand IS extracted here.** The "brand completely missing" symptom is real but it is the *general* case
  (see Finding D), not this product.

### What the current pipeline persisted for this product (max_candidates was set to 5)
| score | label | domain | note |
|------|-------|--------|------|
| 0.621 | medium | nike.com | true |
| 0.425 | low | dsw.com | true |
| 0.425 | low | lyst.com | true (size 10) |
| 0.425 | low | lyst.com | true (size 13) — **near-dupe** |
| 0.425 | low | lyst.com | true (size 11.5) — **near-dupe** |

dsw, dickssportinggoods, finishline, jdsports, goat, ebay all matched in search but were **cut by the cap or
buried by weak ranking**, and the 5 that survived are mostly the same lyst listing at 3 sizes.

### Live recall on the same product (all built queries, deduped)
- **119 unique candidates.**
- contain the model token `promina`: **116/119 (97%)**
- contain the exact manufacturer style code `fv5285`: **22/119 (18%)**
- have a usable image/thumbnail in the payload: **119/119 (100%)**
- candidate brand inferred as `nike`: **119/119 (100%)** (because Nike is in the registry)

### Current vs proposed scoring on those 119 (projection)
| band | CURRENT | PROPOSED (identity-anchor) |
|------|---------|----------------------------|
| high (≥0.85) | 1 | 22 |
| medium (≥0.60) | 7 | 95 |
| low (≥0.40) | 112 | 1 |
| uncertain | 0 | 2 |

**109** candidates that score `<0.60` today move to `≥medium` under the proposed anchor scoring.

---

## Root-Cause Findings

### Finding A — The manufacturer style number is the missing identity key, and it was deliberately discarded
Belk's SKU is a **composite**: `3900462` (Belk internal prefix) + `FV5285` (Nike's style number).
Nike, DSW, Dick's, eBay, GOAT all key the product by `FV5285` (+ a colorway suffix like `-002`).
The previous recall plan (Slice 3) removed all SKU/style scoring with the rationale that Belk identifiers are
"internal ... with no relevance to external retailers." **That rationale is false for branded manufacturer
goods.** The fix is to extract the manufacturer style core out of the composite SKU and treat an exact match
of it as a near-certain (GTIN-class) identity signal.

### Finding B — Title similarity is the dominant weight but is structurally unfair here
`title_similarity` carries weight 0.45. Source title is terse and brand-stripped ("Men's Promina Sneakers");
candidate titles are verbose ("Nike Promina Men's Walking Shoes (Extra Wide) Black/White Size 11").
Token overlap lands at 0.30–0.34 for true matches, so the additive score collapses to `low`. Title-sim is a
fine *refinement* signal but a poor *primary* signal for cross-retailer matching. The distinctive **model
token** ("promina") — present in 97% of true matches — is the durable signal title-sim is failing to capture.

### Finding C — Recall caps + weak ranking + no URL-level dedupe waste the good candidates
- `_rank_discovered_candidates` ranks on `_identity_token_match` (effectively GTIN, which search payloads
  never carry), shopping-group flag, then title overlap. With no GTIN and low title overlap, ranking is
  near-random among true matches, so the per-product cap keeps an arbitrary subset (3 lyst sizes) and drops
  the diverse retailers (dsw/dicks/finishline/goat).
- Same product at different sizes/colors arrives as separate URLs differing only by query params
  (`?size=13`, `?activeColor=002`). There is no canonical-URL dedupe, so near-dupes consume cap slots.

### Finding D — Brand recognition is allowlist-bound, so it collapses for any unmapped brand
`normalize_brand` + `_infer_known_brand` only resolve a brand if it is in `BRAND_DOMAIN_MAP`,
`BRAND_ALIAS_MAP`, or the Belk registry files (~30 mapped brands + registry). For Nike this works (brand
present, 100% candidate inference). For any product whose brand is **not** pre-listed:
- source brand may extract from the PDP, but candidate brand inference returns `""`,
- `brand_match` is then always `False`,
- no brand-scoped DTC query is built,
- score collapses regardless of how obviously the candidate states the brand.

This is the architectural reason "brand is completely missing" shows up. Brand should be **evidence-based**
(trust the SerpAPI `source`/title/immersive `brand` field), with the registry used to *canonicalize*, not to
*gate*.

### Finding E — pHash / imagehash.md: NO-GO (decision, with evidence)
- **Image availability is not the blocker** — 100% of candidates carry a thumbnail. So the spike's "do
  candidates even have a usable image" question answers favorably, but that is the only point in pHash's favor.
- **Colorway breaks it.** "Find this product on other sites" returns the same model in many colorways
  (Black/White, Clay Green, Dusty Cactus, Comet Blue...). These are *true model-level matches* but have
  *different images*. pHash Hamming distance would be large → it would **reject true matches**. Image
  similarity is the wrong tool for model-level recall.
- **Source image is a layered scene7 composite** (`belk.scene7.com/...?layer=0&src=..._A_101&`), rendered
  very differently from nike.com studio shots → inflated Hamming distance even for the identical colorway.
- **Cost/latency** is real: 100+ extra image fetches per source product, each a network round-trip, plus
  decode — for a signal the deterministic style-code/model-token already beats.
- **Verdict:** the cheaper, deterministic text-identity tier (Finding A/B) rescues exactly the matches pHash
  was hypothesized to rescue, without pHash's colorway false-negatives. Do not implement pHash. Close the
  Tier-4 image-hash investigation as NO-GO and remove it from the queue.

### LLM assessment (per user's "only if low cost + substantial improvement")
Not needed and not justified. The deterministic anchor rework alone moves recall from 1→22 auto-accept and
8→117 reviewable on the linked product. LLM would add per-candidate token cost for a problem solved
deterministically. Keep LLM opt-in/disabled (INVARIANTS Rule 10). If ever revisited, the only defensible
LLM use is *brand inference for unmapped brands* (Finding D) — but Finding D's evidence-based brand fix is
deterministic and should be tried first. No LLM in this plan.

---

## Target Architecture (the "ignore current code" answer)

Given a Belk PDP, find the same product on brand + marketplace sites using a deterministic identity ladder:

1. **Identity extraction (from the PDP record).** Pull the strongest cross-retailer identifiers in priority
   order: `gtin/upc` → **manufacturer style/model number** (decomposed from the composite SKU) → `brand` →
   distinctive **model name** token → color → size. The manufacturer style number is the primary discovery
   *and* match key; everything else refines.
2. **Query construction (mostly already correct).** Lead with the quoted GTIN (Google indexes GTIN), then
   brand+model+style, then brand-site, then brand+title. Keep SerpAPI dispatch untouched (user-verified).
3. **Candidate harvest (already strong).** SerpAPI shopping + immersive expansion. Keep as-is.
4. **Canonicalize + dedupe candidates.** Strip volatile size/color/tracking query params to a canonical
   product URL before dedupe so the same listing at N sizes counts once.
5. **Identity-anchored scoring (the core change).** Tiered, deterministic:
   - GTIN exact → ~0.95 (already)
   - **manufacturer style-code exact** → ~0.92 (NEW — same model, near-certain)
   - brand-exact + distinctive model token → ~0.82 (NEW — model-level match)
   - brand-exact + strong title-sim → 0.85/0.88 (keep)
   - brand-exact + medium title-sim → 0.65 (keep)
   - title-sim only → refinement, never auto-accept
   Keep the variant-spec mismatch guard for genuine spec conflicts (capacity/“N-in-1”). Footwear colorway/size
   is **not** a wrong-product mismatch; it is the same model and must stay matchable.
6. **Brand resolution by evidence, not allowlist.** Accept candidate brand from SerpAPI `source`/title/
   immersive `brand`; use the registry to canonicalize aliases, not to gate. Unmapped brands still match.
7. **Output semantics.** Return matches sorted by the identity ladder, bounded by the user's
   `max_candidates_per_product`. Expose `match_basis` (gtin | style_code | model+brand | title) so review is
   explainable.

This is generic (INVARIANTS Rule 13): style-code decomposition + model-token anchoring helps every branded
ecommerce target, not just Belk/Nike.

---

## Acceptance Criteria

- [x] Manufacturer style core is deterministically derived from a composite source SKU (e.g.
      `3900462FV5285` → `FV5285`) and is available to matching as an identity field, sourced upstream.
- [x] An exact manufacturer-style-code match scores in the auto-accept band, ranked just below GTIN.
- [x] brand-exact + distinctive model token scores in the high-medium band (model-level match).
- [x] Brand resolution is evidence-based: a candidate whose brand appears in its title/source/payload matches
      even when the brand is absent from `BRAND_DOMAIN_MAP`/registry.
- [x] Candidate URLs are canonicalized (size/color/tracking params stripped) before dedupe; the same listing
      at multiple sizes no longer consumes multiple cap slots.
- [x] On the linked Nike Promina product, a live discovery yields multiple distinct true-match domains at
      `≥medium`, with nike.com (DTC) and exact-style-code listings at `high`. (Live: 8 distinct ≥medium
      domains, 3 at high incl. nike.com; lyst near-dupes collapsed 3→1. Baseline was 1 high / 7 medium / 112
      low with 3 lyst sizes filling the cap.)
- [x] No regression on the earlier source sets (Polo Ralph Lauren, Tommy Hilfiger, KitchenAid, Cuisinart,
      USA Pan): existing scoring tests stay green; only the Wrangler test changed band (low→medium) because
      brand-exact + full model-token coverage is now a correct model-level match.
- [x] No LLM path added; SerpAPI dispatch unchanged.
- [x] `python -m pytest tests -q` exits 0 (1174 passed).
- [x] imagehash.md investigation closed as NO-GO; queue item removed; probe scripts/temp images absent.

## Do Not Touch

- `_search_serpapi`, `_search_serpapi_engine`, `_shopping_query`, `_brand_scoped_query`, immersive expansion —
  user-verified dispatch; recall comes from identity/scoring/dedupe, not dispatch rewrites.
- `google_native` session logic — out of scope.
- BELK_EXCLUSIVE routing, `unauthorized_flag`, alerts — out of scope.
- LLM paths — stay disabled.
- The per-field extraction candidate system (INVARIANTS Rule 3) — style-code derivation is a read-only parse
  of the already-extracted SKU, not a new extraction tier.

## Slices

### Slice 1: Derive the manufacturer style core (identity extraction)
**Status:** DONE
**Files:** `backend/app/services/product_intelligence/matching.py` (snapshot builders),
`backend/app/services/config/product_intelligence.py` (decomposition pattern + config), tests in
`backend/tests/component/test_product_intelligence.py`.
**What:** In `extract_product_snapshot` (source) and `extract_search_result_snapshot` (candidate), derive a
`style_code` from the SKU/title using a configured pattern that splits a trailing alnum manufacturer code from
a leading numeric retailer prefix (`\d*([A-Z]{2,}\d{3,})` style, plus the bare-numeric colorway split
`FV5285-002`). Store as a normalized identity token. Config owns the regex + min length (INVARIANTS Rule 1).
**Done (2026-05-30):** Added `manufacturer_style_code()` in `matching.py` driven by
`PRODUCT_STYLE_CODE_PATTERN`/`PRODUCT_STYLE_CODE_MIN_LENGTH`; both snapshot builders now emit `style_code`
(candidate also reads title/snippet). GTIN excluded from the code set.
**Verify:** `test_manufacturer_style_code_decomposes_composite_sku` — `3900462FV5285 → fv5285`,
`FV5285-002 → fv5285`, pure numeric prefix → empty, GTIN excluded. PASSED.

### Slice 2: Identity-anchored scoring
**Status:** DONE
**Files:** `matching.py` (`score_candidate`, `_style_code_match`, `_model_token_match`),
`config/product_intelligence.py` (floors/weights/basis labels), tests.
**What:** Add `style_code_match` (GTIN-class floor) and `model_token_match` (directional containment guard,
brand-anchored). Record `reasons["match_basis"]`. Title-sim stays additive refinement. Keep the variant-spec
guard; confirm colorway/size does not trip it.
**Done (2026-05-30):** Added `style_code_match` weight + `MATCH_SCORE_FLOOR_STYLE_CODE` (0.92, 0.85 w/o brand)
and `MATCH_SCORE_FLOOR_MODEL_BRAND` (0.82). Model-token match is directional
(`MATCH_MODEL_TOKEN_MIN_CONTAINMENT=0.6`) so a truncated generic candidate cannot self-promote. The
model-only-without-brand floor was deliberately NOT added (FP risk on generic titles). `match_basis` recorded.
**Verify:** `test_score_candidate_style_code_match_reaches_auto_accept`,
`test_score_candidate_model_token_brand_is_model_level_match`,
`test_score_candidate_same_brand_different_model_not_promoted`,
`test_score_candidate_truncated_candidate_does_not_self_promote`. PASSED.

### Slice 3: Evidence-based brand resolution
**Status:** DONE
**Files:** `matching.py` (`score_candidate` brand block), tests.
**What:** When the candidate brand is unresolved but the candidate's own text states the source brand, trust
that evidence; registry only canonicalizes (no gating). No brand fabricated without evidence (Rule 6).
**Done (2026-05-30):** Moved the `_candidate_mentions_source_brand` evidence fallback into `score_candidate`
so both the discovery and candidate-crawl scoring paths benefit; records
`reasons["brand_from_candidate_evidence"]`.
**Verify:** `test_score_candidate_brand_resolved_from_candidate_evidence` (unmapped brand matches via title
evidence). PASSED.

### Slice 4: Canonical-URL dedupe + ranking by identity ladder
**Status:** DONE
**Files:** `discovery.py` (`_candidate_dedupe_key`, `_collect_candidates`, `_rank_discovered_candidates`,
`_identity_token_match`, `_query_identifier_value`), `config/product_intelligence.py`
(`DISCOVERY_VOLATILE_QUERY_PARAMS`), tests.
**What:** Strip volatile size/color/tracking params to a canonical dedupe key; re-rank by the identity ladder
(style-code/model token before title overlap); make discovery identity matching + query construction use the
decomposed manufacturer core instead of the composite SKU.
**Done (2026-05-30):** `_candidate_dedupe_key` collapses size/color variants while preserving identity params.
`_identity_token_match` now adds the decomposed style code on both sides. `_query_identifier_value` prefers the
bare manufacturer core over the composite SKU. Ranking adds a model-token tier.
**Verify:** `test_candidate_dedupe_key_collapses_size_and_color_variants`,
`test_build_search_queries_uses_decomposed_style_core_not_composite_sku`. PASSED. Live: lyst collapsed 3→1.

### Slice 5: Live verification + full suite
**Status:** DONE
**Done (2026-05-30):**
- Live discovery on the real Nike Promina Belk product: nike.com (DTC) and eBay style-code listings at
  **0.92 high**, **8 distinct retailers at ≥medium** (nike, dsw, dicks, finishline-class, goat, flightclub,
  lyst, shoeshowmega, ebay), lyst near-dupes collapsed 3→1. Baseline was `{high:1, medium:7, low:112}` with 3
  lyst sizes eating the cap.
- Full backend suite: `pytest tests -q` → **1174 passed**, 0 failures (pre-existing async-transport warnings
  only). PI component suite 103 passed (8 new identity-anchor tests).
- All throwaway probes deleted.

## Doc Updates Required

- [x] `docs/INVARIANTS.md` — added Rule 16 (Product Intelligence Discovery Identity Ladder): GTIN >
      manufacturer style-code > model+brand > title; brand resolution is evidence-based; colorway/size is
      same-model not a variant mismatch; pHash NO-GO.
- [ ] `docs/backend-architecture.md` — note the identity-ladder discovery/matching if discovery is described.
      (Deferred: discovery internals not currently described there; no stale text to correct.)
- [x] `docs/plans/ACTIVE.md` — Tier-4 image-hash queue item removed (NO-GO); this plan slotted and marked DONE.
- [x] `docs/CODEBASE_MAP.md` — no new file added; no change required.

## Notes

- Audit performed with throwaway probes (now deleted) against live SerpAPI (key from `.env`) and the real DB
  (`crawlerai`), 2026-05-30. Numbers above are from those runs, not theory.
- One probe query hit a transient DNS failure on a single `google_shopping` call; the other queries covered
  the same candidate set, so totals are stable (119–120 unique).
- The previous recall plan's SKU/style removal (its Slice 3) is the specific regression this plan reverses —
  but corrected: it is the *manufacturer style core decomposed from the composite SKU* that matters, not the
  raw Belk SKU string.
- pHash decision is final NO-GO; recorded here so the spike is not re-opened.

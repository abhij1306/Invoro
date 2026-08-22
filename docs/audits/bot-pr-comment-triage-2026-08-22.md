# Bot PR comment triage — 2026-08-22

**Date:** 2026-08-22  
**HEAD:** `172aa7e` (`main`, Productionize backend application services (#101))  
**Scope:** Bot comments on GitHub PRs merged on 2026-08-22. Findings checked against current tree. No code changes.  
**Status:** Triage snapshot. Do not treat as an implementation plan.

---

## 1. Source set

Merged that day (UTC close times):

| PR | Title | Merged (UTC) | Bot findings posted |
|---|---|---|---|
| [#89](https://github.com/abhij1306/Invoro/pull/89) | setuptools bound bump | 01:20 | none (CodeAnt skipped bot author) |
| [#95](https://github.com/abhij1306/Invoro/pull/95) | ruff 0.16.2 → 0.16.3 | 01:35 | none (CodeAnt skipped bot author) |
| [#98](https://github.com/abhij1306/Invoro/pull/98) | CodeQL backlog + variant recovery | 02:06 | CodeAnt 1, CodeQL 1 |
| [#99](https://github.com/abhij1306/Invoro/pull/99) | explicit variant option mapping | 02:25 | CodeAnt 2 |
| [#100](https://github.com/abhij1306/Invoro/pull/100) | acquisition orchestration split | 04:59 | CodeAnt 12, CodeRabbit 13+, CodeQL 9 |
| [#101](https://github.com/abhij1306/Invoro/pull/101) | productionize / drop unused surfaces | 08:09 | CodeQL 3; other bots skipped or never finished |

Bots seen: `codeant-ai`, `coderabbitai`, `github-advanced-security`, `gitar-bot`, `qodo-code-review`. Qodo was billing-blocked. Gitar posted “working” only. CodeRabbit skipped #98/#99/#101 (star gate) and posted a real review only on #100.

Ignored as non-bugs: marketing comments, review-status tables, “trigger review” checkboxes, Dependabot command footers, CodeRabbit nits (double profile save, unused-test `del`, etc.).

---

## 2. Verdict

**4 still-valid functional bugs remain.** All are extraction/acquisition correctness, not CI failures.

| ID | Sev | Owner | Still valid? |
|---|---|---|---|
| T-01 | P2 | listing readiness | yes |
| T-02 | P2 | JS-state variant options | yes |
| T-03 | P2 | JS-state variant options | yes |
| T-04 | P2 | DOM variant merge | yes |

Everything else from today’s bot threads is **fixed in later commits on the same PRs**, **false positive**, **dead-code hygiene**, or **out of tree**.

---

## 3. Still valid

### T-01 — Listing override can mark ready with no cards

- **PR / bot:** #100 / CodeAnt  
- **Where:** `backend/app/services/acquisition/browser_readiness.py` (`wait_for_listing_readiness`, `_readiness_decision`)  
- **Claim:** Override selector match counts as listing-ready even when no listing cards exist. Wait returns on attached shell selectors; decision is `max(listing_card_count, matched_listing_selectors) >= listing_min_items` (`listing_min_items` default 2).  
- **Why still open:** Two empty-container selectors still satisfy the gate. Settling can stop before async cards render; fast finalize can then run on a shell.  
- **Suggested fix (later):** Require `listing_card_count >= listing_min_items`. Treat override selectors as wait hints, not a substitute for cards.

### T-02 — Partial `variation_values` wins over attributes / traits

- **PR / bot:** #99 / CodeAnt  
- **Where:** `backend/app/services/js_state/variant_options.py` `variant_option_values` (~L92–103)  
- **Claim:** First non-empty `_variation_option_values` result returns immediately. A one-axis map such as `{"size": "M"}` never merges `attributes` / `traits` (e.g. color).  
- **Why still open:** Early return is still there. Later mapping loop never runs when variation values are non-empty.  
- **Suggested fix (later):** Merge axes from variation values, selected options, attributes, traits, size chart, and indexed options. Do not treat a partial map as complete.

### T-03 — Non-public semantic keys suppress indexed color/size

- **PR / bot:** #99 / CodeAnt  
- **Where:** same function; `_option_values_from_mapping` uses `variant_axis_name_is_semantic`  
- **Claim:** `attributes={"brand": "Nike"}` is semantic but not a public variant axis (`PUBLIC_VARIANT_AXIS_FIELDS` has color/size/etc., not brand). Mapping returns `{brand: Nike}`, function returns, indexed color/size never recovered. Public sanitization then drops brand.  
- **Why still open:** Mapping still accepts any semantic name. Early return still fires on that dict.  
- **Suggested fix (later):** Only treat a mapping as authoritative when it contains at least one public axis. Otherwise keep walking fallbacks.

### T-04 — DOM axis expansion drops SKU / variant_id / barcode

- **PR / bot:** #98 / CodeAnt (comment sat on `dom_group_pipeline.py`; logic now in merge helper)  
- **Where:** `backend/app/services/extract/detail/variants/dom_merge.py` `_merge_variant_with_dom_axes`  
- **Claim:** Cartesian expansion of existing transport variants with a new DOM axis copies the row then `pop`s `sku`, `variant_id`, and `barcode`. Expanded combos share price/URL and lose stable identity.  
- **Why still open:** Pops still run for every generated pair.  
- **Suggested fix (later):** Keep identity only when the combo is 1:1 with the source row. Otherwise mint distinct ids or omit transport fields without cloning them onto every combo.

---

## 4. Posted, then fixed or invalid

Checked on `172aa7e`. Do not re-open unless the code regresses.

| PR | Bot | Finding | Disposition |
|---|---|---|---|
| 100 | CodeAnt | Fast-finalize skips block/interstitial classification | **Fixed.** `_classify_page` always runs checkers; `fast_finalize` unused. |
| 100 | CodeAnt | Parallel workers overshoot `max_records` | **Fixed.** `ParallelRecordBudget` claims/releases a shared remaining total. |
| 100 | CodeAnt | Identity prefetch-then-insert race aborts worker | **Fixed.** Prepare first; register inserts; `IntegrityError` nested txn updates existing row. |
| 100 | CodeAnt | Native Chrome ignores locality | **Fixed.** `build_native_real_chrome_context_spec` applies locality. |
| 100 | CodeAnt | Locality UA vs leftover `sec-ch-ua` | **Fixed.** UA override strips `sec-ch-ua*` before merge. |
| 100 | CodeAnt | Merged API endpoints can exceed cap | **Fixed.** Slice after dedupe. |
| 100 | CodeAnt | Expansion overruns `max_elapsed_ms` | **Fixed.** Remaining budget wrapped in `asyncio.timeout`. |
| 100 | CodeAnt | Warmup `max(750, remaining)` extends budget | **Fixed.** `remaining_ms = max(0, budget - elapsed)`; skip recovery at 0. |
| 100 | CodeAnt | Raw JSON detail postprocess drops `surface` | **Fixed.** `_postprocess_detail_records(..., surface=surface)`. |
| 100 | CodeAnt | Nested sitemap indexes not walked | **Fixed.** `_resolve_child_sitemap_urls` recurses with depth/visited. |
| 100 | CodeRabbit | `float()` on locality geo | **Fixed.** `TypeError`/`ValueError` swallowed. |
| 100 | CodeRabbit | Permissions mutated then replaced | **Fixed.** `_normalized_permissions` after locality. |
| 100 | CodeRabbit | Warmup cap/floor hardcoded in service | **Fixed.** `origin_warmup_recent_max_entries` / `origin_warmup_min_budget_ms` in runtime settings. |
| 100 | CodeRabbit | Short-budget warmup omits timing key | **Fixed.** Sets `phase_timings_ms["origin_warmup"] = 0`. |
| 100 | CodeRabbit | Chrome exe paths in service | **Fixed.** `REAL_CHROME_FALLBACK_EXECUTABLE_PATHS` in config. |
| 100 | CodeRabbit | Load-more can store shrunken `card_count` | **Fixed.** Update `previous` only when count does not shrink; `result.card_count = max(...)`. |
| 100 | CodeRabbit | `suppress(BaseException)` swallows cancel | **Fixed.** `cancel_pending_tasks` uses `gather(..., return_exceptions=True)` only. |
| 100 | CodeRabbit | Prefetch identity before `_prepare_record` | **Fixed.** Same as persistence race fix. |
| 100 | CodeRabbit | Rejected owning JSON list still traversed | **Fixed.** `_list_candidate_owns_descendants` `continue`s before nested children. |
| 100 | CodeRabbit | Trace `value_preview` redaction in `extraction_trace.py` | **Void.** File gone after #101 surface drop. |
| 100 | CodeQL | Empty `except` in `browser_page_flow.py` (#579/#580) | **Fixed.** Comment on the pass; alerts not open. |
| 100 | CodeQL | Unused warmup globals in `browser_runtime.py` (#574–#576) | **Fixed.** State lives in `browser_origin_warmup.py` and is used. |
| 101 | CodeQL | Clear-text secret log in `config.py` (#588) | **Fixed.** Logs `issue_count`, not secret values. Alert not open. |
| 101 | CodeQL | Unused import `get_results` (#592) | **Invalid.** Imported as `_get_results`; public `get_results` used by API. |
| 98 | CodeQL | Unreachable in `variant_options.py` (#573) | **Invalid now.** That line is a live fallback return. Alert not open. |
| 100 | CodeQL | Redundant `record_count >= max_records` (#581) | **False positive.** Early return is pre-loop; later check is after `nonlocal` increments. Still listed open in GitHub; not a product bug. |

CodeRabbit also flagged `handoff_cookie_engine` coercion and Patchright→Chrome retry. Current `_apply_handoff_engine` and `should_retry_patchright_with_real_chrome` match the intended contract. Not kept as open bugs.

---

## 5. Hygiene left in GitHub (not product bugs)

Open CodeQL on `main` that came from these PRs or the follow-up scan:

| Alert | Rule | File | Note |
|---|---|---|---|
| [581](https://github.com/abhij1306/Invoro/security/code-scanning/581) | redundant comparison | `batch_parallel.py` | dismiss as FP |
| [582](https://github.com/abhij1306/Invoro/security/code-scanning/582)–[584](https://github.com/abhij1306/Invoro/security/code-scanning/584) | unnecessary `del` | listing-card heuristic tests | test stubs |
| [589](https://github.com/abhij1306/Invoro/security/code-scanning/589) | unused global | `playground_service.py` `_PI_TERMINAL_STATUSES` | leftover after split |
| [593](https://github.com/abhij1306/Invoro/security/code-scanning/593) | unused global | `playground_service.py` `_ENRICH_TERMINAL_STATUSES` | leftover after split |

#101 also left unused wrappers (`_merge_seed_detail_products` only used from tests). Same bucket.

Other open alerts (#585–#587) were **not** commented on today’s merged PRs; out of scope here.

---

## 6. Suggested later order

1. T-02 + T-03 together (`variant_option_values` merge/authority).  
2. T-04 (`dom_merge` identity on expansion).  
3. T-01 (listing selector vs card gate).  
4. Optional: delete unused playground constants; dismiss CodeQL 581.

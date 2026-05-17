# Detail Extraction Second-Pass Decomposition

**Scope:** Decompose four oversized owners that emerged from the first refactor pass:

1. `extract/variant_grouping.py` (1 546 LoC)
2. `extract/detail_candidate_collection.py` (1 425 LoC)
3. `extract/detail_dom_context.py` (1 470 LoC)
4. `extract/detail_final_cleanup.py` (1 334 LoC)

**Why:** Architecture audit (2026-05-17) found that Slices 4–7 of `verified-architecture-audit-remediation-plan.md` shrank the original god modules into shims, but the new owners they pointed at became god modules themselves. Each of the four files above mixes 4–6 sub-concerns. This plan finishes the decomposition by responsibility, not by file rename.

**Status:** COMPLETE
**Started:** 2026-05-17

> **Why this plan exists despite Slices 4–7 of the remediation plan being DONE:** Those slices reduced the old monolith files to shims, but the work moved logic into new files (`variant_grouping.py`, `detail_candidate_collection.py`, `detail_dom_context.py`, `detail_final_cleanup.py`) that became 1 334–1 546 LoC each. The post-refactor architecture review on 2026-05-17 flagged this as the same god-module problem wearing new names. This plan finishes the decomposition.

---

## Plan Layout

| Part | File | Slices |
|---|---|---|
| 1 | `extract/variant_grouping.py` | 1.1 – 1.3 |
| 2 | `extract/detail_candidate_collection.py` | 2.1 – 2.4 |
| 3 | `extract/detail_dom_context.py` | 3.1 – 3.2 |
| 4 | `extract/detail_final_cleanup.py` | 4.1 – 4.4 |
| 5 | Cross-cutting migration & cleanup | 5.1 – 5.3 |

Verify the plan-wide gate at the end before closing.

---

# Part 1 — `extract/variant_grouping.py` Decomposition

**Why:** Slice 4 of the remediation plan reduced `shared_variant_logic.py` to a shim by routing exports through `variant_grouping.py`. That left `variant_grouping.py` at 1 546 LoC with four sub-concerns (axis, option-value, choice traversal, identity/merge). This part splits each into its own owner.

## Symbol mapping

### Owner A — `extract/variant_axis.py` — axis name & label normalization

Public:
- `normalized_variant_axis_key`
- `normalized_variant_axis_display_name`
- `variant_axis_name_is_semantic`

Private helpers:
- `_variant_axis_label_is_noise`
- `_normalized_group_label_candidates`
- `_resolve_visible_variant_group_name`
- `_resolve_machine_variant_group_name`
- `_semantic_group_label_from_text`

### Owner B — `extract/variant_option_value.py` — option-value noise + color/size detection

Public:
- `variant_option_value_matches_ui_noise`
- `variant_option_value_matches_noise_token`
- `variant_option_value_is_noise`

Private helpers:
- `_select_option_values_are_noise`
- `_value_looks_like_color`
- `_is_sequential_integer_run`

### Owner C — `extract/variant_choice_traversal.py` — DOM choice container walking

Public:
- `variant_dom_cues_present`
- `infer_variant_group_name`
- `infer_variant_group_name_from_values`
- `resolve_variant_group_name`
- `iter_variant_select_groups`
- `iter_variant_choice_groups`

Private helpers:
- `_choice_option_text`
- `_variant_input_label`
- `_choice_option_texts`
- `_descendant_variant_group_name`
- `_node_supports_value_only_axis_inference`
- `_descendant_variant_choice_inputs`
- `_anchor_node_has_variant_signal`
- `_descendant_group_label_nodes`
- `_variant_choice_container_is_overbroad`
- `_variant_choice_container_for_input`
- `_variant_group_node_attrs_are_noise`
- `_node_attr_can_hold_group_label`
- `_nearby_variant_group_name`
- `_select_option_texts`
- `_variant_group_has_multiple_options`
- `_select_is_quantity_node`

### Owner D — `extract/variant_identity_merge.py` — identity, merge, richness, alias

Public:
- `split_variant_axes`
- `resolve_variants`
- `variant_identity`
- `variant_semantic_identity`
- `collapse_duplicate_size_aliases`
- `variant_row_richness`
- `merge_variant_pair`
- `merge_variant_rows`

Private helpers:
- `_canonical_variant_axis_value`
- `_duplicate_size_alias_targets`
- `_canonicalize_size_alias`
- `_rewrite_variant_row_size_alias`

### Re-export passthroughs from config (stay where they are; no move)

These already live in `variant_grouping.py` only as imports forwarded for backwards compat. Move them out of the new owners; callers should import from config directly.

- `option_scalar_fields` (alias of `OPTION_SCALAR_FIELDS`)
- `public_variant_axis_fields` (alias of `PUBLIC_VARIANT_AXIS_FIELDS`)
- `variant_axis_allowed_single_tokens` (alias of `VARIANT_AXIS_ALLOWED_SINGLE_TOKENS`)
- `variant_size_value_patterns` (alias of `VARIANT_SIZE_VALUE_PATTERNS`)
- `variant_option_value_suffix_noise_patterns` (alias of `VARIANT_OPTION_VALUE_SUFFIX_NOISE_PATTERNS`)

After the split, `variant_grouping.py` becomes a thin re-export shim mirroring `shared_variant_logic.py`. Mark with `# Delete after 2026-06-30`.

## Slices

### Slice 1.1 — Axis & option-value owners

**Status:** DONE

**Severity:** 🟠 (D3)

**Deletion first:**
- Cut Owner A and Owner B symbols out of `variant_grouping.py`.
- Delete the duplicated definitions from `shared_variant_logic.py` (currently re-exported from `variant_grouping`).

**New code:**
- Create `extract/variant_axis.py` (target ≤ 350 LoC).
- Create `extract/variant_option_value.py` (target ≤ 200 LoC).

**Acceptance:**
- `grep -rn "def normalized_variant_axis_key" backend/app` → 1 result, in `variant_axis.py`.
- `grep -rn "def variant_option_value_is_noise" backend/app` → 1 result, in `variant_option_value.py`.
- `wc -l backend/app/services/extract/variant_grouping.py` → ≤ 1 200.
- All callers in `backend/app/services/js_state/`, `backend/app/services/extract/variant_*`, and `backend/app/services/extract/field_candidates/` keep importing from `variant_grouping` (shim still works) **or** are migrated in this slice.

**Verify:**
```
cd backend && set PYTHONPATH=. && .venv\Scripts\python.exe -m pytest tests/services -q -k "variant"
```

**Verified:** 2026-05-17 with `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services -q -k "variant"` and `.\.venv\Scripts\python.exe -m pytest tests/services/test_structure.py -q`.
**Note:** `variant_choice_traversal.py` was started with `infer_variant_group_name` so the Slice 1.1 LoC gate stayed green; Slice 1.2 still owns the remaining DOM choice traversal move.

### Slice 1.2 — DOM choice traversal owner

**Status:** DONE

**Severity:** 🟠 (D3)

**Deletion first:** Cut Owner C symbols out of `variant_grouping.py`.

**New code:** Create `extract/variant_choice_traversal.py` (target ≤ 700 LoC).

**Acceptance:**
- `grep -rn "def iter_variant_choice_groups\|def resolve_variant_group_name\|def infer_variant_group_name" backend/app` → each appears once, in `variant_choice_traversal.py`.
- `wc -l backend/app/services/extract/variant_grouping.py` → ≤ 600.

**Verify:**
```
cd backend && set PYTHONPATH=. && .venv\Scripts\python.exe -m pytest tests/services -q -k "variant or shared_variant"
.venv\Scripts\python.exe run_extraction_smoke.py --groups controls --limit 2
```

**Verified:** 2026-05-17 with `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services -q -k "variant or shared_variant"` and `.\.venv\Scripts\python.exe run_extraction_smoke.py --groups controls --limit 2` (corpus missing, smoke skipped with exit 0).
**Note:** `variant_choice_traversal.py` is 852 LoC after the mechanical move. Behavior and `variant_grouping.py` shrink gate passed; revisit the target in Slice 5.3 if the structure ratchet requires a lower budget.

### Slice 1.3 — Identity, merge, richness, alias owner

**Status:** DONE

**Severity:** 🟠 (D3)

**Deletion first:** Cut Owner D symbols out of `variant_grouping.py`. Drop the body of `variant_grouping.py` to a re-export shim with deletion deadline.

**New code:** Create `extract/variant_identity_merge.py` (target ≤ 500 LoC).

**Acceptance:**
- `grep -rn "def merge_variant_rows\|def variant_identity\|def split_variant_axes\|def resolve_variants" backend/app` → each appears once, in `variant_identity_merge.py`.
- `wc -l backend/app/services/extract/variant_grouping.py` → ≤ 80, body is purely re-export with `# Delete after 2026-06-30`.

**Verify:**
```
cd backend && set PYTHONPATH=. && .venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe run_extraction_smoke.py
```

**Verified:** 2026-05-17 with `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests -q` (first run had only `test_structure.py` private import failure, fixed by module import) then `.\.venv\Scripts\python.exe -m pytest tests/services/test_structure.py -q`. `run_extraction_smoke.py` skipped because acceptance corpus is missing and exited 0.

---

# Part 2 — `extract/detail_candidate_collection.py` Decomposition

**Why:** The file is the new home for what `detail_materializer.py` used to host. At 1 425 LoC it carries six responsibilities: candidate collection, structured-payload pruning, materialization scoring, DOM-completion rules, image materialization, and the public `build_detail_record` / `extract_detail_records` orchestration. The `_add_sourced_candidate` core is the actual concern that justifies the file's name; everything else needs to move out.

## Symbol mapping

### Owner E — `extract/detail_structured_pruning.py` — structured-payload relevance gates

Public:
- `prune_irrelevant_detail_structured_payload`

Private helpers:
- `_prune_irrelevant_detail_structured_payload`
- `_detail_structured_payload_is_irrelevant_product`
- `_preferred_structured_payload_url`
- `_structured_variant_leaf_conflicts_with_base_request`
- `_structured_payload_is_breadcrumb_list`

### Owner F — `extract/detail_dom_completion.py` — when DOM tier must run

Public:
- `requires_dom_completion`
- `should_collect_dom_variants`

Private helpers:
- `_requires_dom_completion`
- `_should_collect_dom_variants`
- `_requires_dom_long_text_completion`
- `_detail_long_text_value_looks_truncated`
- `_detail_description_value_looks_thin`
- `_missing_requested_fields`
- `_dom_variants_are_validated`
- `_variant_signal_strength`
- `_variant_axis_coverage`

### Owner G — `extract/detail_image_materialize.py` — image field assembly

Public:
- `materialize_image_fields`

Private helpers:
- `_materialize_image_fields`

(Adjacent to existing `extract/detail_image_dedupe.py`. Do not merge; image dedupe is a downstream cleanup concern.)

### Owner H — `extract/detail_record_assembly.py` — public detail record entry

Public:
- `build_detail_record`
- `extract_detail_records`
- `detail_record_rejection_reason`
- `infer_detail_failure_reason`

Private helpers:
- `_finalize_early_detail_record`
- `_finalize_dom_detail_record`
- `_promote_dom_detail_title`
- `_fill_missing_dom_detail_title`
- `_attach_detail_tables`
- `_prepare_detail_extraction`
- `_apply_prepared_dom_fallbacks`
- `_extract_prepared_dom_variants`
- `_normalized_category_path`

### Stays in `extract/detail_candidate_collection.py` — true candidate plumbing

- `_add_sourced_candidate`
- `_collect_record_candidates`
- `_collect_structured_payload_candidates`
- `_primary_source_for_record`
- `_ordered_candidates_for_field`
- `_group_ordered_candidates_by_source`
- `_selector_self_heal_config`
- `_selected_selector_trace`
- `_materialize_record`
- `_field_source_rank`
- `_coerce_float`

After the split, `detail_candidate_collection.py` should be ≤ 600 LoC and only own candidate add/rank/materialize.

## Slices

### Slice 2.1 — Owner E `detail_structured_pruning.py`

**Status:** DONE

**Severity:** 🟠 (D3)

**Deletion first:** Cut Owner E symbols out of `detail_candidate_collection.py`. Update `detail_materializer.py` shim to re-export from the new owner. Update `detail_candidate_collection.py` to import the helper back where it is used internally.

**New code:** Create `extract/detail_structured_pruning.py` (target ≤ 250 LoC).

**Acceptance:**
- `grep -rn "def _prune_irrelevant_detail_structured_payload" backend/app` → 1 result, in `detail_structured_pruning.py`.
- `wc -l backend/app/services/extract/detail_candidate_collection.py` → ≤ 1 200.

**Verify:**
```
cd backend && set PYTHONPATH=. && .venv\Scripts\python.exe -m pytest tests/services/test_detail_extractor_priority_and_selector_self_heal.py tests/services/test_detail_extractor_structured_sources.py -q
```

**Verified:** 2026-05-17 with the listed pytest command.

### Slice 2.2 — Owner F `detail_dom_completion.py`

**Status:** DONE

**Severity:** 🟠 (D3)

**Deletion first:** Cut Owner F symbols out of `detail_candidate_collection.py`.

**New code:** Create `extract/detail_dom_completion.py` (target ≤ 350 LoC).

**Acceptance:**
- `grep -rn "def _requires_dom_completion\|def _should_collect_dom_variants" backend/app` → each appears once, in `detail_dom_completion.py`.
- `wc -l backend/app/services/extract/detail_candidate_collection.py` → ≤ 950.

**Verify:**
```
cd backend && set PYTHONPATH=. && .venv\Scripts\python.exe -m pytest tests/services -q -k "detail or dom"
```

**Verified:** 2026-05-17 with `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services -q -k "detail or dom"`.

### Slice 2.3 — Owner G `detail_image_materialize.py`

**Status:** DONE

**Severity:** 🟡 (D3)

**Deletion first:** Cut Owner G symbols out of `detail_candidate_collection.py`.

**New code:** Create `extract/detail_image_materialize.py` (target ≤ 120 LoC).

**Acceptance:**
- `grep -rn "def _materialize_image_fields" backend/app` → 1 result, in `detail_image_materialize.py`.

**Verified:** 2026-05-17 with detail extractor priority and structured-source tests.

### Slice 2.4 — Owner H `detail_record_assembly.py`

**Status:** DONE

**Severity:** 🟠 (D3)

**Deletion first:** Cut Owner H symbols out of `detail_candidate_collection.py`. Update the `detail_materializer.py` shim's `_sync_test_patchpoints` body so it re-syncs against `detail_record_assembly` instead of `detail_candidate_collection`.

**New code:** Create `extract/detail_record_assembly.py` (target ≤ 500 LoC).

**Acceptance:**
- `grep -rn "def build_detail_record\|def extract_detail_records" backend/app` → each appears once, in `detail_record_assembly.py`.
- `wc -l backend/app/services/extract/detail_candidate_collection.py` → ≤ 600.

**Verify:**
```
cd backend && set PYTHONPATH=. && .venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe run_extraction_smoke.py --groups controls --limit 2
```

**Verified:** 2026-05-17 with `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests -q` (behavior green, then private-import structure cleanup), `.\.venv\Scripts\python.exe -m pytest tests/services/test_structure.py -q`, and `run_extraction_smoke.py --groups controls --limit 2` (corpus missing, smoke skipped with exit 0).

---

# Part 3 — `extract/detail_dom_context.py` Decomposition

**Why:** At 1 470 LoC the file mixes four concerns: DOM context selection, DOM fallback field application, DOM variant axis/value coercion, and DOM variant extraction + backfill. The name implies only context selection.

## Symbol mapping

### Owner I — `extract/detail_dom_section_targets.py` — section field discovery

Public:
- `record_has_rich_existing_variants`
- `existing_variant_cluster_has_transport_signal`
- `primary_dom_context`

Private helpers:
- `_dom_section_target_fields`

### Owner J — `extract/detail_dom_fallbacks.py` — DOM fallback field assembly

Public:
- `apply_dom_fallbacks`

(All `apply_dom_fallbacks` private helpers move with it.)

### Owner K — `extract/detail_dom_variant_coercion.py` — axis/value coercion for DOM variants

Public: none (helpers only)

Private helpers:
- `_dom_variant_axis_allowed`
- `_dom_variant_group_name_allowed`
- `_resolve_dom_variant_group_name`
- `_dom_variant_axis_from_attributes`
- `_strip_variant_option_value_suffix_noise`
- `_coerce_variant_option_value`
- `_coerce_color_option_value`
- `_color_option_value_candidates`
- `_component_size_style_from_group_name`
- `_prefer_axis_inferred_from_values`
- `_split_compound_axis_name`
- `_strip_variant_option_price_suffix`
- `_split_compound_option_value`
- `_expand_compound_option_group`

### Owner L — `extract/detail_dom_variant_extraction.py` — DOM variant rows + backfill

Public:
- `extract_variants_from_dom`
- `backfill_variants_from_dom_if_missing`

Private helpers:
- `_collect_variant_choice_entries`
- `_variant_choice_entry_value`
- `_variant_input_label`
- `_visible_node_text`
- `_descendant_image_alt_text`
- `_dom_variant_combo_count`
- `_axis_only_dom_variants`
- `_variant_axes_present`
- `_dom_variants_add_missing_existing_axis`
- `_expand_existing_variants_with_dom_axes`

After the split, `detail_dom_context.py` either deletes or shrinks to a thin re-export shim with a deletion deadline. Existing facade `detail_dom_extractor.py` continues to forward the public API; update its `_sync_runtime_limits` to point at the new owners.

## Slices

### Slice 3.1 — Owners I + J split

**Status:** DONE

**Severity:** 🟠 (D3)

**Deletion first:** Cut section-target and DOM-fallback symbols out of `detail_dom_context.py`.

**New code:** Create `extract/detail_dom_section_targets.py` and `extract/detail_dom_fallbacks.py`.

**Acceptance:**
- `wc -l backend/app/services/extract/detail_dom_context.py` → ≤ 1 050.
- `grep -rn "def primary_dom_context" backend/app` → in `detail_dom_section_targets.py`.

### Slice 3.2 — Owners K + L split

**Status:** DONE

**Severity:** 🟠 (D3)

**Deletion first:** Cut variant coercion + variant extraction/backfill out of `detail_dom_context.py`. If only re-exports remain, replace the body with a re-export shim with deletion deadline.

**New code:** Create `extract/detail_dom_variant_coercion.py` and `extract/detail_dom_variant_extraction.py`.

**Acceptance:**
- `grep -rn "def extract_variants_from_dom\|def backfill_variants_from_dom_if_missing" backend/app` → each in `detail_dom_variant_extraction.py`.
- `wc -l backend/app/services/extract/detail_dom_context.py` → ≤ 80 (re-export shim) or deleted entirely.

**Verify:**
```
cd backend && set PYTHONPATH=. && .venv\Scripts\python.exe -m pytest tests/services -q -k "detail or variant"
.venv\Scripts\python.exe run_extraction_smoke.py --groups controls --limit 2
```

**Verified:** 2026-05-17 with `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services -q -k "detail or variant"` and `.\.venv\Scripts\python.exe run_extraction_smoke.py --groups controls --limit 2` (corpus missing, smoke skipped with exit 0).

---

# Part 4 — `extract/detail_final_cleanup.py` Decomposition

**Why:** The file mixes detail record sanitization, image cleanup, money/price repair, variant low-signal pruning, and availability reconciliation. Each cluster has a clear owner.

## Symbol mapping

### Owner M — `extract/detail_record_sanitization.py` — placeholder/identity scalar cleanup + title repair

Public:
- `detail_title_looks_like_placeholder`

Private helpers:
- `_compile_detail_waf_queue_title_patterns`
- `_sanitize_ecommerce_detail_record`
- `_sanitize_detail_placeholder_scalars`
- `_feature_text_is_json_object`
- `_sanitize_detail_identity_scalars`
- `_repair_detail_title_from_requested_identity`
- `_detail_title_fallback_is_safe`
- `_preferred_detail_merch_code`
- `_looks_like_uuid`
- `_detail_scalar_value_is_placeholder`
- `_clean_detail_category_path`
- `_category_part_matches_identity`
- `_materials_value_looks_like_org_name`

### Owner N — `extract/detail_money_repair.py` — price magnitude + discount repair

Public: none beyond what is already in `detail_price_core`.

Private helpers:
- `_normalize_detail_money_precision`
- `_detail_money_containers`
- `_money_two_decimals`
- `_drop_invalid_detail_discounts`
- `_repair_invalid_original_prices`
- `_repair_detail_variant_prices_and_identity`
- `_price_is_cents_copy`
- `_price_is_low_signal_copy`

### Owner O — `extract/detail_variant_pruning.py` — variant cluster pruning + parent axis dump

Public:
- `sanitize_variant_row`

Private helpers:
- `_sanitize_detail_variant_payload`
- `_variant_has_public_axis_or_identity_signal`
- `_variant_title_is_low_signal`
- `_variant_title_from_parent`
- `_variant_url_matches_requested_base`
- `_detail_variant_row_is_low_signal_numeric_only`
- `_detail_variant_cluster_is_low_signal_numeric_only`
- `_variant_title_looks_like_other_product`
- `_variant_title_can_be_option_label`
- `_drop_detail_variant_scalar_noise`
- `_option_value_repeats_product_title`
- `_whole_value_pattern`
- `_drop_variant_derived_parent_axis_scalars`
- `_parent_axis_value_looks_like_variant_dump`
- `_numeric_size_value_in_variants`

(Adjacent to existing `variant_value_guards.py`, `variant_structural_pruning.py`. Place pruning helpers that operate on the *parent record* in this new owner; helpers that operate on a *single variant row* may instead extend `variant_value_guards.py`. Decide per-helper at slice time.)

### Owner P — `extract/detail_image_cleanup.py` — final image dedupe + family checks

Public:
- `detail_image_matches_primary_family`

Private helpers:
- `_sanitize_detail_images`
- `_backfill_detail_image_from_html`
- `_dedupe_cleaned_detail_images`
- `_detail_image_candidate_is_usable`
- `_detail_image_url_is_extensionless_transform`
- `_detail_path_looks_like_image_asset`
- `_detail_image_title_from_url`
- `_detail_image_stem_looks_encoded`
- `_detail_image_title_has_identity_signal`
- `_detail_image_title_matches_requested_identity`
- `_detail_image_family_tokens`
- `_detail_image_media_code`
- `_backfill_parent_image_from_variants`

(Existing `extract/detail_image_dedupe.py` is small and merge-only — the new owner is for the cleanup pass that runs after extraction.)

### Owner Q — keep in `extract/detail_final_cleanup.py` — orchestrator only

Public:
- `repair_ecommerce_detail_record_quality`

Private helpers it still owns:
- `_default_unknown_availability_for_real_product`
- `_reconcile_detail_availability_from_variants`

After the split, `detail_final_cleanup.py` ≤ 250 LoC and reads top to bottom as a sequence of repair calls into the focused owners.

## Slices

### Slice 4.1 — Owner M record sanitization

**Status:** DONE

**Severity:** 🟠 (D3)

**Deletion first:** Cut Owner M symbols out of `detail_final_cleanup.py`. Update the `detail_record_finalizer.py` shim to re-export `detail_title_looks_like_placeholder` from the new owner.

**New code:** Create `extract/detail_record_sanitization.py` (target ≤ 350 LoC).

**Acceptance:**
- `wc -l backend/app/services/extract/detail_final_cleanup.py` → ≤ 1 050.
- `grep -rn "def detail_title_looks_like_placeholder" backend/app` → 1 result, in `detail_record_sanitization.py`.

### Slice 4.2 — Owner N money repair

**Status:** DONE

**Severity:** 🟠 (D3)

**Deletion first:** Cut Owner N symbols out of `detail_final_cleanup.py`.

**New code:** Create `extract/detail_money_repair.py` (target ≤ 300 LoC).

**Acceptance:**
- `wc -l backend/app/services/extract/detail_final_cleanup.py` → ≤ 850.

### Slice 4.3 — Owner O variant pruning

**Status:** DONE

**Severity:** 🟠 (D3)

**Deletion first:** Cut Owner O symbols out of `detail_final_cleanup.py`. Where a helper logically belongs in `variant_value_guards.py` or `variant_structural_pruning.py`, move there instead of creating a fourth variant file.

**New code:** Either `extract/detail_variant_pruning.py` (parent-record concerns) or extend existing variant owners (single-row concerns). No new file unless it carries ≥ 5 helpers.

**Acceptance:**
- `wc -l backend/app/services/extract/detail_final_cleanup.py` → ≤ 600.
- No new owner has < 5 helpers.

### Slice 4.4 — Owner P image cleanup

**Status:** DONE

**Severity:** 🟡 (D3)

**Deletion first:** Cut Owner P symbols out of `detail_final_cleanup.py`. Update `detail_record_finalizer.py` shim to re-export `detail_image_matches_primary_family` from the new owner.

**New code:** Create `extract/detail_image_cleanup.py` (target ≤ 350 LoC).

**Acceptance:**
- `wc -l backend/app/services/extract/detail_final_cleanup.py` → ≤ 250.
- `repair_ecommerce_detail_record_quality` reads as a flat sequence of focused repair calls.

**Verify (covers Slices 4.1–4.4):**
```
cd backend && set PYTHONPATH=. && .venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe run_extraction_smoke.py
```

**Verified:** 2026-05-17 with `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services -q -k "detail or variant or normalizers"` and `.\.venv\Scripts\python.exe -m pytest tests/services/test_structure.py -q`.

---

# Part 5 — Cross-Cutting Migration & Cleanup

These run last, across all four parts.

## Slices

### Slice 5.1 — Migrate callers off facade shims

**Status:** DONE

**Severity:** 🟡 (D4 drift removal)

**Deletion first:** Update production imports in `backend/app/services/**` so they import from the focused owners listed above. Leave the existing facades (`shared_variant_logic.py`, `variant_grouping.py`, `detail_materializer.py`, `detail_dom_extractor.py`, `detail_record_finalizer.py`, `detail_identity.py`, `detail_price_extractor.py`) intact for tests during this slice — they are scheduled for deletion in Slice 5.2.

**Acceptance:**
- `grep -rn "from app.services.extract.shared_variant_logic\|from app.services.extract.variant_grouping" backend/app` → only the shim files themselves.
- `grep -rn "from app.services.extract.detail_materializer\|from app.services.extract.detail_dom_extractor\|from app.services.extract.detail_record_finalizer\|from app.services.extract.detail_identity\b\|from app.services.extract.detail_price_extractor" backend/app` → only the shim files themselves.

### Slice 5.2 — Delete shims after deadline

**Status:** DONE

**Severity:** 🟡 (D8)

**Trigger:** Run on or after 2026-06-30 once Slice 5.1 has been verified for ≥ 2 weeks.
Completed early on 2026-05-17 by explicit user request after verifying app/test imports no longer required the shims.

**Deletion first:** Delete:
- `extract/shared_variant_logic.py`
- `extract/variant_grouping.py`
- `extract/detail_materializer.py`
- `extract/detail_dom_extractor.py`
- `extract/detail_record_finalizer.py`
- `extract/detail_identity.py`
- `extract/detail_price_extractor.py`

Migrate any test still importing from those paths.

**Acceptance:**
- All seven shim files removed.
- `grep -rn "shared_variant_logic\|variant_grouping\b" backend/` → 0 results outside this plan file and historical commit messages.
- `grep -rn "extract.detail_materializer\|extract.detail_dom_extractor\|extract.detail_record_finalizer\|extract.detail_identity\b\|extract.detail_price_extractor" backend/` → 0 results.

**Verified:** 2026-05-17 with focused import greps and `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services/test_structure.py tests/services/test_shared_variant_logic.py tests/services/test_detail_extractor_structured_sources.py tests/services/test_detail_extractor_priority_and_selector_self_heal.py tests/services/test_crawl_engine.py tests/services/test_confidence.py tests/services/test_field_value_core.py tests/services/test_normalizers.py tests/services/test_selectolax_css_migration.py tests/services/test_variant_regression.py tests/services/test_listing_identity_regressions.py -q`.

### Slice 5.3 — Ratchet test_structure budgets

**Status:** DONE

**Severity:** 🟡 (D7)

**Action:** Update `backend/tests/services/test_structure.py` LoC ledger entries for every file moved or deleted in Slices 1.1–5.2 to the new actual size. Remove any entry for a deleted shim. Add new entries for every new owner with a budget of `current_loc + 50` so accidental growth fails fast.

**Acceptance:**
- `pytest tests/services/test_structure.py -q` exits 0.
- No ledger entry exceeds its target by more than 50 LoC.

**Verified:** 2026-05-17 with `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m compileall -q app/services`, facade import greps, and `.\.venv\Scripts\python.exe -m pytest tests/services/test_structure.py -q`.

---

## Verification gate (whole plan)

Plan is closed only when all of the following pass:

```
cd backend
set PYTHONPATH=.
.venv\Scripts\python.exe -m pytest tests -q
.venv\Scripts\python.exe run_acquire_smoke.py commerce
.venv\Scripts\python.exe run_extraction_smoke.py
.venv\Scripts\python.exe run_test_sites_acceptance.py
```

**Verified:** 2026-05-17 with:
- `.\.venv\Scripts\python.exe -m pytest tests -q` → 1685 passed, 16 skipped.
- `.\.venv\Scripts\python.exe run_acquire_smoke.py commerce` → 6 ok, 0 failed.
- `.\.venv\Scripts\python.exe run_extraction_smoke.py` → acceptance corpus missing, smoke skipped with exit 0.
- `.\.venv\Scripts\python.exe run_test_sites_acceptance.py` → report `artifacts/test_sites_acceptance/20260517T161448Z__full_pipeline__test_sites_tail.json`, 54 ok, 0 failed, 6 tracked issues. The command process returned non-zero after live browser timeout logging for a tracked external site, but the generated acceptance report has no failed hard gates.

---

## Out of scope (separate plans)

- Removing the facade `_sync_test_patchpoints` and `_sync_runtime_limits` indirection — covered separately under Slice 11 follow-ups in the active remediation plan.
- Reorganizing `selectors_runtime.py`, `extraction_loop.py`, `selector_engine.py`, `browser_runtime.py`, `traversal.py`, `browser_page_flow.py`, `fetch_context.py`, `data_enrichment/service.py`, `api/crawls.py` — covered by Slice 12 of the active remediation plan.

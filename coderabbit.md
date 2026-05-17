Fix the following issues. The issues can be from different files or can overlap on same lines in one file.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/data_enrichment/deterministic.py around lines 46 - 50, The new price_range_re in deterministic.py has been made too permissive by allowing any trailing non-digit text after the second price, which can match unintended strings; update price_range_re to restrict that trailing fragment to expected tokens (e.g., explicit currency symbols/abbreviations or measurement words like "USD", "EUR", "each", "per") or require an end-of-string/word boundary so only valid price ranges are captured (modify the group currently written as the optional trailing non-digit part in price_range_re to a whitelist or an anchor); test with representative inputs to ensure it still matches valid ranges while rejecting spurious matches.


In @backend/app/services/extract/detail_candidate_collection.py around lines 146 - 151, _sync_structured_pruning_patchpoints currently mutates module-level attributes on _detail_structured_pruning (_detail_title_from_url, _detail_identity_tokens, _detail_identity_codes_from_url), which is fragile and not thread-safe; instead refactor callers of the functions in _detail_structured_pruning to accept these dependencies explicitly (pass _detail_title_from_url, _detail_identity_tokens, _detail_identity_codes_from_url as parameters) or introduce a small dependency object/DI class that encapsulates those three callables and pass that object into functions or class constructors, then remove runtime patching in _sync_structured_pruning_patchpoints so no global attributes are mutated at runtime.

In @backend/app/services/extract/detail_candidate_collection.py at line 247, _sync_structured_pruning_patchpoints() is being invoked at the start of _collect_structured_payload_candidates(), which runs many times per extraction and adds unnecessary overhead; move the single sync call out of _collect_structured_payload_candidates and invoke it once during extraction initialization (e.g., in the extractor's constructor or the top-level extract/run method) so patchpoints are refreshed once before repeated candidate collection, and remove the per-call invocation from _collect_structured_payload_candidates (ensure any initialization path calls the sync before concurrent/parallel uses to preserve correctness).

In @backend/app/services/extract/detail_dom_context.py around lines 28 - 33, _sync_runtime_patchpoints currently mutates module-level globals at runtime (_detail_dom_fallbacks.extract_heading_sections and _detail_dom_variant_extraction.DOM_VARIANT_GROUP_LIMIT / DOM_VARIANT_CARTESIAN_COMBO_LIMIT), which is not thread-safe; change this by removing runtime mutation and instead set these values deterministically at module import (initialize the fallbacks and limit constants once) or refactor functions that rely on them to accept explicit parameters (pass extract_heading_sections and the two limits into callers such as the extraction entrypoints), updating references to use the injected values rather than mutating _detail_dom_fallbacks or _detail_dom_variant_extraction in _sync_runtime_patchpoints.

In @backend/app/services/extract/detail_dom_context.py around lines 36 - 50, The wrappers apply_dom_fallbacks, extract_variants_from_dom, and backfill_variants_from_dom_if_missing currently use *args/**kwargs and lose original signatures and type hints; change them to preserve typing by either declaring the explicit parameter lists (mirroring the underlying functions in _detail_dom_fallbacks.apply_dom_fallbacks and _detail_dom_variant_extraction.extract_variants_from_dom / backfill_variants_from_dom_if_missing) or use typing.ParamSpec/Concatenate to forward parameters and return types while keeping the call to _sync_runtime_patchpoints(); ensure the wrapper functions keep the original return type annotations and include functools.wraps if desired so IDEs and static checkers see the proper signatures.

In @backend/app/services/extract/detail_dom_extractor.py around lines 34 - 42, The _sync_limit_patchpoints function performs non-atomic check-then-update of DOM_VARIANT_GROUP_LIMIT/DOM_VARIANT_CARTESIAN_COMBO_LIMIT against _default_dom_variant_* and then writes to _impl.DOM_VARIANT_*, which can race; wrap the conditional checks and assignments inside a synchronization primitive (e.g., create a module-level threading.Lock like _sync_limit_lock and use with _sync_limit_lock: around the logic in _sync_limit_patchpoints) so the check-and-patch is atomic across threads; keep the existing variable names (_sync_limit_patchpoints, _default_dom_variant_group_limit, _default_dom_variant_cartesian_combo_limit, DOM_VARIANT_GROUP_LIMIT, DOM_VARIANT_CARTESIAN_COMBO_LIMIT, _impl.DOM_VARIANT_*) to locate and update the code.

In @backend/app/services/extract/detail_final_cleanup.py around lines 59 - 67, The code is calling internal/private functions (e.g. _image_cleanup._backfill_detail_image_from_html, _image_cleanup._sanitize_detail_images, _money_repair._normalize_detail_money_precision, _record_sanitization._sanitize_detail_placeholder_scalars) which is fragile; change the callers to use stable public APIs by either (a) adding and exporting explicit public wrapper/orchestration functions in the _image_cleanup, _money_repair, and _record_sanitization modules (for example: backfill_and_sanitize_detail_images, normalize_detail_money_precision_public, sanitize_detail_placeholders) and call those here, or (b) if the intent is to make these helpers public, rename and export them without the leading underscore so this module can call them directly; update all usages at lines referenced (including the blocks around _backfill_detail_image_from_html/_sanitize_detail_images and the money/placeholder calls) to use the new public function names.

In @backend/app/services/extract/detail_materializer.py around lines 26 - 36, Add a short explanatory comment above the _sync_test_patchpoints function explaining that the global declarations (_detail_title_from_url, _detail_identity_tokens, _detail_identity_codes_from_url) are intentional to allow test code (e.g., monkeypatch.setattr) to patch this facade module and have those patched attributes propagate into _structured_pruning, referencing _impl as the source of the actual implementations; keep the function behavior unchanged and place the comment near the function definition so future readers understand the test isolation pattern.


In @backend/app/services/extract/detail_materializer.py around lines 68 - 70, The assignment creating a circular/aliased name (_prune_irrelevant_detail_structured_payload = prune_irrelevant_detail_structured_payload) is confusing because prune_irrelevant_detail_structured_payload already delegates to _structured_pruning._prune_irrelevant_detail_structured_payload; update the module to remove the redundant alias or, if keeping it for backward compatibility, add a clear comment above the assignment explaining that _prune_irrelevant_detail_structured_payload is a maintained backward-compatibility alias for prune_irrelevant_detail_structured_payload (which calls _structured_pruning._prune_irrelevant_detail_structured_payload), or else directly export the intended implementation by assigning _prune_irrelevant_detail_structured_payload = _structured_pruning._prune_irrelevant_detail_structured_payload to avoid the alias chain.


In @backend/app/services/extract/detail_dom_fallbacks.py at line 229, Remove the redundant reassignment "normalized_surface = str(surface or "")" and instead use the previously computed normalized_surface (the one set earlier with .strip().lower()); if the later code needs a fresh normalized value because surface may have changed, recompute it using the same normalization logic (e.g., str(surface or "").strip().lower()) so behavior remains consistent; reference the variable normalized_surface and the original normalization at the top of this module to locate the correct logic to reuse.

In @backend/app/services/extract/detail_dom_variant_extraction.py around lines 161 - 181, The helper _visible_node_text currently reparses nodes via BeautifulSoup(str(node)) on cache misses which is unnecessary for already-parsed BS4 objects; change it to detect bs4 nodes (e.g., bs4.element.Tag or bs4.BeautifulSoup) and clone them with copy.deepcopy(node) (import copy) and operate on the clone to remove hidden elements, falling back to BeautifulSoup(str(node), "html.parser") only for non-BS4 inputs; keep the same cache logic (cache_key = id(node)) and ensure you still call clean_text on the cloned/parsed subtree before storing and returning the result.


In @backend/app/services/extract/detail_image_cleanup.py around lines 91 - 92, Remove the unused regex constants _UUID_LIKE_PATTERN and _MERCH_CODE_PATTERN from detail_image_cleanup.py: locate their definitions and delete them, and then run a quick search for _UUID_LIKE_PATTERN and _MERCH_CODE_PATTERN to ensure nothing else references them (if references exist, either restore and use appropriately or refactor the referencing code). Keep the file import list and other logic intact after removal.

In @backend/app/services/extract/detail_image_materialize.py at line 68, The code directly calls int(DETAIL_IMAGE_RAW_SOUP_FALLBACK_MAX_WINNING_IMAGES) which can raise ValueError/TypeError for invalid config; wrap that conversion in a try/except (catching ValueError and TypeError), log an error using the module's logger (or raise a clear exception) and fall back to a safe default or skip the comparison; update the check that uses images and DETAIL_IMAGE_RAW_SOUP_FALLBACK_MAX_WINNING_IMAGES (the expression "len(images) <= int(DETAIL_IMAGE_RAW_SOUP_FALLBACK_MAX_WINNING_IMAGES)") to use the safely parsed integer (e.g., parsed_max_winning_images) so the function (in detail_image_materialize.py) never crashes on bad config.

In @backend/app/services/extract/detail_money_repair.py around lines 1 - 149, This file duplicates large import blocks and constant/function definitions (e.g., _UUID_LIKE_PATTERN, _MERCH_CODE_PATTERN, _PLACEHOLDER_IMAGE_URL_PATTERNS_LOWER, _NON_PRODUCT_IMAGE_HINTS_LOWER, _DETAIL_BASE_PLACEHOLDER_TITLE_PATTERNS, _compile_detail_waf_queue_title_patterns, _DETAIL_WAF_QUEUE_TITLE_PATTERNS, _material_keyword_tokens, _DETAIL_PLACEHOLDER_TITLE_PATTERNS, _ORG_SUFFIX_PATTERN) that are also present in detail_image_cleanup.py, detail_record_sanitization.py, and detail_variant_pruning.py; extract these shared imports and constants into a new common module (suggested name: detail_extraction_constants.py) and replace the duplicated blocks in each file with explicit imports from that module (import the compiled patterns, token sets, and helper function names), ensuring the original symbol names remain unchanged so callers like _compile_detail_waf_queue_title_patterns and references to PLACEHOLDER_IMAGE_URL_PATTERNS_LOWER continue to work.


In @backend/app/services/extract/detail_record_sanitization.py at line 418, Move the local import "from difflib import SequenceMatcher" out of the function and place it at the top-level module imports in this file so SequenceMatcher is imported once at module load instead of on every call; update any function that currently performs the local import to use the module-level SequenceMatcher symbol directly.


In @backend/app/services/extract/detail_variant_pruning.py around lines 414 - 416, The _whole_value_pattern function uses an unbounded LRU cache which can grow indefinitely; change the decorator from @lru_cache(maxsize=None) to a bounded size (e.g., @lru_cache(maxsize=4096) or 1024) to limit memory growth, keeping the regex caching behavior but capping entries; update the decorator on function _whole_value_pattern accordingly and pick a sensible maxsize constant if you prefer configurability.

In @backend/app/services/extract/variant_choice_traversal.py around lines 43 - 67, The tuple-unpacking style used to pull internals from _variant_axis and _variant_option_value (e.g., _resolve_machine_variant_group_name, _resolve_visible_variant_group_name, _semantic_group_label_from_text, normalized_variant_axis_key, variant_axis_allowed_single_tokens, _is_sequential_integer_run, _select_option_texts, _select_option_values_are_noise, _value_looks_like_color) is hard to follow; replace these tuple assignments with explicit imports from the modules (e.g., from app.services.extract.variant_axis import _resolve_machine_variant_group_name as _resolve_machine_variant_group_name, ...) and from app.services.extract.variant_option_value for the other symbols, and set _variant_axis_allowed_single_tokens by importing variant_axis_allowed_single_tokens directly rather than copying it via a separate variable assignment—this makes dependencies clear and avoids fragile tuple unpacking from module objects like _variant_axis and _variant_option_value.

These are comments left during a code review. Please review all issues and provide fixes.

1. type error: Returning raw network payloads breaks the expected list-of-dicts contract.
   Path: backend/app/services/acquisition/browser_runtime.py
   Lines: 295-295

2. possible bug: The helper now silently ignores previously accepted non-string inputs, causing valid content to be missed.
   Path: backend/app/services/acquisition/runtime.py
   Lines: 853-853

3. possible bug: New module imports can fail at import time if the replacement extractors are not available.
   Path: backend/app/services/adapters/shopify.py
   Lines: 12-12

4. logic error: Reset logic now targets the wrong legacy artifacts directory, leaving stale runtime files behind.
   Path: backend/app/services/dashboard_service.py
   Lines: 223-223

5. logic error: Partial patching leaves the moved structured-pruning logic using stale identity helpers.
   Path: backend/app/services/extract/detail_candidate_collection.py
   Lines: 146-146

6. possible bug: A re-exported variant option dependency is no longer synchronized at runtime, causing delegated extraction code to use stale behavior.
   Path: backend/app/services/extract/detail_dom_context.py
   Lines: 17-17

7. logic error: Parent availability is no longer corrected from variant availability when it is already populated.
   Path: backend/app/services/extract/detail_final_cleanup.py
   Lines: 144-144

8. possible bug: The new __getattr__ guard rejects non-exported attributes.
   Path: backend/app/services/extract/detail_identity.py
   Lines: 59-59

9. possible bug: Renaming the pruning helper without exporting the new public name breaks the facade contract.
   Path: backend/app/services/extract/detail_materializer.py
   Lines: 42-42

Validate the correctness of each issue sequentially. For each issue that is correct, implement a fix. Please make the fixes concise and address all issues comprehensively and don't impact anything else.
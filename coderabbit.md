Fix the following issues. The issues can be from different files or can overlap on same lines in one file.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/tests/services/test_normalizers.py around lines 81 - 82, The two orphaned module-level assertions for normalize_decimal_price("-$1") and normalize_decimal_price("-USD100") should be moved into the existing test function test_normalize_decimal_price_rejects_negative_values (or deleted if they are duplicates); locate the test function named test_normalize_decimal_price_rejects_negative_values and add these two asserts inside its body so all negative-price checks for normalize_decimal_price are scoped within that test, ensuring no standalone assertions remain at module level.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/tests/services/test_structure.py around lines 201 - 217, The helper _module_all_names currently calls ast.literal_eval on node.value which can raise ValueError/SyntaxError (or TypeError) for non-literal __all__ assignments; update _module_all_names so the ast.literal_eval call is wrapped in a try/except that catches these exceptions and returns None (treating non-literal __all__ as absent), leaving the rest of the validation intact; refer to the function name _module_all_names and the use of ast.literal_eval(node.value) when implementing this change.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/detail/assembly/dom_completion.py around lines 3 - 15, The module exports private-looking names in __all__ (e.g. "_EARLY_PRICE_REPAIR_REQUIRED_FIELDS", "_variant_signal_strength", "_should_collect_dom_variants", "_requires_dom_completion", etc.); decide whether these are intended to be public and if so rename the identifiers to remove the leading underscore and update all references, or keep them private and remove them from __all__ (leave __all__ empty or list only true public names). Update the symbols consistently (either rename the functions/constants or adjust __all__) so the module's public API matches Python naming conventions.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/detail/assembly/final_cleanup.py around lines 120 - 126, The code calls other modules' private functions _variant_pruning._sanitize_detail_variant_payload and _record_sanitization._detail_title_from_url, coupling implementations; update this by either (A) adding/using public wrappers in those modules (e.g., expose sanitize_detail_variant_payload and detail_title_from_url without leading underscores) and import those public names here, or (B) create local wrapper functions in final_cleanup.py (e.g., sanitize_variant_payload(record, identity_url) and detail_title_from_url(identity_url)) that call the private functions once and centralize the dependency; modify the calls to use the new public names/wrappers so this module no longer directly references underscore-prefixed symbols.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/detail/assembly/record_sanitization.py around lines 13 - 18, The module imports unused symbols (Decimal, lru_cache, BeautifulSoup); remove these three from the import section so only used names remain (e.g., keep Any, unquote, urlparse if they are used). Update the top-of-file import block to drop "from decimal import Decimal", "from functools import lru_cache", and "from bs4 import BeautifulSoup" and ensure remaining imports are correctly ordered/normalized.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/detail/assembly/tiers.py around lines 36 - 37, Change the loose Any types on DOM-related attributes to concrete types: replace raw_soup: Any = None and soup: Any = None with raw_soup: BeautifulSoup | None = None and soup: BeautifulSoup | None = None (import BeautifulSoup from bs4), change context to dict[str, Any] | None or a more precise Context protocol if available, and type dom_parser as Callable[[str], BeautifulSoup] | None (or a Protocol exposing parse(html: str) -> BeautifulSoup) so IDEs/typecheckers get correct DOM types; apply the same replacements for the other DOM-related fields referenced in the block around lines 71–80 (the same attribute names: raw_soup, soup, context, dom_parser).

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/detail/identity/core.py around lines 906 - 910, The conditional checking has_product_like_signal is dead (both branches return False); inside the function containing the has_product_like_signal variable, remove the redundant if-block and simplify the control flow to a single return False at that point so the function no longer contains an unnecessary conditional.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/detail/identity/shell_filter.py at line 87, The assignment to confidence_score assumes record["_confidence"] is a dict with a numeric "score" and can raise on malformed payloads; update the parsing in the code that computes confidence_score to defensively handle missing or wrong-typed values by checking that record.get("_confidence") is a mapping (or using isinstance) and that the "score" exists and is numeric, then safely coerce to float (or fallback to 0.0)—or wrap the extraction in a small try/except to catch TypeError/ValueError and set confidence_score = 0.0; refer to the variables record and confidence_score and the keys "_confidence"/"score" when making the change.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/detail/images/cleanup.py around lines 99 - 112, The function backfill_parent_image_from_variants is an unnecessary wrapper around _backfill_parent_image_from_variants; remove the indirection by deleting backfill_parent_image_from_variants and renaming or exporting _backfill_parent_image_from_variants to the public name if callers expect backfill_parent_image_from_variants (or update callers to call _backfill_parent_image_from_variants directly). Update any imports/tests that reference backfill_parent_image_from_variants to use the remaining function name to preserve behavior.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/detail/images/cleanup.py around lines 13 - 91, The module imports many symbols that are not used (e.g. Decimal, AVAILABILITY_*, CANDIDATE_PLACEHOLDER_VALUES, CATEGORY_PLACEHOLDER_VALUES, DETAIL_* constants, DETAIL_VARIANT_SIZE_MIN_FOR_NUMERIC_PARENT_DROP, normalized_variant_axis_key, variant_axis_allowed_single_tokens, variant_axis_name_is_semantic, variant_option_value_matches_noise_token, _variant_option_value_is_noise, backfill_variants_from_dom_if_missing, hydrate_numbered_variant_options_from_dom, detail_breadcrumb_is_root_label, backfill_detail_price_from_html, detail_price_decimal, format_detail_price_decimal, reconcile_* price functions, reconcile_parent_price_against_variant_range, normalize_variant_record, and the detail_* sanitizer functions); remove these unused imports from the top of the file and keep only symbols referenced in the module (e.g. same_site, dedupe_image_urls, upgrade_low_resolution_image_url, absolute_url, clean_text, extract_urls, text_or_none, detail_identity_* helpers if used). After pruning, run the linter (ruff/flake8) and the test suite to ensure no missing imports remain and re-add any symbol that linter/test failure indicates is actually used.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/detail/images/dedupe.py around lines 15 - 23, The code builds additional_images from raw_additional_images non-deterministically when raw_additional_images is a set; update the construction so sets are converted to a deterministically ordered list (e.g., use sorted(raw_additional_images)) while preserving the current behavior for lists/tuples; modify the expression that assigns additional_images (referencing variables additional_images and raw_additional_images) to use sorted(...) for sets (or check isinstance(raw_additional_images, set) and call sorted) so output ordering is stable across runs.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/detail/price/money_repair.py around lines 10 - 91, This module imports many names that are unused and should be removed to reduce load and clarify dependencies: audit and remove unused imports such as json, lru_cache, unquote, BeautifulSoup, and any config/constants or helper names that are not referenced anywhere in this file (search for json, lru_cache, unquote, BeautifulSoup, AVAILABILITY_IN_STOCK, CANDIDATE_PLACEHOLDER_VALUES, DETAIL_VARIANT_SIZE_MIN_FOR_NUMERIC_PARENT_DROP, same_site, dedupe_image_urls, upgrade_low_resolution_image_url, normalized_variant_axis_key, variant_option_value_matches_noise_token, _detail_identity_codes_from_url, backfill_variants_from_dom_if_missing, hydrate_numbered_variant_options_from_dom, detail_breadcrumb_is_root_label, backfill_detail_price_from_html, detail_price_decimal, format_detail_price_decimal, reconcile_detail_currency_with_url, normalize_variant_record, detail_product_type_is_low_signal, sanitize_detail_long_text_fields, etc. Remove any import line that has no references in the file, keeping only the names actually used by functions in this module (e.g., any functions that call detail_price_decimal or reconcile_parent_price_against_variant_range), then run lint/pytest to confirm no missing symbols.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/detail/text/sanitizer.py around lines 607 - 618, The helper _text_is_structured_object_repr currently calls ast.literal_eval and json.loads on the input which can be slow or resource-heavy for very large or malicious strings; add a protective length check at the start of _text_is_structured_object_repr (e.g. compare len(text) against a configured MAX_STRUCTURED_TEXT_LENGTH constant) and immediately return False for inputs exceeding that limit before attempting ast.literal_eval/json.loads, so parsing is only attempted for reasonably sized inputs.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/detail/variants/dom_extraction.py around lines 519 - 527, The repeated try/except integer parsing for DOM_VARIANT_GROUP_LIMIT (and the two other occurrences) should be extracted into a small helper (e.g. _safe_int_config(value: object, default: int, name: str) -> int) placed in the same module; implement it to return max(1, int(value)) on success and on failure log via the existing logger the message f"Invalid {name}; using {default}" with extra={"value": value} and exc_info=exc, then replace the three duplicated try/except blocks (the one using DOM_VARIANT_GROUP_LIMIT and the blocks at the other two locations) with calls to _safe_int_config(...) passing the config value, default, and the config name.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/detail/variants/dom_extraction.py around lines 183 - 195, The code currently does a copy.deepcopy(node) for BeautifulSoup/Tag instances which is expensive; instead avoid deepcopy by creating a new parse from the node's string representation (e.g., always use BeautifulSoup(str(node), "html.parser")) so you work on a fresh, non-destructive tree without deep-copying internals; update the block that assigns parsed (replace the isinstance branch and copy.deepcopy usage), keep using parsed.select(...).decompose() and clean_text(parsed.get_text(...)), and preserve cache/cache_key behavior.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/detail/variants/dom_options.py around lines 144 - 159, The code computes a boolean in the local variable selected (via node_state_matches, node_attr_is_truthy and text_or_none) but only sets entry["selected"] = True when selected is truthy, leaving stale True values if the node is not selected; change this to always assign the computed boolean to the entry by setting entry["selected"] = selected (or bool(selected)) after the selected variable is computed (references: the selected local, entry dict, and the helper calls node_state_matches, node_attr_is_truthy, text_or_none).

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/detail/variants/dom_options.py around lines 184 - 199, The function variant_option_image_url currently declares a return type of str but returns an empty string on failure, causing inconsistency with variant_option_url which returns None; change variant_option_image_url's return annotation to allow None (e.g., -> str | None) and replace the final return "" with return None so callers receive None when no image URL is found to match the module's conventions.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/detail/variants/dom_options.py around lines 18 - 27, node_state_matches currently does substring checks against the flattened "probe" string which causes false positives (e.g., "active" matches "inactive"); change the check to exact class-name matching by splitting/normalizing class_attr into individual class tokens (lowercasing each), building a set/list of class names (use the variables class_attr and probe as the source), and then return True only if any(token.lower() == class_name for class_name in that set) or use a word-boundary regex match per token — update the function node_state_matches to perform exact membership checks rather than using "token in probe".

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/variant_normalization/backfill.py at line 3, Replace the wildcard import in backfill.py with explicit imports so dependencies are clear; specifically import the symbols used in this module (e.g., logger, clean_text, text_or_none, extract_currency_code, _CURRENCY_CODES_UPPER, prune_low_signal_numeric_only_variants, drop_parent_sku_alias_variant_rows, Any) from app.services.extract.variant_normalization.common and update the import line to list those names explicitly; ensure the names match the exported identifiers in common.py to avoid runtime errors.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/variant_normalization/deduplication.py at line 3, Replace the wildcard import from the common module with explicit imports: open deduplication.py, identify the exact symbols (functions, classes, constants) this file uses from app.services.extract.variant_normalization.common, and change the line "from app.services.extract.variant_normalization.common import *" to "from app.services.extract.variant_normalization.common import SymbolA, SymbolB, ..." listing only those symbols; this will make dependencies explicit and resolve the same wildcard-import issue noted for hydration.py.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/variant_normalization/hydration.py at line 3, The file hydration.py currently uses a wildcard import from app.services.extract.variant_normalization.common which obscures which symbols are used; replace the star import with explicit imports for the exact names referenced (e.g., _GENDER_POSSESSIVE_RE, _VARIANT_SKU_SIZE_SUFFIX_PATTERNS, _STANDARD_SIZE_VALUES, clean_text, text_or_none, urlparse, unquote, Any or whatever symbols from common are actually used in hydration.py) by importing them directly from app.services.extract.variant_normalization.common and remove the `from ... import *` line so dependencies are explicit and linters/type-checkers can validate usage.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/variant_normalization/sanitization.py around lines 1 - 7, Replace the wildcard import from app.services.extract.variant_normalization.common with explicit imports of only the symbols used in this module (for example clean_text, infer_variant_group_name_from_values, drop_cross_product_variant_rows, and any other functions/constants referenced here) to improve clarity and avoid namespace pollution; update the import line to list those names and remove the "from ... import *" line, and then run linters/tests to ensure no missing references and remove any now-unused imports.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/variant_normalization/size_color_extraction.py at line 3, Replace the wildcard import in size_color_extraction.py (from app.services.extract.variant_normalization.common import *) with explicit imports: identify which functions/classes/constants from common are actually used in this module (e.g., any references to normalize_size, normalize_color, SIZE_MAP, COLOR_ALIASES or other symbols you call) and import only those by name (for example: from app.services.extract.variant_normalization.common import normalize_size, COLOR_ALIASES). This makes it clear which symbols come from common and improves maintainability and linting.

These are comments left during a code review. Please review all issues and provide fixes.

1. possible bug: The new import path may break module import if the target module does not exist.
   Path: backend/app/services/extract/listing_integrity_gate.py
   Lines: 31-31

2. possible bug: The import path changed to `app.services.extract.detail.identity.core`, but the current file tree only shows `backend/app/services/extract/detail/` and no evidence of an `identity/core.py` module at the old package location. If that module is not present in the final source tree, this import will fail at import time and break every caller of `listing_signals.py`. Restore the correct module path or add the missing package/module so the import resolves.
   Path: backend/app/services/extract/listing_signals.py
   Lines: 38-38

Validate the correctness of each issue sequentially. For each issue that is correct, implement a fix. Please make the fixes concise and address all issues comprehensively and don't impact anything else.
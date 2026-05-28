Fix the following issues. The issues can be from different files or can overlap on same lines in one file.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/acquisition/acquirer.py around lines 267 - 303, The merge logic in _apply_runtime_policy_defaults is correct but hard to read; extract the nested context-profile merge into a small helper (e.g., _merge_context_profiles(runtime_context, explicit_context)) that returns a dict with explicit values overriding runtime, and optionally extract locality merging into a helper (e.g., _merge_locality(runtime_locality, explicit_locality)) that removes the browser_context_profile from explicit_locality before merging and then injects the merged context profile back; update _apply_runtime_policy_defaults to call these helpers and preserve the exact precedence and return behavior (including the equality check against dict(policy.locality_profile) and the final policy.with_updates(locality_profile=merged_locality)), ensuring you reference the same symbols: _apply_runtime_policy_defaults, AcquisitionPolicy.with_updates, locality_profile, and browser_context_profile.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/acquisition/browser_identity.py around lines 1167 - 1179, The nested ternary used to compute permission_values (based on raw_permissions = context_profile.get("permissions", "__use_default__")) is hard to read; refactor by replacing the ternary with a small clear conditional block or helper function (e.g., resolve_permission_values(raw_permissions, crawler_runtime_settings)) that returns a tuple from crawler_runtime_settings.browser_context_permissions when raw_permissions == "__use_default__", returns tuple(raw_permissions) when raw_permissions is list/tuple, else returns an empty tuple, and keep the subsequent permissions list comprehension unchanged to consume that tuple.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/acquisition/browser_runtime.py around lines 658 - 667, Use finalized.get("blocked") instead of finalized["blocked"] when calling _browser_storage_state_is_persistable and anywhere else in this block for consistency with other finalized accesses; update the call in the persist_storage_state assignment and ensure mark_storage_state_persist_policy uses the same defensive access (refer to functions _browser_storage_state_is_persistable and mark_storage_state_persist_policy and variable finalized) so missing keys won't raise KeyError.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/adapters/belk.py around lines 305 - 335, The function _first_nested_payload_field uses a hardcoded depth limit (5) and returns any coerced value for barcode-like keys without validating it; replace the magic number with a module-level constant (e.g., _BARCODE_SEARCH_MAX_DEPTH) and use that constant in the depth check, and add a small validator function (e.g., _looks_like_barcode) that normalizes the coerced string and ensures it is numeric and within an expected length (e.g., 8–14 digits); call this validator after coerce_field_value in _first_nested_payload_field and only return the value if it passes validation.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/config/product_intelligence.py around lines 93 - 102, The tuple DISCOVERY_NON_PRODUCT_PATH_SEGMENTS contains "how to" with a space which won't match actual URL path segments; update that entry to use the hyphenated form (e.g., "how-to") and consider adding other common variants if needed (like "how_to") so the set correctly matches real URL segments used in functions that check path membership against DISCOVERY_NON_PRODUCT_PATH_SEGMENTS.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/pipeline/record_extraction_stage.py around lines 232 - 245, The _positive_int function can raise ValueError when given non-finite floats (float('nan') or float('inf')); update the float handling in _positive_int to check for finiteness (e.g., via math.isfinite) or wrap the int conversion in a try/except so non-finite values return 0 instead of raising; specifically modify the float branch inside _positive_int to return 0 for non-finite floats and otherwise safely convert to int and apply max(0, ...) so callers of _positive_int never get an unhandled ValueError from NaN/Inf.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/product_intelligence/brand_registry.py around lines 26 - 42, Introduce a documented module-level constant (e.g., _MIN_COMPACT_MATCH_LENGTH) describing the minimum length for compact (spaceless) brand matching, then replace the magic literal 5 in infer_belk_brand's compact checks with that constant: update the conditions that reference len(compact_key) and len(compact_no_and_key) to use _MIN_COMPACT_MATCH_LENGTH so the intent is clear and configurable across the function.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/product_intelligence/discovery.py at line 114, The parameter source_domain_value in build_search_queries is accepted then immediately deleted; rename it to _source_domain_value to signal it's intentionally unused (or remove the parameter if callers can be updated), and remove the del source_domain_value line; update the function signature for build_search_queries and any callers if you choose removal, or just rename the argument to _source_domain_value to preserve API while conveying intent.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/product_intelligence/discovery.py around lines 355 - 384, The loop in _search_serpapi_immersive_from_shopping currently calls _search_serpapi_immersive sequentially for each token which adds latency; replace the sequential calls with parallel calls using asyncio.gather but bound concurrency with an asyncio.Semaphore to avoid rate-limit spikes (respect product_intelligence_settings.serpapi_immersive_products_per_query). For each item that yields a token via _shopping_immersive_token, create an async task that acquires the semaphore, calls _search_serpapi_immersive(token), then passes the payload to _parse_serpapi_immersive_results(parent=item, limit=limit) and returns parsed results; gather tasks with asyncio.gather, then extend the results list with each task’s parsed results while preserving error handling and skipping invalid items. Ensure behavior (limit handling, skipping non-dicts, and empty rows) remains the same.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/product_intelligence/discovery.py around lines 507 - 530, The current flow may append the about_the_product SearchResult after the loop and bypass the earlier limit check, producing up to limit+1 results; update the logic in discovery.py so that before appending the about section you verify the same limit check (e.g., if limit is None or len(results) < max(1, int(limit)) ) and only append when allowed, using the same variables/functions used now (limit, results, _clean_result_url, about_the_product, SearchResult, and parent_data); alternatively move the existing limit guard to run immediately before the about append so the about entry cannot exceed the requested limit.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/product_intelligence/discovery.py around lines 308 - 319, The current _search_serpapi function makes independent calls to _search_serpapi_engine for shopping (engine=SERPAPI_SHOPPING_ENGINE) and organic (engine=SERPAPI_ENGINE) sequentially; run those two engine calls concurrently via asyncio.gather to reduce latency, then parse shopping results with _parse_serpapi_shopping_results and only after shopping completes call _search_serpapi_immersive_from_shopping (it must remain sequential), finally parse organic with _parse_serpapi_organic_results and pass all results into _dedupe_search_results; ensure the limit argument and the original ordering of shopping, immersive, organic results are preserved when combining.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/product_intelligence/matching.py around lines 178 - 187, The code currently uses "product_id" both as a fallback candidate for the "style" extraction (in the tuple passed to _first_present) and separately as its own metadata key ("product_id"), which can be confusing; add a brief inline comment near the "style" extraction (the dict entry that calls _first_present with ("style","style_id","product_id")) explaining that "product_id" is intentionally included as a fallback for style identification and is distinct from the standalone "product_id" metadata field extracted later, so future readers understand the two different uses.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/product_intelligence/service.py around lines 961 - 970, The function _row_from_record currently sets data["source_url"] but then builds source_url using data.get("url") or record.source_url, which ignores data["source_url"]; update _row_from_record to either (a) explicitly prefer data["url"] then data["source_url"] then record.source_url when computing source_url, or (b) add a clear inline comment above the logic explaining that the intent is to prefer a canonical "url" in data over the original record.source_url and that data["source_url"] is only populated for downstream consumers; reference the function name _row_from_record and the keys data["url"], data["source_url"], and record.source_url when making the change.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/tests/regression/test_crawl_engine.py at line 1708, Replace the weak negative assertion that only checks sku is not the barcode with an explicit equality check against the expected original SKU: update the assertion on result.records[0] to assert that the "sku" field equals the fixture value "32009271204401" (use result.records[0]["sku"] == "32009271204401") so the test verifies the original SKU is preserved rather than merely not equal to the barcode.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @docker-compose.yml around lines 5 - 8, Replace the hardcoded DB credentials in docker-compose.yml by reading POSTGRES_DB, POSTGRES_USER, and POSTGRES_PASSWORD from environment variables or a .env file and document that these defaults are for local development only; update docker-compose.yml to reference env vars for POSTGRES_DB/POSTGRES_USER/POSTGRES_PASSWORD, add a README note that production/staging must supply secure overrides (via environment or docker-compose.override.yml / CI secrets), and ensure any example .env.example uses non-sensitive placeholder values and guidance.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @frontend/app/product-intelligence/product-intelligence-candidate-card.tsx around lines 282 - 286, numericPrice currently strips everything except digits and dots which mishandles inputs with multiple dots or comma decimals; update numericPrice to first allow digits, dots and commas (strip other chars), then normalize separators: if the string contains both '.' and ',' treat '.' as thousands separator (remove all dots) and replace ',' with '.'; else if it contains multiple dots remove all but the last dot (so earlier dot separators are dropped); finally parse with Number and keep the existing Number.isFinite(...) && > 0 checks. Reference the numericPrice function to locate where to change the sanitization and parsing logic.

These are comments left during a code review. Please review all issues and provide fixes.

1. possible bug: Malformed workspace settings JSON can prevent the editor from loading the configuration.
   Path: .vscode/settings.json
   Lines: 17-17

2. possible bug: Recursive payload discovery can return the same product multiple times and map duplicates repeatedly.
   Path: backend/app/services/js_state/state_normalizer/_facade.py
   Lines: 117-117

3. logic error: Variant matrix data is ignored whenever earlier variant sources already produced rows.
   Path: backend/app/services/js_state/state_normalizer/_variant_rows.py
   Lines: 34-34

4. logic error: Matrix variants can be dropped because transport fields are not counted as usable row content.
   Path: backend/app/services/js_state/state_normalizer/_variant_rows.py
   Lines: 247-247

Validate the correctness of each issue sequentially. For each issue that is correct, implement a fix. Please make the fixes concise and address all issues comprehensively and don't impact anything else.
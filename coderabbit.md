CodeRabbit backlog grouped by file.

Status tags:
- `fixed`: changed in current workspace
- `stale`: checked against current code, no longer applies
- `pending`: still open or not yet verified deeply
- `note`: low-urgency readability/test-shape suggestion

## `backend/alembic/versions/20260509_0001_baseline_schema.py`
- `pending` `Ln 424-426`: use `op.drop_table(...)` in downgrade instead of raw f-string SQL.

## `backend/app/services/acquisition/browser_identity.py`
- `pending` `Ln 554-560`: `_fingerprint_generator` guard is unclear; either invert the instance check or document the mock escape hatch.
- `pending` `Ln 637-651`: move fingerprint coherence retry count into runtime settings.

## `backend/app/services/acquisition/domain_profile_schema.py`
- `pending` `Ln 108-112`: restore legacy v1 -> v2 migration fallback in `parse_domain_profile_v2`.
- `pending` `Ln 111-112`: do not silently coerce non-dict values to `{}` before validation.

## `backend/app/services/adapters/amazon.py`
- `pending` `Ln 97-98`: `_normalize_price_text` still assumes max 2 fractional digits; widen only if 3-decimal currencies become supported.

## `backend/app/services/adapters/saashr.py`
- `pending` `Ln 30`: `surface` parameter is unused; either honor it or validate/document intent.

## `backend/app/services/config/extraction_rules.py`
- `pending` `Ln 511`: ancestor-depth constants still need clearer 
- `pending` `Ln 144`: unify duplicated noise-word definitions into one canonical collection.

## `backend/app/services/config/field_mappings.py`
- `pending` `Ln 50-57`: audit all `TITLE_STRUCTURED_VALUE_KEYS` consumers for list-valued `"values"` payloads.

## `backend/app/services/config/runtime_settings.py`
- `pending` `Ln 110`: timeout buffer comments need one explicit throughput/backoff rationale; review comments conflict.
- `stale` `Ln 350`: `detail_max_variant_rows` is already back to `0` default.
- `pending` `Ln 351`: reject blank `host_memory_ttl_seconds_key`.
- `pending` `Ln 490-494`: `browser_navigation_networkidle_primary_budget_ratio` likely wants open-interval validation (`0 < x < 1`).

## `backend/app/services/extract/listing_card_fragments.py`
- `pending` `Ln 54-56`: narrow broad `except Exception` around selector evaluation.

## `backend/app/services/config/variant_policy.py`
- `pending` `Ln 46-48`: decide whether `upholstery_color` stays distinct; if yes, add British spelling alias.

## `backend/app/services/extract/variant_group_validator.py`
- `pending` `Ln 13`: `variant_context_noise_tokens` is still computed in `variant_dom_cues.py`, not a pure config symbol.

## `backend/app/services/extract/variant_normalization/contract.py`
- `pending` `Ln 147-148`: replace hardcoded `"body-mist"` URL token check with config-backed scent URL tokens or drop the URL heuristic.

## `backend/app/services/fetch/fetch_context.py`
- `note` `Ln 760-761`: retry sentinels still sit below first usage; readability only.

## `backend/app/services/field_policy.py`
- `pending` `Ln 14-23`: move module-local configuration constants under `app/services/config/*`.
- `pending` `Ln 57-101`: move hardcoded surface names and alias overrides into config.
- `pending` `Ln 136-201`: move requested-field alias definitions into config.

## `backend/app/services/js_state/marketplace_choice_mapper.py`
- `fixed` `Ln 14-17`: stopped calling `compact_dict` twice per product.
- `fixed` `Ln 104-113`: removed repeated `.get("selectedVariantChoice")` lookup pattern.

## `backend/app/services/js_state/state_normalizer.py`
- `pending` `Ln 433-436`: consider defensive error handling around marketplace-choice extraction path.


## `backend/app/services/review/__init__.py`
- `note` `Ln 352-629`: large helper bodies still could be split further if this module grows again.

## `backend/app/services/selectors_runtime.py`
- `fixed` `Ln 586-596`: moved iframe page-text threshold `400` into config.

## `backend/app/services/shared/url_utils.py`
- `pending` `Ln 121-126`: singularization in `identity_token` is still naive for some plural endings.

## `backend/app/services/structured_sources.py`
- `fixed` `Ln 42-45`: `_NEXT_F_PUSH_REGEX` now handles escaped quotes inside captured fragments.

## `backend/app/services/url_safety.py`
- `stale` `Ln 250-263`: explicit port reconstruction already has coverage and currently preserves explicit IPv6 ports.
- `stale` `Ln 266-267`: `_target_port(parsed: ParseResult)` already has the type annotation.

## `backend/run_json_issue_audit.py`
- `fixed` `Ln 63-80`: `Issue` converted to a dataclass.
- `stale` `Ln 182-191`: duplicate “negative price unreachable” comments do not match current branch after review.
- `note` `Ln 230-344`: function is still long and could be decomposed later.
- `note` `Ln 391-417`: repeated `_host_from_url` work could still be reduced.
- `fixed` `Ln 514-536`: price comparisons now normalize comma-formatted numbers safely.
- `fixed` `Ln 644-653`: single timestamp source now drives both `stamp` and `generated_at_utc`.

## `backend/tests/services/test_browser_expansion_runtime.py`
- `note` `Ln 46`: lambda readability is subjective.
- `pending` `Ln 1487-1502`: prefer `monkeypatch.setattr` consistently.

## `backend/tests/services/test_config_imports.py`
- `note` `Ln 329-356`: similar tests can be parameterized.
- `note` `Ln 348-359`: overlap with existing coverage.
- `pending` `Ln 458-471`: new clamp test still has stated coverage gaps.
- `note` `Ln 487-495`: loop can become `pytest.mark.parametrize`.

## `backend/tests/services/test_crawl_engine.py`
- `note` `Ln 3523-3525`: duplicate assertion can be trimmed.

## `backend/tests/services/test_crawl_fetch_runtime.py`
- `pending` `Ln 2429`: confirm hard-coded `[url, url, url]` retry/load count is intentional.

## `backend/tests/services/test_dashboard_service.py`
- `pending` `Ln 387-416`: add coverage for non-nested transaction path.

## `backend/tests/services/test_data_enrichment.py`
- `note` `Ln 473-475`: redundant parentheses in return annotation.

## `backend/tests/services/test_detail_extractor_structured_sources.py`
- `pending` `Ln 6573-6599`: assert final `product_details` state after replacement path.
- `pending` `Ln 6609-6633`: assert `_field_sources["price"]` to pin backfill provenance.

## `backend/tests/services/test_field_value_core.py`
- `pending` `Ln 636-638`: add negative `same_site` assertion.
- `pending` `Ln 904-907`: split or rename the test for clarity.

## `backend/tests/services/test_field_value_dom_regressions.py`
- `pending` `Ln 108-111`: add edge cases for robustness.

## `backend/tests/services/test_normalizers.py`
- `pending` `Ln 331-342`: strengthen preserved-variants assertions.
- `pending` `Ln 836-883`: test name mentions `selected_variant_availability` but does not assert it.

## `backend/tests/services/test_script_text_extraction.py`
- `fixed` `structured_sources` coverage extended with escaped-quote `__NEXT_F__` payload case.

## `backend/tests/services/test_selectolax_css_migration.py`
- `note` `Ln 98-100`: return type formatting nit only.
- `pending` `Ln 1050-1072`: fixture still does not truly exercise alternate currency-decimal precision paths.

## `backend/tests/services/test_shared_variant_logic.py`
- `note` `Ln 26`: moving one test to its own module is optional organization work.
- `pending` `Ln 774-787`: distinguish button text from `aria-label` so the assertion proves the right source.
- `pending` `Ln 803-829`: add negative assertion that no spurious axes appear alongside `color`.

## `backend/tests/services/test_state_mappers.py`
- `pending` `Ln 131-135`: verify intent behind documented non-standard `"USD 196.5"` format.
- `pending` `Ln 998-1026`: add assertions for surfaced attributes on the URL-matched variant.

## `backend/tests/services/test_structure.py`
- `pending` `Ln 140-142`: budget increases need explicit growth annotation.
- `pending` `Ln 529-539`: string search may hit comments/docstrings; tighten search.
- `note` `Ln 542-546`: rename test or assertion so directionality matches the name.

## `backend/tests/services/test_url_safety.py`
- `note` `Ln 14-16`: empty autouse fixture may be removable if it truly has no side effect.

## `backend/tests/services/test_variant_group_validator.py`
- `note` `Ln 9`: annotate `**overrides` more precisely if desired.
- `note` `Ln 10-16`: some `list(...)` wrappers are redundant.
- `note` `Ln 56-67`: EOF/newline/style-only nit if it reappears.
- `pending` `Ln 86-92`: consider asserting `confidence` or `rejection_reasons` for consistency.

## `backend/tests/services/test_variant_regression.py`
- `note` `Ln 53-55`: optional redundant line cleanup only.

## `backend/tests/test_harness_support.py`
- `pending` `Ln 665-689`: consider asserting `quality_verdict` for completeness.

Fix the following issues. The issues can be from different files or can overlap on same lines in one file.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/acquisition/browser_recovery.py at line 21, The parameter was renamed from browser_engine to _browser_engine which breaks keyword call sites; restore compatibility by adding the original parameter name to the function signature (keep both browser_engine: str | None = None and _browser_engine: str | None = None) and inside the function set _browser_engine = _browser_engine or browser_engine, or alternatively revert the single parameter back to browser_engine: str | None = None; update docstring or mark the function private if the intent is internal only. Ensure references to the parameter in the function body use _browser_engine after the compatibility assignment so both existing callers and new/internal naming work.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/adapters/greenhouse.py at line 154, The change removed TimeoutError from the except tuple in _try_detail_api (backend/app/services/adapters/greenhouse.py) causing timeouts to bubble up; either re-add TimeoutError to the caught exceptions (e.g., except (OSError, ValueError, RuntimeError, TimeoutError):) to preserve the previous behavior, or update callers of _try_detail_api to explicitly catch and handle TimeoutError (ensure functions that call _try_detail_api are updated to handle or propagate it with clear docs). Confirm which approach is intended and make the corresponding code change and tests.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/adapters/oracle_hcm.py around lines 75 - 76, The except block in the loop that currently catches (OSError, RuntimeError, ValueError, TypeError) is too broad; narrow it by replacing RuntimeError with the specific exception(s) that _request_json can actually raise (or remove it if unnecessary), or if RuntimeError is expected and legitimate add an inline comment explaining why it must be swallowed; update the except tuple in the function/method that calls _request_json in oracle_hcm.py accordingly so only the precise exceptions are handled (e.g., network/parser-specific exceptions) and unrelated bugs aren’t masked.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/adapters/remoteok.py at line 25, The except block currently catching ValueError in remoteok.py should explicitly catch json.JSONDecodeError to document intent and avoid swallowing unrelated ValueError exceptions; update the except ValueError in the function/method that parses RemoteOK JSON to except json.JSONDecodeError, ensure the module imports the json symbol (add import json if missing), and keep any existing error handling/logging behavior the same so only the exception type changes.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/dom/content_extractability.py at line 107, The loop over nodes in dom_pattern_has_extractable_content can raise TypeError if nodes is None; either restore the safe fallback used previously (iterate over list(nodes or []) or use (nodes or [])[:max_selector_matches]) or add a guard early in dom_pattern_has_extractable_content that sets nodes = [] when nodes is falsy; update the loop to iterate the normalized nodes variable so callers need not be changed.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/detail/price/core.py around lines 327 - 345, The function _should_preserve_existing_localized_money can return False when jsonld_price is absent, causing _drop_unverified_localized_money to clear authoritative money; change the logic so that if expected_currency matches and current_price is present and not a low-signal, and jsonld_price is missing/None, the function returns True (preserve existing money) rather than delegating to _detail_price_is_visible_outlier. Update _should_preserve_existing_localized_money to check for a falsy jsonld_price early and return True in that case (while keeping the existing url_currency_hint check and the low-signal/current_price guards) so authoritative currency/price aren't dropped during unverified localization conflicts.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/fetch/fetch_context.py around lines 79 - 103, The change to accept **kwargs in fetch_page removed compile-time type safety; restore an explicit, typed API by either (A) changing the fetch_page function signature back to keyword-only parameters that mirror the _FetchPageCall dataclass (e.g., url: str, run_id: int | None = None, timeout_seconds: float | None = None, proxy_list: list[str] | None = None, ...), or (B) accept a single strongly-typed parameter of type _FetchPageCall (or a TypedDict named FetchPageParams) and update callers to build/pass that object; apply the same fix for the other affected functions/locations referenced (around the second and third occurrences noted) so callers get proper static typing and typos don’t silently pass.

These are comments left during a code review. Please review all issues and provide fixes.

1. logic error: Swallowing the crawl-run query error makes the metrics scrape succeed despite stale data.
   Path: backend/app/core/metrics.py
   Lines: 208-208

2. possible bug: Iterating config values directly can break when the source is a single-use iterable.
   Path: backend/app/services/acquisition/browser_detail.py
   Lines: 35-35

3. possible bug: The renamed `_prefetched_analysis` parameter is accepted but never used, so callers' precomputed `HtmlAnalysis` is ignored.
   Path: backend/app/services/acquisition/browser_page_flow.py
   Lines: 600-600

4. possible bug: Resetting counters by iterating the live dict is fragile if keys change.
   Path: backend/app/services/acquisition/browser_proxy_bridge.py
   Lines: 328-328

5. logic error: Narrowing the product attribute regex breaks detection of concatenated class tokens.
   Path: backend/app/services/acquisition/browser_readiness.py
   Lines: 50-50

6. logic error: Hard blocks now force browser-first routing for all block types once the threshold is reached.
   Path: backend/app/services/acquisition/host_protection_memory.py
   Lines: 315-315

7. logic error: Captcha pages can now be marked blocked even when the page still contains extractable content.
   Path: backend/app/services/acquisition/runtime.py
   Lines: 287-287

8. possible bug: Iterating over a non-materialized selector collection can exhaust it and break card counting.
   Path: backend/app/services/acquisition/traversal_card_counting.py
   Lines: 50-50

9. logic error: The new detail-image fallback can emit non-normalized placeholder URLs as `image_url`.
   Path: backend/app/services/adapters/amazon.py
   Lines: 225-225

Validate the correctness of each issue sequentially. For each issue that is correct, implement a fix. Please make the fixes concise and address all issues comprehensively and don't impact anything else.
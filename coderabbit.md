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
- `pending` `Ln 511`: ancestor-depth constants still need clearer naming or a precedence comment.
- `stale` `Ln 574-580`: `DETAIL_CURRENT_PRICE_SELECTORS` already uses `_STATIC_EXPORTS.get(...)`.
- `pending` `Ln 144`: unify duplicated noise-word definitions into one canonical collection.
- `fixed` `Ln 1618-1621`: `AMAZON_DETAIL_TABLE_IGNORED_LABELS` and `DETAIL_LONG_TEXT_LEADING_ATTRIBUTE_BLOB_PATTERN` added to exports.

## `backend/app/services/config/field_mappings.py`
- `pending` `Ln 50-57`: audit all `TITLE_STRUCTURED_VALUE_KEYS` consumers for list-valued `"values"` payloads.
- `fixed` `Ln 50-57`: reordered `TITLE_STRUCTURED_VALUE_KEYS` to prefer scalar keys before `"values"`.

## `backend/app/services/config/llm_runtime.py`
- `stale` `Ln 22-24`: default token pricing already includes `anthropic` and `nvidia`.

## `backend/app/services/config/runtime_settings.py`
- `pending` `Ln 110`: timeout buffer comments need one explicit throughput/backoff rationale; review comments conflict.
- `stale` `Ln 350`: `detail_max_variant_rows` is already back to `0` default.
- `pending` `Ln 351`: reject blank `host_memory_ttl_seconds_key`.
- `pending` `Ln 490-494`: `browser_navigation_networkidle_primary_budget_ratio` likely wants open-interval validation (`0 < x < 1`).

## `backend/app/services/extract/listing_card_fragments.py`
- `pending` `Ln 54-56`: narrow broad `except Exception` around selector evaluation.

## `backend/app/services/config/variant_policy.py`
- `pending` `Ln 46-48`: decide whether `upholstery_color` stays distinct; if yes, add British spelling alias.

## `backend/app/services/extract/variant_dom_provenance.py`
- `fixed` `Ln 161`: false-positive substring matching replaced with token-based selected-signal checks.

## `backend/app/services/extract/variant_group_validator.py`
- `pending` `Ln 13`: `variant_context_noise_tokens` is still computed in `variant_dom_cues.py`, not a pure config symbol.
- `fixed` `Ln 43-106`: hardcoded tunables and scope/source literals moved behind config-owned constants.
- `fixed` `Ln 111-120`: semantic container tokens moved to config and matched by token boundaries.

## `backend/app/services/extract/variant_normalization/contract.py`
- `pending` `Ln 147-148`: replace hardcoded `"body-mist"` URL token check with config-backed scent URL tokens or drop the URL heuristic.

## `backend/app/services/extract/variant_structural_pruning.py`
- `fixed` `Ln 22-29`: private cross-product token sets renamed with underscore prefix and removed from `__all__`.
- `fixed` `Ln 147-158`: malformed subset-pruning line repaired; file is syntactically valid again.
- `fixed` `Ln 287-290`: extracted parent price/currency signal check into helper for readability.

## `backend/app/services/extract/variant_value_guards.py`
- `fixed` `Ln 36-48`: removed duplicated word-count guard and moved color-axis constant to config.
- `fixed` `Ln 48-54`: moved variant URL field names to config.
- `fixed` `Ln 60-63`: `variant_url_is_product_like` now parses URL once instead of twice.
- `fixed` `Ln 99-101`: moved allowed URL schemes and product-detail path markers to config.

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

## `backend/app/services/listing_extractor.py`
- `stale` `Ln 63`: `currency_hint_from_page_url` is imported from `detail.price.core`, not a misplaced `detail_price_extractor` module.

## `backend/app/services/normalizers/__init__.py`
- `stale` `Ln 183-185`: falsy availability mappings are not skipped; code already checks `is not None`.

## `backend/app/services/product_intelligence/service.py`
- `stale` `Ln 182-183`: admin role already uses `ADMIN_ROLE`.
- `stale` `Ln 437-439`: flush is outside the source loop, so no N+1 flush pattern exists there now.

## `backend/app/services/review/__init__.py`
- `fixed` `Ln 37-38`: consolidated SQLAlchemy imports.
- `fixed` `Ln 227-238`: removed unused `_serialize_record`.
- `fixed` `Ln 327-329`: removed redundant `.keys()` call.
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

## `coderabbit.md`
- `fixed` `Ln 1-2`: merged the repeated prose sections into one file-grouped backlog with status tags.

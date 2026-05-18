Fix the following issues. The issues can be from different files or can overlap on same lines in one file.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/variant_normalization/backfill.py around lines 152 - 170, The comparison treats ints/floats as numeric and everything else via text_or_none which makes "10.00" and 10 compare unequal; update the logic in _comparable_scalar (used by _has_distinct_variant_value) to normalize numeric-like strings to a numeric type before returning so semantically-equal prices compare equal: attempt to parse string values to a Decimal (or numeric) and return that for numeric inputs (keep ints/floats converted to Decimal for consistent typing), otherwise fall back to text_or_none; ensure fallback_fields and variants still handle None/empty via _value_present and that parsing failures fall back to the original text behavior.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/ucp_audit/agent_delta.py at line 79, Replace the explicit "del url" removal with a Pythonic unused-parameter convention: rename the function parameter "url" to "_url" in the function/method signature where "del url" appears; if you cannot change the signature, remove "del url" and use "_ = url" or append a "# noqa" comment to the parameter to silence linters instead. Ensure you update any references to "url" in that function to use the preserved name (or leave them absent if truly unused).

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/ucp_audit/compliance_checks.py around lines 85 - 89, The metric_count is effectively hardcoded because metrics = (collapsed, sku, availability) always has length 3; update the calculation to count only active (non-zero) metrics so the denominator adapts when metrics change: replace metric_count = len(metrics) with something like counting non-zero entries (e.g., metric_count = sum(1 for m in metrics if m > 0)) in the function in compliance_checks.py that computes the score (the block using variables collapsed, sku, availability and returning int(100 - ...)), and ensure you handle the zero-metric case by returning 100 as the existing guard intended.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/ucp_audit/discovery.py around lines 66 - 82, The bare except in _fetch_manifest_page swallows all errors; update it to catch and handle specific errors (e.g., httpx.HTTPError / build_async_http_client's client exceptions, asyncio.TimeoutError, socket.gaierror) rather than Exception, log the caught exception via the module logger, and/or include an error field in the returned SimpleNamespace (e.g., error=str(exc)) so callers can differentiate network/timeouts/DNS failures; ensure the try/except surrounds the async request and use the function name _fetch_manifest_page and the SimpleNamespace return shape when making these changes.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/ucp_audit/reporting.py around lines 11 - 14, The escape_markdown function currently escapes every char in _MARKDOWN_SPECIAL_CHARS (including '.' and '-') which harms readability for URLs and IDs; update escape_markdown(value: object, safe_chars: Optional[Iterable[str]] = None or mode: Literal['full','selective']='full') to allow a selective escape mode or a configurable set of characters (defaulting to the existing full set) and in selective mode exclude '.' and '-' (and any other safe chars), keep the function name escape_markdown and the existing behavior when defaulting to full, and update call sites that render URLs/audit IDs to call escape_markdown(..., mode='selective') or pass a safe_chars set so only critical markdown chars like '*', '_', '`', '~', '#', '[' etc. are escaped.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/ucp_audit/service.py around lines 645 - 664, The current broad try/except around build_agent_view_delta/_best_agent_delta_url swallows all exceptions; narrow it to catch only expected operational errors (e.g., network/timeouts/HTTP/client errors) such as aiohttp.ClientError, asyncio.TimeoutError, requests.exceptions.RequestException or similar used elsewhere in your codebase, log the exception (using logger.debug with exc_info=True) and return the fallback UCPFinding as now, and let any other unexpected exceptions propagate (or re-raise them) so programming bugs surface; update imports as needed and keep the fallback return logic inside the specific-exception handler that references build_agent_view_delta, _best_agent_delta_url, logger, _dimension, UCPFinding and config.D_UCP7_ID.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/ucp_audit/service.py around lines 358 - 360, The bare except in the UCP audit fetch block masks programming errors; update the handler in the function performing the UCP audit fetch so it only catches network/HTTP/timeouts (e.g., catch httpx.RequestError, httpx.HTTPStatusError and asyncio.TimeoutError) and leave other exceptions to propagate; import httpx (and asyncio if needed), bind the exception (e) and keep the logger.debug("UCP audit fetch failed for %s", url, exc_info=True) behavior, return None for these expected failures, and do not use a bare except Exception so AttributeError/TypeError/etc. are not swallowed.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/tests/services/test_normalizers.py around lines 183 - 197, Add a new unit test that verifies numeric and string prices that are semantically equal are treated as equivalent by the backfill, e.g. create a test function (suggested name: test_variant_price_backfill_handles_numeric_string_equivalence) that builds a record with parent "price" set to "10.00" and a variant with numeric price 10.0 plus a variant missing price, calls backfill._backfill_variant_context(record), and asserts the missing-price variant is backfilled while the numeric-10.0 variant is not; this ensures _backfill_variant_context treats 10.0 and "10.00" as equal instead of differing by type.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/tests/services/test_selectolax_css_migration.py around lines 958 - 973, Update the test to expect the new "fail closed" behavior when crawler_runtime_settings.selector_regex_timeout_seconds is invalid: instead of asserting successful extraction, assert that calling extract_selector_value (the function under test) raises the appropriate error (e.g., ValueError/RuntimeError/TimeoutError) indicating invalid timeout configuration or refusal to run without a valid timeout; locate the change around the test function test_xpath_regex_invalid_timeout_falls_back_without_timeout and reference the runtime config key selector_regex_timeout_seconds and the implementation in xpath_service.py to ensure the test matches the new failure mode.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/tests/services/ucp_audit/test_agent_delta.py around lines 65 - 97, Rename the test function test_agent_view_extracts_structured_values_not_booleans to a clearer name like test_agent_view_extracts_product_group_variants (or alternatively keep the name and add explicit assertions that boolean-valued keys are not present in the result), and update any references; locate the test function in backend/tests/services/ucp_audit/test_agent_delta.py and change the def name accordingly or add assert statements that boolean fields are absent from the extract_agent_view output (e.g., assert "someBooleanField" not in result) to match the original intent.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @frontend/app/ucp-audit/ucp-audit-components.tsx around lines 589 - 610, The current UcpFixSequence uses a shared storageKey when report?.job_id is null causing cross-report collisions; modify UcpFixSequence so that storage persistence is only used when a valid report.job_id exists: compute storageKey only if report?.job_id is truthy (e.g., const storageKey = report?.job_id ? `ucp-fix-sequence-${report.job_id}` : null), update the useState initializer to avoid reading localStorage when storageKey is null or window is undefined, and guard the toggle function so it updates localStorage only when storageKey is non-null (still updating React state unconditionally); keep function names (UcpFixSequence, toggle) and the done state logic intact.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @frontend/app/ucp-audit/ucp-audit-components.tsx around lines 612 - 627, The exportPlan function currently falls back to a generic filename via anchor.download = `ucp-repair-roadmap-${report?.job_id ?? 'run'}.md`; change this to build a more descriptive fallback (e.g., use report.job_id if present, else report.domain if present, else a timestamp) and sanitize the chosen value before interpolating; update the anchor.download assignment in exportPlan to use that computed filenameBase (for example: `ucp-repair-roadmap-${filenameBase}.md`) so exports are uniquely identifiable when report or report.job_id is missing.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @frontend/components/ui/patterns.tsx around lines 61 - 63, The useLayoutEffect currently lists actions in its dependency array unnecessarily; remove actions from the array so it becomes [pathname, signature] — keep useLayoutEffect(() => { syncHeader(); }, [pathname, signature]) so that signature (which already tracks actions) and useEffectEvent-provided syncHeader capture the latest actions without redundant runs; update the dependency list where useLayoutEffect is defined and ensure syncHeader and signature names are unchanged.

These are comments left during a code review. Please review all issues and provide fixes.

1. possible bug: Hardcoded UCP audit table names may not match model mappings.
   Path: backend/app/services/dashboard_service.py
   Lines: 355-355

2. possible bug: Policy findings are tagged with a new count kind that downstream consumers may not interpret correctly.
   Path: backend/app/services/ucp_audit/compliance_checks.py
   Lines: 125-125

3. logic error: Missing schema fields are now undercounted because pages without product JSON-LD are excluded from those findings.
   Path: backend/app/services/ucp_audit/service.py
   Lines: 485-485

4. possible bug: The review note in coderabbit.md points to a numeric/string comparison issue in backfill.py, but the repo evidence does not show an actionable code bug in the final file state.
   Path: coderabbit.md
   Lines: 5-5

5. logic error: The new JSON-only path in `ViewColumn` should not be used for non-JSON samples.
   Path: frontend/app/ucp-audit/ucp-audit-components.tsx
   Lines: 1042-1042

Validate the correctness of each issue sequentially. For each issue that is correct, implement a fix. Please make the fixes concise and address all issues comprehensively and don't impact anything else.
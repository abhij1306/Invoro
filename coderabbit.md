Full pytest tests -q still not green because existing structure ratchets fail:

browser_runtime.py LOC over budget
legacy_inprocess_runner_enabled still present
two existing service-level config constants outside config

These are comments left during a code review. Please review all issues and provide fixes.

1. possible bug: Tightening route patterns to `/{run_id:int}` may change request matching behavior.
   Path: backend/app/api/crawl_domain.py
   Lines: 190-190

2. possible bug: Accessibility-based detail expansion now crashes because the callback signature no longer matches its caller.
   Path: backend/app/services/acquisition/browser_runtime.py
   Lines: 233-233

3. logic error: _sync_browser_pool_compatibility() no longer rebinds `_browser_pool._BROWSER_POOL`, potentially splitting runtime state.
   Path: backend/app/services/acquisition/browser_runtime.py
   Lines: 133-133

4. possible bug: The new DOM-content helper can silently misclassify non-HTML inputs by stringifying them as markup.
   Path: backend/app/services/acquisition/runtime.py
   Lines: 844-844

5. logic error: Replacing direct fallback capture with a deduplicating helper can drop the only HTML fragment.
   Path: backend/app/services/acquisition/traversal.py
   Lines: 236-236

6. logic error: Saved root aliases can be merged into fetch_profile in a way that changes precedence.
   Path: backend/app/services/crawl/profile/merge.py
   Lines: 101-101

7. logic error: The legacy artifacts cleanup points at the wrong directory and will miss old files.
   Path: backend/app/services/dashboard_service.py
   Lines: 223-223

8. possible bug: The new `run_job` wrapper requires a keyword-only `llm_enabled` argument, but existing internal callers still use the old positional form.
   Path: backend/app/services/data_enrichment/service.py
   Lines: 262-262

9. race condition: Per-call mutation of shared browser helper state creates a thread-safety race.
   Path: backend/app/services/acquisition/browser_page_flow.py
   Lines: 50-50

10. race condition: Repeated runtime compatibility rewiring mutates shared module state unnecessarily.
   Path: backend/app/services/acquisition/browser_runtime.py
   Lines: 145-145

11. logic error: Zero values are incorrectly replaced by the default during integer conversion.
   Path: backend/app/services/acquisition/browser_page_helpers.py
   Lines: 40-40

12. possible bug: Accessing a private asyncio loop attribute makes shutdown logic brittle.
   Path: backend/app/services/acquisition/browser_pool.py
   Lines: 757-757

13. possible bug: Private helpers are accidentally exposed as public API.
   Path: backend/app/services/extract/detail_materializer.py
   Lines: 68-68

14. race condition: Repeated patchpoint syncing mutates shared implementation state on every call.
   Path: backend/app/services/extract/detail_materializer.py
   Lines: 34-34

15. code quality: Wildcard import hides the explicit public API.
   Path: backend/app/services/extract/detail_price_extractor.py
   Lines: 9-9

16. code quality: Private variant shim names are included in __all__ unnecessarily.
   Path: backend/app/services/extract/shared_variant_logic.py
   Lines: 47-47

17. code quality: Missing exports keep public aliases out of from-import-star.
   Path: backend/app/services/pipeline/extraction_loop.py
   Lines: 613-613

18. code quality: Typo in test function name.
   Path: backend/tests/services/test_data_enrichment.py
   Lines: 398-398

19. code quality: Docstring references an outdated module name.
   Path: backend/tests/services/test_extraction_runtime_listing_integrity.py
   Lines: 1-1

20. code quality: Test function names do not follow the preferred style.
   Path: backend/tests/services/test_health_api.py
   Lines: 111-111

21. code quality: Misnamed pytest functions use `testlooks_*` instead of `test_*`.
   Path: backend/tests/services/test_network_payload_mapper.py
   Lines: 386-386

22. code quality: Misnamed async tests omit the underscore after `test`.
   Path: backend/tests/services/test_product_intelligence.py
   Lines: 306-306

23. code quality: Missing underscore in test function name.
   Path: backend/tests/test_main.py
   Lines: 85-85

24. code quality: Test function name missing underscore after `test`.
   Path: backend/tests/services/test_shared_url_utils.py
   Lines: 26-26

25. code quality: Test function name missing underscore after `test`.
   Path: backend/tests/services/test_shared_coerce_primitives.py
   Lines: 21-21

26. code quality: Test function name missing underscore after `test`.
   Path: backend/tests/services/test_selectors_runtime.py
   Lines: 158-158

Validate the correctness of each issue sequentially. For each issue that is correct, implement a fix. Please make the fixes concise and address all issues comprehensively and don't impact anything else.

Fix the following issues. The issues can be from different files or can overlap on same lines in one file.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/core/config.py at line 43, Add an inline comment above the configuration field legacy_inprocess_runner_enabled explaining its purpose: that it toggles use of the older in-process task runner implementation versus the newer runner, when to enable it (e.g., for backward compatibility or debugging with legacy behavior), and that it defaults to False; update the comment near the legacy_inprocess_runner_enabled declaration so future readers know the behavior, impact, and recommended usage.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/crawl/profile/merge.py around lines 144 - 150, The fetch_root_aliases dict in merge.py contains redundant identity mappings (e.g. "request_delay_ms": "request_delay_ms", "max_pages": "max_pages", "max_scrolls": "max_scrolls") which are unnecessary because the lookup uses root_aliases.get(root_key, root_key); remove those identity entries from fetch_root_aliases and keep only the non-identity aliases (e.g. "advanced_mode": "traversal_mode", "sleep_ms": "request_delay_ms") so behavior remains identical but the mapping is clearer.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/data_enrichment/deterministic.py around lines 46 - 50, The regex price_range_re doesn't consume trailing currency/unit text, so when the caller uses fullmatch the string must end right after the second numeric group and strings like "$10 - $20 USD" fail; update price_range_re to allow optional trailing non-numeric/unit text after the second capture (e.g., permit optional whitespace plus currency/unit characters and anchor to the end) so fullmatch will succeed — locate the price_range_re definition and broaden the pattern after the second numeric group to consume trailing currency/unit tokens before the end of string.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/extract/detail_identity.py around lines 59 - 60, The module-level __getattr__ currently forwards any undefined attribute to _core which can mask typos; update __getattr__ to validate names before delegating (e.g., maintain an explicit whitelist/tuple of allowed attribute names or check hasattr(_core, name)) and raise AttributeError for unknown names, or document/keep the current behavior if intentional; target the __getattr__ function and the _core delegation to implement this validation/whitelist.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/pipeline/sitemap.py around lines 25 - 28, The except block that swallows all exceptions after ET.fromstring(raw) should log the caught exception before returning []; update the handler to "except Exception as e:" and call a logger (e.g., logging.exception(...) or logger.exception(...)) with a clear message referencing ET.fromstring and the raw input context, then return [] as before; ensure logging is imported/available in sitemap.py and use the existing module logger if one exists.
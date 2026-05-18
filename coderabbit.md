These are comments left during a code review. Please review all issues and provide fixes.

1. possible bug: Importing the currency hint helper from the new module path can break module loading if that path is not actually packaged.
   Path: backend/app/services/data_enrichment/deterministic.py
   Lines: 34-34

2. possible bug: Changing the XPath helper import path can break callers that depend on the shared service location.
   Path: backend/app/services/dom/selector_engine.py
   Lines: 80-80

3. possible bug: Re-exporting a new cleanup helper at the package root can silently change the public API contract.
   Path: backend/app/services/extract/detail/__init__.py
   Lines: 3-3

4. logic error: Generic page images can incorrectly force DOM completion on detail pages.
   Path: backend/app/services/extract/detail/assembly/dom_completion.py
   Lines: 220-220

5. logic error: Inconsistent category normalization can cause false positives for DOM completion.
   Path: backend/app/services/extract/detail/assembly/dom_completion.py
   Lines: 203-203

6. logic error: The title fallback can still resurrect an incorrect product title after pruning.
   Path: backend/app/services/extract/detail/assembly/dom_fallbacks.py
   Lines: 79-79

7. logic error: The DOM selection helper can return the wrong tree and make detail extraction miss content.
   Path: backend/app/services/extract/detail/assembly/dom_section_targets.py
   Lines: 69-69

8. logic error: Availability is defaulted to unknown even when callers may expect it to stay unset.
   Path: backend/app/services/extract/detail/assembly/final_cleanup.py
   Lines: 144-144

Validate the correctness of each issue sequentially. For each issue that is correct, implement a fix. Please make the fixes concise and address all issues comprehensively and don't impact anything else.
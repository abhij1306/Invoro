These are comments left during a code review. Please review all issues and provide fixes.

1. logic error: Legitimate root/category labels can be collapsed into an incorrect generic gender category.
   Path: backend/app/services/extract/detail/assembly/record_sanitization.py
   Lines: 302-302

2. logic error: A weaker DOM-derived currency can overwrite a correct structured currency and corrupt downstream price reconciliation.
   Path: backend/app/services/extract/detail/price/core.py
   Lines: 91-91

3. logic error: The added early return disables trimming for materials strings that still need cleanup.
   Path: backend/app/services/extract/detail/text/sanitizer.py
   Lines: 807-807

4. logic error: Path-only URL parsing can prevent cross-product variants from being pruned.
   Path: backend/app/services/extract/variant_structural_pruning.py
   Lines: 128-128

5. logic error: Dictionary-shaped decimal values can now be discarded even when they still contain valid price data.
   Path: backend/app/services/normalizers/__init__.py
   Lines: 98-98

6. logic error: Using GTIN in place of the MPN for brand+title searches can return the wrong product variant.
   Path: backend/app/services/product_intelligence/discovery.py
   Lines: 138-138

7. logic error: A variant parsing false positive can override an exact identifier match and block valid matches.
   Path: backend/app/services/product_intelligence/matching.py
   Lines: 149-149

Validate the correctness of each issue sequentially. For each issue that is correct, implement a fix. Please make the fixes concise and address all issues comprehensively and don't impact anything else.
These are comments left during a code review. Please review all issues and provide fixes.

1. logic error: Advertising `auto` as supported without a default-field mapping breaks downstream surface handling.
   Path: backend/app/services/config/public_api.py
   Lines: 84-84

2. logic error: The HTML-based bypass can send non-extractable browser results through extraction and break the existing gate.
   Path: backend/app/services/pipeline/record_extraction_stage.py
   Lines: 54-54

3. logic error: Skipping the detail rejection guard for certain detail surfaces can let invalid extractions be treated as successful.
   Path: backend/app/services/pipeline/retry/stage.py
   Lines: 262-262

1. logic error: Hiding the markdown field causes serialized crawl records to lose content that callers may still rely on.
   Path: backend/app/schemas/crawl.py
   Lines: 21-21

2. possible bug: Advertised public surfaces do not have matching default-field mappings.
   Path: backend/app/services/config/public_api.py
   Lines: 37-37

3. logic error: Public presentation fields are stripped from exported data, causing incomplete output.
   Path: backend/app/services/export/schema.py
   Lines: 165-165

4. logic error: Some mixed-content containers can lose markdown structure or flatten content incorrectly.
   Path: backend/app/services/extract/content_surface_extractor.py
   Lines: 299-299

5. logic error: Content-detail extraction skips the normal detail record cleanup pipeline.
   Path: backend/app/services/pipeline/extract_records.py
   Lines: 100-100

6. possible bug: Short content pages can be dropped entirely by the new blocked-page heuristic.
   Path: backend/app/services/pipeline/extract_records.py
   Lines: 108-108

7. logic error: A new whitelist check can skip detail rejection handling and leave failed extractions unmarked.
   Path: backend/app/services/pipeline/retry/stage.py
   Lines: 262-262

Validate the correctness of each issue sequentially. For each issue that is correct, implement a fix. Please make the fixes concise and address all issues comprehensively and don't impact anything else.
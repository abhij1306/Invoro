Fix the following issues. The issues can be from different files or can overlap on same lines in one file.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/alembic/versions/20260528_0008_playground_sessions.py at line 35, The migration sets onupdate=sa.func.now() for the updated_at column, but onupdate is an ORM-level behavior and won't create a DB trigger; either add explicit DDL in the migration to create a PostgreSQL trigger/function that sets updated_at on UPDATE (create a plpgsql function and attach it to the table in the migration) or update the migration comment/docs to state that updated_at relies on ORM-level onupdate (as in the Playground model's updated_at definition) and direct SQL updates will not auto-update the timestamp; implement one of these two approaches and ensure the migration includes the trigger creation SQL if you choose the DB-level solution.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/playground_service.py around lines 603 - 606, The loop that calls await session.get(CrawlRun, rid) for each rid causes N+1 queries; replace it with a single bulk fetch using a query like select(CrawlRun).where(CrawlRun.id.in_(run_ids)) (via session.execute or session.scalars) to load all matching CrawlRun rows at once, build a mapping from CrawlRun.id to CrawlRun.status, and then populate the statuses list using that mapping in the original run_ids order (skipping missing ids) so behavior of variables run_ids, session, CrawlRun, and statuses is preserved while eliminating per-id queries.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/playground_service.py around lines 257 - 262, The code currently normalizes URL strings into normalized_urls and unique_urls but does not validate their format; update the logic in the function that builds normalized_urls (referencing normalized_urls, unique_urls, and MAX_PRODUCTS) to validate each URL with urllib.parse.urlparse (or an equivalent validator) ensuring scheme in ('http','https') and a non-empty netloc, filter out or collect invalid entries before enforcing MAX_PRODUCTS, and raise a ValueError listing invalid or missing URLs if any are found so downstream crawl creation receives only well-formed HTTP(S) URLs.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @frontend/lib/api/index.ts around lines 360 - 364, The payload type for playgroundSelectCategory allows both url and urls to be omitted; create a discriminated union type (e.g. PlaygroundSelectCategoryPayload = { url: string } | { urls: string[] } | { url: string; urls: string[] }) and update the playgroundSelectCategory signature to use it so callers must provide at least one of url or urls, and add a short runtime guard in the caller (or in the function) that throws or rejects when both are missing to double-check at runtime before calling apiClient.post.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @backend/app/services/fetch/types.py at line 20, The type for the on_event field was widened to Any | None which disables type checking; change it back to a more specific type—either object | None if it can be any non-callable value, or preferably a Callable with the correct signature (e.g., Callable[[EventType], None] | None) if it is an event handler—so update the on_event annotation in types.py (both occurrences around the on_event declaration and the duplicate at the later occurrence) to the appropriate specific type to restore type safety and provide clear expectations for callers.

- Verify each finding against current code. Fix only still-valid issues, skip the rest with a brief reason, keep changes minimal, and validate.

In @frontend/components/crawl/markdown-output.tsx around lines 278 - 284, The fenced-code parsing loop in markdown-output.tsx stops at the line cap but leaves the rest of the fenced block unconsumed (and the current condition uses (index - startIndex) which yields one-off capturing 499 of 500 lines); update the inner while condition to use code.length < maxCodeLines instead of (index - startIndex) < maxCodeLines to correctly enforce the cap, and after filling/truncating the code buffer advance index forward in a second loop until you hit the closing fence (lines[index].trim().startsWith('```')) so the parser consumes the remainder of the fenced block before resuming normal parsing, then consume the closing fence as before.

These are comments left during a code review. Please review all issues and provide fixes.

1. logic error: The URL limit is not actually enforced, so oversized selections can slip through.
   Path: backend/app/schemas/playground.py
   Lines: 15-15

2. logic error: Downstream enrichment and compare jobs are created but never executed.
   Path: backend/app/services/playground_service.py
   Lines: 220-220

3. type error: Monitor branch passes an AlertCreate payload with unsupported `urls` data.
   Path: backend/app/services/playground_service.py
   Lines: 257-257

4. logic error: Pipeline completion ignores the monitor branch and can finish too early.
   Path: backend/app/services/playground_service.py
   Lines: 367-367

5. race condition: Extraction is triggered before product selection has finished saving, causing a race condition.
   Path: frontend/app/playground/page.tsx
   Lines: 280-280

6. race condition: Discovery can be triggered multiple times because the effect uses a stale pending flag.
   Path: frontend/app/playground/page.tsx
   Lines: 203-203

7. type error: The page assumes a fixed `step_data` shape that can hide real data when the backend schema differs.
   Path: frontend/app/playground/page.tsx
   Lines: 213-213

Validate the correctness of each issue sequentially. For each issue that is correct, implement a fix. Please make the fixes concise and address all issues comprehensively and don't impact anything else.
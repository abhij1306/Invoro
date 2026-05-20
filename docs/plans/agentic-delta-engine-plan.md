# Plan: Agentic Delta Engine

**Created:** 2026-05-20
**Agent:** Codex
**Status:** BLOCKED — implementation complete; full backend verify has unrelated pre-existing failures
**Touches buckets:** API + Bootstrap, Crawl Ingestion + Orchestration, Config, Frontend, Docs

## Goal

Build Delta Engine by extending the existing monitor subsystem, not creating a parallel watch engine. Done means users and agents can create single-URL ecommerce watches, poll every 60s+, detect field deltas, evaluate simple conditions, send webhook payloads, inspect history/delivery logs, and manage watches through UI, `/api/v1/watches`, and MCP tools.

## Acceptance Criteria

- [x] Users can create single-URL ecommerce watches with target fields, optional condition, webhook URL, and poll interval.
- [x] Watch creation runs an immediate first poll and populates `last_known_values`.
- [x] Scheduled watch polling reuses normal crawl primitives and never adds monitor-specific extraction logic inside the pipeline.
- [x] Field deltas are stored whether or not the condition is met.
- [x] Conditions support `<`, `>`, `<=`, `>=`, `==`, `!=`, and `AND` for `price` and `availability` only.
- [x] Webhook deliveries are logged with attempts, response status/error, and payload preview.
- [x] Console watch routes and public `/api/v1/watches` routes work with auth.
- [x] Monitors UI supports watch creation, list, detail, test, pause/resume, delete, history, and delivery log.
- [x] MCP stdio tools wrap public watch APIs without owning business logic.
- [ ] `python -m pytest tests -q` exits 0.

## Do Not Touch

- `detail_extractor.py`, `listing_extractor.py`, and extraction ranking modules — Delta Engine consumes normal extracted fields.
- `pipeline/*` bodies except the existing run-complete callback path — monitor logic must stay callback-owned.
- `publish/*` and exports — no downstream extraction repair.
- Hosted MCP/SSE and extraction API tools — out of this plan.

## Slices

### Slice 1: Plan Activation
**Status:** DONE
**Files:** `docs/plans/agentic-delta-engine-plan.md`, `docs/plans/ACTIVE.md`
**What:** Save this plan and update ACTIVE to point here.
**Verify:** Plan file exists and ACTIVE points to `docs/plans/agentic-delta-engine-plan.md`.

### Slice 2: Backend Model + Config
**Status:** DONE
**Files:** monitor models/schemas/config and Alembic migration
**What:** Extend `MonitorJob` for watch fields/statuses, add webhook delivery persistence, and add minimal API key model/dependency support.
**Verify:** model imports and migration upgrade/downgrade compile.

### Slice 3: Condition + Webhook Services
**Status:** DONE
**Files:** monitor condition/webhook services and change detection
**What:** Add safe condition evaluator, webhook payload assembly, retry delivery logging, and hook it into monitor change detection.
**Verify:** focused unit tests for condition truth/failures and delivery logging.

### Slice 4: Watch CRUD + Polling
**Status:** DONE
**Files:** watch service/API/schemas and scheduler
**What:** Add console watch APIs over `MonitorJob`, immediate first/test poll, 60s scheduler handling, and no schedule drift on test.
**Verify:** watch API tests pass.

### Slice 5: Public API + MCP
**Status:** DONE
**Files:** `/api/v1/watches`, API-key dependency, MCP stdio wrapper
**What:** Add public watch envelope endpoints and MCP tools: `watch_product`, `get_watch_status`, `cancel_watch`, `list_watches`.
**Verify:** public API and MCP contract tests pass.

### Slice 6: Frontend
**Status:** DONE
**Files:** monitor API types/client and monitor UI components
**What:** Update Monitors UI for watch form/list/detail semantics while keeping old monitor rows readable.
**Verify:** `npm run lint`, `npm test`.

### Slice 7: Docs + Full Verify
**Status:** BLOCKED
**Files:** architecture/codebase docs
**What:** Update canonical docs and run focused then full verification.
**Verify:** backend focused tests and `python -m pytest tests -q`.

## Doc Updates Required

- [x] `docs/backend-architecture.md` — Delta Engine watch/API/MCP behavior.
- [x] `docs/frontend-architecture.md` — monitor UI watch controls.
- [x] `docs/CODEBASE_MAP.md` — new files/models/routes.
- [x] `docs/BUSINESS_LOGIC.md` — watch scheduling/webhook decision rules.

## Notes

- Existing active plan was `DONE`, so this plan is allowed to become active.
- Existing `MonitorJob` remains canonical owner. No separate `Watch` table.
- Focused backend verify passed: `pytest tests\services\test_agentic_delta_engine.py tests\services\test_monitoring_pipeline.py tests\services\test_monitors_api_e2e.py -q` → 14 passed.
- Frontend verify passed: `npm run lint`; `npm test` → 93 passed.
- Full backend verify ran on 2026-05-20: `pytest tests -q` → 1832 passed, 16 skipped, 3 failed. Failures are outside Delta Engine files: footer document asset row rejection, pre-existing LOC budgets, and pre-existing private test import drift.

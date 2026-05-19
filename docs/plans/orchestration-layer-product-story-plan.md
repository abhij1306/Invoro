# Plan: Orchestration Layer And Product Story

**Created:** 2026-05-19
**Agent:** Codex
**Status:** IN PROGRESS
**Touches buckets:** API, models, schemas, crawl orchestration, monitor orchestration, frontend API, frontend project UX, docs

## Goal

Build the MVP orchestration layer for Competitive Pricing Snapshot. Done means business users can create a Project, launch a template-backed listing-to-detail workflow, see workflow status and price comparison results, promote the workflow to an existing monitor, and access the underlying Crawl Studio run IDs. The layer sequences existing crawl and monitor APIs only; it does not add extraction logic.

## Acceptance Criteria

- [x] `docs/plans/ACTIVE.md` points here and old plan state is preserved as previous work.
- [x] Backend exposes `/api/orchestration/projects`, `/api/orchestration/templates`, `/api/orchestration/workflows`, workflow status, promote, and results endpoints.
- [x] Workflow execution creates normal `CrawlRun` rows for listing and detail steps; detail starts after listing completion from discovered record URLs.
- [x] Promote creates a normal `MonitorJob` from completed workflow detail URLs and tracked fields.
- [x] Frontend has Projects nav, project wizard for UC-1, overview/status view, price comparison table, export links, and Crawl Studio links.
- [x] Orchestration docs and codebase map mention new owners.
- [x] Targeted backend and frontend tests pass.

## Do Not Touch

- `backend/app/services/pipeline/*` - orchestration must not change extraction.
- `backend/app/services/extract/*` - no new extractor or downstream compensator.
- `backend/app/services/llm/*` - NL intent is post-MVP.

## Slices

### Slice 1: Plan And Ownership
**Status:** DONE
**Files:** `docs/plans/ACTIVE.md`, `docs/plans/orchestration-layer-product-story-plan.md`
**What:** Save active plan and scope MVP against repo owners.
**Verify:** Plan files exist and active pointer is correct.

### Slice 2: Backend Models And Template Config
**Status:** DONE
**Files:** `backend/app/models/orchestration.py`, `backend/app/models/__init__.py`, `backend/app/services/config/orchestration_templates.py`, Alembic migration
**What:** Add thin Project/WorkflowRun/WorkflowStepRun shells and static versioned UC-1 template config.
**Verify:** metadata includes tables; migration imports cleanly.

### Slice 3: Backend Service And API
**Status:** DONE
**Files:** `backend/app/schemas/orchestration.py`, `backend/app/services/orchestration_service.py`, `backend/app/api/orchestration.py`, `backend/app/main.py`
**What:** Create projects, list/get templates, create workflows, advance workflow on status polling, promote to monitor, and return price comparison rows.
**Verify:** API/service tests pass.

### Slice 4: Frontend Project UX
**Status:** DONE
**Files:** `frontend/lib/api/types.ts`, `frontend/lib/api/index.ts`, `frontend/components/layout/app-shell.tsx`, `frontend/app/projects/*`
**What:** Add Projects navigation, UC-1 wizard, project detail/status/results, export/Crawl Studio links.
**Verify:** frontend tests/lint for touched surface.

### Slice 5: Docs And Broad Verify
**Status:** DONE
**Files:** `docs/CODEBASE_MAP.md`, `docs/backend-architecture.md`, `docs/frontend-architecture.md`, this plan
**What:** Document orchestration owners and mark plan done after verification.
**Verify:** smallest relevant backend tests, frontend tests/lint, and plan acceptance checked.

## Doc Updates Required

- [x] `docs/backend-architecture.md` - new orchestration API/model/service.
- [x] `docs/frontend-architecture.md` - Projects routes and frontend API usage.
- [x] `docs/CODEBASE_MAP.md` - new backend/frontend ownership.
- [x] `docs/INVARIANTS.md` - orchestration contract.

## Notes

- User explicitly assigned new plan even though prior `ACTIVE.md` still said IN PROGRESS. Preserving old plan under Previous.
- MVP deliberately excludes NL intent endpoint, other templates, new extraction, new monitor system, and LLM pipeline changes.
- Slice 2 verified by `py_compile` and model metadata check for all three orchestration tables.
- Slice 3 verified by `pytest tests/test_main.py tests/services/test_orchestration_service.py -q`.
- Slice 4 verified by `npm run lint` and `npm run build`.
- Broad `pytest tests/services/test_structure.py -q` still has pre-existing guard failures in `extract/detail/identity/core.py` LOC and private import drift outside this slice.

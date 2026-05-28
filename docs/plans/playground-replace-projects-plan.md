# Plan: Playground — Replace Projects Feature

**Created:** 2026-05-28
**Agent:** Opus
**Status:** IN PROGRESS
**Touches buckets:** frontend/app/projects, frontend/app/playground, frontend/lib/api, frontend/components/layout, backend/app/api/orchestration, backend/app/api/playground, backend/app/services/orchestration_service, backend/app/services/config/orchestration_templates, backend/app/models/orchestration, backend/app/schemas/orchestration, backend/tests/component/test_orchestration_service, frontend/e2e/projects.spec.ts

## Goal

Remove the dead orchestration/projects feature and replace it with a Playground — a guided pipeline page for non-technical users. Paste a URL, the system discovers what's there, the user picks what to extract, and then selects which downstream APIs to run (enrich, compare, monitor, audit). No selectors, no traversal config, no batch — just simple progressive orchestration of existing capabilities from one place.

## Design Constraints

- **Non-technical users.** No selector editing, no surface pickers, no traversal mode toggles.
- **Single starting URL.** One session = one domain entry point expanding to discovered products.
- **Limited scale.** Max ~50 products per session. Larger = "use Crawl Studio."
- **No new extraction logic.** Playground coordinates existing services only.
- **Dependency-aware parallelism:**
  - Audit → runs immediately on input URL (independent)
  - Discover → Extract PDPs → then Enrich / Compare / Monitor can run in parallel
  - Enrich, Compare, Monitor all depend on PDP extraction data

## Dependency Graph

```
Input URL
  │
  ├──────────────────────────────────── Audit (independent, fires immediately)
  │
  ├── Discover (listing/category crawl)
  │       │
  │   [User picks products, max 50]
  │       │
  ├── Extract PDPs (detail crawl)
  │       │
  │       ├── Enrich (parallel, needs PDP data)
  │       ├── Compare / PI (parallel, needs PDP data)
  │       └── Monitor (parallel, needs PDP URLs)
  │
  └── Results (unified view of all completed steps)
```

## Acceptance Criteria

- [ ] All orchestration/projects backend code deleted
- [ ] Alembic migration drops orchestration tables
- [ ] All frontend projects pages + e2e deleted
- [ ] Nav updated: "Projects" → "Playground"
- [ ] Backend: `/api/playground/sessions` CRUD + advance endpoint with state machine
- [ ] Frontend: `/playground` page with guided stepper UI
- [ ] Step 1 (Discover): paste URL → auto-crawl listing → show discovered products
- [ ] Step 2 (Select): user picks up to 50 products from discovered list
- [ ] Step 3 (Extract): crawl selected PDPs → show extracted data
- [ ] Step 4 (Pipeline): checkboxes for Enrich / Compare / Monitor / Audit → run selected in parallel where possible
- [ ] Step 5 (Results): unified results view with export option
- [ ] Audit can be kicked off from Step 1 (doesn't need PDP data)
- [ ] `python -m pytest tests -q` exits 0

## Do Not Touch

- `backend/alembic/versions/20260519_0005_orchestration.py` — historical, keep
- `docs/archive/plans/orchestration-layer-product-story-plan.md` — historical
- Existing crawl/monitor/alert/PI/enrichment/audit services — consumed, not modified
- Selector management UI, traversal config, surface pickers — not exposed in playground

## Slices

### Slice 1: Delete Orchestration Backend
**Status:** DONE
**Files:**
- `backend/app/api/orchestration.py` — delete
- `backend/app/services/orchestration_service.py` — delete
- `backend/app/services/config/orchestration_templates.py` — delete
- `backend/app/models/orchestration.py` — delete
- `backend/app/schemas/orchestration.py` — delete
- `backend/tests/component/test_orchestration_service.py` — delete
- `backend/app/main.py` — remove orchestration router import + include
- `backend/app/models/__init__.py` — remove orchestration imports + __all__ entries
- `backend/alembic/versions/` — add new migration to drop tables
**What:** Remove all orchestration backend code. Add alembic migration to drop `orchestration_projects`, `orchestration_workflow_runs`, `orchestration_step_runs` tables.
**Verify:** `cd backend && $env:PYTHONPATH='.' ; .\.venv\Scripts\python.exe -m pytest tests -q`

### Slice 2: Delete Orchestration Frontend
**Status:** DONE
**Files:**
- `frontend/app/projects/` — delete entire directory
- `frontend/e2e/projects.spec.ts` — delete
- `frontend/lib/api/index.ts` — remove orchestration methods
- `frontend/lib/api/types.ts` — remove orchestration types (OrchestrationProject, OrchestrationTemplate, OrchestrationWorkflow, OrchestrationStepRun, OrchestrationPromotePayload, OrchestrationPromoteResponse, OrchestrationProjectCreatePayload, OrchestrationWorkflowCreatePayload, PriceComparisonResponse)
- `frontend/components/layout/app-shell.tsx` — remove projects nav item + pathname match
**What:** Remove all frontend projects/orchestration code and nav link.
**Verify:** `cd frontend && npx tsc --noEmit`

### Slice 3: Backend Playground Session API
**Status:** DONE
**Files:**
- `backend/app/api/playground.py` — create
- `backend/app/services/playground_service.py` — create
- `backend/app/models/playground.py` — create (PlaygroundSession model)
- `backend/app/schemas/playground.py` — create
- `backend/app/main.py` — register playground router
- `backend/app/models/__init__.py` — add playground model
- `backend/alembic/versions/` — migration for playground_sessions table
**What:** Build a thin session-based orchestration API:
- `POST /api/playground/sessions` — create session (input URL, auto-detect URL type)
- `GET /api/playground/sessions/{id}` — get session state + all step results
- `POST /api/playground/sessions/{id}/discover` — kick off listing/category crawl
- `POST /api/playground/sessions/{id}/select` — user confirms product selection (max 50)
- `POST /api/playground/sessions/{id}/extract` — kick off PDP crawl for selected URLs
- `POST /api/playground/sessions/{id}/pipeline` — run selected downstream ops (enrich/compare/monitor/audit)
- `GET /api/playground/sessions/{id}/results` — aggregated results

Session state machine: `CREATED → DISCOVERING → DISCOVERED → EXTRACTING → EXTRACTED → RUNNING_PIPELINE → COMPLETE`

Each step internally calls existing services without modification. Session stores state as JSON (step results, selected URLs, run IDs, job IDs).
**Verify:** `cd backend && $env:PYTHONPATH='.' ; .\.venv\Scripts\python.exe -m pytest tests/component/test_playground_service.py -q`

### Slice 4: Frontend Playground — Discovery + Selection
**Status:** DONE
**Files:**
- `frontend/app/playground/page.tsx` — create
- `frontend/lib/api/index.ts` — add playground API methods
- `frontend/lib/api/types.ts` — add playground types
- `frontend/components/layout/app-shell.tsx` — add "Playground" nav item
**What:** Build the playground page with a vertical stepper layout:
- URL input bar + "Start" button
- Step 1: Shows discovery progress → then displays found products as a selectable list (checkboxes, max 50)
- "Continue" button to confirm selection
- Simple, clean, no advanced options exposed
**Verify:** Dev server renders `/playground`, discovery flow works with mock data.

### Slice 5: Frontend Playground — Extraction + Pipeline Selection
**Status:** DONE
**Files:**
- `frontend/app/playground/page.tsx` — extend
**What:**
- Step 2: Shows PDP extraction progress (X/Y complete) → shows preview table of extracted data
- Step 3: Pipeline selection panel — checkboxes:
  - ☐ Enrich data (fill missing fields)
  - ☐ Product Intelligence (find competitors via Google/SerpAPI)
  - ☐ Create Monitor (watch for price/availability changes)
  - ☐ AI Audit (discoverability score) — note: "can run now, doesn't need extraction"
- "Run" button launches selected ops in parallel (respecting dependencies)
- Progress indicators for each running operation
**Verify:** Full flow from URL → discover → select → extract → pipeline selection works.

### Slice 6: Frontend Playground — Results + Export
**Status:** DONE
**Files:**
- `frontend/app/playground/page.tsx` — extend
**What:**
- Unified results view showing output of each completed pipeline step:
  - Extraction: data table with all fields
  - Enrichment: highlighted new/updated fields
  - PI: competitor matches with price comparison
  - Monitor: confirmation with link to monitor page
  - Audit: score card with recommendations
- Export button (JSON/CSV) for the combined dataset
- "Start New Session" button to reset
**Verify:** Results render correctly for each pipeline option.

### Slice 7: Polish + Smoke Test
**Status:** TODO
**Files:**
- `frontend/e2e/playground.spec.ts` — create
- UI polish pass
**What:** Add Playwright smoke test. Ensure loading states, error messages, empty states all look good. Mobile-responsive check.
**Verify:** `cd frontend && npx playwright test e2e/playground.spec.ts`

## Doc Updates Required

- [ ] `docs/CODEBASE_MAP.md` — remove orchestration files, add playground files
- [ ] `docs/frontend-architecture.md` — update page listing (projects → playground)
- [ ] `docs/backend-architecture.md` — add playground session API section

## Notes

- Session model is lightweight: just tracks state + stores JSON blobs for step config/results. Not a full workflow engine.
- Audit can be offered as a checkbox even at Step 1 since it only needs the input URL.
- Max 50 products keeps sessions fast (minutes not hours). UI shows "Showing first 50 of 200 found" with no option to expand beyond cap.
- Surfaces are auto-detected internally (listing surface for discover, ecommerce_detail for PDPs). User never sees surface config.
- If input URL is already a PDP (single product), skip discover/select steps entirely → go straight to extract → pipeline.
- The playground session table is simple: id, user_id, input_url, state, step_data (JSONB), created_at, updated_at.

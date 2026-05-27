# Plan: AI Discoverability Score Migration

**Created:** 2026-05-26
**Agent:** Codex
**Status:** DONE
**Touches buckets:** Bucket 2 Crawl Ingestion + Orchestration, Bucket 3 Acquisition, Bucket 4 Extraction, Frontend App

## Goal

Replace the UCP-first audit behavior with an AI Discoverability Score that evaluates real merchant catalog crawl signals. Reuse the existing UCP audit job, scoring, report, persistence, and UI shell. Done means `/ucp-audit` runs AID checks against sampled catalog/product pages, reports six AID dimensions, and no longer caps normal merchants because `/.well-known/ucp` is missing.

## Acceptance Criteria

- [x] `docs/plans/ACTIVE.md` points to `docs/plans/ai-discoverability-score-migration-plan.md`.
- [x] Audit jobs call catalog crawl/check logic, not UCP manifest/protocol probes.
- [x] Six dimensions exist: `D-AID1` through `D-AID6`, with D-AID1 as the only gate capped at 30.
- [x] AID findings use `AID1_*` through `AID6_*` codes from config, not inline service constants.
- [x] Existing job queue, DB schema, API routes, report JSON/Markdown, and page shell remain compatible.
- [x] Frontend copy says “AI Discoverability Score”, “Score Breakdown”, and “Signal Audit”.
- [x] Focused backend and frontend tests pass.

## Do Not Touch

- `backend/app/models/ucp_audit.py` — no DB schema change.
- `backend/app/api/ucp_audit.py` and `backend/app/schemas/ucp_audit.py` — keep route and wire contract stable for now.
- `backend/app/services/ucp_audit/reporting.py` and `types.py` — reuse existing report and dataclass shape.
- `backend/app/services/ucp_audit/discovery.py` and `protocol_checks.py` — leave dormant UCP implementation in place.
- Publish/export/pipeline persistence modules — this is not a downstream compensation change.

## Slices

### Slice 1: Config and Scoring Switch
**Status:** DONE
**Files:** `backend/app/services/config/aid_score.py`, `backend/app/services/ucp_audit/scoring.py`
**What:** Add AID dimension IDs, weights, finding codes, job status aliases, crawl limits, timeouts, and gate max constants. Update scoring to use AID config and apply only the D-AID1 zero-score cap.
**Verify:** Unit scoring tests cover weighted AID score and D-AID1 cap.

### Slice 2: Catalog Crawl
**Status:** DONE
**Files:** `backend/app/services/ucp_audit/catalog_crawl.py`, `backend/tests/component/test_catalog_crawl.py`
**What:** Use existing acquisition via `fetch_page`, sample listing/detail pages, extract product records and page signals, and keep crawl errors non-fatal.
**Verify:** Component tests mock acquisition/extraction and cover sampling, structured signals, robots, sitemap, and errors.

### Slice 3: Catalog Checks
**Status:** DONE
**Files:** `backend/app/services/ucp_audit/catalog_checks.py`, `backend/tests/component/test_catalog_checks.py`
**What:** Build AID contract payload and six dimension scores from crawl result.
**Verify:** Component tests cover clean catalog and representative gaps.

### Slice 4: Service Adapter
**Status:** DONE
**Files:** `backend/app/services/ucp_audit/service.py`, `backend/app/services/ucp_audit/__init__.py`, `backend/tests/component/test_service.py`
**What:** Replace UCP protocol discovery/probing calls with catalog crawl/check calls while keeping route and persistence contracts stable.
**Verify:** Service tests mock AID crawl/checks and assert persistence plus sample-size propagation.

### Slice 5: Repair Roadmap
**Status:** DONE
**Files:** `backend/app/services/ucp_audit/repair_roadmap.py`, `backend/tests/unit/test_repair_roadmap.py`
**What:** Replace roadmap actions, efforts, dimensions, dependencies, and sources with AID mappings.
**Verify:** Roadmap tests assert representative AID findings.

### Slice 6: Frontend Rename and Signal Copy
**Status:** DONE
**Files:** `frontend/app/ucp-audit/ucp-audit-page.tsx`, `frontend/app/ucp-audit/ucp-audit-components.tsx`, `frontend/components/layout/app-shell.tsx`
**What:** Rename visible product copy to AI Discoverability Score and update dimension/finding text.
**Verify:** Page tests assert new labels and AID evidence.

### Slice 7: Documentation and Active Plan Closeout
**Status:** DONE
**Files:** `docs/CODEBASE_MAP.md`, `docs/backend-architecture.md`, `docs/plans/ACTIVE.md`
**What:** Document new AID crawl/check/config ownership and mark verification notes.
**Verify:** Plan notes list executed commands and results.

## Doc Updates Required

- [x] `docs/CODEBASE_MAP.md` — add new AID crawl/check/config files under existing UCP audit owner.
- [x] `docs/backend-architecture.md` — update UCP audit description to AI Discoverability Score behavior.
- [x] `docs/INVARIANTS.md` — not required unless extraction order or LLM gating changes.
- [x] `docs/ENGINEERING_STRATEGY.md` — not required.

## Notes

- User approved implementation on 2026-05-26.
- Backend focused verify passed: `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests\component\test_service.py tests\component\test_catalog_crawl.py tests\component\test_catalog_checks.py tests\unit\test_scoring.py tests\unit\test_repair_roadmap.py tests\unit\test_reporting.py -q`.
- Frontend focused verify passed: `cd frontend; npm test -- app/ucp-audit/ucp-audit-page.test.tsx`.

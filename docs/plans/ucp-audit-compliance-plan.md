# Plan: UCP Audit Compliance Upgrade

**Created:** 2026-05-24
**Agent:** Codex
**Status:** IN PROGRESS
**Touches buckets:** UCP audit backend, UCP audit frontend, LLM prompt registry, docs plan state

## Goal

Upgrade UCP Audit from a manifest presence check into a protocol compliance audit for the `ucp.dev` 2026-04-08 profile shape. Done means discovery, service/capability validation, transport probes, schema field checks, optional LLM schema explanation, scoring gates, repair roadmap, and frontend displays all expose actionable evidence without changing crawl output.

## Acceptance Criteria

- [x] Discovery sends the UCP JSON Accept header and reports content type, final URL, redirects, version source, and fallback discovery source.
- [x] Manifest validation targets `ucp.version`, `services`, `capabilities`, root `signing_keys`, and `supported_versions["2026-04-08"]`.
- [x] Service/capability entries validate version and endpoint shape; D-UCP2 uses 60 service / 40 capability scoring.
- [x] MCP, REST, and embedded transports are probed without state-changing calls, and D-UCP3 can cap the overall score.
- [x] Schema probes fetch JSON schemas, validate schema syntax, score required field coverage, and preserve field evidence.
- [x] `llm_enabled` runs advisory schema analysis only for deterministic schema gaps and never changes scores.
- [x] Repair roadmap includes evidence, effort, dependencies, sorted fix order, and conditional Shopify advisory.
- [x] Frontend displays evidence, effort, schema matrix, transport status code/tools/errors, gate caps, loading summary, domain validation, and roadmap export evidence.
- [x] `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests\services\ucp_audit -q` exits 0.
- [x] `cd frontend; npm test -- ucp-audit-page.test.tsx` exits 0.

## Do Not Touch

- `backend/app/services/pipeline/*`, `publish/*`, and export modules — UCP audit is a report subsystem only.
- Crawl record persistence and extraction behavior — this change must not hide crawl/extraction defects downstream.

## Slices

### Slice 1: Discovery And Manifest Shape
**Status:** DONE
**Files:** `backend/app/services/ucp_audit/discovery.py`, `backend/app/services/ucp_audit/types.py`, `backend/app/services/config/ucp_audit.py`
**What:** Add Accept negotiation, response metadata, content-type validation, version selection, Link fallback, and official manifest shape checks.
**Verify:** UCP discovery tests cover headers, redirects, content type, supported version, and missing fields.

### Slice 2: Protocol Checks, Schema Validation, And Scoring
**Status:** DONE
**Files:** `backend/app/services/ucp_audit/protocol_checks.py`, `backend/app/services/ucp_audit/scoring.py`, `backend/pyproject.toml`
**What:** Add REST/embedded/MCP conformance checks, schema syntax and field validation, D-UCP2 scoring adjustment, and D-UCP3 gate.
**Verify:** UCP protocol/scoring tests cover transports, schema field misses, and gates.

### Slice 3: Optional LLM Schema Explanation
**Status:** DONE
**Files:** `backend/app/services/ucp_audit/service.py`, `backend/app/services/config/ucp_audit.py`, `backend/app/services/llm/config_service.py`, `backend/app/services/llm/payloads.py`, `backend/app/data/prompts/*`
**What:** Register `ucp_schema_analysis`, snapshot active config, call LLM only for failed deterministic schema checks, and store advisory output.
**Verify:** Service tests monkeypatch `run_prompt_task` for disabled/enabled/no-score-change paths.

### Slice 4: Roadmap Evidence
**Status:** DONE
**Files:** `backend/app/services/ucp_audit/repair_roadmap.py`, `backend/app/services/ucp_audit/reporting.py`
**What:** Add evidence, effort, dependencies, sorted order, and conditional Shopify advisory to repair roadmap payload.
**Verify:** Roadmap/reporting tests assert payload shape and ordering.

### Slice 5: Frontend Evidence Display
**Status:** DONE
**Files:** `frontend/app/ucp-audit/use-ucp-audit.ts`, `frontend/app/ucp-audit/ucp-audit-components.tsx`, `frontend/app/ucp-audit/ucp-audit-page.tsx`
**What:** Render richer backend evidence, schema details, transport fields, loading state, gate cap text, domain validation, and export evidence.
**Verify:** UCP frontend test covers new visible behavior.

## Doc Updates Required

- [x] `docs/backend-architecture.md` — update UCP audit contract summary if payload fields change.
- [ ] `docs/CODEBASE_MAP.md` — not needed unless new owned files beyond prompts are added.
- [ ] `docs/INVARIANTS.md` — not needed unless UCP audit contract becomes a shared runtime invariant.

## Notes

- Target spec is `ucp.dev` 2026-04-08.
- LLM output is advisory only and cannot increase compliance score.
- Existing data-enrichment worktree changes are unrelated and must be preserved.
- 2026-05-24: UCP backend focused suite passed: 25 passed.
- 2026-05-24: Frontend focused UCP test passed: 5 passed.
- 2026-05-24: Frontend lint passed and full frontend test suite passed: 111 passed.
- 2026-05-24: Full backend suite was attempted twice; one run timed out after 5 minutes, and a rerun exited early without actionable failure details before a fail-fast rerun also timed out.

# Plan: Roast Audit Remediation

**Created:** 2026-05-20
**Agent:** Codex
**Status:** DONE
**Touches buckets:** API + Bootstrap, Crawl Ingestion + Orchestration, Acquisition + Browser Runtime, Extraction, LLM Admin + Runtime, Frontend, CI, Docs

## Goal

Resolve the actionable issues from `docs/audits/roast-audit.md` while ignoring the `.env` finding by explicit user request. Done means security key handling and admin-password guards are corrected and tested, root/hygiene issues are cleaned up, dependency and lint drift has enforceable guardrails, config modules no longer mutate globals at import time, large god modules are split by clear ownership, high-risk broad exception catches are narrowed, backend auth/security/LLM config tests exist, and CI runs backend quality checks.

## Acceptance Criteria

- [x] `.env` secrets are not read, edited, rotated, committed, or otherwise handled in this plan.
- [x] `backend/app/core/security.py` derives or validates Fernet keys without predictable padding or silent truncation, with round-trip encryption tests.
- [x] `backend/app/core/config.py` owns `app_env` through `Settings` and rejects known weak default admin passwords, including `AdminPassword123!`.
- [x] Root hygiene issues are resolved: root `image.png` is removed or moved under a named docs asset path, TODOs either link to a tracking issue or are deleted, and contributor conventions are documented.
- [x] Backend dependency ranges are bounded or locked through a committed reproducible install artifact, and frontend CI uses `npm ci`.
- [x] Pylint useful checks are re-enabled with realistic thresholds or ratcheted allowlists, not blanket-disabled.
- [x] `config/extraction_rules.py`, `config/field_mappings.py`, and `config/selectors.py` no longer inject JSON values into module globals during import.
- [x] Large modules called out in the audit are split by responsibility without changing public behavior: `extraction_rules.py`, `js_state/state_normalizer.py`, `extract/detail/identity/core.py`, and `browser_surface_probe/core.py`.
- [x] High-risk `except Exception` catches in business/security/LLM paths are narrowed or re-raise process-control exceptions; browser/acquisition resilience catches have explicit justification where they remain.
- [x] Focused tests cover `security.py`, `auth_service.py`, `api_key_service.py`, `crawl/access_service.py`, `alert_service.py`, and `llm/config_service.py` at their public contracts.
- [x] Backend CI runs at least Ruff, mypy, and pytest on push and pull request.
- [x] `backend/tests/services/test_structure.py` ratchets the new architecture rules so the same audit regressions cannot return.
- [x] `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests -q` exits 0 before closure.

## Do Not Touch

- `.env` and any local secret files - user explicitly said to ignore the `.env` issue.
- `publish/*` and export code - audit fixes must not compensate downstream for extraction or config issues.
- Archived plans under `docs/archive/**` - historical only, unless a moved audit artifact needs an archive note.
- Runtime extraction semantics - module splitting must preserve adapter -> structured source -> DOM ordering and explicit LLM backfill only.

## Slices

### Slice 1: Baseline And Scope Lock
**Status:** DONE
**Files:** `docs/audits/roast-audit.md`, `backend/tests/services/test_structure.py`, `backend/pyproject.toml`, `frontend/package.json`, `.github/workflows/*`
**What:** Reconcile audit claims with current code, record current broad-exception counts by subsystem, current large-file line counts, current dependency policy, and current test coverage targets. Confirm `.env` is excluded from all subsequent work.
**Verify:** `rg -n 'ljust\(32|globals\(\)|except Exception|TODO\(' backend --glob '!backend/.venv/**'`

### Slice 2: Security And Settings Fixes
**Status:** DONE
**Files:** `backend/app/core/security.py`, `backend/app/core/config.py`, `backend/tests/core/test_security.py`, `backend/tests/core/test_config_security.py`
**What:** Replace padded/truncated Fernet key derivation with deterministic SHA-256 derivation or strict Fernet-key validation, depending on current config contract. Add `app_env` to `Settings`, make secret guards use settings state, and add `AdminPassword123!` plus minimum complexity checks for staging/production defaults.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/core/test_security.py tests/core/test_config_security.py -q`

### Slice 3: Auth And Admin Contract Tests
**Status:** DONE
**Files:** `backend/app/services/auth_service.py`, `backend/app/services/api_key_service.py`, `backend/app/services/crawl/access_service.py`, `backend/app/services/alert_service.py`, `backend/app/services/llm/config_service.py`, matching tests under `backend/tests/services/`
**What:** Add public-contract tests for auth bootstrap/login behavior, API-key hashing/create/revoke flows, crawl access decisions, alert creation/update constraints, and encrypted LLM config storage. Refactor only where tests expose real coupling or swallowed errors.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services/test_auth_service.py tests/services/test_api_key_service.py tests/services/test_crawl_access_service.py tests/services/test_alert_service.py tests/services/test_llm_config_service.py -q`

### Slice 4: Repository Hygiene
**Status:** DONE
**Files:** `CONTRIBUTING.md`, `image.png`, `docs/assets/*`, `backend/tests/services/test_structure.py`, `backend/app/services/acquisition/domain_profile_schema.py`
**What:** Add contributor conventions pointing to `AGENTS.md`, `docs/agent/coding-standards.md`, and the verify commands. Delete or move the root image to a descriptive docs asset path. Resolve untracked TODO debt by linking to issue IDs or deleting stale comments.
**Verify:** `rg -n 'TODO\((chore|phase-3)\)' backend docs; Test-Path image.png`

### Slice 5: Dependency And Lint Guardrails
**Status:** DONE
**Files:** `backend/pyproject.toml`, `backend/requirements*.txt` if chosen, `frontend/package.json`, `frontend/package-lock.json`, `.github/workflows/backend-ci.yml`, `.github/workflows/frontend-playwright-smoke.yml`, `backend/tests/services/test_structure.py`
**What:** Choose one reproducibility path for backend dependencies: bounded compatible ranges with upper caps or a generated lock/requirements artifact. Keep frontend ranges acceptable because `package-lock.json` exists, but enforce `npm ci` in CI. Replace blanket Pylint disables with thresholds and explicit narrow suppressions.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m ruff check app tests; .\.venv\Scripts\python.exe -m mypy app`

### Slice 6: Typed Config Loading Without Import-Time Globals Mutation
**Status:** DONE
**Files:** `backend/app/services/config/extraction_rules.py`, `backend/app/services/config/field_mappings.py`, `backend/app/services/config/selectors.py`, related JSON config files, config tests
**What:** Replace `globals()[name] = value` import-time injection with explicit typed config objects or dictionaries. Preserve existing exported names only through deliberate compatibility properties during the migration, then delete unused aliases. Keep all runtime tokens and thresholds inside `app/services/config/*`.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services/test_config_* tests/services/test_structure.py -q`

### Slice 7: Split Extraction Rules By Concern
**Status:** DONE
**Files:** `backend/app/services/config/extraction_rules.py`, new focused config modules under `backend/app/services/config/` or a deliberate replacement package after import migration, import call sites, `docs/CODEBASE_MAP.md`, `docs/backend-architecture.md`
**What:** Split rule groups by coherent domain such as pricing, variants, identity, shell/utility rejection, structured-source keys, and DOM selectors. Keep a small facade that exports the stable contract. Delete dead duplicate constants as they move.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services/test_structure.py tests/services/test_detail_extractor*.py tests/services/test_listing*.py -q`

### Slice 8: Decompose Large Logic Modules
**Status:** DONE
**Files:** `backend/app/services/js_state/state_normalizer.py`, `backend/app/services/extract/detail/identity/core.py`, `backend/browser_surface_probe/core.py`, new focused modules under existing owners, import call sites, `docs/CODEBASE_MAP.md`, `docs/backend-architecture.md`
**What:** Split by responsibility, not by helper buckets. Suggested cuts: ecommerce JS mapping, job JS mapping, Nuxt revival, product identity, requested-detail matching, redirect identity, browser-surface evidence collection, and report assembly. Preserve public facades and remove dead compat shims after callers migrate.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services/test_js_state* tests/services/test_detail_identity* tests/test_browser_surface_probe.py tests/services/test_structure.py -q`

### Slice 9: Exception Narrowing
**Status:** DONE
**Files:** `backend/app/services/crawl/batch_runtime.py`, `backend/app/services/listing_extractor.py`, `backend/app/services/llm/provider_client.py`, `backend/app/services/acquisition/traversal_recovery.py`, `backend/app/services/acquisition/traversal_helpers.py`, other high-risk catch sites identified in Slice 1
**What:** Narrow business-path catches to expected exception classes such as JSON decode, HTTP/client, database, Playwright, timeout, or validation errors. Add a shared process-control re-raise helper only if it removes repetition without hiding control flow. Leave browser resilience catches only where the fallback is intentionally URL-local and logged.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services/test_crawl_batch_runtime.py tests/services/test_listing*.py tests/services/test_llm*.py tests/services/test_acquisition*.py -q`

### Slice 10: CI And Architecture Ratchets
**Status:** DONE
**Files:** `.github/workflows/backend-ci.yml`, `.github/workflows/frontend-playwright-smoke.yml`, `backend/tests/services/test_structure.py`, `docs/ENGINEERING_STRATEGY.md`
**What:** Add backend CI for Ruff, mypy, and pytest. Add structure tests for root binary assets, import-time globals mutation, broad Pylint disables, large-file budgets or explicit allowlists, and high-risk broad exception catches. Document any new audit anti-patterns as stable rules, not a changelog.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services/test_structure.py -q`

### Slice 11: Full Verification And Audit Closure
**Status:** DONE
**Files:** `docs/audits/roast-audit.md`, `docs/plans/ACTIVE.md`, `docs/plans/roast-audit-remediation-plan.md`, relevant architecture docs touched by previous slices
**What:** Run full backend verification, mark acceptance criteria, record final decisions, and mark the audit fixed/archived only after tests pass. Restore `ACTIVE.md` to the next active/queued plan after closure.
**Verify:** `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests -q`

## Doc Updates Required

- [x] `docs/backend-architecture.md` - updated config ownership, JS-state split, and browser report rendering ownership.
- [x] `docs/CODEBASE_MAP.md` - updated new focused modules and moved asset ownership.
- [x] `docs/INVARIANTS.md` - no runtime extraction/user-control contract changed; no update needed.
- [x] `docs/ENGINEERING_STRATEGY.md` - added audit-derived guardrails for import-time globals mutation, broad lint disables, and untracked hygiene debt.
- [x] `CONTRIBUTING.md` - added contributor workflow and verification entrypoint.

## Notes

- Existing active plan before this one was `Agentic Delta Engine` with status `BLOCKED`; it was moved into the queue because the user explicitly assigned this new planning task.
- User explicitly said to ignore the `.env` issue. This plan excludes secret rotation, `.env` editing, and git-history secret scanning.
- Audit test-count claim is stale in current workspace: `backend/tests` currently contains 266 test files. The remaining problem is targeted coverage for auth/security/admin-facing services, not total file count alone.
- Follow `docs/agent/coding-standards.md`: specific names, single-responsibility functions, no fake `Utils` modules, no magic numbers, typed boundaries, no broad log-and-swallow error handling.
- Slice 1 verified with `rg -n 'ljust\(32|globals\(\)|except Exception|TODO\(' backend --glob '!backend/.venv/**'`. Baseline confirmed old Fernet padding, config globals mutation, broad exception debt, and two untracked TODOs. `.env` was not read.
- Slice 2 verified with `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/core/test_security.py tests/core/test_config_security.py -q` (6 passed).
- Slice 3 verified with `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services/test_auth_service.py tests/services/test_api_key_service.py tests/services/test_crawl_access_service.py tests/services/test_alert_service.py tests/services/test_llm_config_service.py -q` (13 passed).
- Slice 4 verified with `rg -n 'TODO\((chore|phase-3)\)' backend docs; Test-Path image.png` (no TODO matches; root image path false).
- Slice 5 verified with `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m ruff check app tests; .\.venv\Scripts\python.exe -m mypy app` (passed).
- Slice 6 verified with `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services/test_config_imports.py tests/services/test_structure.py -q` (59 passed). The protocol glob form was expanded manually on Windows.
- Slice 7 verified with `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services/test_structure.py tests/services/test_detail_extractor_priority_and_selector_self_heal.py tests/services/test_detail_extractor_structured_sources.py tests/services/test_listing_escalation_decision.py tests/services/test_listing_identity_regressions.py tests/services/test_listing_integrity_gate.py -q` (302 passed, 12 skipped).
- Slice 8 verified with `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services/test_js_state_current_color.py tests/services/test_state_mappers.py tests/services/test_listing_identity_regressions.py tests/test_browser_surface_probe.py tests/services/test_structure.py -q` (107 passed).
- Slice 9 verified with `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services/test_listing_escalation_decision.py tests/services/test_listing_identity_regressions.py tests/services/test_listing_integrity_gate.py tests/services/test_llm_circuit_breaker.py tests/services/test_llm_runtime.py tests/services/test_llm_config_service.py tests/services/test_acquisition_domain_profile_schema.py -q` (79 passed).
- Slice 10 verified with `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/services/test_structure.py -q` (28 passed).
- Slice 11 verification first exposed a removed `asyncio` module import that a pipeline test patches; restored it with a targeted `noqa`.
- Final verification passed with `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m ruff check app tests browser_surface_probe; .\.venv\Scripts\python.exe -m mypy app` and `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests -q` (1884 passed, 16 skipped).

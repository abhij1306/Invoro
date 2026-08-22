# Plan: Productionization 07 — Absolute Quality Gates

**Created:** 2026-08-21
**Agent:** Codex
**Status:** QUEUED — blocked from execution until Plans 01–05 leave zero LOC/complexity violations
**PR boundary:** One independent final PR. Quality policy, deterministic checks, and CI enforcement only.
**Touches buckets:** Backend architecture tests/config, frontend lint/architecture scripts, GitHub Actions, quality documentation

## Goal

Make debt limits permanent. CI must block any first-party maintained file above 800 physical lines, any callable above cyclomatic complexity 15, backend/frontend lint or format drift, type errors, test failures, or dependency audit failures. Reuse existing quality owners. Remove obsolete ratchets and broad allowances. Do not change product behavior. Keep application/test source LOC non-increasing; any quality-check code added must replace redundant budget logic where practical.

## Preconditions

Do not start implementation until current scans prove:

- Backend tests/tooling from Plan 01: zero files over 800 and zero callables over 15.
- Backend extraction from Plan 02: zero files over 800 and zero callables over 15.
- Backend acquisition/orchestration from Plan 03: zero files over 800 and zero callables over 15.
- Remaining backend services from Plan 04: zero files over 800 and zero callables over 15.
- Frontend from Plan 05: zero files over 800 and zero callables over 15.

Plan 06 should merge first so workflow edits are based on frozen installs. If it has not merged, rebase or coordinate instead of overwriting dependency-install changes.

## Canonical Gate Semantics

- LOC means physical UTF-8 lines, including blanks and comments.
- Limit is absolute: `>800` fails. No grandfathered first-party allowlist.
- Complexity means per-function/method/callable McCabe cyclomatic complexity. `>15` fails.
- Python uses numeric Radon values. Do not use Radon grade C as the gate because grade C includes 11–20.
- Frontend uses ESLint `complexity: [error, 15]` across maintained JS/TS/TSX and architecture scripts.
- Exclude only `.git`, `.venv`, `node_modules`, `.next`, coverage/htmlcov, caches, `dist`, `build`, generated artifacts, Playwright reports/results, lockfiles, minified assets, and proven vendored/generated code.
- Tests and first-party tooling are included.
- No broad suppressions, legacy budgets above 800, warnings-only steps, or `continue-on-error`.

Existing owners:

- `backend/tests/regression/test_structure.py` owns backend LOC/architecture enforcement.
- `backend/pyproject.toml` owns Python quality-tool configuration and dev dependencies.
- `frontend/eslint.config.mjs` owns frontend complexity/lint policy.
- `frontend/scripts/check-frontend-architecture.mjs` and `check-crawl-architecture.mjs` own frontend architecture checks.
- `.github/workflows/backend-ci.yml` and `frontend-quality.yml` own blocking CI execution.

## Acceptance Criteria

- [ ] Record starting commit, dirty state, existing checks, and zero-violation precondition scans in Notes.
- [ ] One deterministic backend check fails on any maintained backend/repo Python file over 800 physical lines.
- [ ] One deterministic backend check fails on any maintained Python callable over CC 15.
- [ ] Frontend checks fail on any maintained JS/TS/TSX file over 800 physical lines.
- [ ] Frontend ESLint fails on any callable/component over CC 15.
- [ ] Generated/vendor exclusions are narrow, explicit, and tested.
- [ ] Existing `DEFAULT_LOC_BUDGET=1000`, larger legacy ratchets, and crawl budgets of 1400/1500 are deleted or reduced to the absolute policy.
- [ ] Backend CI blocks on Ruff lint, Ruff format check, mypy, LOC, complexity, dependency audit, and safe tests.
- [ ] Frontend CI blocks on frozen install, dependency audit, Prettier check, ESLint including complexity, LOC/architecture, typecheck, unit tests, and build.
- [ ] Frontend quality workflow runs on relevant pushes and pull requests, matching backend coverage.
- [ ] Tests prove the gates fail for synthetic 801-line and CC-16 fixtures and pass at exactly 800/15 without committing oversized fixtures.
- [ ] Vulture and jscpd remain diagnostic unless this PR proves a low-noise deterministic blocking policy. Do not silently turn heuristic output into a launch gate.
- [ ] Local full verification passes and CI configuration is syntax-valid.
- [ ] No product/runtime behavior changes.

## Do Not Touch

- Application behavior or structural refactors — Plans 01–05 must already be complete.
- Dependency versions/lockfiles except a quality-tool dependency strictly required for Radon — Plan 06 owns general updates.
- Coverage thresholds, deployment, branch protection settings, migrations, or product contracts — outside this plan.
- Broad formatting changes — current formatting already passes; only enforce it.

## Slices

### Slice 1: Prove Green Preconditions and Test Gate Boundaries

**Status:** TODO
**Files:** existing quality configs/scripts/tests read-only initially
**What:** Run repo-wide physical LOC and numeric complexity scans. Stop if any violation remains; return it to the owning plan. Inspect existing backend structure budgets and frontend crawl budgets. Add focused synthetic/unit tests for exact 800/801 and 15/16 boundaries using temporary content, not committed giant fixtures.
**Verify:** Boundary tests fail against old policy where expected, then pass after gate implementation. Record exact scan totals.

### Slice 2: Backend Absolute LOC and Complexity Gates

**Status:** TODO
**Files:** `backend/tests/regression/test_structure.py`, `backend/pyproject.toml`, smallest existing quality helper only if justified
**What:** Change backend structure enforcement from non-blank/ratcheted budgets to physical-line absolute 800 across maintained backend tests, source, and tooling. Remove obsolete allowlists. Add exact numeric Radon `>15` enforcement through the existing architecture-test owner or a minimal same-owner helper. Do not duplicate threshold/config sources.
**Verify:** Focused boundary tests; `cd backend; $env:PYTHONPATH='.'; .\.venv\Scripts\python.exe -m pytest tests/regression/test_structure.py -q -m regression`; direct repo-wide Radon comparison.

### Slice 3: Frontend Absolute LOC and Complexity Gates

**Status:** TODO
**Files:** `frontend/eslint.config.mjs`, existing frontend architecture scripts, `frontend/package.json` scripts only if needed, focused script tests if present
**What:** Replace 1400/1500 crawl budgets and any ratchets with absolute physical 800 across maintained frontend files. Add ESLint complexity 15 to committed config so normal `lint:eslint` owns it. Ensure architecture scripts themselves are scanned. Keep exclusions aligned with actual artifacts.
**Verify:** `cd frontend; pnpm run lint; pnpm run typecheck`; boundary fixture tests; direct LOC comparison.

### Slice 4: Blocking CI Wiring

**Status:** TODO
**Files:** `.github/workflows/backend-ci.yml`, `.github/workflows/frontend-quality.yml`
**What:** Add backend Ruff format check and explicit quality gate execution. Keep frozen install from Plan 06. Ensure frontend quality runs on push and PR paths and normal lint invokes complexity. Keep every step blocking. Reuse scripts/tests; do not paste long inline scanners into YAML.
**Verify:** Validate workflow YAML; run every workflow command locally with the same working directory and environment assumptions.

### Slice 5: Diagnostic Debt Tools and Final Verification

**Status:** TODO
**Files:** existing Vulture config and optional jscpd config/scripts only if deterministic value justifies them; quality docs
**What:** Run Vulture at configured 100% confidence and jscpd with explicit exclusions. Validate findings. Delete confirmed dead/duplicate quality-tool code only within this PR's quality scope. Keep heuristic tools informational unless false-positive-free failure semantics are proven and documented.
**Verify:** Backend safe suite; acquisition/extraction smoke where available; frontend format/lint/type/test/build; dependency audits; repo-wide LOC and complexity scans all exit 0.

## Final Verification Commands

```powershell
cd backend
$env:PYTHONPATH='.'
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m ruff format --check app tests
.\.venv\Scripts\python.exe -m mypy app
.\.venv\Scripts\python.exe -m pytest tests -q -m "unit or component or regression"
.\.venv\Scripts\python.exe run_acquire_smoke.py commerce
.\.venv\Scripts\python.exe run_extraction_smoke.py

cd ..\frontend
pnpm install --frozen-lockfile
pnpm audit --audit-level=high
pnpm run format:check
pnpm run lint
pnpm run typecheck
pnpm test
pnpm run build
```

## Doc Updates Required

- [ ] `docs/ENGINEERING_STRATEGY.md` — make absolute physical LOC 800 and callable CC 15 mandatory hygiene gates; remove contradictory guidance.
- [ ] `docs/CODEBASE_MAP.md` — record the quality-check owner only if a new stable helper is unavoidable.
- [ ] `docs/backend-architecture.md` / `docs/frontend-architecture.md` — record stable quality commands.
- [ ] `README.md` — expose canonical local quality commands if not already covered by Plan 06.
- [ ] `docs/plans/ACTIVE.md` — active pointer and final closeout.
- [ ] `docs/audits/productionization-evidence-report-2026-08-21.md` — archive/delete only after all findings are closed by passing verification, per Engineering Strategy.

## Notes

- Source evidence: `docs/audits/productionization-evidence-report-2026-08-21.md`, findings F-LOC-800, F-CC-15, F-CI-GATES, F-BE-FORMAT-CI, F-FE-PUSH, F-FE-COMPLEXITY, F-STRUCT-800, and F-FE-BUDGET.
- Current local quality checks passed in the audit except absolute LOC/complexity and backend CI formatting. Full pytest/Vitest were not run by that audit.
- External GitHub branch protection is unverified. Repo CI must still be correct; provider enforcement needs separate readback if requested.


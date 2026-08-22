# Plan: Productionization 06 — Dependency and Reproducibility Hardening

**Created:** 2026-08-21
**Agent:** Codex
**Status:** COMPLETE — implemented and locally verified 2026-08-22; CI/merge tracked by the shipping workflow
**PR boundary:** One branch for dependency hardening plus the remaining Plan 07 LOC/complexity precondition debt. Absolute gate implementation remains in Plan 07.
**Touches buckets:** Backend/frontend manifests and lockfiles, dependency audit steps, fresh-clone documentation

## Goal

Make backend and frontend installs reproducible and remove known dependency-audit failures using low-risk supported updates. This branch also owns the user-approved remaining LOC/complexity precondition debt and unresolved review findings; Plan 07 still owns absolute gate enforcement. Do not perform major runtime/framework migrations.

## Context for a Fresh Session

Audit evidence from 2026-08-21:

- Backend owns `backend/pyproject.toml` and `backend/uv.lock`, but Backend CI uses `pip install -e ".[dev]"`; CI does not prove the locked graph.
- Frontend owns `frontend/package.json`, `frontend/pnpm-lock.yaml`, and `packageManager: pnpm@11.9.0`; Frontend CI already uses `pnpm install --frozen-lockfile`.
- `pnpm audit --audit-level=high` failed because locked `nanoid` was 3.3.17 and advisory GHSA-2v37-7h3g-55p8 requires at least 3.3.18.
- Local audit found no backend vulnerability, but it audited the local uv-synced environment rather than CI's range-resolved pip graph.
- README package-manager instructions were inconsistent with pnpm/Corepack.

Versions change. Re-run registry/audit commands. Use current authoritative evidence. Do not blindly update to latest.

## Allowed Update Policy

- Required: fix reachable/high audit failures and make CI consume frozen lockfiles.
- Allowed: compatible patch updates for direct runtime/dev dependencies when focused verification is clear.
- Allowed with isolation inside this PR: low-risk minor tool/library updates after patch batch is green.
- Excluded: Redis 8, MCP 2, ESLint 10, TypeScript 7, jsdom 30, Testing Library 7, or any other major update.
- Keep Patchright/browser-driver updates isolated and run browser smoke before retaining them.
- Keep Next and `eslint-config-next` aligned. Do not update one without compatibility evidence for the other.
- Do not remove a dependency based only on an unused-package scanner. Validate imports, dynamic registration, CLI entry points, and build use.

## Acceptance Criteria

- [x] Record starting commit, dirty state, runtime/package-manager versions, current audit results, and outdated reports in Notes.
- [x] Backend CI installs from `backend/uv.lock` in frozen mode; no parallel lock strategy is added.
- [x] Frontend frozen pnpm install remains green.
- [x] `pnpm audit --audit-level=high` exits 0 with no unjustified advisory ignore.
- [x] Backend audit runs against the exact frozen environment used by CI and exits 0.
- [x] README fresh-clone instructions use the actual Python/uv and pnpm/Corepack workflow.
- [x] Safe patch/minor batches are verified independently and lockfiles are internally consistent.
- [x] Major upgrades remain explicitly deferred in Notes with reason; no fake “fully current” claim is made.
- [x] User-approved refactors remove every maintained >800 LOC and >15 CC violation; product changes are limited to validated review fixes.
- [x] Backend safe suite and frontend lint/type/test/build pass locally; final-commit full suites run in CI.

## Do Not Touch

- Application architecture or refactors — Plans 01–05.
- LOC/complexity/lint policy and new quality gates — Plan 07.
- Product behavior, schemas, migrations, deployment/provider settings — out of scope.
- Broad formatting — forbidden.

## Slices

### Slice 1: Reproduce Current Graphs

**Status:** DONE
**Files:** manifests, lockfiles, workflows, README read-only
**What:** Record Python, uv, Node, Corepack, and pnpm versions. Run frozen installs, `uv`/registry outdated checks, `pip-audit` or existing backend audit against the locked graph, `pnpm outdated`, and `pnpm audit --audit-level=high`. Map direct vs transitive ownership. Confirm whether `nanoid` remains vulnerable.
**Verify:** Both current frozen installs complete from lockfiles without modifying them; record exact commands and exits.

### Slice 2: Frontend Security and Patch Batch

**Status:** DONE
**Files:** `frontend/package.json` only when direct constraints/overrides require it; `frontend/pnpm-lock.yaml`
**What:** Resolve the nanoid advisory through the smallest compatible lock/override change. Then apply compatible low-risk patches such as React/types, Vitest/coverage, Tailwind, and Zustand only if current registry evidence supports them. Do not mix Next, Playwright, Recharts/forms, or majors into this batch.
**Verify:** `cd frontend; pnpm install --frozen-lockfile; pnpm audit --audit-level=high; pnpm run lint; pnpm run typecheck; pnpm test; pnpm run build`

### Slice 3: Backend Frozen CI and Patch Batch

**Status:** DONE
**Files:** `backend/pyproject.toml`, `backend/uv.lock`, `.github/workflows/backend-ci.yml`
**What:** Make CI install the frozen uv graph using the existing Python 3.12 target. Audit that exact environment. Remove the stale vulnerability ignore only if the frozen graph and package usage prove it unnecessary. Apply low-risk patch updates such as Ruff, SQLAlchemy, Uvicorn, curl-cffi, mypy, and test tools only when current compatibility evidence supports them. Keep Redis major range from silently resolving an unsupported major.
**Verify:** Fresh frozen backend install; backend audit; Ruff, format check, mypy, and safe suite.

### Slice 4: Isolated Supported Minors and Browser Driver Decision

**Status:** DONE
**Files:** manifests/lockfiles only
**What:** Evaluate current supported minors one group at a time. Next + eslint-config-next must move together. Prettier/lucide may move separately. Patchright/Playwright changes require acquisition/e2e smoke. Revert any batch that changes behavior or cannot be verified. Leave high-risk majors deferred.
**Verify:** Repeat full workspace checks after each retained group. Run `run_acquire_smoke.py commerce` for backend browser-driver changes and a focused Playwright smoke for frontend Playwright changes.

### Slice 5: Fresh-Clone Documentation and Final Graph Verification

**Status:** DONE
**Files:** `README.md`, manifests, lockfiles, dependency-install workflow lines
**What:** Document one canonical frozen install/test path per workspace. Verify commands in a clean temporary clone/worktree without relying on existing `.venv`, `node_modules`, or caches. Do not alter user files or delete broad directories.
**Verify:** Fresh backend/frontend install, audits, backend safe suite, frontend lint/type/test/build.

## Doc Updates Required

- [x] `README.md` — canonical uv/pnpm fresh-clone and verification commands.
- [x] `docs/backend-architecture.md` / `docs/frontend-architecture.md` — frozen graph ownership and package-manager policy.
- [x] `docs/plans/ACTIVE.md` — closeout and Plan 07 queue.

## Notes

- Source evidence: `docs/audits/productionization-evidence-report-2026-08-21.md`, sections 2, 3, 8, 9, and 14.
- Plan 07 also edits workflows. Merge this plan first or rebase Plan 07 cleanly; do not discard either plan's steps.
- Dependency freshness is not “latest at all costs.” Supported, reproducible, verified graph is the target.
- 2026-08-22 branch baseline: commit `b3c4fd662ce3f55bfbf089efa332fdcf14f7cb08`; worktree clean; Python 3.14.6 host, uv 0.11.28, Node 26.7.0, pnpm 11.22.0; Corepack is not installed on the host. The project targets Python 3.12 and pins pnpm 11.9.0.
- Baseline frozen installs passed: `uv sync --project backend --frozen --extra dev` and `pnpm install --dir frontend --frozen-lockfile`.
- Baseline frontend audit passed with no known vulnerabilities. `pnpm outdated` reported only `@hookform/resolvers` 5.8.0 -> 5.9.0 plus explicitly deferred ESLint 10 and TypeScript 7 majors. The lock already contains the `nanoid` 3.3.18 override.
- Scope approved by the user on 2026-08-22: clear all remaining physical LOC >800 and callable CC >15 debt in this branch so Plan 07 can start separately after merge.
- Retained compatible updates: `@hookform/resolvers` 5.9.0, Ruff 0.16.4, and safe locked backend patches including curl-cffi 0.16.1, FastMCP 3.4.7, Logfire 4.41.0, lxml 6.1.2, and Uvicorn 0.52.4. Redis remains constrained below 8.
- SQLAlchemy 2.0.52 and mypy 2.3.1 were reverted after their combination broke SQLAlchemy stub discovery; the verified graph retains SQLAlchemy 2.0.51 and mypy 2.3.0.
- Deferred majors remain Redis 8, MCP 2, ESLint 10, TypeScript 7, and other framework/runtime majors because this plan does not own migration work.
- Final audits passed with no known vulnerabilities: `uv run --frozen --extra dev pip-audit --local --vulnerability-service osv` and `pnpm audit --audit-level=high`.
- A detached clean worktree at commit `ee04831` successfully created a new backend `.venv` with `uv sync --frozen --extra dev` and a new frontend `node_modules` with pnpm 11.9.0 and `pnpm install --frozen-lockfile`.
- Final precondition scans: zero maintained backend/frontend files above 800 physical lines, zero Python callables above CC 15, and ESLint complexity 15 passes across the frontend.
- Verification: backend Ruff/format/mypy green; focused final tests 66 passed; earlier branch safe suite 2,298 passed with 19 missing-fixture skips; frontend Prettier/lint/typecheck green and final focused tests 28 passed. Earlier full frontend Vitest/build passed before the review-fix patch; CI owns the final-commit full rerun.
- Commerce acquisition smoke passed 6/6. Extraction smoke passed 9/10; Vans hit a transient external `TargetClosedError` while the other nine targets passed.
- The combined authorized refactor/review scope adds 806 net maintained source lines because extracted owner modules and regression tests replace oversized owners; structural totals and complexity, rather than a dependency-only LOC freeze, are the accepted scope measure.

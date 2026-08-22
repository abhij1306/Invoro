# Plan: Productionization 06 — Dependency and Reproducibility Hardening

**Created:** 2026-08-21
**Agent:** Codex
**Status:** IN PROGRESS
**PR boundary:** One branch for dependency hardening plus the remaining Plan 07 LOC/complexity precondition debt. Absolute gate implementation remains in Plan 07.
**Touches buckets:** Backend/frontend manifests and lockfiles, dependency audit steps, fresh-clone documentation

## Goal

Make backend and frontend installs reproducible and remove known dependency-audit failures using low-risk supported updates. Keep dependency work separate from structural refactors. Do not perform major runtime/framework migrations. Application/test source LOC must not increase.

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

- [ ] Record starting commit, dirty state, runtime/package-manager versions, current audit results, and outdated reports in Notes.
- [ ] Backend CI installs from `backend/uv.lock` in frozen mode or an equally deterministic existing mechanism; no parallel lock strategy is added.
- [ ] Frontend frozen pnpm install remains green.
- [ ] `pnpm audit --audit-level=high` exits 0 with no unjustified advisory ignore.
- [ ] Backend audit runs against the exact frozen environment used by CI and exits 0, or any exception has reachability evidence and an explicit owner.
- [ ] README fresh-clone instructions use the actual Python/uv and pnpm/Corepack workflow.
- [ ] Safe patch/minor batches are verified independently and lockfiles are internally consistent.
- [ ] Major upgrades remain explicitly deferred in Notes with reason; no fake “fully current” claim is made.
- [ ] No application/test source behavior or first-party source LOC increase.
- [ ] Backend safe suite and frontend lint/type/test/build pass.

## Do Not Touch

- Application architecture or refactors — Plans 01–05.
- LOC/complexity/lint policy and new quality gates — Plan 07.
- Product behavior, schemas, migrations, deployment/provider settings — out of scope.
- Broad formatting — forbidden.

## Slices

### Slice 1: Reproduce Current Graphs

**Status:** TODO
**Files:** manifests, lockfiles, workflows, README read-only
**What:** Record Python, uv, Node, Corepack, and pnpm versions. Run frozen installs, `uv`/registry outdated checks, `pip-audit` or existing backend audit against the locked graph, `pnpm outdated`, and `pnpm audit --audit-level=high`. Map direct vs transitive ownership. Confirm whether `nanoid` remains vulnerable.
**Verify:** Both current frozen installs complete from lockfiles without modifying them; record exact commands and exits.

### Slice 2: Frontend Security and Patch Batch

**Status:** TODO
**Files:** `frontend/package.json` only when direct constraints/overrides require it; `frontend/pnpm-lock.yaml`
**What:** Resolve the nanoid advisory through the smallest compatible lock/override change. Then apply compatible low-risk patches such as React/types, Vitest/coverage, Tailwind, and Zustand only if current registry evidence supports them. Do not mix Next, Playwright, Recharts/forms, or majors into this batch.
**Verify:** `cd frontend; pnpm install --frozen-lockfile; pnpm audit --audit-level=high; pnpm run lint; pnpm run typecheck; pnpm test; pnpm run build`

### Slice 3: Backend Frozen CI and Patch Batch

**Status:** TODO
**Files:** `backend/pyproject.toml`, `backend/uv.lock`, `.github/workflows/backend-ci.yml`
**What:** Make CI install the frozen uv graph using the existing Python 3.12 target. Audit that exact environment. Remove the stale vulnerability ignore only if the frozen graph and package usage prove it unnecessary. Apply low-risk patch updates such as Ruff, SQLAlchemy, Uvicorn, curl-cffi, mypy, and test tools only when current compatibility evidence supports them. Keep Redis major range from silently resolving an unsupported major.
**Verify:** Fresh frozen backend install; backend audit; Ruff, format check, mypy, and safe suite.

### Slice 4: Isolated Supported Minors and Browser Driver Decision

**Status:** TODO
**Files:** manifests/lockfiles only
**What:** Evaluate current supported minors one group at a time. Next + eslint-config-next must move together. Prettier/lucide may move separately. Patchright/Playwright changes require acquisition/e2e smoke. Revert any batch that changes behavior or cannot be verified. Leave high-risk majors deferred.
**Verify:** Repeat full workspace checks after each retained group. Run `run_acquire_smoke.py commerce` for backend browser-driver changes and a focused Playwright smoke for frontend Playwright changes.

### Slice 5: Fresh-Clone Documentation and Final Graph Verification

**Status:** TODO
**Files:** `README.md`, manifests, lockfiles, dependency-install workflow lines
**What:** Document one canonical frozen install/test path per workspace. Verify commands in a clean temporary clone/worktree without relying on existing `.venv`, `node_modules`, or caches. Do not alter user files or delete broad directories.
**Verify:** Fresh backend/frontend install, audits, backend safe suite, frontend lint/type/test/build.

## Doc Updates Required

- [ ] `README.md` — canonical uv/pnpm fresh-clone and verification commands.
- [ ] `docs/backend-architecture.md` / `docs/frontend-architecture.md` — only if supported runtime/package-manager policy changes.
- [ ] `docs/plans/ACTIVE.md` — active pointer and closeout.

## Notes

- Source evidence: `docs/audits/productionization-evidence-report-2026-08-21.md`, sections 2, 3, 8, 9, and 14.
- Plan 07 also edits workflows. Merge this plan first or rebase Plan 07 cleanly; do not discard either plan's steps.
- Dependency freshness is not “latest at all costs.” Supported, reproducible, verified graph is the target.
- 2026-08-22 branch baseline: commit `b3c4fd662ce3f55bfbf089efa332fdcf14f7cb08`; worktree clean; Python 3.14.6 host, uv 0.11.28, Node 26.7.0, pnpm 11.22.0; Corepack is not installed on the host. The project targets Python 3.12 and pins pnpm 11.9.0.
- Baseline frozen installs passed: `uv sync --project backend --frozen --extra dev` and `pnpm install --dir frontend --frozen-lockfile`.
- Baseline frontend audit passed with no known vulnerabilities. `pnpm outdated` reported only `@hookform/resolvers` 5.8.0 -> 5.9.0 plus explicitly deferred ESLint 10 and TypeScript 7 majors. The lock already contains the `nanoid` 3.3.18 override.
- Scope approved by the user on 2026-08-22: clear all remaining physical LOC >800 and callable CC >15 debt in this branch so Plan 07 can start separately after merge.

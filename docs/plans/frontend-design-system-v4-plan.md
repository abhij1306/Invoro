# Plan: Frontend Design System v4 And Debt Reduction

**Created:** 2026-08-10
**Agent:** Codex
**Status:** DONE
**Touches buckets:** frontend design system, app shell, shared UI, frontend CI

## Goal

Port CrawlerAI's v4 visual system and shell to Invoro's Next.js frontend, use local Satoshi and Switzer fonts while retaining Geist Mono, reduce shared UI debt and React Doctor findings, repair frontend CI, and ship the verified work through main without changing product contracts.

## Acceptance Criteria

- [x] CrawlerAI v4 tokens, density, shell, primitives, accessibility, and motion are canonical in Invoro.
- [x] Satoshi display and Switzer body use four local variable WOFF2 files; Geist Mono remains.
- [x] Invoro routes, API behavior, and user workflows remain compatible.
- [x] React Doctor has zero correctness, accessibility, or security errors and no more than 40 total findings.
- [x] Shared frontend architecture is simpler; measured UI/CSS LOC delta is recorded with 15% treated as a directional target.
- [x] Frontend CI uses pnpm and runs formatting, lint, architecture, type, unit, build, and Playwright smoke checks.
- [x] Required CI is green and the pull request is merged into main.

## Do Not Touch

- `backend/` -- no backend contract or behavior changes.
- `.codacy.yaml` -- pre-existing user deletion; preserve and exclude.
- `.deepsource.toml` -- pre-existing user deletion; preserve and exclude.
- CrawlerAI repository -- read-only design source.

## Slices

### Slice 1: Baseline And Canonical Foundations

**Status:** DONE
**Files:** `frontend/app/globals.css`, `frontend/app/layout.tsx`, `frontend/app/fonts/*`, `docs/design.md`
**What:** Record LOC and React Doctor baselines, port v4 tokens and global rules, install approved local fonts, and synchronize design documentation.
**Verify:** formatting, typecheck, build, token guard, font asset inventory.

### Slice 2: Shell And Shared UI Standardization

**Status:** DONE
**Files:** `frontend/components/layout/*`, `frontend/components/ui/*`, affected call sites
**What:** Port shell geometry and consolidate primitives/patterns while preserving Invoro navigation and behaviors; remove superseded duplicates and aliases.
**Verify:** focused layout and primitive tests, lint, typecheck, visual desktop/mobile light/dark pass.

### Slice 3: React Doctor And Architecture Debt

**Status:** DONE
**Files:** reported frontend owners, frontend architecture check and config
**What:** Fix blocking correctness/accessibility/security findings, reduce maintainability/performance findings, and add a regression guard for design-system and shared-module drift.
**Verify:** React Doctor <= 40 with zero blocking categories; architecture and token checks pass.

### Slice 4: CI And Final Verification

**Status:** DONE
**Files:** `.github/workflows/frontend-quality.yml`, `.github/workflows/frontend-playwright-smoke.yml`
**What:** Repair workflows for Corepack/pnpm and complete bounded local static and visual verification.
**Verify:** format check, lint, architecture checks, typecheck, build, Impeccable detector, and CI suites.

### Slice 5: Ship Main

**Status:** DONE
**Files:** repository and GitHub state
**What:** Commit scoped changes, push, open a non-draft PR, wait for green CI, merge, and synchronize local main.
**Verify:** merged PR; local HEAD equals origin/main; user deletions remain preserved.

### Slice 6: Review, Dependency, And Environment Hygiene

**Status:** DONE
**Files:** reviewed frontend owners, dependency manifests and locks, Python/tooling pins, frontend smoke workflow
**What:** Validate and resolve PR bot feedback, harden affected UI behavior, remove unused frontend dependencies, upgrade compatible locks, pin Python to 3.12, and rebuild local environments from clean generated state.
**Verify:** focused UI tests, frontend lint/type/architecture/build, Python 3.12 config tests, frozen lock validation, and green CI.

## Doc Updates Required

- [x] `docs/design.md` -- canonical v4 system and typography.
- [x] `docs/frontend-architecture.md` -- shared UI ownership and CI guard.
- [ ] `docs/CODEBASE_MAP.md` -- only if ownership paths change.

## Notes

- Baseline worktree contained user deletions of `.codacy.yaml` and `.deepsource.toml`.
- CrawlerAI is Vite; only visual system, shell geometry, and reusable patterns port to Next.js.
- React Doctor: 59/100 with 81 findings before; 81/100 with 17 warnings and zero errors after the review pass. The <=40 target remains met.
- Non-test frontend app/components LOC: 28,582 on `main` to 26,516, a reduction of 2,066 lines (7.23%). The 15% target remained directional.
- Local verification: formatting, ESLint, typecheck, token/crawl/frontend architecture guards, production build, nine focused Vitest cases, and Impeccable detector all passed.
- Browser-control runtime was unavailable in this session; responsive/theme behavior is covered by focused shell tests and production build, with full Playwright smoke retained in CI.
- PR review follow-up fixed valid bot findings across identity keys, UTC formatting, storage resilience, accessible controls, dropdown/tooltip behavior, semantic typography, forced-colors focus, table borders, and architecture line counting. Invalid findings were documented rather than implemented.
- Dependency hygiene removed five unused frontend direct dependencies, upgraded compatible frontend/backend locks, pinned Python to the 3.12 family, and rebuilt `.env`, `node_modules`, and `.venv` after deleting generated caches.

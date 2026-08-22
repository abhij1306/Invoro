# Plan: Productionization 05 — Frontend Debt Reduction

**Created:** 2026-08-21
**Agent:** Codex
**Status:** COMPLETE
**PR boundary:** One independent PR. Frontend source, tests, and architecture scripts only.
**Touches buckets:** Next.js routes, Crawl Studio UI, Playground/Selectors UI, API types, frontend tests and architecture scripts

## Goal

Reduce frontend debt without redesigning the UI or changing behavior. Every maintained frontend JS/TS/TSX file must be `<=800` physical lines. Every callable/component must have ESLint cyclomatic complexity `<=15`. Total scoped LOC must decrease. Existing routes, interaction flows, visual design, accessibility behavior, API contracts, and state semantics must remain stable.

## Context for a Fresh Session

The 2026-08-21 audit found seven production files and one test file above 800 lines, plus 42 ESLint complexity violations. Largest hotspots: `CrawlRunScreen` 131, `DataEnrichmentPage` 74, `CrawlConfigScreen` 57, `MarkdownPreview` 52, `getLogIconDescriptor` 52, and `useCrawlRunController` 50. Current code wins over audit counts.

Before code:

1. Read `AGENTS.md`, `docs/frontend-architecture.md`, and the Frontend section of `docs/CODEBASE_MAP.md`.
2. Read `docs/ENGINEERING_STRATEGY.md` principles, AP-5, AP-7, AP-14, AP-15, and File Shape.
3. Read `docs/BUSINESS_LOGIC.md` only for routes/workflows touched.
4. Grep components, hooks, reducers, DTOs, and tests before creating files.

Hard behavior constraints:

- No redesign, copy change, route change, API contract change, new state library, or new design system.
- Keep server data, client state, and presentational ownership where `frontend-architecture.md` assigns them.
- Split JSX by meaningful section and hooks by effect/query/mutation concern.
- Do not convert explicit behavior into generic component factories merely to lower CC.
- Preserve keyboard behavior and accessibility semantics.
- If a split requires changing workflow, navigation, polling, mutation, or API payload behavior, stop and ask the user.

## Scope

Oversized files that must be reduced below 800 physical lines:

- `frontend/components/crawl/crawl-config-screen.tsx` (1323)
- `frontend/components/crawl/crawl-run-screen.test.tsx` (1280)
- `frontend/app/playground/page.tsx` (1144)
- `frontend/components/crawl/crawl-run-screen.tsx` (1140)
- `frontend/lib/api/types.ts` (1072)
- `frontend/components/crawl/log-terminal.tsx` (975)
- `frontend/app/selectors/page-view.tsx` (883)

Complexity scope is all maintained `.ts`, `.tsx`, `.js`, and `.mjs` under `frontend`, excluding generated/build/dependency/coverage artifacts. It includes production code, tests, and architecture scripts. Besides the oversized files, priority callables include:

- `DataEnrichmentPage`, `MarkdownPreview`, `useCrawlRunController`
- monitor and alert forms/reducers
- selector workspace assembly and row merging
- Playground workflow/normalizers
- Dashboard, Product Intelligence, and app-shell components
- shared dropdown/field keyboard and variant logic
- `frontend/scripts/check-crawl-architecture.mjs:scanTemplateLiteral`

## Acceptance Criteria

- [x] Record starting commit, dirty state, scoped physical LOC, files over 800, and all ESLint CC violations in Notes.
- [x] Every maintained frontend JS/TS/TSX file is `<=800` physical lines.
- [x] `pnpm exec eslint . --rule "complexity: [error, 15]" --max-warnings=0` exits 0.
- [x] Scoped physical LOC is lower than baseline.
- [x] All existing routes, UI flows, visual states, accessibility behavior, API requests, and DTO shapes remain stable.
- [x] Existing design tokens/components are reused; no redesign or parallel component system is introduced.
- [x] Exact duplicate logic is deleted after jscpd/search validation; intentional fixture/UI repetition is not abstracted blindly.
- [x] Existing lint, format, typecheck, architecture checks, unit tests, and production build pass.
- [x] No backend, dependency, lockfile, workflow, or broad-format-only changes are included.

## Do Not Touch

- `backend/**` — Plans 01–04, 06–07.
- `frontend/package.json`, `frontend/pnpm-lock.yaml` — Plan 06 unless a script path must be updated because a file moved; do not update package versions.
- `.github/workflows/**`, ESLint/Prettier policy — Plan 07.
- CSS/design direction, copy, analytics, API behavior — out of scope.

## Slices

### Slice 1: Baseline and Component Ownership Map

**Status:** COMPLETE
**Files:** full frontend scope; architecture docs and tests read-only
**What:** Record physical LOC and exact ESLint complexity JSON. Run jscpd as a lead. Map every violation to an existing route, component, hook, reducer, normalizer, or API-domain owner. Identify deletions and split seams before editing.
**Verify:** `cd frontend; pnpm run lint:eslint; pnpm run typecheck; pnpm test`

### Slice 2: Crawl Studio Screens and Log Terminal

**Status:** COMPLETE
**Files:** crawl config/run screens, controller, log terminal/utils, crawl screen tests, current crawl components
**What:** Keep controllers/hooks responsible for state and effects; split render sections into named presentational components. Replace icon/stage switches with data maps when semantics are identical. Split tests by observable screen behavior. Delete duplicated rendering/normalization. Keep every destination file under 800 and callable under 16.
**Verify:** Run crawl-related Vitest files, `pnpm run check:crawl-architecture`, ESLint complexity command, and typecheck.

### Slice 3: Playground, Selectors, and API Types

**Status:** COMPLETE
**Files:** oversized Playground/Selectors files, workflow/normalizer owners, `lib/api/types.ts`, focused tests
**What:** Split Playground stage UI/log humanization, selector reducer/suggestion rows, and API DTOs by existing domain. Preserve import ergonomics with explicit public barrels only where one already exists. Do not create circular barrels or duplicate DTOs.
**Verify:** Run focused Playground, selector, API client/type tests; then architecture checks and typecheck.

### Slice 4: Remaining Frontend Complexity

**Status:** COMPLETE
**Files:** every remaining file reported by the exact ESLint complexity command
**What:** Reduce Data Enrichment, Markdown, monitor/alert, dashboard, Product Intelligence, app-shell, shared UI, and architecture-script complexity. Prefer named predicates, section components, and effect/query separation. Preserve reducer and keyboard semantics.
**Verify:** `cd frontend; pnpm exec eslint . --rule "complexity: [error, 15]" --max-warnings=0`; run focused tests for every touched owner.

### Slice 5: Metrics and Full Frontend Verification

**Status:** COMPLETE
**Files:** all touched frontend files; docs if stable ownership moved
**What:** Re-run physical LOC, ESLint complexity, jscpd, normal lint, format check, typecheck, architecture checks, unit tests, and build. Prove total scoped LOC decreased.
**Verify:** `cd frontend; pnpm run format:check; pnpm run lint; pnpm run typecheck; pnpm test; pnpm run build`

## Doc Updates Required

- [x] `docs/frontend-architecture.md` — stable component/hook/type ownership changes.
- [x] `docs/CODEBASE_MAP.md` — only for meaningful route/component ownership changes.
- [x] `docs/BUSINESS_LOGIC.md` — no change required; behavior did not change.
- [x] `docs/plans/ACTIVE.md` — active pointer and closeout.

## Notes

- Source evidence: `docs/audits/productionization-evidence-report-2026-08-21.md`, sections 4–8.
- `frontend/scripts/check-crawl-architecture.mjs` currently permits higher file budgets. Do not change gate policy here; Plan 07 replaces the budgets after this plan is green.
- UCP Audit, Run Trace/AI Observability, and the Design Crawl feature were removed before this plan under Productionization 04; do not recreate or baseline them.
- Baseline commit: `60868d883d8a96c408be35ad9a6c49f16caec465`; worktree clean.
- Baseline scoped physical LOC: 32,439. Final scoped physical LOC: 31,809 (down 630).
- Baseline oversized files: `crawl-config-screen.tsx` 1,259; `crawl-run-screen.test.tsx` 1,229; `crawl-run-screen.tsx` 1,124; `playground/page.tsx` 1,118; `log-terminal.tsx` 975; `selectors/page-view.tsx` 883; `lib/api/types.ts` 872. Final count over 800: zero; largest file is `log-terminal.tsx` at 788.
- Baseline exact complexity scan: 36 violations. Owners were Crawl config/run screens and controller; log terminal stage/group/icon rendering; Markdown parsing; Playground page/workflow/normalizer; Data Enrichment; selector page/reducer/row merge/workspace assembly; monitor and alert forms, reducer, header, list item, and alert builder; Dashboard; Product Intelligence page/normalizers; app shell; dropdown and field primitives; API/config dispatch helpers; and the crawl architecture template scanner. Final exact scan: zero violations.
- `jscpd@4.0.5` reported 24 clones / 1.46% duplicated lines. The refactor-created 324-line crawl test preamble clone was removed into `crawl-run-screen.test-harness.tsx`; remaining hits are pre-existing fixtures, short UI parallels, or unrelated cross-owner similarities and were not abstracted blindly.
- Verification: format check; normal ESLint; exact CC 15 ESLint; typecheck; crawl architecture check; 66 focused crawl tests; full Vitest suite (31 files, 170 tests); production Next.js build; `git diff --check`.

# Frontend Architecture

> Last updated: 2026-05-28

This document describes the live frontend structure, what it actually calls in the backend, and the remaining client/backend drift that should stay visible.

## 1. Stack and Role

Frontend is a Next.js App Router UI for:

- auth/session handling
- crawl configuration and launch
- run monitoring and record inspection
- selectors workflow
- dashboard/history/jobs operations
- admin users and LLM configuration

Key client libraries:

- Next.js App Router
- React Query
- Lucide icons

## 2. Route Map

App routes under `frontend/app`:

- `/` -> redirect-style entry page
- `/login`
- `/register`
- `/dashboard`
- `/playground`
- `/crawl`
- `/crawl/category`
- `/crawl/pdp`
- `/crawl/bulk`
- `/runs`
- `/runs/[run_id]`
- `/monitors`
- `/monitors/new`
- `/monitors/[id]`
- `/alerts`
- `/alerts/new`
- `/alerts/[id]`
- `/jobs`
- `/selectors`
- `/selectors/manage`
- `/admin/users`
- `/admin/llm`

Important route behavior:

- `/crawl` switches between config mode and run workspace based on `run_id`
- `/crawl/category`, `/crawl/pdp`, and `/crawl/bulk` are route shims into `/crawl?...`
- `/runs/[run_id]` routes back into the crawl workspace
- AWS demo builds set `NEXT_PUBLIC_AWS_DEMO_MODE=true`; the proxy returns 404 for `/monitors*` and `/alerts*`, while the shell hides monitoring navigation and notification requests

## 3. Main Frontend Subsystems

### 3.1 App shell and auth

Primary files:

- `components/layout/app-shell.tsx`
- `components/layout/app-shell.module.css`
- `components/layout/auth-shell.module.css`
- `components/layout/auth-session-query.ts`
- `components/layout/top-bar-context.tsx`
- `app/layout.tsx`
- `components/ui/patterns.tsx` for shared operator-page section shells used across non-crawl app surfaces

Responsibilities:

- session gating
- signed-in identity display and per-user logout; logout clears the complete query cache before routing to `/login` so a later account cannot inherit cached workspace data
- shell layout and nav
- notification menu presentation in `components/layout/notification-menu.tsx`
- demo-mode visibility and route policy from `lib/config/demo-mode.ts`
- auth-route vs app-route split
- header state
- theme toggle and common shell framing

### 3.2 API contract layer

Primary files:

- `lib/api/client.ts`
- `lib/api/index.ts`
- `lib/api/types.ts`
- `lib/api/monitor-types.ts`

Responsibilities:

- all backend HTTP calls
- API typing
- monitor and alert DTO ownership in the monitor-specific type module, re-exported by `types.ts`
- auth-aware fetch wrapper
- URL helpers for review HTML and selector preview HTML

This layer is the frontend/backend contract chokepoint.

### 3.3 Crawl config and dispatch

Primary files:

- `components/crawl/crawl-config-screen.tsx`
- `components/crawl/crawl-config-screen-content.tsx`
- `components/crawl/crawl-config-advanced.tsx`
- `components/crawl/use-crawl-config.ts`
- `components/crawl/use-crawl-config-lifecycle.ts`
- `components/crawl/domain-surface-config.ts`
- `components/crawl/crawl.module.css`
- `components/crawl/shared.ts` for pure types and helpers
- `components/crawl/shared-components.tsx` for the compatibility component surface
- `lib/constants/crawl-defaults.ts`

Responsibilities:

- choose domain/surface tab/mode
- own Crawl Studio form validation and manual field arrays through React Hook Form and Zod
- keep form state/effects in the screen model, target and quick settings in the content owner, and field/advanced controls in their named sections
- coordinate one-shot prefill, saved run-profile loading, dirty-edit protection, and stale domain-memory responses in the feature lifecycle hook
- derive surface from the domain/tab dispatch map
- build dispatch payload
- collect advanced settings and additional fields
- submit crawl or CSV run

Current UI settings behavior reflects the backend contract:

- `advanced_enabled`
- `advanced_mode`
- `request_delay_ms`
- `max_records` as a target count for stopping after a page, not a strict row cap
- `respect_robots_txt`
- proxy input
- additional fields
- additional fields are dispatched as the operator typed them (trimmed/deduped only); the UI no longer rewrites labels like `Features & Benefits` into snake_case before the backend sees them
- Crawl Studio domain options live in `domain-surface-config.ts`: Content, Commerce, Jobs, Automobiles, Article, and Forum Thread.
- Surface tabs adapt by domain. Forum Thread renders one tab and hides the mode picker.

### 3.4 Run workspace

Primary files:

- `components/crawl/crawl-run-screen.tsx`
- `components/crawl/use-crawl-run-screen-model.ts`
- `components/crawl/crawl-run-screen-content.tsx`
- `components/crawl/crawl-run-output-content.tsx`
- `components/crawl/use-crawl-run-controller.ts`
- `components/crawl/crawl-diagnostics.ts`
- `components/crawl/use-run-workspace.ts`
- `components/crawl/use-run-polling.ts`
- `components/crawl/crawl-run-store.ts`
- `components/crawl/alert-builder-drawer.tsx`
- `components/crawl/shared.ts` for pure types and helpers
- `components/crawl/shared-components.tsx` for the compatibility component surface

Responsibilities:

- poll run state while active through TanStack Query `refetchInterval`
- show records, JSON, and logs
- consume websocket logs when available
- show quality/verdict/progress signals
- coordinate derived record selection, result handoffs, run controls, and run-change UI reset through the crawl-run controller
- keep polling/effects in the run-screen model, workspace chrome in the screen-content owner, and output-tab rendering in the output-content owner
- normalize open crawl acquisition, phase timing, confidence, and LLM source diagnostics before renderers consume them
- expose pause/resume/kill and export actions
- keep run workspace UI coordination in the crawl Zustand store, not in server-query state
- build product alert rules from run records in the dedicated alert drawer

Important live data features:

- run records use cleaned `data`, `review_bucket`, and `source_trace`
- provenance API is typed and available through `getRecordProvenance`
- log websocket fallback is built into the screen

### 3.5 Operator surfaces

Primary files:

- `app/playground/page.tsx`
- `app/playground/playground-view.tsx`
- `app/playground/playground-panels.tsx`
- `app/playground/use-playground-workflow.ts`
- `app/playground/playground-normalizers.ts`
- `app/dashboard/page.tsx`
- `app/runs/page.tsx`
- `app/monitors/*`
- `app/jobs/page.tsx`
- `app/selectors/page.tsx`
- `app/admin/users/page.tsx`
- `app/admin/llm/page.tsx`

Responsibilities:

- keep Playground route composition thin while stage layout and reusable panels live in their named owners

- guided playground flow for URL intake, product discovery, product selection, PDP extraction, pipeline launch, and unified results, with workflow queries/transitions owned by `use-playground-workflow.ts` and tolerant payload shaping owned by `playground-normalizers.ts`
- single-page source/rendered-DOM technical audit workspace with deterministic checks and JSON/Markdown exports
- dashboard metrics and recent runs
- run history
- monitor/alert list, creation, detail, event, history, current snapshot inspection, and webhook delivery log
- active jobs view
- selector picker/test/save workflow
- domain-memory management across domains and surfaces
- admin user management
- LLM provider/config/cost-log management

### 3.6 UI ownership and style policy

Primary files:

- `components/ui/button.tsx`, `badge.tsx`, `input.tsx`, `card.tsx`, `metric.tsx`, `table.tsx`, `alert.tsx`, and `dialog.tsx` for typed primitive owners
- `components/ui/primitives.tsx` as a thin compatibility barrel; dropdown, field, skeleton, toggle, tooltip, and typography each have focused owners
- `components/ui/patterns.tsx` as a thin compatibility barrel over focused control, data-display, page-header, run-workspace, and section modules
- `components/layout/app-shell.tsx`, `sidebar.tsx`, and `logo-mark.tsx` for separate shell, navigation, and brand ownership
- `app/product-intelligence/product-intelligence-components.tsx`, `product-intelligence-results.tsx`, and `product-intelligence-candidate-card.tsx` for Product Intelligence local UI pieces, result summaries, source-vs-candidate comparison rows, confidence reason chips, and URL selection actions; crawl result screens can prefill Product Intelligence from both listing and ecommerce detail records
- `components/monitors/*` for Monitor and Alert Management list/detail/form/event/history/snapshot components

Global CSS policy:

- `frontend/pnpm-lock.yaml` is the canonical frontend dependency graph; local verification and CI use the package-manager pin in `package.json` with `pnpm install --frozen-lockfile`.
- `app/globals.css` owns tokens, reset, shared browser defaults, animations, and cross-feature utilities only.
- App/auth shell CSS lives under `components/layout/`.
- Crawl Studio feature CSS lives under `components/crawl/`.
- Dense table geometry and semantic styling live in the table primitive and global design tokens.
- New JSX should use semantic Tailwind tokens such as `bg-background`, `text-muted`, `border-border`, and `shadow-card`. Raw `bg-[var(--...)]`, `text-[var(--...)]`, `border-[var(--...)]`, and `shadow-[var(--...)]` escapes are blocked by `frontend/scripts/check-token-escapes.mjs`.
- `frontend/scripts/check-frontend-architecture.mjs` ratchets shared-owner sizes, required design-system owners, local font assets, and explicit transition properties. Frontend CI runs both guards through pnpm.

## 4. Live Backend API Usage

The frontend currently uses live backend routes for:

- auth: `/api/auth/*`
- dashboard: `/api/dashboard`
- crawls: `/api/crawls/*`
- records: `/api/crawls/{id}/records`
- provenance: `/api/records/{id}/provenance`
- exports: `/api/crawls/{id}/export/*`
- logs + websocket: `/api/crawls/{id}/logs`, `/api/crawls/{id}/logs/ws`
- review: `/api/review/{id}`, `/api/review/{id}/artifact-html`, `/api/review/{id}/save`
- selectors: `/api/selectors`, `/api/selectors/suggest`, `/api/selectors/test`, `/api/selectors/preview-html`
- users: `/api/users`
- llm: `/api/llm/providers`, `/api/llm/configs`, `/api/llm/test-connection`, `/api/llm/cost-log`
- jobs: `/api/jobs/active`
- monitors: `/api/monitors`, `/api/monitors/{id}`, `/api/monitors/{id}/run/now`, `/api/monitors/{id}/events`, `/api/monitors/{id}/history`, `/api/monitors/{id}/snapshot/current`
- alerts: `/api/alerts`, `/api/alerts/{id}`, `/api/alerts/{id}/test`, `/api/alerts/{id}/history`, `/api/alerts/{id}/deliveries`
- playground: `/api/playground/sessions`, `/api/playground/sessions/{id}`, `/api/playground/sessions/{id}/discover`, `/api/playground/sessions/{id}/select`, `/api/playground/sessions/{id}/extract`, `/api/playground/sessions/{id}/pipeline`, `/api/playground/sessions/{id}/results`
- notifications: `/api/notifications`, `/api/notifications/unread-count`, `/api/notifications/{id}/read`, `/api/notifications/monitors/{id}/read`

## 5. Known Client/Backend Drift

There is still some API-surface drift and it should remain documented:

- `frontend/lib/api/index.ts` exposes `previewSelectors()` for `/api/review/{run_id}/selector-preview`, but that backend route does not exist.
- `ReviewPayload` types in the frontend still include `selector_memory` and `selector_suggestions`, while the current backend review response is centered on run, canonical/discovered fields, mapping, and records.
- The main selector UX is no longer LLM-first on `/selectors`; older docs claiming “selectors page missing backend integration” are stale.

## 6. Current Data Contracts That Matter To Frontend

### CrawlRun

The frontend expects:

- `status`
- `surface`
- `settings`
- `requested_fields`
- `result_summary`

### CrawlRecord

The frontend expects:

- `data`
- `raw_data`
- `discovered_data`
- `source_trace`
- optional `review_bucket`
- optional `provenance_available`

### Provenance

The frontend has a typed provenance object:

- `raw_data`
- `discovered_data`
- `source_trace`
- `manifest_trace`
- `raw_html_path`

### Selectors

The selectors UI is built on:

- selector CRUD records, now queryable across all surfaces for a domain when `surface` is omitted
- preview HTML loaded into a same-origin iframe so the selector tool can compute XPath directly from the loaded DOM
- manual test response with count and matched value
- optional LLM suggestion flow from Crawl Studio field configuration, not from the selector tool page
- a dedicated `/selectors/manage` domain-memory surface for edit/delete/toggle operations

### LLM Admin

The admin LLM UI is built on:

- provider catalog
- config CRUD
- connection tests
- cost log listing

## 7. Testing Surface

Frontend tests currently cover:

- auth session query
- API client behavior
- crawl config screen
- selector helper logic
- crawl run screen
- shared crawl helpers
- run polling

There is also Playwright e2e coverage under `frontend/e2e`.

Canonical frontend quality checks are `pnpm format:check`, `pnpm lint`, `pnpm typecheck`, `pnpm test`, and `pnpm build`. `pnpm check:quality-gates` proves the exact 800/801 physical-line and 15/16 complexity boundaries with temporary fixtures.

## 8. Architectural Notes

- The frontend is intentionally thin on domain logic; the backend owns crawl semantics.
- `lib/api/index.ts` should remain the single access layer for backend calls.
- `components/crawl/shared.ts` owns pure crawl types and helpers; `shared-components.tsx` owns the compatibility component surface. Do not recombine them.
- `components/ui/patterns/` owns shared operator-page framing while `patterns.tsx` remains re-exports only.
- `components/ui/dialog.tsx` owns destructive confirmations; browser `alert()` and `confirm()` are not used in app/components code.
- When backend record contracts change, update `lib/api/types.ts` and this doc together.

## 9. Companion Docs

- [../AGENTS.md](../AGENTS.md)
- [backend-architecture.md](backend-architecture.md)
- [ENGINEERING_STRATEGY.md](ENGINEERING_STRATEGY.md)
- [INVARIANTS.md](INVARIANTS.md)

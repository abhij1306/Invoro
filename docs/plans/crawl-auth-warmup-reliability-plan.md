# Plan: Crawl Reliability, Logout, and Warmup Removal

**Created:** 2026-08-22
**Agent:** Codex
**Status:** IN PROGRESS
**Touches buckets:** crawl orchestration, authentication, frontend shell, browser acquisition, runtime configuration, architecture docs

## Goal

Prevent batch crawls from sharing SQLAlchemy sessions across concurrent work, add safe per-user logout and account switching, and remove browser-origin warmup so Patchright and real Chrome navigate directly to targets and recover challenges in place.

## Acceptance Criteria

- [ ] An 80-URL batch at concurrency 4 cannot overlap URL-worker database sessions and does not fail with SQLAlchemy's connection-provisioning concurrency guard.
- [ ] Serial and parallel URL processing both use one owned session per URL while the coordinator alone owns run progress.
- [ ] `POST /api/auth/logout` is idempotent, clears the cookie, revokes only the current user's sessions, and the UI clears cached account data.
- [ ] Patchright and real Chrome perform no origin warmup and retain direct-target challenge recovery and real-Chrome storage state.
- [ ] Frontend checks and targeted acquisition smoke checks pass.
- [ ] `python -m pytest tests -q -m "unit or component or regression"` exits 0.

## Do Not Touch

- `.env` — contains user-owned credentials and environment configuration.
- `frontend/components/crawl/log-terminal.tsx` — unrelated user working-tree change.
- `docs/audits/*` — archived documents are explicitly outside scope.
- Run `4` database history — preserve the original failure record.

## Slices

### Slice 1: Isolate crawl sessions and bound scheduling
**Status:** DONE
**Files:** crawl batch runtime/parallel owners, crawl regression tests, invariants
**What:** Give every URL an owned session in serial and parallel modes, use a fixed worker pool, return plain results to the coordinator, and preserve controls and record limits.
**Verify:** Targeted crawl regressions cover 80 URLs, maximum worker count, distinct sessions, URL failure isolation, ordering, and controls.

### Slice 2: Add per-user logout and account switching
**Status:** DONE
**Files:** backend auth/dependencies/config, frontend API/app shell/sidebar, auth tests and docs
**What:** Add idempotent token-version logout, cookie deletion, visible identity/logout controls, and unconditional client cache cleanup.
**Verify:** Backend and frontend auth tests pass, including cross-account isolation and failed-request cleanup.

### Slice 3: Remove origin warmup
**Status:** DONE
**Files:** browser acquisition/runtime/config owners, acquisition tests, architecture docs
**What:** Delete warmup execution and configuration while preserving direct target navigation, challenge recovery, and storage-state loading.
**Verify:** Browser tests prove target-first navigation, storage-state reuse, recovery, and absence of warmup behavior.

### Slice 4: Broad verification and closeout
**Status:** IN PROGRESS
**Files:** plan tracking and any required documentation corrections
**What:** Run backend, frontend, acquisition, extraction, and acceptance checks; perform the real 80-URL acceptance run when the local services permit it.
**Verify:** Required quality gates pass, or environment-only blockers are recorded precisely.

## Doc Updates Required

- [ ] `docs/backend-architecture.md` — direct-navigation acquisition and URL-session ownership.
- [ ] `docs/frontend-architecture.md` — authenticated shell logout behavior.
- [ ] `docs/CODEBASE_MAP.md` — remove deleted warmup owner.
- [ ] `docs/INVARIANTS.md` — session ownership and no-warmup contracts.
- [ ] `docs/ENGINEERING_STRATEGY.md` — no update expected; check after implementation.

## Notes

- User approved this plan and requested implementation on 2026-08-22.
- Existing `.env` admin was verified during planning without exposing its values.
- No database migration or crawl-resume architecture is in scope.
- Slice 1 found the concrete race: URL tasks read an expired `run.id` attribute from the coordinator ORM instance, causing concurrent lazy SQL on the coordinator session. Workers now capture a primitive id before scheduling, own sessions per URL in both modes, and run through a fixed worker pool. Targeted regressions: 13 passed.
- Slice 2 added idempotent current-user token-version revocation, cookie deletion, sidebar identity/logout, and unconditional query-cache clearing. Backend auth checks: 30 passed. Frontend checks: typecheck passed; full Vitest suite 181 passed.
- Slice 3 deleted the warmup owner, runtime calls, configuration, stale telemetry, and warmup-only tests. Direct-navigation/challenge/config checks: 108 passed. Focused direct-navigation and real-Chrome state checks: 24 passed.

# Plan: Security Audit Remediation

**Created:** 2026-05-21
**Agent:** Codex
**Status:** DONE
**Touches buckets:** api, core, frontend, CI/docs

## Goal

Harden authentication, session transport, security headers, CORS, and dependency hygiene based on repo-verified findings from the security audit. Done means browser auth is cookie-first and safer, backend/frontend responses ship baseline security headers, auth receives stricter throttling and logging, password hashing upgrades without a DB migration, CI gains vulnerability scanning, and focused tests pass.

## Acceptance Criteria

- [x] Login sets a secure cookie outside dev/test, uses explicit path/max-age, and no longer returns the JWT in JSON.
- [x] Auth-specific throttling and structured auth logging are in place.
- [x] Password hashing uses a stronger modern hash for new passwords while legacy PBKDF2 hashes still verify and upgrade on login.
- [x] JWT expiry reduced to improve session security by shortening the token TTL.
- [x] Backend and frontend emit the planned security headers; backend CORS is narrowed.
- [x] CI includes dependency vulnerability scanning and Dependabot config exists.
- [x] Relevant backend and frontend tests pass.

## Do Not Touch

- `backend/app/services/config/extraction_rules/_common.py` — unrelated dirty user changes
- `backend/app/services/js_state/state_normalizer/__init__.py` — unrelated dirty user changes
- `backend/app/services/js_state/state_normalizer/_common.py` — unrelated dirty user changes

## Slices

### Slice 1: Plan Record And Activation
**Status:** DONE
**Files:** `docs/plans/security-audit-remediation-plan.md`, `docs/plans/ACTIVE.md`
**What:** Create a standalone plan file for this user-requested security work and intentionally switch `ACTIVE.md` away from the blocked plan.
**Verify:** Plan file exists and `ACTIVE.md` points to it.

### Slice 2: Backend Auth Hardening
**Status:** DONE
**Files:** `backend/app/api/auth.py`, `backend/app/core/security.py`, `backend/app/core/config.py`, `backend/app/services/auth_service.py`, `backend/app/services/config/*`
**What:** Make login cookie-first, shorten JWT TTL, add auth-specific throttling/logging, and upgrade password hashing with legacy compatibility.
**Verify:** Focused backend auth tests pass.

### Slice 3: Backend Transport Hardening
**Status:** DONE
**Files:** `backend/app/main.py`, `backend/app/services/config/*`
**What:** Add security headers middleware and narrow CORS methods/headers.
**Verify:** Middleware/CORS tests pass.

### Slice 4: Frontend Contract And Headers
**Status:** DONE
**Files:** `frontend/lib/api/types.ts`, `frontend/e2e/smoke.spec.ts`, `frontend/next.config.ts`
**What:** Align login contract with cookie-only auth and add frontend security headers.
**Verify:** Frontend unit/e2e tests covering login and headers pass.

### Slice 5: CI And Dependency Hygiene
**Status:** DONE
**Files:** `.github/workflows/backend-ci.yml`, `.github/workflows/frontend-playwright-smoke.yml`, `.github/dependabot.yml`
**What:** Add dependency scans and automated update config.
**Verify:** Workflow definitions lint visually and contain the expected steps.

## Doc Updates Required

- [x] `docs/audits/security-audit.md` — correct audit assumptions to match repo truth

## Notes

- Security work is intentionally split from the previously blocked Agentic Delta plan by explicit user request.
- New password hashes use `argon2-cffi` directly because the installed `passlib+bcrypt` combination was not stable under this local Python 3.14 environment; legacy PBKDF2 upgrade behavior remains intact.

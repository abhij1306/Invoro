# Invoro pre-launch security and production-readiness review

**Date:** 2026-08-23
**Scope:** Current workspace on `main` (`d569a6d`) plus uncommitted working-tree files. Application code was **not** modified.
**Product:** Invoro — FastAPI + PostgreSQL + Redis + Celery + Playwright backend; Next.js frontend. Auth is first-party email/password + HttpOnly JWT cookie; public `/api/v1` uses hashed API keys.
**Intended tenancy (from code/docs):** Self-hosted / single-admin by default (`REGISTRATION_ENABLED=false`). Phase-2 multi-tenant SaaS is **not** complete (`docs/plans/phase-2-plan.md`). Public API v1 is described as a thin launch surface.

---

## Launch verdict

**NO-GO** for internet-facing production.

Do not ship a public or cloud-hosted instance until the P0/P1 items below are fixed or explicitly accepted with compensating controls. A **closed, single-admin, private-network** install can proceed only after the listed conditions are met (see Unverified / conditions).

This supersedes `docs/audits/security-audit.md` (2026-05-21). Several May findings are already fixed in code (Secure cookie in non-dev, Argon2id hashing, auth rate limits, security headers, CORS method/header allowlists, pip-audit / pnpm audit / Dependabot / CodeQL / Gitleaks).

---

## Release blockers (P0 / P1)

### P1 — Outbound webhook SSRF (cloud metadata / internal network)

| | |
|---|---|
| **Component** | `backend/app/schemas/alert.py` (`validate_webhook_url`), `backend/app/services/monitor_webhook_service.py` |
| **Evidence** | Webhook URLs are accepted if they start with `http://` or `https://` only. Delivery uses `httpx.AsyncClient(...).post(str(monitor.webhook_url), ...)` with **no** `validate_public_target` / `ensure_public_crawl_targets`. Crawl/selector fetches **do** use `url_safety.py`. The current HTTPX client does not enable redirects. |
| **Failure mode** | Authenticated user (or admin) sets `webhook_url` to `http://169.254.169.254/`, `http://127.0.0.1:6379/`, or a DNS name that resolves to a private address at connection time. On alert fire, the **server** POSTs there. Error strings may land in `monitor_webhook_deliveries.error_message`. |
| **Fix** | Reuse `validate_public_target` (or equivalent) at save and immediately before delivery, then enforce public non-link-local destination IPs at connection time through a pinned transport or egress proxy. Keep redirects disabled; if later enabled, apply the same policy to every hop. Prefer HTTPS-only webhooks in production. |
| **Status** | Open. Not fixed (audit-only). |

### P1 — Authenticated HTML preview is an XSS proxy on the API origin

| | |
|---|---|
| **Component** | `backend/app/api/selectors.py` `GET /api/selectors/preview-html`; `backend/app/services/selectors_runtime.py` `build_preview_html`; `frontend/app/selectors/page-view.tsx` |
| **Evidence** | Endpoint requires login, fetches attacker-chosen `http(s)` URL (after SSRF host checks), then returns **unsanitized remote HTML** as `text/html` from the **API origin**. `build_preview_html` only injects `<base href>`. UI loads it in `<iframe sandbox="allow-same-origin">` (no `allow-scripts`) — that **does not** protect a **top-level** navigation to the same URL. `SameSite=lax` **does** send the session cookie on a top-level GET. |
| **Failure mode** | Victim is logged in and opens `/api/selectors/preview-html?url=https://attacker/...`. Attacker HTML/JS runs on the API origin and can call mutating APIs with the victim cookie (session riding). |
| **Fix** | Do not serve third-party HTML with an executable MIME type on the app origin. Options: `Content-Type: text/plain`, `Content-Security-Policy: sandbox`, `Content-Disposition: attachment`, script stripping **and** `X-Frame-Options`/CSP on that route; keep iframe `sandbox` without `allow-scripts`. |
| **Status** | Open. |

### P1 — Stock Docker Compose is not a production deployment

| | |
|---|---|
| **Component** | `docker-compose.yml` (`environment: &backend_env` → `APP_ENV: development`); published `5432` / `6379`; Redis without AUTH |
| **Evidence** | Compose **overrides** `.env` `APP_ENV` to `development`. `secure_transport_required()` then treats the process as non-prod: session cookie `Secure` is off, HSTS is skipped, and `_check_secret_defaults()` **warns instead of crashing** on placeholder JWT/encryption keys. Postgres and Redis are bound to the host. Redis has no password. Frontend image ARG defaults `NEXT_PUBLIC_API_BASE_URL` to `http://127.0.0.1:9000`. |
| **Failure mode** | Operator “ships” `docker compose up` to a public VM: HTTP cookies, default-secret warning only, database/Redis reachable from the network, browser talking to the wrong API URL. |
| **Fix** | Production overlay: `APP_ENV=production` (or `staging`), no host publish for DB/Redis, Redis AUTH, TLS terminator, explicit `FRONTEND_URL` / `FRONTEND_ORIGINS` / `NEXT_PUBLIC_API_BASE_URL`. Do not use the current compose file as-is. |
| **Status** | Open. No k8s/helm/prod compose in repo. |

### P1 — Domain-scoped browser cookie memory is global (blocks multi-user / SaaS)

| | |
|---|---|
| **Component** | `backend/app/models/domain_memory.py` `DomainCookieMemory` unique on `domain` only; `backend/app/services/acquisition/cookie_store.py` `load_storage_state_for_domain` / `persist_storage_state_for_domain`; `GET /api/crawls/domain-memory/cookies` lists metadata for any authenticated user |
| **Evidence** | Storage state (cookies / origins) is keyed by domain, not `user_id`. Browser pool loads domain state for later runs on that host. Dashboard cookie list does **not** return raw cookie values (counts only) — reuse in the **browser worker** is the issue. Selectors and run profiles are also global per domain/surface. |
| **Failure mode** | User A’s logged-in crawl cookies are applied to User B’s crawl of the same site (session hijack of the **target** site; possible cross-tenant data in extracts). Shared selector/profile memory leaks operational config. Acceptable only for a **single operator** with `REGISTRATION_ENABLED=false`. |
| **Fix** | Scope cookie memory (and likely run profiles) by `(user_id, domain)` or disable domain cookie reuse when more than one user exists. Keep `REGISTRATION_ENABLED=false` until then. |
| **Status** | Open. Treat as launch blocker for any second account or public registration. |

No **P0** (unauthenticated RCE, trivial account takeover without user action, or unauthenticated destructive write) was evidenced in this pass.

---

## Important findings (P2)

1. **CSV upload has no size cap** — `crawls_create_csv` does `await file.read()` then decode. Authenticated DoS / memory exhaustion. Add `UploadFile` size limit and a max URL count (already likely later in CSV parse — confirm and enforce at the HTTP boundary).

2. **`/api/metrics` is unauthenticated** — `backend/app/main.py` exposes Prometheus text; rate-limit exempt. Fine behind a private scrape network; hostile on the public internet (run volume, pool size). Bind to internal network or require scrape auth.

3. **FastAPI `/docs`, `/redoc`, `/openapi.json` left at defaults** — no `docs_url=None` in production. Schema and auth model are public. Disable in non-dev or protect them.

4. **In-process rate limits** — dashboard, auth, and public API limits live in `app.state` deques, not Redis. Multiple API replicas do not share budgets. Attackers reset limits by hitting another replica.

5. **Register has no password policy** — `UserCreate.password` is unconstrained; Argon2id hashing is used, but `"a"` is a valid password if `REGISTRATION_ENABLED=true`. Admin bootstrap has a 16-char complexity check; registration does not.

6. **No password reset / MFA / email verification** — expected for a closed admin tool; not acceptable for open signup. There is no recovery flow to audit.

7. **Frontend production CSP is Next-only** — `frontend/proxy.ts` sets CSP in `NODE_ENV=production`. Backend responses have nosniff / frame-options / referrer / permissions-policy / conditional HSTS, **no CSP**. Preview HTML (P1) is the urgent gap.

8. **CORS `allow_credentials=True` with origin allowlist** — `get_frontend_origins()` from `FRONTEND_ORIGINS` or `FRONTEND_URL`. Mis-set origins (wildcard not used in code — good) or extra origins expand CSRF surface. No CSRF token; reliance on SameSite=lax + origin allowlist. Keep origins exact.

9. **JWT HS256, 1h TTL, `ver` claim, no `aud`/`iss`** — improved vs May (was 24h). Symmetric secret must stay server-only. Fine for a single API; document rotation.

10. **`.gitignore` gap** — `.env` and `*.env` are ignored; tracked template is `.env.example`. `.env.production` / `.env.local` at **repo root** are not matched by `*.env`. Frontend ignores `*.local`. Add `.env.*` / `!.env.example`.

11. **Compose Postgres 15 vs CI Postgres 16** — version skew for migrations/ops.

12. **Worker pickle IPC** — `extraction_process.py` pickles to a local subprocess. Trusted boundary if the child is the same image; do not ever unpickle client input (current path is internal).

13. **Public extract is a paid-cost crawler** — API-key + 60/min extract limit. Still a bill-shock / abuse path if keys leak. Keys hashed at rest (`hmac` with `jwt_secret_key`); plaintext shown once at create.

14. **Unrelated dirty tree** — extraction/runtime files are modified locally. This review did not treat those as shipped until committed; they were not reverted.

---

## Hardening (P3)

- Add `TrustedHostMiddleware` for production hosts.
- Constrain `UserUpdate.role` to an enum (`user`/`admin`).
- Pin `SameSite=strict` for cookie login if OAuth/top-level cross-site POST is not needed.
- Ignore `*.pem` / `*.key` in gitignore (none tracked today).
- Disable OpenAPI in production; add request body size middleware globally.
- Prefer Redis AUTH even on private networks.
- Structured log redaction review for webhook `RequestError` strings and crawl logs.
- HS256 → RS256 only if multiple verifiers appear.
- Backup/restore runbook is not in-repo (see unverified).

---

## Control status (evidence)

| Control | Status | Notes |
|---|---|---|
| Secrets not in client bundle | PASS | `NEXT_PUBLIC_API_BASE_URL` only public env; tokens in HttpOnly cookie, not localStorage |
| `.env` gitignored / example committed | PASS with gap | `.env.example` placeholders; root `.env.*` incomplete |
| CI secret echo | PASS | Gitleaks workflow; CI uses dummy JWT/encryption keys in env, not `echo` of GitHub secrets |
| Git history secret scan | UNVERIFIED | Gitleaks Action exists; this session did not replay full history locally |
| Auth on sensitive APIs | PASS | `get_current_user` / `require_admin` / public API key middleware |
| Admin routes | PASS | `/api/users`, `/api/llm/*`, parts of dashboard |
| Cookie Secure/HttpOnly/SameSite | PASS (non-dev) | `secure=secure_transport_required(runtime_app_env())`; httponly; samesite=lax; path=/; max_age from `jwt_expire_hours` (default 1) |
| Password hashing | PASS | Argon2id default; PBKDF2 verify + rehash on login |
| Session revoke | PASS | `token_version` bump on logout |
| Login/register rate limit | PASS | 10/5 per 60s per client id |
| Object ownership on runs/records | PASS | `require_accessible_run` / record via run; admin override |
| Public API tenancy | PASS | Key → `user_id`; alerts/extract scoped |
| Domain cookie / selector tenancy | FAIL | Global per domain (P1 for multi-user) |
| Mass assignment on register | PASS | `UserCreate` email+password only |
| Privileged DB to client | N/A | No Supabase anon key; SQLAlchemy server-side |
| SQL parameterization | PASS | ORM; `text()` in metrics health checks is static |
| SSRF on crawl targets | PASS with residual risk | `url_safety.py` + tests (40 focused tests passed); see [redirect/DNS-rebinding limits](#unverified-external-controls) |
| SSRF on webhooks | FAIL | P1 |
| Condition language RCE | PASS | Tokenized field/operator/literal parser, not `eval` |
| Uploads | FAIL (limits) | CSV only; auth yes; no size/MIME; not stored as executable origin content |
| Pagination | PASS | Typical `le=100` / record page max |
| Inbound webhooks | N/A | Outbound only |
| Security headers (API) | PASS partial | nosniff, DENY frame, referrer, permissions-policy, HSTS when HTTPS+non-dev; no CSP |
| Security headers (Next) | PASS partial | next.config + production CSP in `proxy.ts` |
| CORS | PASS | Explicit origins; methods/headers allowlisted; credentials true |
| Production debug / stack pages | PASS | No `debug=True`; no custom 500 traceback handler (Starlette default hides traces) |
| Validation error bodies | PASS/P3 | 422 returns `exc.errors()` (can echo input) |
| Settings sanitization on run GET | PASS | Strips password/token/proxy secrets from `CrawlRunResponse.settings` |
| Lockfiles | PASS | `backend/uv.lock`, `frontend/pnpm-lock.yaml` |
| Dep scanners in CI | PASS | pip-audit, pnpm audit --audit-level=high, Dependabot, CodeQL |
| Health/ready | PASS | `/health/live`, `/health/ready`, `/api/health` |
| Migrations | PASS (repo) | Single Alembic revision `20260822_0001_canonical_invoro_schema.py`; compose has legacy rename path |
| Default secret guard | PASS (if APP_ENV prod) | RuntimeError outside dev/test; **defeated by compose APP_ENV=development** |

---

## Verification

| Check | Result |
|---|---|
| `git branch` / `HEAD` / `git status -sb` | `main` @ `d569a6d`, dirty working tree (extraction + docs). Not discarded. |
| Code/config inspection | Completed (auth, CORS, headers, public API, webhooks, url_safety, compose, CI, selectors preview, tenancy) |
| `git check-ignore` / `git ls-files` for env/keys | `.env` ignored; `.env.example` tracked; no `*.pem`/`*.key` tracked |
| Pattern grep for AWS/GitHub/OpenAI-style keys in repo | No matches |
| `backend/.venv` `pip_audit --local --vulnerability-service osv` | **Pass** — no known vulnerabilities |
| `frontend` `pnpm audit --audit-level=high` | **Pass** — no known vulnerabilities |
| `pytest tests/component/test_url_safety.py tests/component/test_login_returns_user_only_sets_cookie_env.py` | **40 passed** |
| Full `pytest -m "unit or component or regression"` | **Not run** this session (scope: security-focused) |
| Frontend `pnpm run build` / typecheck | **Not run** this session (CI job exists on frontend paths) |
| Local Gitleaks CLI | **Unavailable** in this session; GitHub workflow `gitleaks/gitleaks-action` present |
| Live TLS/DNS/WAF probe of a production URL | **Unavailable** (no production host in repo) |

---

## Unverified external controls

Mark these UNVERIFIED until an operator confirms them in the real environment:

- Production `APP_ENV`, `JWT_SECRET_KEY`, `ENCRYPTION_KEY`, admin bootstrap flags, and provider API keys in the secret manager (not the repo)
- TLS certificates, HTTP→HTTPS redirect, HSTS preload eligibility, DNS
- Reverse proxy / CDN / WAF, whether `/api/metrics` and `/docs` are exposed
- Trusted proxy list (`api_rate_limit_trusted_proxies`) vs real `X-Forwarded-Proto` / client IP
- Postgres/Redis not published to the internet; Redis AUTH; network policies
- Backups and restore drills for `pg_data` / artifact volumes
- Logfire / metrics / alerting actually wired
- Whether `BOOTSTRAP_ADMIN_ONCE` was turned back off after first boot
- Celery workers using the same production credentials and not a sandbox key
- Git history cleanliness beyond CI Gitleaks (rotate if an old secret was ever committed)
- Host firewall around Playwright/browser workers (SSRF residual via crawl is reduced by `url_safety`, not zero for all redirect/DNS-rebinding races)

---

## Conditions if launching a **private single-admin** instance anyway

These do **not** convert the verdict to GO. They reduce blast radius until P1s are fixed:

1. `REGISTRATION_ENABLED=false`; do not create a second human user.
2. Do **not** use stock `docker-compose.yml` as production; set `APP_ENV=production` and lock origins/secrets.
3. Put API behind VPN or IP allowlist until webhook SSRF and HTML preview XSS are fixed.
4. Disable or auth-gate `/api/metrics` and OpenAPI docs.
5. Keep browser cookie reuse in mind: only one operator’s target-site sessions should exist.

---

## Changes made

None to application code. This file is the audit artifact (`docs/audits/pre-launch-security-and-readiness-2026-08-23.md`).

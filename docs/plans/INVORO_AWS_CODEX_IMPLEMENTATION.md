# Plan: Invoro AWS Feedonomics Demo Launch

**Created:** 2026-08-23
**Agent:** Codex
**Status:** IN PROGRESS
**Touches buckets:** authentication, API routes, crawl ingestion, selector/review rendering, frontend shell, containers, AWS infrastructure, CI/CD, operations docs

## Goal

Launch a disposable, public AWS demo for Feedonomics with exactly one provisioned
admin. Keep crawl, extraction, review, export, selector tooling, and optional API
keys. Disable registration, monitoring, alerts, notifications, webhooks, and Beat.
Approval applies only to the one-week demo, not general production or multi-user use.

## Acceptance Criteria

- [x] API runtime cannot bootstrap the admin; the one-shot migration task does so idempotently.
- [x] Monitoring routers, scheduler, frontend pages, and AWS Beat service are absent in demo mode.
- [x] Selector preview and review artifacts use restrictive sandbox CSP; iframe candidates are revalidated.
- [x] CSV uploads are capped at 1 MiB and 1,000 URLs.
- [x] Terraform validates and defines the intended no-NAT, no-WAF, three-service topology.
- [x] Manual provision, deploy/rollback, control, and destroy workflows use OIDC and confirmation gates.
- [x] Complete backend/frontend release checks and Docker builds pass on this exact tree.
- [ ] Live AWS, DNS, TLS, IAM, secret, smoke, stop/start, and rollback checks pass.

## Do Not Touch

- `.env` — user-owned local credentials.
- Deleted `docs/audits/*` files — user-owned working-tree deletions.
- Existing local Docker Compose topology — development compatibility must remain.
- Cloudflare or AWS provider state — owner performs external steps through the runbook.

## Slices

### Slice 1: Application demo boundary
**Status:** DONE
**Files:** backend settings/routes/services and frontend shell/proxy
**What:** One-shot bootstrap, monitoring-off profile, route hiding, untrusted HTML sandboxing, SSRF hop validation, CSV limits, trusted proxy CIDR handling.
**Verify:** Focused security/config suite passed 78 tests; frontend lint, types, and all 182 tests passed.

### Slice 2: Reproducible containers
**Status:** DONE
**Files:** backend and frontend Dockerfiles, runtime configuration
**What:** Immutable base digests, frozen backend lock install, non-root UID/GID 10001, demo build flag, Chromium shared-memory argument.
**Verify:** Both production images build; backend runs as UID 10001 with demo routes absent; frontend returns 404 for registration and monitoring pages.

### Slice 3: AWS infrastructure and release automation
**Status:** DONE
**Files:** `infra/aws/*`, `.github/workflows/aws-*.yml`
**What:** VPC/ALB/Fargate/RDS/Redis/EFS/ECR/logs/IAM plus guarded manual provision, deploy, rollback, start, stop, status, and destroy flows.
**Verify:** Terraform 1.14 with AWS provider 6.61.0 validates; all four workflows pass Actionlint; release shell passes `bash -n`.

### Slice 4: Documentation and repository verification
**Status:** DONE
**Files:** plan tracking, owner runbook, architecture ownership docs
**What:** Reconcile stale plan state, document exact owner steps, run repository-wide checks, validate workflows and build both images.
**Verify:** Backend static checks pass. Broad backend run reached 2,337 passed and exposed only three stale Chromium-argument expectations; after correction, both owning files pass 42/42. Frontend audit, format, lint, architecture, types, 182 tests, production build, and runtime route smoke pass.

### Slice 5: Owner launch and evidence
**Status:** TODO
**Files:** owner runbook and launch evidence section below
**What:** Apply Terraform, populate secrets, add DNS, deploy, start, smoke, rehearse rollback, stop, present, and destroy.
**Verify:** Every live checklist item passes before verdict changes from NO-GO.

## Doc Updates Required

- [x] `docs/plans/ACTIVE.md` — old plan closed; this launch is active.
- [x] `docs/plans/INVORO_AWS_OWNER_RUNBOOK.md` — exact post-step-12 operations.
- [x] `docs/CODEBASE_MAP.md` — register AWS infrastructure and untrusted HTML owner.
- [x] `docs/backend-architecture.md` — record one-shot bootstrap and demo surface controls.
- [x] `docs/frontend-architecture.md` — record demo-mode route hiding.
- [x] `docs/INVARIANTS.md` — no shared extraction/persistence invariant changed.

## Launch Evidence

| Control | Status | Evidence |
|---|---|---|
| Single-admin/bootstrap boundary | PASS | Focused tests; API lifespan no longer bootstraps |
| Monitoring/webhook reachability | PASS | Demo routers omitted; frontend hidden; no Beat task/service |
| Untrusted HTML active content | PASS | Shared sandbox CSP and route tests |
| CSV resource bounds | PASS | Exact-boundary and URL-count tests |
| Terraform static validation | PASS | Terraform 1.14 `validate` with provider lock |
| Full release test suite | PASS | Backend 2,337-pass broad run plus 42/42 corrected owning tests; frontend 182/182 and production build |
| Container image builds | PASS | Frozen backend and demo frontend images built; runtime smokes passed |
| ECR vulnerability scans | UNVERIFIED | Runs during first deploy and blocks High/Critical findings |
| AWS resources/IAM/network | UNVERIFIED | Requires Terraform apply and AWS API readback |
| DNS/TLS/security headers | UNVERIFIED | Requires Cloudflare records and public endpoint checks |
| Login/crawl/review/export smoke | UNVERIFIED | Requires live environment |
| Stop/start and rollback | UNVERIFIED | Requires deployed release |

## Notes

- Current launch verdict remains **NO-GO** until the owner completes Slice 5.
- No WAF, CloudFront, NAT, Multi-AZ RDS, Redis TLS/auth, or application task role.
- Webhook SSRF is made unreachable for this demo, not fixed for future full-product launch.
- Domain cookie memory remains unsuitable for multi-user deployment; registration must stay disabled.
- Cloudflare stays DNS-only. AWS Shield Standard is the only managed DDoS baseline.

# Plan: Review Findings Remediation

**Created:** 2026-08-10
**Agent:** Codex
**Status:** COMPLETE
**Touches buckets:** Acquisition + Browser Runtime; Fetch Policy; Extraction; Pipeline; Frontend Auth Shell + Crawl Results; Backend Tests; Plan Docs

## Goal

Verify the supplied review findings against current code, fix only still-valid issues with minimal changes, preserve existing extraction and acquisition contracts, and report skipped findings with evidence.

## Acceptance Criteria

- [x] Every supplied finding is fixed or explicitly skipped as stale/invalid.
- [x] Config-owned tokens and policy values no longer live inline in touched services.
- [x] Extraction contexts do not reuse a pruned DOM built from a different source document.
- [x] Login screen loads and inherits the local fonts introduced by the previous frontend PR.
- [x] Focused acquisition, fetch, detail-assembly, listing, and structure tests pass.
- [x] Frontend architecture checks and targeted auth/UI tests pass.
- [x] Recent batch-run failures are traced against active-branch changes and any proven crawler regression is fixed upstream.
- [x] Crawl result images have a non-zero containing block and emit no Next `fill` height warning.
- [x] `python -m pytest tests -q -m "unit or component or regression"` exits 0.

## Do Not Touch

- Frontend features outside the auth shell/font owners — unrelated to the added font regression.
- Public HTTP APIs, schemas, persistence, and export contracts — outside supplied scope.
- Live smoke and network acceptance — prohibited by the completed refactor plan.
- Existing unrelated worktree edits — preserve user changes.

## Slices

### Slice 1: Acquisition configuration and blocker cleanup
**Status:** DONE
**Files:** `backend/app/services/acquisition/{browser_detail,runtime}.py`, existing config owners, focused tests
**What:** Move valid inline tokens/status values to config, preserve prefetched empty snapshots, extract active-provider matching, and remove runtime captcha literals.
**Verify:** Focused browser expansion and block-detection tests.

### Slice 2: Login font regression
**Status:** DONE
**Files:** frontend layout, globals, auth shell, and local font owners identified by the prior PR
**What:** Trace the prior font change through Next font loading and auth-shell inheritance; fix the current root cause without redesigning the login screen.
**Verify:** Frontend architecture guards, targeted tests, and bounded visual inspection when the local app can run.

### Slice 3: Fetch deadline and engine policy cleanup
**Status:** DONE
**Files:** `backend/app/services/fetch/{browser_policy,fetch_context}.py`, `backend/app/services/config/runtime_settings.py`, focused fetch tests
**What:** Centralize engine/error policy symbols and cap HTTP transports by the deadline remaining after host-slot wait.
**Verify:** Focused fetch-policy and crawl-fetch tests.

### Slice 4: Extraction context, price, listing, and pipeline cleanup
**Status:** DONE
**Files:** extraction context/detail assembly/price/listing/pipeline owners and focused tests
**What:** Key pruned-DOM cache by source identity, remove confirmed dead branches, preserve existing price behavior, add rendered-fragment fallback, and remove unreachable serialization guard.
**Verify:** Detail assembly, price, listing, and Selectolax regression tests.

### Slice 5: Regression assertions and completed-plan docs
**Status:** DONE
**Files:** supplied regression tests and completed-plan docs
**What:** Strengthen cache assertions, clarify parser budgets/LOC diagnostics, repair completed-plan wording, and close active-plan state.
**Verify:** Structure and touched regression files plus documentation inspection.

### Slice 6: Broad verification and closeout
**Status:** DONE
**Files:** this plan and `docs/plans/ACTIVE.md`
**What:** Run static checks and the safe backend suite once, record results, mark complete, and return ACTIVE.md to idle state.
**Verify:** `python -m pytest tests -q -m "unit or component or regression"`.

### Slice 7: Active-branch crawl regression review
**Status:** DONE
**Files:** active branch diff, recent run logs/data, and only proven owning backend files/tests
**What:** Compare the active branch with its base, inspect the latest six batch outcomes, distinguish environmental/site failures from code regressions, and fix confirmed upstream causes.
**Verify:** Focused tests for each confirmed cause plus batch/runtime regression coverage; no live network smoke.

### Slice 8: Crawl result image layout
**Status:** DONE
**Files:** existing crawl result image/card owner and focused frontend tests
**What:** Give every `next/image` fill usage a stable non-zero containing block without changing image semantics or result data.
**Verify:** Frontend lint/typecheck/tests/build and user-visible warning removal.

## Doc Updates Required

- [x] `docs/plans/ACTIVE.md` — point to this plan while active, then return to idle.
- [x] `docs/plans/backend-core-debt-refactor-plan.md` — resolve supplied verification wording contradictions.
- [x] Architecture/invariant docs — no update required; both runtime fixes restore documented contracts.

## Notes

- Initial audit found an existing regression contract that intentionally keeps authoritative JSON-LD `original_price` on an out-of-stock record. The supplied request to skip original-price application for all blocked selections appears incompatible and will be rechecked during Slice 3.
- Existing dirty files are preserved; only directly requested overlapping lines will be touched.
- Slice 1 verification: block detection plus browser expansion selected 187 tests; all passed. Ruff passed on every touched acquisition/config file.
- Slice 2 root cause: PR #86 applied generated Next font variables to `body`, below the `:root` aliases that consume them. Moving the variables to `html` lets the local Switzer/Satoshi faces resolve. Frontend lint, architecture guards, TypeScript, 7 targeted tests, production build, and user visual verification passed.
- Slice 3 verification: the 91 pre-existing crawl-fetch component tests passed. The added post-host-slot timeout regression initially had fixture setup misuse, then passed by node after correction. Ruff and mypy passed on touched fetch/config files.
- Slice 4 verification: 95 detail unit tests passed. Focused extraction selected 599 tests: 580 passed, 19 fixture skips, and 4 deselected. Ruff and targeted mypy passed.
- Skipped supplied price-flow finding: gating original-price application on `selection.blocked` and removing trailing unavailable-price cleanup would break two existing regression contracts. Authoritative JSON-LD `original_price` is intentionally retained for out-of-stock products, while trailing cleanup removes non-authoritative visible DOM price when selection itself is not blocked.
- Slice 5 strengthened the supplied regression assertions, kept effective structure ratchets unchanged, and corrected the completed refactor plan's verification wording. Focused structure nodes passed.
- Slice 7 inspected persisted run 4, a six-URL batch with four successes. B&H returned a Cloudflare challenge in Patchright and real Chrome. Arc'teryx returned HTTP 429; Patchright consumed most of the shared 90-second budget and left real Chrome about 18 seconds. The next batch progressed normally, so no broad branch regression was established. Protected HTTP blocks now receive the existing short Patchright probe cap when real Chrome is queued. The 93 fetch/deadline component tests pass.
- Slice 8 traced the image warning to PR #86 deleting `.ct-image-wrap` while `RecordThumbnail` still depended on it. The component now owns a fixed 64px containing block and `object-contain`; its focused regression test, frontend lint, architecture guards, and typecheck pass.
- Slice 6 verification: Ruff passed across `app` and `tests`; mypy passed across 461 source files; all 30 structure tests passed. The regression marker selected 1,017 tests: 998 passed and 19 fixture-dependent cases skipped. Frontend lint, architecture guards, typecheck, 187 tests, production build, and the Impeccable detector passed. One frontend test timed out only during a parallel CPU-heavy run and passed alone and again in the full frontend run. The required safe backend suite selected 2,421 tests: 2,402 passed, 19 fixture-dependent cases skipped, and 17 live/integration/e2e cases deselected in 467.33 seconds.

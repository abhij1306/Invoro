# Invoro Productionization Evidence Report

**Date:** 2026-08-21  
**Commit:** `c091052ceb6bb6c8c0d860ed4d0b1113c396a1b3` (`main`, clean working tree)  
**Scope:** Read-only, repository-grounded production-readiness analysis for LOC ≤800, cyclomatic complexity ≤15, lint/format CI, and dependency review.  
**Status:** Forensic snapshot. Do not treat as an implementation plan.

---

## 1. Executive Summary

**Overall readiness: GO WITH CONDITIONS**  
**Readiness for enabling the requested absolute gates (LOC ≤800 and complexity ≤15, blocking): NO-GO**

The repo already has real backend and frontend quality CI, local lint/format/typecheck that **passed in this session**, health endpoints, `.env.example`, and a structure-test LOC ratchet. The requested **absolute** 800-line and complexity-15 gates are **not** in CI, **conflict** with current ratchets (default 1000 non-blank lines; frontend crawl screens allowed 1400–1500), and would **fail immediately** on current first-party code.

| Severity | FAIL | PASS | UNVERIFIED | N/A |
|---|---:|---:|---:|---:|
| P0 | 0 | — | — | — |
| P1 | 1 | — | 1 | — |
| P2 | 12 | — | 2 | — |
| P3 | 4 | — | 1 | — |
| Informational / control PASS | — | 11 | 3 | 2 |

**Five most important verified conclusions**

1. **61** first-party `.py`/`.ts`/`.tsx`/`.js`/`.mjs` files exceed **800 physical lines** (28 backend production, 21 backend tests, 7 frontend production, 1 frontend test, 4 tooling/scripts). **43** exceed 1000. Existing `test_structure.py` uses **non-blank** LOC and **grandfathers** files above 800 (default budget 1000).
2. **Radon** McCabe CC **>15**: **333** Python callables (about **304** production, **20** tooling, **9** tests). Peak `coerce_field_value` **96**. **ESLint `complexity` >15**: **42** frontend callables. Peak `CrawlRunScreen` **131**.
3. Backend CI **does** run Ruff check, mypy, pytest (unit/component/regression), and pip-audit. It does **not** run `ruff format`. Frontend Quality **does** run Prettier check, ESLint `--max-warnings=0`, `tsc`, Vitest, build, and `pnpm audit --audit-level=high`, but **only on `pull_request` + `workflow_dispatch`**, not `push`.
4. `pnpm audit --audit-level=high` **fails today** (`nanoid@3.3.17`, GHSA-2v37-7h3g-55p8). Local **pip-audit** on the backend venv reported **no known vulnerabilities**. Vulture at the committed **100%** threshold is effectively clean (one Pydantic false positive).
5. jscpd **4.2.4** on `backend/app` + frontend app/components/lib: **52** clones, **664** duplicated lines (**0.48%**). Duplication is not the primary 800/15 blocker.

**Grader claims:** LOC totals and oversized-file counts are **stale/wrong** (current physical first-party scan is **245,981** lines / **872** files; **123** files >500; **43** >1000). `test_detail_extractor_structured_sources.py` is **9379**, not ~8486. `browser_surface_probe/core.py` is **2178**, not ~2006. Backend CI Ruff/mypy/pytest/pip-audit **confirmed**; Ruff **format** is **not** in that workflow. Frontend lint/format/typecheck **exist and passed locally**; “missing frontend CI/config” is **disproven** for PRs, with a **push-trigger gap**. Dependency “update everything” is **not** supported; targeted outdated packages and one high npm advisory are. `.env.example` and `/api/health` **exist**. Coverage/commit-history optics **not treated as production evidence**.

---

## 2. Repository and Tooling Baseline

**Git:** branch `main`, commit `c091052ceb6bb6c8c0d860ed4d0b1113c396a1b3` (`chore: consolidate dependency updates (#88)`, 2026-08-10). Working tree **clean**.

| Area | Detected technology/tool | Version | Configuration path | CI workflow/job | Status | Evidence |
|---|---|---|---|---|---|---|
| VCS | git / `main` | `c091052c` | — | — | PASS | `git rev-parse`; dirty=false |
| Backend runtime | CPython | 3.12 required; venv **3.12.10** | `.python-version`, `backend/pyproject.toml` `requires-python = ">=3.12,<3.13"` | `backend-ci.yml` `setup-python` 3.12 | PASS | files + `--version` |
| Backend packaging | setuptools + **uv.lock**; CI uses **pip** | uv **0.11.28** local | `backend/pyproject.toml`, `backend/uv.lock` | `pip install -e ".[dev]"` | FAIL (drift risk) | CI does not consume `uv.lock`; local venv has **no `pip` module** |
| Backend lint | Ruff | **0.16.2** (pinned) | `backend/pyproject.toml` `[tool.ruff.lint]` select `E4,E7,E9,F` | `backend` / `Ruff` | PASS (check) | `ruff check` exit 0 |
| Backend format | Ruff format | 0.16.2 | default Ruff format (no `[tool.ruff.format]` block) | **absent** | FAIL (CI gap) | local `ruff format --check` exit 0, 621 files |
| Backend types | mypy | **2.3.0** | `[tool.mypy]` python 3.12, exclude tests/alembic | `Mypy` | PASS | `mypy app` “461 source files”, exit 0 |
| Backend extra static | Pylint, basedpyright, bandit, vulture, radon | in `dev` extra; **not CI** | pylint `max-module-lines = 1000`; `[tool.vulture] min_confidence = 100` | none | FAIL (not gates) | `pyproject.toml` |
| Backend tests | pytest | markers in `pytest.ini` | `backend/pytest.ini` | `Pytest` `-m "unit or component or regression"` | UNVERIFIED (not re-run here) | workflow |
| Backend audit | pip-audit | installed in **temp** venv for this review | `--ignore-vuln PYSEC-2025-183` in CI | `Dependency vulnerability scan` | PASS locally; ignore is disputed pyjwt | temp `pip_audit --path .venv` exit 0 |
| Frontend PM | **pnpm** (Corepack) | `packageManager` **pnpm@11.9.0**; local pnpm **11.22.0** | `frontend/package.json`, `pnpm-lock.yaml`, `pnpm-workspace.yaml` | `frontend-quality.yml` | FAIL (docs/CI vs local) | README still says `npm install` |
| Frontend runtime | Node | CI **22**; local **26.7.0**; README badge 20+ | workflow `node-version: 22` | quality + playwright | PASS (CI pin) | workflows |
| Frontend lint | ESLint 9 + `eslint-config-next` | ESLint **9.39.4** | `frontend/eslint.config.mjs` | `Run ESLint` `pnpm run lint:eslint` | PASS | exit 0, `--max-warnings=0` |
| Frontend format | Prettier + tailwind plugin | **3.8.3** | `frontend/.prettierrc`, `.prettierignore` | `Check formatting` | PASS | `prettier --check .` |
| Frontend types | `tsc --noEmit` | TypeScript **6.0.3** | `frontend/tsconfig.json` `strict: true` | `Typecheck` | PASS | exit 0 |
| Frontend tests | Vitest / Playwright | vitest **4.1.8** | `vitest.config.ts`, `playwright.config.ts` | quality `pnpm test`; smoke e2e | UNVERIFIED (not re-run) | workflows |
| Frontend architecture ratchets | custom node scripts | — | `scripts/check-*.mjs`; crawl screens **1400/1500** lines | quality job | PASS as current policy; **conflicts** with 800 | `check-crawl-architecture.mjs` |
| Complexity (Py) | Radon | **6.0.1** | no project radon.ini; grades A1–5 … F41+ | none | FAIL vs ≤15 | 333 CC>15 |
| Complexity (JS/TS) | ESLint `complexity` | not in `eslint.config.mjs` | additive CLI rule only | none | FAIL vs ≤15 | 42 functions |
| Dead code | Vulture | **2.16** | `min_confidence = 100` | none | PASS at 100% after validation | 1 hit, false positive |
| Duplication | jscpd | **4.2.4** (npx) | no committed jscpd config | none | N/A (not a current requirement) | 0.48% |
| Secrets CI | Gitleaks | action pin `e0c47f4` | `.github/workflows/gitleaks.yml` | all branches push/PR | PASS (exists) | workflow |
| CodeQL | python + js/ts | — | `codeql.yml` | path-filtered | PASS (exists) | workflow |
| Env template | dotenv example | — | `.env.example` | — | PASS | file present |
| Health | FastAPI routes | — | `backend/app/main.py` L574–589 | playwright waits `/api/health` | PASS | live/ready/api health |

**Radon grade mapping used (Radon `cc` ranks):** A=1–5, B=6–10, **C=11–20**, D=21–30, E=31–40, F=41+. The requested ceiling **15** is a **numeric McCabe cap**, not a grade: it sits **inside rank C**. `-n D` would miss 16–20; `-n C` would fail 11–15.

**ESLint `complexity`:** McCabe-style cyclomatic complexity on functions/methods/arrows. Close enough to Radon for a dual-language gate; differences include how `&&`/`||`, optional chaining, and JSX branching are counted. Not identical to Radon.

---

## 3. Current CI Quality-Gate Matrix

| Gate | Local command exists | Committed configuration | CI enforced | Blocking | Currently passes | Evidence/gap |
|---|---|---|---|---|---|---|
| Backend lint | Yes `python -m ruff check app tests` | Yes, narrow `E4,E7,E9,F` | Yes `backend-ci.yml` | Yes | **Yes** (this session, also `browser_surface_probe harness`) | CI omits probe/harness; no C901 |
| Backend format | Yes `ruff format --check` | Implicit Ruff defaults | **No** | No | **Yes** locally (621 files) | CI gap |
| Backend type check | Yes `mypy app` | Yes | Yes | Yes | **Yes** | tests/alembic excluded |
| Backend tests | Yes pytest markers | `pytest.ini` | Yes | Yes | UNVERIFIED here | not executed this review |
| Backend LOC ≤800 | Ad-hoc physical count; structure test uses **non-blank** + budgets | `tests/regression/test_structure.py` default **1000**, ratchets up to **9379** tests | Only ratchet tests, not 800 | Yes for ratchet | **Fails absolute 800**; ratchet likely still green | `_source_loc` counts non-blank |
| Backend complexity ≤15 | Radon in dev extra | Pylint `max-branches=12` **not CI** | **No** | No | **Fails** (333) | radon 6.0.1 |
| Frontend lint | `pnpm run lint:eslint` | `eslint.config.mjs` | Yes **PR only** | Yes | **Yes** | no `push` |
| Frontend format | `pnpm run format:check` | `.prettierrc` | Yes **PR only** | Yes | **Yes** | |
| Frontend type check | `pnpm run typecheck` | `tsconfig.json` | Yes **PR only** | Yes | **Yes** | |
| Frontend tests | `pnpm test` / `test:e2e` | vitest/playwright configs | unit on PR; e2e smoke on PR | Yes | UNVERIFIED here | |
| Frontend LOC ≤800 | partial file budgets (not 800) | `check-frontend-architecture.mjs`, crawl **1500/1400** | Yes those scripts | Yes those | **Fails absolute 800** | 8 FE files >800 |
| Frontend complexity ≤15 | CLI-only this review | **No** committed rule | **No** | No | **Fails** (42) | ESLint exit 1 with rule |
| Dependency audit | pip-audit / `pnpm audit` | CI ignore PYSEC-2025-183 | Yes both | Yes | Backend **pass** local; frontend **fail** high | nanoid 3.3.17 |
| Dead-code analysis | `vulture` | min 100 | **No** | No | 100% ≈ clean | FastAPI FPs at 60% |
| Duplication analysis | npx jscpd | none committed | **No** | No | 0.48% (info) | not a required gate |

---

## 4. Files Over 800 LOC

**Counting method:** physical lines = UTF-8 newline count (+1 if no trailing newline). Includes blanks and comments.

**Excluded dirs (from repo evidence + standard artifacts):** `.git`, `.venv`, `node_modules`, `.next`, `coverage`, `htmlcov`, `.mypy_cache`, `.pytest_cache`, `.ruff_cache`, `__pycache__`, `dist`, `build`, `backend/artifacts`, Playwright reports, `.scannerwork`, `.codacy`, `.qodo`, `cookie_store`. Lockfiles and `*.min.js` skipped.

**Not excluded:** `backend/alembic` (none >800), first-party tests, `browser_surface_probe`, `harness`, `agent_debug`.

**Totals scanned:** 872 files, **245,981** physical LOC (`.py` 209,105; `.tsx` 25,122; `.ts` 10,998; `.js` 396; `.mjs` 360). **>800: 61**. **>1000: 43**. **>500: 123**.

| Subsystem | Role | Count |
|---|---|---:|
| backend-app | production source | 28 |
| backend-tests | test | 21 |
| frontend | production source | 7 |
| frontend-tests | test | 1 |
| backend-tooling | script/tooling | 3 |
| repo-scripts | script/tooling | 1 |

Current architecture tests **must not** be used as the 800 gate: they count **non-blank** lines (`backend/tests/regression/test_structure.py`) and **allowlist** growth (`DEFAULT_LOC_BUDGET = 1000`, `LEGACY_SOURCE_LOC_RATCHETS`, `CRITICAL_TEST_LOC_RATCHETS` up to 9379).

Do **not** slice `field_coerce.py`, identity, or price **only** to hit 800. Split along owners already named in `docs/CODEBASE_MAP.md` / `docs/ENGINEERING_STRATEGY.md`.

| File | LOC | Classification | Current responsibility | Suggested split seams | Likely owner/destination | Risk | Related tests | Finding ID |
|---|---:|---|---|---|---|---|---|---|
| `backend/tests/regression/test_detail_extractor_structured_sources.py` | 9379 | test | Structured-source detail regressions | Split by source family (JSON-LD / JS state / network) as test modules | extraction tests | High if private imports freeze internals (AP-7) | self | F-LOC-800 |
| `backend/tests/regression/test_crawl_engine.py` | 6753 | test | Crawl-engine contract | By surface / adapter vs DOM | extraction tests | High | self | F-LOC-800 |
| `backend/tests/regression/test_browser_expansion_runtime.py` | 6245 | test | Browser expansion | Probe vs navigation vs assertion helpers | acquisition tests | High | self | F-LOC-800 |
| `backend/tests/regression/test_pipeline_core.py` | 4032 | test | Pipeline core | Persistence vs extract-loop vs retry | pipeline tests | Med | self | F-LOC-800 |
| `backend/tests/component/test_crawl_fetch_runtime.py` | 3753 | test | Fetch runtime | HTTP vs browser vs handoff | acquisition tests | Med | self | F-LOC-800 |
| `backend/tests/component/test_browser_context.py` | 3322 | test | Browser context | Identity vs pool vs cookies | acquisition tests | Med | self | F-LOC-800 |
| `backend/tests/component/test_product_intelligence.py` | 3211 | test | PI jobs | Discovery vs scoring vs persist | `product_intelligence/` tests | Med | self | F-LOC-800 |
| `backend/tests/regression/test_selectolax_css_migration.py` | 2723 | test | Parser migration | Per adapter / selector owner | DOM tests | Med | self | F-LOC-800 |
| `backend/browser_surface_probe/core.py` | 2178 | script/tooling | Browser-surface diagnostic harness | Findings builder vs probe I/O | `browser_surface_probe/` | Med (not runtime) | harness/acceptance | F-LOC-800 |
| `backend/tests/unit/test_state_mappers.py` | 2028 | test | JS-state mappers | Per mapper module | `js_state/` tests | Med | self | F-LOC-800 |
| `backend/tests/component/test_traversal_runtime.py` | 1970 | test | Traversal | Mode: scroll/paginate/load_more | acquisition tests | Med | self | F-LOC-800 |
| `backend/harness/support.py` | 1658 | script/tooling | Acceptance helpers / TEST_SITES | Surface infer vs quality classify vs markdown parse | `harness/` | Med | `test_harness_support.py` | F-LOC-800 |
| `backend/tests/unit/test_normalizers.py` | 1636 | test | Normalizers | Price vs availability vs text | `normalizers/` tests | Low | self | F-LOC-800 |
| `backend/tests/regression/test_batch_runtime.py` | 1570 | test | Batch runtime | Dispatch vs persist vs failure log | crawl tests | Med | self | F-LOC-800 |
| `agent_debug/run_json_issue_audit.py` | 1497 | script/tooling | Offline JSON issue audit | Pollution vs variant vs logical scanners | `agent_debug/` or merge with `run_json_issue_audit.py` | Low | none required | F-LOC-800 |
| `frontend/app/ucp-audit/ucp-audit-components.tsx` | 1410 | production source | UCP audit panels | Contract panel vs score summary vs tables | `app/ucp-audit/` | Med UI contract | `ucp-audit-page.test.tsx` | F-LOC-800 |
| `frontend/components/crawl/crawl-config-screen.tsx` | 1323 | production source | Crawl config UI | Already has `crawl-config-logic.ts`; extract remaining form sections | crawl UI | High; CI allows **1500** | `crawl-config-screen.*.test.tsx` | F-LOC-800 |
| `backend/tests/component/test_crawl_service.py` | 1304 | test | Crawl service | Create vs control vs logs | crawl tests | Med | self | F-LOC-800 |
| `backend/app/services/product_intelligence/discovery.py` | 1291 | production source | Search/discovery parsing | SerpAPI vs Google native vs query helpers | `product_intelligence/` | High live-search behavior | `test_product_intelligence.py` | F-LOC-800 |
| `backend/tests/regression/test_harness_support.py` | 1290 | test | Harness support | Mirror harness splits | harness tests | Low | self | F-LOC-800 |
| `backend/app/services/extract/detail/identity/core.py` | 1286 | production source | Detail identity / listing-vs-PDP | URL structural vs token overlap vs redirect mismatch | `extract/detail/identity/` | **High** (INVARIANTS identity) | structured-source + crawl_engine tests | F-LOC-800 |
| `frontend/components/crawl/crawl-run-screen.test.tsx` | 1280 | test | Crawl run UI | By controller vs log vs records | crawl tests | Med | pairs with screen | F-LOC-800 |
| `backend/app/services/page_audit/analysis.py` | 1207 | production source | Page-audit DOM/source checks | `_dom_checks` vs network vs scoring | `page_audit/` | Med | page-audit tests | F-LOC-800 |
| `backend/app/services/extract/detail/variants/dom_extraction.py` | 1185 | production source | DOM variant extraction | Axis vs backfill vs option walk | `extract/detail/variants/` | **High** (AP-12 variants) | expansion + structured tests | F-LOC-800 |
| `backend/app/services/product_intelligence/service.py` | 1154 | production source | PI job orchestration | Persist vs score vs poll | `product_intelligence/service.py` | High | `test_product_intelligence.py` | F-LOC-800 |
| `backend/tests/unit/test_field_value_core.py` | 1153 | test | Field coercion | Per field family matching `field_coerce*` | shared coercion tests | Med | self | F-LOC-800 |
| `frontend/app/playground/page.tsx` | 1144 | production source | Playground page | Split log humanize vs page chrome; workflow hook exists | `app/playground/` | Med | `playground-workflow.test.tsx` | F-LOC-800 |
| `frontend/components/crawl/crawl-run-screen.tsx` | 1140 | production source | Run workspace UI | `use-crawl-run-controller.ts` exists; split remaining render | crawl UI | High; CI allows **1400** | `crawl-run-screen.test.tsx` | F-LOC-800 |
| `backend/tests/unit/test_shared_variant_logic.py` | 1125 | test | Variant helpers | Axis vs merge vs sanitize | variant tests | Med | self | F-LOC-800 |
| `backend/app/services/extract/detail/text/sanitizer.py` | 1123 | production source | Long-text sanitize | Materials vs other-product vs chunk policy | `extract/detail/text/` | High extraction quality | field/detail tests | F-LOC-800 |
| `backend/app/services/acquisition/browser_detail.py` | 1100 | production source | Detail browser expansion | Accessibility expand vs field tokens (legacy ratchet **1018** non-blank) | acquisition | **High** AP-16 | `test_browser_expansion_runtime.py` | F-LOC-800 |
| `backend/tests/component/test_public_api.py` | 1096 | test | Public API | Extract vs alerts vs envelope | `api/public/` tests | Med | self | F-LOC-800 |
| `backend/app/services/acquisition/browser_pool.py` | 1095 | production source | Browser pool lifecycle | Ensure vs evict vs page | `browser_pool.py` | High resource leaks | browser context tests | F-LOC-800 |
| `frontend/lib/api/types.ts` | 1072 | production source | API DTO dump | Split by domain (crawl, monitor, PI, UCP) | `lib/api/` | Med contract drift | `client.test.ts` | F-LOC-800 |
| `backend/app/services/acquisition/browser_runtime.py` | 1068 | production source | Browser fetch orchestration | Warm-origin vs navigation | acquisition | High | fetch runtime tests | F-LOC-800 |
| `backend/app/services/shared/field_coerce.py` | 1052 | production source | Canonical field coercion dispatch | Keep dispatcher; move remaining per-type branches into existing `field_coerce_*` | `shared/field_coerce*` | **High** AP-19 | `test_field_value_core.py` | F-LOC-800 |
| `backend/tests/regression/test_data_enrichment.py` | 1052 | test | Enrichment | Deterministic vs LLM payload | enrichment tests | Med | self | F-LOC-800 |
| `backend/app/services/design_system.py` | 1051 | production source | Design-token crawl + markdown export | Token extract vs markdown vs sitemap sample | `design_system.py` + `config/design_system` | Med | design-system tests if present | F-LOC-800 |
| `backend/app/services/extract/detail/price/core.py` | 1029 | production source | Detail price core | Currency reconcile vs zero-price drop vs original price | `extract/detail/price/` | **High** AP-12 prices | structured + field tests | F-LOC-800 |
| `backend/app/services/adapters/belk.py` | 1021 | production source | Belk adapter | State payload vs DOM cards vs brand-from-slug | `adapters/belk.py` | Med site-specific | adapter tests | F-LOC-800 |
| `backend/app/services/playground_service.py` | 1018 | production source | Playground session owner | Discover vs pipeline vs auto-advance | `playground_service.py` | Med | `test_playground_service.py` | F-LOC-800 |
| `backend/app/services/fetch/fetch_context.py` | 1013 | production source | Typed fetch_page | HTTP vs browser attempts vs handoff | `fetch/fetch_context.py` | High | `test_crawl_fetch_runtime.py` | F-LOC-800 |
| `backend/app/services/ucp_audit/protocol_checks.py` | 1012 | production source | UCP protocol probes | Transports vs schemas vs dimensions | `ucp_audit/` | Med | UCP tests | F-LOC-800 |
| `backend/app/services/acquisition/runtime.py` | 977 | production source | Acquisition runtime | Detail vs listing extractability signals | acquisition | High | fetch/traversal tests | F-LOC-800 |
| `frontend/components/crawl/log-terminal.tsx` | 975 | production source | Log terminal UI | Icon map vs grouping vs render (`log-terminal-utils.ts` exists) | crawl UI | Med | screen tests | F-LOC-800 |
| `backend/app/services/adapters/shopify.py` | 974 | production source | Shopify adapter | Public endpoint vs variant normalize vs linked handles | `adapters/shopify.py` | High | adapter tests | F-LOC-800 |
| `backend/tests/component/test_playground_service.py` | 957 | test | Playground service | Stage-by-stage | playground tests | Low | self | F-LOC-800 |
| `backend/app/services/review/__init__.py` | 952 | production source | Review + domain recipe | Payload vs promote vs selector candidates | `review/` | High review contracts | review tests | F-LOC-800 |
| `backend/tests/regression/test_detail_extractor_priority_and_selector_self_heal.py` | 933 | test | Priority + self-heal | Split the two concerns | extraction + selectors tests | Med | self | F-LOC-800 |
| `backend/app/services/data_enrichment/shopify_catalog.py` | 925 | production source | Shopify taxonomy index | Load vs match vs attributes (AP-18) | `data_enrichment/shopify_catalog.py` | Med | enrichment tests | F-LOC-800 |
| `backend/app/services/extract/variant_choice_traversal.py` | 925 | production source | Variant control traversal | Group name vs container vs iter groups | `extract/variant_choice_traversal.py` | High | variant tests | F-LOC-800 |
| `backend/tests/component/test_sitemap_resolver.py` | 923 | test | Sitemap resolver | Homepage vs category classify | crawl tests | Low | self | F-LOC-800 |
| `backend/app/services/pipeline/extraction_loop.py` | 915 | production source | Extraction loop facade | Trace vs persistence stage | `pipeline/extraction_loop.py` | High | `test_pipeline_core.py` | F-LOC-800 |
| `backend/app/services/crawl/sitemap_resolver.py` | 912 | production source | Sitemap + site-link discovery | Classify vs extract homepage entries | `crawl/sitemap_resolver.py` | Med | `test_sitemap_resolver.py` | F-LOC-800 |
| `backend/app/services/crawl/batch_runtime.py` | 898 | production source | Batch run orchestration | Span process vs URL failure persist | crawl batch runtime | High | `test_batch_runtime.py` | F-LOC-800 |
| `frontend/app/selectors/page-view.tsx` | 883 | production source | Selectors page | Reducer vs suggestion rows | `app/selectors/` | Med | selector tests | F-LOC-800 |
| `backend/app/services/data_enrichment/deterministic.py` | 882 | production source | Deterministic enrichment | Size/color/normalize buckets | `data_enrichment/deterministic.py` | Med | enrichment tests | F-LOC-800 |
| `backend/run_json_issue_audit.py` | 827 | script/tooling | JSON issue audit CLI | Same seams as `agent_debug` copy | tooling | Low; possible duplicate of `agent_debug/` | none | F-LOC-800 |
| `backend/app/services/dom/selector_engine.py` | 826 | production source | Selector engine | Node value vs fallbacks vs hidden | `dom/selector_engine.py` | High | selectolax tests | F-LOC-800 |
| `backend/app/services/listing_extractor.py` | 820 | production source | Listing facade | Card candidates vs record-from-card | `listing_extractor.py` | High | listing tests | F-LOC-800 |
| `backend/app/services/extract/listing_candidate_ranking.py` | 808 | production source | Listing rank/drop | Quality metrics vs utility URL vs dedupe | `extract/listing_candidate_ranking.py` | High | listing tests | F-LOC-800 |

---

## 5. Complexity Violations

**Metric:** Radon `cc` cyclomatic complexity (McCabe). Gate: **score > 15 fails**. Rank C includes 11–20, so **grade C is not the gate**.

**Command:** `python -m radon cc app tests browser_surface_probe -j` plus extra `harness` and `run_*.py`. Filter `complexity > 15`.

**Limitations / FP risk:** `try`/`except`/`with`/`if`/`for`/`and`/`or` all increment; class CC includes methods; nested functions counted separately; Radon does not measure cognitive complexity.

**ESLint:** `pnpm exec eslint . --rule "complexity: [error, 15]"` — 42 violations. JSX-heavy page components inflate CC.

**Counts (Python):** 333 callables: 16–20: **164**; 21–30: **111**; 31–40: **32**; ≥41: **26**. Frontend: **42**.

Simplification seam (default): extract **named predicates / stage functions in the same owner file/package**; do not add a new cross-cutting helper layer (AP-5/AP-15).

Paths below are under `backend/` unless they already include `backend/` or `frontend/`.

### Python (complete inventory)

| File:line | Symbol | Language | Complexity | Production/test | Control-flow cause | Simplification seam | Finding ID |
|---|---|---|---:|---|---|---|---|
| `app/services/shared/field_coerce.py:828` | `coerce_field_value` | Python | 96 | production | Giant per-field type switch | Dispatch table to existing `field_coerce_*` owners | F-CC-15 |
| `app/services/extract/detail/identity/shell_filter.py:42` | `looks_like_site_shell_record` | Python | 86 | production | Many independent shell heuristics | One predicate per evidence kind | F-CC-15 |
| `app/services/extract/field_candidates/structured_payloads.py:213` | `collect_structured_candidates` | Python | 85 | production | Nested payload walks + field switches | Per-payload-shape collectors already nearby | F-CC-15 |
| `browser_surface_probe/core.py:1015` | `build_findings` | Python | 78 | tooling | Finding taxonomy branches | Per-finding builders in probe package | F-CC-15 |
| `app/services/extract/detail/assembly/dom_fallbacks.py:45` | `apply_dom_fallbacks` | Python | 68 | production | Per-field DOM fallback chain | Field-owned fallback functions | F-CC-15 |
| `app/services/extract/variant_choice_traversal.py:664` | `iter_variant_choice_groups` | Python | 63 | production | DOM shape + grouping guards | Iterator vs filter split in same module | F-CC-15 |
| `tests/component/test_monitors_api_e2e.py:61` | `test_monitor_api_end_to_end_with_monitor_form_settings` | Python | 62 | test | Monolithic e2e script | Scenario helpers | F-CC-15 |
| `app/services/page_audit/analysis.py:279` | `_dom_checks` | Python | 60 | production | Many independent DOM checks | One function per check, list-run | F-CC-15 |
| `run_extraction_smoke.py:170` | `_run_one` | Python | 54 | tooling | Smoke orchestration | Result classify vs fetch | F-CC-15 |
| `app/services/listing_extractor.py:162` | `_build_card_candidates` | Python | 51 | production | Card assembly branches | Use `listing_signals` owners | F-CC-15 |
| `tests/component/test_crawls_api_domain_recipe.py:82` | `test_crawls_domain_recipe_routes_round_trip` | Python | 50 | test | Round-trip mega-test | Split assertions by route | F-CC-15 |
| `app/services/extract/detail/assembly/dom_completion.py:236` | `_requires_dom_completion` | Python | 49 | production | Early-exit vs cue conjunctions | Keep in this owner; predicate helpers (AP-12) | F-CC-15 |
| `app/services/public_record_firewall.py:52` | `public_record_data_for_surface` | Python | 49 | production | Surface allowlists | Config-driven field sets | F-CC-15 |
| `app/services/acquisition/browser_pool.py:709` | `_evict_idle_browser_runtimes_locked` | Python | 47 | production | Pool eviction states | State machine helpers in pool module | F-CC-15 |
| `app/services/acquisition/browser_page_flow.py:274` | `settle_browser_page_impl` | Python | 46 | production | Readiness + settle branches | Existing page-flow splits | F-CC-15 |
| `app/services/js_state/variant_options.py:86` | `variant_option_values` | Python | 45 | production | Option-shape unions | Per-shape parsers | F-CC-15 |
| `harness/support.py:172` | `infer_surface` | Python | 45 | tooling | Token/URL heuristics | Config tokens | F-CC-15 |
| `app/services/extract/field_candidates/variant_rows.py:325` | `_structured_variants_from_product_payload` | Python | 44 | production | Payload union | Per-key extractors | F-CC-15 |
| `app/services/extract/detail/variants/state_targets.py:17` | `state_variant_targets` | Python | 43 | production | Target discovery branches | List of target rules | F-CC-15 |
| `app/services/pipeline/extract_records.py:49` | `extract_records` | Python | 43 | production | Stage orchestration | Keep facade; extract stage calls already split | F-CC-15 |
| `app/services/review/__init__.py:399` | `_collect_selector_candidates` | Python | 43 | production | Candidate ranking branches | Selector runtime owner | F-CC-15 |
| `harness/support.py:490` | `classify_failure_mode` | Python | 43 | tooling | Failure taxonomy | Table of matchers | F-CC-15 |
| `app/services/extract/detail/identity/core.py:1102` | `_detail_redirect_identity_is_mismatched` | Python | 42 | production | Identity mismatch conjunctions | Stay in identity package | F-CC-15 |
| `app/services/extract/content_surface_extractor.py:445` | `_markdown_lines` | Python | 41 | production | Markdown line-state machine | Block parsers | F-CC-15 |
| `app/services/listing_extractor.py:280` | `_listing_record_from_card` | Python | 41 | production | Card field fill | `listing_signals` | F-CC-15 |
| `app/services/selectors_runtime.py:404` | `suggest_selectors` | Python | 41 | production | Suggest heuristics | Existing `selector_suggestions.py` | F-CC-15 |

Remaining Python 16–40 (same finding ID `F-CC-15`; cause = nested guards / unions / orchestration unless the name is a test):

`sanitize_variant_row` 40; `discover_ucp_manifest` 39; `option_value_labels` 38; `_persist_discovery_job` 38; `_materialize_record` 37; `_variant_choice_container_for_input` 37; `score_candidate` 37; `_observed_quality_failure_mode` 37; `requested_content_extractability_impl` 36; `_listing_record_quality_metrics` 36; `_apply_llm_payload` 35; `apply_selector_fallbacks` 35; `resolve_variant_group_name` 35; `_normalize_variant` 35; `run_test_sites_acceptance.main` 35; `_maybe_warm_origin_before_navigation` 34; `extract_heading_sections` 34; `backfill_variants_from_dom_if_missing` 34; `_cluster_visual_elements` 34; `MonitorChangeDetectionService` 34; `persist_extracted_records` 34; `detail_image_matches_primary_family` 33; `handle_run_complete` 33; `_auto_advance` 33; `_parse_serpapi_immersive_results` 33; `_next_data_product` 32; `extract_node_value` 32; `_repair_detail_variant_prices_and_identity` 31; `_run_browser_attempts` 31; `_map_product_payload` 31; `_audit_traces` 31; `apply_domain_recipe_field_action` 31; `count_listing_cards` 30; `_detail_structured_payload_is_irrelevant_product` 30; `finalize_candidate_value` 30; `_structured_variant_rows` 30; `extract_listing_records` 30; `build_url_metrics` 30; `_ecommerce_node_has_product_evidence` 29; `oracle_hcm._try_public_endpoint` 29; `_populate_adapter_records` 29; `build_domain_recipe_payload` 29; `_snapshot_to_resolved` 29; `load_site_set` 29; `shopify._build_product_record` 28; `_process_run_with_span` 28; `VariantGroupValidator` 28; `flatten_variants_for_public_output` 28; `select_variant` 28; `_availability_payload_detail_result` 28; `detect_platform_family` 28; `_find_pollution` 28; `expand_interactive_elements_via_accessibility_impl` 27; `probe_browser_readiness_impl` 27; `listing_url_is_structural` 27; `reconcile_variant_availability_from_dom` 27; `_select_primary_anchor` 27; `_listing_candidate_raw_price` 27; `VariantGroupValidator.validate` 27; `_marketplace_choice_product` 27; `variant_selection_values` 27; `normalize_value` 27; `apply_selector_self_heal` 27; `browser_surface_probe._target_root_cause` 26; `_run_paginate_traversal` 26; `saashr._try_public_endpoint` 26; `AdapterRuntimeSettings` 26; `_clean_detail_category_path` 26; `_detail_image_candidate_is_usable` 26; `sanitize_detail_long_text` 26; `_unsupported_non_detail_ecommerce_merchandise_hint` 26; `variant_axis_name_is_semantic` 26; `resolve_variants` 26; `run_prompt_task` 26; `_detail_url_matches_page` 26; `normalize_decimal_price` 26; `score_record_confidence` 25; `AdapterRuntimeSettings._validate` 25; `_apply_profile_defaults` 25; `create_crawl_run` 25; `top_taxonomy_candidates` 25; `_detail_image_title_matches_requested_identity` 25; `_visual_cluster_to_record` 25; `get_surface_field_aliases` 25; `apply_llm_fallback` 25; `_record_extraction_trace` 25; `test_split_reset_crawl_data_and_domain_memory_preserve_the_other_scope` 25; `oracle_hcm._normalize_requisition` 24; `html_parser.find_all` 24; `_is_other_detail_link` 24; `variant_option_availability` 24; `listing_record_supported` 24; `_extract_price_signal_from_card` 24; `_normalize_separate_dimension_size_rows` 24; `refresh_record_commit_metadata` 24; `_promote_review_bucket_fields` 24; `_find_variant_issues` 24; `belk._extract_listing_records` 23; `belk._variant_from_payload` 23; `shopify._normalize_variant` 23; `_field_penalties` 23; `discover_rendered_category_links` 23; `image_candidate_score` 23; `extract_section_content` 23; `_inline_markdown` 23; `_structured_offer_variant_rows` 23; `looks_like_utility_url` 23; `_descendant_variant_group_name` 23; `canonical_public_record_url` 23; `_option_group_variant_rows` 23; `compare_to_baseline` 23; `_overlay_listing_rows_from_adapter` 23; `_best_nested_listing_items` 23; `_sanitize_option_scalar` 23; `test_extract_ecommerce_detail_returns_normalized_record` 23; `test_map_js_state_to_fields_recovers_next_data_shopify_product_fields` 23; `build_playwright_context_spec` 22; `_select_primary_browser_html` 22; `_emit_challenge_activity` 22; `build_success_acquisition_contract` 22; `_looks_like_category_url` 22; `_frontmatter_yaml` 22; `_detail_image_family_tokens_disagree_on_colorway` 22; `_expand_compound_option_group` 22; `_deep_merge_structured_dict` 22; `_record_url_suffix_after_title` 22; `drop_color_only_rows_when_size_rows_exist` 22; `_try_browser_http_handoff` 22; `_handle_http_result` 22; `extract_search_result_snapshot` 22; `_currency_hint_from_page_url` 22; `validate_record_for_surface` 22; `is_title_noise` 22; `_find_incorrect_fields` 22; `browser_pool._ensure` 21; `amazon._extract_detail_variants` 21; `belk._infer_belk_brand_from_slug_prefix` 21; `belk._variants_from_sku_arrays` 21; `_drop_invalid_detail_discounts` 21; `_variant_choice_container_is_overbroad` 21; `variant_scope_roots` 21; `_validated_xpath_rules` 21; `extract_urls` 21.

CC 16–20 (still fail ≤15): `shopify.try_public_endpoint` 20; `workday._extract_listing` 20; `merge_saved_run_profile` 20; `data_enrichment._run_job` 20; `html_parser._attrs_match` 20; `extract_selector_value` 20; `_detail_url_looks_like_product` 20; `reconcile_detail_currency_with_url` 20; `detail_long_text_chunk_is_other_product` 20; `_variant_axis_value_from_option_url` 20; `expand_existing_variants_with_dom_axes` 20; `backfill_listing_rows_from_network` 20; `_enforce_variant_currency_context` 20; `_remap_generic_variant_axes` 20; `_extract_size_value` 20; `drop_parent_shared_variant_axes` 20; `pre_check_url` 20; `_has_detail_anchor` 20; `artifact_table_rows` 20; `save_review` 20; `promote_domain_recipe_selectors` 20; `_append_reduced_node` 20; `create_selector_record` 20; `_quality_category_clean_ok` 20; `ready_probe_supports_fast_finalize` 19; `_http_cookie_pairs_for_url` 19; `_has_extractable_detail_signals` 19; `looks_like_paginate_control` 19; `jibe._normalize_job` 19; `myntra._extract_listing_records` 19; `resolve_category_urls_with_site_links` 19; `build_operational_metrics` 19; `normalize_sizes` 19; `phrase_path_category_match` 19; `load_attribute_repository_data` 19; `load_taxonomy_index` 19; `_brand_from_title_prefix` 19; `_prune_irrelevant_detail_structured_payload` 19; `_apply_detail_original_price` 19; `_control_join_keys` 19; `_variant_choice_entry_value` 19; `_drop_variant_derived_parent_axis_scalars` 19; `_record_has_supporting_signals` 19; `meaningful_table` 19; `_collapse_mislabeled_duplicate_axes` 19; `_vtex_state_product_price` 19; `_resolve_category_list_for_inputs` 19; `start_pipeline` 19; `auto_save_dom_observed_selectors` 19; `update_selector_record` 19; `parse_test_sites_markdown` 19; `_find_logical_errors` 19; `_build_summary` 19; `test_build_url_metrics_promotes_traversal_diagnostics` 19; `recover_browser_challenge` 18; `_normalize_cookies` 18; `_has_extractable_listing_signals` 18; `adp._extract_listing` 18; `algolia_jobs._normalize_hit` 18; `_decode_firestore_value` 18; `greenhouse._extract_from_html` 18; `shopify._linked_handle_family_prefix` 18; `_extract_homepage_candidate_entries` 18; `compose_runtime_selector_rules` 18; `_normalize_detail_tables` 18; `_listing_query_looks_structural` 18; `_sanitize_detail_images` 18; `base_listing_fragment_score` 18; `_visual_cluster_score` 18; `_listing_candidate_currency` 18; `_structured_listing_record` 18; `_anchor_has_inline_variant_option_signal` 18; `_clean_variant_rows` 18; `apply_direct_record_llm_fallback` 18; `resolve_listing_readiness_platform` 18; `looks_like_product_detail_url` 18; `run_health_verdict` 18; `build_review_payload` 18; `_merge_selector_rules` 18; `_challenge_summary_from_diagnostics` 18; `browser_failure_kind` 17; `browser_pool.page` 17; `wait_for_listing_readiness_impl` 17; `_run_load_more_traversal` 17; `greenhouse._normalize_detail_record` 17; `commit_selected_fields` 17; `apply_acquisition_contract_to_profile` 17; `record_acquisition_contract_outcome` 17; `extract_label_value_pairs` 17; `_collapse_tokenized_code_block` 17; `sanitize_detail_placeholder_scalars` 17; `promote_detail_title` 17; `_detail_url_candidate_is_low_signal` 17; `title_looks_like_brand_shell` 17; `_detail_image_stem_looks_encoded` 17; `_reconcile_detail_price_currency` 17; `reconcile_parent_price_against_variant_range` 17; `collect_inline_scalar_rows` 17; `_clean_materials_pollution` 17; `_breadcrumb_names` 17; `_variation_attribute_labels` 17; `_should_drop_record` 17; `evaluate_listing_integrity` 17; `_card_title_score` 17; `_visual_cluster_brand` 17; `_choice_option_text` 17; `merge_variant_rows` 17; `_prune_child_size_rows_from_adult_products` 17; `_extract_trailing_color_phrase` 17; `drop_parent_sku_alias_variant_rows` 17; `_extract_vtex_state_listing_items` 17; `availability_value` 17; `_map_ecommerce_detail_state` 17; `_extract_ecommerce_description_fields` 17; `build_page_audit_report` 17; `_run_persistence_stage` 17; `_retry_listing_integrity_with_stronger_tier` 17; `record_detail_expansion_extraction_outcome` 17; `_selected_manifest_payload` 17; `config._check_secret_defaults` 16; `browser_capture.close` 16; `requested_field_tokens` 16; `browser_result_builder.build` 16; `persist_context_storage_state` 16; `_collect_structured_script_fragments` 16; `click_with_retry` 16; `icims._extract_listing` 16; `icims._extract_row_from_soup` 16; `try_blocked_adapter_recovery` 16; `shopify._linked_variant_product_handles` 16; `resolve_category_urls_from_sitemap_result` 16; `_classify_homepage_candidate` 16; `build_design_tokens` 16; `build_design_markdown` 16; `gallery_image_score` 16; `section_text_is_meaningful` 16; `_node_is_hidden_or_auxiliary` 16; `_looks_like_css_selector` 16; `_variant_parent_availability_value` 16; `drop_low_signal_zero_detail_price` 16; `variant_option_url` 16; `_listing_record_dedupe_key` 16; `_structured_listing_items` 16; `normalized_variant_axis_display_name` 16; `_backfill_variant_shared_fields_from_record` 16; `_drop_polluted_parent_scalar_axes` 16; `fetch_page` 16; `normalize_field_key` 16; `_variant_matrix_row` 16; `update_monitor` 16; `_canonicalize_decimal_candidate` 16; `update_baseline` 16; `extract_product_snapshot` 16; `_score_candidate_if_ready` 16; `_derive_acquisition_info` 16; `_balanced_json_fragment` 16; `crawl_catalog` 16; `build_markdown_report` 16; `_looks_like_site_shell_success` 16; `_expectation_met` 16; `_expected_contract_met` 16; `test_alert_api_end_to_end_with_dummy_product_change` 16; `test_amazon_adapter_extracts_detail_completeness_fields` 16; `test_structure._module_all_names` 16.

Full Radon CSV with file:line for every row was written during the review to `%TEMP%\invoro-prod-metrics\radon-gt15-all.csv`.

### TypeScript/TSX/JS (complete)

| File:line | Symbol | Language | Complexity | Production/test | Control-flow cause | Simplification seam | Finding ID |
|---|---|---|---:|---|---|---|---|
| `frontend/components/crawl/crawl-run-screen.tsx:108` | `CrawlRunScreen` | TSX | 131 | production | Page-level render + state | Push remaining UI to existing controller/hooks | F-CC-15 |
| `frontend/app/data-enrichment/page-view.tsx:92` | `DataEnrichmentPage` | TSX | 74 | production | Page branches | Section components in same route | F-CC-15 |
| `frontend/components/crawl/crawl-config-screen.tsx:86` | `CrawlConfigScreen` | TSX | 57 | production | Form sections | `crawl-config-logic.ts` already owner | F-CC-15 |
| `frontend/components/crawl/markdown-output.tsx:154` | `MarkdownPreview` | TSX | 52 | production | Markdown/KaTeX cases | Parser vs preview | F-CC-15 |
| `frontend/components/crawl/log-terminal.tsx:66` | `getLogIconDescriptor` | TS | 52 | production | Icon switch | Map/table | F-CC-15 |
| `frontend/components/crawl/use-crawl-run-controller.ts:49` | `useCrawlRunController` | TS | 50 | production | Hook orchestration | Split effects by concern | F-CC-15 |
| `frontend/components/monitors/monitor-form.tsx:125` | `MonitorForm` | TSX | 44 | production | Form + reducer | Keep with `monitorFormReducer` | F-CC-15 |
| `frontend/app/playground/page.tsx:67` | `PlaygroundPage` | TSX | 43 | production | Multi-stage UI | Existing workflow hook | F-CC-15 |
| `frontend/components/selectors/domain-memory/build-workspaces.ts:28` | `buildDomainWorkspaces` | TS | 42 | production | Workspace assembly | Per-tab builders | F-CC-15 |
| `frontend/components/crawl/log-terminal.tsx:657` | (arrow) | TSX | 37 | production | Render branch | Extract row renderer | F-CC-15 |
| `frontend/app/ucp-audit/ucp-audit-components.tsx:593` | `UcpContractPanel` | TSX | 37 | production | Panel sections | Split file (also >800 LOC) | F-CC-15 |
| `frontend/app/playground/page.tsx:462` | `humanizeLogMessage` | TS | 36 | production | Message taxonomy | Move next to playground normalizers | F-CC-15 |
| `frontend/app/dashboard/page.tsx:107` | `DashboardPage` | TSX | 31 | production | Dashboard widgets | Widget components | F-CC-15 |
| `frontend/components/crawl/alert-builder-drawer.tsx:84` | `AlertBuilderDrawer` | TSX | 29 | production | Drawer form | Shared with alert-form | F-CC-15 |
| `frontend/components/ui/dropdown.tsx:20` | `Dropdown` | TSX | 27 | production | A11y + variants | Keep in UI owner; extract key handlers | F-CC-15 |
| `frontend/components/crawl/crawl-config-logic.ts:320` | `buildDispatch` | TS | 27 | production | Dispatch assembly | Stay in this file | F-CC-15 |
| `frontend/components/monitors/monitor-header.tsx:99` | `MonitorHeader` | TSX | 26 | production | Header states | Status subview | F-CC-15 |
| `frontend/app/product-intelligence/use-product-intelligence.ts:23` | `useProductIntelligence` | TS | 25 | production | Job hook | Split query vs mutation | F-CC-15 |
| `frontend/components/monitors/monitor-list-item.tsx:27` | `MonitorListItem` | TSX | 24 | production | Row states | Presentational split | F-CC-15 |
| `frontend/components/crawl/log-terminal-utils.ts:269` | `buildLogSiteGroups` | TS | 24 | production | Grouping | Stay in utils | F-CC-15 |
| `frontend/app/playground/playground-normalizers.ts:121` | `normalizeSitemap` | TS | 23 | production | Sitemap shapes | Stay in normalizers | F-CC-15 |
| `frontend/app/run-trace/run-trace-page.tsx:245` | `RunTracePage` | TSX | 22 | production | Trace UI | Section components | F-CC-15 |
| `frontend/components/crawl/log-terminal.tsx:423` | `LogTerminal` | TSX | 21 | production | Terminal UI | Uses utils already | F-CC-15 |
| `frontend/app/ucp-audit/ucp-audit-components.tsx:401` | `UcpScoreSummary` | TSX | 21 | production | Score UI | Same package | F-CC-15 |
| `frontend/app/product-intelligence/product-intelligence-utils.ts:107` | (arrow) | TS | 21 | production | Mapping | Named function | F-CC-15 |
| `frontend/scripts/check-crawl-architecture.mjs:82` | `scanTemplateLiteral` | JS | 20 | tooling | AST walk | Acceptable in checker; still fails gate | F-CC-15 |
| `frontend/components/crawl/page-audit-workspace.tsx:34` | `PageAuditWorkspace` | TSX | 20 | production | Workspace UI | Same folder | F-CC-15 |
| `frontend/components/crawl/markdown-output.tsx:76` | `parseInlineMarkdownNodes` | TS | 20 | production | Inline markdown | Parser helper | F-CC-15 |
| `frontend/app/selectors/selector-page-utils.ts:50` | `mergeSelectorRows` | TS | 20 | production | Merge rules | Stay in utils | F-CC-15 |
| `frontend/components/monitors/monitor-form.tsx:64` | `monitorFormReducer` | TS | 19 | production | Reducer cases | Fine as reducer; still >15 | F-CC-15 |
| `frontend/components/crawl/log-terminal-utils.ts:93` | `getLogStage` | TS | 19 | production | Stage map | Table | F-CC-15 |
| `frontend/app/admin/llm/page.tsx:157` | `AdminLlmPage` | TSX | 19 | production | Admin form | Sections | F-CC-15 |
| `frontend/components/layout/app-shell.tsx:156` | `ShellContent` | TSX | 18 | production | Shell routing | Stay in layout owner | F-CC-15 |
| `frontend/app/selectors/page-view.tsx:98` | `selectorsPageReducer` | TS | 18 | production | Reducer | OK shape, still >15 | F-CC-15 |
| `frontend/components/ui/field.tsx:13` | `Field` | TSX | 17 | production | Field variants | Stay in UI owner | F-CC-15 |
| `frontend/components/monitors/alert-form.tsx:122` | `submit` | TS | 17 | production | Submit path | Stay in form | F-CC-15 |
| `frontend/components/layout/app-shell.tsx:382` | `getFallbackHeader` | TS | 17 | production | Header map | Table | F-CC-15 |
| `frontend/app/ucp-audit/ucp-audit-page.tsx:28` | `UcpAuditPage` | TSX | 17 | production | Page compose | Thin page | F-CC-15 |
| `frontend/app/selectors/page-view.tsx:792` | `buildRowFromSuggestion` | TS | 17 | production | Row map | Utils | F-CC-15 |
| `frontend/app/playground/use-playground-workflow.ts:42` | `usePlaygroundWorkflow` | TS | 17 | production | Workflow hook | Already the owner | F-CC-15 |
| `frontend/components/ui/dropdown.tsx:151` | `handleKeyDown` | TS | 16 | production | Keyboard cases | Stay in dropdown | F-CC-15 |
| `frontend/components/monitors/alert-form.tsx:85` | `AlertForm` | TSX | 16 | production | Form UI | Same file as submit | F-CC-15 |

---

## 6. Dead-Code Findings

**Tool:** Vulture **2.16**. Commands: `python -m vulture app --min-confidence 100|80|60 --exclude ".venv,artifacts,htmlcov"`. Configured threshold: `[tool.vulture] min_confidence = 100`.

**Limitations:** Misses decorator-registered FastAPI routes, Celery `.task(name=...)`, Pydantic fields, `__getattr__` config exports, tests-only usage, string imports.

### Confirmed

None. No symbol is unused after decorator/framework/test validation **and** high Vulture confidence.

### Likely

| Symbol | Evidence | Confidence |
|---|---|---|
| `shutdown_robots_policy` (`robots_policy.py:95`) | Repo-wide grep: definition only | medium |
| `find_first_script_text_matching` (`script_text_extractor.py:98`) | Definition only; sibling `iter_script_text_nodes_async` **is** tested | medium |

Do not delete without checking dynamic imports and worker shutdown paths.

### Uncertain/dynamic

~740 Vulture **60%** hits, dominated by FastAPI handlers, Celery beat/task registration, Pydantic `model_config` / schema fields, ORM attributes, and late imports.

### False positives

| Item | Why |
|---|---|
| `export/schema.py:75` `__context` (100%) | Required `model_post_init(self, __context)` Pydantic hook |
| Entire `app/api/*` unused-function list at 60% | FastAPI routing |
| Pydantic validators / `Field` attributes | Reflection |

Do **not** add a blocking Vulture CI job at 60%. If added, keep **100%** plus an allowlist for `__context` / framework hooks.

---

## 7. Duplication Findings

**Command (executed):** `npx --yes jscpd@4.2.4 --silent --min-lines 10 --min-tokens 50 --reporters json` on `backend/app frontend/app frontend/components frontend/lib`. Exit 0.

**Totals:** 750 files, **52** exact clones, **664** duplicated lines (**0.48%**), 6339 duplicated tokens. **3** clones ≥20 lines.

**High-value consolidation (same architectural owner):**

| Pair | Lines | Owner | Note |
|---|---:|---|---|
| `dispatch/celery_dispatcher.py` ↔ `local_dispatcher.py` | 15 | dispatch | Consolidate shared scheduling contract only if both must stay |
| `api/data_enrichment.py` ↔ `api/product_intelligence.py` | 14 | API | Job CRUD shape |
| `listing_extractor.py` ↔ `extract/detail/assembly/candidate_collection.py` | 16 | extraction | Confirm same rule before DRY (AP-9) |
| `structured_sources.py` ↔ `adapters/shopify.py` | 15 | extraction vs adapter | Prefer adapter-specific vs generic structured path |
| `models/data_enrichment.py` ↔ `models/product_intelligence.py` | 15 | models | Similar job ORM |

**Intentional/acceptable:** intra-file clones (`batch_runtime.py`, `playground.py`, `field.tsx`, `alert.py` schema); frontend test clones (`alert-workflow` vs `monitor-workflow`); small 10–14 line fragments.

**Recommended future CI threshold (not approved):** fail if jscpd on `backend/app` + `frontend/{app,components,lib}` excluding `**/*.{test,spec}.*` reports **duplicatedLines > 900** or **percentage > 1.0** at `--min-lines 12 --min-tokens 70`. Current 664 / 0.48% would pass. Do **not** gate on tests.

---

## 8. Lint and Format Findings

### Backend

**Enforced in CI:** `python -m ruff check app tests` (correctness subset only). `python -m mypy app`.

**Local, not CI:** `python -m ruff format --check app tests` — **passed** (621 files). **No pre-commit** config in repo.

**Gaps:** Ruff does not enable `C90`/`C901`. Pylint design limits exist (`max-branches = 12`, `max-module-lines = 1000`) but Pylint is not CI. `basedpyright`/`bandit` in dev extra, unused in workflows.

**Recommended gate ownership:** extend `.github/workflows/backend-ci.yml` job `backend`. Add format check beside Ruff. LOC/CC as separate steps using **physical** LOC and Radon numeric filter, **after** inventory is green.

### Frontend

**Enforced on PR:** `format:check`, `lint:eslint` (`--max-warnings=0`), architecture scripts, `typecheck`, `vitest`, `build`, `pnpm audit --audit-level=high`.

**Missing:** `push` trigger. No ESLint `complexity`. README `npm install` / `npm run dev` contradicts `packageManager: pnpm@11.9.0` and CI Corepack.

**Format/lint this session:** Prettier **pass**, ESLint **pass**, `tsc` **pass**. Adding `complexity: [error, 15]` **fails** (42).

**Recommended ownership:** extend `.github/workflows/frontend-quality.yml` job `quality`. Align README with pnpm. Complexity via ESLint rule in `eslint.config.mjs` once functions are split.

---

## 9. Dependency Findings

**Manifests:** `backend/pyproject.toml` (unpinned ranges + `uv.lock`); frontend `package.json` + `pnpm-lock.yaml`. CI backend: `pip install -e ".[dev]"` (range install, **not** `uv sync --frozen`).

**pip-audit** (local `.venv` via temp pip-audit): no findings, with or without `PYSEC-2025-183`. CI ignore targets disputed **PyJWT / CVE-2025-45768**. App JWT uses **`joserfc`**, not PyJWT (`backend/app/core/security.py`). Reachability of the disputed JWT key-length issue: **low**.

### Backend (selected)

| Package | Direct/transitive | Current version | Target version | Update class | Security/support reason | Compatibility risk | Required verification | Finding ID |
|---|---|---|---|---|---|---|---|---|
| redis | direct | 6.4.0 | stay 6.x **or** deliberate 7/8 | major if 8 | not CVE-driven here | **High** (asyncio API) | worker + cache tests | F-DEP-BE |
| ruff | direct (dev pin `==0.16.2`) | 0.16.2 | 0.16.4 | patch | lint engine | Low | `ruff check` | F-DEP-BE |
| sqlalchemy | direct | 2.0.51 | 2.0.52 | patch | maintenance | Low | unit/component | F-DEP-BE |
| uvicorn | direct | 0.52.1 | 0.52.4 | patch | maintenance | Low | smoke boot | F-DEP-BE |
| patchright | direct | 1.61.2 | 1.62.1 | minor | browser driver | Med | acquire smoke | F-DEP-BE |
| curl-cffi | direct | 0.16.0 | 0.16.1 | patch | HTTP impersonation | Low | fetch tests | F-DEP-BE |
| logfire | direct | 4.40.0 | 4.41.0 | minor | telemetry | Low | tests with LOGFIRE off | F-DEP-BE |
| mypy | direct (dev) | 2.3.0 | 2.3.1 | patch | types | Low | `mypy app` | F-DEP-BE |
| hypothesis | direct (dev) | 6.165.2 | 6.165.10 | patch | tests | Low | pytest unit | F-DEP-BE |
| mcp | transitive (fastmcp) | 1.29.0 | **do not** 2.0 in same batch | major | protocol | **High** | MCP wrappers | F-DEP-BE |
| argon2-cffi-bindings | transitive | 25.1.0 | 26.1.0 | major | bindings | Med | auth tests | F-DEP-BE |

### Frontend

| Package | Direct/transitive | Current version | Target version | Update class | Security/support reason | Compatibility risk | Required verification | Finding ID |
|---|---|---|---|---|---|---|---|---|
| nanoid | transitive (postcss/next/vite) | **3.3.17** (lock) | **≥3.3.18** | patch | **GHSA-2v37-7h3g-55p8** | Low for PostCSS; **CI high audit fails** | `pnpm audit --audit-level=high` | F-DEP-NANOID |
| react / react-dom | direct | 19.2.7 | 19.2.8 | patch | maintenance | Low | vitest + build | F-DEP-FE |
| @types/react(-dom) | direct dev | 19.2.17 / 19.2.3 | 19.2.18 / 19.2.4 | patch | types | Low | tsc | F-DEP-FE |
| vitest / coverage-v8 | direct dev | 4.1.8 | 4.1.10 | patch | tests | Low | `pnpm test` | F-DEP-FE |
| tailwindcss | direct | 4.3.0 | 4.3.3 | patch | CSS | Low | build | F-DEP-FE |
| zustand | direct | 5.0.14 | 5.0.15 | patch | state | Low | vitest | F-DEP-FE |
| prettier | direct dev | 3.8.3 | 3.9.6 | minor | format | Low | format:check | F-DEP-FE |
| next | direct | 16.2.12 | 16.3.1 | minor | framework | Med | build + e2e | F-DEP-FE |
| eslint-config-next | direct | 16.2.6 | 16.3.1 | minor | lint | Med | eslint | F-DEP-FE |
| @playwright/test | direct | 1.60.0 | 1.62.1 | minor | e2e | Med | smoke spec | F-DEP-FE |
| lucide-react | direct | 1.17.0 | 1.31.0 | minor | icons | Low | build | F-DEP-FE |
| recharts | direct | 3.8.1 | 3.10.1 | minor | charts | Med | dashboard tests | F-DEP-FE |
| react-hook-form / resolvers | direct | 7.78.0 / 5.4.0 | 7.85.0 / 5.8.0 | minor | forms | Med | monitor/alert forms | F-DEP-FE |
| eslint | direct pin `9.39.4` | 9.39.4 | **10.8.1** | **major** | lint | **High** | keep 9 until Next supports | F-DEP-FE |
| typescript | direct | 6.0.3 | **7.0.2** | **major** | types | **High** | separate slice | F-DEP-FE |
| jsdom | direct | 29.1.1 | 30.0.1 | major | test env | High | vitest | F-DEP-FE |
| @testing-library/jest-dom | direct | 6.9.1 | 7.0.1 | major | tests | High | vitest | F-DEP-FE |
| katex | direct (used) | 0.17.0 | 0.18.4 | minor/major | markdown math | Med | markdown-output | F-DEP-FE |

**Safe batches:** (1) nanoid ≥3.3.18 override; (2) frontend patches (react 19.2.8, types, vitest, tailwind, zustand); (3) backend patches (ruff, sqlalchemy, uvicorn, curl-cffi, mypy) then `uv lock`; (4) frontend minors isolated (prettier, lucide, then Next 16.3 + eslint-config-next together). **Do not batch:** redis 8, mcp 2, ESLint 10, TypeScript 7, jsdom 30, testing-library 7, patchright with browser smoke.

`katex` **is used**. README mentions BeautifulSoup/extruct; **no `bs4`/`extruct` in `backend/app`** (stale README).

---

## 10. Other Verified Production Blockers

None found in this focused review at P0.

Incidental (not stop-launch by themselves):

- Frontend high audit failure (F-DEP-NANOID) is a **CI/delivery** P1 if branch protection requires `Frontend Quality`; exploitability of nanoid `size===0` in PostCSS is **not demonstrated**.
- `docs/CODEBASE_MAP.md` lists `health.py`; routes live in `main.py` (docs drift, P3).
- README Node 20+/`npm` vs CI Node 22/`pnpm` (fresh-clone friction, P2).

Health: `/health/live`, `/health/ready`, `/api/health` implemented (`backend/app/main.py`). Playwright smoke waits on `/api/health`.

---

## 11. Finding Register

| ID | Title | Area | Status | Severity | Confidence | Evidence | Owner | Depends on | Verification command |
|---|---|---|---|---|---|---|---|---|---|
| F-LOC-800 | 61 first-party files >800 physical LOC | size | FAIL | P2 | high | LOC scan 61/872 | extraction, acquisition, FE crawl, tests | — | physical line count |
| F-CC-15 | 333 Py + 42 JS/TS callables CC>15 | complexity | FAIL | P2 | high | radon + eslint | same owners | F-LOC-800 | radon filter; eslint complexity |
| F-CI-GATES | Absolute 800/15 not in CI | CI | FAIL | P2 | high | workflows | `.github/workflows` | F-LOC-800, F-CC-15 | workflow grep |
| F-BE-FORMAT-CI | Ruff format not in Backend CI | lint | FAIL | P2 | high | `backend-ci.yml` vs local pass | backend CI | — | `ruff format --check` |
| F-RUFF-NARROW | Ruff select lacks complexity/bugbear | lint | FAIL | P3 | high | `pyproject.toml` | backend lint | F-CC-15 | ruff |
| F-FE-PUSH | Frontend quality not on push | CI | FAIL | P2 | high | `frontend-quality.yml` `on:` | frontend CI | — | workflow |
| F-FE-COMPLEXITY | No ESLint complexity rule | lint | FAIL | P2 | high | `eslint.config.mjs` | frontend | F-CC-15 | eslint --rule complexity |
| F-DEP-NANOID | pnpm high audit fails (nanoid 3.3.17) | deps | FAIL | P1 | high | `pnpm audit --audit-level=high` exit 1 | frontend lockfile | — | `pnpm audit --audit-level=high` |
| F-DEP-BE | Backend outdated + redis range allows 8.x | deps | FAIL | P3 | medium | `uv pip list --outdated` | pyproject/uv.lock | — | uv outdated + tests |
| F-DEP-FE | Frontend minors/majors pending | deps | FAIL | P3 | high | `pnpm outdated` | package.json | F-DEP-NANOID | pnpm outdated |
| F-LOCK-CI | CI pip install vs uv.lock | deps | FAIL | P2 | high | `backend-ci.yml`; `uv.lock` present | backend CI | — | compare freeze |
| F-README-PM | README npm vs pnpm/Corepack | docs/setup | FAIL | P2 | high | README vs packageManager | README | — | follow README on clean clone |
| F-STRUCT-800 | Structure tests grandfather >800 | tests | FAIL | P2 | high | `DEFAULT_LOC_BUDGET=1000` | `test_structure.py` | F-LOC-800 | pytest test_structure |
| F-FE-BUDGET | Crawl architecture allows 1400–1500 lines | tests | FAIL | P2 | high | `check-crawl-architecture.mjs` | frontend scripts | F-LOC-800 | `pnpm run check:crawl-architecture` |
| F-VULTURE-CI | Vulture not CI; 60% unusable | dead code | N/A | P3 | high | pyproject + scan | optional later | — | vulture --min-confidence 100 |
| F-JSCPD-CI | No duplication CI | duplication | N/A | P3 | high | no config | optional | — | jscpd command |
| F-MAP-HEALTH | CODEBASE_MAP health.py missing | docs | FAIL | P3 | high | glob 0 files; `main.py` health routes | CODEBASE_MAP | — | grep health |
| F-PYTEST | Default pytest suite not re-run here | tests | UNVERIFIED | P2 | high | not executed | backend | — | pytest markers |
| F-VITEST | Vitest not re-run here | tests | UNVERIFIED | P2 | high | not executed | frontend | — | `pnpm test` |
| F-BRANCH-PROT | Whether Frontend Quality is required | CI | UNVERIFIED | P1 | low | GitHub settings not in repo | org | F-DEP-NANOID | GitHub branch protection |
| F-BE-LINT | Ruff check | lint | PASS | — | high | exit 0 | — | — | ruff check |
| F-BE-FMT-LOCAL | Ruff format | format | PASS | — | high | 621 formatted | — | — | ruff format --check |
| F-MYPY | mypy app | types | PASS | — | high | 461 files, exit 0 | — | — | mypy app |
| F-FE-LINT | ESLint max-warnings 0 | lint | PASS | — | high | exit 0 | — | — | lint:eslint |
| F-FE-FMT | Prettier check | format | PASS | — | high | exit 0 | — | — | format:check |
| F-TSC | tsc --noEmit | types | PASS | — | high | exit 0 | — | — | typecheck |
| F-PIP-AUDIT | pip-audit venv | deps | PASS | — | medium | no vulns; CI may differ vs pip -e | — | F-LOCK-CI | pip-audit |
| F-HEALTH | health endpoints | ops | PASS | — | high | main.py L574–589 | API | — | curl /api/health |
| F-ENV | .env.example | setup | PASS | — | high | file exists | — | — | — |
| F-VULTURE100 | Vulture 100% | dead code | PASS | — | high | 1 FP | — | — | vulture 100 |

---

## 12. Recommended Work Slices

Planning inputs only. Sequence: config/CI **shape** after splits; **do not** combine format, refactors, upgrades, and CI flips.

**Slice A — Unblock frontend audit CI**  
Objective: `pnpm audit --audit-level=high` green. IDs: F-DEP-NANOID, F-BRANCH-PROT. Files: `pnpm-workspace.yaml` / lockfile overrides. Verify: `pnpm audit --audit-level=high`. **CI can be blocking after this slice** (already is).

**Slice B — Document and optionally freeze backend installs**  
Objective: CI matches lockfile. IDs: F-LOCK-CI, F-README-PM. Files: `backend-ci.yml`, README, maybe `uv sync --frozen`. Verify: clean install from README.

**Slice C — Add format check only (already green)**  
Objective: `ruff format --check` in Backend CI. IDs: F-BE-FORMAT-CI. Files: `backend-ci.yml` only. Verify: ruff format --check. **CI blocking: yes immediately.**

**Slice D — Align LOC policy (tests/scripts, not production behavior)**  
Objective: structure + frontend architecture budgets move toward **physical 800** without claiming green. IDs: F-STRUCT-800, F-FE-BUDGET. Files: `test_structure.py`, `check-*.mjs`. **CI blocking at 800: no.**

**Slice E — Split oversized tests**  
Objective: 21 backend test files + 1 FE test under 800. IDs: F-LOC-800 (test subset). Files: `backend/tests/**`, `crawl-run-screen.test.tsx`. Verify: same pytest assertions via modules.

**Slice F — Split tooling scripts**  
Objective: probe/harness/audit scripts <800. IDs: F-LOC-800 tooling. Files: `browser_surface_probe/`, `harness/`, `run_json_issue_audit.py`, `agent_debug/`. Verify: harness tests.

**Slice G — Production file splits by owner (behavior-preserving)**  
Objective: 28 backend + 7 frontend production files under 800 physical lines, split only along existing CODEBASE_MAP / strategy owners. IDs: F-LOC-800 (production subset). Implement **per subsystem**, not one mega-PR. Preconditions: Slice D so ratchets shrink. Verify: focused owner tests + `test_structure.py` + frontend architecture scripts. **CI 800 blocking: no** until every listed file is under 800.

**Slice H — Complexity reduction in the same owners**  
Objective: Radon/ESLint CC ≤15 on remaining callables (333 Python + 42 JS/TS). IDs: F-CC-15, F-FE-COMPLEXITY, F-RUFF-NARROW. Combine with G when the hotspot **is** the oversized file; otherwise separate PRs per function family. Verify: radon filter; `eslint --rule complexity:[error,15]`. **CI complexity blocking: no** until inventory is empty.

**Slice I — Enable absolute LOC + complexity CI gates**  
Objective: blocking steps in `backend-ci.yml` and `frontend-quality.yml`. IDs: F-CI-GATES, F-FE-PUSH (optional push trigger). Preconditions: G+H+E+F green; format already on (C). **CI can become blocking at the end of this slice only.**

**Slice J — Safe dependency batches**  
Objective: patches/minors without mixing majors. IDs: F-DEP-BE, F-DEP-FE. Preconditions: A done; do **not** combine with G/H.

**Slice K — Optional duplication / Vulture**  
Objective: informational or later blocking jscpd/vulture@100. IDs: F-JSCPD-CI, F-VULTURE-CI. **CI blocking: not required** for the three primary gates.

---

## 13. Exact Proposed CI Gate Commands

Package managers: backend **pip in CI today** / **uv.lock present**; frontend **pnpm** (`packageManager: pnpm@11.9.0`).

### LOC ≤800 (physical lines)

**Tested** this review: Python scan writing `loc.json` — 61 files >800.

**Proposed CI shape** (must be committed and re-run in CI; not a committed script today): fail if any kept first-party `.py`/`.ts`/`.tsx`/`.js`/`.mjs` file has `splitlines()` length `> 800`. Exclude `node_modules`, `.venv`, `.next`, coverage, htmlcov, artifacts, `__pycache__`, `.mypy_cache`, `.pytest_cache`, dist, build, playwright-report, test-results.

Do **not** reuse `test_structure._source_loc` (non-blank). Do **not** use frontend crawl budgets 1400/1500 as the gate. **Would fail today.**

### Complexity ≤15

**Python (tested):**

```powershell
cd backend
$env:PYTHONPATH='.'
.\.venv\Scripts\python.exe -m radon cc app tests browser_surface_probe harness run_json_issue_audit.py run_extraction_smoke.py run_test_sites_acceptance.py -j
# fail if any block complexity > 15
```

Radon `-n C` is **wrong** for this gate (also fails 11–15). `-n D` is **wrong** (misses 16–20).

**Frontend (tested with JSON formatter):**

```powershell
cd frontend
pnpm exec eslint . --rule "complexity: [error, 15]" --max-warnings=0
```

(`-f unix` **failed**: formatter not installed. Use default or `-f json`.)

**Would fail today** (333 + 42).

### Backend lint / format / types

**Tested, currently pass:**

```powershell
cd backend
.\.venv\Scripts\python.exe -m ruff check app tests
.\.venv\Scripts\python.exe -m ruff format --check app tests
.\.venv\Scripts\python.exe -m mypy app
```

CI already runs check + mypy. **Proposed:** add the format line to `backend-ci.yml` job `backend`.

### Frontend lint / format / types

**Tested, currently pass:**

```powershell
cd frontend
pnpm run format:check
pnpm run lint:eslint
pnpm run typecheck
```

Already in `frontend-quality.yml`. **Proposed:** add `push` alongside `pull_request` if mainline should match backend.

### Tests relevant to quality-tool changes

**Proposed (match CI; not executed in this review):**

```powershell
cd backend
$env:PYTHONPATH='.'
.\.venv\Scripts\python.exe -m pytest tests -q -m "unit or component or regression"
```

```powershell
cd frontend
pnpm test
```

After LOC splits: `pytest tests/regression/test_structure.py -q` and `pnpm run check:frontend-architecture` / `check:crawl-architecture`.

### Dependency audits

```powershell
cd frontend
pnpm audit --audit-level=high
```

```powershell
# CI already:
pip-audit --vulnerability-service osv --ignore-vuln PYSEC-2025-183
```

Local venv had **no** findings even without the ignore. Prefer `uv lock` + audit of the **frozen** graph once F-LOCK-CI is resolved.

---

## 14. Verification Log

| Working directory | Exact command | Exit | Duration | Result summary | Truncation / limits |
|---|---|---:|---|---|---|
| repo root | `git rev-parse`; `git status --porcelain=v1`; `git log -1` | 0 | ~16s | `main`, `c091052c`, clean tree | none |
| repo root | Python physical LOC scan → `%TEMP%\invoro-prod-metrics\loc.json` | 0 | 72.5s | 872 files, 245981 LOC, 61>800, 43>1000, 123>500 | printed first 40 oversized; full list in `loc.json` |
| `backend` | `python -m radon cc app tests browser_surface_probe -j -n C` | 0 | 22.7s | JSON written; **316** CC>15 after numeric filter | `-n C` includes 11–15 in raw JSON; filter applied in Python |
| `backend` | `python -m radon cc harness run_*.py -j -n C` | 0 | ~18s (with vulture) | **+17** CC>15 | combined **333** |
| `backend` | `python -m vulture app --min-confidence 100` | 3 | ~5s (with 80) | 1 hit `__context` | exit 3 = findings |
| `backend` | `python -m vulture app --min-confidence 80` | 3 | same | same 1 hit | — |
| `backend` | `python -m vulture app --min-confidence 60` | 3 | included above | **741** lines, mostly FastAPI/Pydantic | `vulture-60.txt` |
| `backend` | `python -m ruff check app tests browser_surface_probe harness` | 0 | 0.62s (with format) | All checks passed | — |
| `backend` | `python -m ruff format --check app tests browser_surface_probe harness` | 0 | same | 621 files already formatted | — |
| repo root | jscpd including missing `frontend/hooks` | 1 | 114s | **ENOENT** `frontend/hooks` | first attempt invalid |
| repo root | jscpd on existing source paths | 0 | 27.6s | 52 clones, 664 lines, 0.48% | scanned some FE tests colocated with app/components |
| `frontend` | `pnpm run format:check` | 0 | part of 147s | All matched files use Prettier | — |
| `frontend` | `pnpm run lint:eslint` | 0 | same | clean, max-warnings=0 | — |
| `frontend` | `pnpm run typecheck` | 0 | same | `tsc --noEmit` clean | — |
| `backend` | `python -m pip_audit` on project venv | 1 | 0.25s | `No module named pip_audit` | used temp venv instead |
| temp pip-audit venv | `pip_audit --path backend\.venv` | 0 | 89s | No known vulnerabilities | not CI `pip install -e` graph |
| same | same + `--ignore-vuln PYSEC-2025-183` | 0 | included | No known vulnerabilities | — |
| `frontend` | `pnpm audit --audit-level=high` | 1 | ~6s | 1 high: nanoid <3.3.18 | — |
| `frontend` | `pnpm outdated` | 1 | same | many patch/minor/major | pnpm exits 1 when outdated |
| `backend` | `python -m pip list --outdated` | 1 | ~5s with mypy | **No module named pip** in project venv | used `uv pip list --outdated` |
| `backend` | `python -m mypy app` | 0 | ~5s wall (likely cache) | Success: 461 source files | cache may hide cold duration |
| `backend` | `uv pip list --outdated` | 0 | ~16s | redis 6.4→8.1, ruff 0.16.2→0.16.4, others | uv 0.11.28 |
| `frontend` | eslint complexity `-f unix` | 2 | 38s | unix formatter missing | no complexity results |
| `frontend` | eslint complexity `-f json` | 1 | 30.7s | **42** complexity errors | expected fail |
| n/a | full pytest / vitest / pip-audit of **CI pip resolve** | — | — | **not run** | see §15 |

---

## 15. Unverified Items and Questions

- Whether GitHub **branch protection** requires `Frontend Quality` / `Backend CI` on `main` (F-BRANCH-PROT). If yes, **nanoid audit is a live red check** on PRs.
- **pytest** unit/component/regression and **Vitest** / Playwright smoke were **not** executed in this session.
- Exact **pip-audit** result of CI’s `pip install -e ".[dev]"` (unpinned ranges) versus this machine’s **uv-synced** `.venv`.
- Whether `shutdown_robots_policy` / `find_first_script_text_matching` are reached via **string import** or workers not present in-repo.
- Production **runtime** (TLS, backups, secret strength, Redis/Postgres versions in deploy) is outside the repository.
- Fresh-clone duration and whether `.\.venv\Scripts\pip` exists after `python -m venv` on Windows when the current venv has **no pip**.
- jscpd **4.2.4** vs previously mentioned **5.0.11** in old plan notes: this review used 4.2.4 only; 5.x totals UNVERIFIED.
- ESLint vs Radon **numeric equivalence** on identical algorithms: not cross-checked on a shared fixture.

No further questions that the tree already answers: frontend lint/format configs exist; backend Ruff/mypy/pytest/pip-audit **are** in CI; health routes **are** on `main.py`; `.env.example` **exists**; grader LOC/file-size numbers are **stale**.

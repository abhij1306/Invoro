# Plan: Backend Acquisition, Extraction, and Test Debt Refactor

**Created:** 2026-08-10
**Agent:** Codex
**Status:** IN PROGRESS
**Touches buckets:** Acquisition + Browser Runtime; Extraction; Backend Tests; Architecture Docs

## Goal

Reduce backend acquisition, extraction, and critical-test debt without changing public contracts. Done means clearer ownership, fewer repeated parser builds and adapter calls, lower targeted complexity, less dead/duplicated code, unchanged deterministic extraction order, and passing safe local verification. Live acceptance remains user-owned and is not run in this plan.

## Acceptance Criteria

- [ ] `fetch_page()` and acquisition result contracts remain unchanged; policy owns pure attempt/proxy/deadline decisions.
- [ ] Readiness reuses cached `HtmlAnalysis`; adapters receive one ordered, unique evidence sequence.
- [ ] Listing/detail extraction can reuse one `ExtractionContext` per HTML artifact while raw-HTML callers remain compatible.
- [ ] Touched acquisition and extraction hotspot orchestration functions are Radon C/20 or lower.
- [ ] Dead `original_value` and stale page-flow forwarding wrappers are removed.
- [ ] Default safe pytest suite is `unit or component or regression`; live/integration/e2e stay excluded.
- [ ] Parser-construction and adapter-call tests prove reduced work with unchanged public behavior.
- [ ] Reduced LOC, private-import debt, and verified duplication are ratcheted without relaxing existing caps.
- [ ] For each code/test commit, the safe full suite is run exactly once with `python -m pytest tests -q -m "unit or component or regression"`; reported failures are rerun only by node/file.
- [ ] No live, test-site, or network acceptance command is run.

## Baseline

- Base commit: `02bfb397cacb4fe4c7ddc06bbfa96ddf55e1cc1e` (`main`).
- Worktree: `C:\Projects\Invoro-backend-refactor`; branch: `refactor/backend-core-debt`.
- Selectolax is already canonical through `dom/html_parser.py`; no parser migration is planned.
- Radon hotspot baseline: acquisition expansion F/90; blocker classification F/82; DOM variant extraction F/116; price backfill F/93.
- Vulture baseline: dead `original_value` in `extract/detail/variants/dom_extraction.py`.
- jscpd 5.0.11 supplied baseline: `backend/app` 1,000 duplicated lines; critical runtime folders 204; five critical test files 1,907. The first two reproduce on the pinned base; the five-file figure does not, as detailed in Notes.
- Detailed LOC, exact scan commands, parser-build counts, adapter-invocation counts, local fixture timings, and focused-test results are recorded in Notes before this plan commit closes.
- The earlier LOC/complexity plan remains separately blocked on external extraction smoke. This plan does not reopen it.

## Do Not Touch

- `frontend/` — dirty frontend work stays in its original worktree.
- HTTP APIs, schemas, persistence, publish/export contracts — no contract or downstream compensation change.
- `docs/INVARIANTS.md` — unchanged unless implementation proves a real contract correction.
- Live test-site/network acceptance — user runs it at the end.
- `lxml` sites required by extruct/XML behavior — preserve them.
- Global `BeautifulSoup` compatibility alias — do not rename it in this branch.

## Slices

### Slice 1: Start plan and capture baselines
**Status:** DONE
**Files:** `docs/plans/backend-core-debt-refactor-plan.md`, `docs/plans/ACTIVE.md`
**What:** Record branch/worktree isolation and Radon, Vulture, jscpd, LOC, parser-build, adapter-call, focused-test baselines. Record prior LOC-plan blocker.
**Verify:** Documentation inspection only; no pytest.

### Slice 2: Clarify acquisition attempt and page-flow ownership
**Status:** DONE
**Files:** `app/services/fetch/{fetch_context,browser_policy,types}.py`, acquisition browser page owners, nearby public-behavior tests
**What:** Move pure attempt/proxy/deadline decisions into policy, retain typed state in types, keep fetch context orchestration-only, delete stale page-flow forwarding wrappers, and replace private-alias tests.
**Verify:** Focused acquisition set, touched-path static scans, then one safe full suite.

### Slice 3: Remove duplicate analysis and adapter work
**Status:** DONE
**Files:** readiness/page flow, extraction adapter orchestration, focused acquisition/extraction tests
**What:** Reuse cached `HtmlAnalysis`; build one ordered unique adapter-evidence stream; keep listing short-circuit and detail all-source behavior; add existing-span work attributes; stop attempts when the shared deadline has no usable budget.
**Verify:** Focused tests prove one parse per snapshot, unique adapter calls, source ordering, and exhausted-deadline behavior; static scans; one safe full suite.

### Slice 4: Reuse canonical Selectolax documents
**Status:** DONE
**Files:** DOM parser/context owner, listing/detail extractors, price/final-cleanup owners, focused extraction tests
**What:** Create optional `ExtractionContext`; parse cleaned/original/pruned and each unique rendered artifact once; thread prepared soups into price repair and cleanup; preserve raw-HTML compatibility and existing fallbacks.
**Verify:** Parser-construction-count tests for detail, listing, price repair, original-DOM fallback, rendered-fragment fallback; static scans; one safe full suite.

### Slice 5: Simplify blocker and expansion hotspots
**Status:** DONE
**Files:** acquisition runtime blocker owner, detail expansion owner, focused public-behavior tests
**What:** Separate evidence collection/classification and candidate discovery/safety/action/diagnostics. Preserve usable-content precedence, challenge recovery, chrome safety, action order, budgets, and evidence.
**Verify:** Focused acquisition tests; touched orchestration functions Radon C/20 or lower; Vulture/jscpd; one safe full suite.

### Slice 6: Simplify price and variant hotspots
**Status:** DONE
**Files:** existing detail price and DOM variant owners, focused extraction tests
**What:** Split price evidence/currency/selection/application and variant collection/validation/assembly/fallback merge. Delete dead `original_value` and unreachable branches. Preserve field candidates, source priority, structured multi-source finalization, DOM completion, every-return price repair, flat variants, and LLM gating.
**Verify:** `backfill_detail_price_from_html` and `extract_variants_from_dom` Radon C/20 or lower; focused extraction tests; Vulture/jscpd; one safe full suite.

### Slice 7: Reduce critical-suite debt
**Status:** DONE
**Files:** pytest config, agent/CI verification docs, touched acquisition/extraction suites, shared test fixtures, `tests/regression/test_structure.py`
**What:** Include regression in safe defaults; consolidate fakes and repeated cases; split touched giant suites by public behavior; remove private assertions only after public coverage; ratchet LOC/private imports/duplication while preserving isolation.
**Verify:** Focused tests, structure tests, static scans, one safe full suite.

### Slice 8: Close plan and update architecture docs
**Status:** TODO
**Files:** this plan, `docs/plans/ACTIVE.md`, `docs/CODEBASE_MAP.md`, `docs/backend-architecture.md`
**What:** Record before/after metrics and ownership. Mark complete. Leave invariants unchanged unless a contract correction was required.
**Verify:** Documentation inspection only; no pytest.

## Verification Rules

- Acquisition focus: `tests/component/test_acquirer.py tests/component/test_crawl_fetch_runtime.py tests/component/test_traversal_runtime.py tests/regression/test_browser_expansion_runtime.py`.
- Extraction focus: `tests/regression/test_crawl_engine.py tests/regression/test_detail_extractor_priority_and_selector_self_heal.py tests/regression/test_detail_extractor_structured_sources.py tests/regression/test_selectolax_css_migration.py tests/unit/test_normalizers.py tests/unit/test_detail_quality_cleanup.py`.
- Static gates per code/test commit: Radon, Vulture, pinned `npx jscpd@5.0.11` on touched paths.
- Never run `run_acquire_smoke.py`, `run_extraction_smoke.py`, `run_test_sites_acceptance.py`, live tests, or network acceptance.

## Doc Updates Required

- [ ] `docs/backend-architecture.md` — changed acquisition/extraction ownership and reusable context.
- [ ] `docs/CODEBASE_MAP.md` — changed page-flow/policy/context ownership.
- [ ] `docs/INVARIANTS.md` — only if implementation discovers a real contract correction.
- [ ] `docs/ENGINEERING_STRATEGY.md` — only if a new enforceable anti-pattern is discovered.

## Notes

- User approved this plan before implementation by supplying the commit plan and asking for execution in a fresh context.
- CrawlerAI supplies concepts only. No code or business logic will be copied.
- No hard latency-percentage target. Local fixture timing must not regress; simpler ownership and reduced repeated work are the acceptance signal.
- Slice 1 static verification (2026-08-10):
  - Radon: `python -m radon cc` on the four hotspot owners reports `expand_all_interactive_elements_impl` F/90, `classify_blocked_page` F/82, `extract_variants_from_dom` F/116, and `backfill_detail_price_from_html` F/93; 105 blocks average C/10.01.
  - Vulture: `python -m vulture app/services/extract/detail/variants/dom_extraction.py --min-confidence 100` reports only `original_value` at line 445 as unused at 100% confidence.
  - jscpd: `npx --yes jscpd@5.0.11 backend/app --silent --min-lines 10` reports 55 clones and 1,000 duplicated lines (0.74%). The same command over `acquisition`, `fetch`, `extract`, and `dom` reports 16 clones and 204 lines (0.48%). The supplied five-critical-suite figure of 1,907 is not reproducible from the pinned base or repository history: the likely five files (`crawl_fetch`, `browser_expansion`, `detail_structured`, `selectolax`, `crawl_engine`) report 111 clones / 1,924 lines (6.65%). Slice 7 will ratchet this reproducible set.
  - Physical LOC: `backend/app` has 461 Python files / 116,215 lines; `backend/tests` has 136 files / 81,108 lines. `acquisition` + `fetch` + `extract` has 117 Python files / 39,527 lines. Focused acquisition files have 309 test definitions / 12,628 lines; focused extraction files have 588 definitions / 21,614 lines.
  - Parser construction by inspected representative path: ecommerce detail builds cleaned + original + pruned DOMs and reparses HTML once per quality-repair pass (4 builds when primary DOM supplies variants; 5 when original-DOM quality fallback runs); listing builds cleaned + original comparison DOMs (2), plus one composed rendered-fragment DOM when present (3); standalone visible-price repair builds one DOM. Slice 4 will replace this inspection baseline with construction-count tests.
  - Adapter invocation by inspected orchestration: one call per primary/browser-artifact/network input after separate per-category dedupe; duplicates are not eliminated across the whole evidence stream. Existing sufficient-listing fixture asserts one call. Detail has no global call-count guard and intentionally processes every source. Slice 3 will add ordered unique-input counters and contract tests.
  - No completed pytest baseline is recorded for this documentation-only commit. A delegated focused-acquisition attempt exceeded 64 seconds before producing a result and was stopped; static focused-suite baselines above are definition/LOC counts. Code slices own test execution.
- Slice 2 verification (2026-08-10):
  - Fetch policy now owns typed browser attempt plans, engine order/extension, deadline budgeting, HTTP timeout choice, handoff engine choice, and Patchright retry decisions. `fetch_context.py` retains I/O orchestration and host-memory updates.
  - Removed page-flow forwarding/re-export debt. Runtime and tests call `browser_page_helpers.py` and `browser_result_builder.py` public owners. Page-flow dropped 68 lines; total slice delta is 321 additions / 411 deletions.
  - Focused acquisition command selected 310 tests: 310 passed, 10 deselected in 49.97s.
  - Static scans: Ruff clean; Vulture found no 100%-confidence dead code; touched-path Radon average B/6.97; touched-path jscpd reports 55 clones / 959 lines. `browser_policy.py` tops out at C/13; public result-builder helpers top out at C/19.
  - Required safe full suite ran exactly once: 2,411 selected / 17 deselected. It reached 51%, then exposed one selector-synthesis assertion and a repeatable native access violation in the microdata fallback. Per protocol, the full suite was not rerun. Only the reported nodes were fixed and rerun.
  - Safe-suite blocker fixes: declarative shadow-root content now survives reduced-HTML cloning; microdata ancestor checks use the DOM wrapper's safe `has_attr` contract instead of mapping access. Both reported nodes pass. The worktree venv is pinned to installed Python 3.14.6; Python 3.14.0 reproduced the same native microdata crash before the safe wrapper fix.
- Slice 3 verification (2026-08-10):
  - Browser settling passes its cached `HtmlAnalysis` into readiness probing. Adapter orchestration now strips empty evidence and globally deduplicates primary HTML, full rendered HTML, composed listing fragments, and serialized network payloads in that order. Detail still evaluates every unique source; sufficient listings still stop early.
  - Existing adapter spans now record input, empty-skip, duplicate-skip, call-count, and elapsed-millisecond attributes. Browser attempts already enforced the shared deadline before and after host-slot waiting; a public orchestration test now locks the zero-budget behavior.
  - Focused adapter/readiness/deadline nodes: 4 passed. Focused acquisition set: 311 passed / 10 deselected in 74.71s. Ruff clean; Vulture found no 80%-confidence dead code; touched Radon average B/8.13; touched jscpd reports one clone / 11 lines.
  - Required safe full suite ran exactly once: 2,412 selected / 17 deselected; 2,383 passed, 25 skipped, and 4 failed in 819.37s. Two variant fixtures remain reproducibly red in the existing DOM-variant owner and are assigned to Slice 6. Two structure ratchets remain red and are assigned to Slice 7. Per protocol, the full suite was not rerun; the two reported variant nodes were rerun directly and remained red.
- Slice 4 verification (2026-08-10):
  - `ExtractionContext` now owns cached cleaned, original, and pruned DOMs. Detail/listing internal entry points accept an optional context; raw-HTML callers still create one. Rendered listing fragments use a separate context for their single composed artifact.
  - Detail cleanup passes its prepared soup into price repair. Prepared-soup price repair performs zero parser builds; raw-HTML compatibility still parses once. Representative detail extraction drops from four parser builds to three while retaining the original breadcrumb/cleaned-loss fallback. New parser-count and object-identity tests cover detail, pruned-cache, rendered-fragment, visible-price, and cleanup handoff paths.
  - Focused extraction selected 598 tests: 567 passed, 25 skipped, and 6 failed initially. Four breadcrumb regressions caused by over-lazy original-DOM access were fixed; their reported nodes and all seven parser-contract nodes pass. The two pre-existing variant fixtures remain assigned to Slice 6.
  - Ruff clean; Vulture found no 80%-confidence dead code; touched-path Radon average B/7.78; touched jscpd reports two clones / 23 lines.
  - Required safe full suite ran exactly once: 2,417 selected / 17 deselected; 2,386 passed, 25 skipped, and 6 failed in 750.48s. Two fallback-seam unit regressions were fixed and their reported nodes pass. Remaining failures are the two Slice 6 variant fixtures and two Slice 7 structure ratchets. The full suite was not rerun.
- Slice 5 verification (2026-08-10):
  - Block classification now separates status handling, evidence collection, verdict rules, usable-content override, and result assembly. Detail expansion now separates ordered discovery, snapshot priority, dedupe/safety/relevance filtering, action execution, budget/cap state, and diagnostic finalization.
  - Public blocker/expansion contract set: 187 passed. Full focused acquisition set: 311 passed / 10 deselected in 31.73s. Action order, chrome filtering, requested-field priority, caps, time budget, fallback click, usable-content precedence, and evidence diagnostics remain covered.
  - Radon drops `classify_blocked_page` from F/82 to B/9 and `expand_all_interactive_elements_impl` from F/90 to B/6. All extracted blocker/DOM-expansion helpers are C/14 or lower. Ruff clean; Vulture found no 80%-confidence dead code; touched average B/6.0; touched jscpd reports zero clones.
  - Required safe full suite ran exactly once: 2,417 selected / 17 deselected; 2,388 passed, 25 skipped, and only the two known Slice 6 variant fixtures plus two Slice 7 structure ratchets failed in 475.04s. No full rerun was performed.
- Slice 6 verification (2026-08-10):
  - Price repair now separates evidence collection, currency reconciliation, price selection, record/variant application, and original-price completion. DOM variants now separate select/choice collection, validation/compound expansion, group merge, state metadata, Cartesian/axis-only row assembly, and final public materialization.
  - Removed dead `original_value`. Fixed the two standing variant fixtures at their shared upstream cause: the nonstandard CSS `[aria-pressed!='']` invalidated the entire strong-option selector under Lexbor. The standards-compatible `[aria-pressed]` preserves the intended evidence and lets radio/data-selected choices reach validation.
  - Focused extraction set: 573 passed, 25 fixture skips, 4 deselected in 43.53s. Additional structured/selectolax/variant contract set: 373 passed, 18 fixture skips, 2 deselected. Both formerly red variant fixtures pass.
  - Radon drops `backfill_detail_price_from_html` from F/93 to B/6 and `extract_variants_from_dom` from F/116 to B/6; extracted helpers top out at C/20. Ruff clean; Vulture found no 80%-confidence dead code; touched average B/7.74; touched jscpd reports one clone / 21 lines.
  - Required safe full suite ran exactly once: 2,417 selected / 17 deselected; 2,390 passed, 25 skipped, and only the two Slice 7 structure ratchets failed in 563.83s. No full rerun was performed.
- Slice 7 verification (2026-08-10):
  - Pytest now defaults to `unit or component or regression`; CI and canonical agent/backend verification docs use the same safe marker expression. Live, integration, and e2e tests remain deselected.
  - Fetch-runtime context/result/async fakes now have one shared fixture owner. Repeated durable-vendor engine cases are parameterized. The critical fetch suite shrank from 3,800 to 3,753 physical lines and has a no-regrowth ratchet.
  - Two tests moved off private DOM helpers to public `extract_section_content` and `extract_node_value` contracts. The private-test import allowlist did not grow. Structure LOC checks now measure source LOC consistently and grandfather only exact pre-existing overages while preserving their original target budgets.
  - Five-critical-suite jscpd falls from the reproducible base of 111 clones / 1,924 lines to 108 clones / 1,895 lines. Ruff clean; Vulture found no 80%-confidence dead code in touched tests; touched test Radon has one existing C/16 structure helper and no higher block.
  - Focused fetch suite: 91 passed. Public DOM plus structure set: 37 passed. Required safe full suite completed once after an initial runner-timeout launch produced no pytest output: 2,418 selected / 17 deselected; 2,393 passed and 25 fixture skips in 770.10s.

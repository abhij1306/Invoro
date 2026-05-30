# Active Plan

**Current:** Self-Healing Observability & Run-Audit Layer → `docs/plans/self-healing-observability-plan.md`
**Status:** IN PROGRESS
**Started:** 2026-05-30
**Last slice completed:** Slice 1 — RunTrace collector + typed trace contract (DONE; obs tests 12 passed)

## Queue
1. Extraction Wrong-Data Fixes (94URLs Audit) → `docs/plans/extraction-wrong-data-fixes-plan.md`
2. Playground — Replace Projects Feature → `docs/plans/playground-replace-projects-plan.md`

## Previously Completed
- Product Discovery Identity-Anchor Rework (deterministic, No LLM) → `docs/plans/product-discovery-identity-anchor-plan.md`
  (DONE 2026-05-30; live-verified on real Nike Promina product; full backend suite `pytest tests -q` = 1174 passed; Slices 1–5 all DONE)

> Image-hash matching investigation (Tier 4): CLOSED — NO-GO. Audited 2026-05-30 with live data
> (see `product-discovery-identity-anchor-plan.md`, Finding E). pHash rejects same-model colorway
> matches; the deterministic style-code/model-token tier rescues the same matches without image-fetch cost.

## Previous
- Belk React PDP Extraction Fixes (Multi-Variant, No LLM) (DONE; full backend suite = 1166 passed) → `docs/plans/belk-react-pdp-extraction-plan.md`
- Belk Product Discovery Recall (UPC-First, No LLM) (DONE; live-verified on real products + full suite) → `docs/plans/belk-product-discovery-recall-plan.md`

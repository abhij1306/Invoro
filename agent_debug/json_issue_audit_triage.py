from __future__ import annotations

from ._run_json_issue_audit_shared import *  # noqa: F403


ROOT_CAUSE_RULES: list[dict[str, Any]] = [
    {
        "id": "acquisition_blocked",
        "match_category": "blocked_page",
        "match_message": ".*",
        "label": "Page blocked — anti-bot or WAF rejection",
        "fix_layer": "acquisition",
        "is_actionable": True,
        "code_targets": [
            "app/services/fetch/fetch_context.py",
            "app/services/acquisition/browser_readiness.py",
            "app/services/acquisition/browser_page_flow.py",
        ],
        "debug_steps": [
            "1. Check acquisition logs for HTTP status (403/503) or challenge-shell classification",
            "2. Verify proxy rotation in app/services/acquisition/browser_proxy_config.py",
            "3. Check if host has HostProtectionMemory hard-block entry",
            "4. If title='Access denied' but HTML has product content, this is a false block — fix in browser_readiness.py",
        ],
        "do_not": "Do NOT add downstream compensation in extraction or publish. Fix at acquisition layer.",
    },
    {
        "id": "wrong_product_served",
        "match_category": "coherence",
        "match_message": "zero meaningful tokens",
        "label": "Wrong product extracted — URL redirected or stale",
        "fix_layer": "acquisition",
        "is_actionable": True,
        "code_targets": [
            "app/services/acquisition/browser_page_flow.py",
            "app/services/pipeline/extraction_loop.py",
            "app/services/fetch/fetch_context.py",
        ],
        "debug_steps": [
            "1. Compare input URL vs final navigated URL in acquisition diagnostics",
            "2. If final_url != input_url, acquisition followed a redirect — check if redirect detection exists",
            "3. If same URL but wrong content, site may serve different product based on geo/cookies",
            "4. Check if URL is stale in crawl queue (product removed, URL reused)",
        ],
        "do_not": "Do NOT fix in extraction. The wrong page was fetched — extraction correctly extracted what it saw.",
    },
    {
        "id": "possible_redirect",
        "match_category": "coherence",
        "match_message": "low token overlap|only one token",
        "label": "Possible soft redirect or locale mismatch",
        "fix_layer": "acquisition",
        "is_actionable": True,
        "code_targets": [
            "app/services/acquisition/browser_page_flow.py",
            "app/services/fetch/fetch_context.py",
        ],
        "debug_steps": [
            "1. Check if final URL differs from input URL (soft redirect)",
            "2. Check if site served locale-specific version (different product name in local language)",
            "3. If URL has /collections/ or /c/ prefix, may be category page served as detail — check detail_shell_filter",
        ],
        "do_not": "Do NOT assume all mismatches are bugs. Some sites legitimately have different URL slugs vs display titles.",
    },
    {
        "id": "extraction_price_missing",
        "match_category": "missing_fields",
        "match_message": "missing or empty `price`",
        "label": "Price not extracted",
        "fix_layer": "extraction",
        "is_actionable": True,
        "code_targets": [
            "app/services/structured_sources.py",
            "app/services/extract/detail_price_extractor.py",
            "app/services/config/extraction_rules.py",
            "app/services/dom/selector_engine.py",
        ],
        "debug_steps": [
            "1. Check if JSON-LD has offers.price — if yes, structured_sources.py should have caught it",
            "2. Check if price is behind login/add-to-cart interaction (not extractable without browser action)",
            "3. Check detail_price_extractor.py for visible PDP price backfill",
            "4. If blocked_page also flagged on same record, price is missing BECAUSE of block — fix acquisition first",
        ],
        "do_not": "Do NOT add price in publish/ or persistence. Price is extraction-owned per INVARIANTS Rule 3.",
    },
    {
        "id": "extraction_availability_missing",
        "match_category": "missing_fields",
        "match_message": "missing or empty `availability`",
        "label": "Availability not extracted",
        "fix_layer": "extraction",
        "is_actionable": True,
        "code_targets": [
            "app/services/structured_sources.py",
            "app/services/detail_extractor.py",
            "app/services/config/extraction_rules.py",
        ],
        "debug_steps": [
            "1. Check JSON-LD offers.availability field",
            "2. Check meta[property='product:availability'] or og:availability",
            "3. Check if site only shows availability after variant selection (common on fashion sites)",
            "4. If MANY hosts miss availability, likely a gap in structured_sources.py availability parsing",
        ],
        "do_not": "If site genuinely doesn't expose availability (e.g. luxury brands), this is expected — not a bug.",
    },
    {
        "id": "extraction_currency_missing",
        "match_category": "missing_fields",
        "match_message": "missing or empty `currency`",
        "label": "Currency not extracted",
        "fix_layer": "extraction",
        "is_actionable": True,
        "code_targets": [
            "app/services/structured_sources.py",
            "app/services/shared/field_coerce_price.py",
            "app/services/config/extraction_rules.py",
        ],
        "debug_steps": [
            "1. Check JSON-LD priceCurrency",
            "2. Check if price was extracted but currency wasn't — may need to infer from locale/TLD",
            "3. If price is also missing, currency gap is secondary — fix price extraction first",
        ],
        "do_not": "Do NOT hardcode currency assumptions. If price is missing too, this is a symptom not a root cause.",
    },
    {
        "id": "extraction_image_missing",
        "match_category": "missing_fields",
        "match_message": "missing or empty `image_url`",
        "label": "Primary image not extracted",
        "fix_layer": "extraction",
        "is_actionable": True,
        "code_targets": [
            "app/services/structured_sources.py",
            "app/services/dom/selector_engine.py",
            "app/services/extract/detail_image_dedupe.py",
        ],
        "debug_steps": [
            "1. Check og:image meta tag",
            "2. Check JSON-LD image field",
            "3. Check if site uses lazy-loading (data-src instead of src)",
            "4. If blocked_page also flagged, image is missing because page wasn't fetched — fix acquisition",
        ],
        "do_not": "Do NOT add image URL guessing or construction. Image must come from page source.",
    },
    {
        "id": "extraction_no_identifier",
        "match_category": "missing_fields",
        "match_message": "no core product identifier",
        "label": "No SKU/barcode/part_number found",
        "fix_layer": "skip",
        "is_actionable": False,
        "code_targets": [
            "app/services/structured_sources.py",
            "app/services/shared/field_coerce_text.py",
        ],
        "debug_steps": [
            "1. Many sites genuinely don't expose SKU/barcode publicly",
            "2. Only investigate if the site is known to have identifiers (e.g. Shopify stores always have SKU)",
            "3. Check JSON-LD sku, mpn, gtin fields",
        ],
        "do_not": "Do NOT treat this as a high-priority bug. Many legitimate sites don't expose identifiers.",
    },
    {
        "id": "variant_extraction_gap",
        "match_category": "incorrect_variants",
        "match_message": "variants missing but product looks multi-variant",
        "label": "Variants not extracted on multi-variant product",
        "fix_layer": "extraction",
        "is_actionable": True,
        "code_targets": [
            "app/services/js_state/state_normalizer.py",
            "app/services/js_state/variant_options.py",
            "app/services/extract/detail_dom_extractor.py",
            "app/services/extract/variant_dom_cues.py",
            "app/services/adapters/registry.py",
        ],
        "debug_steps": [
            "1. Check if site has adapter — adapter should handle variants (adapters/registry.py)",
            "2. Check JS state for variant data (window.__NEXT_DATA__, Shopify product.variants)",
            "3. Check if DOM has variant swatches/selectors that need interaction",
            "4. Per INVARIANTS Rule 3: extraction order is adapter -> structured -> JS state -> DOM",
            "5. If site is endclothing/ssense/grailed — check if adapter exists or needs creation",
        ],
        "do_not": "Do NOT add browser-side variant clicking that bypasses normal extraction provenance (INVARIANTS Rule 3).",
    },
    {
        "id": "variant_explosion",
        "match_category": "incorrect_variants",
        "match_message": "suspiciously high variant volume",
        "label": "Too many variants — cartesian explosion",
        "fix_layer": "extraction",
        "is_actionable": True,
        "code_targets": [
            "app/services/extract/shared_variant_logic.py",
            "app/services/extract/variant_structural_pruning.py",
            "app/services/js_state/variant_options.py",
        ],
        "debug_steps": [
            "1. Check if source provides color×size×width cartesian product",
            "2. Check variant_structural_pruning.py for existing dedup/collapse logic",
            "3. May need to group by color and only emit size variants per color",
            "4. Check if adapter should handle this (e.g. Birkenstock, Macy's)",
        ],
        "do_not": "Do NOT just cap variant count. Fix the grouping/dedup logic upstream.",
    },
    {
        "id": "variant_noise_pollution",
        "match_category": "incorrect_variants",
        "match_message": "UI/control noise",
        "label": "Variant fields contain UI noise",
        "fix_layer": "extraction",
        "is_actionable": True,
        "code_targets": [
            "app/services/extract/detail_dom_extractor.py",
            "app/services/extract/detail_dom_variant_options.py",
            "app/services/extract/variant_value_guards.py",
        ],
        "debug_steps": [
            "1. DOM variant extraction pulling button/nav text into variant values",
            "2. Check variant_value_guards.py for noise filtering",
            "3. Tighten variant container CSS selector in config/selectors.py",
        ],
        "do_not": "Do NOT filter noise in publish/persistence. Fix the DOM selector or add guard in extraction.",
    },
    {
        "id": "image_pollution_non_product",
        "match_category": "polluted_data",
        "match_message": "non-product assets.*category|banner|navigation",
        "label": "Additional images are site chrome not product photos",
        "fix_layer": "extraction",
        "is_actionable": True,
        "code_targets": [
            "app/services/dom/selector_engine.py",
            "app/services/extract/detail_image_dedupe.py",
            "app/services/config/extraction_rules.py",
        ],
        "debug_steps": [
            "1. Image selector is too broad — pulling page-level banners/category images",
            "2. Check if site has product gallery container that should scope the selector",
            "3. Add URL-path filter in detail_image_dedupe.py for known non-product patterns",
        ],
        "do_not": "Do NOT filter in publish. Fix image selector scope in extraction.",
    },
    {
        "id": "features_garbage",
        "match_category": "polluted_data",
        "match_message": "product ID leak",
        "label": "Features field has product IDs not features",
        "fix_layer": "extraction",
        "is_actionable": True,
        "code_targets": [
            "app/services/structured_sources.py",
            "app/services/js_state/state_normalizer.py",
            "app/services/config/js_state_field_specs.py",
        ],
        "debug_steps": [
            "1. Check which source tier produced the features value",
            "2. Likely JS state or structured source mapped wrong field to 'features'",
            "3. Check js_state_field_specs.py for features mapping",
        ],
        "do_not": "Do NOT strip numeric features globally — some products have numeric feature codes legitimately.",
    },
    {
        "id": "image_duplication",
        "match_category": "polluted_data",
        "match_message": "heavily duplicated",
        "label": "Additional images are resized duplicates of same base",
        "fix_layer": "extraction",
        "is_actionable": True,
        "code_targets": [
            "app/services/extract/detail_image_dedupe.py",
            "app/services/shared/field_coerce_url.py",
        ],
        "debug_steps": [
            "1. Same image repeated with ?width=X or CDN resize suffixes",
            "2. detail_image_dedupe.py should normalize before dedup — check if it strips query params",
            "3. May need to add CDN-specific normalization (Shopify, Amplience, etc.)",
        ],
        "do_not": "Acceptable if count is low (< 3 dupes). Only fix if ratio is high.",
    },
    {
        "id": "tag_pollution_internal",
        "match_category": "polluted_data",
        "match_message": "internal metadata tokens",
        "label": "Tags contain platform-internal metadata",
        "fix_layer": "extraction",
        "is_actionable": True,
        "code_targets": [
            "app/services/structured_sources.py",
            "app/services/adapters/",
            "app/services/config/extraction_rules.py",
        ],
        "debug_steps": [
            "1. Shopify/platform internal tags leaking (clearance_, dropship_, etc.)",
            "2. Check if adapter should filter these",
            "3. Add prefix-based exclusion in extraction or config",
        ],
        "do_not": "Do NOT filter in publish. Tags are extraction-owned.",
    },
    {
        "id": "text_pollution_ui",
        "match_category": "polluted_data",
        "match_message": "UI/control noise",
        "label": "Text fields have UI/nav noise mixed in",
        "fix_layer": "extraction",
        "is_actionable": True,
        "code_targets": [
            "app/services/extract/detail_text_sanitizer.py",
            "app/services/dom/selector_engine.py",
            "app/services/config/selectors.py",
        ],
        "debug_steps": [
            "1. DOM extraction pulling carousel/button/nav text into description/features",
            "2. Check detail_text_sanitizer.py for existing noise filters",
            "3. Tighten content container selector",
        ],
        "do_not": "Do NOT add text cleanup in publish or persistence.",
    },
    {
        "id": "brand_normalization",
        "match_category": "incorrect_data",
        "match_message": "brand appears unnormalized",
        "label": "Brand name lowercase (cosmetic)",
        "fix_layer": "skip",
        "is_actionable": False,
        "code_targets": ["app/services/shared/field_coerce_text.py"],
        "debug_steps": [
            "1. Brand like 'adidas' is intentionally lowercase by the brand itself",
            "2. Only fix if brand is clearly wrong (e.g. 'NIKE INC' instead of 'Nike')",
        ],
        "do_not": "Do NOT force title-case on brands. Many brands use intentional lowercase (adidas, lululemon).",
    },
    {
        "id": "size_default_value",
        "match_category": "incorrect_data",
        "match_message": "size looks like selector index",
        "label": "Size field has pre-selected variant value (likely correct)",
        "fix_layer": "skip",
        "is_actionable": False,
        "code_targets": ["app/services/js_state/variant_options.py"],
        "debug_steps": [
            "1. Size '8' or '7.5' is the pre-selected/default variant size on the page",
            "2. This is EXPECTED behavior — the page loads with a size pre-selected",
            "3. Only a bug if size is clearly an index (0, 1, 2) not a real size value",
        ],
        "do_not": "Do NOT fix this. Pre-selected size is correct extraction behavior.",
    },
    {
        "id": "redundant_description",
        "match_category": "logical_errors",
        "match_message": "description and product_details look redundant",
        "label": "Description duplicated in product_details (cosmetic)",
        "fix_layer": "skip",
        "is_actionable": False,
        "code_targets": [
            "app/services/detail_extractor.py",
            "app/services/config/field_mappings.py",
        ],
        "debug_steps": [
            "1. Same source text mapped to both fields",
            "2. Low priority — doesn't affect data quality for consumers",
            "3. Only fix if it causes export bloat",
        ],
        "do_not": "Do NOT prioritize this over missing-field or pollution bugs.",
    },
    {
        "id": "price_logic_error",
        "match_category": "logical_errors",
        "match_message": "price greater than original_price",
        "label": "Price > original_price (field swap or logic error)",
        "fix_layer": "extraction",
        "is_actionable": True,
        "code_targets": [
            "app/services/extract/detail_price_extractor.py",
            "app/services/shared/field_coerce_price.py",
        ],
        "debug_steps": [
            "1. Check which DOM element maps to price vs original_price",
            "2. May be swapped in selector config",
            "3. Check if sale_price and price are confused",
        ],
        "do_not": "Do NOT swap values in publish. Fix the selector/mapping in extraction.",
    },
]

_ROOT_CAUSE_COMPILED = [
    (
        rule["match_category"],
        re.compile(rule["match_message"], re.I),
        rule["id"],
    )
    for rule in ROOT_CAUSE_RULES
]

_ROOT_CAUSE_MAP: dict[str, dict[str, Any]] = {rule["id"]: rule for rule in ROOT_CAUSE_RULES}

def _classify_root_cause(issue: dict[str, Any]) -> str:
    """Return root_cause_id for an issue, or 'uncategorized'."""
    cat = issue.get("category", "")
    msg = issue.get("message", "")
    for rule_cat, rule_rx, rc_id in _ROOT_CAUSE_COMPILED:
        if cat == rule_cat and rule_rx.search(msg):
            return rc_id
    return "uncategorized"

def _build_root_cause_groups(audited: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group issues by root cause — compact format for agent consumption."""
    groups: dict[str, dict[str, Any]] = {}

    for record in audited:
        if not record["issues"]:
            continue
        for issue in record["issues"]:
            rc_id = _classify_root_cause(issue)
            if rc_id not in groups:
                rule = _ROOT_CAUSE_MAP.get(rc_id, {})
                groups[rc_id] = {
                    "id": rc_id,
                    "label": rule.get("label", rc_id),
                    "fix_layer": rule.get("fix_layer", "unknown"),
                    "is_actionable": rule.get("is_actionable", True),
                    "severity": issue["severity"],
                    "hosts": [],
                    "host_count": 0,
                    "sample_urls": [],
                    "sample_evidence": [],
                    "count": 0,
                }
            group = groups[rc_id]
            group["count"] += 1
            sev_rank = {"high": 3, "medium": 2, "low": 1}
            if sev_rank.get(issue["severity"], 0) > sev_rank.get(group["severity"], 0):
                group["severity"] = issue["severity"]
            host = record["host"]
            if host and host not in group["hosts"] and len(group["hosts"]) < 5:
                group["hosts"].append(host)
            if host:
                group["host_count"] = len(set(group.get("_all_hosts", set()) | {host}))
                group.setdefault("_all_hosts", set()).add(host)
            url = record["url"]
            if url and len(group["sample_urls"]) < 3:
                if url not in group["sample_urls"]:
                    group["sample_urls"].append(url)
            if issue.get("evidence") and len(group["sample_evidence"]) < 2:
                group["sample_evidence"].append(issue["evidence"])

    # sort: actionable first, then severity desc, then count desc
    sev_order = {"high": 0, "medium": 1, "low": 2}
    sorted_groups = sorted(
        groups.values(),
        key=lambda g: (0 if g["is_actionable"] else 1, sev_order.get(g["severity"], 3), -g["count"]),
    )
    # strip internal tracking fields
    for g in sorted_groups:
        g.pop("_all_hosts", None)
    return sorted_groups

def _build_host_summary(audited: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Per-host rollup — ONLY hosts with issues. Clean hosts omitted."""
    host_data: dict[str, dict[str, Any]] = {}
    for record in audited:
        host = record["host"]
        if not host or record["issue_count"] == 0:
            continue
        if host not in host_data:
            host_data[host] = {
                "host": host,
                "records": 0,
                "issues": 0,
                "max_severity": "none",
                "root_causes": set(),
            }
        hd = host_data[host]
        hd["records"] += 1
        hd["issues"] += record["issue_count"]
        sev_rank = {"high": 3, "medium": 2, "low": 1, "none": 0}
        if sev_rank.get(record["max_severity"], 0) > sev_rank.get(hd["max_severity"], 0):
            hd["max_severity"] = record["max_severity"]
        for issue in record["issues"]:
            hd["root_causes"].add(_classify_root_cause(issue))

    result = []
    for hd in host_data.values():
        hd["root_causes"] = sorted(hd.pop("root_causes"))
        result.append(hd)

    result.sort(key=lambda h: (-h["issues"], h["host"]))
    return result[:15]  # top 15 hosts only — agent doesn't need the long tail

def _build_triage_section(root_cause_groups: list[dict[str, Any]], audited: list[dict[str, Any]]) -> dict[str, Any]:
    """Top-level triage: what to fix, what to skip, what's secondary."""
    actionable = [g for g in root_cause_groups if g["is_actionable"]]
    skippable = [g for g in root_cause_groups if not g["is_actionable"]]

    # Detect correlated issues (blocked/redirect hosts cause cascading missing fields)
    blocked_hosts = set()
    for g in root_cause_groups:
        if g["id"] in ("acquisition_blocked", "wrong_product_served"):
            blocked_hosts.update(g["hosts"])

    secondary_count = 0
    for record in audited:
        if record["host"] in blocked_hosts:
            secondary_count += sum(1 for i in record["issues"] if i["category"] == "missing_fields")

    return {
        "action_required": len(actionable),
        "skip_count": len(skippable),
        "fix_order": [
            {
                "priority": idx + 1,
                "id": g["id"],
                "fix_layer": g["fix_layer"],
                "count": g["count"],
                "file": _ROOT_CAUSE_MAP.get(g["id"], {}).get("code_targets", [None])[0],
            }
            for idx, g in enumerate(actionable[:6])
        ],
        "secondary_on_blocked_hosts": secondary_count,
        "note": (
            f"{secondary_count} missing-field issues are on blocked/redirected hosts. "
            "Fix acquisition_blocked/wrong_product_served FIRST — those resolve automatically."
            if secondary_count > 3 else ""
        ),
        "do_not_fix": [g["id"] for g in skippable],
    }

__all__ = tuple(
    name for name in globals() if not name.startswith("__")
)

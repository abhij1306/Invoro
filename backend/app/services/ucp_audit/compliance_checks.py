from __future__ import annotations

import re

from app.services.config import ucp_audit as config
from app.services.ucp_audit.types import (
    PolicyReadabilityReport,
    UCPFinding,
    VariantFidelityReport,
)


# D-UCP5 reads from existing crawl record variant data.
# If fidelity scores are systematically low, the fix is upstream
# in the commerce extractor, not in this audit module. (Rule 4)
build_variant_fidelity_report = lambda records: _variant_report(list(records))

_variants = lambda row: list(row.get(config.PUBLIC_VARIANTS_FIELD) or [])
_products = lambda rows: [row for row in rows if len(_variants(row)) > 1]
_variant_value = lambda row, key: row.get(key) if isinstance(row, dict) else None
_price_key = lambda row: (
    _variant_value(row, config.PUBLIC_VARIANT_PRICE_FIELD),
    _variant_value(row, config.PUBLIC_VARIANT_CURRENCY_FIELD),
)
_missing = lambda row, key: _variant_value(row, key) in (None, "", [], {})
_collapsed = lambda rows: sum(
    1
    for row in rows
    if len({_price_key(item) for item in _variants(row)}) == 1
)
_missing_count = lambda rows, key: sum(
    1 for row in rows for item in _variants(row) if _missing(item, key)
)
_finding = lambda code, count: UCPFinding(
    code=code,
    dimension_id=config.D_UCP5_ID,
    severity=config.UCP_FINDING_WARNING,
    affected_count=count,
)
_variant_findings = lambda collapsed, sku, availability: [
    item
    for item in (
        _finding(config.FINDING_VARIANT_OFFERS_COLLAPSED, collapsed) if collapsed else None,
        _finding(config.FINDING_VARIANT_SKU_MISSING, sku) if sku else None,
        _finding(config.FINDING_VARIANT_AVAILABILITY_MISSING, availability)
        if availability
        else None,
    )
    if item is not None
]
_variant_score = lambda total, collapsed, sku, availability: (
    100
    if total <= 0
    else max(0, int(100 - (((collapsed + sku + availability) / (total * 3)) * 100)))
)
_variant_report = lambda rows: _variant_report_from_products(_products(rows))
_variant_report_from_products = lambda products: VariantFidelityReport(
    products_with_variants_sampled=len(products),
    collapsed_offers_count=(collapsed := _collapsed(products)),
    missing_sku_count=(sku := _missing_count(products, config.PUBLIC_VARIANT_SKU_FIELD)),
    missing_availability_count=(
        availability := _missing_count(
            products, config.PUBLIC_VARIANT_AVAILABILITY_FIELD
        )
    ),
    fidelity_score=_variant_score(len(products), collapsed, sku, availability),
    findings=_variant_findings(collapsed, sku, availability),
)

build_policy_readability_report = lambda *, structured_shipping_found, period_machine_readable=False, currency_value="", policy_page_http_accessible=False: PolicyReadabilityReport(
    bool(structured_shipping_found),
    bool(period_machine_readable),
    bool(re.fullmatch(config.ISO4217_PATTERN, str(currency_value or ""))),
    bool(policy_page_http_accessible),
    config.POLICY_SCORE_PER_SIGNAL
    * sum(
        (
            bool(structured_shipping_found),
            bool(period_machine_readable),
            bool(re.fullmatch(config.ISO4217_PATTERN, str(currency_value or ""))),
            bool(policy_page_http_accessible),
        )
    ),
    [
        item
        for item in (
            UCPFinding(
                config.FINDING_POLICY_SHIPPING_MISSING,
                config.D_UCP6_ID,
                config.UCP_FINDING_WARNING,
            )
            if not structured_shipping_found
            else None,
            UCPFinding(
                config.FINDING_POLICY_RETURN_PERIOD_MISSING,
                config.D_UCP6_ID,
                config.UCP_FINDING_WARNING,
            )
            if not period_machine_readable
            else None,
            UCPFinding(
                config.FINDING_POLICY_CURRENCY_INVALID,
                config.D_UCP6_ID,
                config.UCP_FINDING_WARNING,
            )
            if not re.fullmatch(config.ISO4217_PATTERN, str(currency_value or ""))
            else None,
            UCPFinding(
                config.FINDING_POLICY_PAGE_INACCESSIBLE,
                config.D_UCP6_ID,
                config.UCP_FINDING_WARNING,
            )
            if not policy_page_http_accessible
            else None,
        )
        if item is not None
    ],
)

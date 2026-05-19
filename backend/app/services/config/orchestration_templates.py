from __future__ import annotations

COMPETITIVE_PRICING_TEMPLATE_ID = "competitive_pricing_snapshot"

ORCHESTRATION_TEMPLATE_IDS = {COMPETITIVE_PRICING_TEMPLATE_ID}
ORCHESTRATION_DEFAULT_TRACKED_FIELDS = ["price", "was_price", "availability", "title"]
ORCHESTRATION_LISTING_REQUEST_FIELDS = ["url", "title", "brand"]
ORCHESTRATION_LISTING_LINK_FIELDS = ["url", "product_url", "detail_url", "canonical_url"]
ORCHESTRATION_PRICE_VIEW_TITLE_FIELDS = ["title", "name"]
ORCHESTRATION_PRICE_VIEW_WAS_PRICE_FIELDS = ["was_price", "original_price"]
ORCHESTRATION_PRICE_VIEW_FIELDS = {
    "brand": "brand",
    "price": "price",
    "currency": "currency",
    "availability": "availability",
}

ORCHESTRATION_TEMPLATES: dict[str, dict[str, object]] = {
    COMPETITIVE_PRICING_TEMPLATE_ID: {
        "id": COMPETITIVE_PRICING_TEMPLATE_ID,
        "display_name": "Competitive Pricing Snapshot",
        "description": "Sequence ecommerce listing and detail crawls into a price comparison view.",
        "version": "1.0",
        "intent_inputs": [
            {
                "key": "listing_url",
                "type": "url",
                "label": "Listing URL",
                "required": True,
            },
            {
                "key": "category",
                "type": "category_selector",
                "label": "What product category?",
                "required": True,
            },
            {
                "key": "fields",
                "type": "field_picker",
                "label": "Which fields to track?",
                "defaults": ORCHESTRATION_DEFAULT_TRACKED_FIELDS,
            },
        ],
        "pipeline_defaults": {
            "listing_surface": "ecommerce_listing",
            "detail_surface": "ecommerce_detail",
            "fetch_mode": "auto",
            "llm_enabled": False,
            "locality": "auto",
            "max_pages_listing": 5,
            "max_items_detail": 200,
        },
        "advanced_overrides": [
            "fetch_mode",
            "llm_enabled",
            "proxy_profile",
            "max_pages_listing",
            "max_items_detail",
            "custom_fields",
        ],
        "steps": [
            {
                "step_id": "listing_run",
                "type": "crawl_run",
                "inputs": {
                    "surface": "ecommerce_listing",
                    "fields": ORCHESTRATION_LISTING_REQUEST_FIELDS,
                },
            },
            {
                "step_id": "detail_run",
                "type": "crawl_run",
                "depends_on": "listing_run",
                "inputs": {
                    "surface": "ecommerce_detail",
                },
            },
            {
                "step_id": "comparison_view",
                "type": "view_render",
                "depends_on": "detail_run",
                "view_type": "price_comparison_table",
            },
        ],
        "continuations": [
            {
                "label": "Save as recurring monitor",
                "action": "promote_to_monitor",
                "template": "recurring_category_watch",
            },
            {
                "label": "Export results",
                "action": "open_export",
            },
        ],
    }
}


def get_orchestration_template(template_id: str) -> dict[str, object]:
    template = ORCHESTRATION_TEMPLATES.get(template_id)
    if template is None:
        raise KeyError(template_id)
    return template


def list_orchestration_templates() -> list[dict[str, object]]:
    return list(ORCHESTRATION_TEMPLATES.values())

from __future__ import annotations

MAX_RETENTION_DAYS = 90
MIN_SCHEDULE_INTERVAL_HOURS = 1
MIN_ALERT_POLL_INTERVAL_SECONDS = 60
MAX_URLS_PER_MONITOR = 500
MAX_ALERTS_PER_USER = 50
MAX_ALERT_TARGET_FIELDS = 5
MAX_ALERT_TARGET_RULES = 10
MAX_CONCURRENT_MONITOR_DISPATCHES_PER_TICK = 20
SCHEDULER_POLL_INTERVAL_SECONDS = 300
SCHEDULER_DRIVER_DEV = "dev"
SCHEDULER_DRIVER_CELERY = "celery"
HEAD_CHECK_TIMEOUT_SECONDS = 5
MAX_HASH_BYTES = 5_000_000
WEBHOOK_DELIVERY_TIMEOUT_SECONDS = 10
WEBHOOK_MAX_RETRY_ATTEMPTS = 3
WEBHOOK_RETRY_BACKOFF_BASE_SECONDS = 0.25
WEBHOOK_RETRY_BACKOFF_MAX_SECONDS = 2.0
WEBHOOK_RETRY_JITTER_SECONDS = 0.1
WEBHOOK_PAYLOAD_MAX_BYTES = 10_000
ALERT_CONSECUTIVE_FAILURE_LIMIT = 5

MONITOR_STATUS_ACTIVE = "active"
MONITOR_STATUS_PAUSED = "paused"
MONITOR_STATUS_ARCHIVED = "archived"
MONITOR_STATUS_TRIGGERED = "triggered"
MONITOR_STATUS_ERROR = "error"

MONITOR_PRIORITY_ON_DEMAND = "on_demand"
MONITOR_PRIORITY_PRIORITY = "priority"
MONITOR_PRIORITY_BACKGROUND = "background"

NOTIFICATION_STATUS_PENDING = "pending"
NOTIFICATION_STATUS_SENT = "sent"
NOTIFICATION_STATUS_SKIPPED = "skipped"
MONITOR_NOTIFICATION_MESSAGE_TEMPLATE = "{monitor_name}: {event_count} tracked price change(s) detected"
WEBHOOK_STATUS_PENDING = "pending"
WEBHOOK_STATUS_SENT = "sent"
WEBHOOK_STATUS_FAILED = "failed"
WEBHOOK_STATUS_SKIPPED = "skipped"

MONITOR_EVENT_FIELD_CHANGED = "field_changed"
MONITOR_EVENT_RECORD_NEW = "record_new"
MONITOR_EVENT_RECORD_REMOVED = "record_removed"

MONITOR_RUN_TYPE_CRAWL = "crawl"
MONITOR_RUN_TYPE_BATCH = "batch"
MONITOR_ID_SETTING_KEY = "monitor_id"
MONITOR_SUPPRESS_WEBHOOKS_SETTING_KEY = "monitor_suppress_webhooks"
SKIP_HEAD_CHECK_KEY = "skip_head_check"
PRODUCT_INTELLIGENCE_MONITOR_DEFAULT_SURFACE = "ecommerce_detail"
PRODUCT_INTELLIGENCE_MONITOR_DEFAULT_TRACKED_FIELDS = ["price", "availability"]
PRODUCT_INTELLIGENCE_MONITOR_DEFAULT_SCHEDULE_HOURS = 24
ALERT_DEFAULT_TARGET_FIELDS = ["price", "availability"]
ALERT_SURFACE = "ecommerce_detail"
ALERT_RULES_SETTING_KEY = "alert_rules"
ALERT_RULE_PATH_KEY = "path"
ALERT_RULE_LABEL_KEY = "label"
ALERT_RULE_OPERATOR_KEY = "operator"
ALERT_RULE_VALUE_KEY = "value"
ALERT_RULE_VARIANT_MATCH_KEY = "variant_match"
ALERT_RULE_OPERATOR_CHANGED = "changed"
ALERT_RULE_OPERATOR_EQUALS = "equals"
ALERT_RULE_OPERATOR_NOT_EQUALS = "not_equals"
ALERT_RULE_OPERATOR_LESS_THAN = "less_than"
ALERT_RULE_OPERATOR_GREATER_THAN = "greater_than"
ALERT_RULE_OPERATOR_LESS_THAN_OR_EQUALS = "less_than_or_equals"
ALERT_RULE_OPERATOR_GREATER_THAN_OR_EQUALS = "greater_than_or_equals"
ALERT_RULE_OPERATOR_EXISTS = "exists"
ALERT_RULE_OPERATOR_MISSING = "missing"
ALERT_RULE_OPERATORS = frozenset({
    ALERT_RULE_OPERATOR_CHANGED,
    ALERT_RULE_OPERATOR_EQUALS,
    ALERT_RULE_OPERATOR_NOT_EQUALS,
    ALERT_RULE_OPERATOR_LESS_THAN,
    ALERT_RULE_OPERATOR_GREATER_THAN,
    ALERT_RULE_OPERATOR_LESS_THAN_OR_EQUALS,
    ALERT_RULE_OPERATOR_GREATER_THAN_OR_EQUALS,
    ALERT_RULE_OPERATOR_EXISTS,
    ALERT_RULE_OPERATOR_MISSING,
})
ALERT_VARIANT_COLLECTION_FIELD = "variants"
ALERT_VARIANT_WILDCARD_PATH_PREFIX = "variants[*]."
ALERT_VARIANT_IDENTITY_FIELDS = ("sku", "url", "size", "color")
ALERT_ALLOWED_FIELDS = frozenset({
    "price",
    "availability",
    "sku",
    "title",
    "brand",
    "color",
    "size",
    "currency",
    "image_url",
    ALERT_VARIANT_COLLECTION_FIELD,
})
ALERT_CONDITION_FIELDS = frozenset({"price", "availability"})
ALERT_CONDITION_OPERATORS = frozenset({"<", ">", "<=", ">=", "==", "!="})
MCP_API_KEY_ENV = "CRAWLERAI_API_KEY"
MCP_API_BASE_URL_ENV = "CRAWLERAI_API_BASE_URL"
MCP_DEFAULT_API_BASE_URL = "http://127.0.0.1:8000/api/v1"

# Surfaces where HEAD pre-check should be skipped by default (CDN ETags unreliable)
ECOMMERCE_SURFACES = frozenset({
    "ecommerce_detail",
    "ecommerce_listing",
})

# Maps raw extraction field names to standard monitored field names
TRACKED_FIELD_ALIASES: dict[str, str] = {
    "sale_price": "price",
    "current_price": "price",
    "final_price": "price",
    "upc": "gtin",
    "ean": "gtin",
    "isbn": "gtin",
    "in_stock": "availability",
    "stock_status": "availability",
    "product_title": "title",
    "name": "title",
    "manufacturer": "brand",
    "primary_image": "image",
    "thumbnail": "image",
}

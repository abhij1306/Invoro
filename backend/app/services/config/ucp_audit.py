from __future__ import annotations

UCP_MANIFEST_PATH = "/.well-known/ucp"
UCP_DEFAULT_URL_SCHEME = "https"
UCP_REQUIRED_CAPABILITIES = (
    "product_discovery",
    "checkout",
    "orders",
)

UCP_HTTP_ONLY_MODE = "http_only"
UCP_BROWSER_ONLY_MODE = "browser_only"
UCP_AUDIT_SURFACE = "ecommerce_detail"
UCP_DISCOVERY_TIMEOUT_SECONDS = 10.0
UCP_AGENT_UA_OVERRIDE: str | None = None

JSON_LD_TYPE_KEY = "@type"
JSON_LD_PRODUCT_TYPES = frozenset({"Product", "ProductGroup"})
JSON_LD_NAME_FIELD = "name"
JSON_LD_VALUE_FIELD = "value"
JSON_LD_OFFERS_FIELD = "offers"
JSON_LD_ADDITIONAL_PROPERTY_FIELD = "additionalProperty"
JSON_LD_CATEGORY_FIELDS = ("product_type", "category")
JSON_LD_REQUIRED_FIELD_PATHS = (
    ("name",),
    ("offers", "price"),
    ("offers", "availability"),
    ("offers", "priceCurrency"),
)
JSON_LD_RECOMMENDED_FIELD_PATHS = (
    ("sku",),
    ("brand",),
    ("gtin13",),
    ("description",),
    ("image",),
)

UCP_CRITICAL_ATTRIBUTES = (
    "color",
    "size",
    "material",
    "brand",
    "gtin",
)
UCP_METAFIELD_COVERAGE_THRESHOLD = 0.7
UCP_CATEGORY_DEPTH_MIN = 3
UCP_CATEGORY_DEPTH_SEPARATORS = (">", "/")

PUBLIC_VARIANTS_FIELD = "variants"
PUBLIC_VARIANT_SKU_FIELD = "sku"
PUBLIC_VARIANT_PRICE_FIELD = "price"
PUBLIC_VARIANT_CURRENCY_FIELD = "currency"
PUBLIC_VARIANT_AVAILABILITY_FIELD = "availability"
POLICY_JSONLD_SHIPPING_FIELD = "shippingDetails"
POLICY_JSONLD_CURRENCY_FIELD = "priceCurrency"
POLICY_SCORE_PER_SIGNAL = 25
ISO4217_PATTERN = r"^[A-Z]{3}$"

FINDING_VARIANT_OFFERS_COLLAPSED = "variant_offers_collapsed"
FINDING_VARIANT_SKU_MISSING = "variant_sku_missing"
FINDING_VARIANT_AVAILABILITY_MISSING = "variant_availability_missing"
FINDING_POLICY_SHIPPING_MISSING = "policy_shipping_missing"
FINDING_POLICY_RETURN_PERIOD_MISSING = "policy_return_period_missing"
FINDING_POLICY_CURRENCY_INVALID = "policy_currency_invalid"
FINDING_POLICY_PAGE_INACCESSIBLE = "policy_page_inaccessible"
FINDING_AGENT_DELTA_LOW_FIDELITY = "agent_delta_low_fidelity"

D_UCP1_ID = "D-UCP1"
D_UCP2_ID = "D-UCP2"
D_UCP3_ID = "D-UCP3"
D_UCP4_ID = "D-UCP4"
D_UCP5_ID = "D-UCP5"
D_UCP6_ID = "D-UCP6"
D_UCP7_ID = "D-UCP7"
UCP_STATUS_PASS = "pass"
UCP_STATUS_WARNING = "warning"
UCP_STATUS_FAIL = "fail"
UCP_FINDING_BLOCKING = "blocking"
UCP_FINDING_WARNING = "warning"
UCP_FINDING_INFO = "info"
DIMENSION_WEIGHTS = {
    D_UCP1_ID: 0.2,
    D_UCP2_ID: 0.15,
    D_UCP3_ID: 0.15,
    D_UCP4_ID: 0.1,
    D_UCP5_ID: 0.15,
    D_UCP6_ID: 0.1,
    D_UCP7_ID: 0.15,
}
D_UCP1_GATE_MAX_SCORE = 30
AGENT_DELTA_BLOCKING_THRESHOLD = 0.3

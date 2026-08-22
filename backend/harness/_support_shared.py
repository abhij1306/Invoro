from __future__ import annotations


import logging


import re

from collections.abc import Iterable

from pathlib import Path


from app.services.publish import VERDICT_PARTIAL, VERDICT_SUCCESS


from app.services.config.public_record_policy import PUBLIC_RECORD_LEGACY_VARIANT_FIELDS

from app.services.config.variant_policy import PUBLIC_VARIANT_AXIS_FIELDS


logger = logging.getLogger(__name__)

HARNESS_MODE_ACQUISITION_ONLY = "acquisition_only"

HARNESS_MODE_FULL_PIPELINE = "full_pipeline"

DEFAULT_SITE_SET_PATH = (
    Path(__file__).resolve().parent / "test_site_sets" / "commerce_browser_heavy.json"
)

DEFAULT_HARNESS_EMAIL = "admin@admin.com"

DEFAULT_HARNESS_PASSWORD = "AdminPassword123!"  # nosec B105 # skipcq: SCT-A000 - local harness bootstrap placeholder only.

_VARIANT_AXIS_FIELDS = tuple(
    dict.fromkeys(
        str(token).strip().lower()
        for token in tuple(PUBLIC_VARIANT_AXIS_FIELDS or ())
        if str(token).strip()
    )
)


def _field_name_tuple(value: object, config_name: str) -> tuple[str, ...]:
    if isinstance(value, str) or not isinstance(value, Iterable):
        raise TypeError(f"{config_name} must be an iterable of field names")
    fields = tuple(str(token).strip() for token in value if str(token).strip())
    if not fields:
        raise TypeError(f"{config_name} must contain at least one field name")
    return fields


_PUBLIC_RECORD_LEGACY_VARIANT_FIELDS = _field_name_tuple(
    PUBLIC_RECORD_LEGACY_VARIANT_FIELDS,
    "PUBLIC_RECORD_LEGACY_VARIANT_FIELDS",
)

if not _VARIANT_AXIS_FIELDS:
    logger.warning(
        "PUBLIC_VARIANT_AXIS_FIELDS is empty; using default axis fields for "
        "_quality_variant_artifacts_ok and _variant_row_has_axis"
    )
    _VARIANT_AXIS_FIELDS = ("color", "size")

_HIGH_DENOMINATION_PRICE_CURRENCIES = {"INR", "JPY", "KRW", "VND", "IDR", "HUF", "CLP"}

_MIN_SANE_PRICE = 0.01

_DETAIL_HINTS = (
    "/products/",
    "/product/",
    "/p/",
    "/dp/",
    "/job/",
    "/viewjob",
    "showjob=",
    "/release/",
)

_PRODUCT_LIKE_TERMINAL_SLUG_RE = re.compile(
    r"(?=.{16,}$)(?=.*[a-z])(?:[a-z0-9]+-){2,}[a-z0-9]+$",
    re.I,
)

_LISTING_HINTS = (
    "/collections",
    "/shop/",
    "/category/",
    "/careers",
    "/jobs",
    "job-search",
    "career-page",
    "jobboard",
    "recruitment",
    "currentopenings",
)

_JOB_LISTING_HINTS = (
    "/jobs",
    "/careers",
    "/search/results",
    "/search?",
    "job-search",
    "career-page",
    "jobboard",
    "recruitment",
    "currentopenings",
    "searchrelation=",
    "mode=location",
    "sortby=",
    "page=",
)

_SUCCESS_VERDICTS = {VERDICT_SUCCESS.lower(), VERDICT_PARTIAL.lower()}

_PLACEHOLDER_TITLES = {
    "404",
    "all products",
    "edit",
    "page not found",
    "sylius demo",
}

_DETAIL_SLUG_WITH_ID_RE = re.compile(r".+_\d+$")

_DETAIL_FILE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*\.html?$")

_NON_DETAIL_FILE_RE = re.compile(r"^(?:index|page[-_]?\d+)\.html?$")

_IDENTITY_SEGMENT_SKIP = {
    "c",
    "catalog",
    "collections",
    "dp",
    "item",
    "items",
    "p",
    "page",
    "product",
    "products",
    "release",
    "releases",
    "shop",
    "store",
    "w",
}

_IDENTITY_TOKEN_SKIP = {
    "and",
    "for",
    "from",
    "the",
    "with",
}

_GENERIC_DETAIL_SECTION_TITLES = {
    "customers also bought",
    "frequently bought together",
    "recommended products",
    "related products",
    "you may also like",
}

_ALLOWED_GENDERS = {"Men", "Women", "Unisex", "Kids", "Boys", "Girls"}

_ALLOWED_GENDERS_LOWER = frozenset(g.lower() for g in _ALLOWED_GENDERS)

_BARCODE_LENGTHS = {8, 12, 13, 14}

_INTERNAL_IDENTITY_TOKENS = {
    "plp",
    "pdp",
    "specification",
    "specifications",
    "description",
    "details",
    "overview",
    "reviews",
}

__all__ = ['DEFAULT_HARNESS_EMAIL', 'DEFAULT_HARNESS_PASSWORD', 'DEFAULT_SITE_SET_PATH', 'HARNESS_MODE_ACQUISITION_ONLY', 'HARNESS_MODE_FULL_PIPELINE', '_ALLOWED_GENDERS', '_ALLOWED_GENDERS_LOWER', '_BARCODE_LENGTHS', '_DETAIL_FILE_RE', '_DETAIL_HINTS', '_DETAIL_SLUG_WITH_ID_RE', '_GENERIC_DETAIL_SECTION_TITLES', '_HIGH_DENOMINATION_PRICE_CURRENCIES', '_IDENTITY_SEGMENT_SKIP', '_IDENTITY_TOKEN_SKIP', '_INTERNAL_IDENTITY_TOKENS', '_JOB_LISTING_HINTS', '_LISTING_HINTS', '_MIN_SANE_PRICE', '_NON_DETAIL_FILE_RE', '_PLACEHOLDER_TITLES', '_PRODUCT_LIKE_TERMINAL_SLUG_RE', '_PUBLIC_RECORD_LEGACY_VARIANT_FIELDS', '_SUCCESS_VERDICTS', '_VARIANT_AXIS_FIELDS', '_field_name_tuple']  # fmt: skip

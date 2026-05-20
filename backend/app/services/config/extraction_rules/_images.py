from __future__ import annotations
# ruff: noqa: F401,F403,F405

from ._common import *

CDN_IMAGE_QUERY_PARAMS = _string_frozenset(
    _STATIC_EXPORTS.get("CDN_IMAGE_QUERY_PARAMS", ())
) | frozenset(
    {
        "fit",
        "fmt",
        "h",
        "height",
        "hei",
        "imwidth",
        "odnbg",
        "odnheight",
        "odnwidth",
        "op_sharpen",
        "qlt",
        "quality",
        "v",
        "w",
        "wid",
        "width",
    }
)
CDN_IMAGE_QUERY_KEY_PATTERNS = (r"^\$n_\d+w\$$",)
CDN_IMAGE_TRANSFORM_SUFFIX_PATTERN = r"[._](?:AC_)?(?:US|SR|SL|SX|SY|SS|UL)\d+_?"
CDN_IMAGE_PATH_SUFFIX_PATTERN = (
    r"(?:"
    r"_(?:\d+x\d+|pico|icon|thumb|thumbnail|small|compact|medium|large|grande|original)"
    rf"|{CDN_IMAGE_TRANSFORM_SUFFIX_PATTERN}"
    r"|/t_(?:default|thumbnail|pdp_\d+_v\d+|web_pdp_\d+_v\d+)"
    r")(?=\.[a-z0-9]+$|/|$)"
)
AMAZON_IMAGE_CDN_HOSTS = frozenset(
    {"m.media-amazon.com", "images-na.ssl-images-amazon.com"}
)
AMAZON_IMAGE_LOW_RES_SUFFIX_PATTERN = (
    rf"(?:\.?{CDN_IMAGE_TRANSFORM_SUFFIX_PATTERN}|"
    r"\._[^/]*?(?:US|SR|SL|SX|SY|SS|UL)\d+[^/]*_)(?=\.[a-z0-9]+$)"
)
AMAZON_IMAGE_LOW_RES_MAX_DIMENSION = 999
VARIANT_UI_NOISE_EXACT_MATCH_MAX_LENGTH = 8

EXPORT_IMAGE_URL_SUFFIXES = tuple(_CANDIDATE_IMAGE_FILE_EXTENSIONS)
BARE_HOST_URL_RE = re.compile(str(_BARE_HOST_URL_PATTERN), re.I)

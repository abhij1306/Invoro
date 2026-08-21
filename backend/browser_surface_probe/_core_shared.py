from __future__ import annotations


import logging

import re


from pathlib import Path


import pytz  # type: ignore[import-untyped]


from browser_surface_probe.value_coercion import (
    object_dict,
    object_list,
    string_list,
)

_IP_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")

_WHITESPACE_RE = re.compile(r"\s+")

_NON_ALNUM_RE = re.compile(r"[^a-z0-9]+")

_COUNTRY_CODE_BY_NAME = {
    _NON_ALNUM_RE.sub(" ", name.lower()).strip(): code
    for code, name in pytz.country_names.items()
}

_COUNTRY_CODE_BY_NAME.update(
    {
        "uk": "GB",
        "united kingdom": "GB",
        "usa": "US",
        "u s a": "US",
        "united states": "US",
        "united states of america": "US",
    }
)

_BUNDLE_DIRNAME = "browser_surface_probe"

_BASELINE_PROBE_SCRIPT_PATH = Path(__file__).resolve().with_name("baseline_probe.js")

logger = logging.getLogger(__name__)

_object_dict = object_dict

_object_list = object_list

_string_list = string_list

__all__ = ['_BASELINE_PROBE_SCRIPT_PATH', '_BUNDLE_DIRNAME', '_COUNTRY_CODE_BY_NAME', '_IP_RE', '_NON_ALNUM_RE', '_WHITESPACE_RE', '_object_dict', '_object_list', '_string_list', 'logger']  # fmt: skip

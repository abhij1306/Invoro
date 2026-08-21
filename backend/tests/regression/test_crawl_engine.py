from __future__ import annotations

import pytest

from app.services.fetch import fetch_context as crawl_fetch_runtime

from app.services.pipeline import raw_json as extraction_runtime

from app.services.acquisition.host_protection_memory import HostProtectionPolicy

from app.services.adapters.belk import BelkAdapter

from app.services.extract.detail.assembly import record_assembly as detail_extractor

from app.services.extract.detail.identity.core import (
    detail_identity_codes_from_url,
    detail_title_from_url,
    detail_url_is_utility,
    listing_detail_like_path,
)

from app.services.extract.detail.price.core import backfill_detail_price_from_html

from app.services.extract.detail.variants.dom_merge import (
    dom_variants_add_missing_existing_axis,
)

from app.services.extract.detail.variants.pruning import sanitize_variant_row

from app.services.extract.variant_normalization import normalize_variant_record

from app.services.pipeline.extract_records import extract_records

from app.services.js_state.helpers import select_variant

from app.services.js_state.state_normalizer import map_js_state_to_fields

from app.services.listing_extractor import extract_listing_records

from tests.fixtures.loader import read_optional_artifact_text


def _js_shell_html() -> str:
    return """
    <html>
      <body>
        <div id="__next"></div>
        <script>window.__INITIAL_STATE__ = {};</script>
        <script>window.__APP_DATA__ = {};</script>
        <script src="/static/app.js"></script>
      </body>
    </html>
    """


def _rendered_listing_fragment(
    *,
    title: str,
    url: str,
    price: str = "",
    image_url: str = "",
    brand: str = "",
) -> str:
    return f"""
    <article class="product-card">
      <a href="{url}">
        {f'<img src="{image_url}" alt="{title}" />' if image_url else ""}
        <h2 class="product-title">{title}</h2>
      </a>
      {f'<div class="product-brand">{brand}</div>' if brand else ""}
      {f'<div class="price">{price}</div>' if price else ""}
    </article>
    """


__all__ = tuple(name for name in globals() if not name.startswith("__"))

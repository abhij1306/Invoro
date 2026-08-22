# Shopify platform adapter.
from __future__ import annotations

import json
import re
import math
from urllib.parse import ParseResult, urljoin, urlparse

from app.services.dom.html_parser import BeautifulSoup, Tag

from app.services.adapters.base import AdapterResult, BaseAdapter
from app.services.config.adapter_runtime_settings import adapter_runtime_settings
from app.services.extract.variant_axis import normalized_variant_axis_key
from app.services.shared.field_coerce import clean_text, text_or_none

_FETCH_ERRORS = (OSError, RuntimeError, ValueError, TypeError, json.JSONDecodeError)
_SHOPIFY_CDN_URL_RE = re.compile(r"https?://cdn\.shopify\.com(?:[/:?#]|$)", re.I)

from . import shopify_products as _split_owner  # noqa: E402


class ShopifyAdapter(_split_owner.ShopifyProductMixin, BaseAdapter):
    name = "shopify"
    domains: list[str] = []  # any domain can be Shopify; detected by signals

    async def can_handle(self, url: str, html: str) -> bool:
        host = (urlparse(str(url or "")).hostname or "").lower()
        signals = [
            "Shopify.theme" in html,
            bool(_SHOPIFY_CDN_URL_RE.search(html)),
            '"shopify"' in html.lower(),
            host == "myshopify.com" or host.endswith(".myshopify.com"),
        ]
        return any(signals)

    async def extract(
        self,
        url: str,
        html: str,
        surface: str,
        proxy: str | None = None,
    ) -> AdapterResult:
        records: list[dict] = []
        embedded = self._extract_embedded_product(html, url)
        if embedded:
            records.extend(embedded)
        # Listing pages are best served by the public collection endpoint.
        # Detail pages still probe the public endpoint to enrich the embedded
        # payload with the fuller Shopify product object.
        if surface in ("ecommerce_listing", "ecommerce_detail"):
            api_records = await self.try_public_endpoint(
                url,
                html=html,
                surface=surface,
                proxy=proxy,
            )
            if api_records:
                if surface == "ecommerce_detail" and records:
                    records = [self._merge_product_records(records[0], api_records[0])]
                else:
                    records = api_records
        return self._result(records)

    async def try_public_endpoint(
        self,
        url: str,
        html: str = "",
        surface: str = "",
        *,
        proxy: str | None = None,
    ) -> list[dict]:
        """Fetch Shopify product endpoint data.

        Listing pages use `/collections/<handle>/products.json` when possible so
        records stay scoped to the requested collection instead of the entire catalog.
        Detail pages use `/products/<handle>.js` to avoid returning unrelated products.
        """
        parsed = urlparse(url)
        if surface == "ecommerce_detail":
            return await self._fetch_detail_products(
                url, html=html, parsed=parsed, surface=surface, proxy=proxy
            )
        products = await self._fetch_listing_products(parsed, proxy=proxy)
        return [
            self._build_product_record(product, page_url=url, surface=surface)
            for product in products[: adapter_runtime_settings.shopify_max_products]
            if isinstance(product, dict)
        ]

    async def _fetch_detail_products(
        self,
        url: str,
        *,
        html: str,
        parsed: ParseResult,
        surface: str,
        proxy: str | None,
    ) -> list[dict]:
        handle = self._extract_product_handle(parsed.path)
        if not handle:
            return []
        linked = self._linked_variant_product_handles(html, url, current_handle=handle)
        linked = linked or [(handle, "", "")]
        records: list[dict] = []
        for linked_handle, axis_value, axis_key in linked[
            : adapter_runtime_settings.shopify_linked_variant_max_handles
        ]:
            api_url = f"{parsed.scheme}://{parsed.netloc}/products/{linked_handle}.js"
            try:
                data = await self._request_json(
                    api_url,
                    proxy=proxy,
                    timeout_seconds=adapter_runtime_settings.shopify_request_timeout_seconds,
                )
            except _FETCH_ERRORS:
                continue
            if not isinstance(data, dict):
                continue
            page_url = urljoin(
                url, self._localized_product_path(parsed.path, linked_handle)
            )
            record = self._build_product_record(
                data, page_url=page_url, surface=surface
            )
            axis_value = axis_value or self._linked_axis_value_from_product(
                data, axis_key=axis_key, current_handle=handle
            )
            self._apply_linked_axis(record, axis_key=axis_key, axis_value=axis_value)
            records.append(record)
        return self._merge_linked_product_records(records)

    async def _fetch_listing_products(
        self, parsed: ParseResult, *, proxy: str | None
    ) -> list[dict]:
        collection = self._extract_collection_handle(parsed.path)
        api_path = (
            f"/collections/{collection}/products.json"
            if collection
            else "/products.json"
        )
        max_pages = max(
            1,
            math.ceil(
                adapter_runtime_settings.shopify_max_products
                / adapter_runtime_settings.shopify_catalog_limit
            ),
        )
        products: list[dict] = []
        for page in range(1, max_pages + 1):
            api_url = f"{parsed.scheme}://{parsed.netloc}{api_path}?limit={adapter_runtime_settings.shopify_catalog_limit}&page={page}"
            try:
                data = await self._request_json(
                    api_url,
                    proxy=proxy,
                    timeout_seconds=adapter_runtime_settings.shopify_request_timeout_seconds,
                )
            except _FETCH_ERRORS:
                break
            batch = data.get("products", []) if isinstance(data, dict) else []
            if not isinstance(batch, list) or not batch:
                break
            products.extend(product for product in batch if isinstance(product, dict))
            if (
                len(products) >= adapter_runtime_settings.shopify_max_products
                or len(batch) < adapter_runtime_settings.shopify_catalog_limit
            ):
                break
        return products

    def _linked_variant_product_handles(
        self,
        html: str,
        page_url: str,
        *,
        current_handle: str,
    ) -> list[tuple[str, str, str]]:
        if not html:
            return []
        soup = BeautifulSoup(html, "html.parser")
        parsed = urlparse(page_url)
        current_host = parsed.netloc.lower()
        current_handle = str(current_handle or "").strip()
        rows: list[tuple[str, str, str]] = []
        seen: set[str] = set()
        for group in soup.select(
            "[role='radiogroup'], fieldset, [class*='swatch' i], "
            "[class*='variant' i], [class*='option' i], [data-testid*='swatch' i], "
            "[role='group'][aria-label]"
        ):
            self._append_linked_group_handles(
                rows,
                group,
                page_url=page_url,
                current_host=current_host,
                current_handle=current_handle,
                seen=seen,
            )
            if len(rows) >= adapter_runtime_settings.shopify_linked_variant_max_handles:
                return rows
        if current_handle and current_handle not in seen and rows:
            rows.insert(0, (current_handle, "", rows[0][2]))
        if not rows:
            rows.extend(
                self._linked_variant_handles_from_raw_html(
                    html,
                    current_handle=current_handle,
                )
            )
        return rows

    def _append_linked_group_handles(
        self,
        rows: list[tuple[str, str, str]],
        group: Tag,
        *,
        page_url: str,
        current_host: str,
        current_handle: str,
        seen: set[str],
    ) -> None:
        axis_key = self._linked_group_axis(group)
        if axis_key not in {"color", "scent", "style", "material"}:
            return
        anchors = group.select("a[href*='/products/']")
        if len(anchors) < 2:
            return
        for anchor in anchors:
            href = text_or_none(anchor.get("href"))
            linked = urlparse(urljoin(page_url, href or ""))
            handle = self._extract_product_handle(linked.path)
            if (
                not href
                or linked.netloc.lower() != current_host
                or not handle
                or handle in seen
            ):
                continue
            rows.append(
                (
                    handle,
                    self._linked_axis_value(anchor, handle, current_handle),
                    axis_key,
                )
            )
            seen.add(handle)
            if len(rows) >= adapter_runtime_settings.shopify_linked_variant_max_handles:
                return

    def _linked_variant_handles_from_raw_html(
        self,
        html: str,
        *,
        current_handle: str,
    ) -> list[tuple[str, str, str]]:
        pattern = re.compile(r"/products/([a-z0-9][a-z0-9-]+)", re.I)
        handles = [match.group(1).strip("-") for match in pattern.finditer(html)]
        family_prefix = self._linked_handle_family_prefix(current_handle, handles)
        if not family_prefix:
            return []
        axis_key = (
            "scent"
            if any(token in family_prefix for token in ("mist", "fragrance", "scent"))
            else "color"
        )
        rows: list[tuple[str, str, str]] = []
        seen: set[str] = set()
        for handle in handles:
            if not handle.startswith(f"{family_prefix}-") and handle != current_handle:
                continue
            if handle in seen:
                continue
            value = self._axis_value_from_handle(handle, family_prefix)
            rows.append((handle, value, axis_key))
            seen.add(handle)
            if len(rows) >= adapter_runtime_settings.shopify_linked_variant_max_handles:
                break
        if current_handle and current_handle not in seen and rows:
            rows.insert(
                0,
                (
                    current_handle,
                    self._axis_value_from_handle(current_handle, family_prefix),
                    axis_key,
                ),
            )
        return rows

    def _linked_handle_family_prefix(
        self,
        current_handle: str,
        handles: list[str] | None = None,
    ) -> str:
        tokens = [token for token in str(current_handle or "").split("-") if token]
        if len(tokens) < 3:
            return ""
        handle_set = {
            cleaned
            for handle in handles or []
            if (cleaned := str(handle or "").strip())
        }
        for prefix_len in range(len(tokens) - 1, 2, -1):
            prefix = "-".join(tokens[:prefix_len])
            if self._handle_family_match_count(handle_set, current_handle, prefix) >= 2:
                return prefix
        if (
            any(token in tokens for token in ("mist", "fragrance", "scent"))
            and len(tokens) > 3
        ):
            return "-".join(tokens[:-2])
        # Without at least one true sibling handle on the page, the last
        # handle token is most likely a SKU/style code or a category word,
        # not a color. Returning a fabricated family-prefix here causes the
        # adapter to invent ``color`` from the SKU tail (e.g. Dime
        # ``dime2sp2542blk`` or Pura Vida ``bracelet``). Refuse to guess.
        return ""

    @staticmethod
    def _handle_family_match_count(handles: set[str], current: str, prefix: str) -> int:
        return sum(
            handle == current or handle.startswith(f"{prefix}-") for handle in handles
        )

    def _linked_group_axis(self, group: object) -> str:
        if not hasattr(group, "get"):
            return ""
        values: list[object] = [
            group.get("aria-label"),
            group.get("data-option-name"),
            group.get("name"),
            group.get("id"),
            group.get("data-testid"),
            group.get("class"),
        ]
        legend = group.find("legend") if hasattr(group, "find") else None
        if legend is not None:
            values.append(legend.get_text(" ", strip=True))
        for value in values:
            if isinstance(value, list):
                value = " ".join(str(item) for item in value if item)
            axis_key = normalized_variant_axis_key(value)
            if axis_key:
                return axis_key
        return ""

    def _linked_axis_value(
        self,
        anchor: object,
        handle: str,
        current_handle: str,
    ) -> str:
        candidates: list[object] = []
        if hasattr(anchor, "get"):
            candidates.extend(
                [
                    anchor.get("aria-label"),
                    anchor.get("title"),
                    anchor.get("data-value"),
                    anchor.get("data-option-value"),
                    anchor.get_text(" ", strip=True)
                    if hasattr(anchor, "get_text")
                    else "",
                ]
            )
            if hasattr(anchor, "find_parent"):
                for parent in (
                    anchor.find_parent("button"),
                    anchor.find_parent("label"),
                ):
                    if parent is not None:
                        candidates.extend(
                            [
                                parent.get("aria-label"),
                                parent.get("title"),
                                parent.get("data-value"),
                                parent.get("data-option-value"),
                                parent.get_text(" ", strip=True),
                            ]
                        )
        for candidate in candidates:
            value = self._clean_linked_axis_label(candidate)
            if value:
                return value
        return self._axis_value_from_handle(handle, current_handle)

    def _linked_axis_value_from_product(
        self,
        product: dict,
        *,
        axis_key: str,
        current_handle: str,
    ) -> str:
        for field_name in (
            axis_key,
            "shade" if axis_key == "scent" else "",
            "color" if axis_key == "color" else "",
            "colour" if axis_key == "color" else "",
        ):
            value = text_or_none(product.get(field_name)) if field_name else None
            if value:
                return value
        title = text_or_none(product.get("title"))
        if title:
            parts = re.split(r"\s[-–—]\s", title, maxsplit=1)
            if len(parts) == 2 and text_or_none(parts[1]):
                return text_or_none(parts[1]) or ""
        handle = text_or_none(product.get("handle")) or current_handle
        family_prefix = self._linked_handle_family_prefix(current_handle)
        return self._axis_value_from_handle(handle, family_prefix or current_handle)

    def _clean_linked_axis_label(self, value: object) -> str:
        label = clean_text(value)
        if not label:
            return ""
        label = re.sub(
            r"^(?:choose|select|view|alternate|product|color|variant)\s+",
            "",
            label,
            flags=re.I,
        )
        label = re.sub(
            r"^(?:view\s+)?alternate\s+product\s+color\s+",
            "",
            label,
            flags=re.I,
        )
        label = re.sub(r"\s+(?:variant|selected|unselected)$", "", label, flags=re.I)
        return clean_text(label)

    def _axis_value_from_handle(self, handle: str, current_handle: str) -> str:
        handle_tokens = [token for token in str(handle or "").split("-") if token]
        current_tokens = [
            token for token in str(current_handle or "").split("-") if token
        ]
        common_prefix = 0
        for left, right in zip(handle_tokens, current_tokens):
            if left != right:
                break
            common_prefix += 1
        tail = handle_tokens[common_prefix:] or handle_tokens[-1:]
        return clean_text(" ".join(token.capitalize() for token in tail))

    def _apply_linked_axis(
        self,
        record: dict,
        *,
        axis_key: str,
        axis_value: str,
    ) -> None:
        if not axis_key or not axis_value:
            return
        if axis_key == "scent":
            record.pop("color", None)
        if record.get(axis_key) in (None, "", [], {}):
            record[axis_key] = axis_value
        variants = record.get("variants")
        if not isinstance(variants, list):
            variant = {
                field_name: record.get(field_name)
                for field_name in (
                    "sku",
                    "price",
                    "original_price",
                    "currency",
                    "url",
                    "image_url",
                    "availability",
                    "stock_quantity",
                )
                if record.get(field_name) not in (None, "", [], {})
            }
            variant[axis_key] = axis_value
            record["variants"] = [variant]
            record["variant_count"] = 1
            return
        for variant in variants:
            if not isinstance(variant, dict):
                continue
            if axis_key == "scent":
                variant.pop("color", None)
            if variant.get(axis_key) in (None, "", [], {}):
                variant[axis_key] = axis_value

    def _merge_linked_product_records(self, records: list[dict]) -> list[dict]:
        if not records:
            return []
        primary = dict(records[0])
        variants: list[dict] = []
        for record in records:
            for variant in record.get("variants") or []:
                if isinstance(variant, dict):
                    variants.append(variant)
        merged_variants = self._dedupe_variants(variants)
        if merged_variants:
            primary["variants"] = merged_variants
            primary["variant_count"] = len(merged_variants)
        return [primary]

    def _extract_product_handle(self, path: str) -> str | None:
        match = re.search(r"/products/([^/?#]+)", path)
        return match.group(1) if match else None

    def _extract_collection_handle(self, path: str) -> str | None:
        match = re.search(r"/collections/([^/?#]+)", path)
        return match.group(1) if match else None

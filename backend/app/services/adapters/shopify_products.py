# ruff: noqa: F401, F821
from __future__ import annotations

from . import shopify as _owner

globals().update({name: value for name, value in vars(_owner).items() if not name.startswith("__")})

class ShopifyProductMixin:
    def _extract_embedded_product(self, html: str, url: str) -> list[dict]:
        """Extract product data from Shopify's embedded JSON in <script> tags."""
        records = []
        for meta in _shopify_meta_payloads(html):
            product = meta.get("product", {})
            if not isinstance(product, dict) or not product.get("title"):
                continue
            option_names = self._option_names(product.get("options"))
            normalized_variants = [
                normalized
                for variant in (product.get("variants") or [])
                if isinstance(variant, dict)
                if (
                    normalized := self._normalize_variant(
                        variant,
                        option_names=option_names,
                        scheme=urlparse(url).scheme or "https",
                        base_url=url,
                    )
                )
            ]
            normalized_variants = self._dedupe_variants(normalized_variants)
            active_variant = self._select_shopify_variant(
                normalized_variants,
                base_url=url,
            )
            axes = self._variant_axes(normalized_variants)
            # Only the single-value attributes are needed on this branch; discard
            # the selectable-axes half of the tuple.
            _, single_value_attributes = self._split_selectable_axes(axes)
            selected_price = active_variant.get("price") if isinstance(active_variant, dict) else product.get("price")
            flat_variants = flatten_variants_for_public_output(
                normalized_variants,
                page_url=url,
            )
            records.append(
                {
                    "title": product.get("title"),
                    "brand": product.get("vendor"),
                    "vendor": product.get("vendor"),
                    "price": normalize_decimal_price(
                        selected_price,
                        interpret_integral_as_cents=True,
                    ),
                    "category": product.get("type"),
                    "product_type": product.get("type"),
                    "product_id": str(product.get("id")) if product.get("id") not in (None, "", [], {}) else None,
                    "variants": flat_variants,
                    "variant_count": len(flat_variants or []) or None,
                    "product_attributes": single_value_attributes or None,
                }
            )
        return records

    def _image_src(self, image: object) -> str | None:
        if isinstance(image, str):
            return image or None
        if isinstance(image, dict):
            return image.get("src") or image.get("url") or None
        return None

    def _normalize_url(self, value: str | None, scheme: str) -> str | None:
        if not value:
            return None
        if value.startswith("//"):
            return f"{scheme}:{value}"
        return value

    def _option_names(self, raw_options: object) -> list[str]:
        names: list[str] = []
        if isinstance(raw_options, list):
            for option in raw_options:
                if isinstance(option, str):
                    names.append(option)
                elif isinstance(option, dict):
                    label = option.get("name") or option.get("title")
                    if label:
                        names.append(str(label))
        return names

    def _normalize_variant(
        self,
        variant: dict,
        *,
        option_names: list[str],
        scheme: str,
        base_url: str,
    ) -> dict | None:
        row: dict[str, object] = {}
        self._apply_variant_identity_and_money(row, variant, base_url=base_url)
        self._apply_variant_availability(row, variant.get("available"))
        featured = self._normalize_url(self._image_src(variant.get("featured_image")), scheme)
        if featured:
            row["image_url"] = featured
        option_values = self._variant_option_values(variant, option_names=option_names)
        for axis_key, value in option_values.items():
            if axis_key in {"color", "size"}:
                row[axis_key] = value
        if option_values:
            row["option_values"] = option_values
        return row or None

    @staticmethod
    def _apply_variant_identity_and_money(row: dict[str, object], variant: dict, *, base_url: str) -> None:
        if variant.get("id") not in (None, "", [], {}):
            row["variant_id"] = str(variant["id"])
            row["url"] = f"{base_url}{'&' if '?' in base_url else '?'}variant={row['variant_id']}"
        for field in ("sku", "barcode"):
            if variant.get(field):
                row[field] = variant[field]
        for source, target in (("price", "price"), ("compare_at_price", "original_price")):
            value = normalize_decimal_price(variant.get(source), interpret_integral_as_cents=True)
            if value is not None:
                row[target] = value

    @staticmethod
    def _apply_variant_availability(row: dict[str, object], raw: object) -> None:
        if raw is None:
            return
        if isinstance(raw, bool):
            available = raw
        elif isinstance(raw, str):
            available = raw.strip().lower() in {"true", "1", "yes"}
        else:
            available = bool(raw) if isinstance(raw, (int, float)) else False
        row["available"] = available
        row["availability"] = "in_stock" if available else "out_of_stock"

    def _variant_option_values(self, variant: dict, *, option_names: list[str]) -> dict[str, str]:
        option_values: dict[str, str] = {}
        raw_payload = variant.get("options")
        raw_options = raw_payload if isinstance(raw_payload, list) else []
        for index in range(
            1,
            adapter_runtime_settings.shopify_max_option_axis_count + 1,
        ):
            axis_name = option_names[index - 1] if index - 1 < len(option_names) else f"option_{index}"
            axis_key = normalized_variant_axis_key(axis_name) or self._normalize_axis(axis_name)
            value = variant.get(f"option{index}")
            if value in (None, "", [], {}) and index - 1 < len(raw_options):
                value = raw_options[index - 1]
            if value in (None, "", [], {}):
                continue
            option_values[axis_key] = str(value)
        return option_values

    def _build_product_record(
        self,
        product: dict,
        *,
        page_url: str,
        surface: str,
    ) -> dict:
        parsed = urlparse(page_url)
        product_url = urljoin(
            page_url,
            self._localized_product_path(parsed.path, product.get("handle")),
        )
        normalized_variants = self._normalized_product_variants(product, scheme=parsed.scheme, product_url=product_url)
        active_variant = self._select_shopify_variant(normalized_variants, base_url=page_url) or {}
        axes = self._variant_axes(normalized_variants)
        # Only the single-value attributes are needed here; discard the
        # selectable-axes half of the tuple.
        _, single_value_attributes = self._split_selectable_axes(axes)
        flat_variants = flatten_variants_for_public_output(
            normalized_variants,
            page_url=page_url,
        )
        images = self._product_images(product, scheme=parsed.scheme)
        tags = self._product_tags(product.get("tags"))
        record = {
            "title": product.get("title"),
            "brand": product.get("vendor"),
            "description": product.get("body_html", ""),
            "url": product_url,
            "image_url": images[0] if images else None,
            "additional_images": ", ".join(images[1:]) if len(images) > 1 else None,
            "price": active_variant.get("price"),
            "original_price": active_variant.get("original_price"),
            "sku": active_variant.get("sku"),
            "availability": active_variant.get("availability"),
            "category": product.get("product_type"),
            "tags": tags,
            "variants": flat_variants,
            "variant_count": len(flat_variants or []) or None,
            "product_attributes": single_value_attributes or None,
        }
        for field_name in ("color", "size", "barcode"):
            if active_variant.get(field_name):
                record[field_name] = active_variant[field_name]
        if surface == "ecommerce_detail":
            record.update(self._detail_product_fields(product, image_count=len(images)))
        return record

    def _normalized_product_variants(self, product: dict, *, scheme: str, product_url: str) -> list[dict]:
        raw = product.get("variants")
        variants = raw if isinstance(raw, list) else []
        option_names = self._option_names(product.get("options"))
        normalized = [
            row
            for variant in variants
            if isinstance(variant, dict) and (row := self._normalize_variant(variant, option_names=option_names, scheme=scheme, base_url=product_url))
        ]
        return self._dedupe_variants(normalized)

    def _product_images(self, product: dict, *, scheme: str) -> list[str]:
        raw_images = product.get("images")
        return [url for image in (raw_images if isinstance(raw_images, list) else []) if (url := self._normalize_url(self._image_src(image), scheme))]

    @staticmethod
    def _detail_product_fields(product: dict, *, image_count: int) -> dict:
        product_id = product.get("id")
        return {
            "vendor": product.get("vendor"),
            "product_type": product.get("product_type"),
            "product_id": str(product_id) if product_id not in (None, "", [], {}) else None,
            "handle": product.get("handle"),
            "created_at": product.get("created_at"),
            "updated_at": product.get("updated_at"),
            "published_at": product.get("published_at"),
            "image_count": image_count or None,
        }

    @staticmethod
    def _product_tags(raw_tags: object) -> object:
        if not isinstance(raw_tags, str):
            return raw_tags if isinstance(raw_tags, list) else []
        return [token for item in raw_tags.split(",") if (token := item.strip())]

    def _merge_product_records(self, primary: dict, fallback: dict) -> dict:
        merged = dict(primary)
        for key, value in fallback.items():
            if key not in merged or merged.get(key) in (None, "", [], {}):
                merged[key] = value
                continue
            if isinstance(merged.get(key), dict) and isinstance(value, dict) and value:
                nested = dict(value)
                nested.update({nested_key: nested_value for nested_key, nested_value in merged[key].items() if nested_value not in (None, "", [], {})})
                merged[key] = nested
        return merged

    def _variant_axes(self, variants: list[dict]) -> dict[str, list[str]]:
        axes: dict[str, list[str]] = {}
        for variant in variants:
            if not isinstance(variant, dict):
                continue
            option_values = variant.get("option_values")
            if not isinstance(option_values, dict):
                continue
            for axis_name, value in option_values.items():
                cleaned = str(value or "").strip()
                if not cleaned:
                    continue
                axes.setdefault(str(axis_name), [])
                if cleaned not in axes[str(axis_name)]:
                    axes[str(axis_name)].append(cleaned)
        return axes

    def _localized_product_path(self, page_path: str, handle: object) -> str:
        product_handle = str(handle or "").strip().strip("/")
        if not product_handle:
            return str(page_path or "") or "/"
        raw_path = str(page_path or "").strip()
        marker = "/products/"
        marker_index = raw_path.find(marker)
        prefix = raw_path[:marker_index] if marker_index >= 0 else ""
        if marker_index < 0:
            locale_match = re.match(r"^/([a-z]{2}(?:-[a-z]{2})?)(?:/|$)", raw_path, re.I)
            if locale_match is not None:
                prefix = f"/{locale_match.group(1)}"
        return f"{prefix}/products/{product_handle}"

    def _dedupe_variants(self, variants: list[dict]) -> list[dict]:
        deduped: list[dict] = []
        seen: dict[str, int] = {}
        for variant in variants:
            fingerprint = self._variant_fingerprint(variant)
            if fingerprint is None:
                deduped.append(dict(variant))
                continue
            existing_index = seen.get(fingerprint)
            if existing_index is None:
                seen[fingerprint] = len(deduped)
                deduped.append(dict(variant))
                continue
            current = deduped[existing_index]
            if len(variant.keys()) > len(current.keys()):
                merged = dict(variant)
                for key, value in current.items():
                    if merged.get(key) in (None, "", [], {}) and value not in (
                        None,
                        "",
                        [],
                        {},
                    ):
                        merged[key] = value
                deduped[existing_index] = merged
                continue
            for key, value in variant.items():
                if current.get(key) in (None, "", [], {}) and value not in (
                    None,
                    "",
                    [],
                    {},
                ):
                    current[key] = value
        return deduped

    def _variant_fingerprint(self, variant: dict) -> str | None:
        variant_id = str(variant.get("variant_id") or "").strip()
        if variant_id:
            return f"id:{variant_id}"
        sku = str(variant.get("sku") or "").strip()
        option_values = variant.get("option_values")
        if sku and isinstance(option_values, dict) and option_values:
            return json.dumps({"sku": sku, "option_values": option_values}, sort_keys=True)
        if sku:
            return f"sku:{sku}"
        if isinstance(option_values, dict) and option_values:
            return json.dumps({"option_values": option_values}, sort_keys=True)
        return None

    def _split_selectable_axes(self, axes: dict[str, list[str]]) -> tuple[dict[str, list[str]], dict[str, str]]:
        return split_variant_axes(
            axes,
            always_selectable_axes=frozenset({"size"}),
        )

    def _select_shopify_variant(
        self,
        variants: list[dict],
        *,
        base_url: str,
    ) -> dict | None:
        if not variants:
            return None
        parsed = urlsplit(str(base_url or "").strip())
        variant_id = next(
            (str(value).strip() for key, value in parse_qsl(parsed.query, keep_blank_values=False) if key == "variant" and str(value).strip()),
            "",
        )
        if variant_id:
            matched_variant = next(
                (row for row in variants if str(row.get("variant_id") or "").strip() == variant_id),
                None,
            )
            if matched_variant is not None:
                return matched_variant
        return next((row for row in variants if row.get("available") is True), None) or variants[0]

    def _normalize_axis(self, value: object) -> str:
        normalized = normalized_variant_axis_key(value)
        if normalized:
            return normalized
        text = str(value or "").strip().lower().replace("&", " ")
        text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
        return text or "option"

def _shopify_meta_payloads(html: str) -> list[dict]:
    source = str(html or "")
    payloads: list[dict] = []
    for match in _SHOPIFY_META_ASSIGNMENT_RE.finditer(source):
        fragment = _balanced_json_fragment(source[match.end() :])
        if not fragment:
            continue
        payload = _loads_shopify_meta(fragment)
        if isinstance(payload, dict):
            payloads.append(payload)
    return payloads

def _loads_shopify_meta(fragment: str) -> dict | None:
    try:
        payload = json.loads(fragment)
    except (json.JSONDecodeError, TypeError):
        product_fragment = _balanced_object_property_fragment(fragment, "product")
        if not product_fragment:
            return None
        try:
            return {"product": json.loads(product_fragment)}
        except (json.JSONDecodeError, TypeError):
            return None
    return payload if isinstance(payload, dict) else None

def _balanced_object_property_fragment(text: str, property_name: str) -> str:
    match = re.search(rf"(?:^|[{{,])\s*{re.escape(property_name)}\s*:\s*", text, re.S)
    return _balanced_json_fragment(text[match.end() :]) if match else ""

def _balanced_json_fragment(text: str) -> str:
    source = str(text or "")
    start = next((index for index, char in enumerate(source) if char in "{["), -1)
    if start < 0:
        return ""
    opening = source[start]
    closing = "}" if opening == "{" else "]"
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, len(source)):
        char = source[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return source[start : index + 1]
    return ""

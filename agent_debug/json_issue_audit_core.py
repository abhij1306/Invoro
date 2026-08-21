from __future__ import annotations

from ._run_json_issue_audit_shared import *  # noqa: F403


class Issue:
    def __init__(self, category: str, severity: str, field: str, message: str, evidence: Any = None):
        self.category = category
        self.severity = severity
        self.field = field
        self.message = message
        self.evidence = evidence

    def as_dict(self) -> dict[str, Any]:
        row: dict[str, Any] = {
            "category": self.category,
            "severity": self.severity,
            "field": self.field,
            "message": self.message,
        }
        if self.evidence is not None:
            row["evidence"] = self.evidence
        return row

def _safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []

def _safe_str(value: Any) -> str:
    return "" if value is None else str(value).strip()

def _host_from_url(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except Exception:
        return ""

def _is_noise_text(text: str) -> bool:
    cleaned = _safe_str(text)
    if not cleaned:
        return False
    return any(rx.search(cleaned) for rx in NOISE_RES)

def _text_token_count(text: str) -> int:
    return len(re.findall(r"[A-Za-z0-9]+", text or ""))

def _looks_price(value: Any) -> bool:
    text = _safe_str(value).replace(",", "")
    return bool(text and PRICE_RE.match(text))

def _looks_currency(value: Any) -> bool:
    return bool(CURRENCY_RE.match(_safe_str(value)))

def _variant_signature(variant: dict[str, Any]) -> tuple[tuple[str, str], ...]:
    keys = [k for k in variant.keys() if k not in {"url", "image_url", "price", "currency", "availability", "sku", "barcode"}]
    parts = []
    for key in sorted(keys):
        parts.append((key, _safe_str(variant.get(key))))
    return tuple(parts)

def _is_variant_size_value(text: str) -> bool:
    value = _safe_str(text).lower()
    if not value:
        return False
    if SIZE_TOKEN_RE.match(value):
        return True
    if re.fullmatch(r"\d{1,2}(?:\.\d)?(?:w|m)?", value):
        return True
    if re.search(r"\b(oz|fl\.?\s*oz|ml|l|inch|in\.|cm|mm|pack)\b", value, re.I):
        return False
    if re.search(r"\b(queen|king|twin|full)\b", value, re.I):
        return True
    return False

def _find_missing_fields(record: dict[str, Any], issues: list[Issue]) -> None:
    for field in DEFAULT_REQUIRED_FIELDS:
        if field == "currency" and record.get("price") in (None, "", [], {}):
            continue
        value = record.get(field)
        if value in (None, "", [], {}):
            issues.append(Issue("missing_fields", "high", field, f"missing or empty `{field}`"))
    if not any(_safe_str(record.get(key)) for key in ("sku", "barcode", "part_number")):
        issues.append(
            Issue(
                "missing_fields",
                "medium",
                "sku/barcode/part_number",
                "no core product identifier found",
            )
        )

def _find_incorrect_fields(record: dict[str, Any], issues: list[Issue]) -> None:
    url = _safe_str(record.get("url"))
    if url and not URL_RE.match(url):
        issues.append(Issue("incorrect_data", "high", "url", "url not http/https", url))

    price = record.get("price")
    if price not in (None, "") and not _looks_price(price):
        issues.append(Issue("incorrect_data", "high", "price", "price not numeric string", price))

    currency = record.get("currency")
    if currency not in (None, "") and not _looks_currency(currency):
        issues.append(Issue("incorrect_data", "medium", "currency", "currency not 3-letter ISO", currency))

    availability = _safe_str(record.get("availability")).lower()
    if availability and availability not in AVAILABILITY_ALLOWED:
        issues.append(
            Issue(
                "incorrect_data",
                "medium",
                "availability",
                "availability outside canonical set",
                availability,
            )
        )

    for key in ("price", "original_price", "sale_price"):
        value = record.get(key)
        if value in (None, ""):
            continue
        if _looks_price(value):
            try:
                if float(str(value).replace(",", "")) < 0:
                    issues.append(Issue("logical_errors", "high", key, "negative price", value))
            except ValueError:
                pass

    brand = _safe_str(record.get("brand"))
    if brand and re.search(r"[a-z]", brand) and brand == brand.lower() and len(brand) >= 4:
        issues.append(
            Issue(
                "incorrect_data",
                "low",
                "brand",
                "brand appears unnormalized lowercase",
                brand,
            )
        )

    color = _safe_str(record.get("color"))
    if color and re.fullmatch(r"\d{5,}", color):
        issues.append(
            Issue(
                "incorrect_data",
                "medium",
                "color",
                "color looks like numeric swatch/id, not human-readable value",
                color,
            )
        )

    size = _safe_str(record.get("size"))
    if size and re.fullmatch(r"\d(?:\.\d+)?", size) and len(_safe_list(record.get("variants"))) > 0:
        issues.append(
            Issue(
                "incorrect_data",
                "medium",
                "size",
                "size looks like selector index/default, not normalized size label",
                size,
            )
        )

def _find_pollution(record: dict[str, Any], issues: list[Issue]) -> None:
    for field in OPTIONAL_SUSPECT_FIELDS:
        value = record.get(field)
        if isinstance(value, str):
            text = value.strip()
            if not text:
                continue
            if _is_noise_text(text):
                issues.append(Issue("polluted_data", "medium", field, "UI/control noise pattern in text", text[:200]))
            if field == "description":
                trailing = re.search(r"((?:\b\d{1,2}(?:\.5)?\b\s*){8,})$", text)
                if trailing:
                    issues.append(
                        Issue(
                            "polluted_data",
                            "medium",
                            field,
                            "description has trailing size-like numeric list",
                            trailing.group(1).strip()[:200],
                        )
                    )
                if re.search(r"read reviews and buy .* at target\. choose from", text, re.I):
                    issues.append(
                        Issue(
                            "polluted_data",
                            "medium",
                            field,
                            "description looks like generic SEO/storefront copy, not product detail",
                            text[:200],
                        )
                    )
            continue

        if isinstance(value, list):
            if not value:
                continue
            noisy_samples: list[str] = []
            tiny_token_ratio_hits = 0
            for item in value:
                if field == "variants" and isinstance(item, dict):
                    continue
                else:
                    item_text = _safe_str(item)
                if not item_text:
                    continue
                if _is_noise_text(item_text):
                    noisy_samples.append(item_text[:160])
                if field in {"features", "description"} and _text_token_count(item_text) <= 2:
                    tiny_token_ratio_hits += 1
            if noisy_samples:
                issues.append(
                    Issue(
                        "polluted_data",
                        "medium",
                        field,
                        "list contains UI/control noise tokens",
                        noisy_samples[:5],
                    )
                )
            if field == "features" and len(value) >= 8 and tiny_token_ratio_hits >= max(4, len(value) // 2):
                issues.append(
                    Issue(
                        "polluted_data",
                        "high",
                        field,
                        "features list dominated by tiny/noisy tokens",
                        {
                            "total_items": len(value),
                            "tiny_items": tiny_token_ratio_hits,
                        },
                    )
                )
            if field == "tags":
                noisy_tag_prefixes = (
                    "clearance_",
                    "dropship_",
                    "dtlrexclusive_",
                    "employeepromoexclude_",
                    "instoreonly_",
                    "lastsyncdatetime_",
                    "onlineonly_",
                    "promoexclude_",
                    "stylelimit_",
                    "unisexsizingeligible_",
                    "size_",
                    "stock_",
                    "sale_",
                )
                noisy_tags = [
                    _safe_str(item)
                    for item in value
                    if _safe_str(item).lower().startswith(noisy_tag_prefixes)
                ]
                if len(noisy_tags) >= 6:
                    issues.append(
                        Issue(
                            "polluted_data",
                            "high",
                            "tags",
                            "tags polluted by internal metadata tokens",
                            noisy_tags[:12],
                        )
                    )
                url_like_tags = [
                    _safe_str(item)
                    for item in value
                    if re.search(r"(?:^/shop/product/|https?://)", _safe_str(item), re.I)
                ]
                if len(url_like_tags) >= 3:
                    issues.append(
                        Issue(
                            "polluted_data",
                            "medium",
                            "tags",
                            "tags contain related-product URLs or links",
                            url_like_tags[:8],
                        )
                    )

def _normalized_image_key(url: str) -> str:
    text = _safe_str(url)
    if not text:
        return ""
    parsed = urlparse(text)
    filtered_query = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if not (
            str(key or "").lower() in {"fit", "wid", "width", "hei", "height", "qlt"}
            or re.fullmatch(r"\$n_\d+w\$", str(key or ""), re.I)
        )
    ]
    return urlunparse(
        parsed._replace(query=urlencode(filtered_query, doseq=True), fragment="")
    ).lower()

def _variant_rows_have_semantic_axis_grid(variants: list[Any]) -> bool:
    axis_fields = {"size", "color", "style", "width", "length", "flavor"}
    axis_rows = 0
    unique_signatures: set[tuple[tuple[str, str], ...]] = set()
    for variant in variants:
        if not isinstance(variant, dict):
            continue
        axis_parts = tuple(
            sorted(
                (key, _safe_str(variant.get(key)).lower())
                for key in axis_fields
                if _safe_str(variant.get(key))
            )
        )
        if len(axis_parts) >= 2:
            axis_rows += 1
            unique_signatures.add(axis_parts)
    return axis_rows >= max(8, len(variants) * 0.8) and len(unique_signatures) == axis_rows

def _find_image_issues(record: dict[str, Any], issues: list[Issue]) -> None:
    image_url = _safe_str(record.get("image_url"))
    additional = [_safe_str(item) for item in _safe_list(record.get("additional_images")) if _safe_str(item)]
    all_images = [item for item in [image_url, *additional] if item]
    if not all_images:
        return

    lowres_amazon = [url for url in all_images if "_AC_US40_" in url]
    if lowres_amazon and len(lowres_amazon) >= max(2, len(all_images) // 2):
        issues.append(
            Issue(
                "polluted_data",
                "high",
                "image_url/additional_images",
                "image set appears low-res thumbnail-only (Amazon _AC_US40_)",
                lowres_amazon[:4],
            )
        )

    if len(additional) >= 8:
        norm = [_normalized_image_key(url) for url in additional if _normalized_image_key(url)]
        if norm:
            unique = len(set(norm))
            duplicate_ratio = 1 - (unique / max(1, len(norm)))
            if duplicate_ratio >= 0.35:
                issues.append(
                    Issue(
                        "polluted_data",
                        "medium",
                        "additional_images",
                        "additional_images heavily duplicated across resized/query variants",
                        {"total": len(norm), "unique_base": unique},
                    )
                )

def _looks_like_variant_expected(record: dict[str, Any]) -> bool:
    host = _host_from_url(_safe_str(record.get("url")))
    if "discogs.com" in host:
        return False
    text = " ".join(
        [
            _safe_str(record.get("title")),
            _safe_str(record.get("category")),
            _safe_str(record.get("description"))[:600],
        ]
    )
    if any(rx.search(text) for rx in APPAREL_VARIANT_HINT_RES):
        return True
    url = _safe_str(record.get("url")).lower()
    if re.search(r"/(sneaker|shoe|footwear|apparel|clothing)/", url):
        return True
    host = _host_from_url(url)
    if host in {"www.goat.com", "stockx.com", "www.size.co.uk", "www.endclothing.com"}:
        return True
    desc = _safe_str(record.get("description"))
    if re.search(r"\b(size|sizes)\s*:\s*(?:please\s+select|[0-9xmsl])", desc, re.I):
        return True
    if re.search(r"((?:\b\d{1,2}(?:\.\d)?\b\s*){8,})$", desc):
        return True
    if _is_variant_size_value(_safe_str(record.get("size"))):
        return True
    return False

def _find_variant_issues(record: dict[str, Any], issues: list[Issue]) -> None:
    variants = _safe_list(record.get("variants"))
    variant_count = record.get("variant_count")

    if variant_count not in (None, ""):
        try:
            declared = int(str(variant_count))
            if declared != len(variants):
                issues.append(
                    Issue(
                        "logical_errors",
                        "medium",
                        "variant_count",
                        "variant_count mismatches variants length",
                        {"variant_count": declared, "actual": len(variants)},
                    )
                )
        except ValueError:
            issues.append(Issue("incorrect_data", "medium", "variant_count", "variant_count not int", variant_count))

    if not variants:
        if _looks_like_variant_expected(record):
            issues.append(
                Issue(
                    "incorrect_variants",
                    "high",
                    "variants",
                    "variants missing but product looks multi-variant",
                )
            )
        return

    noisy_variant_rows = 0
    duplicate_signatures = 0
    seen_signatures: set[tuple[tuple[str, str], ...]] = set()

    for idx, variant in enumerate(variants):
        if not isinstance(variant, dict):
            issues.append(Issue("incorrect_variants", "high", "variants", f"variant index {idx} not object", variant))
            continue

        variant_url = _safe_str(variant.get("url"))
        if variant_url and not URL_RE.match(variant_url):
            issues.append(Issue("incorrect_variants", "medium", "variants.url", "variant url not http/https", variant_url))

        v_price = variant.get("price")
        if v_price not in (None, "") and not _looks_price(v_price):
            issues.append(Issue("incorrect_variants", "medium", "variants.price", "variant price not numeric", v_price))

        for key, value in variant.items():
            if key in {"url", "image_url"}:
                continue
            text = _safe_str(value)
            if not text:
                continue
            if key in {"flavor", "scent"} and re.search(r"\bcookie\b", text, re.I):
                continue
            if _is_noise_text(text):
                noisy_variant_rows += 1
                break

        signature = _variant_signature(variant)
        if signature in seen_signatures and signature:
            duplicate_signatures += 1
        seen_signatures.add(signature)

    if noisy_variant_rows:
        sev = "high" if noisy_variant_rows >= max(3, len(variants) // 3) else "medium"
        issues.append(
            Issue(
                "incorrect_variants",
                sev,
                "variants",
                "variants contain UI/control noise values",
                {"noisy_variants": noisy_variant_rows, "total_variants": len(variants)},
            )
        )

    if duplicate_signatures >= max(2, len(variants) // 5):
        issues.append(
            Issue(
                "incorrect_variants",
                "medium",
                "variants",
                "many duplicate variant attribute signatures",
                {"duplicate_signatures": duplicate_signatures, "total_variants": len(variants)},
            )
        )
    if len(variants) >= 80 and not _variant_rows_have_semantic_axis_grid(variants):
        issues.append(Issue("incorrect_variants", "high", "variants", "suspiciously high variant volume", len(variants)))

def _url_path_tokens(url: str) -> set[str]:
    """Extract meaningful tokens from URL path for coherence checking."""
    try:
        path = urlparse(url).path.lower()
    except Exception:
        return set()
    # strip common ecommerce path prefixes
    path = re.sub(r"^/(products?|shop|p|collections?|dp|ip|store|detail)/", "/", path)
    # split on separators
    tokens = set(re.findall(r"[a-z]{3,}", path))
    # remove generic noise tokens
    tokens -= {
        "html", "htm", "aspx", "php", "www", "com", "products", "product",
        "shop", "collections", "the", "and", "for", "with", "from",
        "mens", "womens", "men", "women", "unisex", "kids",
        "catalog", "jsp", "prod", "camera", "cameras", "lens", "lenses",
        "interchangeable",
    }
    return tokens

def _title_tokens(title: str) -> set[str]:
    """Extract meaningful tokens from title."""
    tokens = set(re.findall(r"[a-z]{3,}", title.lower()))
    tokens -= {
        "the", "and", "for", "with", "from", "men", "women", "mens", "womens",
        "unisex", "kids", "size", "color", "style", "new",
    }
    return tokens

def _find_url_title_mismatch(record: dict[str, Any], issues: list[Issue]) -> None:
    """Flag when URL path and title share almost no meaningful tokens."""
    url = _safe_str(record.get("url"))
    title = _safe_str(record.get("title"))
    if not url or not title:
        return

    url_tokens = _url_path_tokens(url)
    t_tokens = _title_tokens(title)

    if not url_tokens or not t_tokens:
        return
    # need at least 3 tokens on each side to make a meaningful comparison
    if len(url_tokens) < 3 or len(t_tokens) < 2:
        return

    overlap = url_tokens & t_tokens
    # ratio relative to the smaller set
    smaller = min(len(url_tokens), len(t_tokens))
    ratio = len(overlap) / smaller if smaller else 0

    if ratio == 0:
        issues.append(
            Issue(
                "coherence",
                "high",
                "url/title",
                "URL path and title share zero meaningful tokens — possible wrong product or redirect",
                {"url_tokens": sorted(url_tokens)[:10], "title_tokens": sorted(t_tokens)[:10]},
            )
        )
    elif ratio <= 0.2 and smaller >= 3:
        issues.append(
            Issue(
                "coherence",
                "medium",
                "url/title",
                "URL path and title have very low token overlap",
                {"overlap_ratio": round(ratio, 2), "overlap": sorted(overlap)},
            )
        )
    elif len(overlap) == 1 and smaller >= 4 and len(url_tokens) >= 5:
        # single generic word overlap with substantial URL path — likely wrong product
        issues.append(
            Issue(
                "coherence",
                "medium",
                "url/title",
                "URL path and title share only one token despite rich URL — possible mismatch",
                {"overlap_ratio": round(ratio, 2), "overlap": sorted(overlap), "url_tokens": sorted(url_tokens)[:10]},
            )
        )

def _find_blocked_page(record: dict[str, Any], issues: list[Issue]) -> None:
    """Detect titles that indicate a blocked/captcha page rather than real product."""
    title = _safe_str(record.get("title"))
    if not title:
        return
    for rx in BLOCKED_PAGE_TITLE_RES:
        if rx.search(title):
            issues.append(
                Issue(
                    "blocked_page",
                    "high",
                    "title",
                    "title matches blocked/captcha page pattern — extraction likely failed",
                    title[:200],
                )
            )
            return

def _find_non_product_images(record: dict[str, Any], issues: list[Issue]) -> None:
    """Flag additional_images that look like category/banner/navigation assets."""
    additional = [_safe_str(item) for item in _safe_list(record.get("additional_images")) if _safe_str(item)]
    if not additional:
        return

    non_product_hits: list[str] = []
    for img_url in additional:
        for rx in NON_PRODUCT_IMAGE_PATH_RES:
            if rx.search(img_url):
                non_product_hits.append(img_url)
                break

    if non_product_hits and len(non_product_hits) >= max(2, len(additional) // 2):
        issues.append(
            Issue(
                "polluted_data",
                "high",
                "additional_images",
                "additional_images contain non-product assets (category/banner/navigation)",
                non_product_hits[:5],
            )
        )
    elif non_product_hits:
        issues.append(
            Issue(
                "polluted_data",
                "medium",
                "additional_images",
                "some additional_images look like non-product assets",
                non_product_hits[:5],
            )
        )

def _find_garbage_features(record: dict[str, Any], issues: list[Issue]) -> None:
    """Flag features list that contains only product IDs or purely numeric garbage."""
    features = record.get("features")
    if not isinstance(features, list) or not features:
        return
    if len(features) == 1:
        item = _safe_str(features[0])
        if item and re.fullmatch(r"\d{5,}", item):
            issues.append(
                Issue(
                    "polluted_data",
                    "medium",
                    "features",
                    "features contains single numeric value — likely product ID leak, not a feature",
                    item,
                )
            )
    elif len(features) <= 3:
        all_numeric = all(re.fullmatch(r"\d{4,}", _safe_str(f)) for f in features if _safe_str(f))
        if all_numeric and any(_safe_str(f) for f in features):
            issues.append(
                Issue(
                    "polluted_data",
                    "medium",
                    "features",
                    "features list is all numeric IDs — likely not real product features",
                    [_safe_str(f) for f in features],
                )
            )

def _find_logical_errors(record: dict[str, Any], issues: list[Issue]) -> None:
    price = record.get("price")
    sale_price = record.get("sale_price")
    original_price = record.get("original_price")

    if _looks_price(price) and _looks_price(original_price):
        if float(str(price)) > float(str(original_price)):
            issues.append(
                Issue(
                    "logical_errors",
                    "medium",
                    "price/original_price",
                    "price greater than original_price",
                    {"price": price, "original_price": original_price},
                )
            )

    if _looks_price(price) and _looks_price(sale_price):
        if float(str(sale_price)) > float(str(price)):
            issues.append(
                Issue(
                    "logical_errors",
                    "low",
                    "sale_price/price",
                    "sale_price greater than price",
                    {"price": price, "sale_price": sale_price},
                )
            )

    title = _safe_str(record.get("title"))
    description = _safe_str(record.get("description"))
    if title and description and title.lower() == description.lower():
        issues.append(Issue("logical_errors", "low", "description", "description identical to title"))
    product_details = _safe_str(record.get("product_details"))
    if description and product_details and description[:200].lower() == product_details[:200].lower():
        issues.append(
            Issue(
                "logical_errors",
                "low",
                "description/product_details",
                "description and product_details look redundant",
            )
        )

    host = _host_from_url(_safe_str(record.get("url")))
    tags = [str(item) for item in _safe_list(record.get("tags"))]
    if "discogs.com" in host:
        discogs_noise = [
            token
            for token in tags
            if re.search(r"(labelrelationship|phonographic_copyright|published_by|distributed_by)", token, re.I)
        ]
        if discogs_noise:
            issues.append(
                Issue(
                    "logical_errors",
                    "high",
                    "url/tags",
                    "record likely non-ecommerce page misclassified as commerce product",
                    discogs_noise[:8],
                )
            )

def audit_record(record: dict[str, Any]) -> dict[str, Any]:
    issues: list[Issue] = []

    _find_missing_fields(record, issues)
    _find_incorrect_fields(record, issues)
    _find_pollution(record, issues)
    _find_image_issues(record, issues)
    _find_non_product_images(record, issues)
    _find_variant_issues(record, issues)
    _find_logical_errors(record, issues)
    _find_url_title_mismatch(record, issues)
    _find_blocked_page(record, issues)
    _find_garbage_features(record, issues)

    url = _safe_str(record.get("url"))
    host = _host_from_url(url)

    severity_rank = {"high": 3, "medium": 2, "low": 1}
    max_severity = "none"
    for issue in issues:
        if severity_rank.get(issue.severity, 0) > severity_rank.get(max_severity, 0):
            max_severity = issue.severity

    category_counts = Counter(issue.category for issue in issues)

    return {
        "url": url,
        "host": host,
        "title": _safe_str(record.get("title")),
        "issue_count": len(issues),
        "max_severity": max_severity,
        "category_counts": dict(sorted(category_counts.items())),
        "issues": [issue.as_dict() for issue in issues],
    }

__all__ = tuple(
    name for name in globals() if not name.startswith("__")
)

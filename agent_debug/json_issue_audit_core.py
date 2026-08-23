from __future__ import annotations

from ._run_json_issue_audit_shared import (  # fmt: skip
    APPAREL_VARIANT_HINT_RES,
    BLOCKED_PAGE_TITLE_RES,
    NON_PRODUCT_IMAGE_PATH_RES,
    URL_RE,
    Any,
    Counter,
    parse_qsl,
    re,
    urlencode,
    urlparse,
    urlunparse,
)
from .json_issue_audit_field_checks import (  # fmt: skip
    Issue,
    _find_incorrect_fields,
    _find_missing_fields,
    _find_pollution,
    _host_from_url,
    _host_matches_domain,
    _is_noise_text,
    _is_variant_size_value,
    _looks_price,
    _safe_list,
    _safe_str,
    _variant_signature,
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
    return (
        axis_rows >= max(8, len(variants) * 0.8) and len(unique_signatures) == axis_rows
    )


def _find_image_issues(record: dict[str, Any], issues: list[Issue]) -> None:
    image_url = _safe_str(record.get("image_url"))
    additional = [
        _safe_str(item)
        for item in _safe_list(record.get("additional_images"))
        if _safe_str(item)
    ]
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
        norm = [
            _normalized_image_key(url)
            for url in additional
            if _normalized_image_key(url)
        ]
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
    if _host_matches_domain(host, "discogs.com"):
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
    return _is_variant_size_value(_safe_str(record.get("size")))


def _check_declared_variant_count(
    variant_count: object, variants: list[Any], issues: list[Issue]
) -> None:
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
            issues.append(
                Issue(
                    "incorrect_data",
                    "medium",
                    "variant_count",
                    "variant_count not int",
                    variant_count,
                )
            )


def _check_variant_fields(variant: dict[str, Any], issues: list[Issue]) -> None:
    variant_url = _safe_str(variant.get("url"))
    if variant_url and not URL_RE.match(variant_url):
        issues.append(
            Issue(
                "incorrect_variants",
                "medium",
                "variants.url",
                "variant url not http/https",
                variant_url,
            )
        )
    variant_price = variant.get("price")
    if variant_price not in (None, "") and not _looks_price(variant_price):
        issues.append(
            Issue(
                "incorrect_variants",
                "medium",
                "variants.price",
                "variant price not numeric",
                variant_price,
            )
        )


def _variant_has_noise(variant: dict[str, Any]) -> bool:
    for key, value in variant.items():
        if key in {"url", "image_url"}:
            continue
        text = _safe_str(value)
        if not text or (
            key in {"flavor", "scent"} and re.search(r"\bcookie\b", text, re.I)
        ):
            continue
        if _is_noise_text(text):
            return True
    return False


def _variant_quality_counts(
    variants: list[Any], issues: list[Issue]
) -> tuple[int, int]:
    noisy_variant_rows = 0
    duplicate_signatures = 0
    seen_signatures: set[tuple[tuple[str, str], ...]] = set()
    for idx, variant in enumerate(variants):
        if not isinstance(variant, dict):
            issues.append(
                Issue(
                    "incorrect_variants",
                    "high",
                    "variants",
                    f"variant index {idx} not object",
                    variant,
                )
            )
            continue
        _check_variant_fields(variant, issues)
        noisy_variant_rows += int(_variant_has_noise(variant))
        signature = _variant_signature(variant)
        if signature in seen_signatures and signature:
            duplicate_signatures += 1
        seen_signatures.add(signature)
    return noisy_variant_rows, duplicate_signatures


def _append_aggregate_variant_issues(
    variants: list[Any],
    issues: list[Issue],
    *,
    noisy_variant_rows: int,
    duplicate_signatures: int,
) -> None:

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
                {
                    "duplicate_signatures": duplicate_signatures,
                    "total_variants": len(variants),
                },
            )
        )
    if len(variants) >= 80 and not _variant_rows_have_semantic_axis_grid(variants):
        issues.append(
            Issue(
                "incorrect_variants",
                "high",
                "variants",
                "suspiciously high variant volume",
                len(variants),
            )
        )


def _find_variant_issues(record: dict[str, Any], issues: list[Issue]) -> None:
    variants = _safe_list(record.get("variants"))
    _check_declared_variant_count(record.get("variant_count"), variants, issues)
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
    noisy_variant_rows, duplicate_signatures = _variant_quality_counts(variants, issues)
    _append_aggregate_variant_issues(
        variants,
        issues,
        noisy_variant_rows=noisy_variant_rows,
        duplicate_signatures=duplicate_signatures,
    )


def _url_path_tokens(url: str) -> set[str]:
    """Extract meaningful tokens from URL path for coherence checking."""
    try:
        path = urlparse(url).path.lower()
    except ValueError:
        return set()
    # strip common ecommerce path prefixes
    path = re.sub(r"^/(products?|shop|p|collections?|dp|ip|store|detail)/", "/", path)
    # split on separators
    tokens = set(re.findall(r"[a-z]{3,}", path))
    # remove generic noise tokens
    tokens -= {
        "html",
        "htm",
        "aspx",
        "php",
        "www",
        "com",
        "products",
        "product",
        "shop",
        "collections",
        "the",
        "and",
        "for",
        "with",
        "from",
        "mens",
        "womens",
        "men",
        "women",
        "unisex",
        "kids",
        "catalog",
        "jsp",
        "prod",
        "camera",
        "cameras",
        "lens",
        "lenses",
        "interchangeable",
    }
    return tokens


def _title_tokens(title: str) -> set[str]:
    """Extract meaningful tokens from title."""
    tokens = set(re.findall(r"[a-z]{3,}", title.lower()))
    tokens -= {
        "the",
        "and",
        "for",
        "with",
        "from",
        "men",
        "women",
        "mens",
        "womens",
        "unisex",
        "kids",
        "size",
        "color",
        "style",
        "new",
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
                {
                    "url_tokens": sorted(url_tokens)[:10],
                    "title_tokens": sorted(t_tokens)[:10],
                },
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
                {
                    "overlap_ratio": round(ratio, 2),
                    "overlap": sorted(overlap),
                    "url_tokens": sorted(url_tokens)[:10],
                },
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
    additional = [
        _safe_str(item)
        for item in _safe_list(record.get("additional_images"))
        if _safe_str(item)
    ]
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
        all_numeric = all(
            re.fullmatch(r"\d{4,}", _safe_str(f)) for f in features if _safe_str(f)
        )
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

    if (
        _looks_price(price)
        and _looks_price(original_price)
        and float(str(price).replace(",", ""))
        > float(str(original_price).replace(",", ""))
    ):
        issues.append(
            Issue(
                "logical_errors",
                "medium",
                "price/original_price",
                "price greater than original_price",
                {"price": price, "original_price": original_price},
            )
        )

    if (
        _looks_price(price)
        and _looks_price(sale_price)
        and float(str(sale_price).replace(",", "")) > float(str(price).replace(",", ""))
    ):
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
        issues.append(
            Issue(
                "logical_errors", "low", "description", "description identical to title"
            )
        )
    product_details = _safe_str(record.get("product_details"))
    if (
        description
        and product_details
        and description[:200].lower() == product_details[:200].lower()
    ):
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
    if _host_matches_domain(host, "discogs.com"):
        discogs_noise = [
            token
            for token in tags
            if re.search(
                r"(labelrelationship|phonographic_copyright|published_by|distributed_by)",
                token,
                re.I,
            )
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


__all__ = ['Issue', 'audit_record']  # fmt: skip

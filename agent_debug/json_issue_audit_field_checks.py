from __future__ import annotations

from ._run_json_issue_audit_shared import (  # fmt: skip
    AVAILABILITY_ALLOWED,
    CURRENCY_RE,
    DEFAULT_REQUIRED_FIELDS,
    NOISE_RES,
    OPTIONAL_SUSPECT_FIELDS,
    PRICE_RE,
    SIZE_TOKEN_RE,
    URL_RE,
    Any,
    re,
    urlparse,
)


class Issue:
    def __init__(
        self,
        category: str,
        severity: str,
        field: str,
        message: str,
        evidence: Any = None,
    ):
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
    keys = [
        k
        for k in variant
        if k
        not in {
            "url",
            "image_url",
            "price",
            "currency",
            "availability",
            "sku",
            "barcode",
        }
    ]
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
            issues.append(
                Issue("missing_fields", "high", field, f"missing or empty `{field}`")
            )
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
        issues.append(
            Issue("incorrect_data", "high", "price", "price not numeric string", price)
        )

    currency = record.get("currency")
    if currency not in (None, "") and not _looks_currency(currency):
        issues.append(
            Issue(
                "incorrect_data",
                "medium",
                "currency",
                "currency not 3-letter ISO",
                currency,
            )
        )

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
                    issues.append(
                        Issue("logical_errors", "high", key, "negative price", value)
                    )
            except ValueError:
                pass

    brand = _safe_str(record.get("brand"))
    if (
        brand
        and re.search(r"[a-z]", brand)
        and brand == brand.lower()
        and len(brand) >= 4
    ):
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
    if (
        size
        and re.fullmatch(r"\d(?:\.\d+)?", size)
        and len(_safe_list(record.get("variants"))) > 0
    ):
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
                issues.append(
                    Issue(
                        "polluted_data",
                        "medium",
                        field,
                        "UI/control noise pattern in text",
                        text[:200],
                    )
                )
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
                if re.search(
                    r"read reviews and buy .* at target\. choose from", text, re.I
                ):
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
                if (
                    field in {"features", "description"}
                    and _text_token_count(item_text) <= 2
                ):
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
            if (
                field == "features"
                and len(value) >= 8
                and tiny_token_ratio_hits >= max(4, len(value) // 2)
            ):
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
                    if re.search(
                        r"(?:^/shop/product/|https?://)", _safe_str(item), re.I
                    )
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

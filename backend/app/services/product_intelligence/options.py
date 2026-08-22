from __future__ import annotations

from app.services.config.product_intelligence import (
    PRIVATE_LABEL_EXCLUDE,
    PRIVATE_LABEL_FLAG,
    PRIVATE_LABEL_INCLUDE,
    product_intelligence_settings,
)


def normalized_options(value: object) -> dict[str, object]:
    raw = dict(value or {}) if isinstance(value, dict) else {}
    return {
        "max_source_products": bounded_int(
            raw.get("max_source_products"),
            product_intelligence_settings.max_source_products,
        ),
        "max_candidates_per_product": bounded_int(
            raw.get("max_candidates_per_product"),
            product_intelligence_settings.max_candidates_per_product,
        ),
        "search_provider": str(
            raw.get("search_provider")
            or product_intelligence_settings.default_search_provider
        )
        .strip()
        .lower(),
        "private_label_mode": private_label_mode(raw.get("private_label_mode")),
        "confidence_threshold": bounded_float(
            raw.get("confidence_threshold"),
            product_intelligence_settings.confidence_threshold,
        ),
        "allowed_domains": string_list(raw.get("allowed_domains")),
        "excluded_domains": string_list(raw.get("excluded_domains")),
        "llm_enrichment_enabled": bool(raw.get("llm_enrichment_enabled")),
    }


def meets_confidence_threshold(
    score: float, *, options: dict[str, object] | None
) -> bool:
    threshold = bounded_float(
        (options or {}).get("confidence_threshold"),
        product_intelligence_settings.confidence_threshold,
    )
    return float(score) >= threshold


def private_label_mode(value: object) -> str:
    mode = str(value or PRIVATE_LABEL_EXCLUDE).strip().lower()
    return (
        mode
        if mode in {PRIVATE_LABEL_EXCLUDE, PRIVATE_LABEL_FLAG, PRIVATE_LABEL_INCLUDE}
        else PRIVATE_LABEL_EXCLUDE
    )


def bounded_int(value: object, default: int) -> int:
    try:
        parsed = int(value) if isinstance(value, (int, float)) else int(str(value))
    except (TypeError, ValueError):
        parsed = int(default)
    return max(1, parsed)


def bounded_float(value: object, default: float) -> float:
    try:
        parsed = float(value) if isinstance(value, (int, float)) else float(str(value))
    except (TypeError, ValueError):
        parsed = float(default)
    return min(max(parsed, 0.0), 1.0)


def as_float_or_default(value: object, default: float) -> float:
    try:
        return float(value) if isinstance(value, (int, float)) else float(str(value))
    except (TypeError, ValueError):
        return default


def as_price(value: object) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def as_int(value: object) -> int | None:
    try:
        parsed = int(value) if isinstance(value, (int, float)) else int(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def as_nonnegative_int(value: object) -> int | None:
    try:
        parsed = int(value) if isinstance(value, (int, float)) else int(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed >= 0 else None


def option_int(options: dict[str, object], key: str, *, default: int) -> int:
    return bounded_int(options.get(key), default)


def int_list(value: object) -> list[int]:
    if not isinstance(value, list):
        return []
    return [parsed for item in value if (parsed := as_int(item)) is not None]


def string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        if not isinstance(value, str):
            return []
        value = [line.strip() for line in value.splitlines()]
    return [
        str(item or "").strip().lower() for item in value if str(item or "").strip()
    ]

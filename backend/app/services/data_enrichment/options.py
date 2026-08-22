from __future__ import annotations

from app.services.config.data_enrichment import (
    DATA_ENRICHMENT_TAXONOMY_VERSION,
    data_enrichment_settings,
)


def normalized_options(value: object) -> dict[str, object]:
    raw = dict(value or {}) if isinstance(value, dict) else {}
    return {
        "max_source_records": bounded_int(
            raw.get("max_source_records"),
            data_enrichment_settings.max_source_records,
            ceiling=data_enrichment_settings.max_source_records,
        ),
        "llm_enabled": bool(raw.get("llm_enabled", False)),
        "taxonomy_path": str(data_enrichment_settings.taxonomy_path),
        "attributes_path": str(data_enrichment_settings.attributes_path),
        "taxonomy_version": DATA_ENRICHMENT_TAXONOMY_VERSION,
        "max_concurrency": data_enrichment_settings.max_concurrency,
    }


def option_int(options: dict[str, object], key: str) -> int:
    return bounded_int(
        options.get(key),
        data_enrichment_settings.max_source_records,
        ceiling=data_enrichment_settings.max_source_records,
    )


def bounded_int(value: object, default: int, *, ceiling: int) -> int:
    try:
        parsed = int(value) if isinstance(value, (int, float)) else int(str(value))
    except (TypeError, ValueError):
        parsed = int(default)
    return min(max(1, parsed), int(ceiling))


def int_list(value: object) -> list[int]:
    if not isinstance(value, list):
        return []
    return [parsed for item in value if (parsed := as_int(item)) is not None]


def as_int(value: object) -> int | None:
    try:
        parsed = int(value) if isinstance(value, (int, float)) else int(str(value))
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None

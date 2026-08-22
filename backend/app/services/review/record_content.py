from __future__ import annotations

from pathlib import Path

from app.models.crawl_run import CrawlRecord
from app.services.config.extraction_rules import EXTRACTION_RULES, REVIEW_CONTAINER_KEYS
from app.services.db_utils import mapping_or_empty


def render_review_html(records: list[CrawlRecord]) -> str:
    for record in records:
        html = _load_record_html(record)
        if html:
            return html
    return ""


def _load_record_html(record: CrawlRecord) -> str:
    raw_path = str(record.raw_html_path or "").strip()
    if not raw_path:
        return ""
    path = Path(raw_path)
    if not path.exists() or not path.is_file():
        return ""
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""


def review_bucket_rows(record: CrawlRecord) -> list[dict]:
    discovered_data = mapping_or_empty(record.discovered_data)
    rows = discovered_data.get("review_bucket")
    if not isinstance(rows, list):
        return []
    return [row for row in rows if isinstance(row, dict)]


def normalized_review_fields(records: list[CrawlRecord]) -> list[str]:
    return sorted(
        {
            str(key)
            for record in records
            for key, value in mapping_or_empty(record.data).items()
            if review_value_is_visible(key, value)
        }
    )


def discovered_review_fields(records: list[CrawlRecord]) -> list[str]:
    bucket_fields = {
        key
        for record in records
        for row in review_bucket_rows(record)
        if (key := str(row.get("key") or "").strip())
    }
    if bucket_fields:
        return sorted(bucket_fields)
    return sorted(
        {
            str(key)
            for record in records
            for source in record_review_sources(record)
            for key, value in source.items()
            if review_value_is_visible(key, value) and key not in REVIEW_CONTAINER_KEYS
        }
    )


def record_review_sources(record: CrawlRecord) -> tuple[dict, dict, dict]:
    return (
        mapping_or_empty(record.discovered_data),
        mapping_or_empty(record.raw_data),
        mapping_or_empty(record.data),
    )


def review_value_is_visible(key: object, value: object) -> bool:
    return value not in (None, "", [], {}) and not str(key).startswith("_")


def found_review_fields(
    records: list[CrawlRecord], *, requested_fields: list[str]
) -> list[str]:
    found = {
        str(field_name)
        for record in records
        for field_name, value in mapping_or_empty(record.data).items()
        if value not in (None, "", [], {})
    }
    found.update(
        str(field_name)
        for record in records
        for field_name, payload in mapping_or_empty(
            mapping_or_empty(record.source_trace).get("field_discovery")
        ).items()
        if isinstance(payload, dict) and payload.get("status") == "found"
    )
    if found or not requested_fields:
        return sorted(found)
    dom_patterns = mapping_or_empty(EXTRACTION_RULES.get("dom_patterns"))
    return sorted(
        field
        for field in requested_fields
        if str(dom_patterns.get(field) or "").strip()
    )

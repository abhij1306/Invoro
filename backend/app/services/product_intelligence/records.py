from __future__ import annotations

from app.models.crawl_run import CrawlRecord
from app.models.product_intelligence import ProductIntelligenceSourceProduct
from app.services.product_intelligence.candidate_urls import (
    looks_like_product_detail_url,
)


def row_data_payload(row: dict[str, object]) -> dict[str, object]:
    raw_data = row.get("data")
    if isinstance(raw_data, dict):
        return {str(key): value for key, value in raw_data.items()}
    return {}


def resolved_source_url(row: dict[str, object], snapshot: dict[str, object]) -> str:
    row_url = str(row.get("source_url") or "").strip()
    snapshot_url = str(snapshot.get("url") or "").strip()
    if snapshot_url and (not row_url or not looks_like_product_detail_url(row_url)):
        return snapshot_url
    return row_url or snapshot_url


def row_from_record(record: CrawlRecord) -> dict[str, object]:
    data = dict(record.data or {})
    data.setdefault("source_url", record.source_url)
    source_url = str(data.get("url") or record.source_url or "").strip()
    return {
        "source_record_id": record.id,
        "source_run_id": record.run_id,
        "source_url": source_url,
        "data": data,
    }


def source_product_payload(
    source: ProductIntelligenceSourceProduct,
) -> dict[str, object]:
    return {
        **dict(source.payload or {}),
        "title": source.title,
        "brand": source.brand,
        "normalized_brand": source.normalized_brand,
        "price": source.price,
        "currency": source.currency,
        "image_url": source.image_url,
        "url": source.source_url,
        "sku": source.sku,
        "mpn": source.mpn,
        "gtin": source.gtin,
    }

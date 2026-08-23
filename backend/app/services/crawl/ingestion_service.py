from __future__ import annotations

import json
import logging

from app.models.crawl_run import CrawlRun
from app.services.crawl.crud import create_crawl_run
from app.services.crawl.service import dispatch_run
from app.services.crawl.utils import parse_csv_urls
from app.services.config.runtime_settings import crawler_runtime_settings
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _parse_additional_fields(additional_fields: str) -> list[str]:
    return [field.strip() for field in additional_fields.split(",") if field.strip()]


def _parse_settings_json(settings_json: str) -> dict:
    try:
        parsed = json.loads(settings_json)
    except json.JSONDecodeError as exc:
        logger.debug(
            "_parse_settings_json failed to decode settings JSON",
            extra={"settings_json_length": len(settings_json)},
            exc_info=exc,
        )
        raise ValueError("_parse_settings_json failed to decode settings JSON") from exc
    if not isinstance(parsed, dict):
        logger.debug(
            "_parse_settings_json expected a JSON object",
            extra={"parsed_type": type(parsed).__name__},
        )
        raise ValueError(
            f"_parse_settings_json expected a JSON object, got {type(parsed).__name__}"
        )
    return parsed


def prepare_crawl_create_payload(payload: dict) -> dict:
    """Normalize crawl creation payloads before persistence."""
    data = dict(payload or {})
    if data.get("run_type") == "batch" and data.get("urls"):
        settings = dict(data.get("settings") or {})
        settings["urls"] = data.get("urls") or []
        data["settings"] = settings
    return data


def build_csv_crawl_payload(
    *,
    csv_content: str,
    surface: str,
    additional_fields: str = "",
    settings_json: str = "{}",
) -> tuple[dict, int]:
    urls = parse_csv_urls(csv_content)
    if not urls:
        raise ValueError("No valid URLs found in CSV")
    max_urls = int(crawler_runtime_settings.csv_url_max_count)
    if len(urls) > max_urls:
        raise ValueError(f"CSV contains more than the {max_urls}-URL limit")

    crawl_settings = _parse_settings_json(settings_json)
    crawl_settings["csv_content"] = csv_content
    crawl_settings["urls"] = urls
    data = {
        "run_type": "csv",
        "url": urls[0],
        "urls": urls,
        "surface": surface,
        "settings": crawl_settings,
        "additional_fields": _parse_additional_fields(additional_fields),
    }
    return data, len(urls)


async def create_crawl_run_from_payload(
    session: AsyncSession, user_id: int, payload: dict
) -> CrawlRun:
    data = prepare_crawl_create_payload(payload)
    run = await create_crawl_run(session, user_id, data)
    return await dispatch_run(session, run)


async def create_crawl_run_from_csv(
    session: AsyncSession,
    user_id: int,
    *,
    csv_content: str,
    surface: str,
    additional_fields: str = "",
    settings_json: str = "{}",
) -> tuple[CrawlRun, int]:
    data, url_count = build_csv_crawl_payload(
        csv_content=csv_content,
        surface=surface,
        additional_fields=additional_fields,
        settings_json=settings_json,
    )
    run = await create_crawl_run(session, user_id, data)
    run = await dispatch_run(session, run)
    return run, url_count

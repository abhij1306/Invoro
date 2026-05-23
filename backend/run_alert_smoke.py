r"""Run live product alert smoke checks against real ecommerce detail pages.

Usage:
    cd backend
    $env:PYTHONPATH='.'
    .\.venv\Scripts\python.exe run_alert_smoke.py --limit 1
    .\.venv\Scripts\python.exe run_alert_smoke.py --url https://web-scraping.dev/product/1
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models.user import User
from app.schemas.alert import AlertCreate, AlertStatus, AlertUpdate
from app.services.alert_service import (
    alert_history,
    alert_response,
    alert_run_delta_count,
    create_alert,
    delete_alert,
    test_alert,
    update_alert,
)
from app.services.config.monitor_settings import (
    MONITOR_STATUS_ACTIVE,
    MONITOR_STATUS_PAUSED,
)
from app.services.monitor_change_detection import (
    ensure_monitor_change_detection_registered,
)

DEFAULT_ALERT_SITES: list[dict[str, Any]] = [
    {
        "name": "web-scraping.dev product",
        "url": "https://web-scraping.dev/product/1",
        "target_fields": ["price", "availability"],
        "condition": "price < 100000",
    },
    {
        "name": "books.toscrape detail",
        "url": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
        "target_fields": ["price"],
        "condition": None,
    },
]
DEFAULT_REPORT_DIR = Path("artifacts/alert_smoke")


async def _smoke_user(session) -> User:
    stamp = datetime.now(UTC).strftime("%Y%m%d%H%M%S%f")
    user = User(
        email=f"alert-smoke-{stamp}@local.test",
        hashed_password=hash_password("alert-smoke"),
        role="admin",
        is_active=True,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def _run_one(site: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    result: dict[str, Any] = {
        "name": site["name"],
        "url": site["url"],
        "target_fields": site["target_fields"],
    }
    monitor_id: int | None = None
    async with SessionLocal() as session:
        user = await _smoke_user(session)
        try:
            monitor, initial_run_id = await create_alert(
                session,
                user=user,
                payload=AlertCreate(
                    url=site["url"],
                    target_fields=list(site["target_fields"]),
                    condition=site.get("condition"),
                    webhook_url="https://example.invalid/crawlerai-alert-smoke",
                    poll_interval_seconds=300,
                ),
            )
            monitor_id = int(monitor.id)
            initial = alert_response(monitor).model_dump(mode="json")

            paused = await update_alert(
                session,
                alert_id=monitor_id,
                user_id=int(user.id),
                payload=AlertUpdate(
                    status=cast(AlertStatus, MONITOR_STATUS_PAUSED),
                    poll_interval_seconds=60,
                ),
            )
            paused_status = str(paused.status)
            resumed = await update_alert(
                session,
                alert_id=monitor_id,
                user_id=int(user.id),
                payload=AlertUpdate(
                    status=cast(AlertStatus, MONITOR_STATUS_ACTIVE),
                    target_fields=list(site["target_fields"]),
                    condition=site.get("condition"),
                    webhook_url=None,
                ),
            )
            resumed_status = str(resumed.status)
            tested, test_run_id = await test_alert(
                session, alert_id=monitor_id, user_id=int(user.id)
            )
            history_items, history_total = await alert_history(
                session,
                alert_id=monitor_id,
                user_id=int(user.id),
                page=1,
                limit=20,
            )
            test_delta_count = await alert_run_delta_count(session, run_id=test_run_id)
            await delete_alert(session, alert_id=monitor_id, user_id=int(user.id))
            monitor_id = None

            current = alert_response(tested).model_dump(mode="json")
            result.update(
                {
                    "ok": bool(current["last_known_values"]),
                    "initial_run_id": initial_run_id,
                    "test_run_id": test_run_id,
                    "test_delta_count": test_delta_count,
                    "initial_snapshot": initial["last_known_values"],
                    "current_snapshot": current["last_known_values"],
                    "paused_status": paused_status,
                    "resumed_status": resumed_status,
                    "history_total": history_total,
                    "history_event_types": [item.event_type for item in history_items],
                }
            )
            if not result["ok"]:
                result["issue"] = "Alert poll completed but last_known_values was empty"
        except Exception as exc:  # pylint: disable=broad-exception-caught
            result["ok"] = False
            result["error"] = f"{type(exc).__name__}: {exc}"
            if monitor_id is not None:
                try:
                    await delete_alert(
                        session, alert_id=monitor_id, user_id=int(user.id)
                    )
                except Exception:  # pylint: disable=broad-exception-caught
                    pass
        finally:
            result["elapsed_s"] = round(time.perf_counter() - started, 2)
    return result


def _write_report(results: list[dict[str, Any]]) -> Path:
    DEFAULT_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = DEFAULT_REPORT_DIR / f"{stamp}__alert_smoke.json"
    payload = {
        "timestamp_utc": datetime.now(UTC).isoformat(),
        "summary": {
            "ok": sum(1 for row in results if row.get("ok")),
            "failed": sum(1 for row in results if not row.get("ok")),
            "total": len(results),
        },
        "results": results,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


async def main(argv: list[str]) -> int:
    ensure_monitor_change_detection_registered()
    parser = argparse.ArgumentParser(description="Run live alert smoke checks.")
    parser.add_argument(
        "--url", action="append", default=[], help="Explicit product detail URL."
    )
    parser.add_argument("--limit", type=int, default=None, help="Optional site limit.")
    args = parser.parse_args(argv)

    sites = (
        [
            {
                "name": f"explicit-{index}",
                "url": url,
                "target_fields": ["price", "availability"],
                "condition": None,
            }
            for index, url in enumerate(args.url, start=1)
        ]
        if args.url
        else list(DEFAULT_ALERT_SITES)
    )
    if args.limit is not None:
        sites = sites[: args.limit]

    results: list[dict[str, Any]] = []
    for index, site in enumerate(sites, start=1):
        print(f"[{index}/{len(sites)}] {site['url']}")
        row = await _run_one(site)
        results.append(row)
        print(json.dumps(row, indent=2))

    report_path = _write_report(results)
    summary = {
        "ok": sum(1 for row in results if row.get("ok")),
        "failed": sum(1 for row in results if not row.get("ok")),
        "total": len(results),
        "report_path": str(report_path),
    }
    print(json.dumps({"summary": summary}, indent=2))
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1:])))

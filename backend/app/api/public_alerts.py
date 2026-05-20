from __future__ import annotations

from time import perf_counter
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db
from app.core.public_auth import get_public_api_user
from app.models.user import User
from app.schemas.alert import AlertCreate, AlertUpdate
from app.services.alert_service import (
    create_alert,
    delete_alert,
    get_alert,
    list_alerts,
    test_alert,
    update_alert,
    alert_history,
    alert_response,
)

router = APIRouter(prefix="/api/v1/alerts", tags=["public-alerts"])


def _envelope(data: Any, request: Request, started_at: float) -> dict[str, Any]:
    return {
        "status": "ok",
        "data": data,
        "meta": {
            "request_id": request.headers.get("x-request-id", ""),
            "duration_ms": int((perf_counter() - started_at) * 1000),
        },
    }


def _error(code: str, message: str, request: Request) -> dict[str, Any]:
    return {
        "status": "error",
        "error": {"code": code, "message": message, "details": {}},
        "meta": {"request_id": request.headers.get("x-request-id", "")},
    }


@router.post("", status_code=status.HTTP_201_CREATED)
async def public_alert_create(
    payload: AlertCreate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_public_api_user)],
) -> dict[str, Any]:
    started_at = perf_counter()
    try:
        monitor, _ = await create_alert(session, user=user, payload=payload)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=_error("ALERT_CREATE_FAILED", str(exc), request),
        ) from exc
    return _envelope(alert_response(monitor).model_dump(mode="json"), request, started_at)


@router.get("")
async def public_alert_list(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_public_api_user)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> dict[str, Any]:
    started_at = perf_counter()
    monitors = await list_alerts(session, user_id=int(user.id), status=status_filter)
    data = [alert_response(monitor).model_dump(mode="json") for monitor in monitors]
    return _envelope(data, request, started_at)


@router.get("/{alert_id}")
async def public_alert_get(
    alert_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_public_api_user)],
) -> dict[str, Any]:
    started_at = perf_counter()
    try:
        monitor = await get_alert(session, alert_id, user_id=int(user.id))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=_error("ALERT_NOT_FOUND", str(exc), request)) from exc
    return _envelope(alert_response(monitor).model_dump(mode="json"), request, started_at)


@router.patch("/{alert_id}")
async def public_alert_patch(
    alert_id: int,
    payload: AlertUpdate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_public_api_user)],
) -> dict[str, Any]:
    started_at = perf_counter()
    try:
        monitor = await update_alert(session, alert_id=alert_id, user_id=int(user.id), payload=payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=_error("ALERT_NOT_FOUND", str(exc), request)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=_error("ALERT_UPDATE_FAILED", str(exc), request)) from exc
    return _envelope(alert_response(monitor).model_dump(mode="json"), request, started_at)


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def public_alert_delete(
    alert_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_public_api_user)],
) -> Response:
    try:
        await delete_alert(session, alert_id=alert_id, user_id=int(user.id))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=_error("ALERT_NOT_FOUND", str(exc), request)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{alert_id}/history")
async def public_alert_history(
    alert_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_public_api_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, Any]:
    started_at = perf_counter()
    try:
        items, total = await alert_history(
            session,
            alert_id=alert_id,
            user_id=int(user.id),
            page=page,
            limit=page_size,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=_error("ALERT_NOT_FOUND", str(exc), request)) from exc
    return _envelope(
        {
            "items": [item.model_dump(mode="json") for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        request,
        started_at,
    )


@router.post("/{alert_id}/test")
async def public_alert_test(
    alert_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_public_api_user)],
) -> dict[str, Any]:
    started_at = perf_counter()
    try:
        monitor, run_id = await test_alert(session, alert_id=alert_id, user_id=int(user.id))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=_error("ALERT_NOT_FOUND", str(exc), request)) from exc
    return _envelope(
        {
            "alert": alert_response(monitor).model_dump(mode="json"),
            "run_id": run_id,
            "current_snapshot": dict(monitor.last_known_values or {}),
            "delta_count": 0,
        },
        request,
        started_at,
    )

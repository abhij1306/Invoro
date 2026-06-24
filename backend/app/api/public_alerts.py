from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.public.common import PublicApiError, public_success
from app.core.dependencies import get_db
from app.core.public_auth import get_public_api_user
from app.models.user import User
from app.schemas.alert import AlertCreate, AlertUpdate
from app.services.alert_service import (
    alert_run_delta_count,
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


@router.post("", status_code=status.HTTP_201_CREATED)
async def public_alert_create(
    payload: AlertCreate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_public_api_user)],
) -> dict[str, Any]:
    try:
        monitor, _ = await create_alert(session, user=user, payload=payload)
    except ValueError as exc:
        raise PublicApiError(
            "ALERT_CREATE_FAILED",
            str(exc),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        ) from exc
    return public_success(alert_response(monitor).model_dump(mode="json"), request)


@router.get("")
async def public_alert_list(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_public_api_user)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> dict[str, Any]:
    monitors = await list_alerts(session, user_id=int(user.id), status=status_filter)
    data = [alert_response(monitor).model_dump(mode="json") for monitor in monitors]
    return public_success(data, request)


@router.get("/{alert_id}")
async def public_alert_get(
    alert_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_public_api_user)],
) -> dict[str, Any]:
    try:
        monitor = await get_alert(session, alert_id, user_id=int(user.id))
    except LookupError as exc:
        raise PublicApiError(
            "ALERT_NOT_FOUND",
            str(exc),
            status_code=status.HTTP_404_NOT_FOUND,
        ) from exc
    return public_success(alert_response(monitor).model_dump(mode="json"), request)


@router.patch("/{alert_id}")
async def public_alert_patch(
    alert_id: int,
    payload: AlertUpdate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_public_api_user)],
) -> dict[str, Any]:
    try:
        monitor = await update_alert(session, alert_id=alert_id, user_id=int(user.id), payload=payload)
    except LookupError as exc:
        raise PublicApiError(
            "ALERT_NOT_FOUND",
            str(exc),
            status_code=status.HTTP_404_NOT_FOUND,
        ) from exc
    except ValueError as exc:
        raise PublicApiError(
            "ALERT_UPDATE_FAILED",
            str(exc),
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        ) from exc
    return public_success(alert_response(monitor).model_dump(mode="json"), request)


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
        raise PublicApiError(
            "ALERT_NOT_FOUND",
            str(exc),
            status_code=status.HTTP_404_NOT_FOUND,
        ) from exc
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
    try:
        items, total = await alert_history(
            session,
            alert_id=alert_id,
            user_id=int(user.id),
            page=page,
            limit=page_size,
        )
    except LookupError as exc:
        raise PublicApiError(
            "ALERT_NOT_FOUND",
            str(exc),
            status_code=status.HTTP_404_NOT_FOUND,
        ) from exc
    return public_success(
        {
            "items": [item.model_dump(mode="json") for item in items],
            "total": total,
            "page": page,
            "page_size": page_size,
        },
        request,
    )


@router.post("/{alert_id}/test")
async def public_alert_test(
    alert_id: int,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_public_api_user)],
) -> dict[str, Any]:
    try:
        monitor, run_id = await test_alert(session, alert_id=alert_id, user_id=int(user.id))
    except LookupError as exc:
        raise PublicApiError(
            "ALERT_NOT_FOUND",
            str(exc),
            status_code=status.HTTP_404_NOT_FOUND,
        ) from exc
    return public_success(
        {
            "alert": alert_response(monitor).model_dump(mode="json"),
            "run_id": run_id,
            "current_snapshot": dict(monitor.last_known_values or {}),
            "delta_count": await alert_run_delta_count(session, run_id=run_id),
        },
        request,
    )

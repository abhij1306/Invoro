from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.alert import (
    AlertCreate,
    AlertResponse,
    AlertTestResponse,
    AlertUpdate,
    WebhookDeliveryResponse,
)
from app.services.monitor_webhook_service import list_webhook_deliveries
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

router = APIRouter(prefix="/api/alerts", tags=["alerts"])


@router.post("", status_code=status.HTTP_201_CREATED)
async def alert_create(
    payload: AlertCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> AlertResponse:
    try:
        monitor, _run_id = await create_alert(session, user=user, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return alert_response(monitor)


@router.get("")
async def alert_list(
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    status_filter: Annotated[str | None, Query(alias="status")] = None,
) -> list[AlertResponse]:
    monitors = await list_alerts(session, user_id=int(user.id), status=status_filter)
    return [alert_response(monitor) for monitor in monitors]


@router.get("/{alert_id}")
async def alert_get(
    alert_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> AlertResponse:
    try:
        monitor = await get_alert(session, alert_id, user_id=int(user.id))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return alert_response(monitor)


@router.patch("/{alert_id}")
async def alert_patch(
    alert_id: int,
    payload: AlertUpdate,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> AlertResponse:
    try:
        monitor = await update_alert(
            session,
            alert_id=alert_id,
            user_id=int(user.id),
            payload=payload,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return alert_response(monitor)


@router.delete("/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def alert_delete(
    alert_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> Response:
    try:
        await delete_alert(session, alert_id=alert_id, user_id=int(user.id))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{alert_id}/history")
async def alert_history_route(
    alert_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=200)] = 50,
) -> dict[str, object]:
    try:
        items, total = await alert_history(
            session,
            alert_id=alert_id,
            user_id=int(user.id),
            page=page,
            limit=page_size,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/{alert_id}/test")
async def alert_test(
    alert_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> AlertTestResponse:
    try:
        monitor, run_id = await test_alert(session, alert_id=alert_id, user_id=int(user.id))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    return AlertTestResponse(
        alert=alert_response(monitor),
        run_id=run_id,
        current_snapshot=dict(monitor.last_known_values or {}),
        delta_count=await alert_run_delta_count(session, run_id=run_id),
    )


@router.get("/{alert_id}/deliveries")
async def alert_deliveries(
    alert_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[WebhookDeliveryResponse]:
    try:
        await get_alert(session, alert_id, user_id=int(user.id))
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    rows = await list_webhook_deliveries(session, monitor_id=alert_id)
    return [WebhookDeliveryResponse.model_validate(row, from_attributes=True) for row in rows]

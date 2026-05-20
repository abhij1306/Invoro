from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request

from app.api.public.common import PublicApiError
from app.core.public_auth import get_public_api_user
from app.models.user import User
from app.services.config.public_api import PUBLIC_API_ERROR_WORKER_REQUIRED

router = APIRouter(prefix="/api/v1/watches", tags=["public-watches"])


@router.api_route("", methods=["GET", "POST"])
@router.api_route("/{watch_id}", methods=["GET", "PATCH", "DELETE"])
@router.api_route("/{watch_id}/history", methods=["GET"])
@router.api_route("/{watch_id}/test", methods=["POST"])
async def public_watches_deferred(
    request: Request,
    user: Annotated[User, Depends(get_public_api_user)],
    watch_id: int | None = None,
) -> dict[str, Any]:
    del request, user, watch_id
    raise PublicApiError(
        PUBLIC_API_ERROR_WORKER_REQUIRED,
        "Public watch APIs require verified worker infrastructure and are deferred in public API v1.",
        status_code=501,
    )

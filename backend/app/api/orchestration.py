from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.orchestration import (
    OrchestrationProjectCreate,
    OrchestrationProjectResponse,
    OrchestrationPromoteRequest,
    OrchestrationPromoteResponse,
    OrchestrationStepRunResponse,
    OrchestrationTemplateResponse,
    OrchestrationWorkflowCreate,
    OrchestrationWorkflowResponse,
    PriceComparisonResponse,
)
from app.services import orchestration_service

router = APIRouter(prefix="/api/orchestration", tags=["orchestration"])


@router.post("/projects", status_code=status.HTTP_201_CREATED)
async def project_create(
    payload: OrchestrationProjectCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> OrchestrationProjectResponse:
    project = await orchestration_service.create_project(
        session,
        user=user,
        payload=payload.model_dump(),
    )
    return OrchestrationProjectResponse.model_validate(project, from_attributes=True)


@router.get("/projects")
async def project_list(
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[OrchestrationProjectResponse]:
    projects = await orchestration_service.list_projects(session, user=user)
    return [
        OrchestrationProjectResponse.model_validate(project, from_attributes=True)
        for project in projects
    ]


@router.get("/projects/{project_id}")
async def project_get(
    project_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> OrchestrationProjectResponse:
    try:
        project = await orchestration_service.get_project(
            session,
            project_id=project_id,
            user=user,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return OrchestrationProjectResponse.model_validate(project, from_attributes=True)


@router.get("/templates")
async def template_list() -> list[OrchestrationTemplateResponse]:
    return [OrchestrationTemplateResponse.model_validate(item) for item in orchestration_service.templates()]


@router.get("/templates/{template_id}")
async def template_get(template_id: str) -> OrchestrationTemplateResponse:
    try:
        item = orchestration_service.template(template_id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return OrchestrationTemplateResponse.model_validate(item)


@router.post("/workflows", status_code=status.HTTP_201_CREATED)
async def workflow_create(
    payload: OrchestrationWorkflowCreate,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> OrchestrationWorkflowResponse:
    try:
        workflow = await orchestration_service.create_workflow(
            session,
            user=user,
            payload=payload.model_dump(),
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return await _workflow_response(session, workflow)


@router.get("/workflows")
async def workflow_list(
    project_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> list[OrchestrationWorkflowResponse]:
    try:
        workflows = await orchestration_service.list_workflows(
            session,
            project_id=project_id,
            user=user,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return [await _workflow_response(session, workflow) for workflow in workflows]


@router.get("/workflows/{workflow_id}")
async def workflow_get(
    workflow_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> OrchestrationWorkflowResponse:
    try:
        workflow = await orchestration_service.get_workflow(
            session,
            workflow_id=workflow_id,
            user=user,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return await _workflow_response(session, workflow)


@router.get("/workflows/{workflow_id}/status")
async def workflow_status(
    workflow_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> OrchestrationWorkflowResponse:
    return await workflow_get(workflow_id, session, user)


@router.post("/workflows/{workflow_id}/promote")
async def workflow_promote(
    workflow_id: int,
    payload: OrchestrationPromoteRequest,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> OrchestrationPromoteResponse:
    try:
        workflow, monitor_id, url_count, tracked_fields = await orchestration_service.promote_workflow_to_monitor(
            session,
            workflow_id=workflow_id,
            user=user,
            payload=payload.model_dump(),
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return OrchestrationPromoteResponse(
        workflow_id=workflow.id,
        monitor_id=monitor_id,
        url_count=url_count,
        tracked_fields=tracked_fields,
    )


@router.get("/workflows/{workflow_id}/results/price-comparison")
async def workflow_price_comparison(
    workflow_id: int,
    session: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[User, Depends(get_current_user)],
) -> PriceComparisonResponse:
    try:
        payload = await orchestration_service.price_comparison(
            session,
            workflow_id=workflow_id,
            user=user,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return PriceComparisonResponse.model_validate(payload)


async def _workflow_response(
    session: AsyncSession,
    workflow,
) -> OrchestrationWorkflowResponse:
    steps = await orchestration_service.workflow_steps(session, workflow.id)
    response = OrchestrationWorkflowResponse.model_validate(workflow, from_attributes=True)
    response.steps = [
        OrchestrationStepRunResponse.model_validate(step, from_attributes=True)
        for step in steps
    ]
    return response

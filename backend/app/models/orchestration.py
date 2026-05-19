from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.crawl_run import (
    CASCADE,
    CRAWL_RUN_FK,
    SET_NULL,
    USERS_FK,
    UpdatedAtMixin,
)
from app.models.monitor import MONITOR_JOB_FK

PROJECT_FK = "orchestration_projects.id"
WORKFLOW_FK = "orchestration_workflow_runs.id"


class OrchestrationProject(UpdatedAtMixin, Base):
    __tablename__ = "orchestration_projects"
    __table_args__ = (
        Index("ix_orchestration_projects_user_archived", "user_id", "archived"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey(USERS_FK, ondelete=SET_NULL), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text, default="")
    competitors: Mapped[list] = mapped_column(JSONB, default=list)
    category: Mapped[str] = mapped_column(String(160), default="")
    tracked_fields: Mapped[list] = mapped_column(JSONB, default=list)
    archived: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


class OrchestrationWorkflowRun(UpdatedAtMixin, Base):
    __tablename__ = "orchestration_workflow_runs"
    __table_args__ = (
        Index("ix_orchestration_workflow_runs_project_created", "project_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey(USERS_FK, ondelete=SET_NULL), nullable=True, index=True
    )
    project_id: Mapped[int] = mapped_column(
        ForeignKey(PROJECT_FK, ondelete=CASCADE), index=True
    )
    template_id: Mapped[str] = mapped_column(String(80), index=True)
    template_version: Mapped[str] = mapped_column(String(24))
    label: Mapped[str] = mapped_column(String(180))
    status: Mapped[str] = mapped_column(String(32), default="queued", index=True)
    intent_inputs: Mapped[dict] = mapped_column(JSONB, default=dict)
    advanced_overrides: Mapped[dict] = mapped_column(JSONB, default=dict)
    pipeline_config: Mapped[dict] = mapped_column(JSONB, default=dict)
    summary: Mapped[dict] = mapped_column(JSONB, default=dict)
    monitor_id: Mapped[int | None] = mapped_column(
        ForeignKey(MONITOR_JOB_FK, ondelete=SET_NULL), nullable=True, index=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, default=None
    )


class OrchestrationStepRun(UpdatedAtMixin, Base):
    __tablename__ = "orchestration_step_runs"
    __table_args__ = (
        Index("ix_orchestration_steps_workflow_step", "workflow_id", "step_id", unique=True),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    workflow_id: Mapped[int] = mapped_column(
        ForeignKey(WORKFLOW_FK, ondelete=CASCADE), index=True
    )
    step_id: Mapped[str] = mapped_column(String(80))
    step_type: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(32), default="pending", index=True)
    run_id: Mapped[int | None] = mapped_column(
        ForeignKey(CRAWL_RUN_FK, ondelete=SET_NULL), nullable=True, index=True
    )
    inputs: Mapped[dict] = mapped_column(JSONB, default=dict)
    outputs: Mapped[dict] = mapped_column(JSONB, default=dict)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

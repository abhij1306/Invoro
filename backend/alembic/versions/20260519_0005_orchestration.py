"""add orchestration tables

Revision ID: 20260519_0005
Revises: 20260519_0004
Create Date: 2026-05-19 00:05:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260519_0005"
down_revision = "20260519_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "orchestration_projects",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("competitors", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("category", sa.String(length=160), nullable=False),
        sa.Column("tracked_fields", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("archived", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_orchestration_projects_user_id", "orchestration_projects", ["user_id"])
    op.create_index("ix_orchestration_projects_archived", "orchestration_projects", ["archived"])
    op.create_index(
        "ix_orchestration_projects_user_archived",
        "orchestration_projects",
        ["user_id", "archived"],
    )

    op.create_table(
        "orchestration_workflow_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("project_id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.String(length=80), nullable=False),
        sa.Column("template_version", sa.String(length=24), nullable=False),
        sa.Column("label", sa.String(length=180), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("intent_inputs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("advanced_overrides", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("pipeline_config", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("monitor_id", sa.Integer(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["monitor_id"], ["monitor_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["orchestration_projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_orchestration_workflow_runs_user_id", "orchestration_workflow_runs", ["user_id"])
    op.create_index("ix_orchestration_workflow_runs_project_id", "orchestration_workflow_runs", ["project_id"])
    op.create_index("ix_orchestration_workflow_runs_template_id", "orchestration_workflow_runs", ["template_id"])
    op.create_index("ix_orchestration_workflow_runs_status", "orchestration_workflow_runs", ["status"])
    op.create_index("ix_orchestration_workflow_runs_monitor_id", "orchestration_workflow_runs", ["monitor_id"])
    op.create_index(
        "ix_orchestration_workflow_runs_project_created",
        "orchestration_workflow_runs",
        ["project_id", "created_at"],
    )

    op.create_table(
        "orchestration_step_runs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("step_id", sa.String(length=80), nullable=False),
        sa.Column("step_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=True),
        sa.Column("inputs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("outputs", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["crawl_runs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workflow_id"], ["orchestration_workflow_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_orchestration_step_runs_workflow_id", "orchestration_step_runs", ["workflow_id"])
    op.create_index("ix_orchestration_step_runs_status", "orchestration_step_runs", ["status"])
    op.create_index("ix_orchestration_step_runs_run_id", "orchestration_step_runs", ["run_id"])
    op.create_index(
        "ix_orchestration_steps_workflow_step",
        "orchestration_step_runs",
        ["workflow_id", "step_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_orchestration_steps_workflow_step", table_name="orchestration_step_runs")
    op.drop_index("ix_orchestration_step_runs_run_id", table_name="orchestration_step_runs")
    op.drop_index("ix_orchestration_step_runs_status", table_name="orchestration_step_runs")
    op.drop_index("ix_orchestration_step_runs_workflow_id", table_name="orchestration_step_runs")
    op.drop_table("orchestration_step_runs")
    op.drop_index("ix_orchestration_workflow_runs_project_created", table_name="orchestration_workflow_runs")
    op.drop_index("ix_orchestration_workflow_runs_monitor_id", table_name="orchestration_workflow_runs")
    op.drop_index("ix_orchestration_workflow_runs_status", table_name="orchestration_workflow_runs")
    op.drop_index("ix_orchestration_workflow_runs_template_id", table_name="orchestration_workflow_runs")
    op.drop_index("ix_orchestration_workflow_runs_project_id", table_name="orchestration_workflow_runs")
    op.drop_index("ix_orchestration_workflow_runs_user_id", table_name="orchestration_workflow_runs")
    op.drop_table("orchestration_workflow_runs")
    op.drop_index("ix_orchestration_projects_user_archived", table_name="orchestration_projects")
    op.drop_index("ix_orchestration_projects_archived", table_name="orchestration_projects")
    op.drop_index("ix_orchestration_projects_user_id", table_name="orchestration_projects")
    op.drop_table("orchestration_projects")

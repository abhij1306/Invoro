"""Drop legacy projects/workflow tables.

Revision ID: 0007
Revises: 0006
Create Date: 2026-05-28
"""

from alembic import op

revision = "20260528_0007"
down_revision = "20260520_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("orchestration_step_runs")
    op.drop_table("orchestration_workflow_runs")
    op.drop_table("orchestration_projects")


def downgrade() -> None:
    # Legacy projects/workflow tables removed permanently; no downgrade path.
    pass

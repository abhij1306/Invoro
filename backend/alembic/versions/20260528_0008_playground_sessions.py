"""Add playground_sessions table.

Revision ID: 20260528_0008
Revises: 20260528_0007
Create Date: 2026-05-28
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260528_0008"
down_revision = "20260528_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "playground_sessions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False, index=True),
        sa.Column("input_url", sa.Text(), nullable=False),
        sa.Column("state", sa.String(32), nullable=False, server_default="created"),
        sa.Column("step_data", postgresql.JSONB(), nullable=False, server_default="{}"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("playground_sessions")

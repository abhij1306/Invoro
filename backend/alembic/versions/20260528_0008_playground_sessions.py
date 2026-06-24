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
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION set_playground_sessions_updated_at()
        RETURNS trigger AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_playground_sessions_updated_at
        BEFORE UPDATE ON playground_sessions
        FOR EACH ROW
        EXECUTE FUNCTION set_playground_sessions_updated_at()
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_playground_sessions_updated_at ON playground_sessions")
    op.execute("DROP FUNCTION IF EXISTS set_playground_sessions_updated_at()")
    op.drop_table("playground_sessions")

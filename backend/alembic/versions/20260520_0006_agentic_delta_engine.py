"""add agentic delta engine watch fields

Revision ID: 20260520_0006
Revises: 20260519_0005
Create Date: 2026-05-20 00:06:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260520_0006"
down_revision = "20260519_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("monitor_jobs", sa.Column("condition", sa.Text(), nullable=True))
    op.add_column("monitor_jobs", sa.Column("webhook_url", sa.Text(), nullable=True))
    op.add_column("monitor_jobs", sa.Column("poll_interval_seconds", sa.Integer(), nullable=True))
    op.add_column(
        "monitor_jobs",
        sa.Column(
            "last_known_values",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column("monitor_jobs", sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column(
        "monitor_jobs",
        sa.Column("consecutive_failure_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("monitor_jobs", sa.Column("last_error", sa.Text(), nullable=True))
    op.add_column("monitor_jobs", sa.Column("last_crawl_method", sa.String(length=32), nullable=True))
    op.add_column(
        "monitor_events",
        sa.Column("condition_met", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_index("ix_monitor_events_condition_met", "monitor_events", ["condition_met"])

    op.create_table(
        "monitor_webhook_deliveries",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("monitor_id", sa.Integer(), nullable=False),
        sa.Column("event_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attempt", sa.Integer(), nullable=False),
        sa.Column("response_code", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("payload_preview", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["monitor_events.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["monitor_id"], ["monitor_jobs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_monitor_webhook_deliveries_monitor_id", "monitor_webhook_deliveries", ["monitor_id"])
    op.create_index("ix_monitor_webhook_deliveries_event_id", "monitor_webhook_deliveries", ["event_id"])
    op.create_index("ix_monitor_webhook_deliveries_status", "monitor_webhook_deliveries", ["status"])
    op.create_index(
        "ix_monitor_webhook_deliveries_monitor_created",
        "monitor_webhook_deliveries",
        ["monitor_id", "created_at"],
    )

    op.create_table(
        "api_keys",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("key_prefix", sa.String(length=16), nullable=False),
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("key_hash"),
    )
    op.create_index("ix_api_keys_user_id", "api_keys", ["user_id"])
    op.create_index("ix_api_keys_key_prefix", "api_keys", ["key_prefix"])
    op.create_index("ix_api_keys_is_active", "api_keys", ["is_active"])

    op.alter_column("monitor_jobs", "last_known_values", server_default=None)
    op.alter_column("monitor_jobs", "consecutive_failure_count", server_default=None)
    op.alter_column("monitor_events", "condition_met", server_default=None)


def downgrade() -> None:
    op.drop_index("ix_api_keys_is_active", table_name="api_keys")
    op.drop_index("ix_api_keys_key_prefix", table_name="api_keys")
    op.drop_index("ix_api_keys_user_id", table_name="api_keys")
    op.drop_table("api_keys")
    op.drop_index("ix_monitor_webhook_deliveries_monitor_created", table_name="monitor_webhook_deliveries")
    op.drop_index("ix_monitor_webhook_deliveries_status", table_name="monitor_webhook_deliveries")
    op.drop_index("ix_monitor_webhook_deliveries_event_id", table_name="monitor_webhook_deliveries")
    op.drop_index("ix_monitor_webhook_deliveries_monitor_id", table_name="monitor_webhook_deliveries")
    op.drop_table("monitor_webhook_deliveries")
    op.drop_index("ix_monitor_events_condition_met", table_name="monitor_events")
    op.drop_column("monitor_events", "condition_met")
    op.drop_column("monitor_jobs", "last_crawl_method")
    op.drop_column("monitor_jobs", "last_error")
    op.drop_column("monitor_jobs", "consecutive_failure_count")
    op.drop_column("monitor_jobs", "last_checked_at")
    op.drop_column("monitor_jobs", "last_known_values")
    op.drop_column("monitor_jobs", "poll_interval_seconds")
    op.drop_column("monitor_jobs", "webhook_url")
    op.drop_column("monitor_jobs", "condition")

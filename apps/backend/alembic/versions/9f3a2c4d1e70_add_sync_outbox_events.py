"""Add the minimal local-first outbox for optional Supabase project sync.

Revision ID: 9f3a2c4d1e70
Revises: 308955bf55b0
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "9f3a2c4d1e70"
down_revision = "308955bf55b0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sync_outbox_events",
        sa.Column("domain", sa.String(32), nullable=False),
        sa.Column("record_type", sa.String(32), nullable=False),
        sa.Column("record_id", sa.UUID(), nullable=False),
        sa.Column("owner_id", sa.UUID(), nullable=False),
        sa.Column("operation", sa.String(16), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempt_count", sa.Integer(), nullable=False),
        sa.Column("last_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_sync_outbox_pending", "sync_outbox_events", ["status", "next_retry_at", "created_at"])
    op.create_index("ix_sync_outbox_record", "sync_outbox_events", ["domain", "record_type", "record_id"])


def downgrade() -> None:
    op.drop_index("ix_sync_outbox_record", table_name="sync_outbox_events")
    op.drop_index("ix_sync_outbox_pending", table_name="sync_outbox_events")
    op.drop_table("sync_outbox_events")

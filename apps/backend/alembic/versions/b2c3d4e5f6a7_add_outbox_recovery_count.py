"""Add recovery_count to sync_outbox_events (dead-letter recovery).

Dead-lettered outbox events are re-armed hourly up to 3 recoveries before
giving up permanently (decisions.md #43). recovery_count tracks how many
times an event was re-armed from dead_letter back to pending; existing rows
start with 0, so currently dead-lettered events automatically become
eligible for recovery after this migration runs.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "sync_outbox_events",
        sa.Column("recovery_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("sync_outbox_events", "recovery_count")

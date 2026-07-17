"""Add timestamps and duration to automation_executions.

Revision ID: 20260717_0004
Revises: 20260717_0003
Create Date: 2026-07-17
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260717_0004"
down_revision: str | None = "20260717_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "automation_executions",
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "automation_executions",
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "automation_executions",
        sa.Column("duration_ms", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("automation_executions", "duration_ms")
    op.drop_column("automation_executions", "finished_at")
    op.drop_column("automation_executions", "started_at")

"""Add planning fields to goals and executive_tasks (Goal Engine).

Adds priority, deadline, and completion tracking to goals and their tasks,
plus task dependencies. All new columns are nullable/backward-compatible so
existing rows and the running executive worker keep working untouched.

Revision ID: a1b2c3d4e5f6
Revises: 9f3a2c4d1e70
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "a1b2c3d4e5f6"
down_revision = "9f3a2c4d1e70"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Goals: planning + completion fields.
    op.add_column("goals", sa.Column("priority", sa.Integer(), nullable=True))
    op.add_column("goals", sa.Column("deadline", sa.DateTime(timezone=True), nullable=True))
    op.add_column("goals", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_goals_user_status", "goals", ["user_id", "status"])
    op.create_index("ix_goals_user_deadline", "goals", ["user_id", "deadline"])

    # Executive tasks: planning fields, dependencies, completion tracking.
    op.add_column("executive_tasks", sa.Column("priority", sa.Integer(), nullable=True))
    op.add_column("executive_tasks", sa.Column("deadline", sa.DateTime(timezone=True), nullable=True))
    op.add_column("executive_tasks", sa.Column("depends_on", sa.JSON(), nullable=True))
    op.add_column("executive_tasks", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_executive_tasks_deadline", "executive_tasks", ["deadline"])


def downgrade() -> None:
    op.drop_index("ix_executive_tasks_deadline", table_name="executive_tasks")
    op.drop_column("executive_tasks", "completed_at")
    op.drop_column("executive_tasks", "depends_on")
    op.drop_column("executive_tasks", "deadline")
    op.drop_column("executive_tasks", "priority")
    op.drop_index("ix_goals_user_deadline", table_name="goals")
    op.drop_index("ix_goals_user_status", table_name="goals")
    op.drop_column("goals", "completed_at")
    op.drop_column("goals", "deadline")
    op.drop_column("goals", "priority")

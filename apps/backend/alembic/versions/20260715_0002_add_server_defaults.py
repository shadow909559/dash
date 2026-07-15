"""Add server_default to timestamp columns

Revision ID: 20260715_0002
Revises: 064dcb41eb02
Create Date: 2026-07-15 07:05:00
"""
from collections.abc import Sequence

from alembic import op

revision: str = "20260715_0002"
down_revision: str | None = "064dcb41eb02"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Map table -> columns that have TimestampMixin
TIMESTAMP_COLUMNS = {
    "users": ["created_at", "updated_at"],
    "refresh_tokens": ["created_at"],  # no updated_at in this model
    "api_keys": ["created_at", "updated_at"],
    "conversations": ["created_at", "updated_at"],
    "devices": ["created_at", "updated_at"],
    "memories": ["created_at", "updated_at"],
    "messages": ["created_at", "updated_at"],
    "notifications": ["created_at", "updated_at"],
    "plugins": ["created_at", "updated_at"],
    "sessions": ["created_at", "updated_at"],
    "tasks": ["created_at", "updated_at"],
}


def upgrade() -> None:
    for table, columns in TIMESTAMP_COLUMNS.items():
        for col in columns:
            op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} SET DEFAULT now()")


def downgrade() -> None:
    for table, columns in TIMESTAMP_COLUMNS.items():
        for col in columns:
            op.execute(f"ALTER TABLE {table} ALTER COLUMN {col} DROP DEFAULT")
"""Add is_archived column to conversations table (fix for missing column).

This migration exists because the application model and queries expect
`conversations.is_archived`, but the database schema in some environments
does not include it.

Revision ID: 20260716_0004
Revises: 20260716_0003_conversation_memory
Create Date: 2026-07-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260716_0004"
down_revision: str | None = "20260716_0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add column if it does not exist.
    # Using a DO block for idempotency across partially migrated DBs.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'conversations'
                  AND column_name = 'is_archived'
            ) THEN
                ALTER TABLE conversations
                ADD COLUMN is_archived BOOLEAN NOT NULL DEFAULT FALSE;
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'conversations'
                  AND column_name = 'is_archived'
            ) THEN
                ALTER TABLE conversations DROP COLUMN is_archived;
            END IF;
        END $$;
        """
    )


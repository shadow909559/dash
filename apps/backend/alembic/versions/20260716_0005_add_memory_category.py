"""Add category column to memories.

Milestone 1 requirement: persistent user memory with categories.

Revision ID: 20260716_0005
Revises: 20260716_0004
Create Date: 2026-07-16
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260716_0005"
down_revision: str | None = "20260716_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Idempotent: safe for partially migrated DBs.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.columns
                WHERE table_name = 'memories'
                  AND column_name = 'category'
            ) THEN
                ALTER TABLE memories
                ADD COLUMN category VARCHAR(64);
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
                WHERE table_name = 'memories'
                  AND column_name = 'category'
            ) THEN
                ALTER TABLE memories DROP COLUMN category;
            END IF;
        END $$;
        """
    )


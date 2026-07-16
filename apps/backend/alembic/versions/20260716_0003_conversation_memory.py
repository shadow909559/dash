"""Enhance conversation/message models and add conversation_summaries.

Revision ID: 20260716_0003
Revises: 20260715_0002_add_server_defaults
Create Date: 2026-07-16 22:00:00.000000

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "20260716_0003"
down_revision: str | None = "20260715_0002_add_server_defaults"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add new columns and tables for conversation management."""

    # ── conversations ────────────────────────────────────────────
    op.add_column(
        "conversations",
        sa.Column("is_pinned", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "conversations",
        sa.Column("is_favorited", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "conversations",
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "conversations",
        sa.Column("summary", sa.Text(), nullable=True),
    )
    op.add_column(
        "conversations",
        sa.Column("summary_updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "conversations",
        sa.Column("message_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "conversations",
        sa.Column("token_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )
    op.add_column(
        "conversations",
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "conversations",
        sa.Column("model", sa.String(length=128), nullable=True),
    )

    # Indexes for pinned and archived queries
    op.create_index(
        "ix_conversations_user_id_pinned",
        "conversations",
        ["user_id", "is_pinned"],
    )
    op.create_index(
        "ix_conversations_user_id_archived",
        "conversations",
        ["user_id", "is_archived"],
    )

    # ── messages ─────────────────────────────────────────────────
    op.add_column(
        "messages",
        sa.Column("token_count", sa.Integer(), nullable=True),
    )
    op.add_column(
        "messages",
        sa.Column("model", sa.Text(), nullable=True),
    )

    # ── conversation_summaries ────────────────────────────────────
    op.create_table(
        "conversation_summaries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("conversation_id", sa.UUID(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("message_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_summaries_conversation_id",
        "conversation_summaries",
        ["conversation_id"],
    )


def downgrade() -> None:
    """Revert schema changes."""
    op.drop_table("conversation_summaries")
    op.drop_column("messages", "model")
    op.drop_column("messages", "token_count")
    op.drop_index("ix_conversations_user_id_archived", table_name="conversations")
    op.drop_index("ix_conversations_user_id_pinned", table_name="conversations")
    op.drop_column("conversations", "model")
    op.drop_column("conversations", "last_message_at")
    op.drop_column("conversations", "token_count")
    op.drop_column("conversations", "message_count")
    op.drop_column("conversations", "summary_updated_at")
    op.drop_column("conversations", "summary")
    op.drop_column("conversations", "is_archived")
    op.drop_column("conversations", "is_favorited")
    op.drop_column("conversations", "is_pinned")
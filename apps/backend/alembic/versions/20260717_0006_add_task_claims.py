"""Add task claim and heartbeat fields for durable worker coordination

Revision ID: 20260717_0006_add_task_claims
Revises: 20260717_0005_add_executive_fks
Create Date: 2026-07-17 07:45:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '20260717_0006_add_task_claims'
down_revision = '20260717_0005_add_executive_fks'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('tasks', sa.Column('claimed_by', postgresql.UUID(as_uuid=True), nullable=True))
    op.add_column('tasks', sa.Column('claimed_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('tasks', sa.Column('last_heartbeat', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_tasks_claimed_by', 'tasks', ['claimed_by'])
    op.create_index('ix_tasks_last_heartbeat', 'tasks', ['last_heartbeat'])


def downgrade() -> None:
    op.drop_index('ix_tasks_last_heartbeat', table_name='tasks')
    op.drop_index('ix_tasks_claimed_by', table_name='tasks')
    op.drop_column('tasks', 'last_heartbeat')
    op.drop_column('tasks', 'claimed_at')
    op.drop_column('tasks', 'claimed_by')

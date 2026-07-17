"""Add foreign key constraints to executive tables

Revision ID: 20260717_0005_add_executive_fks
Revises: 20260717_0004_add_executive_tables
Create Date: 2026-07-17 07:40:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260717_0005_add_executive_fks'
down_revision = '20260717_0004_add_executive_tables'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add FK from tasks.goal_id -> goals.id
    op.create_foreign_key('fk_tasks_goal', 'tasks', 'goals', ['goal_id'], ['id'], ondelete='CASCADE')

    # Add FK from execution_history.task_id -> tasks.id
    op.create_foreign_key('fk_execution_history_task', 'execution_history', 'tasks', ['task_id'], ['id'], ondelete='CASCADE')

    # Add FK from approvals.user_id -> users.id (users table assumed existing)
    # If users table is in a different schema, adjust accordingly
    op.create_foreign_key('fk_approvals_user', 'approvals', 'users', ['user_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('fk_approvals_user', 'approvals', type_='foreignkey')
    op.drop_constraint('fk_execution_history_task', 'execution_history', type_='foreignkey')
    op.drop_constraint('fk_tasks_goal', 'tasks', type_='foreignkey')

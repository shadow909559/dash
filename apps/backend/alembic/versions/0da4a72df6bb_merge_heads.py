"""merge heads

Revision ID: 0da4a72df6bb
Revises: 111b1f187000, 20260716_0005
Create Date: 2026-07-17 03:41:27.915019

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa



# revision identifiers, used by Alembic.
revision: str = '0da4a72df6bb'
down_revision: Union[str, None] = ('111b1f187000', '20260716_0005')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass

"""${message}

Revision ID: ${up_revision}
Revises: ${', '.join(down_revision or [])}
Create Date: ${create_date}

"""

from __future__ import annotations

import sqlalchemy as sa
import typing as t

from alembic import op

# revision identifiers, used by Alembic.
revision: str = ${repr(up_revision)}
down_revision: t.Union[str, None] = ${repr(down_revision)}
branch_labels: t.Union[str, t.Sequence[str], None] = ${repr(branch_labels)}
depends_on: t.Union[str, t.Sequence[str], None] = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else 'pass'}


def downgrade() -> None:
    ${downgrades if downgrades else 'pass'}


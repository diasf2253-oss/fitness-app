"""add height_cm to settings

Revision ID: a7c3e9d1f2b4
Revises: 85c6951715d5
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a7c3e9d1f2b4'
down_revision: Union[str, None] = '85c6951715d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('settings') as batch:
        batch.add_column(sa.Column('height_cm', sa.Float(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('settings') as batch:
        batch.drop_column('height_cm')

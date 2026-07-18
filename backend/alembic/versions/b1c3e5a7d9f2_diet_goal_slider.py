"""Diet goal slider (workbook H1a): rename target_loss_kg_per_week to the
signed goal_kg_per_week (negative = cut, 0 = maintain, positive = bulk).
Existing values flip sign: a stored loss of 0.5 becomes a goal of -0.5.

Revision ID: b1c3e5a7d9f2
Revises: a7d2c9f1b3e5
Create Date: 2026-07-18
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'b1c3e5a7d9f2'
down_revision: Union[str, None] = 'a7d2c9f1b3e5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('settings') as batch:
        batch.alter_column(
            'target_loss_kg_per_week',
            new_column_name='goal_kg_per_week',
            existing_type=sa.Float(),
            existing_nullable=False,
        )
    op.execute('UPDATE settings SET goal_kg_per_week = -goal_kg_per_week')


def downgrade() -> None:
    op.execute('UPDATE settings SET goal_kg_per_week = -goal_kg_per_week')
    with op.batch_alter_table('settings') as batch:
        batch.alter_column(
            'goal_kg_per_week',
            new_column_name='target_loss_kg_per_week',
            existing_type=sa.Float(),
            existing_nullable=False,
        )

"""phase3_apple_health_ingest

Nutrition micronutrients (JSON column, canonical unit-suffixed keys) and
the last-ingest timestamp shown in Settings.

Revision ID: d6e3f1a4c8b7
Revises: b7a91c4e8d02
Create Date: 2026-06-10 16:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd6e3f1a4c8b7'
down_revision: Union[str, None] = 'b7a91c4e8d02'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('nutrition_day', schema=None) as batch_op:
        batch_op.add_column(sa.Column('micros', sa.JSON(), nullable=True))

    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('health_last_ingest', sa.DateTime(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.drop_column('health_last_ingest')

    with op.batch_alter_table('nutrition_day', schema=None) as batch_op:
        batch_op.drop_column('micros')

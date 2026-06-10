"""phase2_remove_yazio

YAZIO is cancelled: its data reaches Apple Health on the phone, and the
Apple Health ingest (Phase 3) is the single source for all health and
nutrition data. Drop the YAZIO sync-state columns from settings.

Revision ID: b7a91c4e8d02
Revises: 99b057afe1c1
Create Date: 2026-06-10 15:10:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b7a91c4e8d02'
down_revision: Union[str, None] = '99b057afe1c1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # batch mode: SQLite can't ALTER TABLE DROP COLUMN in place
    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.drop_column('yazio_last_sync')
        batch_op.drop_column('yazio_last_error')


def downgrade() -> None:
    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('yazio_last_sync', sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column('yazio_last_error', sa.Text(), nullable=True))

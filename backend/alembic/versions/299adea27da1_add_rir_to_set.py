"""add rir to set

Revision ID: 299adea27da1
Revises: 3244ad3b9f72
Create Date: 2026-09-08 15:37:12.116886

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '299adea27da1'
down_revision: Union[str, None] = '3244ad3b9f72'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable — existing sets simply have no RIR recorded. The UI replaced the
    # RPE input with RIR; the rpe column is kept for already-logged data.
    op.add_column("set", sa.Column("rir", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("set") as batch:
        batch.drop_column("rir")

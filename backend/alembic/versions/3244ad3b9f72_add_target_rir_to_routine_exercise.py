"""add target_rir to routine_exercise

Revision ID: 3244ad3b9f72
Revises: c4d5e6f7a8b9
Create Date: 2026-08-27 23:05:50.710381

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3244ad3b9f72'
down_revision: Union[str, None] = 'c4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable — existing routine exercises simply have no RIR target yet.
    # add_column is natively supported by SQLite, so no batch mode needed here.
    op.add_column(
        "routine_exercise",
        sa.Column("target_rir", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    # DROP COLUMN needs batch mode for older SQLite.
    with op.batch_alter_table("routine_exercise") as batch:
        batch.drop_column("target_rir")

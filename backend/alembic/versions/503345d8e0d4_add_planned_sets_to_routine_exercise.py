"""add planned_sets to routine_exercise

Revision ID: 503345d8e0d4
Revises: 87c1b655f1fb
Create Date: 2026-09-08 16:20:19.279299

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '503345d8e0d4'
down_revision: Union[str, None] = '87c1b655f1fb'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable — routines created before per-set planning simply have no plan;
    # the editor derives empty rows from target_sets for them.
    op.add_column("routine_exercise", sa.Column("planned_sets", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("routine_exercise") as batch:
        batch.drop_column("planned_sets")

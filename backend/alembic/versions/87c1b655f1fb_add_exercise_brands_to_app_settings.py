"""add exercise_brands to app_settings

Revision ID: 87c1b655f1fb
Revises: 299adea27da1
Create Date: 2026-09-08 15:44:19.687012

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '87c1b655f1fb'
down_revision: Union[str, None] = '299adea27da1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # {exercise_uuid: brand} per user. Nullable — treated as {} when unset.
    op.add_column("settings", sa.Column("exercise_brands", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("settings") as batch:
        batch.drop_column("exercise_brands")

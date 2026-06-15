"""phase8_plan_items

Trackable plan items (day / study / workout) — many rows per date, checkable,
drafted by the AI Coach or by hand. The first non-health, non-tracker daily
domain.

Revision ID: a1c9f0b3e264
Revises: f4b8d2e7a1c5
Create Date: 2026-06-15 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1c9f0b3e264'
down_revision: Union[str, None] = 'f4b8d2e7a1c5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'plan_item',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('start_time', sa.String(length=5), nullable=True),
        sa.Column('end_time', sa.String(length=5), nullable=True),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('category', sa.String(length=20), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('is_done', sa.Boolean(), nullable=False),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('plan_item', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_plan_item_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_plan_item_date'), ['date'], unique=False)


def downgrade() -> None:
    op.drop_table('plan_item')

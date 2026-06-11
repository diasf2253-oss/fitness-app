"""phase6_trackers

Generic tracker system: habits (with streaks), 1-5 scales (mood),
numbers (custom metrics), and text (journal). One log per tracker per
day, same date-keyed upsert pattern as the health tables.

Revision ID: f4b8d2e7a1c5
Revises: d6e3f1a4c8b7
Create Date: 2026-06-11 09:20:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4b8d2e7a1c5'
down_revision: Union[str, None] = 'd6e3f1a4c8b7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tracker',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('unit', sa.String(length=50), nullable=True),
        sa.Column('position', sa.Integer(), nullable=False),
        sa.Column('is_archived', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('tracker', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tracker_id'), ['id'], unique=False)

    op.create_table(
        'tracker_log',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('tracker_id', sa.Integer(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('value_num', sa.Float(), nullable=True),
        sa.Column('value_text', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['tracker_id'], ['tracker.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tracker_id', 'date', name='uq_tracker_date'),
    )
    with op.batch_alter_table('tracker_log', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_tracker_log_id'), ['id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tracker_log_tracker_id'), ['tracker_id'], unique=False)
        batch_op.create_index(batch_op.f('ix_tracker_log_date'), ['date'], unique=False)


def downgrade() -> None:
    op.drop_table('tracker_log')
    op.drop_table('tracker')

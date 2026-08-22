"""Phase 1-2 friends beta: add nullable user_id to every data table.

Nullable for now — a manual backfill (app/backfill_owner.py) attaches every
existing row to the seeded admin account between this migration and the
next, which then makes user_id NOT NULL and fixes up the per-user
uniqueness constraints. exercise.user_id stays nullable forever: NULL means
the shared/global seeded library, set only for a user's own custom exercise.

Revision ID: a2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-08-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Every table that becomes NOT NULL user_id after the backfill (migration
# c4d5e6f7a8b9). exercise is handled separately below (nullable forever).
_TABLES = [
    'routine', 'routine_exercise', 'session', 'session_exercise', 'set',
    'routine_note', 'plan_item', 'weight_log', 'steps_log', 'sleep_log',
    'nutrition_day', 'tracker', 'settings', 'streak_state', 'activity',
]


def upgrade() -> None:
    for table in _TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key(
                f'fk_{table}_user_id', 'users', ['user_id'], ['id'], ondelete='CASCADE'
            )
            batch_op.create_index(f'ix_{table}_user_id', ['user_id'])

    with op.batch_alter_table('exercise', schema=None) as batch_op:
        batch_op.add_column(sa.Column('user_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_exercise_user_id', 'users', ['user_id'], ['id'], ondelete='CASCADE'
        )
        batch_op.create_index('ix_exercise_user_id', ['user_id'])


def downgrade() -> None:
    with op.batch_alter_table('exercise', schema=None) as batch_op:
        batch_op.drop_index('ix_exercise_user_id')
        batch_op.drop_constraint('fk_exercise_user_id', type_='foreignkey')
        batch_op.drop_column('user_id')

    for table in reversed(_TABLES):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_index(f'ix_{table}_user_id')
            batch_op.drop_constraint(f'fk_{table}_user_id', type_='foreignkey')
            batch_op.drop_column('user_id')

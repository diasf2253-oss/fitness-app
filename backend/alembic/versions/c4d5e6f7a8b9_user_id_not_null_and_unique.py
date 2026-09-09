"""Phase 1-2 friends beta: make user_id NOT NULL, fix per-user uniqueness.

Run AFTER app/backfill_owner.py has attached every existing row to the
admin account (verify the printed row counts match first).

  - user_id becomes NOT NULL on all 15 tables from the previous migration
    (exercise.user_id stays nullable — the global library has none).
  - weight_log/steps_log/sleep_log/nutrition_day: the old bare unique(date)
    becomes unique(user_id, date) — two users logging the same date must
    no longer collide.
  - settings/streak_state: user_id becomes unique (one row per user,
    replacing the old hardcoded id=1 singleton convention).
  - tracker_log is untouched: it has no user_id column at all — it's
    scoped indirectly through tracker_id -> tracker.user_id (see
    routers/trackers.py's _get_tracker, which is always called first).

Revision ID: c4d5e6f7a8b9
Revises: a2b3c4d5e6f7
Create Date: 2026-08-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'c4d5e6f7a8b9'
down_revision: Union[str, None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_NOT_NULL_TABLES = [
    'routine', 'routine_exercise', 'session', 'session_exercise', 'set',
    'routine_note', 'plan_item', 'weight_log', 'steps_log', 'sleep_log',
    'nutrition_day', 'tracker', 'settings', 'streak_state', 'activity',
]

_DATE_UNIQUE_TABLES = ['weight_log', 'steps_log', 'sleep_log', 'nutrition_day']


def upgrade() -> None:
    for table in _NOT_NULL_TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column('user_id', existing_type=sa.Integer(), nullable=False)

    for table in _DATE_UNIQUE_TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_index(f'ix_{table}_date')  # old bare UNIQUE index on date alone
            batch_op.create_unique_constraint(f'uq_{table}_user_date', ['user_id', 'date'])
            batch_op.create_index(f'ix_{table}_date', ['date'])  # plain index, matches models.py

    for table in ('settings', 'streak_state'):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.create_unique_constraint(f'uq_{table}_user_id', ['user_id'])


def downgrade() -> None:
    for table in ('settings', 'streak_state'):
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_constraint(f'uq_{table}_user_id', type_='unique')

    for table in _DATE_UNIQUE_TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.drop_index(f'ix_{table}_date')
            batch_op.drop_constraint(f'uq_{table}_user_date', type_='unique')
            batch_op.create_index(f'ix_{table}_date', ['date'], unique=True)

    for table in _NOT_NULL_TABLES:
        with op.batch_alter_table(table, schema=None) as batch_op:
            batch_op.alter_column('user_id', existing_type=sa.Integer(), nullable=True)

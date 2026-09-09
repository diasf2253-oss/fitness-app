"""phase10_ranks

Rank ladder (ported from the redesign branch onto the local-first line):
  - exercise.primary_muscle_group (indexed), backfilled by auto-tagging each
    exercise from its name (falling back to the legacy primary_muscle).
  - settings.sex ('male' | 'female') — scales the strength references.
  - settings.rank_config (JSON) — per-user standard overrides; null ⇒ defaults.

Backfilled rows get updated_at bumped so devices syncing incrementally
(Phase 9) pull the new tags instead of missing them.

Revision ID: e9f2a4b6c8d0
Revises: c2d4e6f8a0b1
Create Date: 2026-07-11 22:45:00.000000

"""
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.muscles import suggest_muscle_group


# revision identifiers, used by Alembic.
revision: str = 'e9f2a4b6c8d0'
down_revision: Union[str, None] = 'c2d4e6f8a0b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('exercise', schema=None) as batch_op:
        batch_op.add_column(sa.Column('primary_muscle_group', sa.String(length=20), nullable=True))
        batch_op.create_index(batch_op.f('ix_exercise_primary_muscle_group'), ['primary_muscle_group'], unique=False)

    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('sex', sa.String(length=10), nullable=False, server_default='male'))
        batch_op.add_column(sa.Column('rank_config', sa.JSON(), nullable=True))

    bind = op.get_bind()
    now = datetime.utcnow()

    # Backfill by auto-tagging from the name (legacy primary_muscle as the
    # fallback hint). updated_at bump makes the change visible to sync pulls.
    ex = sa.table(
        'exercise',
        sa.column('id', sa.Integer),
        sa.column('name', sa.String),
        sa.column('primary_muscle', sa.String),
        sa.column('primary_muscle_group', sa.String),
        sa.column('updated_at', sa.DateTime),
    )
    for row in bind.execute(sa.select(ex.c.id, ex.c.name, ex.c.primary_muscle)).fetchall():
        group = suggest_muscle_group(row.name, row.primary_muscle)
        if group:
            bind.execute(
                sa.update(ex).where(ex.c.id == row.id)
                .values(primary_muscle_group=group, updated_at=now)
            )
    bind.execute(sa.text('UPDATE settings SET updated_at = :now'), {"now": now})


def downgrade() -> None:
    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.drop_column('rank_config')
        batch_op.drop_column('sex')

    with op.batch_alter_table('exercise', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_exercise_primary_muscle_group'))
        batch_op.drop_column('primary_muscle_group')

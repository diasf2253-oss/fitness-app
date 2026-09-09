"""phase11_restore_features

Re-ports the feature work from the redesign branch onto the local-first line:
  - routine.source ('manual' | 'generated') for the workout generator.
  - routine_note table — one-shot next-session notes (syncs by uuid).
  - activity table — logged non-barbell sport sessions (syncs by uuid).
  - streak_state singleton — training-streak snapshot (recomputed per device).
  - settings: profile (age/onboarded), adaptive-calorie engine, per-muscle
    volume overrides, streak rest gap, default rest-timer seconds, and the
    retired legacy TDEE fields (nullable, unused).

Existing installs are backfilled to onboarded=True (they've already been using
the app) and get updated_at bumped so incremental sync pulls the change.

Revision ID: a7d2c9f1b3e5
Revises: e9f2a4b6c8d0
Create Date: 2026-07-12 20:10:00.000000

"""
from datetime import datetime
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7d2c9f1b3e5'
down_revision: Union[str, None] = 'e9f2a4b6c8d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---- routine.source -----------------------------------------------------
    with op.batch_alter_table('routine', schema=None) as batch_op:
        batch_op.add_column(sa.Column(
            'source', sa.String(length=20), nullable=False, server_default='manual'))

    # ---- routine_note (synced entity) --------------------------------------
    op.create_table(
        'routine_note',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uuid', sa.String(length=36), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('routine_id', sa.Integer(), nullable=False),
        sa.Column('text', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('created_in_session_id', sa.Integer(), nullable=True),
        sa.Column('surfaced_in_session_id', sa.Integer(), nullable=True),
        sa.Column('archived_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['routine_id'], ['routine.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_routine_note_id'), 'routine_note', ['id'], unique=False)
    op.create_index(op.f('ix_routine_note_uuid'), 'routine_note', ['uuid'], unique=True)
    op.create_index(op.f('ix_routine_note_routine_id'), 'routine_note', ['routine_id'], unique=False)
    op.create_index(op.f('ix_routine_note_surfaced_in_session_id'), 'routine_note', ['surfaced_in_session_id'], unique=False)

    # ---- activity (synced entity) ------------------------------------------
    op.create_table(
        'activity',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('uuid', sa.String(length=36), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('type', sa.String(length=40), nullable=False),
        sa.Column('duration_min', sa.Integer(), nullable=False),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('source', sa.String(length=50), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_activity_id'), 'activity', ['id'], unique=False)
    op.create_index(op.f('ix_activity_uuid'), 'activity', ['uuid'], unique=True)
    op.create_index(op.f('ix_activity_date'), 'activity', ['date'], unique=False)

    # ---- streak_state (singleton snapshot, not synced) ---------------------
    op.create_table(
        'streak_state',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.Column('current_streak', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('longest_streak', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_workout_date', sa.Date(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )

    # ---- settings columns ---------------------------------------------------
    with op.batch_alter_table('settings', schema=None) as batch_op:
        batch_op.add_column(sa.Column('age', sa.Integer(), nullable=False, server_default='19'))
        batch_op.add_column(sa.Column('onboarded', sa.Boolean(), nullable=False, server_default=sa.false()))
        batch_op.add_column(sa.Column('target_loss_kg_per_week', sa.Float(), nullable=False, server_default='0.5'))
        batch_op.add_column(sa.Column('adapt_step_kcal', sa.Integer(), nullable=False, server_default='100'))
        batch_op.add_column(sa.Column('adapt_tolerance_kg', sa.Float(), nullable=False, server_default='0.15'))
        batch_op.add_column(sa.Column('calorie_floor', sa.Integer(), nullable=False, server_default='1800'))
        batch_op.add_column(sa.Column('calorie_ceiling', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('last_adapted_week', sa.Date(), nullable=True))
        batch_op.add_column(sa.Column('volume_targets', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('streak_rest_gap', sa.Integer(), nullable=False, server_default='1'))
        batch_op.add_column(sa.Column('default_rest_seconds', sa.Integer(), nullable=False, server_default='120'))
        batch_op.add_column(sa.Column('goal_rate_kg_per_week', sa.Float(), nullable=False, server_default='-0.25'))
        batch_op.add_column(sa.Column('expenditure_kcal', sa.Float(), nullable=True))
        batch_op.add_column(sa.Column('calorie_target_set_at', sa.Date(), nullable=True))

    # Existing installs have been in use → mark them onboarded; bump updated_at
    # so devices syncing incrementally pull the new singleton state.
    now = datetime.utcnow()
    bind = op.get_bind()
    bind.execute(sa.text('UPDATE settings SET onboarded = :t, updated_at = :now'),
                 {"t": True, "now": now})


def downgrade() -> None:
    with op.batch_alter_table('settings', schema=None) as batch_op:
        for col in (
            'calorie_target_set_at', 'expenditure_kcal', 'goal_rate_kg_per_week',
            'default_rest_seconds', 'streak_rest_gap', 'volume_targets',
            'last_adapted_week', 'calorie_ceiling', 'calorie_floor',
            'adapt_tolerance_kg', 'adapt_step_kcal', 'target_loss_kg_per_week',
            'onboarded', 'age',
        ):
            batch_op.drop_column(col)

    op.drop_table('streak_state')
    op.drop_index(op.f('ix_activity_date'), table_name='activity')
    op.drop_index(op.f('ix_activity_uuid'), table_name='activity')
    op.drop_index(op.f('ix_activity_id'), table_name='activity')
    op.drop_table('activity')
    op.drop_index(op.f('ix_routine_note_surfaced_in_session_id'), table_name='routine_note')
    op.drop_index(op.f('ix_routine_note_routine_id'), table_name='routine_note')
    op.drop_index(op.f('ix_routine_note_uuid'), table_name='routine_note')
    op.drop_index(op.f('ix_routine_note_id'), table_name='routine_note')
    op.drop_table('routine_note')

    with op.batch_alter_table('routine', schema=None) as batch_op:
        batch_op.drop_column('source')

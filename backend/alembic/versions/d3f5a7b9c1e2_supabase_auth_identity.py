"""Supabase Auth: link each account to its Supabase login.

  - users.supabase_uid (nullable, unique): the Supabase Auth user id — the
    access token's `sub`. NULL until the person first signs in through
    Supabase, when app/auth.py links it by verified email. Nothing to
    backfill: existing accounts link themselves on first sign-in.
  - users.password_hash becomes nullable: passwords live in Supabase now, so
    accounts created after the switch have none. Existing hashes are left in
    place (unused) for a later cleanup migration, which will drop this column
    together with users.must_change_password and the auth_session table once
    the switch has run in production.

Additive and safe to run before the new code deploys (old code ignores the
new column). As with every schema change: staging first, with a backup.

Revision ID: d3f5a7b9c1e2
Revises: a7c3e9d1f2b4
Create Date: 2026-11-14
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'd3f5a7b9c1e2'
down_revision: Union[str, None] = 'a7c3e9d1f2b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('supabase_uid', sa.String(length=36), nullable=True))
        batch_op.alter_column('password_hash', existing_type=sa.String(length=255), nullable=True)
        batch_op.create_index('ix_users_supabase_uid', ['supabase_uid'], unique=True)


def downgrade() -> None:
    # Accounts created after the switch have no hash; '!' can never match an
    # argon2 hash, so they simply can't use the old password login.
    op.execute("UPDATE users SET password_hash = '!' WHERE password_hash IS NULL")
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_index('ix_users_supabase_uid')
        batch_op.alter_column('password_hash', existing_type=sa.String(length=255), nullable=False)
        batch_op.drop_column('supabase_uid')

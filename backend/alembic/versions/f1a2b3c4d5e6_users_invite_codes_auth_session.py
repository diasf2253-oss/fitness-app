"""Phase 1-2 friends beta: users, invite_codes, auth_session tables.

Purely additive — creates the three new auth tables. No existing table is
touched here; user_id retrofits onto existing tables happen in the next
migration, after a manual backfill (see app/backfill_owner.py). Safe to run
against production later with no data-migration risk of its own.

Revision ID: f1a2b3c4d5e6
Revises: b1c3e5a7d9f2
Create Date: 2026-08-22
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'b1c3e5a7d9f2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(length=255), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('role', sa.String(length=20), nullable=False, server_default='user'),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('must_change_password', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('ingest_token', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)
    op.create_index('ix_users_ingest_token', 'users', ['ingest_token'], unique=True)

    op.create_table(
        'invite_codes',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('code', sa.String(length=64), nullable=False),
        sa.Column('label', sa.String(length=200), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column('max_uses', sa.Integer(), nullable=True),
        sa.Column('uses', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_invite_codes_code', 'invite_codes', ['code'], unique=True)

    op.create_table(
        'auth_session',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('session_id', sa.String(length=64), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
        sa.Column('last_seen_at', sa.DateTime(), nullable=True),
    )
    op.create_index('ix_auth_session_session_id', 'auth_session', ['session_id'], unique=True)
    op.create_index('ix_auth_session_user_id', 'auth_session', ['user_id'])
    op.create_index('ix_auth_session_expires_at', 'auth_session', ['expires_at'])


def downgrade() -> None:
    op.drop_table('auth_session')
    op.drop_table('invite_codes')
    op.drop_table('users')

"""lock every table away from Supabase's public Data API

Revision ID: e1f3a5c7b9d2
Revises: d3f5a7b9c1e2
Create Date: 2026-11-14

Why: a Supabase project publishes every table in the `public` schema through
its Data API (PostgREST), reachable with the *publishable* key — and that key
is public by design (it ships inside the frontend for sign-in). On Supabase,
that API acts as the `anon` (signed-out) or `authenticated` (any signed-in
Supabase user) database role. Left alone, anyone holding the public key could
read or write this app's tables directly, bypassing the backend's per-user
checks entirely.

This app never uses the Data API: every read and write goes through FastAPI,
which connects as the database owner (`postgres`). So the lock is total:

  1. Row Level Security ON for every table in `public`, with NO policies.
     RLS with no policies means "no rows, ever" for every role except the
     table owner — and the backend is the owner, so it's unaffected.
  2. Revoke every privilege `anon` and `authenticated` hold on the tables,
     sequences and functions in `public` — a second, independent wall.
  3. Default privileges: tables/sequences/functions created LATER by this
     same role (i.e. every future migration) start with no grants for `anon`
     or `authenticated` either, so a new table can't quietly reopen the hole.

Postgres-only; a no-op on SQLite (local dev and tests). Steps 2-3 only run
where the Supabase roles exist, so a plain Postgres (local restore, CI) is
fine too. Safe to run again: every statement is idempotent.
"""
from alembic import op


revision = 'e1f3a5c7b9d2'
down_revision = 'd3f5a7b9c1e2'
branch_labels = None
depends_on = None


_LOCK = r"""
DO $lock$
DECLARE
  t record;
  r text;
BEGIN
  FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE format('ALTER TABLE public.%I ENABLE ROW LEVEL SECURITY', t.tablename);
  END LOOP;

  FOREACH r IN ARRAY ARRAY['anon', 'authenticated'] LOOP
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = r) THEN
      EXECUTE format('REVOKE ALL ON ALL TABLES    IN SCHEMA public FROM %I', r);
      EXECUTE format('REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM %I', r);
      EXECUTE format('REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM %I', r);
      EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON TABLES    FROM %I', r);
      EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON SEQUENCES FROM %I', r);
      EXECUTE format('ALTER DEFAULT PRIVILEGES IN SCHEMA public REVOKE ALL ON FUNCTIONS FROM %I', r);
    END IF;
  END LOOP;
END
$lock$;
"""

# Downgrade only switches RLS back off. It deliberately does NOT re-grant
# anything to anon/authenticated: reopening the public Data API should never
# happen as a side effect of rolling back a migration.
_UNLOCK = r"""
DO $unlock$
DECLARE
  t record;
BEGIN
  FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' LOOP
    EXECUTE format('ALTER TABLE public.%I DISABLE ROW LEVEL SECURITY', t.tablename);
  END LOOP;
END
$unlock$;
"""


def upgrade() -> None:
    if op.get_bind().dialect.name == 'postgresql':
        op.execute(_LOCK)


def downgrade() -> None:
    if op.get_bind().dialect.name == 'postgresql':
        op.execute(_UNLOCK)

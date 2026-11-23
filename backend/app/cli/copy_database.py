"""
Copy the whole app database into a Supabase Postgres — safely.

Three jobs, one tool:

    python -m app.cli.copy_database --from old  --to staging     # rehearse the move
    python -m app.cli.copy_database --from old  --to production  # THE move
    python -m app.cli.copy_database --from prod --to staging     # refresh staging later

(Or the one-word wrappers: ./scripts/move_to_supabase.sh, ./scripts/seed_staging.sh.)

The connection strings come from scripts/.env.backup (git-ignored) or the
environment — never the command line, so they never land in shell history:

    OLD_DATABASE_URL      the pre-Supabase production database (source of the move)
    PROD_DATABASE_URL     production Supabase  — Session pooler string (port 5432)
    STAGING_DATABASE_URL  staging Supabase     — Session pooler string (port 5432)

How it works (no pg_dump needed — just the backend's own Python):
  1. Build the target's tables with `alembic upgrade head`, exactly as the
     code expects them — including migration e1f3a5c7b9d2, which locks every
     table away from Supabase's public Data API.
  2. In ONE transaction on the target: copy every table, parents before
     children, then move each id counter past the copied ids, then compare
     row counts table by table. Any error or mismatch rolls the whole copy
     back — the target is left exactly as it was.
  3. --to staging only: scrub personal data with scripts/anonymise_staging.sql.
  4. Prove the lock: Postgres confirms every table has Row Level Security on
     and that the roles the public key acts as can't touch any of them.

The source is only ever READ. The old production database stays untouched,
so it remains a complete fallback until you delete it.

Guards (each one stops the run before anything is written):
  - the target must be a Supabase database, and never the same database as
    the source;
  - --to production refuses the staging project and refuses a target that
    already holds data — it can never overwrite a live production database;
  - --to staging refuses the production project (its existing rows are
    replaced: staging is disposable);
  - the transaction pooler (port 6543) is refused — schema changes need the
    session pooler or the direct connection;
  - you must type the target's project id to go ahead.
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from dotenv import dotenv_values
from sqlalchemy import JSON, MetaData, Text, cast, create_engine, func, inspect, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.types import TypeDecorator

from app.core.config import Settings
from app.core.db import Base, _connect_args
import app.models  # noqa: F401 — registers every table on Base.metadata

BACKEND_DIR = Path(__file__).resolve().parents[2]
REPO_DIR = BACKEND_DIR.parent
ENV_FILE = REPO_DIR / "scripts" / ".env.backup"
ANONYMISE_SQL = REPO_DIR / "scripts" / "anonymise_staging.sql"
BATCH = 1000

SOURCES = {"old": "OLD_DATABASE_URL", "prod": "PROD_DATABASE_URL"}
TARGETS = {"staging": "STAGING_DATABASE_URL", "production": "PROD_DATABASE_URL"}


class Refused(Exception):
    """A guard said no. Nothing has been written."""


# ---------------------------------------------------------------- addresses
def normalise(url: str) -> str:
    """postgres:// → postgresql+psycopg:// — the same rule the app uses."""
    return Settings(database_url=url).database_url


def project_ref(url: str) -> str | None:
    """The Supabase project id in a connection string, or None.

    Pooler strings carry it in the user name (postgres.<ref>@…pooler.supabase.com);
    direct strings in the host (db.<ref>.supabase.co).
    """
    u = urlparse(url)
    host = (u.hostname or "").lower()
    user = u.username or ""
    if host.endswith(".pooler.supabase.com") and "." in user:
        return user.split(".", 1)[1].lower()
    if host.startswith("db.") and host.endswith(".supabase.co"):
        return host.split(".")[1]
    return None


def identity(url: str) -> str:
    """What makes two strings 'the same database'. Supabase projects can share
    a pooler host, so for them the project id decides, not the host."""
    ref = project_ref(url)
    if ref:
        return f"supabase:{ref}"
    u = urlparse(url)
    return f"{(u.hostname or '').lower()}:{u.port or 5432}/{(u.path or '/').lstrip('/')}"


def shown(url: str) -> str:
    """A connection string with the password removed — safe to print."""
    u = urlparse(url)
    if u.scheme.startswith("sqlite"):
        return url
    port = f":{u.port}" if u.port else ""
    return f"{u.hostname}{port}/{(u.path or '/').lstrip('/')} (user {u.username})"


def check_pair(source: str, target: str, to: str, other: str | None) -> None:
    """Every guard that can be checked without connecting. Raises Refused."""
    if identity(source) == identity(target):
        raise Refused("the source and the target are the same database.")
    if project_ref(target) is None:
        raise Refused(f"the target ({shown(target)}) isn't a Supabase database. "
                      "Use the Session pooler string from Supabase → Connect.")
    if urlparse(target).port == 6543:
        raise Refused("the target is the transaction pooler (port 6543). Use the "
                      "Session pooler string (port 5432) — it's for one-off jobs like this.")
    if other and identity(other) == identity(target):
        which = "staging" if to == "production" else "production"
        raise Refused(f"the --to {to} address is the {which} project. "
                      "Check scripts/.env.backup.")


# ---------------------------------------------------------------- the copy
def _engine(url: str) -> Engine:
    return create_engine(url, connect_args=_connect_args(url))


def migrate(target: str) -> None:
    """Build/upgrade the target's tables with the app's own migrations."""
    env = {**os.environ, "DATABASE_URL": target}
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"],
                   cwd=BACKEND_DIR, env=env, check=True)


class _JSONText(TypeDecorator):
    """JSON carried as its raw text, cast back to json by Postgres on insert."""
    impl = Text
    cache_ok = True

    def bind_expression(self, bindvalue):
        return cast(bindvalue, JSON)


def _copy_tables(dialect: str) -> list:
    """The app's tables, parents first, as copies whose JSON columns are
    handled as raw text. Round-tripping through Python would blur a SQL NULL
    and the JSON value `null` together; as text, each is copied exactly.
    (SQLite stores JSON as plain text anyway; Postgres needs the cast.)"""
    meta = MetaData()
    tables = []
    for t in Base.metadata.sorted_tables:
        c = t.to_metadata(meta)
        for col in c.columns:
            if isinstance(col.type, JSON):
                col.type = _JSONText() if dialect == "postgresql" else Text()
                col.info["json"] = True
        tables.append(c)
    return tables


def _count(conn, table) -> int:
    return conn.execute(select(func.count()).select_from(table)).scalar_one()


def copy(source: str, target: str, *, replace: bool, log=print) -> dict[str, int]:
    """Copy every app table from source into target in one transaction.

    The target's tables must already exist (see migrate()). Returns
    {table: rows}. Raises Refused, or rolls back on any error/mismatch.
    """
    src, tgt = _engine(source), _engine(target)
    tables = _copy_tables(tgt.dialect.name)
    try:
        src_tables = set(inspect(src).get_table_names())
        known = {t.name for t in tables} | {"alembic_version"}
        for extra in sorted(src_tables - known):
            log(f"  note: source table '{extra}' isn't part of the app — not copied")

        counts: dict[str, int] = {}
        with src.connect() as s, tgt.begin() as d:
            existing = {t.name: _count(d, t) for t in tables}
            if any(existing.values()):
                if not replace:
                    busy = ", ".join(f"{k} ({v})" for k, v in existing.items() if v)
                    raise Refused(f"the target already holds data: {busy}. "
                                  "--to production never overwrites a database.")
                for t in reversed(tables):          # children first
                    d.execute(t.delete())

            src_cols = {name: {c["name"] for c in inspect(src).get_columns(name)}
                        for name in src_tables}
            for t in tables:
                if t.name not in src_tables:
                    log(f"  {t.name:<18} not in the source — left empty")
                    counts[t.name] = 0
                    continue
                cols = [cast(c, Text).label(c.name) if c.info.get("json") else c
                        for c in t.columns if c.name in src_cols[t.name]]
                missing = [c.name for c in t.columns if c.name not in src_cols[t.name]]
                if missing:
                    log(f"  {t.name:<18} source has no {', '.join(missing)} — left at defaults")
                order = [t.c.id] if "id" in t.c else []
                rows = s.execute(select(*cols).order_by(*order)).mappings()
                n = 0
                while chunk := rows.fetchmany(BATCH):
                    d.execute(t.insert(), [dict(r) for r in chunk])
                    n += len(chunk)
                counts[t.name] = n

            # Id counters: Postgres hands out ids from a sequence that knows
            # nothing about the rows we just inserted with explicit ids. Move
            # each one past the highest copied id, or the next new workout
            # would collide with an old one.
            if d.dialect.name == "postgresql":
                for t in tables:
                    if "id" in t.c:
                        d.execute(text(
                            f"SELECT setval(pg_get_serial_sequence('public.\"{t.name}\"', 'id'), "
                            f"COALESCE(MAX(id), 1), MAX(id) IS NOT NULL) FROM \"{t.name}\""))

            # Verify inside the transaction: a mismatch rolls everything back.
            for t in tables:
                got = _count(d, t)
                if got != counts[t.name]:
                    raise RuntimeError(f"row count mismatch in {t.name}: "
                                       f"copied {counts[t.name]}, target has {got}")
        return counts
    finally:
        src.dispose()
        tgt.dispose()


# ---------------------------------------------------------------- after
def anonymise(target: str) -> None:
    """Scrub the staging copy (its own all-or-nothing transaction)."""
    import psycopg

    dsn = target.replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(dsn, autocommit=True, prepare_threshold=None) as conn:
        conn.execute(ANONYMISE_SQL.read_text())


_LOCK_CHECK = """
SELECT t.tablename,
       t.rowsecurity AS rls_on,
       EXISTS (
         SELECT 1 FROM pg_roles r
         WHERE r.rolname IN ('anon', 'authenticated')
           AND has_table_privilege(r.oid, format('public.%I', t.tablename),
                                   'SELECT, INSERT, UPDATE, DELETE')
       ) AS public_access
FROM pg_tables t
WHERE t.schemaname = 'public'
"""


def check_lock(target: str, log=print) -> None:
    """Prove no table is reachable through Supabase's public Data API.

    Asks Postgres itself, for every table: is Row Level Security on, and can
    the `anon` / `authenticated` roles (what the publishable key acts as)
    read or write it at all? Both walls must hold. Raises RuntimeError if not.
    """
    eng = _engine(target)
    try:
        with eng.connect() as c:
            rows = c.execute(text(_LOCK_CHECK)).all()
    finally:
        eng.dispose()
    rls_off = [r.tablename for r in rows if not r.rls_on]
    reachable = [r.tablename for r in rows if r.public_access]
    if rls_off or reachable:
        raise RuntimeError(f"tables not locked — RLS off: {rls_off or 'none'}; "
                           f"public roles can access: {reachable or 'none'}")
    log(f"  {len(rows)} tables: Row Level Security on, no access for the public key ✓")


# ---------------------------------------------------------------- CLI
def _env() -> dict[str, str]:
    values = {k: v for k, v in dotenv_values(ENV_FILE).items() if v} if ENV_FILE.exists() else {}
    return {**values, **{k: v for k, v in os.environ.items() if v}}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Copy the app database into Supabase.")
    p.add_argument("--from", dest="source", choices=SOURCES, required=True)
    p.add_argument("--to", dest="target", choices=TARGETS, required=True)
    args = p.parse_args(argv)

    env = _env()
    src_var, tgt_var = SOURCES[args.source], TARGETS[args.target]
    if src_var == tgt_var:
        print("Refused: --from prod --to production copies a database onto itself.")
        return 2
    missing = [v for v in (src_var, tgt_var) if not env.get(v)]
    if missing:
        print(f"Refused: set {' and '.join(missing)} in scripts/.env.backup first.")
        return 2
    source, target = normalise(env[src_var]), normalise(env[tgt_var])
    other_var = "STAGING_DATABASE_URL" if args.target == "production" else "PROD_DATABASE_URL"
    other = normalise(env[other_var]) if env.get(other_var) else None

    try:
        check_pair(source, target, args.target, other)
    except Refused as e:
        print(f"Refused: {e}")
        return 2

    ref = project_ref(target)
    print()
    print("  ============================================================")
    print(f"   COPY DATABASE  →  {args.target.upper()}")
    print("  ============================================================")
    print(f"   From : {shown(source)}   (read only)")
    print(f"   To   : {shown(target)}")
    if args.target == "staging":
        print("   Staging's current rows are replaced, then personal data is scrubbed.")
    else:
        print("   Production must be empty; it is never overwritten.")
    print("  ============================================================")
    if input(f"   Type the target project id ({ref}) to go ahead: ").strip() != ref:
        print("Aborted — nothing was changed.")
        return 1

    try:
        print("\n1/4 Building tables (alembic upgrade head)…")
        migrate(target)
        print("2/4 Copying rows (one transaction)…")
        counts = copy(source, target, replace=args.target == "staging")
        for name, n in counts.items():
            print(f"  {name:<18} {n:>7} rows")
        print(f"  total              {sum(counts.values()):>7} rows — counts match the source ✓")
        if args.target == "staging":
            print("3/4 Scrubbing personal data (anonymise_staging.sql)…")
            anonymise(target)
        else:
            print("3/4 (production keeps real data — nothing to scrub)")
        print("4/4 Checking the public key can't read anything…")
        check_lock(target)
    except Refused as e:
        print(f"Refused: {e}")
        return 2
    except Exception as e:  # noqa: BLE001 — report plainly, never with a password
        print(f"\nStopped: {type(e).__name__}: {str(e).splitlines()[0][:300]}")
        print("The copy runs in one transaction, so a failure there left the target unchanged.")
        return 1

    print(f"\nDone: {args.target} now holds a copy of the {args.source} database.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
app.cli.copy_database — the tool that moves the data into Supabase.

The guards are pure string checks, tested directly. The copy itself runs
between two throwaway SQLite files (the real move is Postgres → Postgres, but
the copy code is dialect-neutral; only the id-counter reset is Postgres-only).
Building the target with migrate() also proves the whole Alembic chain —
including the Postgres-only lock migration, a no-op here — runs cleanly.
"""
from datetime import date, datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.cli.copy_database import (
    Refused, check_pair, copy, identity, migrate, project_ref, shown,
)
from app.models import Exercise, User, WeightLog

POOLER = "postgresql+psycopg://postgres.{ref}:{pw}@aws-0-eu-west-1.pooler.supabase.com:{port}/postgres"
PROD = POOLER.format(ref="prodref", pw="secret1", port=5432)
STAGING = POOLER.format(ref="stagingref", pw="secret2", port=5432)
OLD = "postgresql+psycopg://neondb_owner:pw@ep-cool-1.eu-central-1.aws.neon.tech/neondb"


# ------------------------------------------------------------------ guards
def test_project_ref_from_pooler_and_direct_strings():
    assert project_ref(PROD) == "prodref"
    assert project_ref("postgresql://postgres:pw@db.abcxyz.supabase.co:5432/postgres") == "abcxyz"
    assert project_ref(OLD) is None


def test_projects_sharing_a_pooler_host_are_different_databases():
    # Same host, same port — only the project id in the user name differs.
    assert identity(PROD) != identity(STAGING)
    # Same project, different password → still the same database.
    assert identity(PROD) == identity(POOLER.format(ref="prodref", pw="other", port=5432))


def test_shown_never_contains_the_password():
    assert "secret1" not in shown(PROD)


def test_the_move_is_allowed_old_to_production():
    check_pair(OLD, PROD, "production", STAGING)          # no exception


@pytest.mark.parametrize("source, target, to, other, why", [
    (PROD, POOLER.format(ref="prodref", pw="x", port=5432), "staging", None, "same database"),
    (OLD, OLD.replace("neondb", "otherdb"), "production", None, "isn't a Supabase"),
    (OLD, POOLER.format(ref="prodref", pw="x", port=6543), "production", None, "transaction pooler"),
    (OLD, STAGING, "production", STAGING, "staging project"),
    (OLD, PROD, "staging", PROD, "production project"),
])
def test_guards_refuse(source, target, to, other, why):
    with pytest.raises(Refused, match=why):
        check_pair(source, target, to, other)


# ------------------------------------------------------------------ copy
@pytest.fixture
def dbs(tmp_path):
    """A migrated, seeded source and a migrated, empty target (SQLite files)."""
    src = f"sqlite:///{tmp_path / 'source.sqlite3'}"
    tgt = f"sqlite:///{tmp_path / 'target.sqlite3'}"
    migrate(src)
    migrate(tgt)
    eng = create_engine(src)
    with Session(eng) as s:
        u = User(email="a@example.com", name="A", role="admin", status="active",
                 supabase_uid="11111111-1111-1111-1111-111111111111")
        s.add(u)
        s.flush()
        s.add_all([
            WeightLog(user_id=u.id, date=date(2026, 11, 1), weight_kg=82.5, source="manual"),
            WeightLog(user_id=u.id, date=date(2026, 11, 2), weight_kg=82.1, source="apple_health"),
            Exercise(name="Squat", secondary_muscles=["glutes"], is_custom=False),
            Exercise(name="Odd one", secondary_muscles=None, is_custom=True, user_id=u.id),
        ])
        s.commit()
    eng.dispose()
    return src, tgt


def _rows(url, sql):
    eng = create_engine(url)
    try:
        with eng.connect() as c:
            return c.execute(text(sql)).all()
    finally:
        eng.dispose()


def test_copies_every_row_and_keeps_ids_and_values(dbs):
    src, tgt = dbs
    counts = copy(src, tgt, replace=False, log=lambda *_: None)

    assert counts["users"] == 1 and counts["weight_log"] == 2 and counts["exercise"] == 2
    assert _rows(tgt, "SELECT id, email, supabase_uid FROM users") == \
        _rows(src, "SELECT id, email, supabase_uid FROM users")
    assert _rows(tgt, "SELECT date, weight_kg, source FROM weight_log ORDER BY date") == \
        _rows(src, "SELECT date, weight_kg, source FROM weight_log ORDER BY date")


def test_a_sql_null_json_value_stays_null(dbs):
    src, tgt = dbs
    copy(src, tgt, replace=False, log=lambda *_: None)
    assert _rows(tgt, "SELECT secondary_muscles FROM exercise WHERE name = 'Odd one'") == \
        _rows(src, "SELECT secondary_muscles FROM exercise WHERE name = 'Odd one'")


def test_never_overwrites_a_target_that_holds_data(dbs):
    src, tgt = dbs
    copy(src, tgt, replace=False, log=lambda *_: None)
    with pytest.raises(Refused, match="already holds data"):
        copy(src, tgt, replace=False, log=lambda *_: None)
    assert _rows(tgt, "SELECT COUNT(*) FROM weight_log") == [(2,)]   # untouched


def test_staging_mode_replaces_existing_rows(dbs):
    src, tgt = dbs
    copy(src, tgt, replace=True, log=lambda *_: None)
    counts = copy(src, tgt, replace=True, log=lambda *_: None)   # again: no duplicates
    assert counts["weight_log"] == 2
    assert _rows(tgt, "SELECT COUNT(*) FROM weight_log") == [(2,)]


def test_a_failed_copy_leaves_the_target_unchanged(dbs, monkeypatch):
    src, tgt = dbs
    import app.cli.copy_database as mod

    real_count = mod._count
    calls = {"n": 0}

    def broken_count(conn, table):               # sabotage the final verification
        calls["n"] += 1
        n = real_count(conn, table)
        return n + 1 if table.name == "weight_log" and n else n

    monkeypatch.setattr(mod, "_count", broken_count)
    with pytest.raises(RuntimeError, match="mismatch in weight_log"):
        copy(src, tgt, replace=False, log=lambda *_: None)
    assert _rows(tgt, "SELECT COUNT(*) FROM users") == [(0,)]       # rolled back


def test_the_source_is_only_read(dbs):
    src, tgt = dbs
    before = _rows(src, "SELECT id, weight_kg, updated_at FROM weight_log ORDER BY id")
    copy(src, tgt, replace=False, log=lambda *_: None)
    assert _rows(src, "SELECT id, weight_kg, updated_at FROM weight_log ORDER BY id") == before


def test_new_rows_after_the_copy_get_fresh_ids(dbs):
    src, tgt = dbs
    copy(src, tgt, replace=False, log=lambda *_: None)
    eng = create_engine(tgt)
    with Session(eng) as s:
        w = WeightLog(user_id=1, date=date(2026, 11, 3), weight_kg=81.9, source="manual",
                      updated_at=datetime(2026, 11, 3))
        s.add(w)
        s.commit()
        assert w.id == 3
    eng.dispose()

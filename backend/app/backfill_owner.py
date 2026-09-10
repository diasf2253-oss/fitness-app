"""
One-off backfill: attaches every pre-multi-user row to the admin account.

Run this AFTER migration a2b3c4d5e6f7 (nullable user_id added) and BEFORE
migration c4d5e6f7a8b9 (user_id made NOT NULL) — against staging only, with
a fresh backup and these row counts recorded first. See CLAUDE.md's
"Auth & multi-user" migration note and backup runbook.
Never run this against PROD_DATABASE_URL.

Usage:
    cd backend
    source .venv/bin/activate
    ADMIN_EMAIL=you@example.com ADMIN_PASSWORD=... python -m app.backfill_owner
"""
import sys
import os

# Allow running as a standalone script
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from sqlalchemy import text

from app.auth_bootstrap import get_or_create_admin_user
from app.db import SessionLocal
from app.models import Exercise

# Every table that gets a NOT NULL user_id after this backfill (mirrors
# migration a2b3c4d5e6f7's _TABLES list).
_TABLES = [
    'routine', 'routine_exercise', 'session', 'session_exercise', 'set',
    'routine_note', 'plan_item', 'weight_log', 'steps_log', 'sleep_log',
    'nutrition_day', 'tracker', 'settings', 'streak_state', 'activity',
]


def _row_counts(db, tables):
    # Double-quoted identifiers: `set` is a reserved SQL keyword and one of
    # our table names, and this quoting style works on both SQLite and
    # Postgres.
    return {t: db.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar() for t in tables}


def backfill():
    db = SessionLocal()
    try:
        admin = get_or_create_admin_user(db)
        print(f"Admin account: {admin.email} (id={admin.id})")

        before = _row_counts(db, _TABLES)
        print("\nRow counts before backfill:")
        for t, c in before.items():
            print(f"  {t}: {c}")

        for table in _TABLES:
            db.execute(
                text(f'UPDATE "{table}" SET user_id = :admin_id WHERE user_id IS NULL'),
                {"admin_id": admin.id},
            )

        # Custom exercises created before multi-user get owned by the admin;
        # the seeded global library (is_custom=False) stays user_id=NULL.
        custom = (
            db.query(Exercise)
            .filter(Exercise.is_custom.is_(True), Exercise.user_id.is_(None))
            .all()
        )
        for ex in custom:
            ex.user_id = admin.id
        print(f"\nAttached {len(custom)} custom exercise(s) to the admin account "
              f"(the seeded global library stays unowned).")

        db.commit()

        after = _row_counts(db, _TABLES)
        print("\nRow counts after backfill (must match before, all now owned):")
        mismatches = []
        for t in _TABLES:
            print(f"  {t}: {after[t]}")
            if after[t] != before[t]:
                mismatches.append(t)
        if mismatches:
            raise RuntimeError(f"Row count mismatch after backfill: {mismatches}")

        print("\nBackfill complete. Verify the counts above against your "
              "pre-migration backup, then run: alembic upgrade head")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    backfill()

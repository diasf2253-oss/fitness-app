"""
One-off cleanup: delete every demo row written by the sample-data seeder.

`POST /api/dev/seed-sample-health` used to be reachable by any logged-in user
from Settings → Developer, and it writes ~30 days of invented weight, steps,
sleep and nutrition tagged `source='sample'`. Those rows render like real
measurements on the Dashboard, Diet, Insights and Report, so any account that
ever tapped that button is showing numbers nobody recorded. This removes them.

Only rows whose source is exactly 'sample' are touched — real entries
('manual', 'apple_health') and interpolated weights ('estimated') are left
alone, and every other table is untouched.

Usage:
    cd backend
    source .venv/bin/activate

    python -m app.purge_sample              # dry run: report what would go
    python -m app.purge_sample --yes        # actually delete
    python -m app.purge_sample --yes --user 3   # limit to one account

Run it against staging first, and take a fresh `./scripts/backup.sh` before
pointing it at production — see CLAUDE.md's backup runbook.
"""
import argparse
import os
import sys

# Allow running as a standalone script
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from app.db import SessionLocal
from app.models import Activity, NutritionDay, SleepLog, StepsLog, WeightLog

SAMPLE_SOURCE = "sample"

# Every table the seeder writes, plus Activity — streak.py filters
# `Activity.source != 'sample'`, so demo activities can exist there too.
_MODELS = (WeightLog, StepsLog, SleepLog, NutritionDay, Activity)


def _counts(db, user_id=None):
    out = {}
    for model in _MODELS:
        q = db.query(model).filter(model.source == SAMPLE_SOURCE)
        if user_id is not None:
            q = q.filter(model.user_id == user_id)
        out[model.__tablename__] = q.count()
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--yes", action="store_true",
                    help="actually delete (without this it is a dry run)")
    ap.add_argument("--user", type=int, default=None,
                    help="limit to a single user_id (default: every account)")
    args = ap.parse_args()

    db = SessionLocal()
    try:
        scope = f"user_id={args.user}" if args.user is not None else "all users"
        before = _counts(db, args.user)
        total = sum(before.values())

        print(f"Sample rows ({scope}):")
        for table, n in before.items():
            print(f"  {table:16} {n}")
        print(f"  {'TOTAL':16} {total}")

        if total == 0:
            print("\nNothing to do.")
            return

        if not args.yes:
            print("\nDry run — nothing deleted. Re-run with --yes to remove these rows.")
            return

        deleted = 0
        for model in _MODELS:
            q = db.query(model).filter(model.source == SAMPLE_SOURCE)
            if args.user is not None:
                q = q.filter(model.user_id == args.user)
            deleted += q.delete(synchronize_session=False)
        db.commit()

        print(f"\nDeleted {deleted} sample rows.")
        remaining = sum(_counts(db, args.user).values())
        print(f"Remaining sample rows: {remaining}")
    finally:
        db.close()


if __name__ == "__main__":
    main()

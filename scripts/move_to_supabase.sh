#!/bin/bash
# ---------------------------------------------------------------------------
# Move the app's data from the old production database into Supabase.
#
#   ./scripts/move_to_supabase.sh staging      # rehearsal: copy + scrub into staging
#   ./scripts/move_to_supabase.sh production   # the real move
#
# Reads OLD_DATABASE_URL, PROD_DATABASE_URL and STAGING_DATABASE_URL from
# scripts/.env.backup. The old database is only ever READ — it stays a full
# fallback. `production` first takes a pg_dump of the old database into
# backups/ (belt and braces), then copies. All guards and the step-by-step
# output live in backend/app/cli/copy_database.py.
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")/.."   # repo root
. scripts/lib.sh

case "${1:-}" in
  staging|production) ;;
  *) echo "Usage: ./scripts/move_to_supabase.sh staging|production" >&2; exit 2 ;;
esac
[ -x backend/.venv/bin/python ] || { echo "backend/.venv missing — run ./start.sh once first." >&2; exit 1; }

if [ "$1" = production ] && [ "${SKIP_BACKUP:-}" != 1 ] && [[ "${OLD_DATABASE_URL:-}" == sqlite:///* ]]; then
  # The old database is a SQLite file (e.g. the laptop's backend/fitness.sqlite3):
  # a backup is simply a timestamped copy of that file.
  OLD_FILE="${OLD_DATABASE_URL#sqlite:///}"
  [ -f "$OLD_FILE" ] || { echo "OLD_DATABASE_URL points at a missing file: $OLD_FILE" >&2; exit 1; }
  mkdir -p "${BACKUP_DIR:-backups}"
  cp "$OLD_FILE" "${BACKUP_DIR:-backups}/fitness_old_$(date +%Y%m%d_%H%M%S).sqlite3"
  echo "Backed up $OLD_FILE into ${BACKUP_DIR:-backups}/"
elif [ "$1" = production ] && [ "${SKIP_BACKUP:-}" != 1 ]; then
  ./scripts/backup.sh old || {
    echo "Backup of the old database failed — stopping before the move." >&2
    echo "(The old database is never modified by the move; SKIP_BACKUP=1 skips this step.)" >&2
    exit 1
  }
fi

cd backend
exec .venv/bin/python -m app.cli.copy_database --from old --to "$1"

#!/bin/bash
# ---------------------------------------------------------------------------
# Back up the production database to a timestamped local file.
#
#   ./scripts/backup.sh        # production (Supabase): PROD_DATABASE_URL
#   ./scripts/backup.sh old    # the pre-Supabase database: OLD_DATABASE_URL
#
# Connection strings come from scripts/.env.backup (git-ignored) or the
# environment — credentials are NEVER hardcoded here, and neither the
# strings nor the dumps are committed (both git-ignored).
#
# Output: a compressed pg_dump *custom-format* archive under backups/, which
# scripts/restore.sh loads into a LOCAL database.
#
# Env:
#   PROD_DATABASE_URL  Production Supabase — Session pooler string (port 5432).
#   OLD_DATABASE_URL   Only for `old`, during the move to Supabase.
#   BACKUP_DIR         Where dumps land (default: backups).
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")/.."   # repo root
. scripts/lib.sh

if [ "${1:-}" = old ]; then
  : "${OLD_DATABASE_URL:?Set OLD_DATABASE_URL in scripts/.env.backup (the pre-Supabase production database).}"
  URL="$OLD_DATABASE_URL"; LABEL=old
else
  : "${PROD_DATABASE_URL:?Set PROD_DATABASE_URL in scripts/.env.backup (production Supabase, Session pooler string). Never commit it.}"
  URL="$PROD_DATABASE_URL"; LABEL=prod
fi

command -v pg_dump >/dev/null 2>&1 || {
  echo "pg_dump not found. Install the Postgres client tools — see notes/runbooks/SUPABASE.md (Backups)." >&2
  exit 1
}

BACKUP_DIR="${BACKUP_DIR:-backups}"
mkdir -p "$BACKUP_DIR"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUTFILE="$BACKUP_DIR/fitness_${LABEL}_${TIMESTAMP}.dump"

# Only the app's own tables (schema `public`): a Supabase database also holds
# Supabase's internal schemas (auth, storage, …), which aren't ours to back up.
echo "Dumping the $LABEL database -> $OUTFILE"
pg_dump \
  --dbname="$URL" \
  --schema=public \
  --format=custom \
  --no-owner \
  --no-privileges \
  --file="$OUTFILE"

SIZE="$(du -h "$OUTFILE" | cut -f1)"
echo "Done. Wrote $OUTFILE ($SIZE)."
echo "Restore into a LOCAL database with:  ./scripts/restore.sh \"$OUTFILE\""

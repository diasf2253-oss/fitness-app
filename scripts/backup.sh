#!/bin/bash
# ---------------------------------------------------------------------------
# Back up the production Postgres (Railway) to a timestamped local file.
#
#   ./scripts/backup.sh
#
# The connection string is read from the PROD_DATABASE_URL environment
# variable (or from scripts/.env.backup) — credentials are NEVER hardcoded in
# this file, and neither the URL nor the dumps are committed (both git-ignored).
#
# Output: a compressed pg_dump *custom-format* archive under backups/, which
# scripts/restore.sh loads into a LOCAL/STAGING database.
#
# Env:
#   PROD_DATABASE_URL  Railway *public* connection string (required).
#   BACKUP_DIR         Where dumps land (default: backups).
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")/.."   # repo root

# Optional git-ignored secrets file: put PROD_DATABASE_URL=... in it so you
# don't have to export it every shell. See scripts/.env.backup.example.
if [ -f scripts/.env.backup ]; then
  set -a; . scripts/.env.backup; set +a
fi

: "${PROD_DATABASE_URL:?Set PROD_DATABASE_URL to the Railway public connection string (see README -> Database backups). Never commit it.}"

command -v pg_dump >/dev/null 2>&1 || {
  echo "pg_dump not found. Install the Postgres client, e.g.:  brew install libpq  (or postgresql@16)" >&2
  exit 1
}

BACKUP_DIR="${BACKUP_DIR:-backups}"
mkdir -p "$BACKUP_DIR"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUTFILE="$BACKUP_DIR/fitness_prod_${TIMESTAMP}.dump"

echo "Dumping production database -> $OUTFILE"
pg_dump \
  --dbname="$PROD_DATABASE_URL" \
  --format=custom \
  --no-owner \
  --no-privileges \
  --file="$OUTFILE"

SIZE="$(du -h "$OUTFILE" | cut -f1)"
echo "Done. Wrote $OUTFILE ($SIZE)."
echo "Restore into a LOCAL database with:  ./scripts/restore.sh \"$OUTFILE\""

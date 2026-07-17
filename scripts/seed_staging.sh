#!/bin/bash
# ---------------------------------------------------------------------------
# Seed STAGING with an anonymised copy of production.
#
#   ./scripts/seed_staging.sh               # fresh prod dump -> staging
#   ./scripts/seed_staging.sh path.dump     # reuse an existing dump
#
# Flow: pg_dump production (scripts/backup.sh) -> pg_restore into
# STAGING_DATABASE_URL (scripts/restore.sh, keeping its typed-confirmation
# guard) -> run scripts/anonymise_staging.sql on the restored copy, so real
# free text (journal entries, notes) never sits in staging and body/health
# numbers are masked while every trend stays realistic.
#
# Guards, on top of restore.sh's:
#   - STAGING_DATABASE_URL is required and must differ from PROD_DATABASE_URL
#     in host AND port. The dump source is production by definition, so this
#     makes "seeding" production impossible — the target can never be prod.
#   - restore.sh still makes you type the target DB name before it drops it.
#
# Env (scripts/.env.backup is loaded if present):
#   PROD_DATABASE_URL      Railway prod PUBLIC url (required — dump source).
#   STAGING_DATABASE_URL   Railway staging PUBLIC url (required — target).
#   BACKUP_DIR             Where dumps land (default: backups).
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")/.."   # repo root

if [ -f scripts/.env.backup ]; then
  set -a; . scripts/.env.backup; set +a
fi

: "${PROD_DATABASE_URL:?Set PROD_DATABASE_URL (prod public connection string) — seed_staging dumps production first.}"
: "${STAGING_DATABASE_URL:?Set STAGING_DATABASE_URL (staging Postgres public connection string, see scripts/.env.backup.example).}"

command -v psql >/dev/null 2>&1 || { echo "psql not found. Install the Postgres client (e.g. brew install libpq)." >&2; exit 1; }

host_port() {  # $1 = url — prints "host:port", lowercased, default port 5432
  URL="$1" python3 - <<'PY'
import os
from urllib.parse import urlparse
u = urlparse(os.environ["URL"])
print(f"{(u.hostname or '').lower()}:{u.port or 5432}")
PY
}

PROD_HP="$(host_port "$PROD_DATABASE_URL")"
STAGING_HP="$(host_port "$STAGING_DATABASE_URL")"
STAGING_HOST="${STAGING_HP%%:*}"

if [ "$PROD_HP" = "$STAGING_HP" ]; then
  echo "REFUSING: STAGING_DATABASE_URL points at the production server ($PROD_HP)." >&2
  echo "Staging must be its own Postgres service — check scripts/.env.backup." >&2
  exit 1
fi

# ---- 1. get a dump --------------------------------------------------------
DUMP="${1:-}"
if [ -z "$DUMP" ]; then
  echo "No dump given — taking a fresh production backup…"
  ./scripts/backup.sh
  DUMP="$(ls -1t "${BACKUP_DIR:-backups}"/*.dump | head -1)"
fi
[ -f "$DUMP" ] || { echo "Dump not found: $DUMP" >&2; exit 1; }

# ---- 2. restore into staging (restore.sh keeps its own guards) ------------
# The prod-mismatch check above already ran; passing the staging host via
# STAGING_HOSTS satisfies restore.sh's allowlist without weakening it —
# restore.sh independently re-checks the target against PROD_DATABASE_URL
# and still requires the typed DB-name confirmation.
LOCAL_DATABASE_URL="$STAGING_DATABASE_URL" \
STAGING_HOSTS="$STAGING_HOST" \
  ./scripts/restore.sh "$DUMP"

# ---- 3. anonymise the restored copy ---------------------------------------
echo "Anonymising staging (free text scrubbed, body data masked)…"
psql "$STAGING_DATABASE_URL" -v ON_ERROR_STOP=1 -q -f scripts/anonymise_staging.sql

echo
echo "Staging seeded from $DUMP and anonymised."
echo "If the staging branch has newer migrations than production, redeploy or"
echo "restart the staging service so its boot-time 'alembic upgrade head' runs."

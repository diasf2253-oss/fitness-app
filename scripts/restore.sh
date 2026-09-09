#!/bin/bash
# ---------------------------------------------------------------------------
# Restore a pg_dump archive into a LOCAL or STAGING Postgres. NEVER production.
#
#   ./scripts/restore.sh [path/to/dump]     # defaults to the newest backups/*.dump
#
# The target is read from LOCAL_DATABASE_URL (default: a localhost database).
# Two hard guards make it impossible to point this at production:
#
#   Guard 1 - host allowlist: the target host MUST be localhost / 127.0.0.1
#             (or a *staging* host); any other host aborts immediately, no prompt.
#   Guard 2 - anti-prod: if PROD_DATABASE_URL is set and shares the target's
#             host, it aborts. You can never restore onto the prod server.
#
# Only after both guards pass does it print a loud banner and require you to
# type the target database name to proceed. This DROPS and REPLACES that DB.
#
# Env:
#   LOCAL_DATABASE_URL  Target (default: postgresql://postgres:postgres@localhost:5432/fitness_local).
#   STAGING_HOSTS       Optional comma-separated extra hosts allowed as targets.
#   PROD_DATABASE_URL   If set, used only to double-check the target != prod host.
#   BACKUP_DIR          Where to look for the newest dump (default: backups).
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")/.."   # repo root

if [ -f scripts/.env.backup ]; then
  set -a; . scripts/.env.backup; set +a
fi

LOCAL_DATABASE_URL="${LOCAL_DATABASE_URL:-postgresql://postgres:postgres@localhost:5432/fitness_local}"

command -v pg_restore >/dev/null 2>&1 || { echo "pg_restore not found. Install the Postgres client (e.g. brew install libpq)." >&2; exit 1; }
command -v psql       >/dev/null 2>&1 || { echo "psql not found. Install the Postgres client (e.g. brew install libpq)." >&2; exit 1; }

# ---- pick the dump ---------------------------------------------------------
DUMP="${1:-}"
if [ -z "$DUMP" ]; then
  DUMP="$(ls -1t "${BACKUP_DIR:-backups}"/*.dump 2>/dev/null | head -1 || true)"
fi
if [ -z "$DUMP" ] || [ ! -f "$DUMP" ]; then
  echo "No dump file given and none found in ${BACKUP_DIR:-backups}/. Run ./scripts/backup.sh first." >&2
  exit 1
fi

# ---- parse the target URL (robust: Python's urllib, not string munging) ----
read_url() {  # $1 = url, $2 = field: host | dbname | redacted | maint
  URL="$1" FIELD="$2" python3 - <<'PY'
import os
from urllib.parse import urlparse, urlunparse
u = urlparse(os.environ["URL"])
field = os.environ["FIELD"]
host = (u.hostname or "").lower()
db = (u.path or "/").lstrip("/")
if field == "host":
    print(host)
elif field == "dbname":
    print(db)
elif field == "redacted":                       # never print the password
    net = host + (f":{u.port}" if u.port else "")
    print(f"{u.scheme}://***@{net}/{db}")
elif field == "maint":                           # same server, 'postgres' db
    print(urlunparse((u.scheme, u.netloc, "/postgres", "", u.query, "")))
PY
}

TARGET_HOST="$(read_url "$LOCAL_DATABASE_URL" host)"
TARGET_DB="$(read_url "$LOCAL_DATABASE_URL" dbname)"
TARGET_SHOWN="$(read_url "$LOCAL_DATABASE_URL" redacted)"

[ -n "$TARGET_HOST" ] || { echo "Could not parse a host from LOCAL_DATABASE_URL." >&2; exit 1; }
[ -n "$TARGET_DB" ]   || { echo "LOCAL_DATABASE_URL has no database name." >&2; exit 1; }

# ---- Guard 1: host allowlist ----------------------------------------------
is_safe_host() {
  case "$1" in
    localhost|127.0.0.1|::1|0.0.0.0) return 0 ;;
    *staging*)                        return 0 ;;
  esac
  if [ -n "${STAGING_HOSTS:-}" ]; then          # opt-in extra staging hosts
    IFS=',' read -ra _extra <<< "$STAGING_HOSTS"
    for h in "${_extra[@]}"; do [ "$1" = "$h" ] && return 0; done
  fi
  return 1
}
if ! is_safe_host "$TARGET_HOST"; then
  echo "REFUSING: target host '$TARGET_HOST' is not local or staging." >&2
  echo "restore.sh only writes to localhost, 127.0.0.1, or a *staging* host." >&2
  echo "If '$TARGET_HOST' really is a staging box, add it to STAGING_HOSTS." >&2
  exit 1
fi

# ---- Guard 2: never the same server as production -------------------------
if [ -n "${PROD_DATABASE_URL:-}" ]; then
  PROD_HOST="$(read_url "$PROD_DATABASE_URL" host || true)"
  if [ -n "$PROD_HOST" ] && [ "$PROD_HOST" = "$TARGET_HOST" ]; then
    echo "REFUSING: target host matches the PROD_DATABASE_URL host ('$PROD_HOST')." >&2
    exit 1
  fi
fi

# ---- loud confirmation -----------------------------------------------------
printf '\n'
printf '  ============================================================\n'
printf '   RESTORE - this DROPS and REPLACES the target database\n'
printf '  ============================================================\n'
printf '   Dump   : %s\n' "$DUMP"
printf '   Target : %s\n' "$TARGET_SHOWN"
printf '   Host   : %s   (local/staging - prod guard passed)\n' "$TARGET_HOST"
printf '  ============================================================\n'
printf '   Type the target database name (%s) to proceed: ' "$TARGET_DB"
read -r CONFIRM
if [ "$CONFIRM" != "$TARGET_DB" ]; then
  echo "Aborted - you typed '$CONFIRM', expected '$TARGET_DB'." >&2
  exit 1
fi

# ---- create the DB if missing, then restore --------------------------------
MAINT_URL="$(read_url "$LOCAL_DATABASE_URL" maint)"
if ! psql "$MAINT_URL" -Atqc "SELECT 1 FROM pg_database WHERE datname = '$TARGET_DB'" | grep -q 1; then
  echo "Creating database '$TARGET_DB'..."
  psql "$MAINT_URL" -c "CREATE DATABASE \"$TARGET_DB\""
fi

echo "Restoring into '$TARGET_DB'..."
pg_restore \
  --dbname="$LOCAL_DATABASE_URL" \
  --clean --if-exists \
  --no-owner --no-privileges \
  "$DUMP"

echo "Done. Restored $DUMP -> $TARGET_SHOWN"

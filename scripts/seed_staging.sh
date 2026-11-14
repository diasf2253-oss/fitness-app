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
# free text (journal entries, notes) never sits in staging, body/health
# numbers are masked while every trend stays realistic, and no production
# credential survives: non-admin emails/names rewritten, every password reset
# to STAGING_USER_PASSWORD, ingest tokens regenerated, sessions deleted,
# invite codes regenerated and deactivated.
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
#   STAGING_USER_PASSWORD  Password EVERY staging account gets after the scrub,
#                          admin included (required, 12+ chars, staging-only).
#                          Hashed locally with argon2; only the hash is sent.
#   BACKUP_DIR             Where dumps land (default: backups).
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")/.."   # repo root

if [ -f scripts/.env.backup ]; then
  set -a; . scripts/.env.backup; set +a
fi

: "${PROD_DATABASE_URL:?Set PROD_DATABASE_URL (prod public connection string) — seed_staging dumps production first.}"
: "${STAGING_DATABASE_URL:?Set STAGING_DATABASE_URL (staging Postgres public connection string, see scripts/.env.backup.example).}"
: "${STAGING_USER_PASSWORD:?Set STAGING_USER_PASSWORD (the password every staging account gets after the scrub, see scripts/.env.backup.example).}"
if [ "${#STAGING_USER_PASSWORD}" -lt 12 ]; then
  echo "STAGING_USER_PASSWORD must be at least 12 characters — staging is reachable from the internet." >&2
  exit 1
fi

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

# ---- 0. hash the staging password (before touching any database) ---------
# Same argon2 defaults as app/auth.py's PasswordHasher(), so the app verifies
# it like any other hash. Prefers the backend venv (has argon2-cffi). The
# password reaches Python via the environment, not argv, so `ps` can't see it.
HASH_PY=python3
[ -x backend/.venv/bin/python ] && HASH_PY=backend/.venv/bin/python
STAGING_PW_HASH="$(STAGING_USER_PASSWORD="$STAGING_USER_PASSWORD" "$HASH_PY" - <<'PY'
import os, sys
try:
    from argon2 import PasswordHasher
except ImportError:
    sys.exit("argon2-cffi is not installed for this Python — run ./start.sh once (creates backend/.venv) or pip install argon2-cffi.")
print(PasswordHasher().hash(os.environ["STAGING_USER_PASSWORD"]))
PY
)"

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
# One transaction: it either fully scrubs or changes nothing. The restore has
# already happened, so a failure here leaves staging holding an UNSCRUBBED
# production copy — say so loudly rather than exiting quietly.
echo "Anonymising staging (free text scrubbed, body data masked, credentials replaced)…"
if ! psql "$STAGING_DATABASE_URL" -v ON_ERROR_STOP=1 -v staging_pw_hash="$STAGING_PW_HASH" \
       -q -f scripts/anonymise_staging.sql; then
  echo >&2
  echo "!! ANONYMISATION FAILED — staging now holds an UNSCRUBBED production copy" >&2
  echo "!! (real emails, password hashes, ingest tokens, live session ids)." >&2
  echo "!! Fix the error above and re-run ./scripts/seed_staging.sh $DUMP now," >&2
  echo "!! or stop the staging service until you can." >&2
  exit 1
fi

echo
echo "Staging seeded from $DUMP and anonymised."
echo "Every account's password is now STAGING_USER_PASSWORD — log in as the admin"
echo "with its usual email, or as anyone else with user<id>@example.test."
echo "If the staging branch has newer migrations than production, redeploy or"
echo "restart the staging service so its boot-time 'alembic upgrade head' runs."

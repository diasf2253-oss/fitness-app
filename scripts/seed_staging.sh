#!/bin/bash
# ---------------------------------------------------------------------------
# Refresh staging with an anonymised copy of production.
#
#   ./scripts/seed_staging.sh
#
# Copies PROD_DATABASE_URL → STAGING_DATABASE_URL (both from
# scripts/.env.backup), replacing staging's rows, then scrubs personal data
# with scripts/anonymise_staging.sql. Production is only ever READ.
# Guards (it refuses to write to production, or to anything that isn't a
# Supabase database) live in backend/app/cli/copy_database.py.
#
# After a refresh, sign in to staging with a STAGING Supabase login: the
# admin keeps its email and links on first sign-in; everyone else is
# user<id>@example.test.
# ---------------------------------------------------------------------------
set -euo pipefail
cd "$(dirname "$0")/.."   # repo root
. scripts/lib.sh
[ -x backend/.venv/bin/python ] || { echo "backend/.venv missing — run ./start.sh once first." >&2; exit 1; }
cd backend
exec .venv/bin/python -m app.cli.copy_database --from prod --to staging

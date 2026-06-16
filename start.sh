#!/bin/bash
# ---------------------------------------------------------------------------
# One command to run the whole app for daily use.
#
#   ./start.sh
#
# It builds the frontend, applies any new migrations, seeds defaults (safe to
# re-run), then serves everything on one origin bound to 0.0.0.0 so your phone
# can reach it over Wi-Fi. Leave the window open — that's the app being "on".
#
# Flags:
#   --no-build   skip the frontend build (faster restarts when only backend changed)
# ---------------------------------------------------------------------------
set -e
cd "$(dirname "$0")"

BUILD=1
for arg in "$@"; do
  [ "$arg" = "--no-build" ] && BUILD=0
done

# Put nvm's Node on PATH so `npm` is found from a fresh Terminal.
if ! command -v npm >/dev/null 2>&1; then
  export NVM_DIR="$HOME/.nvm"
  # shellcheck disable=SC1091
  [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh"
fi

# 1. Frontend → static bundle the backend will serve
if [ "$BUILD" -eq 1 ]; then
  echo "Building the app…"
  ( cd frontend && { [ -d node_modules ] || npm install; } && npm run build >/dev/null )
fi

# 2. Backend: venv, deps, DB
cd backend
if [ ! -d .venv ]; then
  echo "Creating Python virtualenv…"
  python3 -m venv .venv
  ./.venv/bin/pip install -q -r requirements.txt
fi
[ -f .env ] || cp .env.example .env

echo "Updating the database…"
./.venv/bin/alembic upgrade head >/dev/null
./.venv/bin/python -m app.seed >/dev/null 2>&1 || true

# 3. Friendly banner with the two URLs you actually need
LAN_IP="$(ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || true)"
TOKEN="$(grep -E '^APP_TOKEN=' .env | head -1 | cut -d= -f2-)"
if [ -n "$LAN_IP" ]; then PHONE="http://$LAN_IP:8000"; else PHONE="(not on Wi-Fi — connect to the same network to sync)"; fi
printf '\n'
printf '  ════════════════════════════════════════════════════\n'
printf '   Tracker is running\n'
printf '  ════════════════════════════════════════════════════\n'
printf '   This laptop:  http://localhost:8000\n'
printf '   This phone:   %s\n' "$PHONE"
printf '\n'
printf '   Open the laptop URL, then Settings → "Add a device"\n'
printf '   to onboard your phone by scanning a QR.\n'
printf '  ════════════════════════════════════════════════════\n'
printf '   Token: %s    ·    Ctrl-C to stop\n\n' "$TOKEN"

# 4. Serve (0.0.0.0 = reachable from the phone). --reload off for steady use.
exec ./.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000

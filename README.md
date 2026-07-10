# Personal Fitness & Health App

A single-user life tracker: workout logging, health & nutrition dashboard,
with Apple Health as the single source for all health data.

## Status

- **Phase 0** — Project skeleton (FastAPI + Vite/React + Alembic). ✅
- **Phase 1** — Workout tracker: exercise library, routine templates, live session
  logging with rest timer and prefill, history, and per-exercise progress charts
  (estimated 1RM + volume) with PR detection. ✅
- **Phase 2** — Health & nutrition data layer + Dashboard v1: weight / steps /
  sleep / nutrition tables with date-keyed upserts, manual logging UI,
  one-call dashboard endpoint, sample-data utility. ✅
- **Phase 3** — Full Apple Health ingest: weight, steps, sleep, and nutrition
  down to micronutrients via Health Auto Export pushes, plus a one-time
  export.zip history backfill. Manual corrections always beat synced data.
  YAZIO writes into Apple Health on the phone, so **YAZIO is not integrated
  directly — and never will be**. ✅
- **Phase 4** — Desktop experience: workspace sidebar at ≥1024px, dashboard
  widget grid, right-rail month calendar with data markers and per-day
  detail (`GET /api/calendar/{year}/{month}`, `GET /api/day/{date}`). Phone
  layout unchanged; both devices share the same backend, so they are always
  in sync. ✅ (4a/4b — desktop polish of remaining pages ongoing)
- **Phase 5** — Always-on + installable PWA: single-origin serving (FastAPI
  hosts the built frontend — one URL for app, PWA, and Health Auto Export),
  manifest + cairn icons + minimal service worker, Dockerfile, and deploy
  paths for a home Mac with Cloudflare Tunnel or Railway. See
  [docs/DEPLOY.md](docs/DEPLOY.md). ✅
- **Phase 6** — Life domains: generic trackers (habit with streaks, 1–5
  scale, number with unit, text) under `/api/trackers`, seeded Mood +
  Journal, daily check-in card on the dashboard, management in Settings,
  calendar + day-detail integration. ✅
- **Phase 7** — Insights: weekly review (this week vs last across training,
  steps, sleep, nutrition, weight, scale trackers, habits), 90-day Pearson
  correlations with scatter detail (pairs need ≥10 overlapping days), and
  scale-tracker averages on training vs rest days. `/api/insights/*`. ✅
- **Phase 8** — AI Coach (Claude): streaming chat plus one-tap planners
  (next workout / day / study) that reason over your training, health, and
  habits and return a proposal you approve before anything is saved —
  workouts become routines, day/study plans become trackable plan items.
  New `plan_item` domain (checkable, on the dashboard + calendar) and
  `/api/coach/*` + `/api/plan/*`. Needs `ANTHROPIC_API_KEY`; without it the
  Coach shows a setup note and the rest of the app is unaffected. ✅
- **Phase 9+** — Desktop polish of remaining pages (4c); whatever we decide
  to track next. _Planned._

---

## Prerequisites

- Python 3.12+
- Node.js 20+
- (Optional, Phase 3) `cloudflared` or `ngrok` for Apple Health remote ingest

---

## Quick start

For everyday use, one command builds the frontend, migrates + seeds the DB, and
serves everything on one origin reachable by your phone:

```bash
./start.sh
```

It prints the laptop URL and the phone URL. Open the laptop URL, then
**Settings → Add a device** to onboard your phone by scanning a QR (it opens
already signed in). Full walkthrough: [docs/TUTORIAL.md](docs/TUTORIAL.md).

The manual steps below are for first-time setup or development.

---

## Setup

### 1. Clone & configure environment

```bash
cd fitness-app

# Copy and fill in your secrets
cp backend/.env.example backend/.env
# Edit backend/.env: set APP_TOKEN
```

### 2. Backend

```bash
cd backend

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run database migrations (creates fitness.sqlite3 and all tables)
alembic upgrade head

# Seed the exercise library, routine templates, and default settings
python -m app.seed

# Start the API server (runs on http://localhost:8000)
uvicorn app.main:app --reload --port 8000
```

### 3. Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start the dev server (runs on http://localhost:5173)
npm run dev
```

Open http://localhost:5173 in your browser.

---

## Running tests

```bash
cd backend
source .venv/bin/activate
pytest tests/ -v
```

---

## API overview

All routes require `Authorization: Bearer <APP_TOKEN>` except `/api/ping`.

### Dashboard

| Route | Purpose |
| --- | --- |
| `GET /api/dashboard` | Everything the home screen needs in one call: weight (90 d series + 7-day moving average), steps (14 d), sleep (14 d), today's nutrition + targets, this week's training volume and recent PRs. Every section returns sensible empty values when no data exists. |

### Health & nutrition (Phase 2)

One row per date; POSTs are **idempotent upserts by date** (re-posting a date
updates it). Manual entries write `source='manual'`; the Apple Health ingest
writes `source='apple_health'`. **Precedence:** a manually corrected day is
only ever replaced by another manual write — syncs and sample data can't
overwrite it (rule lives in the upsert helpers in `routers/health.py`).
Nutrition rows carry a `micros` JSON column with canonical unit-suffixed
keys (`fiber_g`, `sodium_mg`, `vitamin_d_ug`, …).

| Route | Purpose |
| --- | --- |
| `GET /api/health/weight?days=N` | Weight series (default 90) |
| `POST /api/health/weight` | Log/correct a day's weight |
| `GET /api/health/steps?days=N` | Steps series (default 14) |
| `POST /api/health/steps` | Log/correct a day's steps |
| `GET /api/health/sleep?days=N` | Sleep series (default 14) |
| `POST /api/health/sleep` | Log/correct a night's sleep |
| `GET /api/health/nutrition?days=N` | Nutrition series (default 30) |
| `GET /api/nutrition?days=N` / `POST /api/nutrition` | Same table, original route |

### Sample data (dev utility)

Preview the dashboard before real data exists. Rows are tagged
`source='sample'`, so clearing never touches manual or synced data.
The UI buttons live under **Settings → Developer**.

```bash
# Load ~30 days of realistic weight/steps/sleep/nutrition (idempotent)
curl -X POST http://localhost:8000/api/dev/seed-sample-health \
  -H "Authorization: Bearer changeme"

# Remove exactly the seeded rows
curl -X DELETE http://localhost:8000/api/dev/seed-sample-health \
  -H "Authorization: Bearer changeme"
```

### Workouts (Phase 1)

Exercises, routines, sessions, sets, and stats live under `/api/exercises`,
`/api/routines`, `/api/sessions`, and `/api/stats/*` — see the routers in
`backend/app/routers/` or the auto-generated docs at http://localhost:8000/docs.

---

## Apple Health ingest (Phase 3)

All health **and nutrition** data arrives via Apple Health: YAZIO syncs food
(including micronutrients) into Apple Health on the phone, Apple Health pushes
to this backend. There is no YAZIO integration and no YAZIO credentials.

### Daily push — Health Auto Export

Set up the **Health Auto Export** iOS app (healthyapps.dev) once; the in-app
instructions also live under Settings → Apple Health sync.

1. Open Health Auto Export → Automations → Add Automation
2. **Export format**: JSON
3. **URL**: `http://<your-tunnel-url>/api/ingest/health`
4. **Method**: POST
5. **Headers**: `Authorization: Bearer <your APP_TOKEN from .env>`
6. **Metrics**: `step_count`, `weight_body_mass`, `sleep_analysis`, plus the
   dietary ones you track — `dietary_energy`, `protein`, `carbohydrates`,
   `total_fat`, `fiber`, `sugar`, `sodium`, `cholesterol`, vitamins and
   minerals (see `HAE_NUTRITION` in `backend/app/health_metrics.py` for the
   full list). Units are normalized on ingest (kJ→kcal, g/mg/µg).
7. **Schedule**: Daily (e.g. every morning)

Your phone must be able to reach your Mac:

```bash
# Option A: cloudflared (free, no account needed for quick tunnels)
cloudflared tunnel --url http://localhost:8000

# Option B: ngrok
ngrok http 8000
```

Test without a phone using the sample payload (idempotent — re-running adds
no duplicate rows):

```bash
curl -X POST http://localhost:8000/api/ingest/health \
  -H "Authorization: Bearer changeme" \
  -H "Content-Type: application/json" \
  -d @backend/tests/sample_health_payload.json
```

### History backfill — export.zip

Import your entire Apple Health history once: Health app → profile picture →
**Export All Health Data**, then upload the resulting `export.zip` under
Settings → Apple Health sync → History backfill (or POST it to
`/api/ingest/health-export` as multipart `file`). The XML is stream-parsed,
so multi-hundred-MB exports are fine.

De-duplication: overlapping sources (iPhone + Watch both counting steps,
multiple sleep writers) are totalled per source and the highest single
source wins each day — no double counting. Weight takes the day's last
reading; sleep intervals attribute to the wake-up morning; nutrition keeps
the best source per day. Re-importing is idempotent, and manually corrected
days are never overwritten.

---

## Database backups (production Postgres)

Production runs on a Railway **Postgres** service (local dev still uses SQLite —
see `backend/.env.example`). Two scripts back it up to a local file and restore
that file into a **local or staging** Postgres. Credentials are never hardcoded:
the connection string comes from the environment.

```bash
# 1. Dump production -> backups/fitness_prod_<timestamp>.dump
./scripts/backup.sh

# 2. Load the newest dump into your LOCAL Postgres (asks you to confirm)
./scripts/restore.sh
```

### Configure

Prefer a git-ignored secrets file so you don't export vars every shell:

```bash
cp scripts/.env.backup.example scripts/.env.backup
# edit scripts/.env.backup — never commit it
```

| Variable | Used by | Meaning |
| --- | --- | --- |
| `PROD_DATABASE_URL` | backup | Railway **public** connection string (the `*.proxy.rlwy.net:PORT` one). |
| `LOCAL_DATABASE_URL` | restore | Target DB. Default `postgresql://postgres:postgres@localhost:5432/fitness_local`. Created if missing. |
| `STAGING_HOSTS` | restore | Optional comma-separated extra hosts allowed as restore targets. |
| `BACKUP_DIR` | both | Where dumps live. Default `backups/` (git-ignored — dumps hold real personal data). |

`scripts/backup.sh` writes a compressed `pg_dump` custom-format archive;
`scripts/restore.sh` loads it with `pg_restore --clean --if-exists`.

### restore.sh can never hit production

Before it does anything, restore refuses unless the target **host** is
`localhost`, `127.0.0.1`, or a `*staging*` host (extend via `STAGING_HOSTS`) —
any remote host aborts with no prompt. It also refuses if the target shares a
host with `PROD_DATABASE_URL`. Only then does it print a banner and require you
to type the target database name. There is no flag to restore into production.

### Prerequisites

- The Postgres client tools on PATH: `pg_dump`, `pg_restore`, `psql`
  (`brew install libpq` and add its `bin` to PATH, or `brew install postgresql@16`).
  Use a client whose major version is **>= the Railway server's** (PG 16).
- A local Postgres running for restore (e.g. `brew services start postgresql@16`).

### What you must do in Railway (one-time)

1. Open the Railway dashboard → your project → the **Postgres** service.
2. Go to the **Variables** tab (or **Connect** → *Public Network*) and copy
   `DATABASE_PUBLIC_URL` — the **public** string whose host is
   `<name>.proxy.rlwy.net:<port>`. Do **not** use `DATABASE_URL` /
   `postgres.railway.internal`; that host only resolves inside Railway and your
   laptop can't reach it.
3. If the string has no `?sslmode=`, append `?sslmode=require` (Railway serves
   Postgres over TLS).
4. Put it in `scripts/.env.backup` as `PROD_DATABASE_URL=...` (git-ignored) —
   never commit it or paste it into the repo.
5. **IP allowances: nothing to configure.** Railway's public Postgres proxy is
   reachable from any IP and is protected only by the credentials in the URL, so
   there is no allowlist to edit — just keep the URL secret. (Rotate it from the
   Postgres service's settings if it ever leaks. If you later enable private
   networking / restricted egress, that's the only case where you'd need to
   permit your IP.)
6. Confirm the Postgres major version (service → **Deployments**/metadata) and
   install a matching-or-newer client locally so `pg_dump` won't refuse on a
   version mismatch.

## Environment variables

See `backend/.env.example` for the app (`APP_TOKEN`, `DATABASE_URL`,
`ANTHROPIC_API_KEY`). Backup/restore vars live in `scripts/.env.backup.example`
(see [Database backups](#database-backups-production-postgres) above).

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

---

## Prerequisites

- Python 3.12+
- Node.js 20+
- (Optional, Phase 3) `cloudflared` or `ngrok` for Apple Health remote ingest

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

## Environment variables

See `backend/.env.example` — just `APP_TOKEN` and `DATABASE_URL`.

# Personal Fitness & Health App

A single-user fitness tracker with workout logging, Apple Health ingest, and YAZIO nutrition sync.

## Status

- **Phase 0** — Project skeleton (FastAPI + Vite/React + Alembic). ✅
- **Phase 1** — Workout tracker: exercise library, routine templates, live session
  logging with rest timer and prefill, history, and per-exercise progress charts
  (estimated 1RM + volume) with PR detection. ✅
- **Phase 2+** — Manual health/nutrition entry, dashboard, Apple Health ingest, YAZIO
  sync. _Planned (endpoints below are scaffolding)._

---

## Prerequisites

- Python 3.12+
- Node.js 20+
- (Optional) `cloudflared` or `ngrok` for Apple Health remote ingest

---

## Setup

### 1. Clone & configure environment

```bash
cd fitness-app

# Copy and fill in your secrets
cp backend/.env.example backend/.env
# Edit backend/.env: set APP_TOKEN, YAZIO_EMAIL, YAZIO_PASSWORD
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

## Apple Health ingest (Health Auto Export)

### How it works

Install the **Health Auto Export** iOS app (healthyapps.dev). Configure an automation to POST your Apple Health data to this backend.

### Configuration steps

1. Open Health Auto Export → Automations → Add Automation
2. **Export format**: JSON
3. **URL**: `http://<your-tunnel-url>/api/ingest/health`
4. **Method**: POST
5. **Headers**: `Authorization: Bearer <your APP_TOKEN from .env>`
6. **Metrics to select** (at minimum):
   - `step_count`
   - `weight_body_mass`
   - `sleep_analysis`
7. **Schedule**: Daily (e.g. every morning)

### Tunnel (so your phone can reach your Mac)

Your phone and Mac must be reachable from the same URL. Use one of:

```bash
# Option A: cloudflared (free, no account needed for quick tunnels)
cloudflared tunnel --url http://localhost:8000

# Option B: ngrok
ngrok http 8000
```

Copy the generated HTTPS URL and use it as the base in Health Auto Export.

### Test without your phone

A sample payload is at `backend/tests/sample_health_payload.json`. Test with:

```bash
curl -X POST http://localhost:8000/api/ingest/health \
  -H "Authorization: Bearer changeme" \
  -H "Content-Type: application/json" \
  -d @backend/tests/sample_health_payload.json
```

Re-running the same curl should produce no duplicate rows (idempotent).

---

## YAZIO sync

With `YAZIO_EMAIL` and `YAZIO_PASSWORD` set in `.env`, trigger a manual sync:

```bash
# Sync last 3 days (default)
curl -X POST http://localhost:8000/api/sync/yazio \
  -H "Authorization: Bearer changeme"

# Sync last 7 days
curl -X POST "http://localhost:8000/api/sync/yazio?days=7" \
  -H "Authorization: Bearer changeme"
```

An APScheduler job runs automatically at 23:30 local time each day, syncing the last 2 days.

---

## Environment variables

See `backend/.env.example` for all required variables.

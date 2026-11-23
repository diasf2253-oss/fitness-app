# Tracker

**A quiet, self-hosted body-recomposition tracker.** Log workouts in the gym,
let Apple Health push in your weight, steps, sleep and food, and get an adaptive
calorie target that moves with your actual weekly trend. It's an installable,
offline-first PWA backed by FastAPI.

[![CI](https://github.com/diasf2253-oss/fitness-app/actions/workflows/ci.yml/badge.svg)](https://github.com/diasf2253-oss/fitness-app/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-a8bfa1.svg)](LICENSE)
![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-3776ab.svg)
![React 18](https://img.shields.io/badge/react-18-61dafb.svg)

![Dashboard on desktop](.github/assets/screenshots/dashboard-desktop.png)

<table>
  <tr>
    <td><img src=".github/assets/screenshots/workout-mobile.png" alt="Logging a workout on a phone" width="300"></td>
    <td><img src=".github/assets/screenshots/diet-mobile.png" alt="Adaptive diet target on a phone" width="300"></td>
  </tr>
</table>

<sub>Screenshots use invented demo data.</sub>

---

## Why this exists

Most fitness apps are either a gym logger or a calorie counter, and they're
loud about it. This one is built around a single loop — **train → weigh in →
eat → adjust** — and tries to make that loop legible with as little manual
effort as possible.

The design rules, in priority order:

1. **Body recomposition first.** The weight / diet / energy loop is the core.
   A quantified-self lab (sleep, habits, correlations) comes second, the gym
   logger third, gamification last — nice, never load-bearing.
2. **Honest numbers.** Correlations print their sample size, small samples are
   declared, invented demo data can never report itself as real, and a day you
   corrected by hand is never overwritten by a sync.
3. **Quiet design.** Deep green-charcoal, bone ink, serif display type — no
   confetti, no streak-shaming (see [DESIGN.md](DESIGN.md) and [PRODUCT.md](PRODUCT.md)).
4. **Never complicated.** Big thumb targets in the gym; the daily check-in
   takes under 20 seconds.

## Features

**Training**
- Live workout logging with a rest timer, previous numbers prefilled, and
  per-set weight / reps / RIR.
- Routines grouped into **splits**, with ready-made split templates and a
  **workout generator** that builds a whole program from a few inputs.
- Per-exercise progress charts — estimated 1RM (Epley, reps capped at 12) and
  volume — with automatic PR detection.
- **Ranks**: a tier per lift (Wood → Olympian, 9 tiers × 3 divisions) from your
  best estimated 1RM relative to bodyweight, plus a hand-drawn muscle body map.
- Weekly volume targets per muscle group, and a streak that counts workouts,
  sport sessions, or 10k-step days.

![Ranks: a strength tier per muscle group on the body map](.github/assets/screenshots/ranks-desktop.png)

**Body & diet**
- **Adaptive calorie target**: starts from an anchor and moves one step per
  completed week toward your goal (a signed slider from −0.5 to +0.5 kg/week:
  cut, maintain or bulk), bounded by a floor and an estimated-maintenance
  ceiling.
- Manual protein and fat targets, flexible carbs, activity burn, and a
  micronutrient breakdown against daily recommendations.
- Weight trend with a 7-day moving average.

**Health data**
- **Apple Health via an iOS Shortcut.** A web app can't read HealthKit, so the
  phone pushes weight, steps and sleep daily — plus a one-tap *Sync now*
  button. See `notes/runbooks/HEALTH_INGEST_SHORTCUT.md`.
- One-time history import from Apple Health's `export.zip`, streamed so
  multi-hundred-MB exports are fine; iPhone + Watch overlaps are de-duplicated.
- Health Auto Export support for nutrition and micronutrients.
- Freshness tracking per metric, with a stale-data banner.

![Weight trend with 7-day average, steps and sleep](.github/assets/screenshots/trends-desktop.png)

**Insight**
- Weekly review (this week vs last) and 90-day correlations between your
  numbers, shown only with enough overlapping days.
- Weekly / biweekly **report**, downloadable as Markdown, with an optional
  AI-written plan (Claude).
- Simple trackers (habits, 1–5 scales, numbers, a journal line) and a month
  calendar with per-day detail.

**Platform**
- **Offline-first PWA**: the installed phone app keeps its own IndexedDB copy
  and syncs when it has signal — it works in a basement gym.
- **Invite-only multi-user**: invite codes, admin approval, admin-issued
  temporary passwords; every row is scoped to its owner on the server.
- Mobile-first for the gym, a sidebar + widget layout on desktop.

## How it works

```mermaid
flowchart LR
  subgraph phone["iPhone"]
    PWA["Installed PWA<br/>React + Vite"] --- IDB[("IndexedDB<br/>(Dexie)")]
    SC["iOS Shortcut<br/>Tracker Health Sync"]
  end
  Desk["Desktop browser"] -->|"REST · Bearer access token"| API
  Desk & PWA -.->|"sign in"| Auth["Supabase Auth"]
  PWA <-->|"sync · last-write-wins by updated_at"| API["FastAPI<br/>API + built frontend"]
  SC -->|"POST /api/ingest/health/shortcut<br/>Bearer ingest_token"| API
  API --> DB[("Postgres on Supabase (prod)<br/>SQLite (dev)")]
  API -.->|optional| Claude["Claude API"]
```

- **One origin.** FastAPI serves both the API and the built React app, so the
  PWA, the desktop browser and the Shortcut all talk to one URL.
- **Local-first sync.** In production builds the frontend's API calls are
  answered by an on-device twin of the backend (`frontend/src/local/`), and a
  sync engine (`backend/app/services/sync.py`) merges rows — entities by `uuid`, health
  days by date — last-write-wins, with manual entries beating synced ones.
  The ported math is tested in both languages to stay identical.
- **Two kinds of auth.** People sign in through **Supabase Auth** (email +
  password or Google) and send its signed access token with every request;
  the backend verifies it and then applies its own rules — invite code, admin
  approval, per-user data. The Health Shortcut can't run a sign-in, so it
  sends a per-user, rotatable `ingest_token` instead. Setup:
  `notes/runbooks/SUPABASE.md`.
- **One ingest core.** The Shortcut, Health Auto Export, and the `export.zip`
  backfill all go through `app/services/health/ingest.py` — unit conversion, wake-date
  sleep bucketing, per-source de-duplication, idempotent upserts.

## Tech stack

| Layer | Tools |
|---|---|
| Backend | Python, FastAPI, SQLAlchemy 2, Pydantic v2, Alembic, PyJWT |
| Auth | Supabase Auth (email + password, Google) |
| Database | SQLite (local dev) · PostgreSQL on Supabase (production) |
| Frontend | React 18, Vite, React Router, Recharts, Dexie (IndexedDB) |
| PWA | Web app manifest + a versioned service worker precaching the app shell |
| AI (optional) | Anthropic Claude API |
| Tests & CI | pytest, Vitest + Testing Library, GitHub Actions |
| Hosting | Vercel (frontend + API in one project) · Supabase (sign-in + Postgres) |

## Getting started

**Prerequisites:** Python 3.12+ and Node.js 20+.

### Quick start — one command

```bash
git clone https://github.com/diasf2253-oss/fitness-app.git
cd fitness-app
./start.sh
```

This builds the frontend, creates a virtualenv, copies `backend/.env.example`
to `backend/.env`, runs migrations, creates the admin account and an invite
code, and serves everything at **http://localhost:8000** (and on your Wi-Fi for
a phone). The first run stops until you set `ADMIN_EMAIL` in `backend/.env`.
Signing in needs a Supabase project: put its values in `backend/.env` and
`frontend/.env.local` (see `notes/runbooks/SUPABASE.md`), then create
your login with the admin email — it links to the admin account
automatically. A friendly walkthrough lives in
`notes/runbooks/TUTORIAL.md`.

### Manual setup (for development)

```bash
# Backend — http://localhost:8000 (interactive API docs at /docs)
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # then set ADMIN_EMAIL + the SUPABASE_* values
alembic upgrade head          # create / upgrade the database
python -m app.cli.seed_admin      # admin account + first invite code
python -m app.cli.seed            # exercise library, routines, default settings
uvicorn app.main:app --reload

# Frontend — http://localhost:5173 (proxies /api to :8000)
cd frontend
cp .env.example .env.local    # then set the VITE_SUPABASE_* values
npm install
npm run dev
```

`npm run dev` runs in server mode (every call hits the API); production builds
default to local-first. Force either per device with `?local=1` or
`localStorage.local_first`.

## Configuration

Backend settings come from environment variables or `backend/.env`
(see [`backend/.env.example`](backend/.env.example) and
[`backend/app/core/config.py`](backend/app/core/config.py)).

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | `sqlite:///./fitness.sqlite3` | Any SQLAlchemy URL; a bare `postgresql://` URL is routed to psycopg 3 |
| `SUPABASE_URL` | — | The Supabase project (`https://<ref>.supabase.co`); empty ⇒ signed-in routes answer 503 |
| `SUPABASE_PUBLISHABLE_KEY` | — | Publishable (or legacy anon) key — used to confirm an email is verified |
| `SUPABASE_SECRET_KEY` | — | Optional, server-only: enables the admin's password *Reset link* |
| `ADMIN_EMAIL` | — | The first admin account (`python -m app.cli.seed_admin`); its owner signs in through Supabase with this email |
| `AUTH_RATE_LIMIT_ENABLED` | `true` | Brute-force speed bump on signup (`/api/auth/join`); Supabase limits sign-in |
| `APP_ENV` | `production` | Set `staging` to show the STAGING badge |
| `CORS_ORIGINS` / `CORS_ALLOW_ORIGIN_REGEX` | — | Only for cross-origin frontends (e.g. Vercel previews) |
| `ENABLE_DEV_SEED` | `false` | Allow the admin to load invented demo health data — never in production |
| `ANTHROPIC_API_KEY` | — | Enables the AI report narrative; without it those endpoints return 503 |
| `COACH_MODEL` | `claude-opus-4-8` | Claude model for the AI features |

Frontend build-time variables (Vite):

| Variable | Purpose |
|---|---|
| `VITE_SUPABASE_URL` / `VITE_SUPABASE_PUBLISHABLE_KEY` | The Supabase project the app signs in with (public values) |
| `VITE_LOCAL_FIRST` | `1` (production default) = offline-first on-device API; `0` = thin client |
| `VITE_API_BASE_URL` | Point a separately hosted frontend at an API origin |
| `VITE_APP_ENV` | `staging` bakes in the STAGING badge |
| `VITE_HEALTH_SHORTCUT_URL` | iCloud link to the shared Health Shortcut |

## Tests

```bash
cd backend && pytest          # in-memory SQLite; never touches your database
cd frontend && npm test       # Vitest: ported math, sync, and input handling
```

`backend/tests/test_safety_net.py` is the short list that must never break:
auth, weight entry, workout logging, the calorie anchor, and the Apple Health
import. [CI](.github/workflows/ci.yml) runs both suites on every pull request.

## Deployment

- **`notes/runbooks/VERCEL.md`**: production and per-branch previews on one
  Vercel project (frontend + API); **`notes/runbooks/SUPABASE.md`**: sign-in
  and the database, one Supabase project per environment.
- **`notes/runbooks/STAGING.md`**: the staging environment and the
  feature → staging → `main` promotion flow.

### Database security

The app's tables live in a Supabase Postgres, but the browser never talks to
them: every read and write goes through the API, which checks who you are and
returns only your own rows. Supabase's built-in Data API (reachable with the
public key the frontend uses for sign-in) is shut out of every table by
migration `e1f3a5c7b9d2`: Row Level Security on, no grants to the public
roles — and tables added later start with no grants either.

### Database scripts

Connection strings are never hardcoded — they come from a git-ignored
`scripts/.env.backup` (copy [`scripts/.env.backup.example`](scripts/.env.backup.example)).

```bash
./scripts/backup.sh         # pg_dump production → backups/fitness_prod_<timestamp>.dump
./scripts/restore.sh        # load the newest dump into a LOCAL Postgres
./scripts/seed_staging.sh   # refresh staging with an anonymised copy of production
```

| Variable | Used by | Meaning |
| --- | --- | --- |
| `PROD_DATABASE_URL` | backup, seed_staging | Production Supabase, **Session pooler** string (port 5432) |
| `STAGING_DATABASE_URL` | seed_staging | Staging Supabase, Session pooler string |
| `LOCAL_DATABASE_URL` | restore | Target DB. Default `postgresql://postgres:postgres@localhost:5432/fitness_local` |
| `BACKUP_DIR` | backup, restore | Where dumps live. Default `backups/` (git-ignored — dumps hold real personal data) |

**Nothing here can overwrite production.** `restore.sh` only writes to a
local database (it refuses any other host and makes you type the database
name). `seed_staging.sh` (`app/cli/copy_database.py`) refuses the production
project, refuses anything that isn't Supabase, and scrubs personal data from
the copy. You need the Postgres client tools (`pg_dump`, `pg_restore`, `psql`)
at a major version ≥ the server's for backup/restore.

## Project structure

```
backend/
  app/
    main.py            FastAPI app; mounts routers, serves the built frontend
    models.py          SQLAlchemy models — every data table carries user_id
    schemas.py         Pydantic request/response models
    core/              plumbing: settings, database, Supabase sign-in, rate limit
    routers/           thin HTTP endpoints, one module per feature
    services/          business logic, no HTTP — health/, training/, diet/,
                       plus sync, report, insights, user settings
    cli/               run-once scripts (python -m app.cli.seed_admin, …)
  alembic/             database migrations
  tests/               pytest suite (incl. test_safety_net.py)
frontend/
  src/pages/           screens (Dashboard, Workout, Diet, Ranks, …)
  src/components/      ui/ (generic), health/, training/ building blocks
  src/auth/            sign-in state + auth screens
  src/lib/             API client, env detection, number/audio/chart helpers
  src/local/           offline-first twin of the API + sync client
  public/              PWA manifest, icons, service worker
  dev/                 dev-only helpers (iPhone-frame preview)
scripts/               backup / restore / staging refresh / one-time move to Supabase
```

The one architectural rule: **routers call services; routers never import
other routers.** Shared logic always lives in `backend/app/services/`.

Maintainer runbooks (deploy, staging, Supabase setup, the Health Shortcut
recipe) live in a private, git-ignored `notes/` folder and are not published.

## Built with Claude Code

This app was built by a non-developer learning software engineering, pairing
with [Claude Code](https://claude.com/claude-code). The working setup is part
of the repo:

- [`CLAUDE.md`](CLAUDE.md) — the project memory: locked conventions and
  architecture notes the agent reads every session.
- [`.claude/agents/`](.claude/agents) — a `builder` and an independent
  `reviewer` agent.
- [`.claude/commands/`](.claude/commands) — `/plan-feature` (write the spec
  first) and `/ship` (tests → review → pull request, only with a human's yes).
- `notes/runbooks/DEV_HANDBOOK.md` — the Plan → Build → Verify →
  Ship ritual and a plain-English glossary.

## Contributing & security

This is a personal project, so there's no roadmap for outside contributions,
but issues and ideas are welcome. Please report vulnerabilities privately — see
[SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE) © 2026 Felipe Dias

# Personal Fitness & Health App — project memory

Single-user personal fitness and health tracker. FastAPI + SQLite backend that serves a React/Vite PWA frontend. Solo project — mobile-first for use in the gym, desktop for review at home.

## Stack
- Backend: FastAPI, Uvicorn, SQLAlchemy 2.x (synchronous), SQLite, Pydantic v2, Alembic (Python).
- AI Coach: `anthropic` SDK (model `claude-opus-4-8`). Streaming chat + structured planners via forced tool use. Gated on `ANTHROPIC_API_KEY` — empty key ⇒ coach endpoints 503, everything else works.
- Frontend: React + Vite, Recharts for charts, PWA (service worker + web app manifest).
- Tests: Pytest.

## Layout
- `backend/app/main.py` — app entry point; mounts routers and serves the built frontend (single-origin SPA).
- `backend/app/routers/` — endpoints: calendar, coach, dashboard, dev, exercises, health, insights, nutrition, plan, ranks, routines, sessions, settings, stats, sync, trackers.
- `backend/app/ranks.py` + `muscles.py` — rank ladder (9 tiers × 3 divisions + LP from best 1RM ÷ bodyweight vs per-exercise benchmarks; bodyweight uses real readings only, never sample/estimated) and the muscle-group taxonomy/auto-tagging. Body-map shapes are traced from the user's hand-drawn PSD (see memory) — never re-derive them algorithmically.
- `backend/app/sync.py` — device-to-device sync engine (Phase 9): entity tables sync by `uuid`, health tables by `date`, merge is last-write-wins by `updated_at` with health source precedence. No tombstones yet (deletes don't propagate).
- `backend/app/coach_context.py` — builds the data brief (training/health/nutrition/trackers/plan) the Coach plans from. `plan_item` is the trackable day/study/workout domain (many rows per date, checkable); the Coach proposes, the user approves, accept endpoints commit (workout→routine, day→plan items).
- `backend/app/models.py` — SQLAlchemy models. `schemas.py` — Pydantic v2 request/response models. `db.py` — engine + session. `config.py` — settings loaded from `.env`. `auth.py` — bearer-token auth. `stats.py` — 1RM / PR math. `seed.py` — sample data.
- `backend/alembic/` — migrations (`alembic/versions/`).
- `backend/tests/` — Pytest suite.
- `frontend/src/` — React app. `frontend/public/` — PWA assets. `vite.config.js`, `index.html`.
- `frontend/src/local/` — local-first layer (phone independence): `db.js` IndexedDB via Dexie (rows mirror the sync payload), `local/api/` the on-device twin of the REST API (apiFetch dispatches here in local-first mode; Coach/ingest/sync/dev fall through to the network), `sync.js` sync-on-open client, `weights.js` weight math. Mode flag: production builds default to local-first (`VITE_LOCAL_FIRST=1` in `frontend/.env.production`) so the installed phone PWA runs offline without a runtime flag; `npm run dev` stays server-mode (per-device override still available via `localStorage.local_first='1'` / `?local=1`). The offline shell is the versioned service worker in `frontend/public/sw.js`, which precaches the shell + hashed JS/CSS at install. Ported JS math mirrors the backend 1:1 and is tested in vitest (`npm test` from `frontend/`).
- `.env` (not committed) holds the auth token and database URL.

## Commands
Run backend commands from `backend/`, frontend commands from `frontend/`.
- Install backend deps: `pip install -r requirements.txt`
- Migrate DB: `alembic upgrade head`
- Seed sample data (once, after migrating): `python -m app.seed`
- Run backend (dev): `uvicorn app.main:app --reload`
- Frontend dev server: `npm install`, then `npm run dev`
- Build frontend: `npm run build` (the backend then serves the built output on one origin)

## Tests
- Backend: `pytest` from `backend/` (uses `backend/.venv`; tests run on an in-memory SQLite — they never touch `fitness.sqlite3`).
- Frontend: `npm test` from `frontend/` (vitest — ported math in `src/local/`, plus component tests for numeric input handling, e.g. comma decimals like "82,5").
- The named safety net is `backend/tests/test_safety_net.py`: auth, weight entry, workout logging, the 2,300 kcal calorie anchor, and the Apple Health sample-payload import. Deep coverage lives in the per-feature test files next to it.
- CI (`.github/workflows/ci.yml`) runs both suites on every PR and on pushes to `main`. Keep both green — a red suite blocks the promotion flow below.

## Environments & promotion
Two isolated stacks (full runbook: `docs/STAGING.md`). **Production** = Railway service + its own Postgres, deploys from `main` **only**. **Staging** = a second Railway service + its own Postgres (`APP_ENV=staging`), deploys from the long-lived `staging` branch (a throwaway pointer — force-push any feature onto it). Frontends: Vercel builds a preview per feature branch and a persistent staging URL from the `staging` branch, all pointed at the staging API (`VITE_API_BASE_URL`); the frontend shows a **STAGING badge** whenever it talks to a staging API (`frontend/src/env.js` + `/api/ping`'s `env` field).
- Promotion flow: **feature branch → Vercel preview + staging test (`git push --force-with-lease origin <branch>:staging`) → merge to `main` → production deploys**. Never deploy to production from any other branch.
- Staging data is an anonymised prod copy: `./scripts/seed_staging.sh` (dump → guarded restore → `scripts/anonymise_staging.sql`). Staging is disposable; re-seed freely.
- API paths in frontend code stay relative — `apiUrl()` in `src/env.js` prefixes them when a cross-origin base is configured. New cross-origin frontends need their origin in the API's `CORS_ORIGINS`/`CORS_ALLOW_ORIGIN_REGEX`.

## Backups (production Postgres)
Production runs on a Railway **Postgres** service (local dev still uses SQLite — Postgres is a `DATABASE_URL` swap). Two scripts under `scripts/` back that DB up and restore it. Full setup + the one-time Railway steps live in the README (*Database backups*).
- `scripts/backup.sh` — `pg_dump` prod to `backups/fitness_prod_<ts>.dump` (custom format). One command: `./scripts/backup.sh`. The connection string comes from `PROD_DATABASE_URL` (env or the git-ignored `scripts/.env.backup`) — **never hardcode credentials**.
- `scripts/restore.sh` — `pg_restore` the newest (or a given) dump into `LOCAL_DATABASE_URL` (default a `localhost` DB, created if missing). One command: `./scripts/restore.sh`.
- **Restore can never touch production.** A host allowlist aborts unless the target is `localhost`/`127.0.0.1`/a `*staging*` host (extend via `STAGING_HOSTS`); it also refuses a target sharing `PROD_DATABASE_URL`'s host; then it makes you type the target DB name. No flag bypasses the host guard — this is a safety contract, keep it.
- `backups/` and `scripts/.env.backup` are git-ignored (real personal data + the prod connection string). Never commit them.
- Needs the Postgres client (`pg_dump`/`pg_restore`/`psql`) on PATH, client major version >= the Railway server's.

## Product direction — from the July 2026 workbook (FLIGHT_WORKBOOK_DONE.md)
- **Design tiebreaker (V3): the app is a *body recomposition instrument* first** — the weight/diet/energy loop is the core. Quantified-self lab second, gym logger third. Gamification is last — nice, never load-bearing.
- Guardrails (V4): never complicated to use; built for people serious about fitness but usable by anyone; not a clone of existing apps.
- Killed per the workbook: the Coach page (H9) and Plan/day-planner (H8) are hidden from the UI — code and endpoints remain, don't resurrect them without being asked. Trackers stay but stay simple (H5).
- The diet goal is a signed slider `goal_kg_per_week` ∈ [−0.5, +0.5] (− cut · 0 maintain · + bulk); the maintenance ceiling only applies when not bulking.
- A streak "active day" = workout, sport activity, or ≥10k steps (T6a).
- Single-user for ~2 years, but keep it deployable — it may become a product later (V5).

## Conventions — follow these
- Auth is single-user bearer token. Every protected route depends on `require_auth`; new endpoints follow the same pattern.
- Endpoints return Pydantic v2 schemas from `schemas.py` — never raw SQLAlchemy models.
- Schema changes go through a new Alembic migration; don't hand-edit the database.
- Health and nutrition data come from Apple Health: Health Auto Export JSON push, an export.zip backfill, and an iOS-Shortcut push for weight/steps/sleep (`POST /api/ingest/health/shortcut`, spec in `docs/HEALTH_INGEST_SHORTCUT.md`). The backfill and the Shortcut push share one validated core, `app/health_ingest.py` (`HealthAggregator`: units, wake-date sleep bucketing, best-source-per-day dedup, manual-precedence) — route new ingest paths through it, don't reimplement parsing. On conflict, manual entries win over Apple Health. Writes are idempotent upserts keyed by date. Do not reintroduce YAZIO (removed in phase 2).
- The app is single-user by design — don't add multi-user accounts or sharing.
- 1RM uses the Epley formula with reps capped at 12.
- Keep the Pytest suite green.

## Code map — consult before exploring broadly
A pre-built map of this codebase lives at `graphify-out/obsidian-vault/`: one Markdown note per code entity, generated by graphify.
- Use it to locate code and understand how parts relate before grepping or reading widely. Start with the `_COMMUNITY_*` notes for high-level structure and the "bridge" files between clusters.
- Each note's frontmatter has `source_file` and `location` (e.g. L20) — use them to jump straight to the real code.
- The `[[links]]` encode relationships (`calls`, `contains`, `requires`, `references`).
- It is a snapshot and can be stale: treat it as a table of contents, read the actual source file for the current implementation, and open only the specific notes you need — never the whole vault.
- Regenerate it with graphify after structural changes.
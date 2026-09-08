# Personal Fitness & Health App — project memory

Personal fitness and health tracker, originally single-user, now an invite-only multi-user beta for a small group of friends (see "Auth & multi-user" below). FastAPI backend that serves a React/Vite PWA frontend. Mobile-first for use in the gym, desktop for review at home.

## Working style & session ritual
The owner is learning software as they build this — explain the *why* in plain language, define jargon on first use, and don't assume prior knowledge. The full guide is `docs/DEV_HANDBOOK.md` (daily ritual, glossary, the agent↔role map, token discipline); read it if you're unsure how this project likes to work.
- **Session loop: Plan → Build → Verify → Ship.** Plan with `/plan-feature <idea>` (or Plan mode) before writing code; build; verify with the test suites and the browser preview; ship with `/ship`.
- **Never commit to `main`, and never push/PR/merge/deploy without an explicit yes.** Work on a feature branch; `/ship` runs tests + `/code-review`, summarizes the diff, and opens a PR only on the owner's confirmation.
- **The lean team**: `builder` (implementation) and `reviewer` (independent QA) agents, plus the built-in Explore (research) and Plan (architecture) agents. Prefer the main session; spawn a teammate only when independence or isolation is worth the cold-start token cost.
- Teaching intensity is toggled by the **Mentor** output style (`/output-style mentor`); these conventions hold regardless.

## Stack
- Backend: FastAPI, Uvicorn, SQLAlchemy 2.x (synchronous), SQLite (dev) / Postgres via Railway (production), Pydantic v2, Alembic (Python), argon2 password hashing.
- AI Coach: `anthropic` SDK (model `claude-opus-4-8`). Streaming chat + structured planners via forced tool use. Gated on `ANTHROPIC_API_KEY` — empty key ⇒ coach endpoints 503, everything else works.
- Frontend: React + Vite, Recharts for charts, PWA (service worker + web app manifest).
- Tests: Pytest.

## Layout
- `backend/app/main.py` — app entry point; mounts routers and serves the built frontend (single-origin SPA).
- `backend/app/routers/` — endpoints: activities, admin, auth, calendar, coach, dashboard, dev, diet, exercises, generator, health, insights, nutrition, plan, ranks, report, routine_notes, routines, sessions, settings, stats, streak, sync, trackers.
- `backend/app/ranks.py` + `muscles.py` — rank ladder (9 tiers × 3 divisions + LP from best 1RM ÷ bodyweight vs per-exercise benchmarks; bodyweight uses real readings only, never sample/estimated) and the muscle-group taxonomy/auto-tagging. Body-map shapes are traced from the user's hand-drawn PSD (see memory) — never re-derive them algorithmically.
- `backend/app/sync.py` — device-to-device sync engine (Phase 9), scoped per authenticated user (Phase 1-2): entity tables sync by `uuid`, health tables by `date`, merge is last-write-wins by `updated_at` with health source precedence. `Exercise` is the one owner-optional table (NULL = shared global library). No tombstones yet (deletes don't propagate).
- `backend/app/coach_context.py` — builds the data brief (training/health/nutrition/trackers/plan) the Coach plans from. `plan_item` is the trackable day/study/workout domain (many rows per date, checkable); the Coach proposes, the user approves, accept endpoints commit (workout→routine, day→plan items).
- `backend/app/models.py` — SQLAlchemy models; every data table carries a `user_id` FK (see "Auth & multi-user" below). `schemas.py` — Pydantic v2 request/response models. `db.py` — engine + session. `config.py` — settings loaded from `.env`. `auth.py` — session-cookie auth + password hashing. `auth_bootstrap.py` — shared "get or create the admin user" logic. `stats.py` — 1RM / PR math. `seed.py` — sample data (scoped to the admin account). `seed_admin.py` — creates the admin account + first invite code.
- `backend/alembic/` — migrations (`alembic/versions/`).
- `backend/tests/` — Pytest suite.
- `frontend/src/` — React app. `frontend/public/` — PWA assets. `vite.config.js`, `index.html`.
- `frontend/src/local/` — local-first layer (phone independence): `db.js` IndexedDB via Dexie (rows mirror the sync payload), `local/api/` the on-device twin of the REST API (apiFetch dispatches here in local-first mode; Coach/ingest/sync/dev fall through to the network), `sync.js` sync-on-open client, `weights.js` weight math. Mode flag: production builds default to local-first (`VITE_LOCAL_FIRST=1` in `frontend/.env.production`) so the installed phone PWA runs offline without a runtime flag; `npm run dev` stays server-mode (per-device override still available via `localStorage.local_first='1'` / `?local=1`). The offline shell is the versioned service worker in `frontend/public/sw.js`, which precaches the shell + hashed JS/CSS at install. Ported JS math mirrors the backend 1:1 and is tested in vitest (`npm test` from `frontend/`).
- `.env` (not committed) holds `ADMIN_EMAIL`/`ADMIN_PASSWORD` and the database URL.

## Commands
Run backend commands from `backend/`, frontend commands from `frontend/`.
- Install backend deps: `pip install -r requirements.txt`
- Migrate DB: `alembic upgrade head`
- Create the admin account + first invite code (once, after migrating): `python -m app.seed_admin`
- Seed sample data for the admin account (once, after seed_admin): `python -m app.seed`
- Run backend (dev): `uvicorn app.main:app --reload`
- Frontend dev server: `npm install`, then `npm run dev`
- Build frontend: `npm run build` (the backend then serves the built output on one origin)
- One-command local dev (build frontend, set up backend venv, migrate, seed, serve on `0.0.0.0` for phone testing via QR): `./start.sh` (use `--no-build` to skip the frontend build)

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
- **Same-origin via a Vercel rewrite** (`frontend/vercel.json`'s `/api/*` rewrite to the Railway backend) is what makes the session cookie work at all — browsers won't send a cross-origin cookie without extra CORS/SameSite plumbing this app doesn't have. The rewrite's `destination` is a static URL baked into the deployed commit, so **it must be re-pointed at the production Railway URL on `main` separately at promotion time** — copying the feature branch's `vercel.json` verbatim would silently keep pointing at staging. `VITE_API_BASE_URL` must also be blank in that Vercel environment's project settings for the rewrite to actually take effect.

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
- V5 (multi-user): superseded — see "Auth & multi-user" below, now in progress as an invite-only friends beta (`friends-beta-prompt-pack.md`).

## Auth & multi-user (Phase 1-2 friends beta)
Locked decisions live in `friends-beta-prompt-pack.md` at the repo root — read it before touching auth. Summary of what's implemented:
- **Every data table carries a `user_id` FK** (models.py), scoped server-side on every query — the client never sends or selects `user_id`. `Exercise` is the one owner-optional table: `user_id IS NULL` is the shared seeded library, set only on a user's own custom exercise. `TrackerLog` has no `user_id` of its own — it's reached only through `tracker_id` (`Tracker.user_id` scopes it; see `routers/trackers.py`'s `_get_tracker`).
- **Auth is a session cookie**, not a bearer token: `POST /api/auth/login` creates a DB-backed `AuthSession` row and sets an httpOnly/Secure/SameSite=Lax cookie (`app/auth.py`). `require_auth` resolves the current `User` from it; routers depend on it exactly like the old `require_auth` (`current_user: User = Depends(require_auth)`), then filter every query by `current_user.id`. `require_admin` gates `routers/admin.py`. Apple Health ingest (`/api/ingest/health*`) is the one exception — it authenticates via a separate, persistent per-user `ingest_token` bearer header (`require_ingest_auth`), since a Shortcut/HAE automation can't hold a cookie jar.
- **Signup is invite-code-gated** (`POST /api/auth/join`, checked server-side, not just hidden in the UI) and lands `status='pending'` until an admin approves it from `/admin`. No email service — admin issues temp passwords for resets (`POST /api/admin/users/{id}/temp-password`), which forces `must_change_password` and kills that user's other sessions.
- **`session_cookie_secure` (config.py) must be `false` for local dev/tests** (plain `http://`) and stays `true` everywhere else — a `Secure` cookie is silently never sent back over a non-HTTPS connection, which looks like "login succeeds then immediately appears logged out." `tests/conftest.py` sets this for the test client automatically.
- **Frontend**: `src/auth.jsx` (`AuthProvider`/`useAuth`) drives the gate in `App.jsx` — logged out renders only `/login`/`/join`; `must_change_password` forces `ChangePassword`; otherwise the normal app. `src/api.js` sends `credentials: 'include'` on every request, no token handling. The local-first Dexie DB (`src/local/db.js`) is wiped whenever the logged-in user differs from whoever it last synced as (`src/local/sync.js`'s `ensureLocalDbMatchesUser`) — switching accounts on a shared device drops local unsynced changes for the previous account.
- **Migration**: new tables (`users`, `invite_codes`, `auth_session`) plus a `user_id` retrofit on every existing table happened across three Alembic migrations with a manual backfill script (`app/backfill_owner.py`) in between, attaching all pre-multi-user data to an admin account seeded from `ADMIN_EMAIL`/`ADMIN_PASSWORD`. Never run the backfill or the NOT-NULL migration against production directly — staging first, with a backup and row-count check.
- **Deferred** (do not implement without being asked): i18n/pt-BR, the onboarding-wizard rewrite, per-user feature flags, mobile-parity pass, rate limiting/hardening — these are later phases in the prompt pack.

## Conventions — follow these
- Auth is a per-user session cookie (see above). Every protected route depends on `require_auth` and filters its queries by `current_user.id`; new endpoints follow the same pattern. Apple Health ingest routes use `require_ingest_auth` instead.
- Endpoints return Pydantic v2 schemas from `schemas.py` — never raw SQLAlchemy models.
- Schema changes go through a new Alembic migration; don't hand-edit the database.
- **A web app cannot read Apple Health** — iOS gives HealthKit access to native apps only, never to a PWA. All health data therefore arrives by the *phone pushing it*. The primary path is a shared iOS Shortcut (`Tracker Health Sync`, installed from one iCloud link set in `VITE_HEALTH_SHORTCUT_URL`, prompting each user for their server URL + `ingest_token` at install) run by a time-of-day automation or by the in-app **Sync now** button, which deep-links `shortcuts://x-callback-url/run-shortcut`. iOS's "when I open an app" trigger does not reliably see home-screen web apps — don't promise open-triggered sync. Health Auto Export (nutrition/micros) and the export.zip backfill remain as secondary paths. Full spec: `docs/HEALTH_INGEST_SHORTCUT.md`.
- Ingest endpoints: `POST /api/ingest/health` (HAE), `/api/ingest/health/shortcut`, `/api/ingest/health-export`. The backfill and the Shortcut push share one validated core, `app/health_ingest.py` (`HealthAggregator`: units, wake-date sleep bucketing, best-source-per-day dedup, manual-precedence) — route new ingest paths through it, don't reimplement parsing. On conflict, manual entries win over Apple Health. Writes are idempotent upserts keyed by `(user_id, date)`. Do not reintroduce YAZIO (removed in phase 2).
- `GET /api/health/sync-status` reports per-metric freshness (`days_stale` for weight/steps/sleep/nutrition) and drives the stale-data banner, the sidebar line and the Settings card. It counts **real readings only** — `DERIVED_SOURCES` (`estimated`, `sample`) are excluded so fabricated data can never report itself as fresh. Twin in `frontend/src/local/api/health.js` (`buildSyncStatus`).
- **Never let invented data render as real.** Sample seeding (`POST /api/dev/seed-sample-health`, `source='sample'`) is admin-only *and* gated on `settings.enable_dev_seed` (off by default; it is not keyed to `app_env`, which defaults to `production` on the laptop too). `python -m app.purge_sample` removes leftover sample rows. `ingest_token` is rotatable via `POST /api/auth/ingest-token/rotate`.
- 1RM uses the Epley formula with reps capped at 12.
- Keep the Pytest suite green. The whole suite now uses the session-cookie auth fixtures in `tests/conftest.py` (`auth_client` + shared `TestingSession`/`clean_db`) — see that docstring for how to write new tests (cookie auth, per-user seeding with `user_id`, and the ingest-token bearer for `/api/ingest/health*`). Don't reintroduce the old per-file `APP_TOKEN`/`headers=AUTH` pattern.

## Code map — consult before exploring broadly
A pre-built map of this codebase lives at `graphify-out/obsidian-vault/`: one Markdown note per code entity, generated by graphify.
- Use it to locate code and understand how parts relate before grepping or reading widely. Start with the `_COMMUNITY_*` notes for high-level structure and the "bridge" files between clusters.
- Each note's frontmatter has `source_file` and `location` (e.g. L20) — use them to jump straight to the real code.
- The `[[links]]` encode relationships (`calls`, `contains`, `requires`, `references`).
- It is a snapshot and can be stale: treat it as a table of contents, read the actual source file for the current implementation, and open only the specific notes you need — never the whole vault.
- Regenerate it with graphify after structural changes.
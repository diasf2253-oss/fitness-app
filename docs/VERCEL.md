# Deploying to Vercel (frontend + backend in one project)

The whole app runs as **one Vercel project with two services** (`vercel.json`
at the repo root):

| Service | Folder | Public path | What it is |
|---|---|---|---|
| `backend` | `backend/` | `/api/*` | FastAPI (`app/main.py` → `app`), runs as Vercel Functions |
| `frontend` | `frontend/` | everything else | Vite build (the React PWA) |

Both live on **one domain**, so API calls need no CORS setup and
`VITE_API_BASE_URL` stays **empty** (API paths are relative). Sign-in runs on
**Supabase Auth**, which also hosts the database — set that up first:
[SUPABASE.md](SUPABASE.md). The backend gets
the full path (`/api/auth/login`), which is what its routes already expect.
No service-to-service bindings: the browser calls the backend directly.

## One-time setup

1. **Import**: vercel.com → Add New → Project → `fitness-app` → choose
   **Import multi-service project** (it reads `vercel.json`).
2. **Database**: the production Supabase project's **Transaction pooler**
   string (port 6543) as `DATABASE_URL`. Supabase → Connect shows it.
   - Give **Preview** deployments the *staging* project's string — never point
     previews at the production database.
3. **Environment variables** (Project → Settings → Environment Variables,
   Production):
   - `ADMIN_EMAIL` (no password — the admin signs in through Supabase)
   - `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, optionally `SUPABASE_SECRET_KEY`
   - `VITE_SUPABASE_URL`, `VITE_SUPABASE_PUBLISHABLE_KEY` (same project; the
     frontend build bakes them in)
   - Preview gets the same names with the **staging** project's values
   - leave `VITE_API_BASE_URL` **unset/empty**
   - do **not** set `ENABLE_DEV_SEED`
   - optional: `ANTHROPIC_API_KEY` (Coach is hidden; empty is fine)
4. **Prepare the database once, from your laptop** (Vercel has no "server
   start", so the jobs the Docker image ran on boot are run by hand):

   ```bash
   cd backend
   export DATABASE_URL='<Supabase session-pooler or direct string — not the transaction pooler>'
   export ADMIN_EMAIL='you@example.com'
   .venv/bin/alembic upgrade head      # create / update tables
   .venv/bin/python -m app.seed_admin  # admin account + first invite code
   .venv/bin/python -m app.seed        # exercise library + routine templates
   unset DATABASE_URL
   ```

5. **Deploy**, then check `https://<your-app>.vercel.app/api/ping` →
   `{"status":"ok","env":"production"}`, and create your login with the admin
   email (or Google) — it links to the admin account.

## Every release
- Schema change in the release? Run `alembic upgrade head` against the
  production database (step 4, first line) **after a backup**, staging first.
- Bump `VERSION` in `frontend/public/sw.js` so installed phones drop the old
  cached bundle.

## Known limits on Vercel
- **Password guessing is rate-limited by Supabase.** The app's own limiter
  only guards invite-code attempts (`/api/auth/join`), and it is per instance
  (`app/ratelimit.py` keeps counts in memory) — serverless instances come and
  go, so move it to the database before opening invites widely.
- **Request bodies max 4.5 MB** — only matters for the old Apple Health
  `export.zip` upload (paused).
- **Services are a Vercel beta feature.**
- Local databases and backups are excluded from CLI uploads by `.vercelignore`;
  Git-connected deploys only ever see committed files.

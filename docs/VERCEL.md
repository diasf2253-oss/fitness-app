# Deploying to Vercel (frontend + backend in one project)

The whole app runs as **one Vercel project with two services** (`vercel.json`
at the repo root):

| Service | Folder | Public path | What it is |
|---|---|---|---|
| `backend` | `backend/` | `/api/*` | FastAPI (`app/main.py` → `app`), runs as Vercel Functions |
| `frontend` | `frontend/` | everything else | Vite build (the React PWA) |

Both live on **one domain**, so the login cookie works with no CORS setup and
`VITE_API_BASE_URL` stays **empty** (API paths are relative). The backend gets
the full path (`/api/auth/login`), which is what its routes already expect.
No service-to-service bindings: the browser calls the backend directly.

## One-time setup

1. **Import**: vercel.com → Add New → Project → `fitness-app` → choose
   **Import multi-service project** (it reads `vercel.json`).
2. **Database**: Vercel → Storage → Create → **Neon (Postgres)** → connect it
   to this project (Production). It injects `DATABASE_URL`. Use the
   **pooled** connection string for the app.
   - Give **Preview** deployments a *separate* database (or a Neon branch) —
     never point previews at the production database.
3. **Environment variables** (Project → Settings → Environment Variables,
   Production):
   - `ADMIN_EMAIL`, `ADMIN_PASSWORD` (strong, ≥ 8 chars, not `changeme`)
   - leave `VITE_API_BASE_URL` **unset/empty**
   - do **not** set `ENABLE_DEV_SEED`
   - optional: `ANTHROPIC_API_KEY` (Coach is hidden; empty is fine)
4. **Prepare the database once, from your laptop** (Vercel has no "server
   start", so the jobs the Docker image ran on boot are run by hand):

   ```bash
   cd backend
   export DATABASE_URL='<Neon connection string — direct, not pooled>'
   export ADMIN_EMAIL='you@example.com' ADMIN_PASSWORD='<strong password>'
   .venv/bin/alembic upgrade head      # create / update tables
   .venv/bin/python -m app.seed_admin  # admin account + first invite code
   .venv/bin/python -m app.seed        # exercise library + routine templates
   unset DATABASE_URL ADMIN_PASSWORD
   ```

5. **Deploy**, then check `https://<your-app>.vercel.app/api/ping` →
   `{"status":"ok","env":"production"}` and log in.

## Every release
- Schema change in the release? Run `alembic upgrade head` against the
  production database (step 4, first line) **after a backup**, staging first.
- Bump `VERSION` in `frontend/public/sw.js` so installed phones drop the old
  cached bundle.

## Known limits on Vercel
- **Login rate limiting is per instance** (`app/ratelimit.py` keeps counts in
  memory). Serverless instances come and go, so brute-force protection is
  weaker than on a single server. Move it to the database before opening
  invites widely.
- **Request bodies max 4.5 MB** — only matters for the old Apple Health
  `export.zip` upload (paused).
- **Services are a Vercel beta feature.**
- Local databases and backups are excluded from CLI uploads by `.vercelignore`;
  Git-connected deploys only ever see committed files.

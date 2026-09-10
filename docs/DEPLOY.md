# Deploying

One service serves everything: FastAPI hosts the API **and** the built
frontend on a single origin. That one URL is what you open on any device,
what the installed PWA launches, and what the Apple Health Shortcut pushes to.

The `Dockerfile` builds that single image. On every boot it runs
`alembic upgrade head` → `python -m app.seed_admin` → `python -m app.seed`
→ `uvicorn`, and all three setup steps are safe to repeat.

> **Serve it over HTTPS.** Login uses a `Secure` session cookie
> (`SESSION_COOKIE_SECURE=true`, the default). Browsers never send a Secure
> cookie over plain `http://`, so on an http origin every login would appear to
> succeed and then immediately log you out. Only set it to `false` for local
> development.

---

## Option A — Railway + Postgres (what production uses)

1. Railway → **New Project** → deploy this repo (it picks up the `Dockerfile`
   and `railway.json`, which health-checks `/api/ping`).
2. Add a **Postgres** service to the project.
3. On the app service, set variables:

   | Variable | Value |
   |---|---|
   | `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` (a bare `postgresql://` URL is fine — it's routed to the psycopg 3 driver automatically) |
   | `ADMIN_EMAIL` | the first admin account's email |
   | `ADMIN_PASSWORD` | a strong password (change it later with `python -m app.set_admin_password`) |
   | `ANTHROPIC_API_KEY` | *(optional)* enables the AI report narrative / Coach endpoints |

4. **Settings → Networking → Generate Domain.** Railway serves it over HTTPS.
5. Read the deploy log: `seed_admin` prints the **first invite code**. Log in
   as the admin, then share the invite code with friends — their signups
   arrive as *pending* under **/admin** until you approve them.

Back up the database with `./scripts/backup.sh` (see the README's
*Database backups* section). For a separate staging stack, see
[STAGING.md](STAGING.md).

## Option B — any Docker host with SQLite

```bash
docker build -t fitness-app .
docker run -p 8000:8000 \
  -v fitness-data:/app/data \
  -e DATABASE_URL=sqlite:////app/data/fitness.sqlite3 \
  -e ADMIN_EMAIL=you@example.com \
  -e ADMIN_PASSWORD='a-strong-password' \
  fitness-app
```

Mount a volume at `/app/data` so the SQLite file outlives the container, and
put an HTTPS reverse proxy (Caddy, Cloudflare Tunnel, …) in front of it.

## Option C — your own Mac + Cloudflare Tunnel (free)

Good if the Mac is usually on. The tunnel gives you a public **HTTPS** URL,
so the Secure cookie works — **but first delete the
`SESSION_COOKIE_SECURE=false` line from `backend/.env`** (the local-dev
template adds it). Left in, the session cookie is issued without its
`Secure` flag on a public site. Also make sure `ADMIN_PASSWORD` is a real
password, not the template's `changeme`.

```bash
# 1. Build the frontend once (rebuild after each update)
cd frontend && npm run build

# 2. Run the backend (serves app + API on :8000)
cd ../backend && source .venv/bin/activate
uvicorn app.main:app --port 8000

# 3. Expose it
brew install cloudflared

# Quick test (URL changes every run — fine for trying, bad for the Shortcut):
cloudflared tunnel --url http://localhost:8000

# Permanent named tunnel (stable URL, free Cloudflare account):
cloudflared tunnel login
cloudflared tunnel create tracker
cloudflared tunnel route dns tracker tracker.<your-domain>.com
cloudflared tunnel run --url http://localhost:8000 tracker
```

To keep both processes alive across reboots, add them as LaunchAgents or
run them under `tmux`; `cloudflared service install` handles the tunnel
side automatically.

---

## Phone setup (after any option)

1. Open the HTTPS URL on the phone and log in.
2. **Install the app**: iOS Safari → Share → *Add to Home Screen*;
   Android Chrome → menu → *Install app*. You get a standalone window with no
   browser chrome, and it keeps working offline (local-first mode).
3. **Apple Health**: **Settings → Apple Health sync** walks you through
   installing the shared iOS Shortcut and shows the *Server* and personal
   *Token* to paste into it. Full details: [HEALTH_INGEST_SHORTCUT.md](HEALTH_INGEST_SHORTCUT.md).
4. Optional: upload an Apple Health `export.zip` once for your full history
   (Settings → History backfill).

## Updating

Railway: merge to `main` and it redeploys. Docker / Mac: `git pull`,
rebuild the frontend (or the image), restart. Bump `VERSION` in
`frontend/public/sw.js` on every frontend release — otherwise an installed
PWA keeps serving its cached old bundle.

# Going always-on

One service serves everything: FastAPI hosts the API **and** the built
frontend on a single origin. That one URL is what you open on any device,
what the installed PWA launches, and what Health Auto Export pushes to.

Before exposing anything publicly, set a strong token:

```bash
# backend/.env
APP_TOKEN=<long random string>     # e.g. `openssl rand -hex 24`
```

Enter the same token once on each device (Settings → API Token).

---

## Option A — your Mac + Cloudflare Tunnel (free, keeps SQLite)

Best fit if the Mac is usually on. Nothing migrates; your existing
database keeps working.

```bash
# 1. Build the frontend once (rebuild after each update)
cd frontend && npm run build

# 2. Run the backend (serves app + API on :8000)
cd ../backend && source .venv/bin/activate
uvicorn app.main:app --port 8000

# 3. Expose it
brew install cloudflared

# Quick test (URL changes every run):
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

## Option B — Railway (managed, ~$5/mo)

The repo's `Dockerfile` is all Railway needs.

1. Push the repo to GitHub, then Railway → New Project → Deploy from repo.
2. Add a **volume** mounted at `/app/data` (SQLite must outlive deploys).
3. Set variables:
   - `APP_TOKEN` — your long random token
   - `DATABASE_URL` — `sqlite:////app/data/fitness.sqlite3`
4. Generate a domain (Settings → Networking). Done — migrations and the
   exercise seed run automatically on each boot.

To bring your existing data along, copy `backend/fitness.sqlite3` into the
volume once (Railway shell: upload, then move it to `/app/data/`).

---

## Phone setup (after either option)

1. Open the URL in Safari/Chrome → Settings → paste your token.
2. **Install the app**: iOS Safari → Share → *Add to Home Screen*.
   Android Chrome → menu → *Install app*. You get the cairn icon,
   standalone window, no browser chrome.
3. **Point Health Auto Export** at `https://<your-url>/api/ingest/health`
   with the `Authorization: Bearer <token>` header (full steps in
   Settings → Apple Health sync).
4. Upload your `export.zip` once for history (Settings → History backfill).

## Updating

Mac + tunnel: `git pull`, rebuild the frontend, restart uvicorn.
Railway: push to GitHub; it redeploys.

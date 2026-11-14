# Supabase: logins and the database

The app uses **Supabase** for two things:

1. **Logins (Supabase Auth).** Signing up, signing in (email + password, or
   *Continue with Google*), "forgot password" emails and staying signed in all
   happen at Supabase. The browser gets an **access token**: a short-lived
   signed note that says "this is user X". It sends that token with every API
   call, and the backend checks the signature itself
   (`backend/app/supabase_auth.py`).
2. **The database (Supabase Postgres).** It replaces the Neon/Railway
   Postgres. To the app it's just a different `DATABASE_URL`.

What did **not** move: the app still decides **who gets in**. A Supabase
login on its own grants nothing. Someone needs an invite code, which creates
a *pending* account, and then an admin's approval. All of that lives in the
app's own `users` table, as before. The Apple Health Shortcut also keeps its
own per-user `ingest_token`.

```
Browser ── sign in ──▶ Supabase Auth ── access token ──▶ Browser
Browser ── API call + "Authorization: Bearer <token>" ──▶ FastAPI
FastAPI: token genuine? (public keys, cached) → which account? (users.supabase_uid)
         → allowed in? (status: pending / active / disabled) → scoped data
```

## How accounts connect to logins

Each account has a `supabase_uid` column: the Supabase user it signs in as.
It's empty until that person's first sign-in through Supabase. On that first
request, the backend looks for an account with the **same email** and no
login attached yet. It links the two **only if Supabase confirms the email is
verified**: the same proof as a "forgot password" email.

That's the whole migration story for existing people (you, the first
friends). Each person creates a login with the email they already use, or
taps Continue with Google. Their account and all their data are picked up
automatically. There's no password import and no script to run. The Admin
page marks anyone who hasn't done it yet as *"not on the new login yet"*.

A linked account is never re-linked automatically. If someone deletes their
Supabase login and makes a new one, an admin has to clear their
`supabase_uid` in the database (`UPDATE users SET supabase_uid = NULL WHERE
email = '…'`). Their next sign-in then links again.

## One-time setup

Make **two Supabase projects**: one for **staging** (also used for local
development) and one for **production**. Never point previews or your laptop
at production. The free plan covers two projects. Note that free projects
**pause after a week without traffic**. Wake one up from the dashboard if the
app suddenly can't sign anyone in.

In **each** project:

1. **Email sign-in.** Authentication → Sign In / Providers → Email: enabled,
   with **Confirm email** on (the default). Set the minimum password length
   to **8**, to match the app's forms.
2. **Google sign-in.**
   - In Google Cloud Console → APIs & Services → Credentials, create an
     **OAuth client ID** of type *Web application*.
   - Add `https://<project-ref>.supabase.co/auth/v1/callback` as an
     authorized redirect URI.
   - Paste the client ID and secret into Supabase → Authentication →
     Providers → Google.
   - One Google client can serve both projects. List both callback URLs.
3. **Where links send people back.** Authentication → URL Configuration:
   - **Site URL**: the app's address (production:
     `https://<your-app>.vercel.app`; staging: the staging URL).
   - **Redirect URLs**: the same address with `/**` on the end. On the
     staging project, also add `http://localhost:5173/**` (dev server),
     `http://localhost:8000/**` (`./start.sh`), and your Vercel preview
     pattern.
4. **Signing keys.** Project Settings → JWT Keys must show **JWT signing
   keys** (ECC P-256), not "Legacy JWT secret". New projects already use
   signing keys. The backend only accepts tokens signed this way; with the
   legacy secret every request answers 401 and the server log says why. To
   switch, migrate there, then rotate to the new key.
5. **Keys.** Project Settings → API Keys:
   - the **publishable key** (`sb_publishable_…`): public by design; the
     frontend and backend both use it;
   - a **secret key** (`sb_secret_…`): **server-only**. It's needed only for
     the admin's *Reset link* button. Never put it in a `VITE_` variable or
     paste it into chat.
6. **Database.** Connect (top bar) → copy two connection strings:
   - **Transaction pooler** (port 6543): the app on Vercel uses this. (The
     backend already turns off psycopg's server-side prepared statements,
     which this pooler can't keep. See `backend/app/db.py`.)
   - **Session pooler** or **Direct**: use this from your laptop for
     migrations, backups and restores.

## Environment variables

| Where | Variable | Value |
|---|---|---|
| Backend | `SUPABASE_URL` | `https://<project-ref>.supabase.co` |
| Backend | `SUPABASE_PUBLISHABLE_KEY` | the publishable key |
| Backend | `SUPABASE_SECRET_KEY` | *(optional)* a secret key, for admin reset links |
| Backend | `DATABASE_URL` | the Supabase **transaction pooler** string |
| Backend | `ADMIN_EMAIL` | the admin account's email (no password any more) |
| Frontend (build time) | `VITE_SUPABASE_URL` | same as `SUPABASE_URL` |
| Frontend (build time) | `VITE_SUPABASE_PUBLISHABLE_KEY` | same publishable key |

- **Vercel**: set these on the project. Production values come from the
  production Supabase project; **Preview** values from the staging project.
  Delete the old `ADMIN_PASSWORD` variable.
- **Local dev**: put the staging project's values in `backend/.env` and
  `frontend/.env.local` (both git-ignored; templates in
  `backend/.env.example` and `frontend/.env.example`).
- Empty `SUPABASE_URL` means signed-in routes answer **503 "Login isn't
  configured"**. Empty `VITE_SUPABASE_*` means the app shows a *"Login isn't
  set up"* screen.

## Switching production over

Do this together, slowly, **staging first**:

1. **Back up** production: `./scripts/backup.sh`.
2. **Move the data** into the Supabase database. Use `pg_restore` of that
   dump against the *Session pooler / Direct* string. Compare row counts
   table by table before going further. `scripts/restore.sh` deliberately
   refuses non-staging hosts, so restoring into the new production database
   is a manual, eyes-open step.
3. **Migrate**: from `backend/`, with `DATABASE_URL` set to that string, run
   `.venv/bin/alembic upgrade head`. This adds `users.supabase_uid` and lets
   `password_hash` be empty. It's additive, and the old code ignores it.
4. **Set the Vercel variables** above and deploy.
5. **Everyone signs in again.** Each person creates a login with their usual
   email, or uses Google. Start with yourself, to confirm the admin account
   links. Watch the Admin page's *"not on the new login yet"* markers
   disappear.

Staging copies of production: after restoring one, clear the links, because
staging has its own Supabase users:
`UPDATE users SET supabase_uid = NULL;` (see the note in *Still to do*).

## Password resets

- **Self-service**: *Forgot password?* on the login screen. Supabase emails a
  link. Its built-in email sender only sends a few messages per hour. That's
  fine for a friends beta; add your own SMTP server in Supabase if it starts
  to bite.
- **Admin fallback**: Admin → *Reset link* creates a one-time link (needs
  `SUPABASE_SECRET_KEY`). Send it to the person directly. Anyone holding it
  can get into that account.

## Security notes

- Supabase's browser library keeps the session in **localStorage**, not an
  httpOnly cookie. Any script running on the app's own pages could read it.
  The app loads no third-party scripts; keep it that way.
- The backend accepts only `ES256`/`RS256` tokens from this project's
  issuer, with `role = authenticated`. It rejects the public anon and
  service-role keys, anonymous sign-ins, expired tokens and other projects'
  tokens. All of these have tests (`backend/tests/test_supabase_auth.py`).
- Sign-up is rate-limited per IP on `/api/auth/join`. Password guessing is
  rate-limited by Supabase.

## Still to do (later)

- **Cleanup migration**, once production has run on Supabase for a while:
  drop `users.password_hash`, `users.must_change_password` and the
  `auth_session` table. They're unused now.
- **Staging scrub** (`scripts/anonymise_staging.sql` / `seed_staging.sh`):
  it still gives every staging account one shared password using the old
  password hasher. With Supabase that does nothing. It should instead clear
  `supabase_uid`, and staging testers sign in with staging-project logins.

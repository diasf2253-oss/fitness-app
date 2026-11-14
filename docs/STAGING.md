# Environments — staging & production

Two fully separate stacks. You can drop staging's database, ship a broken
migration to it, or delete the whole staging service — production never
notices. Nothing in staging holds a production credential, and the seed
scripts physically refuse to write toward production.

| | Production | Staging |
|---|---|---|
| Backend | Railway service, deploys from **`main`** only | Second Railway service, deploys from the **`staging`** branch |
| Database | Railway Postgres (prod) | Its own Railway Postgres — different host, credentials, data |
| Env label | `APP_ENV=production` (default) | `APP_ENV=staging` → `/api/ping` returns `{"env": "staging"}` |
| Auth | Session cookies + per-user ingest tokens, stored in prod's DB | Same mechanism against its own DB — a session or token issued by staging doesn't exist in prod |
| Frontend | The Railway app itself (single origin — the PWA and Health Auto Export point here) + optional Vercel production deploy from `main` | Vercel: a preview per feature branch **and** a persistent `staging`-branch URL, both pointed at the staging API; plus the staging Railway origin itself |
| Data | Real | Anonymised copy of prod (`./scripts/seed_staging.sh`) |

The **STAGING badge**: `frontend/src/env.js` decides it. Build-time signals
(`VITE_APP_ENV=staging`, an API base or page host containing "staging") show
it instantly; otherwise a one-shot `/api/ping` probe reads the API's `env`
field. Any frontend talking to the staging API shows the badge — Vercel
previews, the persistent staging URL, and the staging Railway origin itself.

## Branch → deploy map

```
feature/xyz  ──push──▶  Vercel preview   (unique URL, staging API, STAGING badge)
staging      ──push──▶  Railway staging  (API + its own baked frontend)
                        Vercel staging   (persistent branch URL, staging API)
main         ──merge─▶  Railway prod     (the real app)
                        Vercel prod      (optional desktop mirror, prod API)
```

`staging` is a throwaway pointer, not history — put any feature on it with:

```bash
git push --force-with-lease origin my-feature:staging
```

## Promotion flow

1. Branch from `main` (`feature/...`), commit, push. Vercel builds a preview
   URL against the staging API — check the UI there.
2. Need the backend half too? `git push --force-with-lease origin feature/...:staging`
   — the staging Railway service redeploys with your migrations/endpoints, and
   the persistent staging frontend picks it up. Test with anonymised data;
   re-seed anytime with `./scripts/seed_staging.sh`.
3. Happy → merge to `main`. Railway production (and Vercel production)
   deploy from `main` and nothing else.
4. Broke staging? Fix forward or just re-seed / redeploy — it's disposable.

## Seeding staging with realistic data

```bash
cp scripts/.env.backup.example scripts/.env.backup   # once; fill in both URLs + STAGING_USER_PASSWORD
./scripts/seed_staging.sh                            # dump prod → restore staging → anonymise
```

The script: `pg_dump` prod (`scripts/backup.sh`) → `pg_restore` into
`STAGING_DATABASE_URL` via `scripts/restore.sh` (typed-confirmation guard
kept) → `scripts/anonymise_staging.sql`. Guards: it refuses if staging and
prod share host:port, and restore.sh separately re-checks the target against
`PROD_DATABASE_URL`.

`anonymise_staging.sql` runs as **one transaction**: it either scrubs
everything below or changes nothing, and it checks its own work (no
sessions left, no real non-admin emails, every hash replaced, no active
invite codes) before committing.

| What | Becomes |
|---|---|
| `users` email / name (non-admin) | `user<id>@example.test` / `User <id>` |
| `users.password_hash` (everyone, admin included) | one staging-only argon2 hash of `STAGING_USER_PASSWORD` |
| `users.must_change_password` | `false` for everyone (a pending prod temp-password reset means nothing once the hash is replaced) |
| `users.ingest_token` | a fresh random value per user — the prod tokens on friends' phones can't push to staging, and a staging token opens nothing in prod |
| `auth_session` | every row deleted — no production session id works on staging |
| `invite_codes` | every code replaced with a random value and deactivated; labels → `Invite <id>` |
| Free text | journal entries, session/routine/exercise/activity notes, routine notes, tracker text entries, plan-item titles scrubbed |
| `weight_log` | one random per-run offset + small per-row noise (the trend stays real for the calorie engine and charts) |
| `steps_log` / `nutrition_day` | per-row jitter (steps ±10%, nutrition ±5%) |
| `settings.age` | reset to 30 |

Kept on purpose: user ids, roles and statuses (pending stays pending,
disabled stays disabled), exercise/routine/session names, dates, sets and
reps, so ranks, insights and streaks look real. The admin row keeps its
email and name. That's your own account, and keeping the email means you
log in the way you always do.

**Logging in after a seed.** Every account's password is
`STAGING_USER_PASSWORD`, from `scripts/.env.backup`. The script refuses to
run without one of 12+ characters, hashes it locally with argon2 (the same
hasher the app uses), and sends only the hash to Postgres. Log in as the
admin with its production email, or as any friend with
`user<id>@example.test`. No password change is forced. The staging
service's `ADMIN_EMAIL`/`ADMIN_PASSWORD` vars are **ignored** after a seed,
because the restored copy already contains an admin. To test Apple Health
ingest against staging, issue that account a staging token
(`POST /api/auth/ingest-token/rotate`). To let someone sign up on staging,
create a fresh invite code in staging's `/admin`.

If the anonymise step fails, the script stops with a loud warning. The
restore has already happened by then, so staging holds an **unscrubbed**
production copy until you fix the error and re-run (or stop the staging
service).

After seeding, if `staging` carries migrations prod doesn't have yet,
restart/redeploy the staging service — `alembic upgrade head` runs on boot.

## Environment variables

Railway **staging** service (service → Variables):

| Var | Value |
|---|---|
| `DATABASE_URL` | reference the staging Postgres (`${{Postgres.DATABASE_URL}}`) |
| `ADMIN_EMAIL` / `ADMIN_PASSWORD` | staging admin, only used when the DB has no admin yet — after a seed, the restored admin logs in with `STAGING_USER_PASSWORD` instead (see *Seeding staging*) |
| `APP_ENV` | `staging` |
| `VITE_APP_ENV` | `staging` (consumed as a Docker build arg → badge baked into that origin's frontend) |
| `CORS_ALLOW_ORIGIN_REGEX` | `https://.*\.vercel\.app` (lets every Vercel preview call this API) |
| `ANTHROPIC_API_KEY` | empty (Coach 503s on staging) or a low-limit key |

Railway **production** service: `DATABASE_URL` (prod Postgres),
`ADMIN_EMAIL`/`ADMIN_PASSWORD`, `ANTHROPIC_API_KEY`; `APP_ENV` unset
(defaults to production). Add
`CORS_ORIGINS=https://<vercel-prod-domain>` only if the Vercel production
frontend is used.

Vercel project (Root Directory = `frontend`):

| Var | Preview env | Production env |
|---|---|---|
| `VITE_API_BASE_URL` | staging Railway URL | prod Railway URL |
| `VITE_APP_ENV` | `staging` | *(unset)* |
| `VITE_LOCAL_FIRST` | `0` | `0` |

`VITE_LOCAL_FIRST=0` matters: `frontend/.env.production` bakes local-first
`1` for the installed PWA, but review surfaces should be thin clients hitting
the staging API on every request (Vercel's dashboard vars are process env, so
they override the `.env.production` file).

## Blast-radius checklist (why prod is safe)

- Separate Railway services **and** separate Postgres instances — no shared
  volume, host, or credentials.
- Production deploys only on merge to `main`; nothing auto-deploys `main`
  anywhere else.
- Separate databases mean separate logins — a session or ingest token issued
  by staging can't authorize against prod.
- No production credential survives a seed. The scrub deletes every
  `auth_session` row, regenerates every `ingest_token`, replaces every
  password hash (admin included) with the staging one, and regenerates +
  deactivates every invite code. Friends' emails and names are rewritten,
  and only the admin's own email is kept. So a leaked staging database
  exposes no working prod session, token, invite code or password hash.
- The one window where that isn't true: between the restore and the scrub
  (seconds), or after a failed scrub. `seed_staging.sh` warns loudly if the
  scrub fails. Re-run it or stop the staging service.
- `restore.sh`/`seed_staging.sh` refuse any target that looks like prod;
  writing *to* prod is not implemented anywhere in the repo.
- The phone PWA and Health Auto Export point at the prod origin; staging
  frontends are server-mode (no local DB to sync junk from).

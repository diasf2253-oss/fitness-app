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
| Auth | Strong `APP_TOKEN` | A *different* token (a leaked staging token opens nothing real) |
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
cp scripts/.env.backup.example scripts/.env.backup   # once; fill in both URLs
./scripts/seed_staging.sh                            # dump prod → restore staging → anonymise
```

The script: `pg_dump` prod (`scripts/backup.sh`) → `pg_restore` into
`STAGING_DATABASE_URL` via `scripts/restore.sh` (typed-confirmation guard
kept) → `scripts/anonymise_staging.sql`. Guards: it refuses if staging and
prod share host:port, and restore.sh separately re-checks the target against
`PROD_DATABASE_URL`. Anonymisation scrubs all free text (journal entries,
notes, plan titles), masks bodyweight with a constant offset + noise (trends
stay real for the calorie engine and charts), jitters steps/nutrition, and
resets profile age. Names, dates, sets and reps survive, so ranks, insights
and streaks look real.

After seeding, if `staging` carries migrations prod doesn't have yet,
restart/redeploy the staging service — `alembic upgrade head` runs on boot.

## Environment variables

Railway **staging** service (service → Variables):

| Var | Value |
|---|---|
| `DATABASE_URL` | reference the staging Postgres (`${{Postgres.DATABASE_URL}}`) |
| `APP_TOKEN` | staging-only token |
| `APP_ENV` | `staging` |
| `VITE_APP_ENV` | `staging` (consumed as a Docker build arg → badge baked into that origin's frontend) |
| `CORS_ALLOW_ORIGIN_REGEX` | `https://.*\.vercel\.app` (lets every Vercel preview call this API) |
| `ANTHROPIC_API_KEY` | empty (Coach 503s on staging) or a low-limit key |

Railway **production** service: `DATABASE_URL` (prod Postgres), `APP_TOKEN`
(strong), `ANTHROPIC_API_KEY`; `APP_ENV` unset (defaults to production). Add
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
- Different `APP_TOKEN`s — a staging token can't authorize against prod.
- `restore.sh`/`seed_staging.sh` refuse any target that looks like prod;
  writing *to* prod is not implemented anywhere in the repo.
- The phone PWA and Health Auto Export point at the prod origin; staging
  frontends are server-mode (no local DB to sync junk from).

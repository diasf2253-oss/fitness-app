# Friends Beta v1 — Claude Code Prompt Pack

**Project:** Fitness PWA — React/Vite (Vercel) + FastAPI/PostgreSQL (Railway)
**Goal:** Single-user app → invite-only multi-user beta. Fewer features, all of them working, on phone and desktop, in English and Portuguese.

---

## How to run this pack

1. **One phase per session.** Start a fresh Claude Code session (or `/clear`) for each prompt. Each prompt is self-contained and tells Claude Code to read `CLAUDE.md` first.
2. **Plan before code.** Every prompt instructs Claude Code to present a plan and wait. Read the plan. Only approve it when the migration steps and file changes make sense to you.
3. **Branch per phase.** `git checkout -b phase-1-auth` etc. Merge only when every acceptance criterion at the bottom of the phase passes. Commit as you go.
4. **Two checkpoints are yours, not Claude Code's:** after Phase 0 (you approve the feature list and bug list) and after Phase 5 (you test on real devices before sending the link).
5. **Model choice:** Phases 1 and 4 carry the most risk (data migration; broad refactor) — run those on your strongest model. The rest are routine.
6. **Never let Claude Code touch the production database.** All phases run against staging. You promote manually at the end.

## Decisions locked into this pack

- **Auth:** email + password, argon2 hashing, session in an httpOnly/Secure/SameSite=Lax cookie, ~30-day expiry. Same-origin via a Vercel rewrite of `/api/*` to Railway — no cross-domain cookies, no CORS pain.
- **Access:** one invite link with a code; signups land in `pending`; you approve/reject from an admin panel. **No email service in v1** — you tell friends directly, and password resets are temp passwords you generate in the admin panel.
- **Scope cuts for v1:** AI coach, progress photos, Apple Health import, push notifications. A `source` column is added now so health import bolts on later without a migration.
- **Onboarding (once, after first login):** language → name → units → goal → age/height/weight → training days → experience → feature selection → install-to-home-screen guide.
- **i18n:** full English + Brazilian Portuguese coverage, including decimal-comma input handling.
- **Feature flags:** per-user JSONB, chosen in onboarding, editable in settings and by you in admin, **enforced server-side** — not just hidden in the UI.
- **Parity:** every kept feature must be fully usable on a ~390px mobile viewport, not only on desktop.

---

## Prompt 0 — Audit & architecture doc (read-only, no code changes)

```
Read CLAUDE.md first. This is Phase 0 of a 6-phase plan to take this single-user
fitness PWA to an invite-only multi-user beta for a small group of friends. This
phase is READ-ONLY analysis plus documentation. Do not modify any application code.

Do the following:

1. Audit the entire repo (frontend and backend). Produce docs/AUDIT.md containing:
   - A feature inventory table: every user-facing feature/module, its frontend
     routes/components, its backend endpoints and database tables, and its status
     on a desktop viewport vs a ~390px mobile viewport (working / partial /
     broken / missing on mobile).
   - A mobile parity gap list: everything usable on desktop that is missing or
     degraded on mobile. This gap is a known top problem — be thorough.
   - A bug list: broken flows, dead code, console errors, half-built features.
     There is an existing onboarding/questionnaire flow that renders (visible in
     an incognito window) but persists nothing — find it and document where it
     lives.
   - A database schema summary, and whether a migration tool (e.g. Alembic) is
     already set up.
   - Anywhere localStorage/sessionStorage or client-side state is the source of
     truth for data that should live in PostgreSQL.

2. Append a section titled "V1 Friends Beta — Locked Decisions" to CLAUDE.md so
   future sessions inherit it. Include exactly: email+password auth with argon2
   and httpOnly cookie sessions; same-origin via Vercel rewrite of /api/* to the
   Railway backend; invite-code signup with admin approval (pending → active);
   no email service in v1 (admin-issued temp passwords for resets); per-user
   feature flags in a users.features JSONB, enforced server-side; onboarding
   wizard order (language, name, units, goal, age/height/weight, training days,
   experience, feature selection, install guide); full i18n in en and pt-BR with
   canonical metric storage in the database; v1 scope cuts (AI coach, progress
   photos, Apple Health import, push notifications); a source column
   (default 'manual') on workout and body-weight tables for future health
   import; mobile parity required for every kept feature.

3. Propose the canonical FEATURE LIST for the beta: which features from the
   inventory become the toggleable set in onboarding, each with a stable key
   (e.g. workouts, nutrition, weight, cardio, dashboard). Exclude the AI coach
   and progress photos — they are cut from v1.

4. Finish by printing: the feature inventory table, the parity gap list, the bug
   list, and the proposed feature keys. Then STOP for my review. Do not begin
   any fixes or refactors.
```

**Your checkpoint:** read the printed inventory. Strike anything you don't want, confirm the feature keys, add bugs Claude Code missed (e.g. things you've only seen on your phone). Tell it to update `docs/AUDIT.md` and the feature list in `CLAUDE.md` accordingly before you move on.

---

## Prompt 1 — Auth + multi-user data model

```
Read CLAUDE.md (including "V1 Friends Beta — Locked Decisions") and docs/AUDIT.md.
This is Phase 1 of 6: introduce authentication and a multi-user data model.
Present a plan first — including the exact migration and backfill steps — and
wait for my approval before writing code.

Requirements:

1. Safety first. Before any migration, run a pg_dump backup against the staging
   database and record row counts of every data table. Print the exact backup
   command I must run against production later. Never run anything against the
   production database yourself.

2. users table: id, email (unique, stored lowercase), password_hash (argon2),
   name, role ('admin' | 'user'), status ('pending' | 'active' | 'disabled'),
   language ('en' | 'pt-BR'), features JSONB default '{}', profile JSONB
   (units, goal, age, height_cm, weight_kg, training_days, experience),
   onboarding_completed boolean default false, must_change_password boolean
   default false, created_at, last_login_at.

3. Introduce Alembic if the audit found none. Write a migration that adds a
   user_id foreign key to every data table (nullable at first, NOT NULL after
   backfill). Write a backfill script that attaches ALL existing rows to my
   admin account. Create that admin account via a seed CLI command that reads
   ADMIN_EMAIL and ADMIN_PASSWORD from environment variables — never hardcode
   credentials.

4. Add a source column (text, default 'manual') to the workout and body-weight
   tables, for a future health-data import.

5. Auth endpoints: login sets a server-side-invalidatable session in an
   httpOnly, Secure, SameSite=Lax cookie with roughly 30-day expiry; logout
   invalidates it. Hash passwords with argon2 via a maintained library.
   Rate-limit login attempts. If must_change_password is true, the only allowed
   action after login is setting a new password.

6. Same-origin setup: add a vercel.json rewrite mapping /api/* to the Railway
   backend URL, switch all frontend API calls to relative /api paths, and
   restrict backend CORS to what the rewrite requires. Document in the README
   which URL goes where per environment.

7. Every data endpoint now requires an authenticated session and scopes every
   query by the session user's id. The client must never send or select a
   user_id. Unauthenticated requests get 401 and the SPA redirects to /login.

8. Frontend: a login page, authenticated app state, and logout. Plain English
   strings are fine for now — i18n arrives in Phase 3.

Acceptance criteria — demonstrate each before we merge:
- An incognito visit shows only the login screen; no data renders and no data
  API succeeds without a session.
- Logging in as the admin account shows all historical data intact — row counts
  match the pre-migration record exactly.
- A second seeded test user sees an empty app, and requesting the admin user's
  resource IDs with the test user's session returns 403 or 404.
- Session cookies are httpOnly and Secure; auth survives a page refresh and a
  PWA relaunch.
```

---

## Prompt 2 — Invite link, approval flow, admin panel

```
Read CLAUDE.md and docs/AUDIT.md. This is Phase 2 of 6: invite-gated signup,
an approval flow, and an admin panel. Present a plan first and wait for approval.

1. invite_codes table: code, label, active boolean, max_uses (nullable), uses,
   created_at. Add a seed/CLI command to create my first code. The signup page
   lives at /join and requires a valid active code in the URL (?code=...);
   without a valid code it reveals nothing about the app.

2. Signup collects name, email, password + confirmation, and a language picker
   (English / Português). It creates the account with status 'pending' and
   increments the code's use count. The user then sees a localizable "waiting
   for approval" screen; logging in later while still pending shows the same
   screen. There is no email sending in v1 — the screen says I will let them
   know personally.

3. Admin panel at /admin, enforced server-side by role='admin':
   - Pending signups with approve / reject actions.
   - Full user list with status control (active / disabled) and per-user
     feature toggles that edit users.features directly.
   - "Set temporary password": generates a random temp password, shows it to me
     exactly once, sets must_change_password on that user, and invalidates
     their existing sessions.

4. Approved users log in normally. Rejected or disabled users cannot log in and
   get a clear message.

Acceptance criteria — demonstrate each:
- /join without a valid code cannot create an account, verified at the API
  level, not just in the UI.
- Full journey works end to end: signup with a valid code → pending screen →
  admin approves → login succeeds (onboarding itself is a placeholder until
  Phase 3).
- Any /admin API called with a non-admin session returns 403, and the admin UI
  is unreachable for non-admins.
- Temp-password flow works end to end: admin sets it, user logs in with it, is
  forced to set a new password, and the user's old sessions are dead.
```

---

## Prompt 3 — i18n, onboarding wizard, feature flags, settings

```
Read CLAUDE.md and docs/AUDIT.md. This is Phase 3 of 6: internationalization,
the onboarding wizard, per-user feature flags, and the settings page. Present a
plan first and wait for approval.

1. i18n foundation: add react-i18next (or the project's existing equivalent if
   one exists) with en and pt-BR resource files. Move EVERY user-facing string
   into the translation layer — including the login, signup, waiting-for-
   approval, and admin screens built in earlier phases, plus validation and
   error messages. The language preference lives on the user record, applies at
   login, and is switchable in settings. The pt-BR copy must read like natural
   Brazilian Portuguese, not literal machine translation.

2. Locale correctness: numeric inputs accept a decimal comma in pt-BR (typing
   82,5 as a body weight must store 82.5) and dates render per locale. The
   database always stores canonical metric values; if the user picks imperial
   units, convert at the display/input edges only.

3. Onboarding wizard, forced exactly once after first login while
   onboarding_completed is false, in this order: language → name → units
   (metric / imperial) → goal (cut / bulk / maintain / endurance) → age, height,
   weight → training days per week → experience level → feature selection →
   install guide. Feature selection presents the canonical feature keys from
   CLAUDE.md as toggles, all enabled by default. The install guide detects the
   platform: iOS Safari gets Share → Add to Home Screen steps with visuals;
   Android/Chrome gets the install prompt or menu steps; an already-installed
   PWA skips this step.

4. Persist every answer to the user record (profile JSONB, language, features),
   then set onboarding_completed. Delete or fully repurpose the old
   non-functional questionnaire found in the audit — no dead flow may remain
   anywhere in the app.

5. Feature flags: navigation and routes render only the user's enabled
   features, AND the backend enforces flags on the corresponding endpoints —
   a disabled feature's API returns 403 for that user. Settings page: edit
   profile fields, change units and language, change password, toggle features
   on/off, log out.

Acceptance criteria — demonstrate each:
- A freshly approved user is forced through onboarding exactly once, and every
  answer persists across sessions and devices.
- Choosing Português at step 1 makes the entire remaining product Portuguese —
  grep the frontend for suspicious hardcoded literals and show the result is
  clean on all happy paths.
- Disabling a feature removes it from navigation, blocks its route, and makes
  its API return 403; re-enabling restores it with no data loss.
- Entering 82,5 as weight in pt-BR stores 82.5 and displays back correctly in
  both locales.
```

---

## Prompt 4 — Feature completeness, mobile parity, bug fixes

```
Read CLAUDE.md and docs/AUDIT.md. This is Phase 4 of 6 and the largest: make
every kept feature actually work, on both desktop and mobile. Present a plan
first, then work feature by feature with a commit per feature.

1. Scope is the approved feature list in CLAUDE.md. Remove the AI coach and
   progress photos from the UI, routes, and navigation. Leave any existing data
   intact; delete code only where removal is clean and low-risk, otherwise
   leave it dormant and unreachable.

2. For each kept feature, close every gap recorded in docs/AUDIT.md: fix the
   listed bugs, finish half-built flows, and achieve mobile parity. Mobile
   parity means fully usable at ~390px width: mobile navigation reaches every
   kept feature, forms work with mobile keyboards (correct inputmode and
   autocomplete attributes), no horizontal scrolling, safe-area insets
   respected in the installed PWA, and touch targets large enough to hit.

3. Every data view needs loading, empty, and error states — a brand-new user
   with zero data must see sensible, translated empty states everywhere, in
   both languages.

4. Stay consistent with the codebase's existing patterns. Do not introduce new
   frameworks or redesign features that already work — this phase is about
   finishing and fixing, not reinventing.

Acceptance criteria — demonstrate each:
- An updated parity matrix in docs/AUDIT.md: every kept feature × (desktop,
  mobile) marked working, with a one-line note of what changed.
- Every bug from the Phase 0 list is fixed, or explicitly listed as deferred
  with a reason I can accept.
- Zero console errors on the happy path of every kept feature, on both desktop
  and mobile viewports.
- A brand-new user with no data can complete each feature's core loop (create a
  workout, log an entry, view history, etc.) on a phone-sized viewport.
```

---

## Prompt 5 — Hardening, smoke test, release check

```
Read CLAUDE.md and docs/AUDIT.md. This is Phase 5 of 6, the final code phase:
hardening and release verification against the staging deployment. Present a
plan first.

1. Hardening pass: rate limiting on login and signup, sensible security
   headers, no secrets anywhere in the repo (environment variables only),
   session/cookie/rewrite behavior verified on the deployed preview URL, and
   all leftover debug logging removed.

2. Write docs/SMOKE_TEST.md as a numbered manual script, then execute every
   step you can yourself against staging, marking each pass/fail:
   1.  Incognito → app URL → login screen only; no data or API leaks.
   2.  /join with an invalid or missing code is blocked, at UI and API level.
   3.  Valid code → signup in Portuguese → pending screen, in Portuguese.
   4.  Admin approves → user logs in → completes onboarding in pt-BR → the
       entire UI is Portuguese with no stray English.
   5.  Features selected in onboarding appear; deselected ones are absent from
       navigation and their APIs return 403.
   6.  Log a workout and a body-weight entry on a mobile viewport; both are
       visible on desktop after refresh.
   7.  A second user cannot access the first user's data — probe the API
       directly with the first user's real resource IDs.
   8.  Settings: toggle a feature off and on, switch language both ways, change
       password (old sessions die).
   9.  Temp-password reset flow end to end.
   10. The admin account still shows all historical data; row counts match the
       pre-migration backup.
   11. Lighthouse: PWA installable; no severe accessibility failures on the
       core screens.

3. Fix anything that fails, re-run, and finish by printing the completed
   checklist plus the exact remaining steps I must do by hand (production
   backup and migration commands, environment variables to set, invite code
   generation).
```

---

## Your checklist (not Claude Code's)

**Before Phase 1**
- Create a staging database on Railway (duplicate the Postgres service or add a second database) and point a Vercel preview environment at it. All phases run here.
- Take a `pg_dump` backup of production and store it somewhere safe off Railway.
- Have ready: `ADMIN_EMAIL`, `ADMIN_PASSWORD`, a long random `SESSION_SECRET`, the staging `DATABASE_URL`, and your Railway backend URL for the rewrite.

**After Phase 0**
- Approve or edit the feature inventory, parity gaps, bug list, and feature keys. This list drives Phases 3 and 4 — time spent here pays off double later.

**After Phase 5**
- Test on real devices: your iPhone plus at least one borrowed Android. Install the PWA on both and run `docs/SMOKE_TEST.md` yourself, in Portuguese on one device and English on the other.
- Promote: fresh production backup → run the printed migration command against production → deploy → log in and verify your history → generate an invite code → send the link to the first two or three friends before the whole group.

**v1.1 parking lot (deliberately cut, ready to bolt on)**
- Email via Resend (needs a verified sending domain) for approval notices and self-serve password resets.
- Apple Health export import — the `source` column is already in place.
- Push notification reminders (iOS requires the installed PWA, 16.4+).
- AI coach returns, with per-user daily caps controlled from the admin panel.

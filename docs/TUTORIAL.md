# Using the app on your phone + laptop

A plain-English walkthrough: get it running, install it on both devices, invite
friends, pull in Apple Health, and take a quick tour.

> **Mental model.** A server (your Mac, or Railway in production) runs the
> "brain" — the backend and the database. Your laptop and phone are windows
> into it. The installed phone app also keeps its **own local copy** of your
> data, so it keeps working in a gym with no signal and syncs back when it can.
> This is **not** an App Store app; you install it from the browser.

---

## 0. What you need

- A Mac or Linux machine with Python 3.12+ and Node 20+.
- Your phone on the **same Wi-Fi** for the easy at-home path.
- (Optional, for Apple Health auto-sync) an always-on HTTPS URL — see
  [DEPLOY.md](DEPLOY.md).
- (Optional, for the AI report narrative) an Anthropic API key — see §6.

---

## 1. Start it (one command)

```bash
cd fitness-app
./start.sh
```

That builds the app, updates the database, creates the admin account and an
invite code, and serves everything — reachable by your phone too. Leave the
window open; that's the app being "on". It prints a banner like:

```
  This laptop:  http://localhost:8000
  This phone:   http://<your-mac-ip>:8000

  Admin account: you@example.com (id=1, status=active)
  Active invite code already exists: <code>
```

The first run copies `backend/.env.example` to `backend/.env` and then
**stops, asking you to set a real `ADMIN_PASSWORD`** — it refuses to create an
admin with the template's `changeme`, because the app is reachable by anyone
on your Wi-Fi. Set `ADMIN_EMAIL` and `ADMIN_PASSWORD` (8+ characters) in
`backend/.env` and run `./start.sh` again. Change them later with
`python -m app.set_admin_password` from `backend/`.

(Use `./start.sh --no-build` for faster restarts when you only touched the
backend.)

---

## 2. Log in on the laptop

1. Open **http://localhost:8000** and log in with your admin email + password.
2. **Install as an app** (optional): Chrome address bar → **install icon**. It
   lands in your dock, in its own window.

---

## 3. Install it on the phone

1. On the phone, open the **phone URL** from the banner
   (`http://<your-mac-ip>:8000`) and log in.
2. **Add to Home Screen:**
   - **iPhone (Safari):** Share → *Add to Home Screen* → Add.
   - **Android (Chrome):** ⋮ → *Install app*.
3. Open it from the new icon — full-screen, native-feeling.

> **Honest limit of the at-home path:** it only works while the Mac is on and
> both devices share the Wi-Fi, and it's plain `http`. For "works anywhere" and
> Apple Health auto-sync you want a stable HTTPS URL — see [DEPLOY.md](DEPLOY.md).

---

## 4. Invite friends

The app is invite-only. The banner (and the deploy log in production) shows
the invite code.

1. A friend opens `/join`, enters the invite code, and creates an account.
2. They land on a *pending* screen. You open **/admin** (the admin link in the
   sidebar) and **approve** them.
3. Forgot a password? There's no email service — from **/admin**, issue a
   **temporary password**. They must change it on next login, and their other
   sessions are logged out.

Every account's data is completely separate; nobody sees anyone else's.

---

## 5. Sync your real data from Apple Health

A web app can't read Apple Health — iOS only lets native apps do that — so the
phone **pushes** the data in. Everything you need is under
**Settings → Apple Health sync**:

1. **Install the Shortcut** ("Tracker Health Sync") and paste in the *Server*
   and your personal *Token* when it asks.
2. **Add a time-of-day automation** in the Shortcuts app so it runs every
   morning, or tap **Sync Health now** in the app at any time.
3. **History backfill:** on iPhone, Health → profile photo → **Export All
   Health Data** → upload the `export.zip` in Settings once.

Nutrition and micronutrients can also arrive via the Health Auto Export app
(Settings shows the URL and token for it). Manually corrected days are never
overwritten by synced data. Full details:
[HEALTH_INGEST_SHORTCUT.md](HEALTH_INGEST_SHORTCUT.md).

---

## 6. Optional AI features (Claude)

The weekly **Report** can add an AI-written plan. It uses the **Claude API**,
so it needs a key of its own:

1. Get a key at **console.anthropic.com**.
2. Add it to `backend/.env`: `ANTHROPIC_API_KEY=sk-ant-...`
3. Restart `./start.sh`.

Without a key those endpoints politely return "not configured" and everything
else works. (A full chat Coach exists in the backend but is hidden from the UI
for now.)

---

## 7. A 60-second tour

- **Dashboard** — your day at a glance: daily check-in, nutrition vs targets,
  weight/steps/sleep trends, this week's training, a month calendar with
  per-day detail.
- **Workout** — start from a routine or empty, log sets with big thumb-friendly
  buttons, rest timer between sets, previous numbers prefilled.
- **Routines** — reusable workouts grouped into splits, with ready-made split
  templates and per-set weight / reps / RIR plans.
- **History** — every past session, plus per-exercise progress charts
  (estimated 1RM and volume) with PR detection.
- **Diet** — an adaptive calorie target that moves once a week toward your
  goal (cut / maintain / bulk), macros, and a micronutrient breakdown.
- **Insights** — this week vs last, and which of your numbers move together,
  with honest small-sample caveats.
- **Report** — a weekly or biweekly review you can download as Markdown.
- **Ranks** — a strength tier per lift from your best estimated 1RM relative to
  bodyweight, plus a body map of which muscles you train.
- **Workout generator** — build a program from a few inputs and apply it as
  routines.
- **Manual log** — type in or correct a day's weight/steps/sleep/nutrition.
  Manual entries always win over Apple Health.
- **Settings** — profile, trackers, rest timer, streak rules, volume targets,
  Apple Health sync.

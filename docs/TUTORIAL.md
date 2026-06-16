# Using the app on your phone + laptop

A plain-English walkthrough: get it running, install it on both devices, make
them sync, pull in Apple Health, and switch on the AI Coach. Keep this file
open and jot notes in it as you go — likes, dislikes, ideas for later.

> **Mental model.** Your Mac runs the "brain" (the backend + the database).
> Your laptop and phone are just windows into it. They sync automatically
> because they talk to the *same* brain — there is no separate "sync" button.
> This is **not** an App Store app; you install it from the browser.

---

## 0. What you need

- Your Mac (it hosts everything). Python 3.13 and Node 22 are already set up.
- Your phone and Mac on the **same Wi-Fi** for the easy path.
- (Optional, for use *away* from home) a free Cloudflare account — see §6.
- (Optional, for the Coach) an Anthropic API key — see §5.

---

## 1. Start it (one command, on the Mac)

```bash
cd "/Users/felipedias/Claude Projects/fitness-app"
./start.sh
```

That builds the app, updates the database, and serves it — reachable by your
phone too. Leave the window open; that's the app being "on". It prints a banner
with the two URLs you need:

```
  This laptop:  http://localhost:8000
  This phone:   http://<your-mac-ip>:8000
```

(Use `./start.sh --no-build` for faster restarts when you only touched the
backend. To keep it on after the laptop sleeps, see [DEPLOY.md](DEPLOY.md).)

---

## 2. Install it on the laptop

1. Open **http://localhost:8000/?token=changeme** — the `?token=` part signs you
   in automatically (use your real `APP_TOKEN` if you've changed it). Or just
   open `http://localhost:8000` and enter the token once in Settings.
2. **Install as an app:** Chrome address bar → **install icon** (or ⋮ →
   *Install Tracker*). It lands in Launchpad / the dock, in its own window.

---

## 3. Install it on the phone — scan one QR

The fast path: no typing an IP, no typing a token.

1. On the **laptop**, go to the **phone URL** from the start banner
   (`http://<your-mac-ip>:8000`) — not localhost — then open
   **Settings → Add a device**. A QR appears.
2. **Scan it with the phone camera** → the app opens already signed in.
3. **Add to Home Screen:**
   - **iPhone (Safari):** Share → *Add to Home Screen* → Add.
   - **Android (Chrome):** ⋮ → *Install app*.
4. Open it from the new icon — full-screen, native-feeling.

**Now they're synced.** Log something on the phone, refresh the laptop — it's
there. Same database, instantly. There's nothing else to switch on.

> **Two honest limits of this at-home path:**
> - It works while the Mac is on and both devices are on the same Wi-Fi.
> - It's plain `http`, so iOS makes a basic web-clip and the Apple Health
>   *push* (§4) is happier over HTTPS. For "works anywhere" + a proper install,
>   do the one-command tunnel in §6 — then the QR and Health URL all use the
>   `https://…` address automatically.

---

## 4. Sync your real data from Apple Health

All health + nutrition data (weight, steps, sleep, food incl. micronutrients —
your YAZIO food shows up here because YAZIO already writes into Apple Health)
comes in two ways.

### A. Daily auto-sync — "Health Auto Export" app

1. Install **Health Auto Export – JSON+CSV** from the App Store (it's the
   bridge from Apple Health to our app).
2. New Automation → **Format: JSON**, **Type: REST API / POST**.
3. **URL:** `http://<mac-address>:8000/api/ingest/health`
   (or your `https://…` tunnel URL from §6 — strongly preferred for this).
4. **Header:** `Authorization: Bearer changeme` (your `APP_TOKEN`).
5. **Metrics:** steps, weight/body mass, sleep analysis, plus the dietary ones
   (energy, protein, carbs, fat, and any vitamins/minerals you want).
6. **Schedule: daily** (e.g. each morning).

The app fills these in for you: **Settings → Apple Health sync** shows the exact
URL and `Authorization` header for *this* device with **Copy** buttons — tap to
copy, paste into Health Auto Export. No typing.

### B. One-time history backfill — `export.zip`

Bring in years of past data at once:

1. On iPhone, open **Health** → tap your profile photo → **Export All Health
   Data** → you get `export.zip`. AirDrop it to the Mac.
2. In the app: **Settings → Apple Health sync → History backfill →** choose the
   zip → **Import**. Manually-corrected days are never overwritten.

> Until real data flows, use **Settings → Developer → Load sample data** to see
> every chart populated, then **Clear sample data** when your real history lands.

---

## 5. Turn on the AI Coach (powered by Claude)

> Quick clarification: the in-app Coach uses the **Claude API** (a key in a
> file). That's different from "Claude Code", the terminal assistant that
> *builds* this app. You don't connect Claude Code to the app — you give the
> app its own Claude key.

1. Get a key at **console.anthropic.com** (Billing → add a little credit;
   plans cost cents each).
2. Add it to `backend/.env`:
   ```
   ANTHROPIC_API_KEY=sk-ant-...
   ```
3. Restart the backend (stop with Ctrl-C, run the `uvicorn …` line again).
4. Open **Coach** in the app. The "Set up the coach" note is gone; you now have
   *Plan next workout / Plan my day / Plan studying* and a chat box. Plans come
   as proposals — nothing saves until you tap **Accept**.

---

## 6. Use it anywhere (optional, recommended once you're hooked)

The same-Wi-Fi path is fine to start. To use the app on the train, give Health
Auto Export a stable HTTPS target, and make the phone install "proper", expose
the Mac with a **Cloudflare Tunnel** — free, no port-forwarding:

```bash
brew install cloudflared
cloudflared tunnel --url http://localhost:8000
```

It prints a `https://something.trycloudflare.com` URL. Use that everywhere
instead of the `http://<mac-ip>:8000` address (open it on each device, set the
token, re-add to home screen). A permanent named URL and the Railway
alternative (so it doesn't depend on your Mac being awake) are in
[DEPLOY.md](DEPLOY.md).

> **Before you expose it publicly, change the token.** Edit `backend/.env`,
> set `APP_TOKEN` to a long random string (`openssl rand -hex 24`), restart,
> and re-enter it on each device. `changeme` is fine on home Wi-Fi, not on a
> public URL.

---

## 7. A 60-second tour of the app

- **Dashboard (Home)** — your day at a glance: today's check-in, nutrition vs
  targets, weight/steps/sleep charts, this week's training. The right rail has
  a calendar — tap any day to see (and tick off) what happened.
- **Coach** — plans and chat grounded in your real data (§5).
- **Workout** — start an empty session or one from a routine, log sets with big
  thumb-friendly buttons, rest timer between sets.
- **Routines** — reusable workout templates (the Coach can create these).
- **History** — every past session; on the laptop it's a two-pane browser.
- **Insights** — this week vs last, and which of your numbers move together
  (e.g. sleep vs training), with honest "small sample" caveats.
- **Manual log** — type in a day's weight/steps/sleep/nutrition by hand, or
  correct a synced day. Manual entries always win over Apple Health.
- **Settings** — token, Apple Health sync + backfill, trackers, sample data.
- **Daily check-in** (on the Dashboard) — habits, a 1–5 mood, a journal line.

---

## 8. Capture your likes / dislikes / ideas (do this here)

You wanted to slowly shape where this goes. Two easy ways to keep that with you:

1. **In the app:** Settings → Trackers → add a **Text** tracker called
   "App ideas". Then the dashboard check-in gives you a daily box to drop a
   thought — it lands on that day's calendar, so your feedback is timestamped
   alongside how you were using the app.
2. **In this file:** jot running notes below. When you next sit down with Claude
   Code, point it here and it'll turn them into the next phase.

### My notes

- Likes:
- Dislikes:
- Ideas for later:

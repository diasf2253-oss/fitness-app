# Health ingest via iOS Shortcut

How **weight, steps and sleep** get off an iPhone and into the app.

## Why this exists

**A web app cannot read Apple Health.** iOS gives HealthKit access to native
apps only — never to a website or an installed PWA. So this app can never pull
your health data; the phone has to *push* it.

An internal diagnosis of the Apple Health pipeline found the old push path
(Health Auto Export's scheduled background jobs) was untrustworthy mostly
because of *delivery*: HAE's pushes only fire reliably when its app is open,
and quick-tunnel URLs rot. An iOS **Shortcut** driven by a Personal Automation
runs on the phone's own schedule and posts straight at the production URL
(stable, always on).

It reuses the exact same validated ingest pipeline as the `export.xml` history
backfill — unit conversion, wake-date sleep bucketing, multi-source dedup and
manual-precedence — so what it writes obeys the same rules a backfill does.

This is additive. HAE and the `export.zip` backfill still work unchanged, and
nutrition/micronutrients still arrive through those. The Shortcut just covers
the three core numbers reliably.

---

## For a beta user: three steps

Everything you need is in the app under **Settings → Apple Health sync**.

1. **Install the Shortcut.** Tap **Get "Tracker Health Sync"** in Settings.
   It opens the Shortcuts app and asks two questions on install:
   - *Server* — copy it from Settings (the **Server** row).
   - *Token* — copy it from Settings (the **Token** row). It's yours alone;
     treat it like a password.
2. **Add the automation.** Shortcuts app → **Automation** tab → **+** →
   **Time of Day** → 08:00 → Run *Tracker Health Sync* → turn **off**
   "Ask Before Running". A second one around 21:00 is a good safety net.
3. **Check it worked.** Settings shows a **Latest data** table — weight,
   steps, sleep and nutrition each with how recent they are. You can also tap
   **Sync Health now** any time to run it immediately.

### The in-app "Sync now" button

iOS exposes a `shortcuts://` URL scheme, so the app really can start the sync:

```
shortcuts://x-callback-url/run-shortcut?name=Tracker%20Health%20Sync&x-success=<return url>
```

`x-success` bounces you back to the app when the push finishes. iOS shows a
one-time confirmation the first time the site opens Shortcuts.

**Note on automatic triggering:** iOS's "When I open an app" automation trigger
does **not** reliably list home-screen web apps, so there is no way to make the
sync fire simply because you opened this app. The supported combination is the
**time-of-day automation** (hands-free, daily) plus the **Sync now** button
(on demand). Don't promise more than that.

If the Shortcut ever stops working, the usual cause is a **regenerated token** —
paste the new one from Settings into the Shortcut (Shortcuts → long-press →
Edit → the Token text field).

---

## Endpoint spec

| | |
|---|---|
| **Method** | `POST` |
| **URL** | `https://<your-app>/api/ingest/health/shortcut` |
| **Auth header** | `Authorization: Bearer <ingest_token>` |
| **Content-Type** | `application/json` |

The bearer value is the **per-user `ingest_token`**, shown in
Settings → Apple Health sync. It is *not* a shared app-wide secret — every
account has its own, and it is what tells the server whose data this is. (A
Shortcut can't hold a cookie jar, which is why ingest uses a bearer token when
the rest of the app uses a session cookie.) It never expires; rotate it with
**Regenerate token** in Settings if it leaks.

Use your **production** origin as `<your-app>` — the same host the installed
PWA talks to. Settings shows your exact URL, pre-filled and copyable.

### Request body

All three sections are optional — post only what you have. A section may be a
single object or an array of them.

```json
{
  "weight": [
    { "date": "2026-07-18T07:20:00-03:00", "kg": 82.4 }
  ],
  "steps": [
    { "date": "2026-07-18", "count": 11205 }
  ],
  "sleep": [
    {
      "date": "2026-07-18",
      "asleep_minutes": 427,
      "in_bed_minutes": 465,
      "deep_minutes": 68,
      "rem_minutes": 95,
      "core_minutes": 264
    }
  ]
}
```

**Fields** (accepted spellings in parentheses — pick whichever your Shortcut
produces most easily):

- **`date`** — required on every item.
  - Weight is bucketed by this timestamp's **calendar date**; the *latest*
    reading of a day wins.
  - Steps and sleep take the **date** portion only.
  - Sleep's `date` is the **wake-up morning** (run the automation in the
    morning and use "today").
  - Accepts a bare date (`2026-07-18`) or an ISO 8601 timestamp with offset
    (`2026-07-18T07:20:00-03:00`). Values like `82,5` (comma decimal) are
    understood too.
- **weight** — value in `kg` (or `value` / `weight_kg` / `qty`), optional
  `unit` of `kg` (default), `lb`, or `g`.
- **steps** — `count` (or `steps` / `value` / `qty`).
- **sleep** — `asleep_minutes` and/or `in_bed_minutes`, plus optional
  `deep_minutes` / `rem_minutes` / `core_minutes` (`_minutes` suffix optional,
  camelCase accepted).

### Response — the import report

`200 OK` with a report of exactly what landed. This is the trust gate: check
it (or Settings' *Latest data* table) to confirm a push worked.

```json
{
  "status": "ok",
  "records_parsed": 3,
  "days": { "weight": 1, "steps": 1, "sleep": 1, "nutrition": 0 },
  "rows_created": 3,
  "date_range": { "from": "2026-07-18", "to": "2026-07-18" },
  "sections_handled": ["sleep", "steps", "weight"],
  "ignored": [],
  "warnings": []
}
```

- `rows_created` counts **new** days. A repost of the same data returns `0` —
  the upserts are idempotent.
- A day you edited by hand in the app is **never** overwritten (source
  precedence: `manual` beats `apple_health`).
- Bad items are skipped with a note in `warnings` rather than failing the
  whole push; unknown top-level keys are echoed in `ignored`.

---

## Building the Shortcut (once, for everyone)

`.shortcut` files are a signed binary format, so this can't be generated from
the repo. Build it once on your own phone, then **Share → Copy iCloud Link**
and put that link in `VITE_HEALTH_SHORTCUT_URL` — every beta user installs
from it.

The design points that matter:

1. **Name it exactly `Tracker Health Sync`.** The in-app Sync button
   deep-links by name (`HEALTH_SHORTCUT_NAME` in `frontend/src/env.js`).
2. **Use Import Questions for `Server` and `Token`.** Shortcuts prompts for
   these at install time and stores the answers, so one shared link works for
   everyone without any per-person editing. (Shortcut details → *Import
   Questions* → add one per text field you want asked.)
3. **Post a rolling last 7 days**, one item per day per metric — not just
   "today". Because the upserts are idempotent and `apple_health` overwrites
   `apple_health`, every run repairs any day a previous run missed. This
   self-healing is exactly what HAE lacked (a missed evening push used to
   freeze a partial day permanently).
4. **Aggregate steps daily.** Apple Health stores overlapping samples from
   both iPhone and Watch; a raw sum double-counts them. Use
   *Get Health Sample* with a **daily** total, or aggregate in the Shortcut.
5. **Key sleep to the wake-up morning.** The backend's `_night_of` in
   `app/health_ingest.py` expects that, and it's how Apple presents sleep.

Rough action sequence:

- *Text* actions holding the two Import Question answers → variables
  `Server`, `Token`.
- *Get Health Sample* → **Body Mass**, last 7 days → *Repeat with Each* →
  build `{ "date": …, "kg": … }` dictionaries into a list.
- *Get Health Sample* → **Steps**, last 7 days, daily totals → same shape with
  `count`.
- *Get Health Sample* → **Sleep Analysis**, last 7 nights → `asleep_minutes` /
  `in_bed_minutes` per wake date.
- *Dictionary* combining the three lists under `weight` / `steps` / `sleep`.
- *Get Contents of URL*:
  - URL = `<Server>/api/ingest/health/shortcut`, Method = **POST**
  - Headers: `Authorization` = `Bearer <Token>`, `Content-Type` =
    `application/json`
  - Request Body = **JSON** (the dictionary above)
- Optionally *Show Result* while testing, then remove it so the automation can
  run silently.

## Testing it

```bash
curl -X POST https://<your-app>/api/ingest/health/shortcut \
  -H "Authorization: Bearer <ingest_token>" \
  -H "Content-Type: application/json" \
  -d '{"weight":[{"date":"2026-07-18","kg":82.4}],
       "steps":[{"date":"2026-07-18","count":11205}],
       "sleep":[{"date":"2026-07-18","asleep_minutes":427,"in_bed_minutes":465}]}'
```

The response report should show the rows. Then check freshness:

```bash
curl -b cookies.txt https://<your-app>/api/health/sync-status
```

`days_stale` should be `0` for whatever you just posted. The same numbers
drive the Settings card, the sidebar sync line and the stale-data banner.
Note that `sync-status` counts **real readings only** — interpolated
(`estimated`) and demo (`sample`) rows are excluded, so it can never claim
fabricated data is fresh.

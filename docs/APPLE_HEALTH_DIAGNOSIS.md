# Apple Health ingest — diagnosis (workbook H4, 2026-07-18)

H4 verdict: grade D, "the most important part of the app". Symptoms: slow to
arrive, needs manual triggering, doesn't always save, sometimes wrong. Findings
from reading `routers/health.py`, `health_metrics.py`, `health_xml.py`, the
README runbook, and the HAE flow — ordered by likely impact.

## Why it needs manual triggering / doesn't always save

1. **iOS kills Health Auto Export's background automations.** HAE scheduled
   pushes only run reliably when the app is opened. Not fixable server-side.
   Mitigation: make every push self-healing (see #2) so opening HAE once a
   week backfills everything missed.
2. **The export window is fragile.** If HAE exports "today" only, any missed
   evening push freezes that day's nutrition at whatever a midday push carried
   — partial data becomes *permanently* wrong. Fix: set the HAE automation's
   date range to a **rolling last 7 days**. The server upserts are idempotent
   and `apple_health` overwrites `apple_health`, so every push then repairs
   the previous week automatically.
3. **The push URL is fragile.** The README flow uses `cloudflared tunnel`
   quick tunnels, whose URL *changes on every restart* — the HAE automation
   then 404s silently until reconfigured. The laptop also must be awake.
   Fix: point the HAE automation at the **production Railway URL** (stable,
   always on) — the phone PWA already syncs against that API when installed
   from the production frontend. This removes both failure modes at once.

## Why it's sometimes wrong

4. **Steps can double-count.** `ingest_health` sums every `step_count` point
   per day (`by_date[d] += qty`). Apple Health stores overlapping samples
   from both iPhone and Watch; Apple dedupes them for display, a raw sum does
   not. Whether this bites depends on HAE's aggregation setting. Fix on our
   side: none clean; fix in HAE: set aggregation to **Daily** so HAE sends
   one pre-deduplicated point per day. Worth verifying the setting.
5. **Sleep is keyed to the night's *start* date** (`nights[start_date]`),
   while Apple keys sleep to the wake date. A normal 23:30→07:00 night lands
   on the previous calendar day; a post-midnight bedtime lands on the wake
   day — inconsistent bucketing, and "last night's sleep" reads off by one.
   Same double-count risk as steps when both Watch and iPhone record a night.
6. **The maintenance estimate ingests partial days.** Visible right now in
   the app: ceiling 1,700 kcal < floor 1,800. `estimate_maintenance` averages
   intake days that may be half-logged (see #2), which drags the estimate
   into nonsense. J10's "hard validation bounds" ruling (Session 16) applies
   here too; a cheap guard: exclude intake days below ~1,000 kcal from the
   maintenance fit, the same way weight math excludes sample data.

## Why it feels slow

7. Mostly latency, not server speed: data appears only when a push fires
   (see #1–#3). The ingest itself is per-point `db.query` upserts — fine at
   daily volumes, and the XML backfill is stream-parsed.

## Recommended order of attack

1. Config only, zero code: HAE → rolling 7-day window, Daily aggregation,
   production URL as target. Likely fixes "manual", "doesn't save", and most
   of "wrong".
2. Small code fixes: sleep keyed to wake date; intake-day sanity floor in
   `estimate_maintenance` (+ tests; both also in the twin).
3. Then re-grade H4 after two weeks of real use.

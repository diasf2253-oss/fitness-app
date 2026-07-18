# ✈️ Flight Workbook — remaining sessions

Sessions 0–6 are **done** — answered on the 2026-07-14 flight, recovered from the
RStudio buffer on 2026-07-18, and preserved with the answers inline in
`FLIGHT_WORKBOOK_DONE.md`. Both files are committed to git now — edit fearlessly.
Say **"process my workbook"** any time to turn the answers into the roadmap.

Still ahead, in suggested order:
- **Sessions 7–8** — the offline-coach split + technical decisions.
- **Session 9 ⭐** — the priority matrix + NOW/NEXT/NEVER boxes — the main deliverable.
- **Session 10** — free writing, then **Part II (Sessions 11–22, ~8h)** deep work.
- **Appendix A** — answer key for Sessions 11–13. No peeking until you've committed answers.

---

## Session 7 · Design exercise: offline coach & intelligence (~1h)

The Coach needs the network + API key. The phone is offline in the gym. Decide what
intelligence lives where.

**C1.** Split these between **rule-based on-device** (works offline, deterministic) vs
**LLM via network** (smart, needs laptop/internet) vs **don't want it**:
- Progression suggestions: ______
- Deload detection: ______
- "You haven't trained X in 10 days" nudges: ______
- Weekly narrative review: ______
- Program redesign ("switch me to 5 days"): ______
- Diet Q&A ("can I fit a burger tonight?"): ______
- Form/technique advice: ______

**C2.** The weekly ritual: describe the ideal Sunday coach interaction — does it open
with the report? Does it end with next week's plan items pre-created for your approval?
Script the conversation's first 3 exchanges.

**C3.** Notifications: the PWA can push. Which are welcome, which are noise?
- [ ] Streak at risk tonight  - [ ] Weigh-in reminder (morning)  - [ ] Rest timer done
  (already have)  - [ ] Weekly report ready  - [ ] "Deload suggested"  - [ ] Plan item
  due  - [ ] None — I open the app when I open the app

**C4.** Coach memory: should it remember decisions across chats ("you said squats hurt
your knee in June")? Where's the line between helpful memory and creepy dossier?

**C5.** If the API cost ever bothered you: which coach features would you pay pennies
for daily, and which should be free/local forever?

---

## Session 8 · Technical decisions (~45 min)

Not code — decisions. Each unblocks work I can execute later.

**X1.** Sync tombstones (deletes currently resurface). How much does this bite you in
practice? Priority: [ ] fix next [ ] fix eventually [ ] never noticed.

**X2.** Backup: today the laptop's SQLite is the fortress and the phone is a full
replica. Is that enough disaster recovery for years of training data? Do you want an
automatic encrypted export (e.g. weekly file into iCloud/Drive)? Define the rule.

**X3.** Data export: if you abandoned the app in 2 years, what format would you want
your data in? (CSV per table? One big JSON? Doesn't matter?) — this decides whether
we build an export endpoint.

**X4.** Multi-device future: phone + laptop today. Tablet? A second phone? Does the
QR-pairing flow need to get better, or is it fine as a rare ritual?

**X5.** The `feat/redesign-qr-diet` branch also had Fly.io deploy config + Postgres
scripts (the `chore/backups` branch). Do you want the app reachable over the internet
(real server), or is home-LAN-only a feature, not a limitation? This is a fork in the
road — decide it deliberately.

**X6.** Testing: the math is well covered (parity suites). What actually breaks for
you day-to-day — UI flows? sync edge cases? Name the last 3 real bugs you hit, and
we'll aim tests at that class of problem.

**X7.** The dead branches (`feat/redesign-qr-diet`, `chore/*`, `claude/*`) are still
in the repo. After confirming nothing else is missing: delete them? [ ] yes [ ] keep
as archaeology.

---

## Session 9 · Priority matrix (~1h) — ⭐ the main deliverable

Score every candidate 1–5 on **Impact** (on YOUR training/health), **Craving** (how
much you personally want it), and **Cost** (5 = cheapest to build). Multiply for a
crude score, then override with your gut in the Rank column — the override IS the data.

| # | Feature | Impact | Craving | Cost | Score | Rank |
|---|---|---|---|---|---|---|
| 1 | Progression engine (Session 4) | | | | | |
| 2 | Rank benchmark calibration (T5b) | | | | | |
| 3 | Rank decay / seasons (T5d, G4) | | | | | |
| 4 | Points/XP system (Session 6) | | | | | |
| 5 | Achievements (G5) | | | | | |
| 6 | Body measurements (B1) | | | | | |
| 7 | Progress photos (B3) | | | | | |
| 8 | Injury log (B4) | | | | | |
| 9 | Deload detection (P5) | | | | | |
| 10 | Maintenance/bulk diet modes (H1a) | | | | | |
| 11 | Auto-scaling protein (H1d) | | | | | |
| 12 | Offline rule-based mini-coach (C1) | | | | | |
| 13 | Proactive coach w/ weekly ritual (C2) | | | | | |
| 14 | Push notifications (C3) | | | | | |
| 15 | Sync tombstones (X1) | | | | | |
| 16 | Auto encrypted backups (X2) | | | | | |
| 17 | Data export (X3) | | | | | |
| 18 | Internet deployment (X5) | | | | | |
| 19 | Superset/circuit logging (T1c) | | | | | |
| 20 | Generator v2: equipment/time/dislikes (T4b) | | | | | |
| 21 | Evolving routines (T3b) | | | | | |
| 22 | Per-sport activity stats (H3a) | | | | | |
| 23 | Real app name + icon (V6) | | | | | |
| 24 | *Your idea:* ______________ | | | | | |
| 25 | *Your idea:* ______________ | | | | | |

**Now the hard part.** Fill these three boxes — they become the literal roadmap:

**NOW (next 2 weeks):** 1. ______________ 2. ______________ 3. ______________

**NEXT (this quarter):** ______________________________________________

**LATER / NEVER (write at least 3 explicit NEVERs):** ______________________________

---

## Session 10 · Free writing & weird ideas (~45 min)

**W1.** The 10-second review: you're on the bus, you open the app for 10 seconds.
What ONE screen tells you everything you need? Design it — it probably doesn't exist yet.

**W2.** Describe your training history to the app as if it were a new coach: injuries,
sports background, what's worked, what hasn't, what you're afraid of. (This literally
becomes the Coach's context brief — write it well and I'll wire it in.)

**W3.** Steal shamelessly: from every fitness/health app you've ever used, list the
ONE thing each did best. (Strong's plate math? Whoop's recovery score? Duolingo's
streak psychology? MyFitnessPal's barcode scan?)

**W4.** The app in 2030: you've used it for 4 years. 800 workouts. What does it show
you on the anniversary screen?

**W5.** Anything that annoyed you this month that has nothing to do with features —
slow load? ugly font? weird wording somewhere? Petty complaints are excellent bug
reports. List everything, no filter.

**W6.** Questions FOR me (the AI that builds this with you): what do you want
explained about how the app works — anything you've been building on top of without
fully understanding? List them; I'll answer each when you're back.

---
---

# PART II — Deep work

The character of Part II is different: less "what do you want," more "understand the
machine, generate real data, make rulings." These sessions produce artifacts I can
act on directly (import, calibrate, fix).

## Session 11 · Learn the machine I: how sync actually works (~1h)

### Read (accurate as of today's code)

Every device holds the full dataset. Sync is a stateless exchange:

1. **Identity.** Workout entities (exercises, routines, sessions, sets, notes,
   activities, plan items, trackers) carry a globally unique `uuid`; their integer IDs
   are device-local and never travel. Foreign keys travel as the *parent's uuid* and
   are re-resolved on arrival. Health tables (weight/steps/sleep/nutrition) have no
   uuid — they merge on their `date`. Settings is a singleton (always row #1).
2. **Dirty flags.** The phone marks every locally-changed row `_dirty`. Push sends
   exactly the dirty rows; on success the flags clear. No clock comparison needed to
   decide *what* to send.
3. **Merge = last-write-wins.** Each row has `updated_at`. Incoming row newer than
   the local copy → incoming wins. Equal or older → skipped. Crucially, an applied
   row keeps its *original* timestamp — it is not re-stamped on arrival, so it won't
   look "newly edited" and echo back on the next exchange.
4. **Health precedence.** For the four health tables, a `manual` row is never
   overwritten by a synced/Apple-Health row, even a newer one. Manual is sacred.
5. **Natural-key rescue.** If both devices created "Cable Fly" independently before
   ever syncing, the uuids differ. Rather than crash on the unique name, sync falls
   back to matching by name (exercises), name+kind (trackers), tracker+date
   (tracker logs). The local uuid survives; incoming children are remapped onto it.
6. **Scope version.** When an app update adds new synced tables, a version bump
   forces one full re-pull so the new tables backfill (an incremental cursor from
   before the update predates them).
7. **The hole: no tombstones.** Deleting a row only deletes it locally. The other
   device still has it, and the next pull happily re-inserts it. Deletes resurface.

### Quiz (answers in Appendix A — commit before checking)

**Q1.** You edit a set's reps on the phone, offline. The laptop is untouched. On the
next sync, what travels, and in which direction?

**Q2.** Both devices rename the same session while apart — phone at 10:00, laptop at
10:05 (clocks accurate). After sync, which name wins on both?

**Q3.** You created "Cable Fly" on both devices before their first-ever sync. After
sync, how many Cable Fly exercises exist, and whose uuid survives?

**Q4.** Tuesday's weight was entered manually on the laptop. Later the phone pulls an
Apple Health weight for the same Tuesday with a *newer* timestamp. Which survives?

**Q5.** You delete a routine on the phone, then sync. What is the state of that
routine on the laptop — and on the phone — afterward?

**Q6.** Why doesn't a row you just pulled get pushed right back on the next sync?

**Q7.** After an app update adds the `activity` table to sync, why does your phone do
one slow full pull instead of its usual quick incremental?

**Q8.** Name the tables that merge by *date* instead of uuid, and the one that merges
as a singleton.

### Rulings (no right answer — your call, becomes the spec)

**R1.** Tombstones. Pick a design:
(a) each row gets `deleted_at` and stays forever as a ghost;
(b) a separate small "deletions" table (`table, uuid, deleted_at`) that syncs;
(c) UI-level soft delete ("archived") and true delete only via a maintenance tool.
Your pick + one sentence why: ______

**R2.** Clock skew. Phone clock 5 min fast → its writes unfairly win ties. Live with
it / warn when skew detected / have the server hand out timestamps during sync?

**R3.** Silent conflicts. When LWW discards your other device's edit, today it
vanishes silently. Fine forever, or do you want a "conflicts" log you can review?

**R4.** Natural-key scope: should *routines* also merge by name (currently they
don't — two "Push Day"s would both survive)? y/n

**R5.** Sync cadence: on app open only (today) / also every N minutes while open /
also a manual "sync now" button you can smash. Pick.

**R6.** Disaster button: is a "make this device the source of truth, overwrite the
other" nuclear option worth having? y/n

---

## Session 12 · Learn the machine II: the adaptive calorie engine (~1h)

### Read

The target is an **anchor that steps**, never a formula recomputed from scratch.
Parameters (yours today): anchor 2300 kcal · desired loss 0.5 kg/wk · step 100 kcal ·
tolerance ±0.15 kg · floor 1800 · ceiling ≈ estimated maintenance · adapts at most
once per ISO week (Mondays).

Each week it compares **avg(last completed week) − avg(week before)**:

- Losing **faster** than 0.5+0.15 kg/wk → you're under-eating → target **+100**
- Losing **slower** than 0.5−0.15 (or maintaining/gaining) → target **−100**
- Within the band [−0.65, −0.35] → **hold**

Guards: needs two *consecutive* completed weeks; needs **≥3 weigh-ins** in the last
completed week (one noisy reading must never move the target); result clamps to
floor/ceiling and rounds to the nearest 10. "Not enough data" does NOT consume the
weekly slot — it keeps re-checking; a genuine evaluation locks the week.
Carbs are the flex macro: `(target − 4·protein − 9·fat) / 4`.

### Compute by hand (answers in Appendix A)

Assume: current target **2300**, loss goal 0.5, step 100, tol 0.15, floor 1800,
no ceiling unless stated, this week's slot unused.

**E1.** Prev completed week avg **82.0** (4 weigh-ins) → last completed week avg
**81.2** (5 weigh-ins). New target? Reason?

**E2.** 81.0 (3 entries) → 80.9 (3 entries). New target? Reason?

**E3.** 80.6 (4) → 80.1 (4). New target? Reason?

**E4.** 80.0 (4) → 79.0 (**2 entries**). New target? Is the weekly slot consumed?

**E5.** Current target **1850**; weeks show 80.2 (3) → 80.1 (3). New target?

**E6.** Current target **2350**, ceiling **2400**; weeks show 81.5 (4) → 80.6 (4).
New target?

**E7.** Same data as E1, but the target already adapted this Monday. What happens?

**E8.** With protein 180 g and fat 100 g: how many carb grams at a 2400 target?
And at 1800?

### Tune it (your rulings)

**E9.** After doing the math: is ±100 kcal/week the right step for your body size, or
should it scale (e.g. 50 when close to the band, 150 when far)?

**E10.** The 3-weigh-in guard: with your real weighing habits, how often will the
engine sit on its hands? Would a "2 weigh-ins + wider tolerance" fallback be better,
or is strictness the feature?

**E11.** Design the "why" display: write the exact sentence the Diet screen should
show after each decision. E.g. *"−100: you lost 0.1 kg last week vs the 0.5 goal."*
Write versions for increase / decrease / hold / insufficient data:

**E12.** Diet phases (from H1a): define the exact parameter set for each mode you'll
use — Cut: (loss ___, floor ___) · Maintain: (band ___) · Bulk: (gain ___/wk,
ceiling rule ___). What triggers the switch — you, or a goal-weight arrival?

---

## Session 13 · Learn the machine III: ranks math + calibration (~1h)

### Read

Your rank per muscle comes from: **best-ever estimated 1RM ÷ bodyweight**, scored
against a per-exercise benchmark, averaged across the muscle's exercises, mapped onto
9 tiers (Wood → Bronze → Silver → Gold → Platinum → Diamond → Champion → Titan →
Olympian) × 3 divisions + LP.

e1RM uses **Epley with reps capped at 12**: `e1RM = w × (1 + min(reps,12)/30)`;
a single rep returns the weight itself. Bodyweight uses **real weigh-ins only** —
never interpolated or sample data. Reference point from the code's tests: for squat,
a ratio of 1.0×BW is still Wood; 1.25×BW reaches Bronze III.

### Drills (answers in Appendix A)

**K1.** e1RM of 100 kg × 5?
**K2.** e1RM of 60 kg × 12?
**K3.** e1RM of 60 kg × 15? (Careful.)
**K4.** e1RM of 140 kg × 1?
**K5.** e1RM of 80 kg × 8?
**K6.** At 80 kg bodyweight, what squat e1RM do you need to leave Wood (ratio 1.25)?

**K7.** Why does capping at 12 reps make high-rep sets "worthless" for rank purposes —
and is that correct behavior in your view, or should sets of 15–20 count somehow?

### Calibration worksheet — fill from memory, honestly

| Lift | Best recent set (kg × reps) | e1RM (compute!) | ÷ your BW | Tier that would feel HONEST | Ratio that should mean "Gold" |
|---|---|---|---|---|---|
| Squat | | | | | |
| Bench | | | | | |
| Deadlift | | | | | |
| Overhead press | | | | | |
| Barbell row | | | | | |
| Pull-up (BW+kg) | | | | | |
| Hip thrust | | | | | |
| ___________ | | | | | |
| ___________ | | | | | |

**K8.** Now the decision (refines T5b): keep objective global standards even if they
sting, or bend the curve so *your* current level sits around Silver–Gold with room to
climb? There's no wrong answer, but pick one and write why.

**K9.** Muscles with no barbell benchmark (abs, calves, forearms): rank them by their
isolation lifts, leave them unranked, or rank by training consistency instead of
strength? Pick per muscle if you like.

---

## Session 14 · Curate your exercise library (~1h, paper-friendly)

The generator, ranks, and volume analytics are only as good as the exercise pool and
its tags. Build the canonical list — I'll import it when you're back.

For every exercise you actually perform (aim for completeness — 30 to 50 rows), fill:

| # | Exercise | Primary muscle | Equipment | Compound? | My rep range | Form cue (1 line) | In generator pool? |
|---|---|---|---|---|---|---|---|
| 1 | | | | | | | |
| 2 | | | | | | | |
| 3 | | | | | | | |
| 4 | | | | | | | |
| 5 | | | | | | | |
| … | *(continue on paper — number every row)* | | | | | | |

Primary muscle must be one of: Chest, Back, Shoulders, Biceps, Triceps, Quads,
Hamstrings, Glutes, Calves, Abs. (If you keep wanting to write "Forearms" or
"Adductors" — note it; the body map has those shapes but the volume system doesn't
track them, and that's a decision: **L1.** promote them to full muscle groups? y/n)

**L2.** While listing, mark with ⭐ the ~10 exercises that will carry your progression
engine (the ones worth automating first).

**L3.** Mark with ⚠ any exercise you do despite discomfort/doubt — these seed the
injury-log design (B4).

**L4.** The auto-tagger guesses muscle from the exercise's *name* ("bulgarian split
squat" → Quads). Write 5 of your exercise names it would plausibly get wrong; propose
the fix (rename convention vs. manual tag).

---

## Session 15 · Write your real programs (~45 min)

**M1.** Write out, by hand, the program you *actually want to run* for the next 8
weeks: days, exercises in order, sets × reps, rest. Not aspirational — the one you'll
do.

**M2.** Now run the generator in your head with matching inputs (split, days,
priorities). Where would its output differ from M1? Every difference is a generator
bug or a missing input — list them:

**M3.** Write the *deload week* version of M1 (what actually changes — sets? load? both?).

**M4.** Write the *"I only have 35 minutes"* version of each day (this becomes the
"short on time" mode spec — T4b's time budget made concrete).

---

## Session 16 · Edge-case court (~1h)

You are the judge. For each case: **Verdict** (what SHOULD happen) + **Severity**
(🔥 fix soon / 😐 someday / 🤷 fine as is). Cases marked ⚡ are *real current
behavior* I can confirm from the code — the rest are unknowns to define.

**J1.** ⚡ You finish a set at 00:30 after a late session. Timestamps are stored in
UTC, so past midnight (or in another timezone) the workout can land on the "wrong"
calendar day — affecting streaks and weekly volume. Verdict: which day should a
00:30 workout belong to? (Common answer: the "gym day" runs until ~4am.)

**J2.** ⚡ You weigh in twice in one morning (81.2, then 80.9 after coffee). The
day's row is simply overwritten — last write wins. Verdict: keep-last / keep-first /
keep-lowest / average?

**J3.** ⚡ You delete an embarrassing session on the phone, offline. Next sync it
returns from the laptop (no tombstones). Verdict feeds R1 — but also: severity?

**J4.** You delete an *exercise* that 40 historical sessions reference. What should
happen? (Block deletion? Archive it — hidden from pickers, kept in history? Cascade?)

**J5.** ⚡ A warm-up-only session (you got interrupted) counts as NO workout for the
streak — only completed working sets count. Fair? Or should showing up count?

**J6.** You forgot to log Tuesday's workout and it's Thursday. Sessions can't be
backdated today. Verdict: allow editing `started_at`? Full manual back-entry mode?

**J7.** You fly to another timezone for two weeks. Weigh-ins, streaks, and "today"
all shift. What's the rule — device-local time everywhere, or home timezone?

**J8.** ⚡ The imperial unit setting exists but the app's math and displays are
kg-native. Verdict: finish imperial properly / delete the setting?

**J9.** Two devices edit the same set differently while apart; LWW silently discards
one. (Same as R3, but now decide severity having seen the whole picture.)

**J10.** Apple Health pushes an obviously-wrong day (500 kcal, or a 8.0 kg weight
typo). The engines will happily ingest garbage — the maintenance estimate has a
sanity band, the weight trend does not. Verdict: hard validation bounds per metric?
Flag-and-ask? Trust the source?

**J11.** ⚡ A set of 20 reps computes the same e1RM as 12 reps (cap). A 1 kg × 1 rep
set still marks the day as a workout for streak purposes. Can the streak be gamed,
and do you care? Define "a real workout" in one measurable sentence.

**J12.** Your session stays "in progress" for 3 days because you never tapped Finish.
Auto-close after N hours? Prompt on next open? Leave it?

**J13.** ⚡ The rank system reads your latest REAL weigh-in. If you stop weighing for
a month while getting stronger, ranks inflate against a stale bodyweight. Verdict:
staleness cutoff? Warning? Fine?

**J14.** ⚡ Server and phone compute "longest streak" differently in one corner: the
server persists longest-ever monotonically; the phone recomputes from history under
the *current* rest-gap setting. Change the gap and they can disagree. Verdict: which
is right — monotonic-forever, or recompute-under-current-rules?

**J15.** The service worker updates the app while you're mid-workout. Today nothing
guards against a refresh at a bad moment. Verdict: hold updates while a session is
active? Don't care?

**J16.** You add a second phone. It full-pulls years of data over the gym wifi. Any
rules (wifi-only sync? progress bar? chunking), or is this a non-problem?

**J17.** The coach proposes a workout; you accept; then edit the generated routine
heavily. Next coach conversation, should it know its proposal was rewritten?

**J18.** ⚡ Sample/demo data uses `source: sample` and is excluded from weight math —
but if you ever seeded sample *workouts*, they'd pollute PRs/ranks forever. Verdict:
a "purge all sample data" button? Never seed on a real install?

**J19.** A tracker you've logged 200 times gets archived, then you make a new one
with the same name. Merge histories or keep separate?

**J20.** Invent two edge cases I didn't think of (you know your usage better):
- J20a: ______
- J20b: ______

---

## Session 17 · Voice & microcopy (~45 min)

**N1.** The app's voice in 5 adjectives (e.g. calm, dry, direct, warm, nerdy):
1. … 2. … 3. … 4. … 5. …

**N2.** Banned words/styles (e.g. "crush it", "beast mode", exclamation marks,
motivational-poster tone): ______

**N3.** Emoji policy: the app currently uses 🔥 (streak), 🏆 (ranks button), ⚠️
(at-risk), 🗑 (delete). Keep / reduce / replace with icons? ______

**N4.** Rewrite these real strings in your voice (or bless them as-is):
- a) "No workouts logged yet. Start one from the Workout tab." → ______
- b) "Nothing logged today. Log manually ›" → ______
- c) "No trackers yet — add habits, scales or metrics in Settings." → ______
- d) "Select a muscle to see its rank." → ______
- e) Delete confirm: "Delete "X"? Its logged sets are removed for good and PRs/ranks
  will recompute without them." → ______
- f) "Gathering data — the target adapts each Monday once there are two consecutive
  weeks with at least 3 weigh-ins." → ______
- g) Rest notification: "Rest complete — time to start your next set." → ______

**N5.** Write the rank-up moment. The exact line (and any ceremony) for:
- Bronze → Silver: ______
- First ever Diamond: ______
- A *demotion* (if decay exists): ______

**N6.** Write the streak-at-risk evening notification — motivating without being
guilt-trippy (or decide it shouldn't exist):

**N7.** Write the empty Ranks page for a brand-new user (what it promises):

**N8.** Dashboard greeting says "Good evening — Here's where things stand." Keep the
time-of-day greeting or replace with something with actual information? Draft one:

---

## Session 18 · The coach's brain (~1h)

**O1.** Write the coach's persona brief in your own words, ~10 lines. Cover: tone;
how blunt when you're slacking; how it handles "should I train through this pain?"
(hint: it must not play doctor — where's the line?); when it should refuse to answer.

**O2.** Its opening move. When you open the coach on a random Tuesday, what should
the FIRST message be — silent waiting, a one-line status, or an observation with a
question? Draft it using fake-but-plausible data:

**O3.** The eval suite (expand H9a to 15). For each, one line on what a GREAT answer
includes. These become the test cases we grade the coach against:
1–5: (from H9a) …
6. "Plan my training around a Saturday football match" — great answer includes: ___
7. "I'm traveling for 10 days with hotel gyms" — ___
8. "Why did my calorie target go down?" — ___ (must cite the actual weekly numbers)
9. "What's my weakest muscle group and what would fix it?" — ___
10. "Build me a deload week from my current routine" — ___
11. "I slept 5h, should I still do legs?" — ___
12. "How's my protein been, honestly?" — ___
13. "I want to be Gold in bench by December — realistic?" — ___ (must do the math)
14. "My knee clicks on squats" — ___ (the careful one)
15. Your own: ______

**O4.** What data may the coach see? (It currently gets training/health/nutrition/
trackers/plan.) Anything you'd *exclude* — journal-type trackers? mood? Draw the line:

**O5.** Proactivity contract (finalizes H9b): complete the rule —
*"The coach may start a conversation only when ______, at most ___ times per week."*

**O6.** The offline mini-coach (from C1): pick the 3 rule-based checks worth building
first (e.g. stall detection: "e1RM flat 3 sessions", volume drift, weigh-in gaps,
streak risk, protein 3-day average). Write each as an if-then sentence:
1. If ______ then show ______
2. If ______ then show ______
3. If ______ then show ______

---

## Session 19 · 100 ideas (~1h, paper recommended)

Number 1–100 on paper. Fill every slot — the last 30 are where the interesting ones
live, after the obvious ones run out. Ten per theme:

- **1–10** the workout screen (speed, input, mid-session intelligence)
- **11–20** ranks & gamification
- **21–30** diet & body
- **31–40** the coach & AI
- **41–50** insights, stats, history
- **51–60** phone/hardware tricks (watch? widgets? NFC tag on the power rack? voice logging?)
- **61–70** recovery: sleep, mobility, rest days, deloads
- **71–80** your sports: football, judo, padel
- **81–90** data: export, backup, interop, longevity (even ideas that violate the
  anti-vision — explore, then reject consciously)
- **91–100** wildcards, jokes, "stupid" ideas (write them anyway)

Then: ⭐ the top 10 → they join the Session 9 matrix as rows 24+.
✗ ten explicit rejects → they join the NEVER list. Rejecting is as valuable as picking.

---

## Session 20 · Predictions game (~30 min)

Guess without checking. When you land, I'll compute the real numbers from your data —
every miss of >20% is a stat the app should probably surface better.

| # | Stat | Your guess | Actual (post-flight) |
|---|---|---|---|
| 1 | Total sessions ever logged | | |
| 2 | Total volume ever lifted (tonnes) | | |
| 3 | Current squat e1RM | | |
| 4 | Current bench e1RM | | |
| 5 | Current deadlift e1RM | | |
| 6 | Avg sessions/week, last 3 months | | |
| 7 | Avg session duration | | |
| 8 | Longest streak ever | | |
| 9 | Most-trained muscle (weekly sets) | | |
| 10 | Least-trained muscle | | |
| 11 | Most-performed exercise (by sets) | | |
| 12 | PRs hit in the last 90 days | | |
| 13 | Bodyweight 90 days ago | | |
| 14 | Weekly rate of change, last month (kg/wk) | | |
| 15 | Avg daily protein, last 30 days | | |
| 16 | Avg daily calories, last 30 days | | |
| 17 | Avg sleep, last 30 days | | |
| 18 | Avg steps, last 30 days | | |
| 19 | Sport sessions logged, last 60 days | | |
| 20 | % of days with a weigh-in, last 30 | | |

**Y1.** Before landing: circle the 5 stats above you most *want* to always know.
That's the spec for the 10-second screen (W1).

---

## Session 21 · A year in the life (~45 min)

Simulate the next 12 months. For each month: life context (exams, holidays, seasons
of your sports), training phase, and the ONE thing the app must do well that month.
This surfaces features no static brainstorm finds (vacation mode, illness handling,
phase transitions).

| Month | Life context | Training/diet phase | The app must… |
|---|---|---|---|
| Aug | | | |
| Sep | | | |
| Oct | | | |
| Nov | | | |
| Dec (holidays!) | | | |
| Jan | | | |
| Feb | | | |
| Mar | | | |
| Apr | | | |
| May | | | |
| Jun | | | |
| Jul | | | |

**S1.** Reading the table back: which recurring situation does the app handle *worst*
today? ______

**S2.** Design "away mode" (travel/illness/exam week): what pauses (streak? adaptive
target?), what continues, and how do you enter/exit it?

---

## Session 22 · The subtraction pass (~30 min)

Growth by deletion. Every screen/feature costs attention even when unused.

**Z1.** List every nav destination from memory (don't peek). The ones you forget are
candidates: ______

**Z2.** For each, answer only: *"Would I notice within a month if it vanished?"*
Dashboard ___ · Workout ___ · Coach ___ · Routines ___ · History ___ · Diet ___ ·
Insights ___ · Report ___ · Ranks ___ · Generator ___ · Exercises ___ · Manual log ___ ·
Plan/Calendar ___ · Trackers/Check-in ___ · Settings ___

**Z3.** Pick at least ONE thing to actually remove or fold into another screen.
(If everything survives, the exercise failed — be harsher.)

**Z4.** Settings audit: which settings should stop being settings (just pick a good
default and delete the knob)? ______

**Z5.** The phone bottom bar holds five slots: Home, Workout, Coach, History,
Settings. Given everything you've decided today — are those still the right five? ______

---
---

# PART III — After you land

Bring this workbook back and work through these WITH me (order matters):

**PL1. "Process my workbook."** I read every answer, build the scored roadmap from
Session 9 + 19, and turn your NOW list into concrete implementation plans.

**PL2. Predictions reveal (Session 20).** I compute the 20 real numbers; we design
the 10-second screen from your circled five + the biggest surprises.

**PL3. Library import (Session 14).** Read me the table; I create/rename/tag all
exercises, fix mistagged muscle groups, and set the generator pool + your ⭐
progression lifts.

**PL4. Benchmark calibration (Session 13).** We apply your K8 philosophy: adjust
rank_config so the tiers match your honesty table, and verify the body map repaints.

**PL5. Coach transplant (Sessions 18 + W2).** Your persona brief, proactivity
contract, and training-history essay get wired into the coach's context; then we run
the 15-prompt eval suite live and grade it together.

**PL6. Edge-case fixes (Session 16).** Every 🔥 verdict becomes a filed fix with a
test. (My guesses for your top three: J1 midnight boundary, J3 tombstones, J10 data
validation — let's see if you agree.)

**PL7. The W6 lecture.** You listed what you want explained; I answer each with
code walkthroughs until the machine has no dark corners for you.

**PL8. Naming ceremony (V6).** If a name won, we rebrand: manifest, icons, wordmark.

**Standing rituals to consider adopting:**
- Sunday 20 min: read the weekly report → adjust next week (this is C2's ritual).
- Monthly: re-open this workbook, re-grade Sessions 2–3 — grades that change are
  the real product feedback.
- Quarterly: redo the Session 20 predictions — calibrated self-knowledge is the
  actual quantified-self win.

---
---

# Appendix A — Answer key (no peeking until you've committed answers)

### Session 11 quiz

**Q1.** Only the phone's edited set row travels, phone → laptop (it was marked dirty).
The pull brings nothing new back.
**Q2.** The laptop's 10:05 name wins everywhere — pure last-write-wins on `updated_at`.
**Q3.** One exercise survives. The natural-key fallback matches on the name; the
*receiving* device keeps its own uuid and the incoming version's children (sets,
routine slots) are remapped onto it.
**Q4.** The manual Tuesday entry survives. Health source precedence beats
last-write-wins: manual is never buried by a synced source, even a newer one.
**Q5.** The laptop still has the routine (deletes don't travel). Worse: the phone's
next pull re-inserts it locally. It "resurrects." (This is the tombstone gap, R1.)
**Q6.** Applied rows keep their original `updated_at` (not re-stamped on arrival) and
are stored clean, not dirty — so nothing about them looks locally edited.
**Q7.** The sync-scope version bumped; the phone's incremental cursor predates the
new table, so one full pull (since = beginning) backfills it. After that,
incrementals resume.
**Q8.** By date: weight_log, steps_log, sleep_log, nutrition_day. Singleton: settings
(always row 1).

### Session 12 scenarios

Band for loss 0.5 ± 0.15 → acceptable weekly change is **−0.65 to −0.35 kg**.

**E1.** Change = 81.2 − 82.0 = **−0.8** → faster than −0.65 → losing too fast →
**increase** → **2400**.
**E2.** Change = **−0.1** → slower than −0.35 → **decrease** → **2200**.
**E3.** Change = **−0.5** → inside the band → **hold** → **2300**.
**E4.** Only 2 weigh-ins in the completed week → **insufficient data** → target stays
2300 and the weekly slot is **NOT consumed** (it will re-evaluate as data arrives).
**E5.** Change −0.1 → decrease → 1850 − 100 = 1750 → **floor clamps to 1800**.
**E6.** Change = 80.6 − 81.5 = −0.9 → increase → 2350 + 100 = 2450 → **ceiling clamps
to 2400**.
**E7.** Nothing. Already adapted this ISO week → **not due**; next evaluation next
Monday.
**E8.** Carbs = (kcal − 180×4 − 100×9)/4 = (kcal − 1620)/4.
At 2400 → 780/4 = **195 g**. At 1800 → 180/4 = **45 g**. (Yes, the floor is keto-ish —
worth knowing before you hit it.)

### Session 13 drills

**K1.** 100 × (1 + 5/30) = **116.7 kg**
**K2.** 60 × (1 + 12/30) = **84 kg**
**K3.** Still **84 kg** — reps cap at 12; the extra 3 reps add nothing.
**K4.** **140 kg** (single reps return the weight unchanged).
**K5.** 80 × (1 + 8/30) = **101.3 kg**
**K6.** 1.25 × 80 = **100 kg** squat e1RM to reach Bronze III.
**K7.** Because beyond 12 reps the formula stops rewarding reps entirely — a 20-rep
set scores like a 12-rep set. It's a deliberate guard (rep-formulas get unreliable at
high reps), but it means endurance work is invisible to ranks. Whether that's right
is your K7 ruling — there's a defensible case for a separate "muscular endurance"
signal instead of bending e1RM.

---

*That's the workbook. If you somehow finish everything: sleep — you've earned it, and
jet lag is a training variable too. When you land: "process my workbook." 🛫*

# ✈️ Flight Workbook — 15+ hours of product thinking

A self-contained working document for the fitness app. No internet needed — everything
you need to know about the current state is summarized inside. Answer inline (edit this
file, or scribble on paper against the question numbers). Every question has an ID like
**V3** or **R2** so your answers can be referenced later and turned directly into a
roadmap + implementation plans.

**Structure:**
- **Part I (Sessions 0–10, ~6h)** — vision, feature audits, design exercises, the priority matrix.
- **Part II (Sessions 11–22, ~8h)** — deep work: learn how the machine actually works
  (with hand-computable exercises + answer key), curate real data, rule on edge cases,
  write the app's voice and the coach's brain.
- **Part III (~2h + ongoing)** — what we do together after you land.
- **Appendix A** — answer key for the computational sessions. No peeking.

**Suggested flight plan** (sessions are modular — reorder freely):

| Flight hour | Do | Why this order |
|---|---|---|
| 1 | S0 + S1 (vision) | Fresh brain for the big questions |
| 2 | S2 (training audit) | |
| 3 | S3 (health audit) | |
| 4 | S12 (calorie math) | Switch to puzzles before fatigue |
| 5 | S4 (progression design) + break | The most valuable design session |
| 6 | S13 (ranks math) + S14 start (library) | Half thinking, half data entry |
| 7 | S14 finish + S16 (edge-case court) | Court is fun when tired |
| 8 | S11 (sync quiz) + S17 (microcopy) | |
| 9 | S18 (coach) + S19 (100 ideas) | Creative sessions late |
| 10 | S9 (priority matrix ⭐) + S10 leftovers | Decide with everything fresh in mind |

Sessions 5–8, 15, 20–22 are the flex material — do them instead of a movie, or after landing.

---
---

# PART I — Vision, audit, design

## Session 0 · The app as it stands (15 min read — no questions)

Read this first so every later question starts from the same picture.

**Architecture.** FastAPI + SQLite backend on the laptop; React PWA on the phone.
The phone is **local-first**: it has its own full copy of the data in IndexedDB and an
on-device twin of the entire API, so everything works with no server reachable. When
the phone can see the laptop, it syncs: push dirty rows, pull changes, last-write-wins
by timestamp. The Coach (Claude) and Apple Health ingest are the only things that
require the network.

**What exists today (after the July restore):**

| Domain | What it does |
|---|---|
| **Workout** | Live session logging: sets/reps/RPE, warm-ups, rest timer (pause, add-time, configurable default), previous-set prefill, PR detection, tap-to-rename, discard |
| **Routines** | Templates with target sets/reps/rest per exercise; "generated" vs hand-made |
| **Generator** | Builds a program from split (full-body / UL / PPL / bro) + days/week + priority muscles, respecting weekly volume targets |
| **Ranks** | 9 tiers × 3 divisions + LP per muscle group, from best 1RM ÷ bodyweight vs benchmarks; hand-drawn body map |
| **History** | Session list + detail, delete session |
| **Diet** | Adaptive calorie target (anchor 2300, ±100 kcal/week from the weekly weight trend, floor 1800, ceiling ≈ maintenance), macro targets (protein/fat fixed, carbs flex), micronutrient RDA analysis, activity log (football/judo/padel, METs burn estimate) |
| **Streak** | Current/longest workout streak; survives `rest_gap` rest days (default 1); at-risk flag; on the dashboard |
| **Notes** | One-shot "next session" notes per routine (surface once, auto-archive) + persistent per-exercise cues |
| **Report** | Weekly/biweekly: new PRs, streak, bodyweight trend, diet adherence, sleep, volume flags, next-week plan; markdown export; optional AI narrative |
| **Insights** | Week-vs-week deltas, correlations (Pearson over 90 days), training-day splits, sets-per-week per muscle vs targets |
| **Trackers** | Track anything: habit / 1–5 scale / number / free text; daily check-in |
| **Coach** | Claude-powered chat + structured planners over your data; proposes plan items / workouts, you approve |
| **Plan** | Time-blocked daily plan items (workout/study/task/meal), checkable |
| **Health data** | Apple Health: weight, steps, sleep, nutrition + micros. Manual entries always win |
| **Sync** | Device-to-device, last-write-wins. **Known gap: no tombstones — deletes can resurface** |
| **Onboarding** | First-run wizard: sex, age, bodyweight, calorie/protein targets, loss rate |

**Known honest problems** (each shows up as a question later):
1. Sync deletes don't propagate (no tombstones).
2. Coach is online-only — dead in the gym if the laptop is off.
3. Rank benchmarks are generic defaults, not calibrated to you.
4. The app is literally named "tracker." — a placeholder.
5. Volume targets are textbook defaults (e.g. Chest 10–20), not yours.
6. No progression logic — the app records but never suggests weights.
7. No body measurements, progress photos, or injury tracking.
8. Clock skew between devices can make last-write-wins unfair.

---

## Session 1 · Vision & identity (~1h)

The point of this hour: define what this app is FOR, so every later trade-off has a
tiebreaker. Write real sentences, not bullet fragments.

**V1.** Finish this sentence three different ways, then circle the truest one:
*"Six months from now, this app has succeeded if ________."*
- a) I use it every day
- b) My friends are able to use the app
- c) I dont require any other apps like sheets, macrofactor or strong

**V2.** What does the app replace in your life? (A notebook? A commercial app you
quit? A coach you'd otherwise pay? Nothing — it's new behavior?) Why did the thing
it replaced fail you?

The app should replace my weekly check in to adapt my calories/macros which I used to do manually with google sheets. 
It should replace apps like strong and it should require me to use apple health to visualize my data. 

**V3.** Rank these identities 1–6. The #1 becomes the design tiebreaker forever:
- [3] A **gym logger** that must be fastest-in-class between sets
- [1] A **body recomposition instrument** (weight/diet/energy loop is the core)
- [6] A **game** that makes consistency addictive (ranks, streaks, points)
- [2] A **quantified-self lab** (correlations, trackers, everything measured)
- [4] An **AI coach** that increasingly decides FOR you
- [5] A **life dashboard** where fitness is just the first module

**V4.** The anti-vision. Write 3 things this app must NEVER become (e.g. "social",
"a chore that takes >30s between sets", "a subscription clone"). These are guardrails
against feature creep — yours, and mine when I build.

I dont want this app to become something complicated to use or an average app that already exists. I want this to be complete with various features meant for people who are serious about fitness.
This doesnt mean that the app should be exlclusive to those people, meaning that everyone should be able to use it. 

**V5.** You built this single-user, for you. Is that permanent? Pick one and defend it
in two sentences:

Currently this app is just for me to use as I am not allowed to develop apps and sell them due to my student visa. In the future I would like this to become a product but it will still take 2 years until then. 


**V6.** Name the app. The wordmark literally says "tracker." today. Brainstorm 10 names,
even bad ones — bad names teach you what the good name must feel like. Circle two.

I currently really like the name tracker. In the future, if I want to change it, I will come back to this. 

**V7.** In one paragraph: describe the *perfect gym session* using this app, from
walking in to walking out. Every touch of the phone, in order. (This becomes the spec
for the workout screen's next iteration.)

Even before going into the gym, I know if I slept well, if I had enough food the previous day, and how I have been doing in the workouts during the week.
I will then pick a day, for example upper, based on the current split that I am doing, which in this case would be upper/lower.
The app will show me all the exercises that I have to do for the day and show me goal weights and reps for every single set. 
It tells me that if I hit a specific goal I will rank up in a certain muscle group going from gold 2 to gold 3 for example.
After finishing the entire workout I give a strain rating from 1-10 and it gives me a summary of the workout. This means all my PRs, if I ranked up on anything and a grade for the session.

**V8.** Same, but the *perfect Sunday morning review* at the laptop: what do you look
at, in what order, and what decision does each screen help you make?

I will get an email, or open a tab on my app which says weekly review. Similarly to the things that appear when I finish my workout, it should start with a summary. 
This means all my most relevant PRs, the amount of PRs, how many gym sessions I had, how my sleep, step and nutrition were. Based on all of those things it will also give a grade for the week.
Now is the very important part. It should give me a detailed feedback. If anything was out of the norm like my weight dropped too fast, I had too many calories, I didnt have any PRs, it should tell me how to adapt.
This should be split into categories like sleep, steps, nutrition, gym, weight. Every category will then say if it needs adjustment and how to adjust it.
This means new calories for the week if my weight was changing too fast or too slow. Increase carbs or calories if sleep or gym performance has been down. Increase steps if weight loss it too low. 
It should be extremly objective with the goals. 

## Session 2 · Feature audit — training half (~1h)

For each feature: grade it **A** (love it, don't touch), **B** (right idea, needs work),
**C** (wrong shape, redesign), **D** (kill it). Then answer the specifics.

**T1.** Workout logging: grade B
- T1a. What's the slowest/most annoying moment mid-workout today? 
The tracking still feels like AI slop. I dont know how to fix it yet, it is in the right direction but I feel like it is aesthetically dull. 

- T1b. Number pads, plus/minus steppers, or "same as last time" one-tap — what's the
  ideal weight/reps input? Sketch it (describe in words). It should be a number pad
  
- T1c. Do you ever log supersets / circuits / drop sets? Does the data model need them,
  or is that over-engineering for how you actually train?
  I dont ever do supersets, circuit sets or drop sets. 
  
- T1d. RPE: do you actually use it? Keep / hide / remove?
I do actually use it to understand how difficult my previous set was. For example, if I got 7 reps on the set last time with aa 3 RPE, I know that I should definently get 8 or more reps this session.
If the RPE was 10, I know that I shouldnt be too bothered it I dont get over 7 reps as the last time was very difficult to get the 7 reps. 

**T2.** Rest timer: grade B
- T2a. Now that pause + add-time is back — what's still missing? (Auto-start on set
  completion? Per-exercise memory of your real rest habits? Vibration patterns?)
  It is missing auto start when finishing a set and having per exercise memory.It should also have a sound and vibration when the timer goes off. 

**T3.** Routines: grade C
- T3a. How many routines do you realistically maintain? 
I typically have push pull legs and upper lower, both of them sometimes inlcuding an arm day.There shouldnt be a limit to how many routines there are, but every routine that exists should be detailed and specific.
This means that upper lower should clearly show what muscles need to be worked out each day, how many sets per week per muscle group, how many sets per day, what exercises. 

- T3b. Should a routine *evolve* (the app updates targets from what you actually did)
  or stay a fixed template you edit by hand? This is a big philosophical fork.
  It should have the option to evolve but should do it automatically unless the users allows it

**T4.** Generator: grade C
- T4a. Did you ever *keep* a generated program, or is it a curiosity? What would make
  the output trustworthy enough to actually run for 8 weeks?
  I have currently not used the auto generated program. The way I want it to work is differnet though. It should analyze what current split I am doing and give me options.
  If I am doing Upper Lower Arms, those should be the three options. It should know how often I do each day during the week as well. Based on that it should create the workout.
  So for example if I need to have 8 sets for quads per week and I have two lower day per week, it should have 4 sets for quads for each lower day. 
  It should also try to develop each area of the muscle group by using different exercises. 
  For example, for the chest, it should ensure I do incline dumbell press for the upper chest and also a flat becnh press for lower chest. 
  For hamstrings, ensuring I do a leg curl and also a hinge movement. 
  
- T4b. Missing inputs: equipment available? session time budget? exercises you hate?
  Rank these three.
When generating this workout, I should be able to change any exercises that arent availabe in my gym or exercises that I dont like. 
There shouldnt be a time budget but rather a set budget. If I am short on time and can only do half the sets during that day, it should cut down all exerise sets in half. 

**T5.** Ranks: grade B
- T5a. Look at your current ranks honestly: do the tiers *feel* right? Which muscle's
  rank feels most wrong, and in which direction?
  My calves seem too high ranked but I am unsure how to decide the ranks. 
  
- T5b. Benchmarks are generic (strength standards scaled by bodyweight). Would you
  rather calibrate them: (a) manually per lift, (b) automatically from your own history
  percentiles, (c) leave global standards so the rank means something objective?
  I want it to be based on global ranks
  
- T5c. What should rank progress FEEL like? (LoL-style LP grind? Belt system — slow,
  ceremonial? Season resets?) Describe the emotion of ranking up.
  It should feel like a Lol-style LP grind but be harder as you get stronger. This means that the first ranks are easy to reach but to become the highest rank is almost impossible unless you are a powerlifter. 
  
- T5d. Should ranks *decay* if a muscle goes untrained for weeks? Yes/no, and how fast?
It should not decay.

**T6.** Streak: grade A
- T6a. Is a workout-only streak right, or should any "active day" (football, judo,
  padel, 10k steps) keep it alive? Define exactly what keeps YOUR streak alive.
  Any active day should be alive
  
- T6b. StreakState was built with a future points/gamification hook. Do you want XP &
  levels on top of ranks, or is that two currencies too many? (See Session 6.)
I would like to have XP as well on top of the ranks. 

**T7.** History & PRs: grade C
- T7a. When you open History, what are you actually looking for? Does the current
  list-of-sessions answer it, or do you want per-exercise timelines front and center?
I am looking for the all the data of the previous session, the pattern for all the data development for an exercise and my PR for that exercise. 

**T8.** Next-session notes & exercise cues: grade C
- T8a. Real example: write the last 3 notes you'd have left yourself. Do they fit the
  one-shot model, or do some want to persist / repeat?
Be attentive on deadlift form as there was minor back pain on the last rep
Keep shoulders down for chest press.
Make sure eccentric is controlled. 


---

## Session 3 · Feature audit — health half (~1h)

**H1.** Diet / adaptive calories: grade B
- H1a. Is 0.5 kg/week still the right goal? What's the plan *after* the cut — does the
  app need a maintenance mode? A lean-bulk mode? Define the modes you'll actually use
  and what switches between them.
  It should work with a slider. On the far left it should be cutting -0.5, the middle should be maintenance 0 and the far right should be bulking 0.5.
  I should be able to slide it anywhere with a 2 decimal place and the max should be -0.5 until 0.5
  
- H1b. The target only moves ±100 kcal once a week, needs 3 weigh-ins in the completed
  week. Too cautious? Too twitchy? Right?
  Yes
  
- H1c. Do you trust the number enough to eat by it? If not, what would earn trust —
  showing its reasoning? A confidence range instead of one number?
  I would trust the number if it works.For example, we could have a trial week where I eat at a certain amount of calories and see how much weight I gaiin or lose.
  Based on that the calories should adapt until it becomes nearly pefrefect. 
  
- H1d. Protein 180g / fat 100g are fixed by hand. Should protein auto-scale to
  bodyweight (e.g. 2.0 g/kg)? Pick a rule or keep manual.
  I think there should be a suggestion of how much to eat but you should be able to change anything manually. 

**H2.** Micronutrients: grade B
- H2a. Have you ever *acted* on the micro breakdown (changed a food, bought a
  supplement)? If not, should it demote to a monthly report instead of a daily view?
  This one is almost perfect. When it came to my fixed diet, I did use it to analyze how I was doing. 
  The issue is when I eat something out of my diet as the apple health sync is still not the best. 

**H3.** Activities (football/judo/padel): grade A
- H3a. What do you actually want from logging these? (Just context on the calendar?
  Load management — "don't lift legs the day after football"? Fun stats per sport?)
 This is perfect. All I want is to know how many calories I burned to help with the calorie calculation for the week. 
 
**H4.** Apple Health ingest: grade D
- H4a. What breaks or annoys you about the current push/backfill flow? How often does
  data arrive late or wrong, and what do you do about it?
  It annoys me that the data takes a while to track, I need to do it manually, it doesnt always save and sometimes it is wrong.
  I have no idea how to fix it and it is the most important part of the app. 
  
**H5.** Trackers & daily check-in: grade A
- H5a. List every tracker you'd *actually* fill in daily for a month: I currently dont need the tracker. It can just be a normal to do list tracker
- H5b. Anything you've stopped filling in? Kill or fix?
You can kill for now. 

**H6.** Insights & correlations: grade A
- H6a. Name one correlation the app showed you that you believed. If none: is the
  problem statistics (n too small), presentation, or the idea itself?
  It is a fun featuer but the correlations are always too small. This is probably due to the lack of data and wrong input though. I wouldnt touch it just yet. 
  
**H7.** Report: grade C
- H7a. Weekly or biweekly — which will you actually read? Where should it arrive
  (in-app / a notification / the Coach opens with it)?
  I would doo it weekly. It can be an in app thing where every week it showy you something new. 

**H8.** Plan items & calendar: grade D
- H8a. Did the day-plan (time-blocked items, coach-proposed) survive contact with real
  life? Grade honestly — this is the feature most at risk of being a D.
  It is too complicated and I dont need the feature.
  
**H9.** Coach: grade D
- H9a. Write 5 real prompts you WISH you could ask the coach and get a great answer.
  (These become its test suite — expanded to 15 in Session 18.)
  1. …  2. …  3. …  4. …  5. …
- H9b. Should the coach be *proactive* (opens with an observation: "bench stalled 3
  weeks, sleep down 40min — deload?") or purely reactive? How proactive is creepy?

We can kill the coach for now. 

## Session 4 · Design exercise: progression engine (~1h)

The biggest missing piece: the app records everything and suggests nothing. Design the
thing that tells you what to lift today.

**P1.** When YOU decide "add 2.5 kg," what's the actual rule in your head? Write your
current mental algorithm as honestly as you can — even if it's "vibes."
For me, if I was able to perform 11 or 12 reps, even at 0 RIR I would go up in weight for the next session.
If I am able to do 9 or 10 reps with 1 RIR on a bulk I would also go up in weight. 
If I do less than 5 reps or 5 reps with 0 RIR I would go down in weight. 

**P2.** Pick a base scheme per lift type (or invent your own):
- Compounds: [ ] linear (+2.5kg each session until fail) [ ] double progression
  (reps 6→10, then +weight, reset reps) [ ] percentage blocks [ ] RPE-driven
- Isolation: [ ] double progression [ ] rep-range drift [ ] don't automate isolation

The goal is just to get an extra rep on every session and the weight depens. If it is dumbell it goes to the next dumbell, if it is machine, the next pin and for barbell or plate loaded increase by 5 kg. 

**P3.** Failure handling: you missed the target on bench two sessions running.
What should the app do? (Repeat weight? Deload 10%? Suggest swapping the exercise?
Just flag it and let you decide?) Write the exact rule.

This one is a tricky one. If I plateu it should not do anything. If I am constantly losing stregnth I need to analyze my calories as I am probably losing muscle. 
This would mean a deload until I am back to normal.

**P4.** Where does the suggestion appear? Sketch (in words) the set row in the workout
screen when a suggestion exists: what does it show, and what's the ONE tap to accept?
It should be a sketch where I can accept or reject. 

**P5.** Deloads: should the app *detect* accumulating fatigue (volume up, e1RM down,
sleep down) and propose a deload week, or is a fixed every-6th-week rule better?
It should recommend a deload week but only if everything is going terrible. 

**P6.** How does progression interact with the generator and routines? (Does accepting
suggestions slowly rewrite the routine's targets? Does the generator become
"generate program + progression scheme"?)

Yes

**P7.** Trust ladder — order these stages, and mark where you'd STOP:
[ ] app shows last time's numbers (today) → [ ] app suggests, I confirm each set →
[ ] app pre-fills, I override rarely → [ ] app periodizes whole blocks → [NO need for this step] coach
adjusts program weekly without asking

---

## Session 5 · Design exercise: the body (~45 min)

Ranks track strength. Nothing tracks the body itself.

**B1.** Body measurements (waist, arms, chest, thighs…): which would you actually tape,
and how often? If the answer is "none, weight is enough," say so and skip B2.

This can be an extra feature but not for ranks. There should just be a section for measurments where I measure things weekly and it shows my progress. 

**B2.** Design the measurement UX in 3 sentences: where does it live, what does it
show over time, does it feed the body map's visuals?

We can add another section on genral called measurments. It should show a graph, hopefully with growth over time. It shouldnt feed the body maps visuals. 

**B3.** Progress photos: yes/no? If yes — how private is private enough (stored only
on-device? synced between your devices? never leaves the phone?), and what would the
comparison UI look like?

No need for photos yet. This could be something I come back to in a few years. 

**B4.** Injuries & pain: you play contact sports. Design a minimal injury log: what's
the smallest useful record (body part + severity + date?), and what should the app DO
with it (warn on exercises hitting that muscle? auto-adjust the generator? just history?)

Currently I still dont know how this would work so we dont need an injury section. 

**B5.** Should bodyweight goals live in the app explicitly ("goal: 78.0 kg by Oct 1")
with a projection line, or does an explicit goal date create bad pressure? Decide.

I would like to have a projection line but it should be able to adapt and change based on life events so that if anything happens like my disease, I dont feel down. 

## Session 6 · Design exercise: gamification (~45 min)

You have ranks (skill) and streaks (consistency). Decide how far the game goes.

**G1.** What actually motivates you on a day you don't want to train? Be honest —
this determines whether gamification is worth building at all.

I always like to keep my streak alive and rank up. The true motivation obviously doesnt come from that but it is something that helps me a little when I dont want to train. 

**G2.** If points existed, what earns them? Assign values or ✗:
- Completed workout: 10 | PR: 1 | Streak day: 1 | Protein target hit: 5
- All check-ins done: 10 | Weekly volume targets all green: 20 | Sport session: 5

**G3.** What do points BUY? (Levels? Nothing — the number is the point? Unlock
cosmetics for the body map? A monthly "season report"?) If nothing good, kill G2.

I was thinking that for now points should just be XP where you can level up the more points you collect. 

**G4.** Seasons: quarterly reset with a season recap (like a personal Spotify Wrapped)?
Or is your history sacred and resets feel like theft? Pick one.

We can do this spotify wrapped thing in a few years, but currenty it isnt nescessary. 

**G5.** Achievements/badges — name 5 you'd actually feel something for earning
("100 sessions", "1000 kg squat volume in a week", "first Diamond muscle"…):
100 gym sessions
365 day. streak
first rank (bronze,silve,gold) for any muscle
100 8+hours of sleep days

50 day, 10k step days

**G6.** Anti-gamification check (re-read V4): which mechanic above risks making you
train *worse* (ego lifting for LP, junk volume for points)? Design one guardrail.

The only one would be the ranks, but I am doing a lot better with egolifiting where I dont chase increase in weight but rather let it be a byproduct.This means that my form is always standardized and I just try to be a little bit better every time. 


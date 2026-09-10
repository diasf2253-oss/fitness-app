# Dev Handbook — how we build this app

This is your plain-English guide to building this app like a real software team,
even though you're still learning. Read it once end-to-end; come back to the
glossary whenever a word trips you up. Nothing here assumes you already know how
software works.

---

## 1. The daily ritual: Plan → Build → Verify → Ship

Every real software team, from two people to two thousand, runs some version of
this loop. Ours has four steps. Doing them *in order* is what makes a session feel
purposeful instead of random.

### 1. Plan — decide *what* and *why* before touching code
Run `/plan-feature <your idea in your own words>`. You get back a short spec:
**What & why · How · Definition of done · When it merges.** No code is written yet.

This is the highest-leverage habit you can build. Ten minutes of planning saves an
hour of building the wrong thing — and building the wrong thing is the single
biggest waste of tokens *and* time. You can also press **Shift+Tab** to enter
**Plan mode**, where Claude researches and proposes a plan and waits for your OK
before changing anything.

> Real-world name: this is a **product spec** or a **ticket**. Teams write the
> ticket first so everyone agrees on the goal.

### 2. Build — write the code
Either let the main session build it (cheapest, and it teaches as it goes), or hand
a well-scoped task to the **builder** agent. Small, coherent steps. The Definition
of Done from step 1 is your target.

> Real-world name: this is **implementation** — the actual engineering work.

### 3. Verify — prove it works
Run the tests (the **safety net**) and, for anything visual, look at it in the
browser preview. "It looks done" and "it *is* done" are different claims; verifying
is how you tell them apart.

> Real-world name: **QA** (quality assurance) and **testing**.

### 4. Ship — get it to the live app
Run `/ship`. It runs tests, runs a code review, summarizes exactly what changed,
and — only with your explicit yes — opens a **Pull Request** to merge into `main`.
When `main` updates, production deploys.

> Real-world name: **shipping** or **releasing**. The Pull Request is the gate the
> change passes through before it's live.

**You are always in control.** Nothing merges or deploys without you saying yes.

---

## 2. Your team (and their real job titles)

You have a small, deliberately lean team. Two are custom teammates you call in; two
are built into Claude Code; and the most important one is the main session itself.

| Who | Real startup title | What they do | When to use |
|---|---|---|---|
| **Main session (you + Claude)** | Lead engineer + mentor | Plans, builds, and *teaches* — all in one place | Almost always. This is home base. |
| **`builder` agent** | Software engineer | Focused implementation across backend + frontend | A well-scoped build task you want done in its own clean workspace |
| **`reviewer` agent** | Code reviewer / QA | Independent second look for bugs & security | After a build, before you `/ship` |
| **Explore agent** | Researcher | Searches the codebase and reports back | "Where does X live?" across many files |
| **Plan agent** | Architect / tech lead | Designs the approach for a bigger task | Planning something with real complexity |

### The most important cost lesson
Every agent you spin up (builder, reviewer, Explore, Plan) **starts with an empty
memory** — it doesn't know what you and the main session just discussed. It has to
re-read files to catch up, and that costs tokens. So:

- **Default to the main session.** It already has the context. It's both your
  cheapest option and your teacher.
- **Spawn a teammate on purpose**, when it genuinely pays off:
  - **Explore** — when the answer means searching *many* files and you only want the
    conclusion, not a pile of file contents in your main chat.
  - **builder** — when a task is self-contained and you'd rather keep the main chat
    clean while it works.
  - **reviewer** — when you specifically want a *fresh, independent* opinion (the
    whole value is that it did NOT see the code being written).
- More agents ≠ better. A real team of two ships more than a confused team of ten.

> This is the honest answer to "should I make an agent for every task?" — no. You
> make an agent when *independence* or *isolation* is worth the cost of a cold start.

---

## 3. Glossary — the words, grounded in *your* app

Read these once; they'll click faster because they're tied to code you own.

- **Frontend** — the part you see and tap. Yours is **React** (a JavaScript tool for
  building screens) in `frontend/src/`. The gym screen, the charts, the buttons.
- **Backend** — the part you don't see: it stores data and does the logic. Yours is
  **FastAPI** (a Python tool) in `backend/app/`. It holds your weights, workouts,
  and health data.
- **API** — the menu of things the frontend can ask the backend to do. Think of a
  restaurant: you (frontend) don't go into the kitchen; you order from a menu (the
  API) and the kitchen (backend) makes it. Each menu item is an **endpoint**.
- **Endpoint** — one specific item on that menu: a URL that does one job. E.g.
  `POST /api/weight` means "save a new weight reading." `POST`/`GET` are the *verbs*
  (roughly: save vs. fetch).
- **Request / response** — the frontend sends a **request** ("save 82.5 kg for
  today"); the backend sends back a **response** ("done, here's the updated record").
- **Database** — where the backend permanently keeps data. Yours is **SQLite** while
  you develop and **Postgres** in production. A giant, reliable set of tables.
- **Model** — in the backend, the Python description of one kind of thing you store
  (a `User`, a `Workout`). Lives in `backend/app/models.py`.
- **Schema** — the agreed shape of data going in/out of the API, so the frontend and
  backend never misunderstand each other. Yours use **Pydantic** in `schemas.py`.
- **Migration** — a *versioned change to the database's shape* (e.g. adding a
  column). You never edit the database by hand; you write a migration (with
  **Alembic**) so the change is repeatable and reversible. Handle with care.
- **Component** — a reusable Lego brick of frontend UI (a button, a chart, a card).
- **Branch** — a private copy of the code where you can work without affecting the
  live app. Names say what's inside, e.g. `feat/splits` or `fix/postgres-driver`.
- **Commit** — a saved checkpoint of your changes, with a message saying what & why.
- **Pull Request (PR)** — a formal request to merge your branch into `main`, so it
  can be reviewed (by a teammate and by the automated tests) before going live.
- **Merge** — accepting a PR: your changes join `main`, the official version.
- **`main`** — the one true branch that represents the live app. Production deploys
  from it. We protect it: no working directly on `main`.
- **Deploy** — putting the merged code onto the real server so real users get it.
  Yours runs on **Railway**.
- **CI (Continuous Integration)** — a robot that automatically runs all your tests
  every time you open a PR. Green = safe to consider merging; red = stop. Yours is
  in `.github/workflows/ci.yml`.
- **Token** — the unit of "thinking" you're billed for. Long chats and cold-start
  agents use more. Planning first and clearing between topics keeps it low.

---

## 4. Keeping token use low (without slowing down)

- **Plan before building.** The wrong build is the most expensive thing there is.
- **Use `/clear` between unrelated tasks.** It wipes the chat's memory so old,
  irrelevant context stops riding along in every message. Start a new topic clean.
- **Let the main session do most work** — it already has context; a fresh agent
  has to re-read files to catch up.
- **Give agents tight scopes.** "Fix the weight-save bug in `sessions.py`" costs far
  less than "look at the app and find things to improve."
- **Verify with tests, not by re-reading everything.** The safety net exists so you
  don't have to re-check by hand.

---

## 5. Quick reference

**Commands**
- `/plan-feature <idea>` — write the spec before building.
- `/ship` — the full merge-to-main checklist (tests → review → PR, with your OK).
- `/code-review` — run the built-in reviewer on your current changes.
- `/output-style mentor` — turn teaching on. `/output-style default` — turn it off
  for a fast session.

**Agents** — ask the main session to "use the builder agent to…" or "have the
reviewer check…", or let it decide.

**Run the app locally** (for verifying): see `README.md` / `start.sh`.

**When a change is risky** (touches auth, production data, or needs a migration):
go through **staging** first — see `docs/STAGING.md`. Better slow than sorry with
real data.

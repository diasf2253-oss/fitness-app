---
description: The merge-to-main checklist — run tests, review, summarize the change in plain English, then open a Pull Request (with your OK).
argument-hint: (optional) a short title for the change
---

The user thinks a piece of work is done and wants to **ship** it — get it toward
the live app the way a real team does. Walk the full Pull-Request flow and narrate
each step so the user learns it. **Never merge or push without an explicit "yes"
from the user.**

Do the steps in order. Explain each step in one plain sentence as you reach it.

### 1. See what changed
Run `git status` and `git diff` (and `git diff --staged`) to gather the full set of
changes. Summarize for the user, in plain English: **what changed and why**, file by
file if it's small. This is the moment they should actually understand their own diff.

### 2. Run the safety net (tests)
- Backend: from `backend/`, run the test suite with the project's venv
  (`pytest`). Tests here run on in-memory SQLite and never touch real data.
- Frontend: from `frontend/`, run `npm test`.
Report results plainly. **If anything is red, stop** — explain what failed and offer
to fix it. A red suite is the team's signal that it's not ready to ship.

### 3. Code review
Run the built-in **`/code-review`** skill on the change. Summarize its findings in
beginner terms — *what* it flagged and *why it matters*. Decide with the user which
findings to fix now vs. note for later. Fix the agreed ones, then re-run tests.

### 4. Confirm before anything leaves the machine
Show the user:
- The branch you'll use (if you're on `main`, propose a sensibly-named feature
  branch first — we never commit straight to `main`).
- The commit message you propose (clear, present-tense, says *why*).
- That the next action opens a **Pull Request** — a request to merge this branch
  into `main`, which teammates (and the CI tests) review before it goes live.

**Then stop and ask the user to confirm.** Do not push or open the PR until they say yes.

### 5. On the user's yes
- Create the branch if needed, stage, commit (end the message with the project's
  Co-Authored-By line), and push.
- Open the PR with `gh` — a clear title and a body that explains the change in plain
  English. End the PR body with the project's "Generated with Claude Code" line.
- Give the user the PR link and explain what happens next for *this* repo: CI runs
  both test suites on the PR; once it's green and merged to `main`, production
  deploys (Railway). Remind them of the staging step if this is risky (auth,
  production data, or a database migration — see `docs/STAGING.md`).

### Teaching note
After shipping, add a short **"🎓 What you just learned"** recap covering the words
that came up: branch, commit, Pull Request, CI, merge, deploy. Keep it to a few
bullets.

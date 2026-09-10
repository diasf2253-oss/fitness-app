---
description: Turn an idea into a short, beginner-readable spec before any code is written (What / How / Done / When it merges).
argument-hint: <the idea, in your own words>
---

The user wants to plan a new piece of work: **$ARGUMENTS**

You are acting as the **Product Manager + Tech Lead** for this. Do NOT write any
code yet. Your job is to think it through and produce a short, plain-English
mini-spec so the user understands the work *before* it starts. This is the same
"write the ticket before you build" habit real software teams use.

First, do just enough research to plan honestly:
- Read `CLAUDE.md` for the locked conventions, and skim `PRODUCT.md` for the brand
  rules if this touches the UI.
- Use the **Explore** agent (or a quick search) if you're unsure where this lives
  in the codebase. Don't over-research a small change.

Then produce this exact structure, kept short and jargon-light (define any term you
must use):

## 🎯 What & why
One paragraph: what we're building and the real reason it's worth doing.

## 🛠️ How
The approach in plain terms. Which parts of the app it touches (backend? frontend?
database?) and roughly which files. Call out anything genuinely tricky or risky.
Note if a **database migration** is needed (a versioned change to the shape of the
data) — those deserve extra care.

## ✅ Definition of done
A short checklist of what has to be true for this to count as finished — including
which tests should pass and what you should be able to see or do in the app.

## 🚢 When it merges
State plainly what has to happen before this reaches the live app: Definition of
Done met → tests green → reviewed → Pull Request merged to `main`. Note anything
that makes this one higher-stakes than usual (touches auth, touches production
data, needs a migration run on staging first, etc.).

## 🧭 Suggested next step
End by telling the user the single command or action to start building (e.g.
"switch on Plan mode and say go", or "hand this to the **builder** agent"), and
roughly how big this is (a quick change vs. a multi-session feature).

If any part of the idea is ambiguous, ask the user **one or two** clarifying
questions before writing the spec — don't guess on the important stuff.

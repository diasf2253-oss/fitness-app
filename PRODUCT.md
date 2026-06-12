# Product

## Register

product

## Users

One user: Felipe. Two contexts with very different demands:

- **Phone in the gym** (390px, installed PWA): mid-workout logging with sweaty
  thumbs — large tap targets, glanceable numbers, zero friction. Also quick
  daily check-ins (mood, habits, journal) from the couch.
- **Laptop at home/desk** (≥1024px): the reflective surface — reviewing weeks,
  browsing the calendar, reading insights, managing settings.

The job: track everything about a life (training, body, sleep, food,
habits, mood) with near-zero manual effort — Apple Health pushes the data —
and make the accumulation legible.

## Product Purpose

A single-user, self-hosted life tracker. Workout logging is manual and
deliberate (it happens in the gym); everything else syncs from Apple Health.
Success = the daily check-in takes under 20 seconds, the dashboard answers
"how am I doing" in one glance, and insights surface relationships Felipe
wouldn't have noticed.

## Brand Personality

Calm, premium, editorial. "Quiet confidence" — the app speaks softly and
never gamifies, shouts, or congratulates. Three words: quiet, considered,
honest. Honest extends to data: no flattering noise (correlations carry n,
caveats are printed, deltas show direction without judgment).

## Anti-references

- Generic fitness apps: loud saturated accents, bold condensed type,
  trophy/flame emoji, confetti, streak-shaming. Felipe rejected an early
  orange "athletic" theme as "generic… rushed and cheap".
- Candy-colored dashboard templates (pastel pink/yellow/green tiles).
- Anything that looks templated or AI-default.

## Design Principles

1. **Quiet over loud** — bone ink on deep green-charcoal; sage is the only
   accent that moves; destructive actions are muted terracotta, never alarm red.
2. **The day is the atom** — everything keys to a date (upserts, calendar,
   check-in, day detail); the UI should always make "this day" tangible.
3. **Honest numbers** — tabular figures, units always visible, small samples
   declared, no judgment colors on deltas.
4. **One system, two postures** — phone is for capture, laptop is for
   reflection; same components, different density and chrome.
5. **Earn every pixel of motion** — transitions are felt, not seen;
   reduced-motion is a first-class path.

## Accessibility & Inclusion

- Gym-context tap targets: ≥44px for primary actions (workout screen rule).
- `prefers-reduced-motion` honored globally.
- Keyboard: visible focus states required on all interactive elements.
- Contrast: bone (#ece9e0) on charcoal (#151b18) for body text; muted sage
  (#9aa69b) reserved for secondary text at larger sizes.

# Design — "Quiet Tracker"

Calm editorial dark system. Deep green-charcoal surfaces under a soft sage
mist, bone ink, serif display type with italic accent words, pill-shaped
actions, hairline borders. The opposite of a loud gym app.

Source of truth: `frontend/src/index.css` (CSS custom properties).

## Theme

Dark only (gym at 6am, bedroom at 11pm — the ambient-light story is dark).
Background carries two faint sage radial gradients so it never reads flat.

## Colors

| Role | Token | Value |
| --- | --- | --- |
| Background | `--color-bg` | `#151b18` |
| Card surface | `--color-surface` | `#1d2521` |
| Wells / inputs | `--color-surface2` | `#273029` |
| Raised / hover | `--color-elevated` | `#2f3a33` |
| Ink (bone) | `--color-text` | `#ece9e0` |
| Secondary (sage gray) | `--color-muted` | `#9aa69b` |
| Primary action (bone pill) | `--color-primary` | `#ece9e0` (ink `--color-on-primary #1b211d`) |
| Accent (sage) | `--color-accent` | `#a8bfa1` |
| Success | `--color-success` | `#8fb573` |
| Danger (muted terracotta) | `--color-danger` | `#cf8772` |
| Warning | `--color-warning` | `#d9b06b` |
| Hairlines | `--color-border` | `rgba(236,233,224,0.08)` (strong: `0.16`) |

Tinted fills exist for each semantic (`--tint-*`). Charts use sage `#a8bfa1`,
moss `#7f9b78`, bone for overlays, grid `rgba(236,233,224,0.07)`.

## Typography

- Display: **Fraunces** (variable, 300–600 + italics) — headings at light
  weight (~380), italic `<em>` accent words ("Good *morning*").
- Body/UI: **Inter** (300–700).
- Numbers: `tabular-nums` everywhere data lives (`.stat-num`, `.tnum`);
  big stats are Inter 300, large and airy.
- Micro-labels: 0.6–0.72rem, uppercase, letter-spacing 0.1–0.14em, muted —
  used as *data labels inside widgets* (e.g. "LAST 7 DAYS"), one per card
  edge, never as section eyebrows.

## Shape & Elevation

- Radii: 12 / 16 / 20px; actions are pills (`999px`).
- Shadows are low-contrast and soft (`--shadow-sm/md/lg`); no glows.
- Cards: surface + hairline + `--radius-lg` + `--shadow-sm`.

## Motion

- Easing `cubic-bezier(0.16,1,0.3,1)` (ease-out-quint family).
- Buttons compress slightly on press (`scale(0.98)`).
- Global `prefers-reduced-motion` kill-switch already in place.

## Components

- **Bottom nav (phone)**: floating translucent pill bar, blur, active item
  gets a soft bone-tint pill.
- **Sidebar (≥1024px)**: fixed 232px, italic serif wordmark ("tracker."
  placeholder), General/Tools sections, 17px stroke icons (1.75 weight).
- **Buttons**: primary = bone pill w/ dark ink; `.secondary` = translucent
  + hairline; `.danger` = terracotta tint, never solid red.
- **Inputs**: surface2, hairline, sage focus ring (`--tint-accent` 3px).
- **Badges**: pill, tracked uppercase, optional sage status dot (`.dot`).
- **Charts (Recharts)**: hairline grid, no axis lines, dark tooltip card.
- **Calendar**: monday-first grid, sage dot = workout, lifted cell = health
  data, bone pill = selected, inset ring = today.
- **Check-in**: habit pills (sage tint when done + streak), 1–5 scale dots,
  inline number inputs, journal textarea.

## Layout

- Phone-first: single column, `.page` max 680px, bottom-nav clearance.
- Desktop: `.page` 760px / `.page.wide` 1180px; dashboard = 2-col widget
  grid (`.dash-widgets`, `.span-2` for charts) + 320px right rail
  (calendar + day detail).

## Voice

Sentence case everywhere. Quiet copy ("Here's where things stand."),
no exclamation marks, no gamification language. Honest data captions
("correlation, not causation — and small samples lie").

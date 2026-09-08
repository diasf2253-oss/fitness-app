/**
 * Rank ladder, local-first — mirrors backend/app/ranks.py (engine) and
 * backend/app/routers/ranks.py (GET /api/ranks aggregation) over IndexedDB.
 *
 * 9 tiers (Wood → Olympian) × 3 divisions (III → I) with an LP readout.
 * A muscle's rank is the AVERAGE of its exercises' scores; each score is
 * the all-time best 1RM ÷ bodyweight against that exercise's own benchmark.
 * Same capped Epley as the PR system, so ranks and PRs never disagree.
 */
import { db } from '../db'
import { realWeightPoints } from '../weights'
import { epley1rm, isWorkingSet } from './workout'
import { MUSCLE_GROUPS } from './muscles'
import { round } from './util'

export const TIERS = ['Wood', 'Bronze', 'Silver', 'Gold', 'Platinum', 'Diamond', 'Champion', 'Titan', 'Olympian']
const DIVISIONS = ['III', 'II', 'I']

export const TIER_COLORS = {
  Wood: '#7c6a52', Bronze: '#b06b2c', Silver: '#b8c0c8', Gold: '#e3b341',
  Platinum: '#45c2b1', Diamond: '#54a8e8', Champion: '#a85cd6',
  Titan: '#e2556a', Olympian: '#f4d35e',
}
export const UNRANKED_COLOR = '#3a423c'

// Legacy male standards — kept for rank_config override compat.
export const STANDARDS = {
  squat: [1.25, 1.50, 1.75, 2.25, 2.75],
  bench: [0.85, 1.00, 1.25, 1.50, 2.00],
  deadlift: [1.50, 1.75, 2.00, 2.50, 3.00],
  ohp: [0.55, 0.65, 0.80, 1.00, 1.30],
}
const BODY_MAP_EXTRA = ['Forearms', 'Adductors']

export const COMMON_ANCHORS = [0.55, 0.78, 1.05, 1.45, 1.95]
const DEFAULT_BENCHMARK = 1.0

export const EXERCISE_BENCHMARK = {
  // Chest
  'Barbell Bench Press': 1.25, 'Incline Barbell Press': 1.05, 'Dumbbell Bench Press': 0.48,
  'Incline Dumbbell Press': 0.42, 'Cable Fly': 0.42, 'Dumbbell Fly': 0.28,
  // Back
  'Barbell Row': 1.20, 'Pull-Up': 1.05, 'Lat Pulldown': 1.20, 'Seated Cable Row': 1.20,
  'Dumbbell Row': 0.55, 'Deadlift': 2.00, 'T-Bar Row': 1.20,
  // Shoulders
  'Overhead Press (Barbell)': 0.80, 'Dumbbell Shoulder Press': 0.34, 'Lateral Raise': 0.20,
  'Cable Lateral Raise': 0.18, 'Face Pull': 0.45, 'Rear Delt Fly': 0.20,
  // Biceps
  'Barbell Curl': 0.55, 'Dumbbell Curl': 0.24, 'Hammer Curl': 0.26, 'Cable Curl': 0.55,
  'Incline Dumbbell Curl': 0.22,
  // Triceps
  'Tricep Pushdown': 0.70, 'Overhead Tricep Extension': 0.52, 'Close-Grip Bench Press': 1.05,
  'Skull Crusher': 0.58,
  // Quads
  'Barbell Squat': 1.75, 'Leg Press': 4.00, 'Bulgarian Split Squat': 0.55,
  'Leg Extension': 1.30, 'Hack Squat': 2.80,
  // Hamstrings / Glutes
  'Romanian Deadlift': 1.60, 'Leg Curl (Lying)': 1.00, 'Hip Thrust': 2.50,
  'Cable Pull-Through': 1.10,
  // Calves
  'Standing Calf Raise': 3.50, 'Seated Calf Raise': 3.00,
  // Core
  'Cable Crunch': 1.00,
}
export const GROUP_BENCHMARK = {
  Chest: 1.00, Back: 1.20, Shoulders: 0.60, Biceps: 0.50, Triceps: 0.65,
  Quads: 1.75, Hamstrings: 1.40, Glutes: 2.20, Calves: 3.20, Abs: 0.90,
  Forearms: 0.55, Adductors: 1.10,
}
export const EQUIPMENT_FACTOR = {
  barbell: 1.00, machine: 1.20, cable: 0.75, dumbbell: 0.42,
  kettlebell: 0.42, bodyweight: 1.00,
  // Fixed bar path: more than free barbell, less than a loaded machine.
  smith: 1.10,
}
export const UNILATERAL_FACTOR = 0.55
const UNILATERAL_HINTS = [
  'single-arm', 'single arm', 'one-arm', 'one arm', 'single-leg', 'single leg',
  'one-leg', 'one leg', 'unilateral', 'bulgarian', 'split squat', 'lunge',
  'step-up', 'step up', 'pistol',
]

export function isUnilateral(name) {
  const n = (name || '').toLowerCase()
  return UNILATERAL_HINTS.some(h => n.includes(h))
}

const DEFAULT_FEMALE_MULTIPLIER = 0.65

/** Lower bound of each of the 9 tiers from the 5 anchors — mirrors tier_lowers. */
export function tierLowers(anchors) {
  const [beg, nov, inter, adv, eli] = anchors
  return [
    0.0, beg, nov, (nov + inter) / 2, inter,
    (inter + adv) / 2, adv, (adv + eli) / 2, eli,
  ]
}

/** Map relative strength → tier / division / LP — mirrors compute_rank. */
export function computeRank(relativeStrength, anchors) {
  const lowers = tierLowers(anchors)
  let ti = 0
  lowers.forEach((low, i) => { if (relativeStrength >= low) ti = i })

  let lo, hi
  if (ti < 8) {
    lo = lowers[ti]; hi = lowers[ti + 1]
  } else {                                 // Olympian is open-ended: synthetic
    const width = lowers[8] - lowers[7]    // band = width of the Titan tier
    lo = lowers[8]; hi = lowers[8] + width
  }

  const sub = hi > lo ? (hi - lo) / 3 : 0.0
  let divIdx, lp
  if (ti === 8 && relativeStrength >= hi) {
    divIdx = 2; lp = 100.0                 // beyond the top → Olympian I, 100 LP
  } else if (sub <= 0) {
    divIdx = 0; lp = 0.0
  } else {
    divIdx = Math.min(2, Math.floor((relativeStrength - lo) / sub))
    const divLo = lo + divIdx * sub
    lp = Math.max(0.0, Math.min(100.0, (relativeStrength - divLo) / sub * 100))
  }

  const tier = TIERS[ti]
  return {
    tier,
    tier_index: ti,
    division: DIVISIONS[divIdx],
    lp: Math.round(lp),
    relative_strength: round(relativeStrength, 2),
    color: TIER_COLORS[tier],
  }
}

/** Defaults + per-user overrides merged — mirrors resolve_config. */
export function resolveConfig(overrides) {
  const cfg = {
    standards: Object.fromEntries(Object.entries(STANDARDS).map(([k, v]) => [k, [...v]])),
    female_multiplier: DEFAULT_FEMALE_MULTIPLIER,
    body_part_agg: 'best',
  }
  if (overrides) {
    for (const [lift, vals] of Object.entries(overrides.standards || {})) {
      if (lift in cfg.standards && Array.isArray(vals) && vals.length === 5) {
        cfg.standards[lift] = vals.map(Number)
      }
    }
    if (typeof overrides.female_multiplier === 'number') {
      cfg.female_multiplier = overrides.female_multiplier
    }
    if (['best', 'average'].includes(overrides.body_part_agg)) {
      cfg.body_part_agg = overrides.body_part_agg
    }
  }
  return cfg
}

/** Reference 1RM ÷ bodyweight for an exercise — mirrors exercise_benchmark. */
export function exerciseBenchmark(name, group, sex, cfg, equipment = null) {
  let base = EXERCISE_BENCHMARK[name]
  if (base == null) {
    base = GROUP_BENCHMARK[group || ''] ?? DEFAULT_BENCHMARK
    base *= EQUIPMENT_FACTOR[(equipment || '').toLowerCase()] ?? 1.0
    if (isUnilateral(name)) base *= UNILATERAL_FACTOR
  }
  if ((sex || 'male').toLowerCase() === 'female') base *= cfg.female_multiplier
  return base
}

// ---------------------------------------------------------------------------
// GET /api/ranks — mirrors routers/ranks.py over IndexedDB
// ---------------------------------------------------------------------------

async function bestAlltimeByExercise() {
  const ses = await db.session_exercise.toArray()
  const best = {}
  for (const se of ses) {
    const sets = (await db.set.where('session_exercise_uuid').equals(se.uuid).toArray())
      .filter(isWorkingSet)
    for (const s of sets) {
      const e = epley1rm(s.weight_kg, s.reps)
      const cur = best[se.exercise_uuid]
      if (!cur || e > cur.e1rm) best[se.exercise_uuid] = { e1rm: e, w: s.weight_kg, reps: s.reps }
    }
  }
  return best
}

async function getRanks() {
  const settings = (await db.settings.get(1)) || {}
  const cfg = resolveConfig(settings.rank_config)
  const sex = settings.sex || 'male'

  // Latest REAL reading only — demo/estimated rows never set the bodyweight
  // every rank divides by (mirrors routers/ranks._latest_bodyweight).
  const real = realWeightPoints(await db.weight_log.toArray())
  const bw = real.length ? real[real.length - 1].weight_kg : null

  const exercises = await db.exercise.toArray()
  const byUuid = Object.fromEntries(exercises.map(e => [e.uuid, e]))
  const byGroup = {}
  for (const e of exercises) {
    if (e.primary_muscle_group) (byGroup[e.primary_muscle_group] ||= []).push(e.uuid)
  }

  const bestAll = await bestAlltimeByExercise()

  const bodyParts = []
  for (const m of [...MUSCLE_GROUPS, ...BODY_MAP_EXTRA]) {
    const contribs = []
    if (bw) {
      for (const eid of byGroup[m] || []) {
        const rec = bestAll[eid]
        if (!rec) continue
        const ex = byUuid[eid]
        const bench = exerciseBenchmark(ex.name, m, sex, cfg, ex.equipment)
        const score = (rec.e1rm / bw) / bench
        const er = computeRank(score, COMMON_ANCHORS)
        contribs.push({
          exercise_name: ex.name,
          equipment: ex.equipment ?? null,
          best_1rm: round(rec.e1rm, 1),
          best_set: `${rec.w} kg × ${rec.reps}`,
          relative: round(rec.e1rm / bw, 2),
          score: round(score, 2),
          tier: er.tier, tier_index: er.tier_index,
          division: er.division, lp: er.lp, color: er.color,
        })
      }
    }
    contribs.sort((a, b) => (b.tier_index + b.lp / 100) - (a.tier_index + a.lp / 100))
    const bp = {
      muscle: m, ranked: false, color: UNRANKED_COLOR,
      tracked: MUSCLE_GROUPS.includes(m),
      n_exercises: contribs.length, exercises: contribs,
    }
    if (contribs.length) {
      const meanScore = contribs.reduce((a, c) => a + c.score, 0) / contribs.length
      const rank = computeRank(meanScore, COMMON_ANCHORS)
      Object.assign(bp, { ranked: true, score: round(meanScore, 2), ...rank })
    }
    bodyParts.push(bp)
  }

  return {
    bodyweight: bw, sex,
    tiers: TIERS, tier_colors: TIER_COLORS, unranked_color: UNRANKED_COLOR,
    body_parts: bodyParts,
    note: bw ? null : 'Log your bodyweight to see ranks.',
  }
}

/** {exercise_uuid: {ranked, tier, division, lp, color}} — mirrors
 * routers/ranks.get_exercise_ranks. Keyed by the same value presentExercise
 * hands the UI as `id`, so a page can look a rank up directly. */
async function getExerciseRanks() {
  const settings = (await db.settings.get(1)) || {}
  const cfg = resolveConfig(settings.rank_config)
  const sex = settings.sex || 'male'
  const real = realWeightPoints(await db.weight_log.toArray())
  const bw = real.length ? real[real.length - 1].weight_kg : null

  const exercises = await db.exercise.toArray()
  const bestAll = await bestAlltimeByExercise()

  const out = {}
  for (const ex of exercises) {
    let entry = { ranked: false, tier: null, division: null, lp: null, color: UNRANKED_COLOR }
    const rec = bestAll[ex.uuid]
    if (bw && rec && ex.primary_muscle_group) {
      const bench = exerciseBenchmark(ex.name, ex.primary_muscle_group, sex, cfg, ex.equipment)
      const er = computeRank((rec.e1rm / bw) / bench, COMMON_ANCHORS)
      entry = { ranked: true, tier: er.tier, division: er.division, lp: er.lp, color: er.color }
    }
    out[ex.uuid] = entry
  }
  return out
}

export const rankRoutes = [
  // Exact-anchored, so /api/ranks/exercises never matches the body-map route.
  { method: 'GET', pattern: /^\/api\/ranks\/exercises$/, handler: () => getExerciseRanks() },
  { method: 'GET', pattern: /^\/api\/ranks$/, handler: () => getRanks() },
]

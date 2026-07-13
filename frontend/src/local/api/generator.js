/**
 * Workout generator, local-first — mirrors backend app/generator.py +
 * routers/generator.py. Pure program-building over IndexedDB; only PRIMARY
 * muscle groups count.
 */
import { db, newUuid, nowIso } from '../db'
import { MUSCLE_GROUPS, resolvedVolumeTargets } from './muscles'
import { LocalApiError } from './util'

const stamp = (row) => ({ ...row, updated_at: nowIso(), _dirty: 1 })

// Which primary muscle groups each split's day-type trains.
export const SPLITS = {
  full_body: [['Full Body', [...MUSCLE_GROUPS]]],
  upper_lower: [
    ['Upper', ['Chest', 'Back', 'Shoulders', 'Biceps', 'Triceps']],
    ['Lower', ['Quads', 'Hamstrings', 'Glutes', 'Calves', 'Abs']],
  ],
  ppl: [
    ['Push', ['Chest', 'Shoulders', 'Triceps']],
    ['Pull', ['Back', 'Biceps']],
    ['Legs', ['Quads', 'Hamstrings', 'Glutes', 'Calves', 'Abs']],
  ],
  bro: [
    ['Chest', ['Chest']],
    ['Back', ['Back']],
    ['Shoulders', ['Shoulders']],
    ['Legs', ['Quads', 'Hamstrings', 'Glutes', 'Calves', 'Abs']],
    ['Arms', ['Biceps', 'Triceps']],
  ],
}
export const SPLIT_LABELS = {
  full_body: 'Full Body', upper_lower: 'Upper/Lower', ppl: 'PPL', bro: 'Bro split',
}

const COMPOUND_REPS = [6, 10]
const ISOLATION_REPS = [10, 15]
const MAX_SETS_PER_EXERCISE = 4
const MAX_EXERCISES_PER_MUSCLE_PER_DAY = 3

const COMPOUND_KEYWORDS = [
  'squat', 'press', 'bench', 'row', 'deadlift', 'pulldown', 'pull-up', 'pull up',
  'pullup', 'chin', 'dip', 'lunge', 'thrust', 'hack', 'leg press', 'split squat',
  'push-up', 'pushup', 'clean', 'overhead',
]

export function isCompound(name) {
  const n = (name || '').toLowerCase()
  return COMPOUND_KEYWORDS.some(k => n.includes(k))
}

function arrange(splitType, days) {
  const cycle = SPLITS[splitType].map(([name]) => name)
  return Array.from({ length: days }, (_, i) => cycle[i % cycle.length])
}

function targetSets(muscle, priority, targets) {
  const [low, high] = targets[muscle]
  if (priority.includes(muscle)) return high
  return Math.max(low, Math.round((low + high) / 2))
}

function splitSets(total, n) {
  const base = Math.floor(total / n)
  const rem = total % n
  return Array.from({ length: n }, (_, i) => base + (i < rem ? 1 : 0))
}

// Pure port of generator.generate → the _program_dict shape.
export function generate({ priority, daysPerWeek, splitType, targets, exercisesByGroup }) {
  if (!(splitType in SPLITS)) throw new LocalApiError(422, `unknown split_type ${splitType}`)

  const daySpecs = Object.fromEntries(SPLITS[splitType])
  const arrangement = arrange(splitType, daysPerWeek)
  const distinctDays = [...new Set(arrangement)]
  const dayCount = Object.fromEntries(
    distinctDays.map(d => [d, arrangement.filter(x => x === d).length])
  )

  const trained = []
  for (const d of distinctDays) {
    for (const m of daySpecs[d]) if (!trained.includes(m)) trained.push(m)
  }

  const notes = []
  for (const m of priority) {
    if (!trained.includes(m)) {
      notes.push(`${m} is a priority but isn't trained by a ${daysPerWeek}-day ` +
        `${SPLIT_LABELS[splitType]} — add a day or pick another split.`)
    }
  }

  const sessionsFor = {}
  const perSession = {}
  const weeklySets = {}
  for (const m of trained) {
    sessionsFor[m] = distinctDays.filter(d => daySpecs[d].includes(m))
      .reduce((a, d) => a + dayCount[d], 0)
    const s = sessionsFor[m]
    perSession[m] = s ? Math.max(1, Math.round(targetSets(m, priority, targets) / s)) : 0
    weeklySets[m] = perSession[m] * s
  }

  if (trained.some(m => priority.includes(m))) {
    notes.push('Priority muscles set to the top of their target range (capped at the maximum).')
  }

  const routines = []
  for (const d of distinctDays) {
    const muscles = daySpecs[d]
    const ordered = [...priority.filter(m => muscles.includes(m)),
                     ...muscles.filter(m => !priority.includes(m))]
    const routine = { name: `${SPLIT_LABELS[splitType]} · ${d}`, day_type: d, exercises: [] }

    for (const m of ordered) {
      const total = perSession[m] || 0
      if (total <= 0) continue
      const pool = exercisesByGroup[m] || []
      if (pool.length === 0) {
        if (!notes.includes(`no-ex-${m}`)) {
          notes.push(`No exercises tagged for ${m} — add some in the library.`)
          notes.push(`no-ex-${m}`)
        }
        continue
      }

      const want = Math.max(1, Math.ceil(total / MAX_SETS_PER_EXERCISE))
      const nEx = Math.min(want, MAX_EXERCISES_PER_MUSCLE_PER_DAY, pool.length)
      if (pool.length < want) {
        notes.push(`Only ${pool.length} exercise(s) tagged for ${m}; add more for variety.`)
      }

      const poolSorted = [...pool].sort((a, b) => {
        const ca = isCompound(a.name) ? 0 : 1
        const cb = isCompound(b.name) ? 0 : 1
        return ca - cb || (a.name < b.name ? -1 : a.name > b.name ? 1 : 0)
      })
      const chosen = poolSorted.slice(0, nEx)
      const sets = splitSets(total, nEx)
      chosen.forEach((ex, i) => {
        const comp = isCompound(ex.name)
        const [lo, hi] = comp ? COMPOUND_REPS : ISOLATION_REPS
        routine.exercises.push({
          exercise_id: ex.id, name: ex.name, muscle_group: m,
          sets: sets[i], rep_low: lo, rep_high: hi, is_compound: comp,
        })
      })
    }
    routines.push(routine)
  }

  const cleanNotes = notes.filter(n => !n.startsWith('no-ex-'))

  return {
    split_type: splitType,
    split_label: SPLIT_LABELS[splitType],
    days_per_week: daysPerWeek,
    arrangement,
    weekly_sets: weeklySets,
    targets: Object.fromEntries(Object.entries(targets).map(([m, [lo, hi]]) => [m, { low: lo, high: hi }])),
    notes: cleanNotes,
    routines,
  }
}

async function settingsRow() {
  return (await db.settings.get(1)) || {}
}

async function exercisesByGroup() {
  const out = {}
  for (const ex of await db.exercise.toArray()) {
    if (!ex.primary_muscle_group) continue
    ;(out[ex.primary_muscle_group] ||= []).push({ id: ex.uuid, name: ex.name })
  }
  return out
}

function validate(body) {
  if (!(body.split_type in SPLITS)) {
    throw new LocalApiError(422, `split_type must be one of ${Object.keys(SPLITS)}`)
  }
  const bad = (body.priority_muscles || []).filter(m => !MUSCLE_GROUPS.includes(m))
  if (bad.length) throw new LocalApiError(422, `unknown priority muscles: ${bad}`)
}

async function build(body) {
  const targets = resolvedVolumeTargets((await settingsRow()).volume_targets)
  return generate({
    priority: body.priority_muscles || [],
    daysPerWeek: body.days_per_week,
    splitType: body.split_type,
    targets,
    exercisesByGroup: await exercisesByGroup(),
  })
}

async function presentRoutine(r) {
  const res = (await db.routine_exercise.where('routine_uuid').equals(r.uuid).toArray())
    .sort((a, b) => a.position - b.position)
  return {
    id: r.uuid, name: r.name, source: r.source ?? 'manual',
    notes: r.notes ?? null, created_at: r.created_at,
    exercises: await Promise.all(res.map(async (re) => {
      const ex = await db.exercise.get(re.exercise_uuid)
      return {
        id: re.uuid, exercise_id: re.exercise_uuid, position: re.position,
        target_sets: re.target_sets, target_rep_low: re.target_rep_low,
        target_rep_high: re.target_rep_high, rest_seconds: re.rest_seconds,
        exercise: ex ? { id: ex.uuid, name: ex.name, primary_muscle_group: ex.primary_muscle_group ?? null } : null,
      }
    })),
  }
}

async function apply(body) {
  validate(body)
  const prog = await build(body)

  const old = (await db.routine.toArray()).filter(r => r.source === 'generated')
  const replaced = old.length
  for (const r of old) {
    const res = await db.routine_exercise.where('routine_uuid').equals(r.uuid).toArray()
    for (const re of res) await db.routine_exercise.delete(re.uuid)
    await db.routine.delete(r.uuid)
  }

  const created = []
  for (const r of prog.routines) {
    const routine = stamp({
      uuid: newUuid(), name: r.name, source: 'generated',
      notes: null, created_at: nowIso(),
    })
    await db.routine.put(routine)
    let pos = 0
    for (const e of r.exercises) {
      await db.routine_exercise.put(stamp({
        uuid: newUuid(), routine_uuid: routine.uuid, exercise_uuid: e.exercise_id,
        position: pos++, target_sets: e.sets, target_rep_low: e.rep_low,
        target_rep_high: e.rep_high, rest_seconds: e.is_compound ? 180 : 90,
      }))
    }
    created.push(routine)
  }

  return {
    replaced,
    notes: prog.notes,
    routines: await Promise.all(created.map(presentRoutine)),
  }
}

export const generatorRoutes = [
  {
    method: 'GET', pattern: /^\/api\/generator\/options$/,
    handler: () => ({
      muscle_groups: MUSCLE_GROUPS,
      split_types: Object.keys(SPLITS).map(k => ({ value: k, label: SPLIT_LABELS[k] })),
    }),
  },
  {
    method: 'POST', pattern: /^\/api\/generator\/preview$/,
    handler: async (_m, _q, body) => { validate(body); return build(body) },
  },
  { method: 'POST', pattern: /^\/api\/generator\/apply$/, handler: (_m, _q, body) => apply(body) },
]

/**
 * Splits, local-first — mirrors backend/app/routers/splits.py and
 * split_templates.py so the phone can group and build splits offline.
 *
 * A split is a named group of routines; routine.split_uuid NULL means
 * ungrouped. Deleting a split detaches its routines rather than deleting them
 * — training history must never disappear with a bit of organisation.
 */
import { db, newUuid, nowIso } from '../db'
import { LocalApiError, notFound } from './util'

const stamp = (row) => ({ ...row, updated_at: nowIso(), _dirty: 1 })

// Mirrors SPLIT_TEMPLATES in backend/app/split_templates.py — keep in step.
// [exerciseName, sets]; a name the library doesn't have is skipped.
export const SPLIT_TEMPLATES = {
  ppl: {
    name: 'Push / Pull / Legs',
    days: [
      { name: 'Push', exercises: [['Barbell Bench Press', 4], ['Overhead Press (Barbell)', 3], ['Incline Dumbbell Press', 3], ['Lateral Raise', 3], ['Tricep Pushdown', 3]] },
      { name: 'Pull', exercises: [['Deadlift', 3], ['Pull-Up', 3], ['Seated Cable Row', 3], ['Face Pull', 3], ['Barbell Curl', 3]] },
      { name: 'Legs', exercises: [['Barbell Squat', 4], ['Romanian Deadlift', 3], ['Leg Press', 3], ['Leg Curl (Lying)', 3], ['Standing Calf Raise', 4]] },
    ],
  },
  bro: {
    name: 'Bro Split',
    days: [
      { name: 'Chest', exercises: [['Barbell Bench Press', 4], ['Incline Dumbbell Press', 3], ['Cable Fly', 3], ['Dumbbell Fly', 3]] },
      { name: 'Back', exercises: [['Deadlift', 3], ['Pull-Up', 3], ['Barbell Row', 3], ['Lat Pulldown', 3], ['Seated Cable Row', 3]] },
      { name: 'Shoulders', exercises: [['Overhead Press (Barbell)', 4], ['Lateral Raise', 4], ['Rear Delt Fly', 3], ['Face Pull', 3]] },
      { name: 'Arms', exercises: [['Barbell Curl', 3], ['Incline Dumbbell Curl', 3], ['Skull Crusher', 3], ['Tricep Pushdown', 3], ['Hammer Curl', 3]] },
      { name: 'Legs', exercises: [['Barbell Squat', 4], ['Romanian Deadlift', 3], ['Leg Press', 3], ['Leg Extension', 3], ['Standing Calf Raise', 4]] },
    ],
  },
  legs_glutes: {
    name: 'Legs & Glutes',
    days: [
      { name: 'Legs & Glutes A', exercises: [['Barbell Squat', 4], ['Hip Thrust', 4], ['Romanian Deadlift', 3], ['Leg Curl (Lying)', 3], ['Standing Calf Raise', 4]] },
      { name: 'Legs & Glutes B', exercises: [['Hack Squat', 4], ['Cable Pull-Through', 3], ['Bulgarian Split Squat', 3], ['Leg Extension', 3], ['Seated Calf Raise', 4]] },
    ],
  },
}

async function present(s) {
  const routines = await db.routine.where('split_uuid').equals(s.uuid).toArray()
  return {
    id: s.uuid, name: s.name, position: s.position ?? 0,
    created_at: s.created_at, routine_count: routines.length,
  }
}

async function buildFromTemplate(split, key) {
  const tpl = SPLIT_TEMPLATES[key]
  if (!tpl) throw new LocalApiError(400, `Unknown split template '${key}'`)
  const library = await db.exercise.toArray()
  const byName = new Map(library.map(e => [e.name, e]))

  for (const day of tpl.days) {
    const routine = stamp({
      uuid: newUuid(), name: day.name, source: 'manual', notes: null,
      split_uuid: split.uuid, created_at: nowIso(),
    })
    await db.routine.put(routine)
    let position = 0
    for (const [exerciseName, sets] of day.exercises) {
      const ex = byName.get(exerciseName)
      if (!ex) continue          // trimmed library — skip, don't fail
      await db.routine_exercise.put(stamp({
        uuid: newUuid(), routine_uuid: routine.uuid, exercise_uuid: ex.uuid,
        position, target_sets: sets, target_rep_low: 8, target_rep_high: 12,
        rest_seconds: 120, target_rir: null, planned_sets: null,
      }))
      position += 1
    }
  }
}

async function listSplits() {
  const rows = await db.split.toArray()
  rows.sort((a, b) => (a.position ?? 0) - (b.position ?? 0) || a.name.localeCompare(b.name))
  return Promise.all(rows.map(present))
}

async function createSplit(body) {
  let name = (body.name || '').trim()
  if (!name && body.template) name = SPLIT_TEMPLATES[body.template]?.name || ''
  if (!name) throw new LocalApiError(422, 'A split needs a name')

  const existing = await db.split.toArray()
  const last = existing.reduce((m, s) => Math.max(m, s.position ?? 0), 0)
  const split = stamp({
    uuid: newUuid(), name, position: last + 1, created_at: nowIso(),
  })
  await db.split.put(split)
  if (body.template) await buildFromTemplate(split, body.template)
  return present(split)
}

async function updateSplit(uuid, body) {
  const s = await db.split.get(uuid)
  if (!s) throw notFound('Split')
  const row = stamp({
    ...s,
    name: body.name != null ? body.name.trim() : s.name,
    position: body.position != null ? body.position : s.position,
  })
  await db.split.put(row)
  return present(row)
}

async function deleteSplit(uuid) {
  const s = await db.split.get(uuid)
  if (!s) throw notFound('Split')
  // Detach the days first — deleting a split never deletes routines.
  const routines = await db.routine.where('split_uuid').equals(uuid).toArray()
  for (const r of routines) {
    await db.routine.put(stamp({ ...r, split_uuid: null }))
  }
  await db.split.delete(uuid)
  return null
}

export const splitRoutes = [
  {
    method: 'GET', pattern: /^\/api\/splits\/templates$/,
    handler: () => Object.entries(SPLIT_TEMPLATES).map(([key, t]) => ({
      key, name: t.name, days: t.days.map(d => d.name),
    })),
  },
  { method: 'GET', pattern: /^\/api\/splits$/, handler: () => listSplits() },
  { method: 'POST', pattern: /^\/api\/splits$/, handler: (_m, _q, body) => createSplit(body || {}) },
  { method: 'PUT', pattern: /^\/api\/splits\/([^/]+)$/, handler: (m, _q, body) => updateSplit(m[1], body || {}) },
  { method: 'DELETE', pattern: /^\/api\/splits\/([^/]+)$/, handler: (m) => deleteSplit(m[1]) },
]

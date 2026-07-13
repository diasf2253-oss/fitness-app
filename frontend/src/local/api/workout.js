/**
 * Workout domain, local-first (P4) — mirrors backend routers exercises.py,
 * routines.py, sessions.py and stats.py. All PR/1RM math is ported 1:1
 * (Epley with reps capped at 12; working sets = completed, non-warmup,
 * reps>0, weight>0).
 */
import { db, newUuid, nowIso } from '../db'
import { MUSCLE_GROUPS, resolvedVolumeTargets, suggestMuscleGroup } from './muscles'
import { consumePendingNotes, nextSessionNotesFor } from './routine_notes'
import { isoWeekStart } from './weight_trend'
import { LocalApiError, addDays, isoWeekKey, naiveIso, notFound, round, todayIso } from './util'

// ---------------------------------------------------------------------------
// Pure math (exported for tests) — mirrors stats.py
// ---------------------------------------------------------------------------

export function epley1rm(weightKg, reps) {
  const capped = Math.min(reps, 12)
  if (capped <= 1) return weightKg
  return weightKg * (1 + capped / 30)
}

export const isWorkingSet = (s) =>
  s.is_completed && !s.is_warmup && s.reps > 0 && s.weight_kg > 0

// ---------------------------------------------------------------------------
// Row access + presenters
// ---------------------------------------------------------------------------

const stamp = (row) => ({ ...row, updated_at: nowIso(), _dirty: 1 })

async function exerciseByUuid(uuid) {
  const ex = await db.exercise.get(uuid)
  if (!ex) throw notFound('Exercise')
  return ex
}

const presentExercise = (ex) => ({
  id: ex.uuid, name: ex.name,
  primary_muscle: ex.primary_muscle ?? null,
  primary_muscle_group: ex.primary_muscle_group ?? null,
  secondary_muscles: ex.secondary_muscles || [],
  equipment: ex.equipment ?? null,
  notes: ex.notes ?? null,
  is_custom: !!ex.is_custom,
})

const presentSet = (s) => ({
  id: s.uuid, session_exercise_id: s.session_exercise_uuid,
  set_number: s.set_number, weight_kg: s.weight_kg, reps: s.reps,
  rpe: s.rpe ?? null, is_warmup: !!s.is_warmup, is_completed: !!s.is_completed,
  completed_at: s.completed_at ?? null,
})

async function presentSessionExercise(se) {
  const [ex, sets] = await Promise.all([
    db.exercise.get(se.exercise_uuid),
    db.set.where('session_exercise_uuid').equals(se.uuid).toArray(),
  ])
  return {
    id: se.uuid, session_id: se.session_uuid, exercise_id: se.exercise_uuid,
    position: se.position,
    exercise: ex ? presentExercise(ex) : null,
    sets: sets.sort((a, b) => a.set_number - b.set_number).map(presentSet),
  }
}

async function presentSession(s) {
  const ses = await db.session_exercise.where('session_uuid').equals(s.uuid).toArray()
  ses.sort((a, b) => a.position - b.position)
  return {
    id: s.uuid, name: s.name, routine_id: s.routine_uuid ?? null,
    started_at: s.started_at, ended_at: s.ended_at ?? null, notes: s.notes ?? null,
    exercises: await Promise.all(ses.map(presentSessionExercise)),
    next_session_notes: await nextSessionNotesFor(s.uuid),
  }
}

const presentSessionSummary = (s) => ({
  id: s.uuid, name: s.name, routine_id: s.routine_uuid ?? null,
  started_at: s.started_at, ended_at: s.ended_at ?? null,
})

async function presentRoutine(r) {
  const res = await db.routine_exercise.where('routine_uuid').equals(r.uuid).toArray()
  res.sort((a, b) => a.position - b.position)
  return {
    id: r.uuid, name: r.name, source: r.source ?? 'manual',
    notes: r.notes ?? null, created_at: r.created_at,
    exercises: await Promise.all(res.map(async (re) => ({
      id: re.uuid, exercise_id: re.exercise_uuid, position: re.position,
      target_sets: re.target_sets, target_rep_low: re.target_rep_low,
      target_rep_high: re.target_rep_high, rest_seconds: re.rest_seconds,
      exercise: presentExercise(await exerciseByUuid(re.exercise_uuid)),
    }))),
  }
}

// ---------------------------------------------------------------------------
// Stats internals — mirrors stats.py
// ---------------------------------------------------------------------------

/** All working sets for an exercise, optionally excluding one session. */
async function workingSetsFor(exerciseUuid, { excludeSessionUuid } = {}) {
  const ses = await db.session_exercise.where('exercise_uuid').equals(exerciseUuid).toArray()
  const kept = ses.filter(se => se.session_uuid !== excludeSessionUuid)
  const nested = await Promise.all(
    kept.map(se => db.set.where('session_exercise_uuid').equals(se.uuid).toArray())
  )
  return nested.flat().filter(isWorkingSet)
}

async function computePrsForExercise(exerciseUuid) {
  const sets = await workingSetsFor(exerciseUuid)
  if (sets.length === 0) return null
  const ex = await db.exercise.get(exerciseUuid)
  return {
    exercise_id: exerciseUuid,
    exercise_name: ex ? ex.name : exerciseUuid,
    heaviest_weight_kg: Math.max(...sets.map(s => s.weight_kg)),
    best_estimated_1rm: round(Math.max(...sets.map(s => epley1rm(s.weight_kg, s.reps))), 1),
    best_set_volume: Math.max(...sets.map(s => s.weight_kg * s.reps)),
  }
}

/** Finish-workout summary with PR detection — mirrors stats.session_summary. */
export async function sessionSummary(sessionUuid) {
  const session = await db.session.get(sessionUuid)
  if (!session) throw notFound('Session')

  let duration = null
  if (session.ended_at) {
    duration = Math.floor(
      (Date.parse(session.ended_at) - Date.parse(session.started_at)) / 60000
    )
  }

  const ses = await db.session_exercise.where('session_uuid').equals(sessionUuid).toArray()
  const byExercise = new Map()
  let completedSets = 0
  let totalVolume = 0
  for (const se of ses) {
    const sets = (await db.set.where('session_exercise_uuid').equals(se.uuid).toArray())
      .filter(isWorkingSet)
    for (const s of sets) {
      if (!byExercise.has(se.exercise_uuid)) byExercise.set(se.exercise_uuid, [])
      byExercise.get(se.exercise_uuid).push(s)
      completedSets += 1
      totalVolume += s.weight_kg * s.reps
    }
  }

  const prsHit = []
  for (const [exerciseUuid, sets] of byExercise) {
    const ex = await db.exercise.get(exerciseUuid)
    const exName = ex ? ex.name : exerciseUuid
    const bestWeight = Math.max(...sets.map(s => s.weight_kg))
    const best1rm = Math.max(...sets.map(s => epley1rm(s.weight_kg, s.reps)))
    const bestVolume = Math.max(...sets.map(s => s.weight_kg * s.reps))

    const prior = await workingSetsFor(exerciseUuid, { excludeSessionUuid: sessionUuid })
    const priorWeight = prior.length ? Math.max(...prior.map(s => s.weight_kg)) : null
    const prior1rm = prior.length ? Math.max(...prior.map(s => epley1rm(s.weight_kg, s.reps))) : null
    const priorVolume = prior.length ? Math.max(...prior.map(s => s.weight_kg * s.reps)) : null

    if (priorWeight === null || bestWeight > priorWeight) {
      prsHit.push({ exercise_id: exerciseUuid, exercise_name: exName, kind: 'heaviest',
                    value: round(bestWeight, 1), previous_best: priorWeight ? round(priorWeight, 1) : null })
    }
    if (prior1rm === null || best1rm > prior1rm) {
      prsHit.push({ exercise_id: exerciseUuid, exercise_name: exName, kind: 'best_1rm',
                    value: round(best1rm, 1), previous_best: prior1rm ? round(prior1rm, 1) : null })
    }
    if (priorVolume === null || bestVolume > priorVolume) {
      prsHit.push({ exercise_id: exerciseUuid, exercise_name: exName, kind: 'best_volume',
                    value: round(bestVolume, 1), previous_best: priorVolume ? round(priorVolume, 1) : null })
    }
  }

  return {
    session_id: sessionUuid,
    duration_minutes: duration,
    total_volume_kg: round(totalVolume, 1),
    completed_sets: completedSets,
    prs_hit: prsHit,
  }
}

/** Completed working-set volume per calendar day — mirrors insights._daily_volume. */
export async function dailyVolume(startIso, endIso) {
  const sessions = await db.session.toArray()
  const inRange = sessions.filter(s => {
    const d = s.started_at.slice(0, 10)
    return d >= startIso && d <= endIso
  })
  const acc = {}
  for (const s of inRange) {
    const ses = await db.session_exercise.where('session_uuid').equals(s.uuid).toArray()
    for (const se of ses) {
      const sets = (await db.set.where('session_exercise_uuid').equals(se.uuid).toArray())
        .filter(isWorkingSet)
      for (const st of sets) {
        const day = s.started_at.slice(0, 10)
        acc[day] = (acc[day] || 0) + st.weight_kg * st.reps
      }
    }
  }
  return acc
}

// ---------------------------------------------------------------------------
// Routes
// ---------------------------------------------------------------------------

export const workoutRoutes = [
  // ---- Exercises ----
  {
    method: 'GET', pattern: /^\/api\/exercises$/,
    handler: async (_m, query) => {
      let rows = await db.exercise.toArray()
      const search = query.get('search')
      const muscle = query.get('muscle')
      if (search) rows = rows.filter(e => e.name.toLowerCase().includes(search.toLowerCase()))
      if (muscle) rows = rows.filter(e => (e.primary_muscle || '').toLowerCase().includes(muscle.toLowerCase()))
      return rows.sort((a, b) => a.name.localeCompare(b.name)).map(presentExercise)
    },
  },
  {
    method: 'POST', pattern: /^\/api\/exercises$/,
    handler: async (_m, _q, body) => {
      const clash = await db.exercise.where('name').equals(body.name).first()
      if (clash) throw new LocalApiError(409, 'Exercise name already exists')
      const row = stamp({
        uuid: newUuid(), name: body.name,
        primary_muscle: body.primary_muscle ?? null,
        // Auto-tag so custom exercises feed the Ranks map — mirrors exercises.py
        primary_muscle_group: body.primary_muscle_group
          || suggestMuscleGroup(body.name, body.primary_muscle),
        secondary_muscles: body.secondary_muscles || [],
        equipment: body.equipment ?? null, notes: body.notes ?? null,
        is_custom: body.is_custom ?? true,
      })
      await db.exercise.put(row)
      return presentExercise(row)
    },
  },
  {
    method: 'GET', pattern: /^\/api\/exercises\/([^/]+)$/,
    handler: async (m) => presentExercise(await exerciseByUuid(m[1])),
  },
  {
    method: 'PUT', pattern: /^\/api\/exercises\/([^/]+)$/,
    handler: async (m, _q, body) => {
      const ex = await exerciseByUuid(m[1])
      const row = stamp({ ...ex, ...Object.fromEntries(
        Object.entries(body).filter(([, v]) => v !== undefined)
      ) })
      await db.exercise.put(row)
      return presentExercise(row)
    },
  },
  {
    method: 'DELETE', pattern: /^\/api\/exercises\/([^/]+)$/,
    handler: async (m) => {
      const ex = await exerciseByUuid(m[1])
      if (!ex.is_custom) throw new LocalApiError(403, 'Cannot delete built-in exercises')
      await db.exercise.delete(m[1])
      return null
    },
  },

  // ---- Routines ----
  {
    method: 'GET', pattern: /^\/api\/routines$/,
    handler: async () => {
      const rows = await db.routine.toArray()
      rows.sort((a, b) => a.name.localeCompare(b.name))
      return Promise.all(rows.map(presentRoutine))
    },
  },
  {
    method: 'POST', pattern: /^\/api\/routines$/,
    handler: async (_m, _q, body) => {
      const routine = stamp({
        uuid: newUuid(), name: body.name, source: 'manual', notes: body.notes ?? null,
        created_at: nowIso(),
      })
      await db.routine.put(routine)
      for (const def of body.exercises || []) {
        await exerciseByUuid(def.exercise_id)   // validate like the backend
        await db.routine_exercise.put(stamp({
          uuid: newUuid(), routine_uuid: routine.uuid, exercise_uuid: def.exercise_id,
          position: def.position, target_sets: def.target_sets ?? 3,
          target_rep_low: def.target_rep_low ?? 8, target_rep_high: def.target_rep_high ?? 12,
          rest_seconds: def.rest_seconds ?? 120,
        }))
      }
      return presentRoutine(routine)
    },
  },
  {
    method: 'GET', pattern: /^\/api\/routines\/([^/]+)$/,
    handler: async (m) => {
      const r = await db.routine.get(m[1])
      if (!r) throw notFound('Routine')
      return presentRoutine(r)
    },
  },
  {
    method: 'PUT', pattern: /^\/api\/routines\/([^/]+)$/,
    handler: async (m, _q, body) => {
      const r = await db.routine.get(m[1])
      if (!r) throw notFound('Routine')
      const row = stamp({
        ...r,
        name: body.name ?? r.name,
        notes: body.notes !== undefined && body.notes !== null ? body.notes : r.notes,
      })
      await db.routine.put(row)
      if (body.exercises != null) {
        // Replace semantics, like _build_routine_exercises
        await db.routine_exercise.where('routine_uuid').equals(m[1]).delete()
        for (const def of body.exercises) {
          await exerciseByUuid(def.exercise_id)
          await db.routine_exercise.put(stamp({
            uuid: newUuid(), routine_uuid: m[1], exercise_uuid: def.exercise_id,
            position: def.position, target_sets: def.target_sets ?? 3,
            target_rep_low: def.target_rep_low ?? 8, target_rep_high: def.target_rep_high ?? 12,
            rest_seconds: def.rest_seconds ?? 120,
          }))
        }
      }
      return presentRoutine(row)
    },
  },
  {
    method: 'DELETE', pattern: /^\/api\/routines\/([^/]+)$/,
    handler: async (m) => {
      const r = await db.routine.get(m[1])
      if (!r) throw notFound('Routine')
      await db.routine_exercise.where('routine_uuid').equals(m[1]).delete()
      await db.routine.delete(m[1])
      return null
    },
  },

  // ---- Sessions ----
  {
    method: 'GET', pattern: /^\/api\/sessions\/active$/,
    handler: async () => {
      const open = (await db.session.toArray()).filter(s => !s.ended_at)
      if (open.length === 0) return null
      open.sort((a, b) => (a.started_at < b.started_at ? 1 : -1))
      return presentSession(open[0])
    },
  },
  {
    method: 'POST', pattern: /^\/api\/sessions$/,
    handler: async (_m, _q, body) => {
      const session = stamp({
        uuid: newUuid(), name: body.name, routine_uuid: body.routine_id ?? null,
        started_at: nowIso(), ended_at: null, notes: body.notes ?? null,
      })
      if (body.routine_id) {
        const routine = await db.routine.get(body.routine_id)
        if (!routine) throw notFound('Routine')
        await db.session.put(session)
        const res = await db.routine_exercise.where('routine_uuid').equals(routine.uuid).toArray()
        for (const re of res.sort((a, b) => a.position - b.position)) {
          const se = stamp({
            uuid: newUuid(), session_uuid: session.uuid,
            exercise_uuid: re.exercise_uuid, position: re.position,
          })
          await db.session_exercise.put(se)
          for (let i = 1; i <= re.target_sets; i++) {
            await db.set.put(stamp({
              uuid: newUuid(), session_exercise_uuid: se.uuid, set_number: i,
              weight_kg: 0.0, reps: 0, rpe: null,
              is_warmup: false, is_completed: false, completed_at: null,
            }))
          }
        }
        // Surface any pending next-session notes for this routine, once.
        await consumePendingNotes(routine.uuid, session.uuid)
      } else {
        await db.session.put(session)
      }
      return presentSession(session)
    },
  },
  {
    method: 'GET', pattern: /^\/api\/sessions$/,
    handler: async (_m, query) => {
      const rows = await db.session.toArray()
      rows.sort((a, b) => (a.started_at < b.started_at ? 1 : -1))
      const offset = Number(query.get('offset') || 0)
      const limit = Number(query.get('limit') || 50)
      return rows.slice(offset, offset + limit).map(presentSessionSummary)
    },
  },
  {
    method: 'GET', pattern: /^\/api\/sessions\/([^/]+)\/previous-sets\/([^/]+)$/,
    handler: async (m) => {
      const [sessionUuid, exerciseUuid] = [m[1], m[2]]
      if (!(await db.session.get(sessionUuid))) throw notFound('Session')
      const ses = await db.session_exercise.where('exercise_uuid').equals(exerciseUuid).toArray()
      const candidates = []
      for (const se of ses) {
        if (se.session_uuid === sessionUuid) continue
        const s = await db.session.get(se.session_uuid)
        if (s && s.ended_at) candidates.push({ se, started_at: s.started_at })
      }
      if (candidates.length === 0) return []
      candidates.sort((a, b) => (a.started_at < b.started_at ? 1 : -1))
      const sets = await db.set.where('session_exercise_uuid').equals(candidates[0].se.uuid).toArray()
      return sets.sort((a, b) => a.set_number - b.set_number).map(presentSet)
    },
  },
  {
    method: 'GET', pattern: /^\/api\/sessions\/([^/]+)$/,
    handler: async (m) => {
      const s = await db.session.get(m[1])
      if (!s) throw notFound('Session')
      return presentSession(s)
    },
  },
  {
    method: 'PATCH', pattern: /^\/api\/sessions\/([^/]+)$/,
    handler: async (m, _q, body) => {
      const s = await db.session.get(m[1])
      if (!s) throw notFound('Session')
      const row = stamp({ ...s, ...Object.fromEntries(
        Object.entries(body).filter(([, v]) => v !== undefined)
      ) })
      row.ended_at = naiveIso(row.ended_at)
      await db.session.put(row)
      return presentSession(row)
    },
  },
  {
    method: 'DELETE', pattern: /^\/api\/sessions\/([^/]+)$/,
    handler: async (m) => {
      const s = await db.session.get(m[1])
      if (!s) throw notFound('Session')
      const ses = await db.session_exercise.where('session_uuid').equals(m[1]).toArray()
      for (const se of ses) await db.set.where('session_exercise_uuid').equals(se.uuid).delete()
      await db.session_exercise.where('session_uuid').equals(m[1]).delete()
      await db.session.delete(m[1])
      return null
    },
  },

  // ---- Session exercises + sets ----
  {
    method: 'POST', pattern: /^\/api\/sessions\/([^/]+)\/exercises$/,
    handler: async (m, _q, body) => {
      if (!(await db.session.get(m[1]))) throw notFound('Session')
      await exerciseByUuid(body.exercise_id)
      const se = stamp({
        uuid: newUuid(), session_uuid: m[1],
        exercise_uuid: body.exercise_id, position: body.position,
      })
      await db.session_exercise.put(se)
      for (const sd of body.sets || []) {
        await db.set.put(stamp({
          uuid: newUuid(), session_exercise_uuid: se.uuid,
          set_number: sd.set_number, weight_kg: sd.weight_kg ?? 0, reps: sd.reps ?? 0,
          rpe: sd.rpe ?? null, is_warmup: sd.is_warmup ?? false,
          is_completed: sd.is_completed ?? false, completed_at: null,
        }))
      }
      return presentSessionExercise(se)
    },
  },
  {
    method: 'DELETE', pattern: /^\/api\/sessions\/([^/]+)\/exercises\/([^/]+)$/,
    handler: async (m) => {
      const se = await db.session_exercise.get(m[2])
      if (!se || se.session_uuid !== m[1]) throw notFound('Session exercise')
      await db.set.where('session_exercise_uuid').equals(m[2]).delete()
      await db.session_exercise.delete(m[2])
      return null
    },
  },
  {
    method: 'POST', pattern: /^\/api\/sessions\/([^/]+)\/exercises\/([^/]+)\/sets$/,
    handler: async (m, _q, body) => {
      const se = await db.session_exercise.get(m[2])
      if (!se || se.session_uuid !== m[1]) throw notFound('Session exercise')
      const row = stamp({
        uuid: newUuid(), session_exercise_uuid: m[2],
        set_number: body.set_number, weight_kg: body.weight_kg ?? 0, reps: body.reps ?? 0,
        rpe: body.rpe ?? null, is_warmup: body.is_warmup ?? false,
        is_completed: body.is_completed ?? false, completed_at: null,
      })
      await db.set.put(row)
      return presentSet(row)
    },
  },
  {
    method: 'PATCH', pattern: /^\/api\/sessions\/([^/]+)\/exercises\/([^/]+)\/sets\/([^/]+)$/,
    handler: async (m, _q, body) => {
      const s = await db.set.get(m[3])
      if (!s || s.session_exercise_uuid !== m[2]) throw notFound('Set')
      const row = stamp({ ...s, ...Object.fromEntries(
        Object.entries(body).filter(([, v]) => v !== undefined)
      ) })
      row.completed_at = naiveIso(row.completed_at)
      // Auto-set completed_at when marking complete — mirrors update_set
      if (body.is_completed && !row.completed_at) row.completed_at = nowIso()
      await db.set.put(row)
      return presentSet(row)
    },
  },
  {
    method: 'DELETE', pattern: /^\/api\/sessions\/([^/]+)\/exercises\/([^/]+)\/sets\/([^/]+)$/,
    handler: async (m) => {
      const s = await db.set.get(m[3])
      if (!s || s.session_exercise_uuid !== m[2]) throw notFound('Set')
      await db.set.delete(m[3])
      return null
    },
  },

  // ---- Stats ----
  {
    method: 'GET', pattern: /^\/api\/stats\/session\/([^/]+)\/summary$/,
    handler: async (m) => sessionSummary(m[1]),
  },
  {
    method: 'GET', pattern: /^\/api\/stats\/prs$/,
    handler: async () => {
      const ses = await db.session_exercise.toArray()
      const ids = [...new Set(ses.map(se => se.exercise_uuid))]
      const prs = (await Promise.all(ids.map(computePrsForExercise))).filter(Boolean)
      return prs.sort((a, b) => a.exercise_name.localeCompare(b.exercise_name))
    },
  },
  {
    method: 'GET', pattern: /^\/api\/stats\/prs\/([^/]+)$/,
    handler: async (m) => computePrsForExercise(m[1]),
  },
  {
    method: 'GET', pattern: /^\/api\/stats\/exercise\/([^/]+)\/history$/,
    handler: async (m) => {
      const ses = await db.session_exercise.where('exercise_uuid').equals(m[1]).toArray()
      const bySession = new Map()
      for (const se of ses) {
        const sets = (await db.set.where('session_exercise_uuid').equals(se.uuid).toArray())
          .filter(isWorkingSet)
        if (sets.length === 0) continue
        const session = await db.session.get(se.session_uuid)
        if (!session) continue
        if (!bySession.has(session.uuid)) {
          bySession.set(session.uuid, { started_at: session.started_at, sets: [] })
        }
        bySession.get(session.uuid).sets.push(...sets)
      }
      const history = [...bySession.entries()].map(([sid, data]) => ({
        session_id: sid,
        date: data.started_at.slice(0, 10),
        estimated_1rm: round(Math.max(...data.sets.map(s => epley1rm(s.weight_kg, s.reps))), 1),
        volume_kg: round(data.sets.reduce((a, s) => a + s.weight_kg * s.reps, 0), 1),
      }))
      return history.sort((a, b) => (a.date < b.date ? -1 : 1))
    },
  },
  {
    method: 'GET', pattern: /^\/api\/stats\/volume\/weekly$/,
    handler: async (_m, query) => {
      const weeks = Number(query.get('weeks') || 8)
      const since = new Date(Date.now() - weeks * 7 * 86400000).toISOString()
      const sessions = (await db.session.toArray()).filter(s => s.started_at >= since.replace('Z', ''))
      const byWeek = {}
      for (const s of sessions) {
        const ses = await db.session_exercise.where('session_uuid').equals(s.uuid).toArray()
        for (const se of ses) {
          const sets = (await db.set.where('session_exercise_uuid').equals(se.uuid).toArray())
            .filter(isWorkingSet)
          for (const st of sets) {
            const key = isoWeekKey(s.started_at)
            byWeek[key] = (byWeek[key] || 0) + st.weight_kg * st.reps
          }
        }
      }
      return Object.entries(byWeek).sort(([a], [b]) => a.localeCompare(b))
        .map(([week, v]) => ({ week, volume_kg: round(v, 1) }))
    },
  },

  // ---- Sets-per-week per primary muscle group (mirrors stats.py) ----
  {
    method: 'GET', pattern: /^\/api\/stats\/volume-targets$/,
    handler: async () => {
      const settings = (await db.settings.get(1)) || {}
      const targets = resolvedVolumeTargets(settings.volume_targets)
      return Object.fromEntries(Object.entries(targets).map(([m, [lo, hi]]) => [m, { low: lo, high: hi }]))
    },
  },
  {
    method: 'GET', pattern: /^\/api\/stats\/sets-per-week$/,
    handler: async (_m, query) => {
      const weeks = Math.min(52, Math.max(1, Number(query.get('weeks') || 8)))
      const today = todayIso()
      const currentWeek = isoWeekStart(today)
      const firstWeek = addDays(currentWeek, -7 * (weeks - 1))

      // Completed working sets (not warm-ups) joined to session date + muscle group.
      const [sets, ses, sessions, exercises] = await Promise.all([
        db.set.toArray(), db.session_exercise.toArray(),
        db.session.toArray(), db.exercise.toArray(),
      ])
      const seMap = new Map(ses.map(s => [s.uuid, s]))
      const sessMap = new Map(sessions.map(s => [s.uuid, s]))
      const exMap = new Map(exercises.map(e => [e.uuid, e]))

      const counts = {}   // `${weekStart}|${group}` -> count
      for (const st of sets) {
        if (!(st.is_completed && !st.is_warmup)) continue
        const se = seMap.get(st.session_exercise_uuid); if (!se) continue
        const sess = sessMap.get(se.session_uuid); if (!sess) continue
        const d = sess.started_at.slice(0, 10)
        if (d < firstWeek) continue
        const grp = exMap.get(se.exercise_uuid)?.primary_muscle_group
        if (!grp) continue
        const key = `${isoWeekStart(d)}|${grp}`
        counts[key] = (counts[key] || 0) + 1
      }

      const settings = (await db.settings.get(1)) || {}
      const targets = resolvedVolumeTargets(settings.volume_targets)
      const weekStarts = Array.from({ length: weeks }, (_, i) => addDays(firstWeek, 7 * i))
      return {
        muscle_groups: MUSCLE_GROUPS,
        targets: Object.fromEntries(Object.entries(targets).map(([m, [lo, hi]]) => [m, { low: lo, high: hi }])),
        weeks: weekStarts.map(wk => ({
          week_start: wk,
          is_current: wk === currentWeek,
          counts: Object.fromEntries(MUSCLE_GROUPS.map(m => [m, counts[`${wk}|${m}`] || 0])),
        })),
      }
    },
  },
]

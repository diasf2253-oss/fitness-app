/**
 * Training streak, local-first — mirrors backend app/streak.py + routers/streak.py.
 *
 * A workout day is any calendar date with at least one completed working set
 * (completed, non-warm-up). The chain survives up to `rest_gap` rest days and
 * breaks when a larger gap passes. Computed over IndexedDB; no persisted
 * snapshot (each device derives it), so `longest` is the longest chain in
 * history under the current gap.
 */
import { db } from '../db'
import { todayIso } from './util'

const DEFAULT_REST_GAP = 1

// Whole-day difference between two 'YYYY-MM-DD' strings (b - a).
function dayDiff(a, b) {
  return Math.round((Date.parse(b + 'T00:00:00Z') - Date.parse(a + 'T00:00:00Z')) / 86400000)
}

// Working set = completed, non-warm-up, real load — mirrors isWorkingSet /
// the streak router's completed-working-set filter.
async function workoutDates() {
  const days = new Set()
  const sets = await db.set.toArray()
  const workingSeUuids = new Set(
    sets.filter(s => s.is_completed && !s.is_warmup).map(s => s.session_exercise_uuid)
  )
  if (workingSeUuids.size === 0) return days
  const ses = await db.session_exercise.toArray()
  const workingSessionUuids = new Set(
    ses.filter(se => workingSeUuids.has(se.uuid)).map(se => se.session_uuid)
  )
  for (const s of await db.session.toArray()) {
    if (workingSessionUuids.has(s.uuid)) days.add(s.started_at.slice(0, 10))
  }
  return days
}

// Pure port of app/streak.py compute_streak.
export function computeStreak(dates, restGap = DEFAULT_REST_GAP, today = null) {
  const t = today || todayIso()
  const days = [...new Set(dates)].sort()
  if (days.length === 0) {
    return { current: 0, longest: 0, last_workout_date: null, alive: false, at_risk: false }
  }

  const maxApart = restGap + 1

  let longest = 1
  let chain = 1
  for (let i = 1; i < days.length; i++) {
    chain = dayDiff(days[i - 1], days[i]) <= maxApart ? chain + 1 : 1
    longest = Math.max(longest, chain)
  }

  let currentChain = 1
  let i = days.length - 1
  while (i > 0 && dayDiff(days[i - 1], days[i]) <= maxApart) {
    currentChain += 1
    i -= 1
  }

  const last = days[days.length - 1]
  const elapsed = dayDiff(last, t)
  const alive = elapsed <= maxApart
  return {
    current: alive ? currentChain : 0,
    longest,
    last_workout_date: last,
    alive,
    at_risk: alive && elapsed === maxApart,
  }
}

/** Current streak snapshot — shared by GET /api/streak and the report/dashboard. */
export async function streakSnapshot() {
  const settings = await db.settings.get(1)
  const restGap = settings?.streak_rest_gap ?? DEFAULT_REST_GAP
  const r = computeStreak(await workoutDates(), restGap)
  return { ...r, rest_gap: restGap }
}

export const streakRoutes = [
  { method: 'GET', pattern: /^\/api\/streak$/, handler: () => streakSnapshot() },
]

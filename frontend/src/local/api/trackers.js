/**
 * Trackers domain, local-first (P4) — mirrors backend/app/routers/trackers.py:
 * daily check-in list with today's values and habit streaks, CRUD, and the
 * clear-on-null log semantics.
 */
import { db, newUuid, nowIso } from '../db'
import { LocalApiError, addDays, notFound, todayIso } from './util'

const TRACKER_KINDS = ['habit', 'scale', 'number', 'text']

const stamp = (row) => ({ ...row, updated_at: nowIso(), _dirty: 1 })

const presentTracker = (t, extra = {}) => ({
  id: t.uuid, name: t.name, kind: t.kind, unit: t.unit ?? null,
  position: t.position, is_archived: !!t.is_archived,
  today: null, streak: null, ...extra,
})

const presentLog = (l) => ({
  date: l.date, value_num: l.value_num ?? null, value_text: l.value_text ?? null,
})

async function trackerByUuid(uuid) {
  const t = await db.tracker.get(uuid)
  if (!t) throw notFound('Tracker')
  return t
}

/** Mirrors trackers.habit_streak: unlogged today doesn't break the streak. */
export function habitStreak(doneDates, today) {
  let streak = 0
  let d = today
  if (!doneDates.has(d)) d = addDays(d, -1)
  while (doneDates.has(d)) {
    streak += 1
    d = addDays(d, -1)
  }
  return streak
}

function sortTrackers(rows) {
  // Backend orders by (position, id); uuid is the stable local tiebreaker
  return rows.sort((a, b) => a.position - b.position || a.uuid.localeCompare(b.uuid))
}

export const trackerRoutes = [
  {
    method: 'GET', pattern: /^\/api\/trackers$/,
    handler: async (_m, query) => {
      let rows = await db.tracker.toArray()
      if (query.get('include_archived') !== 'true') rows = rows.filter(t => !t.is_archived)
      sortTrackers(rows)

      const today = todayIso()
      return Promise.all(rows.map(async (t) => {
        const log = await db.tracker_log.get({ tracker_uuid: t.uuid, date: today })
        const extra = { today: log ? presentLog(log) : null }
        if (t.kind === 'habit') {
          const done = new Set(
            (await db.tracker_log.where('tracker_uuid').equals(t.uuid).toArray())
              .filter(l => l.value_num != null && l.value_num >= 1)
              .map(l => l.date)
          )
          extra.streak = habitStreak(done, today)
        }
        return presentTracker(t, extra)
      }))
    },
  },
  {
    method: 'POST', pattern: /^\/api\/trackers$/,
    handler: async (_m, _q, body) => {
      if (!TRACKER_KINDS.includes(body.kind)) {
        throw new LocalApiError(422, `kind must be one of ${TRACKER_KINDS.join(', ')}`)
      }
      if (!body.name?.trim()) throw new LocalApiError(422, 'name is required')
      const all = await db.tracker.toArray()
      const row = stamp({
        uuid: newUuid(), name: body.name.trim(), kind: body.kind,
        unit: body.unit ?? null,
        position: all.length ? Math.max(...all.map(t => t.position)) + 1 : 0,
        is_archived: false, created_at: nowIso(),
      })
      await db.tracker.put(row)
      return presentTracker(row)
    },
  },
  {
    method: 'PATCH', pattern: /^\/api\/trackers\/([^/]+)$/,
    handler: async (m, _q, body) => {
      const t = await trackerByUuid(m[1])
      const row = stamp({ ...t, ...Object.fromEntries(
        Object.entries(body).filter(([, v]) => v !== undefined)
      ) })
      await db.tracker.put(row)
      return presentTracker(row)
    },
  },
  {
    method: 'DELETE', pattern: /^\/api\/trackers\/([^/]+)$/,
    handler: async (m) => {
      await trackerByUuid(m[1])
      await db.tracker_log.where('tracker_uuid').equals(m[1]).delete()
      await db.tracker.delete(m[1])
      return null
    },
  },
  {
    method: 'POST', pattern: /^\/api\/trackers\/([^/]+)\/log$/,
    handler: async (m, _q, body) => {
      await trackerByUuid(m[1])
      const existing = await db.tracker_log.get({ tracker_uuid: m[1], date: body.date })
      const text = body.value_text?.trim() || null

      // Null values clear the day — mirrors log_tracker
      if (body.value_num == null && !text) {
        if (existing) await db.tracker_log.delete(existing.uuid)
        return null
      }

      const row = stamp({
        ...(existing || { uuid: newUuid(), tracker_uuid: m[1], date: body.date }),
        value_num: body.value_num ?? null,
        value_text: text,
      })
      await db.tracker_log.put(row)
      return presentLog(row)
    },
  },
  {
    method: 'GET', pattern: /^\/api\/trackers\/([^/]+)\/series$/,
    handler: async (m, query) => {
      await trackerByUuid(m[1])
      const since = addDays(todayIso(), -Number(query.get('days') || 90))
      const rows = (await db.tracker_log.where('tracker_uuid').equals(m[1]).toArray())
        .filter(l => l.date >= since)
        .sort((a, b) => (a.date < b.date ? -1 : 1))
      return rows.map(presentLog)
    },
  },
]

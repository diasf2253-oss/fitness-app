/**
 * Plan items, local-first (P4) — mirrors backend/app/routers/plan.py.
 * (Coach *proposals* stay online-only; checking off and hand-editing the
 * plan works fully offline.)
 */
import { db, newUuid, nowIso } from '../db'
import { LocalApiError, notFound } from './util'

const PLAN_CATEGORIES = ['workout', 'study', 'task', 'meal', 'other']

const stamp = (row) => ({ ...row, updated_at: nowIso(), _dirty: 1 })

const present = (p) => ({
  id: p.uuid, date: p.date, start_time: p.start_time ?? null,
  end_time: p.end_time ?? null, title: p.title, category: p.category,
  notes: p.notes ?? null, is_done: !!p.is_done, position: p.position,
  source: p.source,
})

function ordered(rows) {
  // Mirrors: ORDER BY position, start_time, id
  return rows.sort((a, b) =>
    a.position - b.position
    || (a.start_time || '').localeCompare(b.start_time || '')
    || a.uuid.localeCompare(b.uuid))
}

export const planRoutes = [
  {
    method: 'GET', pattern: /^\/api\/plan\/(\d{4}-\d{2}-\d{2})$/,
    handler: async (m) =>
      ordered(await db.plan_item.where('date').equals(m[1]).toArray()).map(present),
  },
  {
    method: 'POST', pattern: /^\/api\/plan\/(\d{4}-\d{2}-\d{2})\/items$/,
    handler: async (m, _q, body) => {
      if (!body.title?.trim()) throw new LocalApiError(422, 'title is required')
      const sameDay = await db.plan_item.where('date').equals(m[1]).toArray()
      const row = stamp({
        uuid: newUuid(), date: m[1], title: body.title.trim(),
        start_time: body.start_time || null, end_time: body.end_time || null,
        category: PLAN_CATEGORIES.includes(body.category) ? body.category : 'task',
        notes: body.notes?.trim() || null,
        position: sameDay.length ? Math.max(...sameDay.map(p => p.position)) + 1 : 0,
        is_done: false, source: body.source || 'manual',
      })
      await db.plan_item.put(row)
      return present(row)
    },
  },
  {
    method: 'PATCH', pattern: /^\/api\/plan\/items\/([^/]+)$/,
    handler: async (m, _q, body) => {
      const item = await db.plan_item.get(m[1])
      if (!item) throw notFound('Plan item')
      const data = Object.fromEntries(Object.entries(body).filter(([, v]) => v !== undefined))
      if ('category' in data && !PLAN_CATEGORIES.includes(data.category)) delete data.category
      const row = stamp({ ...item, ...data })
      await db.plan_item.put(row)
      return present(row)
    },
  },
  {
    method: 'DELETE', pattern: /^\/api\/plan\/items\/([^/]+)$/,
    handler: async (m) => {
      const item = await db.plan_item.get(m[1])
      if (!item) throw notFound('Plan item')
      await db.plan_item.delete(m[1])
      return null
    },
  },
]

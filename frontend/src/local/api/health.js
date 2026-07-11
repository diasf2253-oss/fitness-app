/**
 * Health domain, local-first (P4) — mirrors backend/app/routers/health.py
 * and nutrition.py: date-keyed upserts with source precedence, plus the
 * weight estimate endpoint (math lives in ../weights.js).
 */
import { db, nowIso } from '../db'
import { weightEstimateFor, writeBlocked } from '../weights'
import { addDays, todayIso } from './util'

async function rangeRows(table, days) {
  const since = addDays(todayIso(), -days)
  const rows = await db.table(table).where('date').aboveOrEqual(since).toArray()
  return rows.sort((a, b) => (a.date < b.date ? -1 : 1))
}

// Presenter: local row → API shape (id carries the date in local mode)
const present = ({ _dirty, ...row }) => ({ id: row.date, ...row })

/**
 * Generic date-keyed upsert honoring source precedence — the local twin of
 * the upsert helpers in routers/health.py. Returns the stored row or the
 * existing one when the write is blocked (matching backend behavior).
 */
async function upsertByDate(table, dateIso, fields, source) {
  const existing = await db.table(table).get(dateIso)
  if (existing && writeBlocked(existing, source)) return existing
  const row = {
    ...(existing || {}),
    date: dateIso,
    ...fields,
    source,
    updated_at: nowIso(),
    _dirty: 1,
  }
  await db.table(table).put(row)
  return row
}

export const healthRoutes = [
  {
    method: 'GET', pattern: /^\/api\/health\/weight\/estimate$/,
    handler: async (_m, query) => weightEstimateFor(query.get('date')),
  },
  {
    method: 'GET', pattern: /^\/api\/health\/weight$/,
    handler: async (_m, query) =>
      (await rangeRows('weight_log', Number(query.get('days') || 90))).map(present),
  },
  {
    method: 'POST', pattern: /^\/api\/health\/weight$/,
    handler: async (_m, _q, body) => present(await upsertByDate(
      'weight_log', body.date, { weight_kg: body.weight_kg }, body.source || 'manual',
    )),
  },
  {
    method: 'GET', pattern: /^\/api\/health\/steps$/,
    handler: async (_m, query) =>
      (await rangeRows('steps_log', Number(query.get('days') || 14))).map(present),
  },
  {
    method: 'POST', pattern: /^\/api\/health\/steps$/,
    handler: async (_m, _q, body) => present(await upsertByDate(
      'steps_log', body.date, { steps: body.steps }, body.source || 'manual',
    )),
  },
  {
    method: 'GET', pattern: /^\/api\/health\/sleep$/,
    handler: async (_m, query) =>
      (await rangeRows('sleep_log', Number(query.get('days') || 14))).map(present),
  },
  {
    method: 'POST', pattern: /^\/api\/health\/sleep$/,
    handler: async (_m, _q, body) => present(await upsertByDate(
      'sleep_log', body.date,
      {
        asleep_minutes: body.asleep_minutes,
        in_bed_minutes: body.in_bed_minutes,
        deep_minutes: body.deep_minutes ?? null,
        rem_minutes: body.rem_minutes ?? null,
        core_minutes: body.core_minutes ?? null,
      },
      body.source || 'manual',
    )),
  },
  {
    method: 'GET', pattern: /^\/api\/(health\/)?nutrition$/,
    handler: async (_m, query) =>
      (await rangeRows('nutrition_day', Number(query.get('days') || 30))).map(present),
  },
  {
    method: 'POST', pattern: /^\/api\/nutrition$/,
    handler: async (_m, _q, body) => {
      // Mirrors nutrition.upsert_nutrition: micros only replace when provided
      const existing = await db.nutrition_day.get(body.date)
      const fields = {
        calories: body.calories, protein_g: body.protein_g,
        carbs_g: body.carbs_g, fat_g: body.fat_g,
        micros: body.micros != null ? body.micros : (existing?.micros ?? null),
      }
      return present(await upsertByDate('nutrition_day', body.date, fields, body.source || 'manual'))
    },
  },
]

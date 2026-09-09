/**
 * Health domain, local-first (P4) — mirrors backend/app/routers/health.py
 * and nutrition.py: date-keyed upserts with source precedence, plus the
 * weight estimate endpoint (math lives in ../weights.js).
 */
import { db, nowIso } from '../db'
import { dayDiff, DERIVED_SOURCES, weightEstimateFor, writeBlocked } from '../weights'
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

/**
 * Newest REAL reading date in a set of health rows, or null.
 *
 * "Real" excludes DERIVED_SOURCES (our own interpolated weights, demo seed
 * rows). The whole point of sync-status is to say whether the phone is
 * actually pushing, so a chart full of estimates must never be able to
 * report itself as up to date.
 */
export function lastRealDate(rows) {
  let best = null
  for (const r of rows) {
    if (DERIVED_SOURCES.includes(r.source)) continue
    if (best === null || r.date > best) best = r.date
  }
  return best
}

/**
 * Pure twin of routers/health.py's health_sync_status. Kept separate from
 * the Dexie read so the parity tests can drive it with plain arrays.
 *
 * `rows` is { weight, steps, sleep, nutrition } → arrays of health rows.
 */
export function buildSyncStatus(rows, today, lastIngest = null) {
  const metrics = {}
  for (const name of ['weight', 'steps', 'sleep', 'nutrition']) {
    const last = lastRealDate(rows[name] || [])
    metrics[name] = {
      last_date: last,
      days_stale: last ? dayDiff(last, today) : null,
    }
  }
  const seen = Object.values(metrics)
    .map(m => m.days_stale)
    .filter(d => d !== null)
  return {
    last_ingest: lastIngest,
    stalest_days: seen.length ? Math.max(...seen) : null,
    has_any_data: seen.length > 0,
    ...metrics,
  }
}

export const healthRoutes = [
  {
    // Twin of routers/health.py's health_sync_status. Needed locally because
    // production builds are local-first: without it the installed PWA would
    // hit the network for this on every page and fail when offline.
    //
    // `last_ingest` is always null here: sync.py deliberately excludes
    // settings.health_last_ingest from the sync payload, so the local row
    // never carries it. The per-metric `days_stale` values are the real
    // signal anyway — they're computed from rows that DID sync down.
    method: 'GET', pattern: /^\/api\/health\/sync-status$/,
    handler: async () => {
      const [weight, steps, sleep, nutrition] = await Promise.all([
        db.weight_log.toArray(), db.steps_log.toArray(),
        db.sleep_log.toArray(), db.nutrition_day.toArray(),
      ])
      const settings = await db.settings.get(1)
      return buildSyncStatus(
        { weight, steps, sleep, nutrition },
        todayIso(),
        settings?.health_last_ingest ?? null,
      )
    },
  },
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

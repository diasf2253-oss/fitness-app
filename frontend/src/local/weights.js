/**
 * Weight domain, local-first (P2) — the on-device port of the backend's
 * weight logic. Sources of truth for the math and rules:
 *   backend/app/routers/health.py    (interpolation, source precedence)
 *   backend/app/routers/dashboard.py (series building, 7-day moving average)
 *
 * Pure functions take plain row arrays so they're unit-testable without
 * IndexedDB; the async functions below them are the Dexie glue the UI uses.
 * Rows: { date: 'YYYY-MM-DD', weight_kg, source, updated_at, _dirty }
 */
import { db } from './db'

// Non-authoritative sources — mirror DERIVED_SOURCES in routers/health.py:
// never used as interpolation basis, never allowed to bury a real reading.
export const DERIVED_SOURCES = ['estimated', 'sample']

const DAY_MS = 86400000

function dayDiff(aIso, bIso) {
  return Math.round((Date.parse(bIso) - Date.parse(aIso)) / DAY_MS)
}

function addDays(iso, n) {
  const d = new Date(iso + 'T00:00:00Z')
  d.setUTCDate(d.getUTCDate() + n)
  return d.toISOString().slice(0, 10)
}

function round1(x) { return Math.round(x * 10) / 10 }

/** Mirror of health._write_blocked: may `source` overwrite the existing row? */
export function writeBlocked(row, source) {
  if (!row) return false
  if (row.source === 'manual' && source !== 'manual') return true
  if (DERIVED_SOURCES.includes(source) && !DERIVED_SOURCES.includes(row.source)) return true
  return false
}

/** Real weigh-ins only, date-ascending — the interpolation basis. */
export function realWeightPoints(rows) {
  return rows
    .filter(r => !DERIVED_SOURCES.includes(r.source))
    .sort((a, b) => (a.date < b.date ? -1 : 1))
}

/**
 * Mirror of health.estimate_weight_for: linear interpolation between the
 * nearest real weigh-ins on either side; carry forward/back at the ends.
 * Returns { kg, method } or null when there's nothing to estimate from.
 */
export function estimateWeightFor(dateIso, points) {
  let prev = null
  let next = null
  for (const p of points) {
    if (p.date < dateIso) prev = p
    else if (p.date > dateIso) { next = p; break }
  }
  if (prev && next) {
    const span = dayDiff(prev.date, next.date)
    const frac = dayDiff(prev.date, dateIso) / span
    return { kg: round1(prev.weight_kg + (next.weight_kg - prev.weight_kg) * frac), method: 'interpolated' }
  }
  if (prev) return { kg: round1(prev.weight_kg), method: 'carried_forward' }
  if (next) return { kg: round1(next.weight_kg), method: 'carried_back' }
  return null
}

/** Mirror of health.resolved_weight_for → { kg, estimated, method } | null. */
export function resolvedWeightFor(dateIso, row, points) {
  if (row && !DERIVED_SOURCES.includes(row.source)) {
    return { kg: row.weight_kg, estimated: false, method: null }
  }
  const est = estimateWeightFor(dateIso, points)
  if (est) return { kg: est.kg, estimated: true, method: est.method }
  if (row) return { kg: row.weight_kg, estimated: false, method: null }
  return null
}

/** Mirror of dashboard.moving_average_7d over [{date, weight_kg}]. */
export function movingAverage7d(series) {
  return series.map((p, i) => {
    const windowStart = addDays(p.date, -6)
    const vals = series.slice(0, i + 1).filter(q => q.date >= windowStart).map(q => q.weight_kg)
    return { date: p.date, avg_kg: Math.round((vals.reduce((a, b) => a + b, 0) / vals.length) * 100) / 100 }
  })
}

/**
 * Mirror of the dashboard weight section: continuous series from the first
 * row in the window to today, real readings as-is, gaps and derived-only
 * days filled with flagged estimates; moving average over real rows only.
 */
export function buildWeightSeries(rows, todayIso, windowDays = 90) {
  const since = addDays(todayIso, -windowDays)
  const inWindow = rows.filter(r => r.date >= since).sort((a, b) => (a.date < b.date ? -1 : 1))
  const byDate = Object.fromEntries(inWindow.map(r => [r.date, r]))
  const basis = realWeightPoints(rows)   // full history anchors window edges
  const realInWindow = realWeightPoints(inWindow)

  const series = []
  if (inWindow.length > 0) {
    const start = inWindow[0].date
    for (let d = start; d <= todayIso; d = addDays(d, 1)) {
      const resolved = resolvedWeightFor(d, byDate[d] || null, basis)
      if (resolved) series.push({ date: d, weight_kg: resolved.kg, estimated: resolved.estimated })
    }
  }
  return { series, moving_avg_7d: movingAverage7d(realInWindow) }
}

// ---------------------------------------------------------------------------
// IndexedDB glue — what the UI calls in local-first mode
// ---------------------------------------------------------------------------

/** Weight to prefill for a date — local mirror of GET /api/health/weight/estimate. */
export async function weightEstimateFor(dateIso) {
  const rows = await db.weight_log.toArray()
  const row = rows.find(r => r.date === dateIso) || null
  const resolved = resolvedWeightFor(dateIso, row, realWeightPoints(rows))
  if (!resolved) return { date: dateIso, weight_kg: null, estimated: false }
  return {
    date: dateIso,
    weight_kg: resolved.kg,
    estimated: resolved.estimated,
    method: resolved.method,
    source: resolved.estimated ? 'estimated' : (row ? row.source : null),
  }
}

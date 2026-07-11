/**
 * Shared helpers for the local API modules (P3/P4).
 *
 * Local rows mirror the sync payload (uuid identity, FK-as-parent-uuid).
 * The REST API the pages speak uses `id` + integer-style FKs. Presenters
 * bridge the two: in local-first mode, `id` fields simply carry uuids —
 * opaque to the components, which only use them for keys and URLs.
 */

export function todayIso() {
  const d = new Date()
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

export function addDays(iso, n) {
  const d = new Date(iso + 'T00:00:00Z')
  d.setUTCDate(d.getUTCDate() + n)
  return d.toISOString().slice(0, 10)
}

export function round(x, digits = 1) {
  const f = 10 ** digits
  return Math.round(x * f) / f
}

/**
 * Normalize a client-supplied datetime to the store's naive-UTC format
 * (no trailing Z) so string comparison and server-side parsing stay
 * consistent. Non-strings and date-only strings pass through.
 */
export function naiveIso(value) {
  return typeof value === 'string' && value.endsWith('Z') ? value.slice(0, -1) : value
}

/** HTTP-ish error the dispatcher surfaces exactly like apiFetch would. */
export class LocalApiError extends Error {
  constructor(status, detail) {
    super(detail)
    this.status = status
  }
}

export function notFound(what) {
  return new LocalApiError(404, `${what} not found`)
}

/** ISO year-week key, e.g. "2026-W28" — mirrors Python isocalendar(). */
export function isoWeekKey(dateTimeIso) {
  const d = new Date(dateTimeIso.slice(0, 10) + 'T00:00:00Z')
  // ISO week: Thursday of the same week decides the year
  const day = (d.getUTCDay() + 6) % 7          // Mon=0 … Sun=6
  const thursday = new Date(d)
  thursday.setUTCDate(d.getUTCDate() - day + 3)
  const jan1 = new Date(Date.UTC(thursday.getUTCFullYear(), 0, 1))
  const week = Math.floor(1 + (thursday - jan1) / (7 * 86400000))
  return `${thursday.getUTCFullYear()}-W${String(week).padStart(2, '0')}`
}

/** Pearson r; null for constant series or n < 2 — mirrors insights.pearson. */
export function pearson(xs, ys) {
  const n = xs.length
  if (n < 2) return null
  const mx = xs.reduce((a, b) => a + b, 0) / n
  const my = ys.reduce((a, b) => a + b, 0) / n
  let cov = 0, vx = 0, vy = 0
  for (let i = 0; i < n; i++) {
    cov += (xs[i] - mx) * (ys[i] - my)
    vx += (xs[i] - mx) ** 2
    vy += (ys[i] - my) ** 2
  }
  if (vx === 0 || vy === 0) return null
  return cov / Math.sqrt(vx * vy)
}

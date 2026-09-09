/**
 * Weekly (ISO-week) weight averaging, local-first — mirrors backend
 * app/weight_trend.py. Single source of truth for the weekly-average chart
 * and the adaptive-calorie engine. Weeks with no entry are omitted (gaps are
 * never interpolated); the week containing `today` is flagged provisional.
 */
import { round } from './util'

/** Monday (ISO) of the week containing an 'YYYY-MM-DD' date. */
export function isoWeekStart(iso) {
  const d = new Date(iso.slice(0, 10) + 'T00:00:00Z')
  const dow = (d.getUTCDay() + 6) % 7   // Mon=0 … Sun=6
  d.setUTCDate(d.getUTCDate() - dow)
  return d.toISOString().slice(0, 10)
}

/**
 * Mean bodyweight per ISO week, ascending. `weightByDate` is a plain object
 * { 'YYYY-MM-DD': kg }. Returns [{ week_start, avg_kg, n_entries,
 * is_current_week }]. Mirrors weight_trend.weekly_averages.
 */
export function weeklyAverages(weightByDate, todayIso) {
  const currentWeek = isoWeekStart(todayIso)
  const buckets = {}
  for (const [d, kg] of Object.entries(weightByDate)) {
    ;(buckets[isoWeekStart(d)] ||= []).push(kg)
  }
  return Object.keys(buckets).sort().map(weekStart => {
    const vals = buckets[weekStart]
    return {
      week_start: weekStart,
      avg_kg: round(vals.reduce((a, b) => a + b, 0) / vals.length, 2),
      n_entries: vals.length,
      is_current_week: weekStart === currentWeek,
    }
  })
}

/**
 * Aggregation endpoints, local-first (P3) — mirrors dashboard.py,
 * calendar.py, insights.py and settings.py, computed over IndexedDB.
 */
import { db, nowIso } from '../db'
import { DERIVED_SOURCES, buildWeightSeries, realWeightPoints, resolvedWeightFor } from '../weights'
import { streakSnapshot } from './streak'
import { weeklyAverages } from './weight_trend'
import { dailyVolume, sessionSummary } from './workout'
import { addDays, pearson, round, todayIso } from './util'

const WINDOW_DAYS = 90
const MIN_PAIR_N = 10
const MIN_SPLIT_N = 5
const MAX_PAIRS = 8
const MAX_RECENT_PRS = 5

const DEFAULT_SETTINGS = {
  id: 1, calorie_target: 2300, protein_target_g: 180, fat_max_g: 100,
  unit_system: 'metric', sex: 'male', rank_config: null, health_last_ingest: null,
  age: 19, onboarded: false,
  goal_kg_per_week: 0.5, adapt_step_kcal: 100, adapt_tolerance_kg: 0.15,
  calorie_floor: 1800, calorie_ceiling: null, last_adapted_week: null,
  volume_targets: null, streak_rest_gap: 1, default_rest_seconds: 120,
  goal_rate_kg_per_week: -0.25, expenditure_kcal: null, calorie_target_set_at: null,
}

async function getSettings() {
  const row = await db.settings.get(1)
  if (!row) return { ...DEFAULT_SETTINGS }
  // Existing installs predate `onboarded` — treat a returning user (row already
  // present) as onboarded so the first-run wizard never ambushes them; only a
  // brand-new install (no settings row at all) starts with onboarded=false.
  return { ...DEFAULT_SETTINGS, ...row, onboarded: row.onboarded ?? true }
}

const dateInRange = (rows, start, end) =>
  rows.filter(r => r.date >= start && r.date <= end)

const avg = (xs) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : null)

// ---------------------------------------------------------------------------
// Dashboard
// ---------------------------------------------------------------------------

async function dashboard() {
  const today = todayIso()

  const weights = await db.weight_log.toArray()
  const weight = buildWeightSeries(weights, today)

  // ISO-week averages (real weigh-ins only) — mirrors weight_trend + the diet trend.
  const weightByDate = Object.fromEntries(
    weights.filter(w => !DERIVED_SOURCES.includes(w.source)).map(w => [w.date, w.weight_kg])
  )
  weight.weekly_avg = weeklyAverages(weightByDate, today).map(w => ({
    week_start: w.week_start, avg_kg: w.avg_kg, n_entries: w.n_entries, provisional: w.is_current_week,
  }))

  const steps = dateInRange(await db.steps_log.toArray(), addDays(today, -14), today)
    .sort((a, b) => (a.date < b.date ? -1 : 1))
    .map(r => ({ date: r.date, steps: r.steps }))

  const sleep = dateInRange(await db.sleep_log.toArray(), addDays(today, -14), today)
    .sort((a, b) => (a.date < b.date ? -1 : 1))
    .map(r => ({ date: r.date, asleep_hours: round(r.asleep_minutes / 60, 1) }))

  const nut = await db.nutrition_day.get(today)
  const nutrition_today = {
    date: today, logged: !!nut,
    calories: nut?.calories ?? 0, protein_g: nut?.protein_g ?? 0,
    carbs_g: nut?.carbs_g ?? 0, fat_g: nut?.fat_g ?? 0,
    micros: nut?.micros || {},
  }

  const s = await getSettings()
  const targets = {
    calorie_target: s.calorie_target, protein_target_g: s.protein_target_g,
    fat_max_g: s.fat_max_g, unit_system: s.unit_system,
  }

  // Training: last 7 days, reusing the session summary like the backend does
  const weekStart = addDays(today, -6)
  const weekSessions = (await db.session.toArray())
    .filter(ws => ws.started_at.slice(0, 10) >= weekStart)
    .sort((a, b) => (a.started_at < b.started_at ? 1 : -1))

  let weekVolume = 0
  const recentPrs = []
  for (const ws of weekSessions) {
    const summary = await sessionSummary(ws.uuid)
    weekVolume += summary.total_volume_kg
    for (const pr of summary.prs_hit) {
      recentPrs.push({ ...pr, date: ws.started_at.slice(0, 10) })
    }
  }

  return {
    weight, steps, sleep, nutrition_today, targets,
    training: {
      week_volume_kg: round(weekVolume, 1),
      sessions_this_week: weekSessions.length,
      recent_prs: recentPrs.slice(0, MAX_RECENT_PRS),
    },
    streak: await streakSnapshot(),
  }
}

// ---------------------------------------------------------------------------
// Calendar + day detail
// ---------------------------------------------------------------------------

async function monthCalendar(year, month) {
  const first = `${year}-${String(month).padStart(2, '0')}-01`
  const last = addDays(`${year}-${String(month).padStart(2, '0')}-` +
    String(new Date(Date.UTC(year, month, 0)).getUTCDate()).padStart(2, '0'), 0)

  const days = {}
  const dayOf = (d) => (days[d] ||= {
    date: d, sessions: 0, steps: null, has_weight: false,
    has_sleep: false, has_nutrition: false, trackers: 0, plan_items: 0,
  })

  for (const s of await db.session.toArray()) {
    const d = s.started_at.slice(0, 10)
    if (d >= first && d <= last) dayOf(d).sessions += 1
  }
  for (const r of dateInRange(await db.weight_log.toArray(), first, last)) {
    // Real weigh-ins only light the dot — mirrors calendar.py
    if (!DERIVED_SOURCES.includes(r.source)) dayOf(r.date).has_weight = true
  }
  for (const r of dateInRange(await db.steps_log.toArray(), first, last)) dayOf(r.date).steps = r.steps
  for (const r of dateInRange(await db.sleep_log.toArray(), first, last)) dayOf(r.date).has_sleep = true
  for (const r of dateInRange(await db.nutrition_day.toArray(), first, last)) dayOf(r.date).has_nutrition = true
  for (const r of dateInRange(await db.tracker_log.toArray(), first, last)) dayOf(r.date).trackers += 1
  for (const r of dateInRange(await db.plan_item.toArray(), first, last)) dayOf(r.date).plan_items += 1

  return {
    year, month,
    days: Object.values(days).sort((a, b) => (a.date < b.date ? -1 : 1)),
  }
}

async function dayDetail(day) {
  const sessions = []
  for (const ws of (await db.session.toArray())
    .filter(s => s.started_at.slice(0, 10) === day)
    .sort((a, b) => (a.started_at < b.started_at ? -1 : 1))) {
    const summary = await sessionSummary(ws.uuid)
    sessions.push({
      id: ws.uuid, name: ws.name,
      duration_minutes: summary.duration_minutes,
      total_volume_kg: summary.total_volume_kg,
      completed_sets: summary.completed_sets,
    })
  }

  const weights = await db.weight_log.toArray()
  const weightRow = weights.find(r => r.date === day) || null
  const resolved = resolvedWeightFor(day, weightRow, realWeightPoints(weights))

  const stepsRow = await db.steps_log.get(day)
  const sleepRow = await db.sleep_log.get(day)
  const nutRow = await db.nutrition_day.get(day)

  const logs = (await db.tracker_log.where('date').equals(day).toArray())
  const trackers = []
  for (const log of logs) {
    const t = await db.tracker.get(log.tracker_uuid)
    if (!t) continue
    trackers.push({
      name: t.name, kind: t.kind, unit: t.unit ?? null,
      value_num: log.value_num ?? null, value_text: log.value_text ?? null,
      _position: t.position,
    })
  }
  trackers.sort((a, b) => a._position - b._position)
  trackers.forEach(t => delete t._position)

  const plan = (await db.plan_item.where('date').equals(day).toArray())
    .sort((a, b) => a.position - b.position
      || (a.start_time || '').localeCompare(b.start_time || ''))
    .map(p => ({
      id: p.uuid, date: p.date, start_time: p.start_time ?? null,
      end_time: p.end_time ?? null, title: p.title, category: p.category,
      notes: p.notes ?? null, is_done: !!p.is_done, position: p.position,
      source: p.source,
    }))

  return {
    date: day,
    sessions,
    weight_kg: resolved ? resolved.kg : null,
    weight_estimated: resolved ? resolved.estimated : false,
    steps: stepsRow?.steps ?? null,
    sleep: sleepRow ? { id: sleepRow.date, ...strip(sleepRow) } : null,
    nutrition: nutRow ? { id: nutRow.date, ...strip(nutRow) } : null,
    trackers,
    plan,
  }
}

const strip = ({ _dirty, ...row }) => row

// ---------------------------------------------------------------------------
// Insights — mirrors insights.py
// ---------------------------------------------------------------------------

async function periodMetrics(start, end) {
  const daysInPeriod = Math.round((Date.parse(end) - Date.parse(start)) / 86400000) + 1

  const steps = dateInRange(await db.steps_log.toArray(), start, end).map(r => r.steps)
  const sleep = dateInRange(await db.sleep_log.toArray(), start, end).map(r => r.asleep_minutes)
  const nut = dateInRange(await db.nutrition_day.toArray(), start, end)
  const weights = dateInRange(await db.weight_log.toArray(), start, end)
    .sort((a, b) => (a.date < b.date ? -1 : 1))

  const volumeByDay = await dailyVolume(start, end)
  const sessions = (await db.session.toArray())
    .filter(s => { const d = s.started_at.slice(0, 10); return d >= start && d <= end })

  const scales = []
  const habits = []
  const trackers = (await db.tracker.toArray()).filter(t => !t.is_archived)
    .sort((a, b) => a.position - b.position || a.uuid.localeCompare(b.uuid))
  for (const t of trackers) {
    const logs = (await db.tracker_log.where('tracker_uuid').equals(t.uuid).toArray())
      .filter(l => l.date >= start && l.date <= end)
    if (t.kind === 'scale') {
      const values = logs.filter(l => l.value_num != null).map(l => l.value_num)
      scales.push({ name: t.name, avg: values.length ? round(avg(values), 1) : null })
    } else if (t.kind === 'habit') {
      habits.push({
        name: t.name,
        done: logs.filter(l => l.value_num != null && l.value_num >= 1).length,
        days: daysInPeriod,
      })
    }
  }

  const stepsAvg = avg(steps)
  const sleepAvg = avg(sleep)
  const calsAvg = avg(nut.map(r => r.calories))
  const protAvg = avg(nut.map(r => r.protein_g))

  return {
    date_from: start, date_to: end,
    volume_kg: round(Object.values(volumeByDay).reduce((a, b) => a + b, 0), 1),
    sessions: sessions.length,
    steps_avg: stepsAvg != null ? Math.round(stepsAvg) : null,
    sleep_avg_h: sleepAvg != null ? round(sleepAvg / 60, 1) : null,
    calories_avg: calsAvg != null ? Math.round(calsAvg) : null,
    protein_avg_g: protAvg != null ? Math.round(protAvg) : null,
    weight_change_kg: weights.length >= 2
      ? round(weights[weights.length - 1].weight_kg - weights[0].weight_kg, 1)
      : null,
    scales, habits,
  }
}

async function correlations() {
  const today = todayIso()
  const start = addDays(today, -(WINDOW_DAYS - 1))

  const toMap = (rows, valueOf) =>
    Object.fromEntries(dateInRange(rows, start, today).map(r => [r.date, valueOf(r)]))

  const series = {
    'Steps': toMap(await db.steps_log.toArray(), r => r.steps),
    'Sleep (h)': toMap(await db.sleep_log.toArray(), r => round(r.asleep_minutes / 60, 2)),
    'Calories': toMap(await db.nutrition_day.toArray(), r => r.calories),
    'Weight (kg)': toMap(await db.weight_log.toArray(), r => r.weight_kg),
  }

  // Volume is zero-filled: rest days count as 0 — mirrors insights.py
  const volumeDays = await dailyVolume(start, today)
  const volume = {}
  for (let i = 0; i < WINDOW_DAYS; i++) {
    const d = addDays(start, i)
    volume[d] = volumeDays[d] || 0
  }
  series['Training volume (kg)'] = volume

  const scaleTrackers = (await db.tracker.toArray())
    .filter(t => t.kind === 'scale' && !t.is_archived)
    .sort((a, b) => a.position - b.position || a.uuid.localeCompare(b.uuid))
  for (const t of scaleTrackers) {
    const logs = (await db.tracker_log.where('tracker_uuid').equals(t.uuid).toArray())
      .filter(l => l.date >= start && l.date <= today && l.value_num != null)
    series[t.name] = Object.fromEntries(logs.map(l => [l.date, l.value_num]))
  }

  const candidatePairs = [
    ['Sleep (h)', 'Training volume (kg)'],
    ['Sleep (h)', 'Steps'],
    ['Steps', 'Calories'],
    ['Calories', 'Weight (kg)'],
  ]
  for (const t of scaleTrackers) {
    candidatePairs.push([t.name, 'Sleep (h)'])
    candidatePairs.push([t.name, 'Training volume (kg)'])
  }

  let pairs = []
  for (const [keyA, keyB] of candidatePairs) {
    const mapA = series[keyA], mapB = series[keyB]
    const shared = Object.keys(mapA).filter(d => d in mapB).sort()
    if (shared.length < MIN_PAIR_N) continue
    const r = pearson(shared.map(d => mapA[d]), shared.map(d => mapB[d]))
    if (r === null) continue
    pairs.push({
      label_a: keyA, label_b: keyB, r: round(r, 2), n: shared.length,
      points: shared.map(d => ({ date: d, a: mapA[d], b: mapB[d] })),
    })
  }
  pairs.sort((a, b) => Math.abs(b.r) - Math.abs(a.r))
  pairs = pairs.slice(0, MAX_PAIRS)

  // Scale trackers on training days vs rest days
  const trainingDays = new Set(
    (await db.session.toArray())
      .map(s => s.started_at.slice(0, 10))
      .filter(d => d >= start)
  )
  const splits = []
  for (const t of scaleTrackers) {
    const values = series[t.name]
    const withVals = Object.entries(values).filter(([d]) => trainingDays.has(d)).map(([, v]) => v)
    const withoutVals = Object.entries(values).filter(([d]) => !trainingDays.has(d)).map(([, v]) => v)
    if (withVals.length >= MIN_SPLIT_N && withoutVals.length >= MIN_SPLIT_N) {
      splits.push({
        name: t.name,
        with_avg: round(avg(withVals), 1), without_avg: round(avg(withoutVals), 1),
        n_with: withVals.length, n_without: withoutVals.length,
      })
    }
  }

  return { window_days: WINDOW_DAYS, pairs, training_splits: splits }
}

// ---------------------------------------------------------------------------
// Routes
// ---------------------------------------------------------------------------

export const overviewRoutes = [
  { method: 'GET', pattern: /^\/api\/dashboard$/, handler: () => dashboard() },
  {
    method: 'GET', pattern: /^\/api\/calendar\/(\d{4})\/(\d{1,2})$/,
    handler: (m) => monthCalendar(Number(m[1]), Number(m[2])),
  },
  {
    method: 'GET', pattern: /^\/api\/day\/(\d{4}-\d{2}-\d{2})$/,
    handler: (m) => dayDetail(m[1]),
  },
  {
    method: 'GET', pattern: /^\/api\/insights\/weekly$/,
    handler: async () => {
      const today = todayIso()
      return {
        current: await periodMetrics(addDays(today, -6), today),
        previous: await periodMetrics(addDays(today, -13), addDays(today, -7)),
      }
    },
  },
  { method: 'GET', pattern: /^\/api\/insights\/correlations$/, handler: () => correlations() },
  {
    method: 'GET', pattern: /^\/api\/settings$/,
    handler: async () => strip(await getSettings()),
  },
  {
    method: 'PUT', pattern: /^\/api\/settings$/,
    handler: async (_m, _q, body) => {
      const s = await getSettings()
      const row = {
        ...s,
        ...Object.fromEntries(Object.entries(body).filter(([, v]) => v !== undefined)),
        updated_at: nowIso(), _dirty: 1,
      }
      await db.settings.put(row)
      return strip(row)
    },
  },
]

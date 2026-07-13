/**
 * Diet, local-first — mirrors backend app/diet.py + activities.py and the
 * pure engines app/calorie_adapt.py, app/nutrition_rda.py, app/activity_burn.py.
 *
 * The calorie target is an anchored weekly-trend step model: it moves ±one
 * step once per completed ISO week toward the desired loss rate, never
 * recomputed from scratch. The adapted target is persisted onto the settings
 * singleton (dirty-marked so it syncs).
 */
import { db, newUuid, nowIso } from '../db'
import { isoWeekStart, weeklyAverages } from './weight_trend'
import { LocalApiError, addDays, notFound, round, todayIso } from './util'

const LOOKBACK_DAYS = 35
const MICRO_AVG_DAYS = 7

const stamp = (row) => ({ ...row, updated_at: nowIso(), _dirty: 1 })
const dayDiff = (a, b) => Math.round((Date.parse(b + 'T00:00:00Z') - Date.parse(a + 'T00:00:00Z')) / 86400000)

// ---------------------------------------------------------------------------
// activity_burn.py
// ---------------------------------------------------------------------------

const ACTIVITY_METS = { football: 8.0, judo: 10.0, padel: 7.0 }
const DEFAULT_MET = 6.0

export function activityKcal(type, durationMin, weightKg) {
  const met = ACTIVITY_METS[(type || '').toLowerCase()] ?? DEFAULT_MET
  return Math.round(met * Math.max(weightKg, 1.0) * (durationMin / 60.0))
}

// ---------------------------------------------------------------------------
// calorie_adapt.py
// ---------------------------------------------------------------------------

const KCAL_PER_KG = 7700.0
export const MIN_ENTRIES_FOR_ADAPT = 3
const MAINTENANCE_WINDOW = 21
const MAINTENANCE_MIN_POINTS = 10

function linregSlope(points) {
  const n = points.length
  if (n < 2) return null
  const mx = points.reduce((a, [x]) => a + x, 0) / n
  const my = points.reduce((a, [, y]) => a + y, 0) / n
  const den = points.reduce((a, [x]) => a + (x - mx) ** 2, 0)
  if (den === 0) return null
  return points.reduce((a, [x, y]) => a + (x - mx) * (y - my), 0) / den
}

export function estimateMaintenance(weightByDate, intakeByDate, today) {
  const start = addDays(today, -MAINTENANCE_WINDOW)
  const intakes = Object.entries(intakeByDate)
    .filter(([d, k]) => d >= start && d <= today && k && k > 0).map(([, k]) => k)
  if (intakes.length < MAINTENANCE_MIN_POINTS) return null
  const pts = Object.entries(weightByDate)
    .filter(([d]) => d >= start && d <= today).map(([d, kg]) => [dayDiff(start, d), kg])
  if (pts.length < MAINTENANCE_MIN_POINTS) return null
  const slope = linregSlope(pts)
  if (slope === null) return null
  const maintenance = intakes.reduce((a, b) => a + b, 0) / intakes.length - slope * KCAL_PER_KG
  if (!(maintenance >= 1200.0 && maintenance <= 6000.0)) return null
  return maintenance
}

export function adaptTarget({
  currentTarget, targetLossKgPerWeek, stepKcal, toleranceKg, floor, ceiling,
  weightByDate, today, lastAdaptedWeek,
}) {
  const thisWeek = isoWeekStart(today)
  if (lastAdaptedWeek != null && lastAdaptedWeek >= thisWeek) {
    return { target: currentTarget, changed: false, due: false, reason: 'not_due', actual_change_kg: null, entries_completed_week: null }
  }

  const weeks = weeklyAverages(weightByDate, today)
  const completed = weeks.filter(w => !w.is_current_week)
  const gathering = (entries = null) => ({
    target: currentTarget, changed: false, due: false, reason: 'insufficient_data',
    actual_change_kg: null, entries_completed_week: entries,
  })

  if (completed.length < 2) return gathering()
  const last = completed[completed.length - 1]
  const prev = completed[completed.length - 2]
  if (dayDiff(prev.week_start, last.week_start) !== 7) return gathering(last.n_entries)
  if (last.n_entries < MIN_ENTRIES_FOR_ADAPT) return gathering(last.n_entries)

  const actualChange = round(last.avg_kg - prev.avg_kg, 3)
  const desired = -Math.abs(targetLossKgPerWeek)
  const lower = desired - toleranceKg
  const upper = desired + toleranceKg

  let proposed, reason
  if (actualChange < lower) { proposed = currentTarget + stepKcal; reason = 'increase' }
  else if (actualChange > upper) { proposed = currentTarget - stepKcal; reason = 'decrease' }
  else { proposed = currentTarget; reason = 'hold' }

  proposed = Math.max(floor, proposed)
  if (ceiling != null) proposed = Math.max(floor, Math.min(ceiling, proposed))
  proposed = Math.round(proposed / 10.0) * 10

  return {
    target: proposed, changed: proposed !== currentTarget, due: true, reason,
    actual_change_kg: actualChange, entries_completed_week: last.n_entries,
  }
}

export function carbsFromTarget(calorieTarget, proteinG, fatG) {
  const grams = (calorieTarget - proteinG * 4 - fatG * 9) / 4
  return Math.max(0, Math.round(grams))
}

// ---------------------------------------------------------------------------
// nutrition_rda.py
// ---------------------------------------------------------------------------

// name, label, category, unit, rda_male, rda_female
const NUTRIENTS = [
  ['vitamin_a', 'Vitamin A', 'vitamin', 'mcg', 900, 700],
  ['vitamin_c', 'Vitamin C', 'vitamin', 'mg', 90, 75],
  ['vitamin_d', 'Vitamin D', 'vitamin', 'mcg', 15, 15],
  ['vitamin_e', 'Vitamin E', 'vitamin', 'mg', 15, 15],
  ['vitamin_k', 'Vitamin K', 'vitamin', 'mcg', 120, 90],
  ['thiamin', 'Vitamin B1', 'vitamin', 'mg', 1.2, 1.1],
  ['riboflavin', 'Vitamin B2', 'vitamin', 'mg', 1.3, 1.1],
  ['niacin', 'Vitamin B3', 'vitamin', 'mg', 16, 14],
  ['pantothenic', 'Vitamin B5', 'vitamin', 'mg', 5, 5],
  ['vitamin_b6', 'Vitamin B6', 'vitamin', 'mg', 1.3, 1.3],
  ['folate', 'Folate (B9)', 'vitamin', 'mcg', 400, 400],
  ['vitamin_b12', 'Vitamin B12', 'vitamin', 'mcg', 2.4, 2.4],
  ['choline', 'Choline', 'vitamin', 'mg', 550, 425],
  ['calcium', 'Calcium', 'mineral', 'mg', 1000, 1000],
  ['iron', 'Iron', 'mineral', 'mg', 8, 18],
  ['magnesium', 'Magnesium', 'mineral', 'mg', 400, 310],
  ['zinc', 'Zinc', 'mineral', 'mg', 11, 8],
  ['potassium', 'Potassium', 'mineral', 'mg', 3400, 2600],
  ['phosphorus', 'Phosphorus', 'mineral', 'mg', 700, 700],
  ['selenium', 'Selenium', 'mineral', 'mcg', 55, 55],
  ['iodine', 'Iodine', 'mineral', 'mcg', 150, 150],
  ['manganese', 'Manganese', 'mineral', 'mg', 2.3, 1.8],
  ['copper', 'Copper', 'mineral', 'mcg', 900, 900],
]

const ALIASES = {
  vitamin_b1: 'thiamin', vitamin_b2: 'riboflavin', vitamin_b3: 'niacin',
  vitamin_b5: 'pantothenic', pantothenic_acid: 'pantothenic', vitamin_b9: 'folate',
  folate_dfe: 'folate', vitamin_b7: 'biotin',
}

const UNIT_TO_MG = { g: 1000.0, mg: 1.0, mcg: 0.001, ug: 0.001, 'µg': 0.001 }

function classify(pct) {
  if (pct < 70) return 'low'
  if (pct < 100) return 'slightly_low'
  if (pct <= 150) return 'meets'
  return 'above'
}

const toMg = (v, unit) => v * (UNIT_TO_MG[unit] ?? 1.0)

function splitKey(key) {
  const idx = key.lastIndexOf('_')
  if (idx > 0) {
    const base = key.slice(0, idx)
    const unit = key.slice(idx + 1)
    if (base && unit in UNIT_TO_MG) return [base, unit]
  }
  return [key, '']
}

export function buildBreakdown(avgMicros, sex) {
  const female = (sex || 'male').toLowerCase().startsWith('f')
  const intakeMg = {}
  for (const [key, value] of Object.entries(avgMicros || {})) {
    if (value == null) continue
    let [name, unit] = splitKey(key)
    name = ALIASES[name] || name
    const num = Number(value)
    if (!Number.isFinite(num)) continue
    intakeMg[name] = toMg(num, unit || 'mg')
  }

  const rows = []
  for (const [name, label, category, unit, rdaM, rdaF] of NUTRIENTS) {
    if (!(name in intakeMg)) continue
    const rda = female ? rdaF : rdaM
    const rdaMg = toMg(rda, unit)
    if (rdaMg <= 0) continue
    const pct = intakeMg[name] / rdaMg * 100.0
    const amount = intakeMg[name] / (UNIT_TO_MG[unit] ?? 1.0)
    rows.push({
      name, label, category, amount: round(amount, 1), unit,
      rda, pct: Math.round(pct), status: classify(pct),
    })
  }
  return rows
}

// ---------------------------------------------------------------------------
// build_diet
// ---------------------------------------------------------------------------

const DEFAULTS = {
  calorie_target: 2300, protein_target_g: 180, fat_max_g: 100, sex: 'male',
  target_loss_kg_per_week: 0.5, adapt_step_kcal: 100, adapt_tolerance_kg: 0.15,
  calorie_floor: 1800, calorie_ceiling: null, last_adapted_week: null,
}

async function getSettings() {
  const s = await db.settings.get(1)
  return { ...DEFAULTS, ...(s || {}), id: 1 }
}

function resolvedCeiling(settings, weightByDate, intakeByDate, today) {
  if (settings.calorie_ceiling != null) return settings.calorie_ceiling
  const est = estimateMaintenance(weightByDate, intakeByDate, today)
  return est != null ? Math.round(est / 10.0) * 10 : null
}

async function adaptIfDue(settings, weightByDate, ceiling, today, force) {
  const result = adaptTarget({
    currentTarget: settings.calorie_target,
    targetLossKgPerWeek: settings.target_loss_kg_per_week,
    stepKcal: settings.adapt_step_kcal,
    toleranceKg: settings.adapt_tolerance_kg,
    floor: settings.calorie_floor,
    ceiling,
    weightByDate,
    today,
    lastAdaptedWeek: force ? null : settings.last_adapted_week,
  })
  if (result.due) {
    settings.calorie_target = result.target
    settings.last_adapted_week = isoWeekStart(today)
    await db.settings.put(stamp({ ...settings }))
  }
  return result
}

async function buildDiet(forceRecalc = false) {
  const today = todayIso()
  const settings = await getSettings()
  const since = addDays(today, -LOOKBACK_DAYS)

  const weights = (await db.weight_log.toArray())
    .filter(w => w.date >= since).sort((a, b) => (a.date < b.date ? -1 : 1))
  const nutrition = (await db.nutrition_day.toArray())
    .filter(n => n.date >= since).sort((a, b) => (a.date < b.date ? -1 : 1))
  const weightByDate = Object.fromEntries(weights.map(w => [w.date, w.weight_kg]))
  const intakeByDate = Object.fromEntries(nutrition.map(n => [n.date, n.calories]))

  const ceiling = resolvedCeiling(settings, weightByDate, intakeByDate, today)
  await adaptIfDue(settings, weightByDate, ceiling, today, forceRecalc)

  const avgIntake = (days) => {
    const start = addDays(today, -days)
    const vals = nutrition.filter(n => n.date > start && n.calories).map(n => n.calories)
    return vals.length ? Math.round(vals.reduce((a, b) => a + b, 0) / vals.length) : null
  }

  const recentNut = nutrition.filter(n => n.micros && Object.keys(n.micros).length).slice(-MICRO_AVG_DAYS)
  const sums = {}, counts = {}
  for (const n of recentNut) {
    for (const [k, v] of Object.entries(n.micros || {})) {
      if (v == null) continue
      const num = Number(v)
      if (!Number.isFinite(num)) continue
      sums[k] = (sums[k] || 0) + num
      counts[k] = (counts[k] || 0) + 1
    }
  }
  const avgMicros = Object.fromEntries(Object.keys(sums).map(k => [k, sums[k] / counts[k]]))
  const nutrients = buildBreakdown(avgMicros, settings.sex)

  const weeks = weeklyAverages(weightByDate, today)
  const completed = weeks.filter(w => !w.is_current_week)
  const entriesLastWeek = completed.length ? completed[completed.length - 1].n_entries : null
  const haveCompare = completed.length >= 2 &&
    dayDiff(completed[completed.length - 2].week_start, completed[completed.length - 1].week_start) === 7
  const weeklyChange = haveCompare
    ? round(completed[completed.length - 1].avg_kg - completed[completed.length - 2].avg_kg, 2) : null
  const weightTrend = weeks.length ? weeks[weeks.length - 1].avg_kg : null

  const protein = settings.protein_target_g
  const fat = settings.fat_max_g
  const carb = settings.calorie_target ? carbsFromTarget(settings.calorie_target, protein, fat) : null

  const adaptiveReady = settings.last_adapted_week != null
  let note = null
  if (!haveCompare) {
    note = `Gathering data — the target adapts each Monday once there are two ` +
      `consecutive weeks with at least ${MIN_ENTRIES_FOR_ADAPT} weigh-ins. Holding at ` +
      `your ${settings.calorie_target} kcal anchor.`
  } else if (entriesLastWeek != null && entriesLastWeek < MIN_ENTRIES_FOR_ADAPT) {
    note = `Holding — last completed week had only ${entriesLastWeek} ` +
      `weigh-in(s); ${MIN_ENTRIES_FOR_ADAPT} are needed to adapt.`
  }

  const nextAdapt = addDays(isoWeekStart(today), 7)

  const energy = {
    calorie_target: settings.calorie_target,
    target_loss_kg_per_week: settings.target_loss_kg_per_week,
    protein_target_g: protein, fat_target_g: fat, carb_target_g: carb,
    adaptive_ready: adaptiveReady, weekly_change_kg: weeklyChange,
    last_adapted: settings.last_adapted_week, next_adapt: nextAdapt,
    entries_last_week: entriesLastWeek, floor: settings.calorie_floor, ceiling,
    weight_trend_kg: weightTrend, avg_intake_7d: avgIntake(7), avg_intake_14d: avgIntake(14),
    note,
  }

  const latestW = weights.length ? weights[weights.length - 1].weight_kg : 75.0
  const actRows = (await db.activity.toArray())
    .filter(a => a.date >= addDays(today, -14))
    .sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0))
  const activities = actRows.map(a => ({
    id: a.uuid, date: a.date, type: a.type, duration_min: a.duration_min,
    notes: a.notes ?? null, calories_est: activityKcal(a.type, a.duration_min, latestW),
  }))

  return { energy, nutrients, nutrient_days: recentNut.length, activities }
}

// ---------------------------------------------------------------------------
// Activities CRUD (mirrors activities.py)
// ---------------------------------------------------------------------------

async function latestWeight() {
  const rows = (await db.weight_log.toArray()).sort((a, b) => (a.date < b.date ? 1 : -1))
  return rows.length ? rows[0].weight_kg : 75.0
}

const presentActivity = (a, w) => ({
  id: a.uuid, date: a.date, type: a.type, duration_min: a.duration_min,
  notes: a.notes ?? null, calories_est: activityKcal(a.type, a.duration_min, w),
})

async function listActivities(days) {
  const since = addDays(todayIso(), -days)
  const rows = (await db.activity.toArray())
    .filter(a => a.date >= since)
    .sort((a, b) => (a.date < b.date ? 1 : a.date > b.date ? -1 : 0))
  const w = await latestWeight()
  return rows.map(a => presentActivity(a, w))
}

async function createActivity(body) {
  if (!body.duration_min || body.duration_min <= 0) throw new LocalApiError(422, 'duration_min must be > 0')
  const a = stamp({
    uuid: newUuid(), date: body.date, type: (body.type || '').trim().toLowerCase(),
    duration_min: body.duration_min, notes: body.notes ?? null, source: 'manual',
  })
  await db.activity.put(a)
  return presentActivity(a, await latestWeight())
}

async function deleteActivity(uuid) {
  if (!(await db.activity.get(uuid))) throw notFound('Activity')
  await db.activity.delete(uuid)
  return null
}

export const dietRoutes = [
  { method: 'GET', pattern: /^\/api\/diet$/, handler: () => buildDiet(false) },
  { method: 'POST', pattern: /^\/api\/diet\/recalc$/, handler: () => buildDiet(true) },
  {
    method: 'GET', pattern: /^\/api\/activities$/,
    handler: (_m, q) => listActivities(Math.min(365, Math.max(1, Number(q.get('days') || 30)))),
  },
  { method: 'POST', pattern: /^\/api\/activities$/, handler: (_m, _q, body) => createActivity(body) },
  { method: 'DELETE', pattern: /^\/api\/activities\/([^/]+)$/, handler: (m) => deleteActivity(m[1]) },
]

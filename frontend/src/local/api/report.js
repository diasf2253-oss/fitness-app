/**
 * Weekly / biweekly report, local-first — mirrors backend app/report.py.
 * Every section returns null when there's no data for the period, so the
 * report never breaks on missing Apple-Health-derived data.
 */
import { db } from '../db'
import { MUSCLE_GROUPS, resolvedVolumeTargets } from './muscles'
import { streakSnapshot } from './streak'
import { epley1rm } from './workout'
import { isoWeekStart, weeklyAverages } from './weight_trend'
import { addDays, round, todayIso } from './util'

const PERIOD_DAYS = { weekly: 7, biweekly: 14 }
const g = (x) => `${+x}`   // Python's :g — drop trailing .0

async function joinMaps() {
  const [sets, ses, sessions, exercises] = await Promise.all([
    db.set.toArray(), db.session_exercise.toArray(),
    db.session.toArray(), db.exercise.toArray(),
  ])
  return {
    sets,
    seMap: new Map(ses.map(s => [s.uuid, s])),
    sessMap: new Map(sessions.map(s => [s.uuid, s])),
    exMap: new Map(exercises.map(e => [e.uuid, e])),
  }
}

async function periodPrs(start, end) {
  const { sets, seMap, sessMap, exMap } = await joinMaps()
  const byEx = new Map()
  for (const st of sets) {
    if (!(st.is_completed && !st.is_warmup && st.reps > 0 && st.weight_kg > 0)) continue
    const se = seMap.get(st.session_exercise_uuid); if (!se) continue
    const sess = sessMap.get(se.session_uuid); if (!sess) continue
    const d = sess.started_at.slice(0, 10)
    if (d > end) continue
    const ex = exMap.get(se.exercise_uuid)
    let rec = byEx.get(se.exercise_uuid)
    if (!rec) { rec = { name: ex ? ex.name : se.exercise_uuid, prior: 0, in: 0, set: null }; byEx.set(se.exercise_uuid, rec) }
    const e1rm = epley1rm(st.weight_kg, st.reps)
    if (d < start) rec.prior = Math.max(rec.prior, e1rm)
    else if (e1rm > rec.in) { rec.in = e1rm; rec.set = [st.weight_kg, st.reps] }
  }
  const prs = []
  for (const rec of byEx.values()) {
    if (rec.in > 0 && rec.in > rec.prior) {
      const [w, reps] = rec.set
      prs.push({
        exercise: rec.name, estimated_1rm: round(rec.in, 1),
        previous_best: rec.prior > 0 ? round(rec.prior, 1) : null,
        best_set: `${g(w)} kg × ${reps}`,
      })
    }
  }
  prs.sort((a, b) => b.estimated_1rm - a.estimated_1rm)
  return prs
}

async function bodyweight(end, weeksBack) {
  const since = addDays(end, -(7 * (weeksBack + 2) + 7))
  const rows = (await db.weight_log.toArray()).filter(w => w.date >= since && w.date <= end)
  const byDate = Object.fromEntries(rows.map(w => [w.date, w.weight_kg]))
  const weeks = weeklyAverages(byDate, end)
  if (weeks.length < 2) return null
  const endWk = weeks[weeks.length - 1]
  const targetStart = addDays(endWk.week_start, -7 * weeksBack)
  const startWk = weeks.find(w => w.week_start === targetStart) || weeks[0]
  if (startWk.week_start === endWk.week_start) return null
  const change = round(endWk.avg_kg - startWk.avg_kg, 2)
  return {
    start_week: startWk.week_start, start_avg: startWk.avg_kg,
    end_week: endWk.week_start, end_avg: endWk.avg_kg, change_kg: change,
    direction: change < 0 ? 'down' : change > 0 ? 'up' : 'flat',
  }
}

async function dietSection(start, end, settings) {
  const rows = (await db.nutrition_day.toArray()).filter(n => n.date >= start && n.date <= end)
  if (rows.length === 0) return null
  const calT = settings.calorie_target, protT = settings.protein_target_g
  const calOk = rows.filter(n => n.calories && Math.abs(n.calories - calT) <= 0.10 * calT).length
  const protOk = rows.filter(n => n.protein_g && n.protein_g >= 0.90 * protT).length
  const n = rows.length
  return {
    logged_days: n, calorie_target: calT, protein_target_g: protT,
    calorie_on_target: calOk, protein_on_target: protOk,
    calorie_pct: Math.round(100 * calOk / n), protein_pct: Math.round(100 * protOk / n),
  }
}

async function sleepSection(start, end, days) {
  const all = await db.sleep_log.toArray()
  const avg = (s, e) => {
    const rows = all.filter(r => r.date >= s && r.date <= e)
    if (rows.length === 0) return [null, 0]
    return [rows.reduce((a, r) => a + r.asleep_minutes, 0) / rows.length / 60, rows.length]
  }
  const [cur, nights] = avg(start, end)
  if (cur === null) return null
  const [prev] = avg(addDays(start, -days), addDays(start, -1))
  return {
    avg_hours: round(cur, 1), nights,
    prev_avg_hours: prev ? round(prev, 1) : null,
    change_h: prev ? round(cur - prev, 1) : null,
  }
}

export async function currentWeekVolumeFlags(settings, today) {
  const weekStart = isoWeekStart(today)
  const { sets, seMap, sessMap, exMap } = await joinMaps()
  const counts = {}
  for (const st of sets) {
    if (!(st.is_completed && !st.is_warmup)) continue
    const se = seMap.get(st.session_exercise_uuid); if (!se) continue
    const sess = sessMap.get(se.session_uuid); if (!sess) continue
    if (sess.started_at.slice(0, 10) < weekStart) continue
    const grp = exMap.get(se.exercise_uuid)?.primary_muscle_group
    if (grp) counts[grp] = (counts[grp] || 0) + 1
  }
  const targets = resolvedVolumeTargets(settings.volume_targets)
  const flags = []
  for (const m of MUSCLE_GROUPS) {
    const c = counts[m] || 0
    const [low, high] = targets[m]
    if (c < low) flags.push({ muscle: m, count: c, low, high, status: 'under' })
    else if (c > high) flags.push({ muscle: m, count: c, low, high, status: 'over' })
  }
  return flags
}

async function buildReport(period = 'weekly') {
  if (!(period in PERIOD_DAYS)) throw new Error(`period must be one of ${Object.keys(PERIOD_DAYS)}`)
  const days = PERIOD_DAYS[period]
  const weeksBack = Math.floor(days / 7)
  const today = todayIso()
  const start = addDays(today, -(days - 1))

  const settings = (await db.settings.get(1)) || {}
  const streak = await streakSnapshot()
  const prs = await periodPrs(start, today)

  return {
    period, period_days: days, start, end: today,
    generated_at: new Date().toISOString(),
    prs: { items: prs, count: prs.length },
    streak: { current: streak.current, longest: streak.longest, alive: streak.alive, at_risk: streak.at_risk },
    bodyweight: await bodyweight(today, weeksBack),
    diet: await dietSection(start, today, settings),
    sleep: await sleepSection(start, today, days),
    plan: {
      calorie_target: settings.calorie_target ?? 2400,
      goal_kg_per_week: settings.goal_kg_per_week ?? 0.5,
      next_adapt: addDays(isoWeekStart(today), 7),
      volume_flags: await currentWeekVolumeFlags(settings, today),
    },
    coach_available: false,   // coach-plan falls through to the network when reachable
  }
}

// Markdown export — mirrors report.report_markdown.
export function reportMarkdown(r) {
  const NONE = '_No data for this period._'
  const lines = []
  const title = r.period === 'weekly' ? 'Weekly' : 'Biweekly'
  lines.push(`# ${title} report`, '', `**${r.start} → ${r.end}**`, '')

  lines.push('## New PRs', '')
  if (r.prs.items.length) {
    for (const p of r.prs.items) {
      const prev = p.previous_best ? ` (was ${p.previous_best} kg)` : ' (first record)'
      lines.push(`- **${p.exercise}** — est. 1RM ${p.estimated_1rm} kg${prev}, best set ${p.best_set}`)
    }
  } else lines.push('_No new PRs this period._')
  lines.push('')

  const s = r.streak
  lines.push('## Streak', '',
    `- Current: **${s.current}** workout(s) in a row${s.at_risk ? ' · ⚠️ at risk' : ''}`,
    `- Longest ever: ${s.longest}`, '')

  const bw = r.bodyweight
  lines.push('## Bodyweight trend', '')
  if (bw) {
    const arrow = bw.direction === 'down' ? '▼' : bw.direction === 'up' ? '▲' : '→'
    lines.push(`- ${bw.start_avg} kg → ${bw.end_avg} kg (${arrow} ${Math.abs(bw.change_kg)} kg, weekly avg)`)
  } else lines.push(NONE)
  lines.push('')

  const d = r.diet
  lines.push('## Diet adherence', '')
  if (d) {
    lines.push(
      `- Calories within target: **${d.calorie_pct}%** (${d.calorie_on_target}/${d.logged_days} logged days)`,
      `- Protein on target: **${d.protein_pct}%** (${d.protein_on_target}/${d.logged_days})`)
  } else lines.push(NONE)
  lines.push('')

  const sl = r.sleep
  lines.push('## Sleep', '')
  if (sl) {
    const trend = sl.change_h != null ? ` (${sl.change_h >= 0 ? '+' : ''}${sl.change_h} h vs prior)` : ''
    lines.push(`- Average **${sl.avg_hours} h** over ${sl.nights} night(s)${trend}`)
  } else lines.push(NONE)
  lines.push('')

  const p = r.plan
  lines.push('## Plan for next week', '',
    `- Calorie target: **${p.calorie_target} kcal** (aiming to lose ${p.goal_kg_per_week} kg/wk; next adapt ${p.next_adapt})`)
  if (p.volume_flags.length) {
    for (const f of p.volume_flags) {
      lines.push(`- ${f.muscle}: ${f.count} sets — **${f.status}** target (${f.low}–${f.high})`)
    }
  } else lines.push('- Volume on track across all muscle groups this week.')
  lines.push('')

  return lines.join('\n')
}

const periodOf = (q) => (q.get('period') === 'biweekly' ? 'biweekly' : 'weekly')

export const reportRoutes = [
  { method: 'GET', pattern: /^\/api\/report$/, handler: (_m, q) => buildReport(periodOf(q)) },
  {
    method: 'GET', pattern: /^\/api\/report\/markdown$/,
    handler: async (_m, q) => reportMarkdown(await buildReport(periodOf(q))),
  },
]

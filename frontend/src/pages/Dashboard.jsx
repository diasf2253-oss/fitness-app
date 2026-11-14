/**
 * Dashboard — home screen (Phase 2, v1).
 * One call to GET /api/dashboard renders every widget: nutrition vs
 * targets, weight trend with 7-day moving average, steps, sleep, and
 * training (week volume + recent PRs).
 * Every widget renders a quiet empty state until data exists. Health data is
 * logged by hand for now (quick-log sheet, or the full Log page) — Apple
 * Health sync is paused until a native app exists.
 */
import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../api'
import { Loading, ErrorBox, EmptyNote, NoHealthDataNote } from '../components/States'
import MonthCalendar from '../components/MonthCalendar'
import WidgetLabel from '../components/WidgetLabel'
import WeightCard from '../components/WeightCard'
import GoalBarCard from '../components/GoalBarCard'
import { HEALTH_DATA_CHANGED, openQuickLog } from '../components/QuickLog'
import CheckIn from '../components/CheckIn'

function MacroBar({ label, value, target, over }) {
  const pct = target > 0 ? Math.min(100, (value / target) * 100) : 0
  return (
    <div style={{ marginBottom: '0.7rem' }}>
      <div className="row" style={{ justifyContent: 'space-between', marginBottom: 4 }}>
        <WidgetLabel>{label}</WidgetLabel>
        <span className="tnum" style={{ fontSize: '0.82rem' }}>
          {Math.round(value)} <span className="muted">/ {target}</span>
        </span>
      </div>
      <div className="progress-bar-wrap">
        <div className={`progress-bar-fill${over ? ' over' : ''}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}

// Daily goals the Steps / Sleep bars fill toward.
const STEP_GOAL = 9000
const SLEEP_GOAL_H = 8
/** 7.4 → "7h 24m" */
const fmtHours = h => { const m = Math.round(h * 60); return `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, '0')}m` }

const PR_LABEL = { heaviest: 'Heaviest', best_1rm: 'Est. 1RM', best_volume: 'Set volume' }

// Local calendar date (toISOString alone would shift near midnight)
function localTodayIso() {
  const d = new Date()
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

/**
 * DayDetail — everything recorded on the calendar-selected day.
 * Lives in the dashboard rail under the month calendar.
 */
function DayDetail({ date }) {
  const [detail, setDetail] = useState(null)

  function load() {
    apiFetch(`/api/day/${date}`).then(setDetail).catch(() => setDetail(null))
  }

  useEffect(() => {
    setDetail(null)
    load()
  }, [date])

  const title = new Date(date + 'T00:00:00').toLocaleDateString('en-US', {
    weekday: 'short', month: 'short', day: 'numeric',
  })

  const hasAnything = detail && (
    detail.sessions.length > 0 || detail.weight_kg != null ||
    detail.steps != null || detail.sleep || detail.nutrition ||
    (detail.trackers || []).length > 0
  )

  const Row = ({ label, children }) => (
    <div className="row" style={{ justifyContent: 'space-between', padding: '0.22rem 0' }}>
      <span className="muted" style={{ fontSize: '0.8rem' }}>{label}</span>
      <span className="tnum" style={{ fontSize: '0.82rem' }}>{children}</span>
    </div>
  )

  return (
    <div className="card">
      <div className="row" style={{ marginBottom: '0.4rem' }}>
        <h3 style={{ margin: 0, flex: 1 }}>{title}</h3>
        <Link to={`/log?date=${date}`} style={{ fontSize: '0.75rem' }}>Edit ›</Link>
      </div>

      {!detail && <p className="muted" style={{ fontSize: '0.8rem' }}>Loading…</p>}

      {/* Plan section killed per workbook H8 (grade D) */}

      {detail && detail.sessions.map(s => (
        <div key={s.id} style={{ padding: '0.35rem 0', borderBottom: '1px solid var(--color-border)' }}>
          <div style={{ fontSize: '0.88rem', fontWeight: 500 }}>{s.name}</div>
          <div className="muted" style={{ fontSize: '0.75rem' }}>
            {Math.round(s.total_volume_kg).toLocaleString()} kg · {s.completed_sets} sets
            {s.duration_minutes != null && ` · ${s.duration_minutes} min`}
          </div>
        </div>
      ))}

      {detail && (
        <div style={{ marginTop: '0.35rem' }}>
          {detail.weight_kg != null && (
            <Row label="Weight">
              {detail.weight_kg} kg
              {detail.weight_estimated && (
                <span className="muted" style={{ marginLeft: 5, fontSize: '0.7rem' }}>est.</span>
              )}
            </Row>
          )}
          {detail.steps != null && <Row label="Steps">{detail.steps.toLocaleString()}</Row>}
          {detail.sleep && <Row label="Sleep">{Math.round(detail.sleep.asleep_minutes / 6) / 10} h</Row>}
          {detail.nutrition && (
            <Row label="Intake">
              {Math.round(detail.nutrition.calories)} kcal · {Math.round(detail.nutrition.protein_g)}P
              /{Math.round(detail.nutrition.carbs_g)}C/{Math.round(detail.nutrition.fat_g)}F
            </Row>
          )}
          {(detail.trackers || []).map(t => (
            t.kind === 'text' ? (
              <div key={t.name} style={{ padding: '0.3rem 0' }}>
                <span className="muted" style={{ fontSize: '0.8rem' }}>{t.name}</span>
                <div className="serif-italic" style={{ fontSize: '0.85rem', marginTop: 2 }}>
                  {t.value_text}
                </div>
              </div>
            ) : (
              <Row key={t.name} label={t.name}>
                {t.kind === 'habit'
                  ? (t.value_num >= 1 ? '✓ done' : '—')
                  : t.kind === 'scale'
                    ? `${t.value_num}/5`
                    : `${t.value_num}${t.unit ? ` ${t.unit}` : ''}`}
              </Row>
            )
          ))}
        </div>
      )}

      {detail && !hasAnything && (
        <p className="muted" style={{ fontSize: '0.8rem', padding: '0.4rem 0' }}>
          Nothing recorded this day.
        </p>
      )}
    </div>
  )
}

// Micronutrient display: canonical keys are unit-suffixed (sodium_mg).
// Order roughly: fibre/sugars → fats → minerals → vitamins → misc.
const MICRO_ORDER = [
  'fiber', 'sugar', 'sat_fat', 'mono_fat', 'poly_fat', 'cholesterol',
  'sodium', 'potassium', 'calcium', 'magnesium', 'iron', 'zinc',
  'vitamin_a', 'vitamin_c', 'vitamin_d', 'vitamin_e', 'vitamin_k',
  'vitamin_b6', 'vitamin_b12', 'thiamin', 'riboflavin', 'niacin',
  'folate', 'caffeine', 'water',
]
const MICRO_NAMES = {
  fiber: 'Fiber', sugar: 'Sugar', sat_fat: 'Saturated fat',
  mono_fat: 'Monounsat. fat', poly_fat: 'Polyunsat. fat',
  cholesterol: 'Cholesterol', sodium: 'Sodium', potassium: 'Potassium',
  calcium: 'Calcium', magnesium: 'Magnesium', iron: 'Iron', zinc: 'Zinc',
  vitamin_a: 'Vitamin A', vitamin_c: 'Vitamin C', vitamin_d: 'Vitamin D',
  vitamin_e: 'Vitamin E', vitamin_k: 'Vitamin K', vitamin_b6: 'Vitamin B6',
  vitamin_b12: 'Vitamin B12', thiamin: 'Thiamin', riboflavin: 'Riboflavin',
  niacin: 'Niacin', folate: 'Folate', caffeine: 'Caffeine', water: 'Water',
}
const MICRO_UNITS = { g: 'g', mg: 'mg', ug: 'µg', ml: 'ml' }

function microEntries(micros) {
  return Object.entries(micros)
    .map(([key, value]) => {
      const idx = key.lastIndexOf('_')
      const name = key.slice(0, idx)
      return {
        key,
        label: MICRO_NAMES[name] || name.replace(/_/g, ' '),
        unit: MICRO_UNITS[key.slice(idx + 1)] || '',
        value,
        order: MICRO_ORDER.indexOf(name),
      }
    })
    .sort((a, b) => (a.order === -1 ? 99 : a.order) - (b.order === -1 ? 99 : b.order))
}

function MicroList({ micros }) {
  const [open, setOpen] = useState(false)
  const entries = microEntries(micros)
  if (entries.length === 0) return null
  return (
    <div style={{ marginTop: '0.4rem' }}>
      <button
        onClick={() => setOpen(o => !o)}
        style={{
          background: 'transparent', boxShadow: 'none', color: 'var(--color-muted)',
          padding: '0.3rem 0', minHeight: 0, fontSize: '0.72rem',
          letterSpacing: '0.1em', textTransform: 'uppercase',
        }}
      >
        Micronutrients ({entries.length}) {open ? '▴' : '▾'}
      </button>
      {open && (
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '0.3rem 1.25rem', marginTop: '0.4rem' }}>
          {entries.map(e => (
            <div key={e.key} className="row" style={{ justifyContent: 'space-between', gap: '0.4rem' }}>
              <span className="muted" style={{ fontSize: '0.78rem' }}>{e.label}</span>
              <span className="tnum" style={{ fontSize: '0.78rem' }}>
                {e.value} {e.unit}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedDay, setSelectedDay] = useState(localTodayIso())

  useEffect(() => {
    // In local-first mode apiFetch serves this from the on-device DB,
    // so the dashboard works with no server reachable.
    const load = () => apiFetch('/api/dashboard')
      .then(setData)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
    load()
    // Re-fetch after a quick-log save so the cards update in place
    window.addEventListener(HEALTH_DATA_CHANGED, load)
    return () => window.removeEventListener(HEALTH_DATA_CHANGED, load)
  }, [])

  const now = new Date()
  const dateLabel = now.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })
  const hour = now.getHours()
  const greeting = hour < 12 ? 'morning' : hour < 18 ? 'afternoon' : 'evening'

  const nut = data?.nutrition_today
  const targets = data?.targets

  return (
    <div className="page wide">
      {/* Editorial hero — quiet, dated, personal */}
      <span className="badge dot">{dateLabel}</span>
      <h1 style={{ fontSize: '2.4rem', marginTop: '0.9rem' }}>
        Good <em>{greeting}</em>
      </h1>
      <p className="muted" style={{ marginBottom: '1.5rem' }}>
        Here's where things stand. <Link to="/insights">Insights ›</Link>
      </p>

      <ErrorBox error={error} />
      {loading && <Loading />}

      {data && (
        <div className="dash-grid">
          <div className="dash-widgets">
          {/* ---- Daily check-in (trackers) ---- */}
          <CheckIn />

          {/* ---- Nutrition today ---- */}
          <div className="card">
            <div className="row" style={{ marginBottom: '0.75rem' }}>
              <h3 style={{ margin: 0, flex: 1 }}>Today's intake</h3>
              {nut.logged && (
                <span className="tnum muted" style={{ fontSize: '0.8rem' }}>
                  {Math.round(nut.carbs_g)} g carbs
                </span>
              )}
            </div>
            {nut.logged ? (
              <>
                <MacroBar label="Calories" value={nut.calories} target={targets.calorie_target} over={nut.calories > targets.calorie_target} />
                <MacroBar label="Protein" value={nut.protein_g} target={targets.protein_target_g} />
                <MacroBar label="Fat (cap)" value={nut.fat_g} target={targets.fat_max_g} over={nut.fat_g > targets.fat_max_g} />
                <MicroList micros={nut.micros || {}} />
              </>
            ) : (
              <EmptyNote>Nothing logged today. <Link to="/log">Log manually ›</Link></EmptyNote>
            )}
          </div>

          {/* ---- Training ---- */}
          <div className="card">
            <div className="row" style={{ marginBottom: '0.6rem' }}>
              <h3 style={{ margin: 0, flex: 1 }}>Training</h3>
              <WidgetLabel>last 7 days</WidgetLabel>
            </div>
            <div className="row" style={{ justifyContent: 'space-around', textAlign: 'center', marginBottom: '0.5rem' }}>
              <div>
                <div className="stat-num" style={{ fontSize: '1.8rem' }}>{Math.round(data.training.week_volume_kg).toLocaleString()}</div>
                <WidgetLabel>kg volume</WidgetLabel>
              </div>
              <div>
                <div className="stat-num" style={{ fontSize: '1.8rem' }}>{data.training.sessions_this_week}</div>
                <WidgetLabel>sessions</WidgetLabel>
              </div>
              {data.streak && (
                <div>
                  <div className="stat-num" style={{ fontSize: '1.8rem', color: data.streak.at_risk ? 'var(--color-warning)' : undefined }}>
                    {data.streak.current}
                  </div>
                  <WidgetLabel>streak{data.streak.at_risk ? ' · at risk' : ''}</WidgetLabel>
                </div>
              )}
            </div>
            {data.training.recent_prs.length > 0 ? (
              <>
                <hr />
                {data.training.recent_prs.map((pr, i) => (
                  <div key={i} className="row" style={{ padding: '0.3rem 0' }}>
                    <div style={{ flex: 1 }}>
                      <span style={{ fontSize: '0.9rem' }}>{pr.exercise_name}</span>
                      <span className="muted" style={{ fontSize: '0.75rem', marginLeft: 6 }}>{PR_LABEL[pr.kind] || pr.kind}</span>
                    </div>
                    <span className="text-success tnum" style={{ fontWeight: 600, fontSize: '0.9rem' }}>{pr.value}</span>
                  </div>
                ))}
              </>
            ) : (
              data.training.sessions_this_week === 0 && (
                <EmptyNote>No workouts this week. <Link to="/workout">Start one ›</Link></EmptyNote>
              )
            )}
          </div>

          {/* ---- Weight trend ---- */}
          <WeightCard weight={data.weight} onLog={() => openQuickLog('weight')} />

          {/* ---- Steps: fill a 9k bar each day ---- */}
          <GoalBarCard
            label="👟 Steps"
            points={data.steps.map(p => ({ date: p.date, value: p.steps }))}
            goal={STEP_GOAL}
            goalLabel="9k"
            unit="steps"
            formatValue={v => Math.round(v).toLocaleString()}
            storageKey="steps_range_days"
            empty={<NoHealthDataNote metric="step data" log="steps" />}
            onLog={() => openQuickLog('steps')}
          />

          {/* ---- Sleep: fill an 8h bar each night ---- */}
          <GoalBarCard
            label="☾ Sleep"
            points={data.sleep.map(p => ({ date: p.date, value: p.asleep_hours }))}
            goal={SLEEP_GOAL_H}
            goalLabel="8h"
            unit="asleep"
            formatValue={fmtHours}
            storageKey="sleep_range_days"
            empty={<NoHealthDataNote metric="sleep data" log="sleep" />}
            onLog={() => openQuickLog('sleep')}
          />

          </div>

          {/* ---- Right rail: calendar + selected-day detail ---- */}
          <aside className="rail">
            <MonthCalendar selected={selectedDay} onSelect={setSelectedDay} />
            <DayDetail date={selectedDay} />
          </aside>
        </div>
      )}
    </div>
  )
}

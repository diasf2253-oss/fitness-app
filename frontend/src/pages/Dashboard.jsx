/**
 * Dashboard — home screen (Phase 2, v1).
 * One call to GET /api/dashboard renders every widget: nutrition vs
 * targets, weight trend with 7-day moving average, steps, sleep, and
 * training (week volume + recent PRs).
 * Every widget renders a quiet empty state until data exists — real
 * health data arrives with the Apple Health sync in Phase 3, or via
 * the manual Log page.
 */
import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { apiFetch } from '../api'
import { Loading, ErrorBox } from '../components/States'
import MonthCalendar from '../components/MonthCalendar'
import WidgetLabel from '../components/WidgetLabel'
import CheckIn from '../components/CheckIn'

// Chart palette — mirrors the "Quiet Tracker" CSS tokens
const GRID = 'rgba(236,233,224,0.07)'
const AXIS = '#9aa69b'
const SAGE = '#a8bfa1'
const MOSS = '#7f9b78'
const BONE = '#ece9e0'
const TOOLTIP_STYLE = {
  background: '#1d2521',
  border: '1px solid rgba(236,233,224,0.12)',
  borderRadius: 12,
  color: '#ece9e0',
}

function fmtDay(iso) {
  return new Date(iso + 'T00:00:00').toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

// Weight dots: solid for a real weigh-in, hollow ring for an interpolated
// estimate on a day that wasn't tracked.
function weightDot(props) {
  const { cx, cy, payload, index } = props
  if (cx == null || cy == null) return null
  return payload.estimated
    ? <circle key={index} cx={cx} cy={cy} r={2.2} fill="none" stroke={SAGE} strokeWidth={1} strokeOpacity={0.55} />
    : <circle key={index} cx={cx} cy={cy} r={2} fill={SAGE} />
}

function EmptyNote({ children }) {
  return (
    <p className="muted" style={{ textAlign: 'center', padding: '1.1rem 0' }}>
      {children || <>No data yet. <Link to="/log">Log manually ›</Link></>}
    </p>
  )
}

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
    apiFetch('/api/dashboard')
      .then(setData)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  const now = new Date()
  const dateLabel = now.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })
  const hour = now.getHours()
  const greeting = hour < 12 ? 'morning' : hour < 18 ? 'afternoon' : 'evening'

  // Merge the weight series with its moving average for a two-line chart
  const weightData = data
    ? data.weight.series.map(p => {
        const avg = data.weight.moving_avg_7d.find(a => a.date === p.date)
        return { date: p.date, weight_kg: p.weight_kg, avg_kg: avg ? avg.avg_kg : null, estimated: p.estimated }
      })
    : []
  const hasWeightEstimates = weightData.some(p => p.estimated)

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
                    {data.streak.current}{data.streak.current > 0 ? '🔥' : ''}
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
          <div className="card span-2">
            <div className="row" style={{ marginBottom: '0.5rem' }}>
              <h3 style={{ margin: 0, flex: 1 }}>Weight</h3>
              <WidgetLabel>90 days · 7-day avg</WidgetLabel>
            </div>
            {weightData.length > 0 ? (
              <>
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={weightData} margin={{ top: 8, right: 8, left: -14, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                  <XAxis dataKey="date" stroke={AXIS} fontSize={10} tickLine={false} axisLine={false} tickFormatter={fmtDay} minTickGap={28} />
                  <YAxis stroke={AXIS} fontSize={10} domain={['auto', 'auto']} tickLine={false} axisLine={false} />
                  <Tooltip
                    contentStyle={TOOLTIP_STYLE}
                    labelFormatter={fmtDay}
                    formatter={(value, name, item) =>
                      name === 'kg' && item?.payload?.estimated ? [`${value} (est.)`, name] : [value, name]
                    }
                  />
                  <Line type="monotone" dataKey="weight_kg" name="kg" stroke={SAGE} strokeWidth={1.5} dot={weightDot} />
                  <Line type="monotone" dataKey="avg_kg" name="7d avg" stroke={BONE} strokeWidth={2} strokeDasharray="6 4" dot={false} connectNulls />
                </LineChart>
              </ResponsiveContainer>
              {hasWeightEstimates && (
                <p className="muted" style={{ fontSize: '0.72rem', marginTop: 2, textAlign: 'center' }}>
                  Hollow points are interpolated estimates for days you didn't weigh in.
                </p>
              )}
              </>
            ) : (
              <EmptyNote />
            )}
          </div>

          {/* ---- Steps ---- */}
          <div className="card">
            <div className="row" style={{ marginBottom: '0.5rem' }}>
              <h3 style={{ margin: 0, flex: 1 }}>Steps</h3>
              <WidgetLabel>14 days</WidgetLabel>
            </div>
            {data.steps.length > 0 ? (
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={data.steps} margin={{ top: 8, right: 8, left: -14, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                  <XAxis dataKey="date" stroke={AXIS} fontSize={10} tickLine={false} axisLine={false} tickFormatter={fmtDay} minTickGap={20} />
                  <YAxis stroke={AXIS} fontSize={10} tickLine={false} axisLine={false} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} labelFormatter={fmtDay} cursor={{ fill: 'rgba(236,233,224,0.05)' }} />
                  <Bar dataKey="steps" name="steps" fill={MOSS} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <EmptyNote />
            )}
          </div>

          {/* ---- Sleep ---- */}
          <div className="card">
            <div className="row" style={{ marginBottom: '0.5rem' }}>
              <h3 style={{ margin: 0, flex: 1 }}>Sleep</h3>
              <WidgetLabel>hours · 14 nights</WidgetLabel>
            </div>
            {data.sleep.length > 0 ? (
              <ResponsiveContainer width="100%" height={160}>
                <BarChart data={data.sleep} margin={{ top: 8, right: 8, left: -14, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                  <XAxis dataKey="date" stroke={AXIS} fontSize={10} tickLine={false} axisLine={false} tickFormatter={fmtDay} minTickGap={20} />
                  <YAxis stroke={AXIS} fontSize={10} tickLine={false} axisLine={false} domain={[0, 'auto']} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} labelFormatter={fmtDay} cursor={{ fill: 'rgba(236,233,224,0.05)' }} />
                  <Bar dataKey="asleep_hours" name="h asleep" fill={SAGE} radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <EmptyNote />
            )}
          </div>

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

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

function EmptyNote({ children }) {
  return (
    <p className="muted" style={{ textAlign: 'center', padding: '1.1rem 0' }}>
      {children || <>No data yet. <Link to="/log">Log manually ›</Link></>}
    </p>
  )
}

// Uppercase tracked-out label used across widgets
function WidgetLabel({ children }) {
  return (
    <span className="muted" style={{ fontSize: '0.72rem', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
      {children}
    </span>
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

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
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
        return { date: p.date, weight_kg: p.weight_kg, avg_kg: avg ? avg.avg_kg : null }
      })
    : []

  const nut = data?.nutrition_today
  const targets = data?.targets

  return (
    <div className="page">
      {/* Editorial hero — quiet, dated, personal */}
      <span className="badge dot">{dateLabel}</span>
      <h1 style={{ fontSize: '2.4rem', marginTop: '0.9rem' }}>
        Good <em>{greeting}</em>
      </h1>
      <p className="muted" style={{ marginBottom: '1.5rem' }}>Here's where things stand.</p>

      <ErrorBox error={error} />
      {loading && <Loading />}

      {data && (
        <>
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
              </>
            ) : (
              <EmptyNote>Nothing logged today. <Link to="/log">Log manually ›</Link></EmptyNote>
            )}
          </div>

          {/* ---- Weight trend ---- */}
          <div className="card">
            <div className="row" style={{ marginBottom: '0.5rem' }}>
              <h3 style={{ margin: 0, flex: 1 }}>Weight</h3>
              <WidgetLabel>90 days · 7-day avg</WidgetLabel>
            </div>
            {weightData.length > 0 ? (
              <ResponsiveContainer width="100%" height={200}>
                <LineChart data={weightData} margin={{ top: 8, right: 8, left: -14, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                  <XAxis dataKey="date" stroke={AXIS} fontSize={10} tickLine={false} axisLine={false} tickFormatter={fmtDay} minTickGap={28} />
                  <YAxis stroke={AXIS} fontSize={10} domain={['auto', 'auto']} tickLine={false} axisLine={false} />
                  <Tooltip contentStyle={TOOLTIP_STYLE} labelFormatter={fmtDay} />
                  <Line type="monotone" dataKey="weight_kg" name="kg" stroke={SAGE} strokeWidth={1.5} dot={{ r: 2, fill: SAGE, strokeWidth: 0 }} />
                  <Line type="monotone" dataKey="avg_kg" name="7d avg" stroke={BONE} strokeWidth={2} strokeDasharray="6 4" dot={false} connectNulls />
                </LineChart>
              </ResponsiveContainer>
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
        </>
      )}
    </div>
  )
}

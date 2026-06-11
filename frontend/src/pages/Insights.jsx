/**
 * Insights (Phase 7) — what the data says.
 * - Weekly review: this week vs last, neutral deltas (no good/bad colors;
 *   the reader knows which direction they wanted).
 * - Correlations: Pearson r over the last 90 days; tap a pair for the
 *   scatter. Honest by construction: pairs need ≥10 overlapping days and
 *   the caveat is printed right on the card.
 * - Training-day splits: scale trackers (e.g. Mood) on training vs rest days.
 */
import React, { useEffect, useState } from 'react'
import {
  ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { apiFetch } from '../api'
import { Loading, ErrorBox } from '../components/States'

const GRID = 'rgba(236,233,224,0.07)'
const AXIS = '#9aa69b'
const SAGE = '#a8bfa1'
const TOOLTIP_STYLE = {
  background: '#1d2521',
  border: '1px solid rgba(236,233,224,0.12)',
  borderRadius: 12,
  color: '#ece9e0',
}

function WidgetLabel({ children }) {
  return (
    <span className="muted" style={{ fontSize: '0.72rem', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
      {children}
    </span>
  )
}

// Neutral delta: direction without judgment
function Delta({ cur, prev, digits = 0, suffix = '' }) {
  if (cur == null || prev == null) return <span className="muted">—</span>
  const diff = cur - prev
  if (Math.abs(diff) < 0.5 / 10 ** digits) return <span className="muted">·</span>
  const arrow = diff > 0 ? '▲' : '▼'
  return (
    <span className="muted tnum" style={{ fontSize: '0.75rem' }}>
      {arrow} {Math.abs(diff).toFixed(digits)}{suffix}
    </span>
  )
}

function strength(r) {
  const a = Math.abs(r)
  if (a < 0.2) return 'no real relationship'
  if (a < 0.4) return 'weak'
  if (a < 0.7) return 'moderate'
  return 'strong'
}

// Signed bar centered at zero: sage right for positive, terracotta left for negative
function RBar({ r }) {
  const pct = Math.min(Math.abs(r), 1) * 50
  return (
    <div style={{ position: 'relative', width: 110, height: 5, background: 'var(--color-surface2)', borderRadius: 999 }}>
      <div
        style={{
          position: 'absolute',
          top: 0,
          bottom: 0,
          left: r >= 0 ? '50%' : `${50 - pct}%`,
          width: `${pct}%`,
          background: r >= 0 ? 'var(--color-accent)' : 'var(--color-danger)',
          borderRadius: 999,
        }}
      />
      <div style={{ position: 'absolute', left: '50%', top: -2, bottom: -2, width: 1, background: 'var(--color-border-str)' }} />
    </div>
  )
}

export default function Insights() {
  const [weekly, setWeekly] = useState(null)
  const [corr, setCorr] = useState(null)
  const [selected, setSelected] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([
      apiFetch('/api/insights/weekly'),
      apiFetch('/api/insights/correlations'),
    ])
      .then(([w, c]) => { setWeekly(w); setCorr(c) })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  const cur = weekly?.current
  const prev = weekly?.previous

  // Row config for the review table; null-safe formatting
  const rows = cur ? [
    { label: 'Training volume', cur: cur.volume_kg, prev: prev.volume_kg, fmt: v => `${Math.round(v).toLocaleString()} kg`, digits: 0 },
    { label: 'Sessions', cur: cur.sessions, prev: prev.sessions, fmt: v => v, digits: 0 },
    { label: 'Steps / day', cur: cur.steps_avg, prev: prev.steps_avg, fmt: v => v.toLocaleString(), digits: 0 },
    { label: 'Sleep / night', cur: cur.sleep_avg_h, prev: prev.sleep_avg_h, fmt: v => `${v} h`, digits: 1 },
    { label: 'Calories / day', cur: cur.calories_avg, prev: prev.calories_avg, fmt: v => v.toLocaleString(), digits: 0 },
    { label: 'Protein / day', cur: cur.protein_avg_g, prev: prev.protein_avg_g, fmt: v => `${v} g`, digits: 0 },
    { label: 'Weight change', cur: cur.weight_change_kg, prev: prev.weight_change_kg, fmt: v => `${v > 0 ? '+' : ''}${v} kg`, digits: 1 },
    ...cur.scales.map((s, i) => ({
      label: `${s.name} (avg)`, cur: s.avg, prev: prev.scales[i]?.avg, fmt: v => `${v} / 5`, digits: 1,
    })),
  ] : []

  const pair = corr?.pairs[selected]

  return (
    <div className="page">
      <h1>What the data <em>says</em></h1>
      <p className="muted" style={{ marginBottom: '1.25rem' }}>
        This week against last, and which numbers move together.
      </p>

      <ErrorBox error={error} />
      {loading && <Loading />}

      {/* ---- Weekly review ---- */}
      {weekly && (
        <div className="card">
          <div className="row" style={{ marginBottom: '0.6rem' }}>
            <h3 style={{ margin: 0, flex: 1 }}>This week vs last</h3>
            <WidgetLabel>7-day windows</WidgetLabel>
          </div>

          <div className="row" style={{ padding: '0.2rem 0', borderBottom: '1px solid var(--color-border)' }}>
            <span style={{ flex: 1 }} />
            <WidgetLabel>this week</WidgetLabel>
            <span style={{ width: 86, textAlign: 'right' }}><WidgetLabel>last week</WidgetLabel></span>
            <span style={{ width: 70 }} />
          </div>

          {rows.map(rw => (
            <div key={rw.label} className="row" style={{ padding: '0.4rem 0', borderBottom: '1px solid var(--color-border)' }}>
              <span style={{ flex: 1, fontSize: '0.88rem' }}>{rw.label}</span>
              <span className="tnum" style={{ fontSize: '0.92rem' }}>
                {rw.cur == null ? <span className="muted">—</span> : rw.fmt(rw.cur)}
              </span>
              <span className="tnum muted" style={{ width: 86, textAlign: 'right', fontSize: '0.82rem' }}>
                {rw.prev == null ? '—' : rw.fmt(rw.prev)}
              </span>
              <span style={{ width: 70, textAlign: 'right' }}>
                <Delta cur={rw.cur} prev={rw.prev} digits={rw.digits} />
              </span>
            </div>
          ))}

          {cur.habits.length > 0 && (
            <div style={{ marginTop: '0.6rem' }}>
              <WidgetLabel>habits</WidgetLabel>
              {cur.habits.map((h, i) => (
                <div key={h.name} className="row" style={{ padding: '0.35rem 0' }}>
                  <span style={{ flex: 1, fontSize: '0.88rem' }}>{h.name}</span>
                  <span className="tnum" style={{ fontSize: '0.92rem' }}>{h.done}/{h.days}</span>
                  <span className="tnum muted" style={{ width: 86, textAlign: 'right', fontSize: '0.82rem' }}>
                    {prev.habits[i] ? `${prev.habits[i].done}/${prev.habits[i].days}` : '—'}
                  </span>
                  <span style={{ width: 70 }} />
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* ---- Training-day splits ---- */}
      {corr && corr.training_splits.length > 0 && (
        <div className="card">
          <h3 style={{ marginBottom: '0.5rem' }}>On training days</h3>
          {corr.training_splits.map(s => (
            <p key={s.name} style={{ fontSize: '0.92rem', margin: '0.25rem 0' }}>
              {s.name} averages <span className="tnum" style={{ fontWeight: 600 }}>{s.with_avg}</span> on
              training days against <span className="tnum" style={{ fontWeight: 600 }}>{s.without_avg}</span> on
              rest days
              <span className="muted" style={{ fontSize: '0.78rem' }}> · {s.n_with}/{s.n_without} days</span>
            </p>
          ))}
        </div>
      )}

      {/* ---- Correlations ---- */}
      {corr && (
        <div className="card">
          <div className="row" style={{ marginBottom: '0.6rem' }}>
            <h3 style={{ margin: 0, flex: 1 }}>Moving together</h3>
            <WidgetLabel>last {corr.window_days} days</WidgetLabel>
          </div>

          {corr.pairs.length === 0 ? (
            <p className="muted" style={{ textAlign: 'center', padding: '1rem 0' }}>
              Not enough overlapping data yet — insights need a couple of
              weeks of logging. Keep going.
            </p>
          ) : (
            <>
              {corr.pairs.map((p, i) => (
                <button
                  key={`${p.label_a}-${p.label_b}`}
                  onClick={() => setSelected(i)}
                  style={{
                    display: 'flex', alignItems: 'center', gap: '0.6rem', width: '100%',
                    background: i === selected ? 'rgba(236,233,224,0.06)' : 'transparent',
                    border: 'none', boxShadow: 'none', borderRadius: 10,
                    padding: '0.45rem 0.6rem', minHeight: 0,
                    color: 'var(--color-text)', fontWeight: 400, textAlign: 'left',
                  }}
                >
                  <span style={{ flex: 1, fontSize: '0.88rem' }}>
                    {p.label_a} <span className="muted">×</span> {p.label_b}
                  </span>
                  <RBar r={p.r} />
                  <span className="tnum muted" style={{ width: 76, textAlign: 'right', fontSize: '0.78rem' }}>
                    r {p.r > 0 ? '+' : ''}{p.r.toFixed(2)}
                  </span>
                </button>
              ))}

              {pair && (
                <div style={{ marginTop: '0.75rem' }}>
                  <p className="muted" style={{ fontSize: '0.8rem', marginBottom: '0.4rem' }}>
                    {pair.label_a} × {pair.label_b}: {strength(pair.r)}
                    {Math.abs(pair.r) >= 0.2 ? ` ${pair.r > 0 ? 'positive' : 'negative'}` : ''} ·
                    {' '}{pair.n} days
                  </p>
                  <ResponsiveContainer width="100%" height={220}>
                    <ScatterChart margin={{ top: 8, right: 8, left: -10, bottom: 0 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke={GRID} />
                      <XAxis
                        type="number" dataKey="a" name={pair.label_a}
                        stroke={AXIS} fontSize={10} tickLine={false} axisLine={false}
                        domain={['auto', 'auto']}
                      />
                      <YAxis
                        type="number" dataKey="b" name={pair.label_b}
                        stroke={AXIS} fontSize={10} tickLine={false} axisLine={false}
                        domain={['auto', 'auto']}
                      />
                      <Tooltip
                        contentStyle={TOOLTIP_STYLE}
                        cursor={{ stroke: 'rgba(236,233,224,0.2)' }}
                        formatter={(value, name) => [value, name]}
                        labelFormatter={() => ''}
                      />
                      <Scatter data={pair.points} fill={SAGE} fillOpacity={0.75} />
                    </ScatterChart>
                  </ResponsiveContainer>
                </div>
              )}

              <p className="muted" style={{ fontSize: '0.72rem', marginTop: '0.5rem' }}>
                Correlation, not causation — and small samples lie. Pairs need
                at least 10 overlapping days to appear.
              </p>
            </>
          )}
        </div>
      )}
    </div>
  )
}

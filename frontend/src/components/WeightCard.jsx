/**
 * WeightCard — the dashboard's weight trend, styled after a health-app
 * "heart rate" card: a big current number up top, a range chip in the corner,
 * and a clean line (no grid, no Y axis) that ends in a glowing "now" point.
 *
 * Data comes straight from the dashboard payload (90 days, already loaded):
 *   series        [{date, weight_kg, estimated}]   estimated = interpolated day
 *   moving_avg_7d [{date, avg_kg}]
 * The range chip (7D / 30D / 90D) only slices what's there — no extra fetch.
 *
 * Honesty rule (CLAUDE.md): the big number and the "now" dot always come from a
 * REAL weigh-in. Interpolated days are drawn as hollow rings and never headline.
 */
import React, { useMemo, useState } from 'react'
import {
  Area, ComposedChart, Line, ResponsiveContainer, Tooltip, XAxis, YAxis,
} from 'recharts'
import { AXIS, BONE, KHAKI, SAGE, TOOLTIP_STYLE, fmtDay } from '../chartTheme'
import { NoHealthDataNote } from './States'
import WidgetLabel from './WidgetLabel'

export const RANGES = [7, 30, 90]
const DEFAULT_RANGE = 30
const STORAGE_KEY = 'weight_range_days'

/** Merge the weight series with its 7-day average, oldest → newest. */
export function mergeWeight(weight) {
  if (!weight?.series) return []
  const avgByDate = new Map((weight.moving_avg_7d || []).map(a => [a.date, a.avg_kg]))
  return weight.series
    .map(p => ({
      date: p.date,
      weight_kg: p.weight_kg,
      avg_kg: avgByDate.get(p.date) ?? null,
      estimated: !!p.estimated,
    }))
    .sort((a, b) => (a.date < b.date ? -1 : 1))
}

const DAY_MS = 86400000
const toDay = iso => Date.parse(iso + 'T00:00:00Z') / DAY_MS

/** Keep the last `days` calendar days, counted back from the newest point. */
export function sliceRange(points, days) {
  if (!points.length) return []
  const last = toDay(points[points.length - 1].date)
  return points.filter(p => last - toDay(p.date) < days)
}

/** Headline numbers for a (sliced) series — real weigh-ins only. */
export function summarize(points) {
  const real = points.filter(p => !p.estimated && p.weight_kg != null)
  if (!real.length) return null
  const latest = real[real.length - 1]
  const first = real[0]
  const withAvg = points.filter(p => p.avg_kg != null)
  return {
    latest,
    avg: withAvg.length ? withAvg[withAvg.length - 1].avg_kg : null,
    change: real.length > 1 ? Math.round((latest.weight_kg - first.weight_kg) * 10) / 10 : null,
  }
}

function readRange() {
  try {
    const n = Number(localStorage.getItem(STORAGE_KEY))
    return RANGES.includes(n) ? n : DEFAULT_RANGE
  } catch { return DEFAULT_RANGE }
}

const prefersReducedMotion = () =>
  typeof window !== 'undefined' &&
  !!window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

export default function WeightCard({ weight }) {
  const [range, setRange] = useState(readRange)
  const all = useMemo(() => mergeWeight(weight), [weight])
  const points = useMemo(() => sliceRange(all, range), [all, range])
  const summary = useMemo(() => summarize(points), [points])
  const animate = !prefersReducedMotion()

  function cycleRange() {
    const next = RANGES[(RANGES.indexOf(range) + 1) % RANGES.length]
    setRange(next)
    try { localStorage.setItem(STORAGE_KEY, String(next)) } catch { /* private mode */ }
  }

  const nowDate = summary?.latest.date
  const hasEstimates = points.some(p => p.estimated)

  // Dots: hollow ring for an estimated day, a glowing "now" on the latest real
  // weigh-in, nothing for the rest (the line carries them).
  const renderDot = ({ cx, cy, payload, index }) => {
    if (cx == null || cy == null) return null
    if (payload.date === nowDate) {
      return (
        <g key={index}>
          <circle cx={cx} cy={cy} r={9} fill={KHAKI} opacity={0.16} />
          <circle cx={cx} cy={cy} r={5} fill={KHAKI} opacity={0.32} />
          <circle cx={cx} cy={cy} r={3.2} fill={KHAKI} stroke={BONE} strokeWidth={1.2} />
        </g>
      )
    }
    if (payload.estimated) {
      return <circle key={index} cx={cx} cy={cy} r={2.2} fill="none" stroke={SAGE} strokeWidth={1} strokeOpacity={0.55} />
    }
    return <g key={index} />
  }

  // About five evenly spaced date labels; the newest reads "NOW".
  const ticks = useMemo(() => {
    if (points.length < 2) return points.map(p => p.date)
    const n = Math.min(5, points.length)
    const out = []
    for (let i = 0; i < n; i++) out.push(points[Math.round((i * (points.length - 1)) / (n - 1))].date)
    return [...new Set(out)]
  }, [points])
  const lastDate = points.length ? points[points.length - 1].date : null
  const tickFormatter = d => (d === lastDate ? 'NOW' : fmtDay(d))

  const firstDate = points.length ? points[0].date : null
  const renderTick = ({ x, y, payload }) => {
    const isNow = payload.value === lastDate
    // Pin the end labels inside the card so neither gets clipped
    const anchor = isNow ? 'end' : payload.value === firstDate ? 'start' : 'middle'
    return (
      <text x={x} y={y + 12} textAnchor={anchor} fontSize={10}
        fill={isNow ? SAGE : AXIS} fontWeight={isNow ? 700 : 500} letterSpacing="0.06em">
        {tickFormatter(payload.value)}
      </text>
    )
  }

  return (
    <div className="card span-2 weight-card">
      <div className="weight-card-head">
        <WidgetLabel>⚖ Weight</WidgetLabel>
        <button type="button" className="range-chip" onClick={cycleRange}
          aria-label={`Showing ${range} days. Tap to change range.`}>
          {range}D
        </button>
      </div>

      {summary ? (
        <>
          <div className="weight-card-figure">
            <span className="stat-num weight-card-num" data-testid="weight-latest">
              {summary.latest.weight_kg.toFixed(1)}
            </span>
            <span className="weight-card-unit">
              kg{summary.avg != null && <> · 7-day avg <span className="tnum">{summary.avg.toFixed(1)}</span></>}
            </span>
          </div>
          {summary.change != null && (
            <div className="weight-card-change tnum" data-testid="weight-change">
              {summary.change === 0 ? '— no change' : `${summary.change < 0 ? '▼' : '▲'} ${Math.abs(summary.change).toFixed(1)} kg`}
              <span className="muted"> · last {range} days</span>
            </div>
          )}

          <div className="weight-card-chart">
            <ResponsiveContainer width="100%" height={170}>
              <ComposedChart data={points} margin={{ top: 14, right: 12, left: 12, bottom: 4 }}>
                <defs>
                  <linearGradient id="weightFill" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor={SAGE} stopOpacity={0.22} />
                    <stop offset="100%" stopColor={SAGE} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis dataKey="date" ticks={ticks} interval={0} tick={renderTick}
                  tickLine={false} axisLine={false} height={22} />
                {/* Hidden: without a Y axis Recharts scales from 0 kg and the
                    line goes flat. Fit it to the data with a little headroom. */}
                <YAxis hide domain={[min => Math.floor((min - 0.4) * 2) / 2, max => Math.ceil((max + 0.4) * 2) / 2]} />
                <Tooltip
                  contentStyle={TOOLTIP_STYLE}
                  labelFormatter={fmtDay}
                  cursor={{ stroke: 'rgba(241, 234, 217,0.18)', strokeWidth: 1 }}
                  formatter={(value, name, item) =>
                    name === 'kg' && item?.payload?.estimated ? [`${value} (est.)`, name] : [value, name]
                  }
                />
                <Area type="monotone" dataKey="weight_kg" name="kg" stroke={SAGE} strokeWidth={2}
                  fill="url(#weightFill)" dot={renderDot} activeDot={{ r: 4, fill: BONE, stroke: SAGE }}
                  baseValue="dataMin" isAnimationActive={animate} animationDuration={700} animationEasing="ease-out" />
                <Line type="monotone" dataKey="avg_kg" name="7d avg" stroke={BONE} strokeOpacity={0.45}
                  strokeWidth={1.5} strokeDasharray="4 4" dot={false} activeDot={false} connectNulls
                  isAnimationActive={animate} animationDuration={700} animationEasing="ease-out" />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
          {hasEstimates && (
            <p className="muted" style={{ fontSize: '0.72rem', marginTop: 2, textAlign: 'center' }}>
              Hollow points are interpolated estimates for days you didn't weigh in.
            </p>
          )}
        </>
      ) : (
        <NoHealthDataNote metric="weight readings" />
      )}
    </div>
  )
}

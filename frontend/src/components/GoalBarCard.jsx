/**
 * GoalBarCard — a daily "fill the bar" chart (used for Steps and Sleep).
 *
 * Each day is a rounded track the height of the daily goal. The day's value
 * fills it from the bottom; anything past the goal keeps growing above the
 * track in a lighter green, so a big day visibly "overflows" its bar.
 *
 * Header: label + a 30D / 60D / 90D chip (same pattern as the weight card),
 * the average per day over the range, and how many days hit the goal.
 * Tap / hover a bar to read that day's value.
 *
 * Data: `points` = [{date: 'YYYY-MM-DD', value: number}] — the dashboard sends
 * 90 days; this component only slices it. Days with no reading show an empty
 * track and are left out of the average (missing ≠ zero).
 */
import React, { useMemo, useState } from 'react'
import { fmtDay } from '../chartTheme'
import WidgetLabel from './WidgetLabel'

export const RANGES = [30, 60, 90]
const DEFAULT_RANGE = 30

const FILL = '#809076'        // under/at goal — deep green
const OVER = '#c2d69a'        // the part above the goal — bright lime, clearly different
const TRACK = 'rgba(241, 234, 217,0.11)'

function localTodayIso() {
  const d = new Date()
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

function addDaysIso(iso, n) {
  const t = Date.parse(iso + 'T00:00:00Z') + n * 86400000
  return new Date(t).toISOString().slice(0, 10)
}

/** One entry per calendar day, oldest → newest, ending `endIso`. */
export function buildDays(points, days, endIso = localTodayIso()) {
  const byDate = new Map((points || []).map(p => [String(p.date), p.value]))
  const out = []
  for (let i = days - 1; i >= 0; i--) {
    const date = addDaysIso(endIso, -i)
    const v = byDate.get(date)
    out.push({ date, value: v == null ? null : Number(v) })
  }
  return out
}

/** Average over days that HAVE a reading, plus goal hits. */
export function summarizeDays(days, goal) {
  const real = days.filter(d => d.value != null)
  if (!real.length) return null
  const total = real.reduce((a, d) => a + d.value, 0)
  return {
    avg: total / real.length,
    logged: real.length,
    hits: real.filter(d => d.value >= goal).length,
  }
}

function readRange(key) {
  try {
    const n = Number(localStorage.getItem(key))
    return RANGES.includes(n) ? n : DEFAULT_RANGE
  } catch { return DEFAULT_RANGE }
}

const W = 340, H = 150, TOP = 6, LABEL_H = 18

export default function GoalBarCard({
  label, points, goal, unit, formatValue, formatAvg = formatValue,
  goalLabel, storageKey, empty, onLog,
}) {
  const [range, setRange] = useState(() => readRange(storageKey))
  const [active, setActive] = useState(null)       // index of the bar being read

  const days = useMemo(() => buildDays(points, range), [points, range])
  const summary = useMemo(() => summarizeDays(days, goal), [days, goal])

  function cycleRange() {
    const next = RANGES[(RANGES.indexOf(range) + 1) % RANGES.length]
    setRange(next)
    setActive(null)
    try { localStorage.setItem(storageKey, String(next)) } catch { /* private mode */ }
  }

  // Vertical scale: the goal sits at ~70% of the plot, so overflow has room;
  // a monster day stretches the scale up to 2× goal, then clips.
  const maxVal = Math.max(...days.map(d => d.value ?? 0), 0)
  const scaleMax = Math.min(goal * 2, Math.max(goal * 1.4, maxVal * 1.04))
  const plotH = H - TOP - LABEL_H
  const y = v => TOP + plotH - (Math.min(v, scaleMax) / scaleMax) * plotH
  const baseY = TOP + plotH
  const goalY = y(goal)

  const PLOT_W = W - 24        // right gutter for the goal label
  const slot = PLOT_W / days.length
  const barW = Math.max(2, Math.min(14, slot * 0.6))
  const r = barW / 2

  function pick(e) {
    const box = e.currentTarget.getBoundingClientRect()
    const x = ((e.clientX - box.left) / box.width) * W
    setActive(Math.max(0, Math.min(days.length - 1, Math.floor(x / slot))))
  }

  const sel = active != null ? days[active] : null
  const labelIdx = [0, Math.floor((days.length - 1) / 2), days.length - 1]

  return (
    <div className="card goal-card">
      <div className="weight-card-head">
        <WidgetLabel>{label}</WidgetLabel>
        <span className="card-head-actions">
          {onLog && <button type="button" className="range-chip log-chip" onClick={onLog} aria-label={`Log ${unit === 'steps' ? 'steps' : 'sleep'}`}>+ Log</button>}
          <button type="button" className="range-chip" onClick={cycleRange}
            aria-label={`Showing ${range} days. Tap to change range.`}>
            {range}D
          </button>
        </span>
      </div>

      {summary ? (
        <>
          <div className="weight-card-figure" aria-live="polite">
            {sel ? (
              <>
                <span className="stat-num weight-card-num">{sel.value == null ? '—' : formatValue(sel.value)}</span>
                <span className="weight-card-unit">{unit} · {fmtDay(sel.date)}</span>
              </>
            ) : (
              <>
                <span className="stat-num weight-card-num" data-testid="goal-avg">{formatAvg(summary.avg)}</span>
                <span className="weight-card-unit">{unit} / day · avg</span>
              </>
            )}
          </div>
          <div className="weight-card-change tnum" data-testid="goal-hits">
            {summary.hits} of {summary.logged} days ≥ {goalLabel}
            <span className="muted"> · last {range} days</span>
          </div>

          <svg key={range} className="goal-chart" viewBox={`0 0 ${W} ${H}`} role="img"
            aria-label={`${label}: average ${formatAvg(summary.avg)} ${unit} per day over ${range} days; goal ${goalLabel} hit on ${summary.hits} days.`}
            onPointerMove={pick} onPointerDown={pick} onPointerLeave={() => setActive(null)}>
            {days.map((d, i) => {
              const x = i * slot + (slot - barW) / 2
              const v = d.value ?? 0
              const fillTop = y(Math.min(v, goal))
              const dim = active != null && active !== i ? 0.45 : 1
              return (
                <g key={d.date} opacity={dim}>
                  <rect x={x} y={goalY} width={barW} height={baseY - goalY} rx={r} fill={TRACK} />
                  {v > 0 && (
                    <g className="goal-bar-grow">
                      <rect x={x} y={fillTop} width={barW} height={Math.max(barW, baseY - fillTop)} rx={r} fill={FILL} />
                      {v > goal && (
                        // overflow: from slightly inside the goal fill up to the value
                        <rect x={x} y={y(v)} width={barW} height={Math.max(barW, goalY - y(v) + r)} rx={r} fill={OVER} />
                      )}
                    </g>
                  )}
                </g>
              )
            })}
            {/* faint goal line + label */}
            <line x1="0" x2={W - 22} y1={goalY} y2={goalY} stroke="rgba(241, 234, 217,0.22)"
              strokeWidth="1" strokeDasharray="2 3" />
            <text x={W} y={goalY + 3.5} textAnchor="end" fontSize="9.5" fontWeight="700" fill="#93a08c">{goalLabel}</text>
            {labelIdx.map((i, k) => (
              <text key={i} x={k === 0 ? 0 : k === 2 ? PLOT_W : i * slot + slot / 2} y={H - 3}
                textAnchor={k === 0 ? 'start' : k === 2 ? 'end' : 'middle'}
                fontSize="10" fontWeight={k === 2 ? 700 : 500} letterSpacing="0.06em"
                fill={k === 2 ? '#9db08f' : '#93a08c'}>
                {k === 2 ? 'TODAY' : fmtDay(days[i].date)}
              </text>
            ))}
          </svg>

          <div className="goal-legend">
            <span><i style={{ background: FILL }} /> up to {goalLabel}</span>
            <span><i style={{ background: OVER }} /> over goal</span>
          </div>
        </>
      ) : (
        empty
      )}
    </div>
  )
}

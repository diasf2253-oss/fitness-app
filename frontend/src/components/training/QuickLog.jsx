/**
 * Quick-log sheet — log today's weight, steps or sleep in one or two taps.
 *
 * Apple Health sync is paused (a web app can't read HealthKit, and the Shortcut
 * route wasn't seamless), so manual entry is the data path. This sheet is the
 * fast lane; pages/Log.jsx stays as the full form (nutrition, in-bed time).
 *
 * Usage (no hook needed):  openQuickLog('weight' | 'steps' | 'sleep')
 * <QuickLogHost /> is mounted once in App.jsx.
 *
 * Saves go to the existing date-keyed upserts (POST /api/health/weight|steps|
 * sleep, source='manual'; offline twins in src/local/api/health.js), then fire
 * HEALTH_DATA_CHANGED so the dashboard and the weigh-in nudge refresh.
 */
import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../../lib/api'
import { parseDecimal } from '../../lib/num'
import Modal from '../ui/Modal'

export const HEALTH_DATA_CHANGED = 'health-data-changed'
const METRICS = [
  { key: 'weight', label: 'Weight' },
  { key: 'steps', label: 'Steps' },
  { key: 'sleep', label: 'Sleep' },
]

let showSheet = null   // set by the mounted <QuickLogHost>

export function openQuickLog(metric = 'weight') {
  showSheet?.(metric)
}

function localIso(offsetDays = 0) {
  const d = new Date()
  d.setDate(d.getDate() + offsetDays)
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

const round1 = n => Math.round(n * 10) / 10

function Stepper({ label, onStep, children }) {
  return (
    <div className="ql-stepper">
      <button type="button" className="ql-step" onClick={() => onStep(-1)} aria-label={`Decrease ${label}`}>−</button>
      {children}
      <button type="button" className="ql-step" onClick={() => onStep(1)} aria-label={`Increase ${label}`}>+</button>
    </div>
  )
}

/** The sheet's body — exported for tests. */
export function QuickLogForm({ initialMetric = 'weight', onDone }) {
  const [metric, setMetric] = useState(initialMetric)
  const [date, setDate] = useState(localIso(0))
  const [weight, setWeight] = useState('')
  const [weightEstimated, setWeightEstimated] = useState(false)
  const [steps, setSteps] = useState('')
  const [sleepH, setSleepH] = useState('7')
  const [sleepM, setSleepM] = useState('30')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [saved, setSaved] = useState(false)

  // Prefill weight with the day's reading — or, for a day never tracked, the
  // interpolated estimate (flagged), exactly like pages/Log.jsx.
  useEffect(() => {
    let cancelled = false
    apiFetch(`/api/health/weight/estimate?date=${date}`)
      .then(r => {
        if (cancelled) return
        setWeight(r?.weight_kg != null ? String(r.weight_kg) : '')
        setWeightEstimated(r?.weight_kg != null && !!r.estimated)
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [date])

  function stepWeight(dir) {
    const base = parseDecimal(weight) ?? 0
    setWeight(String(round1(Math.max(0, base + dir * 0.1))))
    setWeightEstimated(false)
  }

  function stepSleep(dir) {
    const total = Math.max(0, Math.min(24 * 60, (Number(sleepH) || 0) * 60 + (Number(sleepM) || 0) + dir * 15))
    setSleepH(String(Math.floor(total / 60)))
    setSleepM(String(total % 60).padStart(2, '0'))
  }

  function request() {
    if (metric === 'weight') {
      const kg = parseDecimal(weight)
      if (kg == null || kg <= 0) throw new Error('Enter a weight first')
      return ['/api/health/weight', {
        date, weight_kg: kg, source: weightEstimated ? 'estimated' : 'manual',
      }]
    }
    if (metric === 'steps') {
      const n = parseDecimal(steps)
      if (n == null || n < 0) throw new Error('Enter a step count first')
      return ['/api/health/steps', { date, steps: Math.round(n) }]
    }
    const minutes = (Number(sleepH) || 0) * 60 + (Number(sleepM) || 0)
    if (minutes <= 0) throw new Error('Enter how long you slept')
    // In-bed time defaults to asleep time (same rule as the full log page)
    return ['/api/health/sleep', { date, asleep_minutes: minutes, in_bed_minutes: minutes }]
  }

  async function save(e) {
    e?.preventDefault()
    setError(null)
    let path, body
    try { [path, body] = request() } catch (err) { setError(err.message); return }
    setBusy(true)
    try {
      await apiFetch(path, { method: 'POST', body: JSON.stringify(body) })
      window.dispatchEvent(new Event(HEALTH_DATA_CHANGED))
      setSaved(true)
      setTimeout(() => onDone?.(), 650)
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  const isToday = date === localIso(0)
  const isYesterday = date === localIso(-1)

  return (
    <form onSubmit={save} className="col" style={{ gap: '0.9rem' }}>
      <div className="ql-tabs" role="tablist" aria-label="What to log">
        {METRICS.map(m => (
          <button key={m.key} type="button" role="tab" aria-selected={metric === m.key}
            className={`ql-tab${metric === m.key ? ' on' : ''}`}
            onClick={() => { setMetric(m.key); setError(null) }}>
            {m.label}
          </button>
        ))}
      </div>

      <div className="row" style={{ gap: '0.4rem', flexWrap: 'wrap' }}>
        <button type="button" className={`range-chip${isToday ? ' on' : ''}`} onClick={() => setDate(localIso(0))}>Today</button>
        <button type="button" className={`range-chip${isYesterday ? ' on' : ''}`} onClick={() => setDate(localIso(-1))}>Yesterday</button>
        <input type="date" aria-label="Day" className="ql-date" value={date} max={localIso(0)}
          onChange={e => e.target.value && setDate(e.target.value)} />
      </div>

      {metric === 'weight' && (
        <div>
          <Stepper label="weight by 0.1 kg" onStep={stepWeight}>
            <div className="ql-big">
              <input aria-label="Weight in kg" className="ql-input" type="text" inputMode="decimal"
                placeholder="80.0" value={weight}
                onChange={e => { setWeight(e.target.value); setWeightEstimated(false) }} />
              <span className="ql-unit">kg</span>
            </div>
          </Stepper>
          {weightEstimated && (
            <p className="muted ql-hint">≈ estimated from nearby days — nudge it or type your real weight</p>
          )}
        </div>
      )}

      {metric === 'steps' && (
        <div className="ql-big">
          <input aria-label="Steps" className="ql-input" type="number" inputMode="numeric"
            placeholder="9000" value={steps} onChange={e => setSteps(e.target.value)} autoFocus />
          <span className="ql-unit">steps</span>
        </div>
      )}

      {metric === 'sleep' && (
        <Stepper label="sleep by 15 minutes" onStep={stepSleep}>
          <div className="ql-big">
            <input aria-label="Hours asleep" className="ql-input ql-input-sm" type="number" inputMode="numeric"
              min="0" max="24" value={sleepH} onChange={e => setSleepH(e.target.value)} />
            <span className="ql-unit">h</span>
            <input aria-label="Minutes asleep" className="ql-input ql-input-sm" type="number" inputMode="numeric"
              min="0" max="59" value={sleepM} onChange={e => setSleepM(e.target.value)} />
            <span className="ql-unit">m</span>
          </div>
        </Stepper>
      )}

      {error && <p className="set-error" role="alert" style={{ padding: 0 }}>{error}</p>}

      <button type="submit" disabled={busy || saved} style={{ width: '100%' }}>
        {saved ? '✓ Saved' : busy ? 'Saving…' : `Save ${metric}`}
      </button>
      <Link to={`/log?date=${date}`} className="muted ql-more" onClick={() => onDone?.()}>
        More options (nutrition, in-bed time) ›
      </Link>
    </form>
  )
}

export function QuickLogHost() {
  const [metric, setMetric] = useState(null)
  useEffect(() => {
    showSheet = m => setMetric(m)
    return () => { showSheet = null }
  }, [])
  if (!metric) return null
  return (
    <Modal title="Quick log" onClose={() => setMetric(null)}>
      <QuickLogForm key={metric} initialMetric={metric} onDone={() => setMetric(null)} />
    </Modal>
  )
}

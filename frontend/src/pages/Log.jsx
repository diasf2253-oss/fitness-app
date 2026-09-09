/**
 * Log — manual entry/correction for a day's health data (Phase 2).
 * Pick a date, then save weight, steps, sleep, or nutrition. Saves are
 * date-keyed upserts with source='manual', so correcting a day is just
 * re-saving it (last write wins). From Phase 3 the same tables fill
 * automatically from Apple Health.
 */
import React, { useEffect, useState } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../api'
import { ErrorBox } from '../components/States'
import { parseDecimal } from '../num'

// Local calendar date (toISOString alone would shift near midnight)
function localToday() {
  const d = new Date()
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

/**
 * Card wrapper with a Save button that reflects request state.
 * `onSave` must return a promise (the apiFetch call).
 */
function LogCard({ title, onSave, children }) {
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState(null)

  async function handleSave() {
    setSaving(true)
    setError(null)
    try {
      await onSave()
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err) {
      setError(err.message)
    } finally {
      setSaving(false)
    }
  }

  return (
    <div className="card">
      <div className="row">
        <h3 style={{ flex: 1, margin: 0 }}>{title}</h3>
        <button onClick={handleSave} disabled={saving} style={{ minWidth: 92, padding: '0.45rem 1rem' }}>
          {saved ? 'Saved ✓' : saving ? 'Saving…' : 'Save'}
        </button>
      </div>
      <ErrorBox error={error} />
      <div className="col" style={{ marginTop: '0.6rem' }}>{children}</div>
    </div>
  )
}

function Field({ label, children }) {
  return (
    <div className="form-group" style={{ margin: 0 }}>
      <label>{label}</label>
      {children}
    </div>
  )
}

export default function Log() {
  const navigate = useNavigate()
  // The dashboard calendar links here with ?date=YYYY-MM-DD ("Edit ›")
  const [searchParams] = useSearchParams()
  const [date, setDate] = useState(searchParams.get('date') || localToday())

  const [weight, setWeight] = useState('')
  const [weightEstimated, setWeightEstimated] = useState(false)
  const [steps, setSteps] = useState('')
  const [asleepH, setAsleepH] = useState('')
  const [inBedH, setInBedH] = useState('')
  const [calories, setCalories] = useState('')
  const [protein, setProtein] = useState('')
  const [carbs, setCarbs] = useState('')
  const [fat, setFat] = useState('')

  const required = (value, name) => {
    const n = parseDecimal(value)
    if (n === null) throw new Error(`Enter ${name} first`)
    return n
  }

  // Prefill the weight field with the day's real reading, or — for a day
  // never tracked — an interpolated estimate flagged as such. Refetches when
  // the date changes; typing a value clears the "estimate" flag.
  // (apiFetch serves this from the on-device DB in local-first mode.)
  useEffect(() => {
    let cancelled = false
    apiFetch(`/api/health/weight/estimate?date=${date}`)
      .then(r => {
        if (cancelled) return
        setWeight(r.weight_kg != null ? String(r.weight_kg) : '')
        setWeightEstimated(r.weight_kg != null && !!r.estimated)
      })
      .catch(() => {})
    return () => { cancelled = true }
  }, [date])

  return (
    <div className="page">
      <div className="row">
        <button className="secondary" onClick={() => navigate(-1)}>‹ Back</button>
        <span className="spacer" />
      </div>

      <h1 style={{ marginTop: '0.5rem' }}>Manual <em>log</em></h1>
      <p className="muted" style={{ marginBottom: '1.25rem' }}>
        Add or correct a day. Saving the same date again overwrites it.
      </p>

      <div className="card">
        <Field label="Date">
          <input type="date" value={date} max={localToday()} onChange={e => setDate(e.target.value)} />
        </Field>
      </div>

      <LogCard
        title="Weight"
        onSave={() => apiFetch('/api/health/weight', {
          method: 'POST',
          body: JSON.stringify({
            date,
            weight_kg: required(weight, 'a weight'),
            source: weightEstimated ? 'estimated' : 'manual',
          }),
        })}
      >
        <Field label="Weight (kg)">
          <input type="text" inputMode="decimal" placeholder="84.0"
            value={weight}
            onChange={e => { setWeight(e.target.value); setWeightEstimated(false) }} />
          {weightEstimated && (
            <span className="muted" style={{ fontSize: '0.75rem', marginTop: 4 }}>
              ≈ interpolated estimate — saved as an estimate unless you edit it
            </span>
          )}
        </Field>
      </LogCard>

      <LogCard
        title="Steps"
        onSave={() => apiFetch('/api/health/steps', {
          method: 'POST',
          body: JSON.stringify({ date, steps: Math.round(required(steps, 'a step count')) }),
        })}
      >
        <Field label="Steps">
          <input type="number" inputMode="numeric" placeholder="10000"
            value={steps} onChange={e => setSteps(e.target.value)} />
        </Field>
      </LogCard>

      <LogCard
        title="Sleep"
        onSave={() => {
          const asleep = required(asleepH, 'hours asleep')
          // In-bed defaults to asleep time when left blank
          const inBed = parseDecimal(inBedH) ?? asleep
          return apiFetch('/api/health/sleep', {
            method: 'POST',
            body: JSON.stringify({
              date,
              asleep_minutes: Math.round(asleep * 60),
              in_bed_minutes: Math.round(inBed * 60),
            }),
          })
        }}
      >
        <div className="form-row">
          <Field label="Asleep (h)">
            <input type="text" inputMode="decimal" placeholder="7.5"
              value={asleepH} onChange={e => setAsleepH(e.target.value)} />
          </Field>
          <Field label="In bed (h, optional)">
            <input type="text" inputMode="decimal" placeholder="8"
              value={inBedH} onChange={e => setInBedH(e.target.value)} />
          </Field>
        </div>
      </LogCard>

      <LogCard
        title="Nutrition"
        onSave={() => apiFetch('/api/nutrition', {
          method: 'POST',
          body: JSON.stringify({
            date,
            calories: required(calories, 'calories'),
            protein_g: required(protein, 'protein'),
            carbs_g: required(carbs, 'carbs'),
            fat_g: required(fat, 'fat'),
          }),
        })}
      >
        <div className="form-row">
          <Field label="Calories (kcal)">
            <input type="number" inputMode="numeric" placeholder="2400"
              value={calories} onChange={e => setCalories(e.target.value)} />
          </Field>
          <Field label="Protein (g)">
            <input type="number" inputMode="numeric" placeholder="180"
              value={protein} onChange={e => setProtein(e.target.value)} />
          </Field>
        </div>
        <div className="form-row">
          <Field label="Carbs (g)">
            <input type="number" inputMode="numeric" placeholder="250"
              value={carbs} onChange={e => setCarbs(e.target.value)} />
          </Field>
          <Field label="Fat (g)">
            <input type="number" inputMode="numeric" placeholder="80"
              value={fat} onChange={e => setFat(e.target.value)} />
          </Field>
        </div>
      </LogCard>
    </div>
  )
}

/**
 * First-run onboarding — shown (full-screen, above the app) until the profile
 * questions are answered. Everything it sets already exists in AppSettings;
 * bodyweight becomes a manual WeightLog for today (manual entries win over
 * synced data, and ranks need a bodyweight to compute).
 */
import React, { useState } from 'react'
import { apiFetch } from '../api'
import { ErrorBox } from './States'

export default function Onboarding({ onDone }) {
  const [sex, setSex] = useState('male')
  const [age, setAge] = useState('')
  const [weight, setWeight] = useState('')
  const [calories, setCalories] = useState('2300')
  const [protein, setProtein] = useState('180')
  const [lossRate, setLossRate] = useState('0.5')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      if (weight !== '') {
        await apiFetch('/api/health/weight', {
          method: 'POST',
          body: JSON.stringify({ date: new Date().toISOString().slice(0, 10), weight_kg: Number(weight) }),
        })
      }
      await apiFetch('/api/settings', {
        method: 'PUT',
        body: JSON.stringify({
          sex,
          ...(age !== '' ? { age: Number(age) } : {}),
          ...(calories !== '' ? { calorie_target: Number(calories) } : {}),
          ...(protein !== '' ? { protein_target_g: Number(protein) } : {}),
          ...(lossRate !== '' ? { target_loss_kg_per_week: Number(lossRate) } : {}),
          onboarded: true,
        }),
      })
      onDone()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function skip() {
    try {
      await apiFetch('/api/settings', { method: 'PUT', body: JSON.stringify({ onboarded: true }) })
    } catch (_) { /* still let them in — the wizard reappears next launch on failure */ }
    onDone()
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 300, overflowY: 'auto',
      background: 'var(--color-bg)', padding: '2rem 1rem calc(2rem + env(safe-area-inset-bottom))',
    }}>
      <div style={{ maxWidth: 460, margin: '0 auto' }}>
        <h1 style={{ marginBottom: '0.25rem' }}>Welcome</h1>
        <p className="muted" style={{ marginBottom: '1.25rem' }}>
          A few questions so targets and strength ranks are tuned to you, not to
          someone else. You can change all of this later in Settings.
        </p>
        <ErrorBox error={error} />

        <form onSubmit={submit} className="col" style={{ gap: '0.9rem' }}>
          <div className="card" style={{ margin: 0 }}>
            <h3 style={{ marginTop: 0 }}>About you</h3>
            <div className="form-group">
              <label>Sex <span className="muted" style={{ fontWeight: 400 }}>(scales the strength references)</span></label>
              <div className="row" style={{ gap: '0.5rem' }}>
                {['male', 'female'].map(s => (
                  <button type="button" key={s} className={sex === s ? undefined : 'secondary'}
                    style={{ flex: 1, textTransform: 'capitalize' }} onClick={() => setSex(s)}>
                    {s}
                  </button>
                ))}
              </div>
            </div>
            <div className="row" style={{ gap: '0.75rem' }}>
              <div className="form-group" style={{ flex: 1 }}>
                <label htmlFor="ob-age">Age</label>
                <input id="ob-age" type="number" inputMode="numeric" min="10" max="100"
                  placeholder="25" value={age} onChange={e => setAge(e.target.value)} />
              </div>
              <div className="form-group" style={{ flex: 1 }}>
                <label htmlFor="ob-weight">Bodyweight (kg)</label>
                <input id="ob-weight" type="number" inputMode="decimal" step="0.1" min="20"
                  placeholder="80.0" value={weight} onChange={e => setWeight(e.target.value)} />
              </div>
            </div>
          </div>

          <div className="card" style={{ margin: 0 }}>
            <h3 style={{ marginTop: 0 }}>Daily targets</h3>
            <div className="row" style={{ gap: '0.75rem' }}>
              <div className="form-group" style={{ flex: 1 }}>
                <label htmlFor="ob-cal">Calories (kcal)</label>
                <input id="ob-cal" type="number" inputMode="numeric" min="800"
                  value={calories} onChange={e => setCalories(e.target.value)} />
              </div>
              <div className="form-group" style={{ flex: 1 }}>
                <label htmlFor="ob-prot">Protein (g)</label>
                <input id="ob-prot" type="number" inputMode="numeric" min="0"
                  value={protein} onChange={e => setProtein(e.target.value)} />
              </div>
            </div>
            <div className="form-group">
              <label htmlFor="ob-loss">Weight goal (kg/week — positive = losing, 0 = maintain)</label>
              <input id="ob-loss" type="number" inputMode="decimal" step="0.05"
                value={lossRate} onChange={e => setLossRate(e.target.value)} />
            </div>
            <p className="muted" style={{ fontSize: '0.78rem', margin: 0 }}>
              The calorie target adapts weekly from your weight trend — this is
              just the starting point.
            </p>
          </div>

          <button type="submit" disabled={busy} style={{ width: '100%' }}>
            {busy ? 'Saving…' : 'Start tracking'}
          </button>
          <button type="button" className="secondary" onClick={skip} disabled={busy} style={{ width: '100%' }}>
            Skip for now
          </button>
        </form>
      </div>
    </div>
  )
}

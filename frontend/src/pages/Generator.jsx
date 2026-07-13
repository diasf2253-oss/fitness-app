/**
 * Workout Generator — pick priority muscles (ranked), days/week, and split;
 * preview a program that respects the weekly volume targets and priority
 * ordering; then save it as routines (replacing only previously generated
 * ones) on confirmation.
 */
import React, { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { apiFetch } from '../api'
import { Loading, ErrorBox } from '../components/States'
import PageHero from '../components/PageHero'
import WidgetLabel from '../components/WidgetLabel'

function statusColor(count, t) {
  if (count < t.low) return 'var(--color-muted)'
  if (count > t.high) return 'var(--color-danger)'
  return 'var(--color-accent)'
}

function Review({ program, onSave, saving, savedMsg }) {
  return (
    <>
      <div className="card">
        <div className="row" style={{ marginBottom: '0.5rem' }}>
          <h3 style={{ margin: 0, flex: 1 }}>{program.split_label} · {program.days_per_week} days</h3>
          <WidgetLabel>week plan</WidgetLabel>
        </div>
        <div className="row" style={{ flexWrap: 'wrap', gap: '0.35rem' }}>
          {program.arrangement.map((d, i) => <span key={i} className="badge">{i + 1}. {d}</span>)}
        </div>
        {program.notes.length > 0 && (
          <div style={{ marginTop: '0.75rem' }}>
            {program.notes.map((n, i) => (
              <p key={i} className="muted" style={{ fontSize: '0.78rem', margin: '0.2rem 0' }}>• {n}</p>
            ))}
          </div>
        )}
      </div>

      <div className="card">
        <WidgetLabel>weekly sets vs target</WidgetLabel>
        <div style={{ marginTop: '0.5rem' }}>
          {Object.entries(program.weekly_sets).filter(([, s]) => s > 0).map(([m, s]) => {
            const t = program.targets[m]
            return (
              <div key={m} className="row" style={{ padding: '0.3rem 0', borderBottom: '1px solid var(--color-border)' }}>
                <span style={{ flex: 1, fontSize: '0.86rem' }}>{m}</span>
                <span className="tnum" style={{ color: statusColor(s, t), fontSize: '0.9rem', width: 30, textAlign: 'right' }}>{s}</span>
                <span className="tnum muted" style={{ width: 58, textAlign: 'right', fontSize: '0.76rem' }}>{t.low}–{t.high}</span>
              </div>
            )
          })}
        </div>
      </div>

      {program.routines.map((r, i) => (
        <div key={i} className="card">
          <h3 style={{ margin: '0 0 0.5rem' }}>{r.name}</h3>
          {r.exercises.map((e, j) => (
            <div key={j} className="row" style={{ padding: '0.35rem 0', borderBottom: '1px solid var(--color-border)' }}>
              <span style={{ flex: 1, fontSize: '0.88rem' }}>
                {e.name} <span className="muted" style={{ fontSize: '0.74rem' }}>· {e.muscle_group}</span>
              </span>
              <span className="tnum" style={{ fontSize: '0.85rem' }}>{e.sets} × {e.rep_low}–{e.rep_high}</span>
            </div>
          ))}
        </div>
      ))}

      <div className="card">
        {savedMsg && <p className="muted" style={{ marginBottom: '0.5rem' }}>{savedMsg}</p>}
        <button onClick={onSave} disabled={saving} style={{ width: '100%' }}>
          {saving ? 'Saving…' : 'Save as my routines'}
        </button>
        <p className="muted" style={{ fontSize: '0.74rem', marginTop: '0.5rem' }}>
          Replaces previously generated routines only — your hand-made routines stay.
        </p>
      </div>
    </>
  )
}

export default function Generator() {
  const navigate = useNavigate()
  const [options, setOptions] = useState(null)
  const [priority, setPriority] = useState([])
  const [days, setDays] = useState(4)
  const [split, setSplit] = useState('ppl')
  const [program, setProgram] = useState(null)
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)
  const [savedMsg, setSavedMsg] = useState(null)

  useEffect(() => {
    apiFetch('/api/generator/options').then(setOptions).catch(e => setError(e.message))
  }, [])

  function togglePriority(m) {
    setProgram(null)
    setPriority(p => p.includes(m) ? p.filter(x => x !== m) : [...p, m])
  }

  async function generate() {
    setLoading(true); setError(null); setProgram(null); setSavedMsg(null)
    try {
      const body = { priority_muscles: priority, days_per_week: Number(days), split_type: split }
      setProgram(await apiFetch('/api/generator/preview', { method: 'POST', body: JSON.stringify(body) }))
    } catch (e) { setError(e.message) } finally { setLoading(false) }
  }

  async function save() {
    if (!confirm('Save this program as your routines? This replaces any previously generated routines — your hand-made ones are untouched.')) return
    setSaving(true); setError(null)
    try {
      const body = { priority_muscles: priority, days_per_week: Number(days), split_type: split }
      const r = await apiFetch('/api/generator/apply', { method: 'POST', body: JSON.stringify(body) })
      setSavedMsg(`Saved ${r.routines.length} routine(s)${r.replaced ? `, replaced ${r.replaced} previous` : ''}. Opening routines…`)
      setTimeout(() => navigate('/routines'), 1000)
    } catch (e) { setError(e.message); setSaving(false) }
  }

  if (!options) return <div className="page"><Loading /></div>

  return (
    <div className="page">
      <PageHero
        meta="Training"
        title={<>Workout <em>generator</em></>}
        lede="Pick your priorities, days, and split — get a program that respects your weekly volume targets."
      />
      <ErrorBox error={error} />

      <div className="card">
        <WidgetLabel>priority muscles — tap in order, first = highest</WidgetLabel>
        <div className="row" style={{ flexWrap: 'wrap', gap: '0.4rem', margin: '0.5rem 0 1rem' }}>
          {options.muscle_groups.map(m => {
            const rank = priority.indexOf(m)
            return (
              <button
                key={m}
                className={rank >= 0 ? '' : 'secondary'}
                onClick={() => togglePriority(m)}
                style={{ padding: '0.4rem 0.7rem', fontSize: '0.82rem', minHeight: 36 }}
              >
                {rank >= 0 && <span style={{ opacity: 0.7, marginRight: 4 }}>{rank + 1}.</span>}{m}
              </button>
            )
          })}
        </div>
        <div className="form-row">
          <div className="form-group">
            <label>Days / week</label>
            <select value={days} onChange={e => { setProgram(null); setDays(e.target.value) }}>
              {[2, 3, 4, 5, 6, 7].map(d => <option key={d} value={d}>{d}</option>)}
            </select>
          </div>
          <div className="form-group">
            <label>Split</label>
            <select value={split} onChange={e => { setProgram(null); setSplit(e.target.value) }}>
              {options.split_types.map(s => <option key={s.value} value={s.value}>{s.label}</option>)}
            </select>
          </div>
        </div>
        <button onClick={generate} disabled={loading} style={{ width: '100%', marginTop: '0.5rem' }}>
          {loading ? 'Generating…' : 'Generate'}
        </button>
      </div>

      {program && <Review program={program} onSave={save} saving={saving} savedMsg={savedMsg} />}
    </div>
  )
}

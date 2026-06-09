/**
 * Routines page (Phase 1c).
 * - List all routines
 * - Create a new routine
 * - Edit a routine (name + ordered exercise list with targets)
 * - Delete a routine
 * - "Start workout" from a routine (navigates to /workout with the routine id)
 */
import React, { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { apiFetch } from '../api'
import ExercisePicker from '../components/ExercisePicker'
import { Loading, ErrorBox, EmptyState } from '../components/States'

export default function Routines() {
  const [routines, setRoutines] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [editing, setEditing] = useState(null)  // routine object being edited, or 'new'
  const navigate = useNavigate()

  function load() {
    setLoading(true)
    apiFetch('/api/routines')
      .then(setRoutines)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  async function handleDelete(id) {
    if (!confirm('Delete this routine?')) return
    try {
      await apiFetch(`/api/routines/${id}`, { method: 'DELETE' })
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  // Start a workout from a routine: create a session, then go to /workout
  async function startWorkout(routine) {
    try {
      const session = await apiFetch('/api/sessions', {
        method: 'POST',
        body: JSON.stringify({ name: routine.name, routine_id: routine.id }),
      })
      navigate('/workout', { state: { sessionId: session.id } })
    } catch (err) {
      setError(err.message)
    }
  }

  if (editing) {
    return (
      <RoutineEditor
        routine={editing === 'new' ? null : editing}
        onSaved={() => { setEditing(null); load() }}
        onCancel={() => setEditing(null)}
      />
    )
  }

  return (
    <div className="page">
      <div className="row">
        <h1>Routines</h1>
        <span className="spacer" />
        <Link to="/exercises"><button className="secondary">Exercises</button></Link>
      </div>

      <button onClick={() => setEditing('new')} style={{ width: '100%', marginBottom: '1rem' }}>
        + New Routine
      </button>

      <ErrorBox error={error} />
      {loading && <Loading />}

      {!loading && routines.length === 0 && (
        <EmptyState>No routines yet. Create one to get started.</EmptyState>
      )}

      <div className="col" style={{ gap: '0.75rem' }}>
        {routines.map(r => (
          <div key={r.id} className="card" style={{ margin: 0 }}>
            <div className="row">
              <h3 style={{ flex: 1, margin: 0 }}>{r.name}</h3>
              <span className="badge">{r.exercises.length} exercises</span>
            </div>
            {r.exercises.length > 0 && (
              <p className="muted" style={{ fontSize: '0.8rem', marginTop: '0.4rem' }}>
                {r.exercises.map(e => e.exercise.name).join(' · ')}
              </p>
            )}
            <div className="row" style={{ marginTop: '0.75rem', gap: '0.5rem' }}>
              <button onClick={() => startWorkout(r)} style={{ flex: 1 }}>Start</button>
              <button className="secondary" onClick={() => setEditing(r)}>Edit</button>
              <button className="danger" onClick={() => handleDelete(r.id)}>🗑</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Routine editor — add/reorder exercises, set targets
// ---------------------------------------------------------------------------

function RoutineEditor({ routine, onSaved, onCancel }) {
  const [name, setName] = useState(routine?.name || '')
  // Local working copy of the exercise list.
  // Each item: { exercise (obj), target_sets, target_rep_low, target_rep_high, rest_seconds }
  const [items, setItems] = useState(
    routine?.exercises.map(re => ({
      exercise: re.exercise,
      target_sets: re.target_sets,
      target_rep_low: re.target_rep_low,
      target_rep_high: re.target_rep_high,
      rest_seconds: re.rest_seconds,
    })) || []
  )
  const [showPicker, setShowPicker] = useState(false)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  function addExercise(ex) {
    setItems(prev => [...prev, {
      exercise: ex,
      target_sets: 3,
      target_rep_low: 8,
      target_rep_high: 12,
      rest_seconds: 120,
    }])
    setShowPicker(false)
  }

  function updateItem(idx, field, value) {
    setItems(prev => prev.map((it, i) => i === idx ? { ...it, [field]: value } : it))
  }

  function removeItem(idx) {
    setItems(prev => prev.filter((_, i) => i !== idx))
  }

  function move(idx, dir) {
    const newIdx = idx + dir
    if (newIdx < 0 || newIdx >= items.length) return
    setItems(prev => {
      const copy = [...prev]
      ;[copy[idx], copy[newIdx]] = [copy[newIdx], copy[idx]]
      return copy
    })
  }

  async function handleSave() {
    if (!name.trim()) { setError('Routine name is required'); return }
    setSaving(true)
    setError(null)
    const body = {
      name: name.trim(),
      exercises: items.map((it, idx) => ({
        exercise_id: it.exercise.id,
        position: idx,
        target_sets: Number(it.target_sets),
        target_rep_low: Number(it.target_rep_low),
        target_rep_high: Number(it.target_rep_high),
        rest_seconds: Number(it.rest_seconds),
      })),
    }
    try {
      if (routine) {
        await apiFetch(`/api/routines/${routine.id}`, { method: 'PUT', body: JSON.stringify(body) })
      } else {
        await apiFetch('/api/routines', { method: 'POST', body: JSON.stringify(body) })
      }
      onSaved()
    } catch (err) {
      setError(err.message)
      setSaving(false)
    }
  }

  return (
    <div className="page">
      <div className="row">
        <h1>{routine ? 'Edit Routine' : 'New Routine'}</h1>
        <span className="spacer" />
        <button className="secondary" onClick={onCancel}>Cancel</button>
      </div>

      <ErrorBox error={error} />

      <div className="form-group">
        <label>Routine name</label>
        <input value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Upper A" autoFocus />
      </div>

      <h3 style={{ marginTop: '1rem' }}>Exercises</h3>
      {items.length === 0 && (
        <p className="muted" style={{ padding: '0.5rem 0' }}>No exercises yet. Add some below.</p>
      )}

      <div className="col" style={{ gap: '0.75rem' }}>
        {items.map((it, idx) => (
          <div key={idx} className="card" style={{ margin: 0 }}>
            <div className="row">
              <strong style={{ flex: 1 }}>{idx + 1}. {it.exercise.name}</strong>
              <button className="secondary" style={{ minWidth: 40, padding: '0.3rem 0.5rem' }} onClick={() => move(idx, -1)} disabled={idx === 0}>↑</button>
              <button className="secondary" style={{ minWidth: 40, padding: '0.3rem 0.5rem' }} onClick={() => move(idx, 1)} disabled={idx === items.length - 1}>↓</button>
              <button className="danger" style={{ minWidth: 40, padding: '0.3rem 0.5rem' }} onClick={() => removeItem(idx)}>✕</button>
            </div>
            <div className="form-row" style={{ marginTop: '0.5rem' }}>
              <div className="form-group" style={{ margin: 0 }}>
                <label>Sets</label>
                <input type="number" inputMode="numeric" value={it.target_sets} onChange={e => updateItem(idx, 'target_sets', e.target.value)} />
              </div>
              <div className="form-group" style={{ margin: 0 }}>
                <label>Rest (s)</label>
                <input type="number" inputMode="numeric" value={it.rest_seconds} onChange={e => updateItem(idx, 'rest_seconds', e.target.value)} />
              </div>
            </div>
            <div className="form-row" style={{ marginTop: '0.5rem' }}>
              <div className="form-group" style={{ margin: 0 }}>
                <label>Rep low</label>
                <input type="number" inputMode="numeric" value={it.target_rep_low} onChange={e => updateItem(idx, 'target_rep_low', e.target.value)} />
              </div>
              <div className="form-group" style={{ margin: 0 }}>
                <label>Rep high</label>
                <input type="number" inputMode="numeric" value={it.target_rep_high} onChange={e => updateItem(idx, 'target_rep_high', e.target.value)} />
              </div>
            </div>
          </div>
        ))}
      </div>

      <button className="secondary" onClick={() => setShowPicker(true)} style={{ width: '100%', marginTop: '0.75rem' }}>
        + Add Exercise
      </button>

      <button onClick={handleSave} disabled={saving} style={{ width: '100%', marginTop: '1rem' }}>
        {saving ? 'Saving…' : 'Save Routine'}
      </button>

      {showPicker && <ExercisePicker onSelect={addExercise} onClose={() => setShowPicker(false)} />}
    </div>
  )
}

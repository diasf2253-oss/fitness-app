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
import { parseDecimal } from '../num'
import ExercisePicker from '../components/ExercisePicker'
import { Loading, ErrorBox, EmptyState, EmptyNote } from '../components/States'
import { RankBadge, rankAccent, useExerciseRanks } from '../components/RankBadge'

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
        + New routine
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
              <button className="danger" onClick={() => handleDelete(r.id)} title="Delete routine" style={{ minWidth: 44, padding: '0.4rem 0.8rem' }}>✕</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Routine editor — add/reorder/replace exercises and plan each set
// ---------------------------------------------------------------------------

/** Editable set rows for an exercise: its saved plan, or blank rows matching
 *  how many sets it used to target. Empty strings (not nulls) so the inputs
 *  stay controlled. */
function blankOrExisting(plannedSets, targetSets) {
  if (plannedSets?.length) {
    return plannedSets.map(ps => ({
      weight_kg: ps.weight_kg ?? '', reps: ps.reps ?? '', rir: ps.rir ?? '',
    }))
  }
  return Array.from({ length: targetSets || 3 }, () => ({ weight_kg: '', reps: '', rir: '' }))
}

function RoutineEditor({ routine, onSaved, onCancel }) {
  const [name, setName] = useState(routine?.name || '')
  const exerciseRanks = useExerciseRanks()   // exercise_id -> rank (colour + tier)
  // Local working copy of the exercise list.
  // Each item: { exercise (obj), target_sets, target_rep_low, target_rep_high, rest_seconds }
  // Each item keeps the aggregate fields (the generator/coach still read them)
  // but the editor only touches planned_sets — one {weight_kg, reps, rir} row
  // per set, mirroring the workout grid. Routines written before per-set
  // planning get blank rows derived from their target_sets.
  const [items, setItems] = useState(
    routine?.exercises.map(re => ({
      exercise: re.exercise,
      target_sets: re.target_sets,
      target_rep_low: re.target_rep_low,
      target_rep_high: re.target_rep_high,
      rest_seconds: re.rest_seconds,
      target_rir: re.target_rir,
      planned_sets: blankOrExisting(re.planned_sets, re.target_sets),
    })) || []
  )
  const [showPicker, setShowPicker] = useState(false)
  // Index the picker should REPLACE, or null when it's adding a new exercise.
  const [replacingIdx, setReplacingIdx] = useState(null)
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  /** One handler for both picker modes: replace the movement in place
   *  (keeping its position and targets) or append a new one. */
  function pickExercise(ex) {
    if (replacingIdx != null) {
      setItems(prev => prev.map((it, i) => (i === replacingIdx ? { ...it, exercise: ex } : it)))
    } else {
      setItems(prev => [...prev, {
        exercise: ex,
        target_sets: 3,
        target_rep_low: 8,
        target_rep_high: 12,
        rest_seconds: 120,
        target_rir: null,
        planned_sets: blankOrExisting(null, 3),
      }])
    }
    closePicker()
  }

  function closePicker() {
    setShowPicker(false)
    setReplacingIdx(null)
  }

  function updateSet(idx, setIdx, field, value) {
    setItems(prev => prev.map((it, i) => (i === idx
      ? { ...it, planned_sets: it.planned_sets.map((ps, j) => (j === setIdx ? { ...ps, [field]: value } : ps)) }
      : it)))
  }

  function addSet(idx) {
    setItems(prev => prev.map((it, i) => (i === idx
      ? { ...it, planned_sets: [...it.planned_sets, { weight_kg: '', reps: '', rir: '' }] }
      : it)))
  }

  function removeSet(idx, setIdx) {
    setItems(prev => prev.map((it, i) => (i === idx
      ? { ...it, planned_sets: it.planned_sets.filter((_, j) => j !== setIdx) }
      : it)))
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
        target_rep_low: Number(it.target_rep_low),
        target_rep_high: Number(it.target_rep_high),
        rest_seconds: Number(it.rest_seconds),
        target_rir: it.target_rir === '' || it.target_rir == null ? null : Number(it.target_rir),
        // Blank cells stay null — a plan is guidance, not a logged lift.
        planned_sets: it.planned_sets.map(ps => ({
          weight_kg: ps.weight_kg === '' || ps.weight_kg == null ? null : parseDecimal(ps.weight_kg),
          reps: ps.reps === '' || ps.reps == null ? null : Number(ps.reps),
          rir: ps.rir === '' || ps.rir == null ? null : Number(ps.rir),
        })),
        target_sets: it.planned_sets.length,
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
        <h1>{routine ? 'Edit routine' : 'New routine'}</h1>
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
        <EmptyNote>No exercises yet. Add some below.</EmptyNote>
      )}

      <div className="col" style={{ gap: '0.75rem' }}>
        {items.map((it, idx) => (
          <div key={idx} className="card" style={{ margin: 0, ...rankAccent(exerciseRanks[it.exercise.id]) }}>
            <div className="row" style={{ flexWrap: 'wrap', gap: '0.3rem' }}>
              <strong style={{ flex: '1 1 140px' }}>{idx + 1}. {it.exercise.name}</strong>
              <RankBadge rank={exerciseRanks[it.exercise.id]} style={{ marginRight: 4 }} />
              <button
                className="secondary" style={{ minWidth: 40, padding: '0.3rem 0.5rem' }}
                title="Replace exercise" aria-label={`Replace ${it.exercise.name}`}
                onClick={() => { setReplacingIdx(idx); setShowPicker(true) }}
              >⇄</button>
              <button className="secondary" style={{ minWidth: 40, padding: '0.3rem 0.5rem' }} onClick={() => move(idx, -1)} disabled={idx === 0}>↑</button>
              <button className="secondary" style={{ minWidth: 40, padding: '0.3rem 0.5rem' }} onClick={() => move(idx, 1)} disabled={idx === items.length - 1}>↓</button>
              <button className="danger" style={{ minWidth: 40, padding: '0.3rem 0.5rem' }} onClick={() => removeItem(idx)}>✕</button>
            </div>
            {/* Per-set plan — same columns as the workout's set rows */}
            <div className="row" style={{ fontSize: '0.7rem', color: 'var(--color-muted)', padding: '0 0.25rem', gap: '0.4rem', marginTop: '0.6rem' }}>
              <span style={{ width: 28, textAlign: 'center' }}>Set</span>
              <span style={{ flex: 1 }}>kg</span>
              <span style={{ flex: 1 }}>reps</span>
              <span style={{ width: 48, textAlign: 'center' }}>RIR</span>
              <span style={{ width: 30 }} />
            </div>
            <div className="col" style={{ gap: '0.4rem', marginTop: '0.25rem' }}>
              {it.planned_sets.map((ps, sIdx) => (
                <div key={sIdx} className="row" style={{ gap: '0.4rem' }}>
                  <span style={{ width: 28, textAlign: 'center', fontSize: '0.85rem', color: 'var(--color-muted)' }}>{sIdx + 1}</span>
                  <input
                    style={{ flex: 1, minHeight: 40, textAlign: 'center' }}
                    type="text" inputMode="decimal" placeholder="–"
                    aria-label={`Set ${sIdx + 1} weight`}
                    value={ps.weight_kg} onChange={e => updateSet(idx, sIdx, 'weight_kg', e.target.value)}
                  />
                  <input
                    style={{ flex: 1, minHeight: 40, textAlign: 'center' }}
                    type="number" inputMode="numeric" placeholder="–"
                    aria-label={`Set ${sIdx + 1} reps`}
                    value={ps.reps} onChange={e => updateSet(idx, sIdx, 'reps', e.target.value)}
                  />
                  <input
                    style={{ width: 48, minHeight: 40, textAlign: 'center', padding: '0.3rem' }}
                    type="number" inputMode="numeric" placeholder="–"
                    aria-label={`Set ${sIdx + 1} RIR`}
                    value={ps.rir} onChange={e => updateSet(idx, sIdx, 'rir', e.target.value)}
                  />
                  <button
                    className="secondary" aria-label={`Remove set ${sIdx + 1}`}
                    style={{ width: 30, minWidth: 30, height: 40, minHeight: 40, padding: 0,
                             background: 'transparent', border: 'none', boxShadow: 'none',
                             color: 'var(--color-muted)' }}
                    onClick={() => removeSet(idx, sIdx)}
                  >✕</button>
                </div>
              ))}
            </div>
            <button
              className="secondary" onClick={() => addSet(idx)}
              style={{ width: '100%', marginTop: '0.5rem', padding: '0.35rem' }}
            >+ Add set</button>
          </div>
        ))}
      </div>

      <button className="secondary" onClick={() => setShowPicker(true)} style={{ width: '100%', marginTop: '0.75rem' }}>
        + Add exercise
      </button>

      <button onClick={handleSave} disabled={saving} style={{ width: '100%', marginTop: '1rem' }}>
        {saving ? 'Saving…' : 'Save routine'}
      </button>

      {showPicker && <ExercisePicker onSelect={pickExercise} onClose={closePicker} />}
    </div>
  )
}

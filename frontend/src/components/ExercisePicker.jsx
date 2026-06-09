/**
 * ExercisePicker — a modal that lets you search/filter the exercise library
 * and pick one exercise. Reused by the Routines editor and the live Workout
 * screen ("Add exercise").
 *
 * Props:
 *   onSelect(exercise)  — called with the chosen exercise object
 *   onClose()           — close without selecting
 */
import React, { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../api'
import Modal from './Modal'
import { Loading, ErrorBox } from './States'

const MUSCLE_OPTIONS = [
  'chest', 'back', 'shoulders', 'biceps', 'triceps',
  'quads', 'hamstrings', 'glutes', 'calves', 'core',
]
const EQUIPMENT_OPTIONS = ['barbell', 'dumbbell', 'cable', 'machine', 'bodyweight']

export default function ExercisePicker({ onSelect, onClose }) {
  const [exercises, setExercises] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [muscle, setMuscle] = useState('')
  const [creating, setCreating] = useState(false)   // showing the inline create form?

  useEffect(() => {
    apiFetch('/api/exercises')
      .then(setExercises)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  // Unique muscle groups for the filter dropdown
  const muscles = useMemo(() => {
    const set = new Set(exercises.map(e => e.primary_muscle).filter(Boolean))
    return [...set].sort()
  }, [exercises])

  // Client-side filtering (the list is small enough)
  const filtered = useMemo(() => {
    return exercises.filter(e => {
      const matchSearch = !search || e.name.toLowerCase().includes(search.toLowerCase())
      const matchMuscle = !muscle || e.primary_muscle === muscle
      return matchSearch && matchMuscle
    })
  }, [exercises, search, muscle])

  // After creating a custom exercise, immediately select it (adds it to the
  // workout/routine) so you don't have to find it in the list again.
  if (creating) {
    return (
      <Modal title="New Exercise" onClose={onClose}>
        <CreateExerciseForm
          initialName={search}
          onCancel={() => setCreating(false)}
          onCreated={ex => onSelect(ex)}
        />
      </Modal>
    )
  }

  return (
    <Modal title="Add Exercise" onClose={onClose}>
      <div className="col" style={{ marginBottom: '0.75rem' }}>
        <input
          placeholder="Search exercises…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          autoFocus
        />
        <select value={muscle} onChange={e => setMuscle(e.target.value)}>
          <option value="">All muscle groups</option>
          {muscles.map(m => <option key={m} value={m}>{m}</option>)}
        </select>
      </div>

      <button onClick={() => setCreating(true)} style={{ width: '100%', marginBottom: '0.75rem' }}>
        + New exercise{search.trim() ? ` "${search.trim()}"` : ''}
      </button>

      {loading && <Loading />}
      <ErrorBox error={error} />

      {!loading && filtered.length === 0 && (
        <p className="muted" style={{ textAlign: 'center', padding: '1rem' }}>
          No exercises match. Use “New exercise” above to add one.
        </p>
      )}

      <div className="col" style={{ gap: '0.4rem' }}>
        {filtered.map(ex => (
          <button
            key={ex.id}
            className="secondary"
            style={{ justifyContent: 'flex-start', textAlign: 'left', display: 'flex' }}
            onClick={() => onSelect(ex)}
          >
            <span style={{ flex: 1 }}>
              {ex.name}
              <span className="muted" style={{ display: 'block', fontSize: '0.75rem' }}>
                {ex.primary_muscle}{ex.equipment ? ` · ${ex.equipment}` : ''}
              </span>
            </span>
          </button>
        ))}
      </div>
    </Modal>
  )
}

// Inline form to create a custom exercise without leaving the picker.
function CreateExerciseForm({ initialName, onCancel, onCreated }) {
  const [name, setName] = useState(initialName || '')
  const [primaryMuscle, setPrimaryMuscle] = useState('chest')
  const [equipment, setEquipment] = useState('barbell')
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    if (!name.trim()) { setError('Name is required'); return }
    setSaving(true)
    setError(null)
    try {
      const ex = await apiFetch('/api/exercises', {
        method: 'POST',
        body: JSON.stringify({
          name: name.trim(),
          primary_muscle: primaryMuscle,
          equipment,
          secondary_muscles: [],
          notes: null,
          is_custom: true,
        }),
      })
      onCreated(ex)
    } catch (err) {
      setError(err.message)
      setSaving(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="col">
      <ErrorBox error={error} />
      <div className="form-group">
        <label>Name</label>
        <input value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Smith Machine Press" autoFocus />
      </div>
      <div className="form-row">
        <div className="form-group">
          <label>Primary muscle</label>
          <select value={primaryMuscle} onChange={e => setPrimaryMuscle(e.target.value)}>
            {MUSCLE_OPTIONS.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>
        <div className="form-group">
          <label>Equipment</label>
          <select value={equipment} onChange={e => setEquipment(e.target.value)}>
            {EQUIPMENT_OPTIONS.map(eq => <option key={eq} value={eq}>{eq}</option>)}
          </select>
        </div>
      </div>
      <button type="submit" disabled={saving}>{saving ? 'Saving…' : 'Create & Add'}</button>
      <button type="button" className="secondary" onClick={onCancel}>Cancel</button>
    </form>
  )
}

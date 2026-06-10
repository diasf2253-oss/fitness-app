/**
 * Exercise Library page (Phase 1a).
 * - List all exercises with search + muscle-group filter
 * - Create custom exercises
 * - Delete custom exercises (built-ins are protected by the API)
 */
import React, { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../api'
import Modal from '../components/Modal'
import { Loading, ErrorBox } from '../components/States'

const MUSCLE_OPTIONS = [
  'chest', 'back', 'shoulders', 'biceps', 'triceps',
  'quads', 'hamstrings', 'glutes', 'calves', 'core',
]

const EQUIPMENT_OPTIONS = ['barbell', 'dumbbell', 'cable', 'machine', 'bodyweight']

export default function Exercises() {
  const [exercises, setExercises] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [muscleFilter, setMuscleFilter] = useState('')
  const [showCreate, setShowCreate] = useState(false)

  function load() {
    setLoading(true)
    apiFetch('/api/exercises')
      .then(setExercises)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }

  useEffect(load, [])

  const filtered = useMemo(() => {
    return exercises.filter(e => {
      const ms = !search || e.name.toLowerCase().includes(search.toLowerCase())
      const mm = !muscleFilter || e.primary_muscle === muscleFilter
      return ms && mm
    })
  }, [exercises, search, muscleFilter])

  async function handleDelete(id) {
    if (!confirm('Delete this custom exercise?')) return
    try {
      await apiFetch(`/api/exercises/${id}`, { method: 'DELETE' })
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="page">
      <div className="row">
        <h1>Exercise Library</h1>
        <span className="spacer" />
        <Link to="/routines"><button className="secondary">Routines</button></Link>
      </div>

      <div className="col" style={{ marginBottom: '1rem' }}>
        <input
          placeholder="Search exercises…"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        <div className="row">
          <select value={muscleFilter} onChange={e => setMuscleFilter(e.target.value)} style={{ flex: 1 }}>
            <option value="">All muscle groups</option>
            {MUSCLE_OPTIONS.map(m => <option key={m} value={m}>{m}</option>)}
          </select>
          <button onClick={() => setShowCreate(true)} style={{ whiteSpace: 'nowrap' }}>+ New</button>
        </div>
      </div>

      <ErrorBox error={error} />
      {loading && <Loading />}

      {!loading && (
        <div className="col" style={{ gap: '0.5rem' }}>
          {filtered.map(ex => (
            <div key={ex.id} className="card" style={{ margin: 0, padding: '0.75rem 1rem' }}>
              <div className="row">
                <div style={{ flex: 1 }}>
                  <strong>{ex.name}</strong>
                  {ex.is_custom && <span className="badge primary" style={{ marginLeft: 6 }}>custom</span>}
                  <div className="muted" style={{ fontSize: '0.8rem' }}>
                    {ex.primary_muscle}
                    {ex.equipment ? ` · ${ex.equipment}` : ''}
                    {ex.secondary_muscles?.length ? ` · also: ${ex.secondary_muscles.join(', ')}` : ''}
                  </div>
                </div>
                {ex.is_custom && (
                  <button className="danger" style={{ minWidth: 44, padding: '0.4rem 0.6rem' }} onClick={() => handleDelete(ex.id)} title="Delete exercise">
                    ✕
                  </button>
                )}
              </div>
            </div>
          ))}
          {filtered.length === 0 && (
            <p className="muted" style={{ textAlign: 'center', padding: '1rem' }}>No exercises match.</p>
          )}
        </div>
      )}

      {showCreate && (
        <CreateExerciseModal
          onClose={() => setShowCreate(false)}
          onCreated={() => { setShowCreate(false); load() }}
        />
      )}
    </div>
  )
}

function CreateExerciseModal({ onClose, onCreated }) {
  const [name, setName] = useState('')
  const [primaryMuscle, setPrimaryMuscle] = useState('chest')
  const [equipment, setEquipment] = useState('barbell')
  const [notes, setNotes] = useState('')
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)

  async function handleSubmit(e) {
    e.preventDefault()
    if (!name.trim()) { setError('Name is required'); return }
    setSaving(true)
    setError(null)
    try {
      await apiFetch('/api/exercises', {
        method: 'POST',
        body: JSON.stringify({
          name: name.trim(),
          primary_muscle: primaryMuscle,
          equipment,
          secondary_muscles: [],
          notes: notes.trim() || null,
          is_custom: true,
        }),
      })
      onCreated()
    } catch (err) {
      setError(err.message)
      setSaving(false)
    }
  }

  return (
    <Modal title="New Custom Exercise" onClose={onClose}>
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
        <div className="form-group">
          <label>Notes (optional)</label>
          <textarea value={notes} onChange={e => setNotes(e.target.value)} rows={2} />
        </div>
        <button type="submit" disabled={saving}>{saving ? 'Saving…' : 'Create Exercise'}</button>
      </form>
    </Modal>
  )
}

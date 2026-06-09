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

export default function ExercisePicker({ onSelect, onClose }) {
  const [exercises, setExercises] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [muscle, setMuscle] = useState('')

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

      {loading && <Loading />}
      <ErrorBox error={error} />

      {!loading && filtered.length === 0 && (
        <p className="muted" style={{ textAlign: 'center', padding: '1rem' }}>
          No exercises match.
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

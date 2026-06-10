/**
 * History page (Phase 1d).
 * - Reverse-chronological list of sessions
 * - Tap a session to expand its full detail (exercises + working sets)
 * - Link from each exercise to its ExerciseDetail page (charts)
 */
import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../api'
import { Loading, ErrorBox, EmptyState } from '../components/States'

// Format an ISO datetime (stored UTC, naive) into a friendly local string
function fmtDate(iso) {
  const d = new Date(iso + 'Z')
  return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })
}

function durationMin(started, ended) {
  if (!ended) return null
  const mins = Math.round((new Date(ended) - new Date(started)) / 60000)
  return mins
}

export default function History() {
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [expandedId, setExpandedId] = useState(null)

  useEffect(() => {
    apiFetch('/api/sessions?limit=100')
      .then(setSessions)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  return (
    <div className="page">
      <h1>History</h1>
      <ErrorBox error={error} />
      {loading && <Loading />}

      {!loading && sessions.length === 0 && (
        <EmptyState>No workouts logged yet. Start one from the Workout tab.</EmptyState>
      )}

      <div className="col" style={{ gap: '0.5rem' }}>
        {sessions.map(s => (
          <div key={s.id} className="card" style={{ margin: 0 }}>
            <div
              className="row"
              style={{ cursor: 'pointer' }}
              onClick={() => setExpandedId(expandedId === s.id ? null : s.id)}
            >
              <div style={{ flex: 1 }}>
                <strong>{s.name}</strong>
                <div className="muted" style={{ fontSize: '0.8rem' }}>
                  {fmtDate(s.started_at)}
                  {s.ended_at
                    ? ` · ${durationMin(s.started_at, s.ended_at)} min`
                    : <span className="text-warning"> · in progress</span>}
                </div>
              </div>
              <span className="muted" style={{ fontSize: '0.7rem' }}>{expandedId === s.id ? '▲' : '▼'}</span>
            </div>

            {expandedId === s.id && <SessionDetail sessionId={s.id} />}
          </div>
        ))}
      </div>
    </div>
  )
}

// Expanded detail — lazy-loads the full session
function SessionDetail({ sessionId }) {
  const [detail, setDetail] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    apiFetch(`/api/sessions/${sessionId}`)
      .then(setDetail)
      .catch(err => setError(err.message))
  }, [sessionId])

  if (error) return <ErrorBox error={error} />
  if (!detail) return <Loading label="Loading detail…" />

  return (
    <div style={{ marginTop: '0.75rem', borderTop: '1px solid var(--color-border)', paddingTop: '0.75rem' }}>
      {detail.exercises.length === 0 && <p className="muted">No exercises logged.</p>}
      {detail.exercises.map(se => {
        const workingSets = se.sets.filter(st => !st.is_warmup)
        return (
          <div key={se.id} style={{ marginBottom: '0.75rem' }}>
            <Link to={`/exercise/${se.exercise_id}`} style={{ fontWeight: 600 }}>
              {se.exercise.name} ›
            </Link>
            <div className="col" style={{ gap: '0.15rem', marginTop: '0.25rem' }}>
              {se.sets.map(st => (
                <div key={st.id} className="muted" style={{ fontSize: '0.85rem' }}>
                  {st.is_warmup ? 'Warm-up' : `Set ${st.set_number}`}: {st.weight_kg} kg × {st.reps}
                  {st.rpe != null && ` @ RPE ${st.rpe}`}
                  {st.is_completed ? ' ✓' : ''}
                </div>
              ))}
            </div>
          </div>
        )
      })}
    </div>
  )
}

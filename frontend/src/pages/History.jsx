/**
 * History page.
 * - Reverse-chronological list of sessions
 * - Phone: tap a session to expand its detail inline (accordion)
 * - Laptop (≥1024px): two-pane — list left, sticky detail right,
 *   latest session selected automatically
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

// Matches the CSS .hist-grid breakpoint so exactly one detail mounts
function useIsDesktop() {
  const [isDesktop, setIsDesktop] = useState(
    () => window.matchMedia('(min-width: 1024px)').matches
  )
  useEffect(() => {
    const mq = window.matchMedia('(min-width: 1024px)')
    const onChange = e => setIsDesktop(e.matches)
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])
  return isDesktop
}

function Chevron({ open }) {
  return (
    <svg
      className={`chevron${open ? ' open' : ''}`}
      viewBox="0 0 24 24" width="16" height="16"
      fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"
    >
      <path d="m9 6 6 6-6 6" />
    </svg>
  )
}

export default function History() {
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedId, setSelectedId] = useState(null)
  const isDesktop = useIsDesktop()

  useEffect(() => {
    apiFetch('/api/sessions?limit=100')
      .then(setSessions)
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [])

  // Desktop two-pane: the latest session is selected by default
  useEffect(() => {
    if (isDesktop && selectedId === null && sessions.length > 0) {
      setSelectedId(sessions[0].id)
    }
  }, [isDesktop, selectedId, sessions])

  const selected = sessions.find(s => s.id === selectedId)

  async function deleteSession(s) {
    if (!confirm(`Delete "${s.name}" (${fmtDate(s.started_at)})? Its logged sets are removed for good and PRs/ranks will recompute without them.`)) return
    try {
      await apiFetch(`/api/sessions/${s.id}`, { method: 'DELETE' })
      setSessions(list => list.filter(x => x.id !== s.id))
      if (selectedId === s.id) setSelectedId(null)
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="page wide">
      <h1>History</h1>
      <ErrorBox error={error} />
      {loading && <Loading />}

      {!loading && sessions.length === 0 && (
        <EmptyState>No workouts logged yet. Start one from the Workout tab.</EmptyState>
      )}

      {sessions.length > 0 && (
        <div className="hist-grid">
          <div className="col" style={{ gap: '0.5rem' }}>
            {sessions.map(s => {
              const isSelected = selectedId === s.id
              return (
                <div
                  key={s.id}
                  className={`card card-interactive${isSelected ? ' selected' : ''}`}
                  style={{ margin: 0 }}
                  onClick={() => setSelectedId(isDesktop ? s.id : (isSelected ? null : s.id))}
                >
                  <div className="row">
                    <div style={{ flex: 1 }}>
                      <strong>{s.name}</strong>
                      <div className="muted" style={{ fontSize: '0.8rem' }}>
                        {fmtDate(s.started_at)}
                        {s.ended_at
                          ? ` · ${durationMin(s.started_at, s.ended_at)} min`
                          : <span className="text-warning"> · in progress</span>}
                      </div>
                    </div>
                    <button
                      className="secondary" aria-label={`Delete ${s.name}`} title="Delete session"
                      style={{ minWidth: 36, padding: '0.25rem 0.5rem', color: 'var(--color-danger)' }}
                      onClick={e => { e.stopPropagation(); deleteSession(s) }}
                    >
                      🗑
                    </button>
                    <Chevron open={isSelected} />
                  </div>

                  {/* Phone: detail expands inline under the selected card */}
                  {isSelected && !isDesktop && <SessionDetail sessionId={s.id} />}
                </div>
              )
            })}
          </div>

          {/* Laptop: detail rides in a sticky right pane */}
          {isDesktop && (
            <aside className="hist-detail-pane">
              <div className="card" style={{ margin: 0 }}>
                {selected ? (
                  <>
                    <div className="row">
                      <h3 style={{ margin: 0, flex: 1 }}>{selected.name}</h3>
                      <span className="muted" style={{ fontSize: '0.8rem' }}>
                        {fmtDate(selected.started_at)}
                        {selected.ended_at && ` · ${durationMin(selected.started_at, selected.ended_at)} min`}
                      </span>
                    </div>
                    <SessionDetail sessionId={selected.id} />
                  </>
                ) : (
                  <p className="muted" style={{ textAlign: 'center', padding: '1rem 0' }}>
                    Select a session.
                  </p>
                )}
              </div>
            </aside>
          )}
        </div>
      )}
    </div>
  )
}

// Expanded detail — lazy-loads the full session
function SessionDetail({ sessionId }) {
  const [detail, setDetail] = useState(null)
  const [error, setError] = useState(null)

  useEffect(() => {
    setDetail(null)
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
        return (
          <div key={se.id} style={{ marginBottom: '0.75rem' }}>
            <Link
              to={`/exercise/${se.exercise_id}`}
              style={{ fontWeight: 600 }}
              onClick={e => e.stopPropagation()}
            >
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

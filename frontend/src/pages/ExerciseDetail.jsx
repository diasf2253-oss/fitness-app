/**
 * ExerciseDetail page (Phase 1d).
 * - Current PRs for the exercise
 * - Charts (Recharts): estimated 1RM over time, total volume per session
 * - Full history of working sets per session
 */
import React, { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import { apiFetch } from '../api'
import { Loading, ErrorBox, EmptyState } from '../components/States'

export default function ExerciseDetail() {
  const { id } = useParams()
  const navigate = useNavigate()
  const [exercise, setExercise] = useState(null)
  const [pr, setPr] = useState(null)
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    Promise.all([
      apiFetch(`/api/exercises/${id}`),
      apiFetch(`/api/stats/prs/${id}`),
      apiFetch(`/api/stats/exercise/${id}/history`),
    ])
      .then(([ex, prData, hist]) => {
        setExercise(ex)
        setPr(prData)
        setHistory(hist)
      })
      .catch(err => setError(err.message))
      .finally(() => setLoading(false))
  }, [id])

  if (loading) return <div className="page"><Loading /></div>

  return (
    <div className="page">
      <div className="row">
        <button className="secondary" onClick={() => navigate(-1)}>‹ Back</button>
        <span className="spacer" />
      </div>

      <ErrorBox error={error} />

      {exercise && (
        <>
          <h1 style={{ marginTop: '0.5rem' }}>{exercise.name}</h1>
          <p className="muted">
            {exercise.primary_muscle}{exercise.equipment ? ` · ${exercise.equipment}` : ''}
          </p>
        </>
      )}

      {/* PRs */}
      {pr ? (
        <div className="card">
          <h2>Personal Records</h2>
          <div className="row" style={{ justifyContent: 'space-around', textAlign: 'center', marginTop: '0.5rem' }}>
            <div>
              <div style={{ fontSize: '1.3rem', fontWeight: 700 }}>{pr.heaviest_weight_kg}</div>
              <div className="muted" style={{ fontSize: '0.75rem' }}>kg heaviest</div>
            </div>
            <div>
              <div style={{ fontSize: '1.3rem', fontWeight: 700 }}>{pr.best_estimated_1rm}</div>
              <div className="muted" style={{ fontSize: '0.75rem' }}>est. 1RM</div>
            </div>
            <div>
              <div style={{ fontSize: '1.3rem', fontWeight: 700 }}>{pr.best_set_volume}</div>
              <div className="muted" style={{ fontSize: '0.75rem' }}>best set vol</div>
            </div>
          </div>
        </div>
      ) : (
        <EmptyState>No completed working sets yet for this exercise.</EmptyState>
      )}

      {/* Charts */}
      {history.length > 0 ? (
        <>
          <div className="card">
            <h3>Estimated 1RM over time</h3>
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={history} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                <XAxis dataKey="date" stroke="#888" fontSize={11} />
                <YAxis stroke="#888" fontSize={11} domain={['auto', 'auto']} />
                <Tooltip contentStyle={{ background: '#1a1a1a', border: '1px solid #333' }} />
                <Line type="monotone" dataKey="estimated_1rm" stroke="#4f8ef7" strokeWidth={2} dot={{ r: 3 }} name="Est. 1RM (kg)" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="card">
            <h3>Volume per session</h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={history} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                <XAxis dataKey="date" stroke="#888" fontSize={11} />
                <YAxis stroke="#888" fontSize={11} />
                <Tooltip contentStyle={{ background: '#1a1a1a', border: '1px solid #333' }} />
                <Bar dataKey="volume_kg" fill="#3dba6f" name="Volume (kg)" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      ) : (
        <EmptyState>Log some sets to see your progress charts here.</EmptyState>
      )}
    </div>
  )
}

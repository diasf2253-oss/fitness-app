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
              <div className="stat-num" style={{ fontSize: '1.8rem' }}>{pr.heaviest_weight_kg}</div>
              <div className="muted" style={{ fontSize: '0.7rem', letterSpacing: '0.1em', textTransform: 'uppercase' }}>kg heaviest</div>
            </div>
            <div>
              <div className="stat-num" style={{ fontSize: '1.8rem' }}>{pr.best_estimated_1rm}</div>
              <div className="muted" style={{ fontSize: '0.7rem', letterSpacing: '0.1em', textTransform: 'uppercase' }}>est. 1RM</div>
            </div>
            <div>
              <div className="stat-num" style={{ fontSize: '1.8rem' }}>{pr.best_set_volume}</div>
              <div className="muted" style={{ fontSize: '0.7rem', letterSpacing: '0.1em', textTransform: 'uppercase' }}>best set vol</div>
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
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(236,233,224,0.07)" />
                <XAxis dataKey="date" stroke="#9aa69b" fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke="#9aa69b" fontSize={11} domain={['auto', 'auto']} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ background: '#1d2521', border: '1px solid rgba(236,233,224,0.12)', borderRadius: 12, color: '#ece9e0' }} />
                <Line type="monotone" dataKey="estimated_1rm" stroke="#a8bfa1" strokeWidth={2} dot={{ r: 3, fill: '#a8bfa1', strokeWidth: 0 }} name="Est. 1RM (kg)" />
              </LineChart>
            </ResponsiveContainer>
          </div>

          <div className="card">
            <h3>Volume per session</h3>
            <ResponsiveContainer width="100%" height={220}>
              <BarChart data={history} margin={{ top: 10, right: 10, left: -10, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(236,233,224,0.07)" />
                <XAxis dataKey="date" stroke="#9aa69b" fontSize={11} tickLine={false} axisLine={false} />
                <YAxis stroke="#9aa69b" fontSize={11} tickLine={false} axisLine={false} />
                <Tooltip contentStyle={{ background: '#1d2521', border: '1px solid rgba(236,233,224,0.12)', borderRadius: 12, color: '#ece9e0' }} cursor={{ fill: 'rgba(236,233,224,0.05)' }} />
                <Bar dataKey="volume_kg" fill="#7f9b78" name="Volume (kg)" radius={[6, 6, 0, 0]} />
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

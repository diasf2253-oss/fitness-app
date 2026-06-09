/**
 * Dashboard — home screen.
 * Phase 0: shows API connectivity status via /api/ping.
 * Phase 2+: weight chart, steps, sleep, nutrition targets, training volume, PRs.
 */
import React, { useEffect, useState } from 'react'
import { apiFetch } from '../api'

export default function Dashboard() {
  const [pingStatus, setPingStatus] = useState('checking…')
  const [pingError, setPingError] = useState(null)

  useEffect(() => {
    // /api/ping is public — no auth needed
    fetch('/api/ping')
      .then(r => r.json())
      .then(data => setPingStatus(data.status))
      .catch(err => {
        setPingStatus('unreachable')
        setPingError(err.message)
      })
  }, [])

  return (
    <div className="page">
      <h1>Dashboard</h1>

      {/* API connectivity indicator */}
      <div className="card">
        <h3>API Status</h3>
        <div className="row" style={{ marginTop: '0.5rem' }}>
          <span
            style={{
              width: 10,
              height: 10,
              borderRadius: '50%',
              background: pingStatus === 'ok' ? 'var(--color-success)' : 'var(--color-danger)',
              flexShrink: 0,
            }}
          />
          <span>
            Backend:{' '}
            <strong style={{ color: pingStatus === 'ok' ? 'var(--color-success)' : 'var(--color-danger)' }}>
              {pingStatus}
            </strong>
          </span>
        </div>
        {pingError && <p className="muted" style={{ marginTop: '0.25rem' }}>{pingError}</p>}
      </div>

      <div className="card">
        <p className="muted" style={{ textAlign: 'center', padding: '1rem 0' }}>
          Dashboard charts will appear here after you log some data.<br />
          Start by logging a workout or entering health data in Settings.
        </p>
      </div>
    </div>
  )
}

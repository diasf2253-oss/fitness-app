/**
 * Dashboard — home screen.
 * Editorial greeting hero (date badge + serif headline), placeholder for
 * Phase 2+ widgets (weight chart, steps, sleep, nutrition, volume, PRs).
 * Backend connectivity is shown as a quiet status line at the bottom.
 */
import React, { useEffect, useState } from 'react'

export default function Dashboard() {
  const [pingStatus, setPingStatus] = useState('checking…')

  useEffect(() => {
    // /api/ping is public — no auth needed
    fetch('/api/ping')
      .then(r => r.json())
      .then(data => setPingStatus(data.status))
      .catch(() => setPingStatus('unreachable'))
  }, [])

  const now = new Date()
  const dateLabel = now.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })
  const hour = now.getHours()
  const greeting = hour < 12 ? 'morning' : hour < 18 ? 'afternoon' : 'evening'

  return (
    <div className="page">
      {/* Editorial hero — quiet, dated, personal */}
      <span className="badge dot">{dateLabel}</span>
      <h1 style={{ fontSize: '2.4rem', marginTop: '0.9rem' }}>
        Good <em>{greeting}</em>
      </h1>
      <p className="muted" style={{ marginBottom: '1.5rem' }}>
        Here's where things stand.
      </p>

      <div className="card">
        <p className="muted" style={{ textAlign: 'center', padding: '1.25rem 0' }}>
          Your day at a glance will live here —<br />
          training, weight, sleep, and nutrition as you log them.
        </p>
      </div>

      {/* Quiet connectivity indicator, not a debug card */}
      <div className="row" style={{ justifyContent: 'center', gap: '0.45rem', marginTop: '1.25rem' }}>
        <span
          style={{
            width: 7, height: 7, borderRadius: '50%', flexShrink: 0,
            background: pingStatus === 'ok' ? 'var(--color-success)' : 'var(--color-danger)',
          }}
        />
        <span className="muted" style={{ fontSize: '0.72rem', letterSpacing: '0.08em', textTransform: 'uppercase' }}>
          {pingStatus === 'ok' ? 'Synced' : `Backend ${pingStatus}`}
        </span>
      </div>
    </div>
  )
}

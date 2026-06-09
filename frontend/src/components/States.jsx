/**
 * Small reusable loading / error / empty-state components.
 * Every page that fetches data uses these for consistent UX.
 */
import React from 'react'

export function Loading({ label = 'Loading…' }) {
  return <div className="loading">{label}</div>
}

export function ErrorBox({ error }) {
  if (!error) return null
  return <div className="error-msg">{String(error)}</div>
}

export function EmptyState({ children }) {
  return (
    <div className="card">
      <p className="muted" style={{ textAlign: 'center', padding: '1rem 0' }}>
        {children}
      </p>
    </div>
  )
}

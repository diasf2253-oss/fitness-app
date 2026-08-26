/**
 * Small reusable loading / error / empty-state components.
 * Every page that fetches data uses these for consistent UX.
 */
import React from 'react'
import { Link } from 'react-router-dom'

export function Loading({ label = 'Loading…' }) {
  return <div className="loading">{label}</div>
}

export function ErrorBox({ error }) {
  if (!error) return null
  return <div className="error-msg">{String(error)}</div>
}

/** The cairn mark — quiet brand moment wherever there's nothing yet. */
function CairnMark() {
  return (
    <svg viewBox="0 0 48 48" width="34" height="34" aria-hidden="true"
      style={{ display: 'block', margin: '0 auto 0.55rem', opacity: 0.45 }}>
      <ellipse cx="24" cy="33" rx="14" ry="5" fill="#7f9b78" />
      <ellipse cx="24" cy="24.5" rx="10.5" ry="4.4" fill="#a8bfa1" />
      <ellipse cx="24" cy="17" rx="7" ry="3.6" fill="#ece9e0" />
    </svg>
  )
}

export function EmptyState({ children }) {
  return (
    <div className="card" style={{ textAlign: 'center', padding: '1.6rem 1rem' }}>
      <CairnMark />
      <p className="muted">{children}</p>
    </div>
  )
}

/**
 * Lighter, inline empty note for a single card or tile (vs the full-view
 * EmptyState card). With no children it falls back to a "log manually" nudge.
 */
export function EmptyNote({ children }) {
  return (
    <p className="muted" style={{ textAlign: 'center', padding: '1.1rem 0' }}>
      {children || <>No data yet. <Link to="/log">Log manually ›</Link></>}
    </p>
  )
}

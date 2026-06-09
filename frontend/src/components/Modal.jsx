/**
 * A simple full-screen modal overlay, mobile-friendly.
 * Renders children centered over a dimmed backdrop. Click backdrop to close.
 */
import React from 'react'

export default function Modal({ title, onClose, children }) {
  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.7)',
        display: 'flex',
        alignItems: 'flex-end',
        justifyContent: 'center',
        zIndex: 200,
      }}
    >
      <div
        onClick={e => e.stopPropagation()}  // don't close when clicking inside
        style={{
          background: 'var(--color-surface)',
          borderTopLeftRadius: 16,
          borderTopRightRadius: 16,
          border: '1px solid var(--color-border)',
          width: '100%',
          maxWidth: 680,
          maxHeight: '85dvh',
          overflowY: 'auto',
          padding: '1rem',
        }}
      >
        <div className="row" style={{ marginBottom: '0.75rem' }}>
          <h2 style={{ margin: 0 }}>{title}</h2>
          <span className="spacer" />
          <button className="secondary" onClick={onClose} style={{ minWidth: 44 }}>✕</button>
        </div>
        {children}
      </div>
    </div>
  )
}

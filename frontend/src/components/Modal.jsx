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
        background: 'rgba(10, 14, 12, 0.6)',
        backdropFilter: 'blur(6px)',
        WebkitBackdropFilter: 'blur(6px)',
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
          borderTopLeftRadius: 24,
          borderTopRightRadius: 24,
          border: '1px solid var(--color-border-str)',
          width: '100%',
          maxWidth: 680,
          maxHeight: '85dvh',
          overflowY: 'auto',
          padding: '1.1rem 1.1rem calc(1.1rem + env(safe-area-inset-bottom))',
          boxShadow: 'var(--shadow-lg)',
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

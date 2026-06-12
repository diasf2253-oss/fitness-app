/**
 * WidgetLabel — the tracked-out uppercase micro-label used as a data
 * label on card edges ("LAST 7 DAYS", "90 DAYS · 7-DAY AVG").
 * One per card edge; never a section eyebrow.
 */
import React from 'react'

export default function WidgetLabel({ children }) {
  return (
    <span className="muted" style={{ fontSize: '0.72rem', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
      {children}
    </span>
  )
}

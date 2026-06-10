/**
 * MonthCalendar — the dashboard rail calendar (Phase 4).
 * Monday-first month grid with data markers from /api/calendar:
 *   - sage dot      = a workout happened that day
 *   - lifted cell   = any health data exists (weight/steps/sleep/nutrition)
 * Clicking a day calls onSelect(isoDate) so the parent can show details.
 */
import React, { useEffect, useMemo, useState } from 'react'
import { apiFetch } from '../api'

function isoOf(year, month, day) {
  return `${year}-${String(month).padStart(2, '0')}-${String(day).padStart(2, '0')}`
}

const DOW = ['Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa', 'Su']

export default function MonthCalendar({ selected, onSelect }) {
  const today = new Date()
  const [year, setYear] = useState(today.getFullYear())
  const [month, setMonth] = useState(today.getMonth() + 1) // 1-12
  const [markers, setMarkers] = useState({})               // iso date -> CalendarDay

  useEffect(() => {
    apiFetch(`/api/calendar/${year}/${month}`)
      .then(data => {
        const map = {}
        data.days.forEach(d => { map[d.date] = d })
        setMarkers(map)
      })
      .catch(() => setMarkers({}))  // markers are decorative; fail quiet
  }, [year, month])

  function shift(delta) {
    let m = month + delta
    let y = year
    if (m < 1) { m = 12; y -= 1 }
    if (m > 12) { m = 1; y += 1 }
    setMonth(m)
    setYear(y)
  }

  const cells = useMemo(() => {
    const first = new Date(year, month - 1, 1)
    const daysInMonth = new Date(year, month, 0).getDate()
    const lead = (first.getDay() + 6) % 7  // Monday-first offset
    return [
      ...Array.from({ length: lead }, () => null),
      ...Array.from({ length: daysInMonth }, (_, i) => i + 1),
    ]
  }, [year, month])

  const todayIso = isoOf(today.getFullYear(), today.getMonth() + 1, today.getDate())
  const monthLabel = new Date(year, month - 1).toLocaleDateString('en-US', {
    month: 'long', year: 'numeric',
  })

  return (
    <div className="card">
      <div className="cal-head">
        <span className="cal-month">{monthLabel}</span>
        <button className="cal-nav-btn" onClick={() => shift(-1)} aria-label="Previous month">‹</button>
        <button className="cal-nav-btn" onClick={() => shift(1)} aria-label="Next month">›</button>
      </div>
      <div className="cal-grid">
        {DOW.map(d => <span key={d} className="cal-dow">{d}</span>)}
        {cells.map((day, i) => {
          if (day === null) return <span key={`x${i}`} className="cal-cell empty" />
          const iso = isoOf(year, month, day)
          const m = markers[iso]
          const hasHealth = m && (m.has_weight || m.has_sleep || m.has_nutrition || m.steps != null)
          const classes = [
            'cal-cell',
            hasHealth ? 'has-data' : '',
            iso === todayIso ? 'today' : '',
            iso === selected ? 'selected' : '',
          ].filter(Boolean).join(' ')
          return (
            <button key={iso} className={classes} onClick={() => onSelect(iso)}>
              {day}
              {m && m.sessions > 0 && <span className="cal-dot" />}
            </button>
          )
        })}
      </div>
    </div>
  )
}

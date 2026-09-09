/**
 * CheckIn — the dashboard's daily check-in card (Phase 6).
 * One tap-friendly surface for every active tracker:
 *   habit  → pill toggles done/not-done (un-doing clears the day's log)
 *   scale  → five dots, 1–5 (e.g. Mood)
 *   number → inline value + unit, saved on blur
 *   text   → small textarea (e.g. Journal), saved on blur
 * Every save re-fetches the list so streaks stay honest.
 */
import React, { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../api'
import { parseDecimal } from '../num'
import { ErrorBox } from './States'

function localTodayIso() {
  const d = new Date()
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

function HabitPill({ tracker, onToggle }) {
  const done = (tracker.today?.value_num ?? 0) >= 1
  return (
    <button
      onClick={() => onToggle(done)}
      style={{
        background: done ? 'var(--tint-success)' : 'rgba(236,233,224,0.06)',
        color: done ? 'var(--color-success)' : 'var(--color-text)',
        border: `1px solid ${done ? 'rgba(143,181,115,0.35)' : 'var(--color-border)'}`,
        boxShadow: 'none',
        padding: '0.45rem 0.95rem',
        minHeight: 40,
        fontSize: '0.85rem',
        fontWeight: 500,
      }}
    >
      {done ? '✓ ' : ''}{tracker.name}
      {tracker.streak > 0 && (
        <span style={{ opacity: 0.65, marginLeft: 6, fontSize: '0.72rem' }} className="tnum">
          {tracker.streak}d
        </span>
      )}
    </button>
  )
}

function ScaleRow({ tracker, onSet }) {
  const current = tracker.today?.value_num ?? null
  return (
    <div className="row" style={{ justifyContent: 'space-between', padding: '0.45rem 0' }}>
      <span style={{ fontSize: '0.88rem' }}>{tracker.name}</span>
      <div className="row" style={{ gap: '0.35rem' }}>
        {[1, 2, 3, 4, 5].map(n => {
          const selected = current === n
          return (
            <button
              key={n}
              onClick={() => onSet(selected ? null : n)}
              aria-label={`${tracker.name} ${n} of 5`}
              style={{
                width: 32, minWidth: 32, height: 32, minHeight: 32, padding: 0,
                borderRadius: '50%', fontSize: '0.75rem', boxShadow: 'none',
                background: selected ? 'var(--color-primary)' : 'transparent',
                color: selected ? 'var(--color-on-primary)' : 'var(--color-muted)',
                border: selected ? 'none' : '1px solid var(--color-border)',
              }}
              className="tnum"
            >
              {n}
            </button>
          )
        })}
      </div>
    </div>
  )
}

function NumberRow({ tracker, onSave }) {
  const value = tracker.today?.value_num ?? ''
  return (
    <div className="row" style={{ justifyContent: 'space-between', padding: '0.45rem 0' }}>
      <span style={{ fontSize: '0.88rem' }}>{tracker.name}</span>
      <div className="row" style={{ gap: '0.4rem' }}>
        <input
          key={`${tracker.id}-${value}`}
          type="text"
          inputMode="decimal"
          defaultValue={value}
          placeholder="–"
          onBlur={e => {
            const next = parseDecimal(e.target.value)
            if (next !== (tracker.today?.value_num ?? null)) onSave(next)
          }}
          style={{ width: 90, minHeight: 38, textAlign: 'center', padding: '0.3rem' }}
        />
        {tracker.unit && <span className="muted" style={{ fontSize: '0.78rem' }}>{tracker.unit}</span>}
      </div>
    </div>
  )
}

function TextRow({ tracker, onSave }) {
  const value = tracker.today?.value_text ?? ''
  return (
    <div style={{ padding: '0.45rem 0' }}>
      <span style={{ fontSize: '0.88rem' }}>{tracker.name}</span>
      <textarea
        key={`${tracker.id}-${value}`}
        rows={2}
        defaultValue={value}
        placeholder="A line about today…"
        onBlur={e => {
          if (e.target.value.trim() !== value.trim()) onSave(e.target.value)
        }}
        style={{ marginTop: '0.4rem', fontSize: '0.9rem' }}
      />
    </div>
  )
}

export default function CheckIn() {
  const [trackers, setTrackers] = useState(null)
  const [error, setError] = useState(null)
  const today = localTodayIso()

  const load = useCallback(() => {
    apiFetch('/api/trackers')
      .then(setTrackers)
      .catch(err => setError(err.message))
  }, [])

  useEffect(load, [load])

  async function save(tracker, payload) {
    try {
      await apiFetch(`/api/trackers/${tracker.id}/log`, {
        method: 'POST',
        body: JSON.stringify({ date: today, value_num: null, value_text: null, ...payload }),
      })
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  if (!trackers && !error) return null

  const habits = (trackers || []).filter(t => t.kind === 'habit')
  const others = (trackers || []).filter(t => t.kind !== 'habit')

  return (
    <div className="card span-2">
      <div className="row" style={{ marginBottom: '0.6rem' }}>
        <h3 style={{ margin: 0, flex: 1 }}>Daily check-in</h3>
        <Link to="/settings" className="muted" style={{ fontSize: '0.75rem' }}>Manage ›</Link>
      </div>
      <ErrorBox error={error} />

      {trackers && trackers.length === 0 && (
        <p className="muted" style={{ textAlign: 'center', padding: '0.75rem 0' }}>
          No trackers yet — add habits, scales or metrics in <Link to="/settings">Settings</Link>.
        </p>
      )}

      {habits.length > 0 && (
        <div className="row" style={{ flexWrap: 'wrap', gap: '0.5rem', marginBottom: others.length ? '0.5rem' : 0 }}>
          {habits.map(t => (
            <HabitPill
              key={t.id}
              tracker={t}
              onToggle={done => save(t, { value_num: done ? null : 1 })}
            />
          ))}
        </div>
      )}

      {others.map((t, i) => (
        <div key={t.id} style={{ borderTop: i > 0 || habits.length > 0 ? '1px solid var(--color-border)' : 'none' }}>
          {t.kind === 'scale' && <ScaleRow tracker={t} onSet={n => save(t, { value_num: n })} />}
          {t.kind === 'number' && <NumberRow tracker={t} onSave={n => save(t, { value_num: n })} />}
          {t.kind === 'text' && <TextRow tracker={t} onSave={text => save(t, { value_text: text })} />}
        </div>
      ))}
    </div>
  )
}

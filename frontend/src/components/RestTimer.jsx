/**
 * RestTimer — a sticky countdown bar shown after completing a set.
 *
 * Behaviour:
 *  - Counts down from `seconds`
 *  - −15 / +15 quick adjust; pause/resume; while paused, add a custom amount
 *  - Plays a beep + browser notification when it reaches zero
 *
 * Props:
 *   seconds  — starting duration in seconds
 *   onDone   — called once when the timer hits zero
 *   onClose  — called when user dismisses/skips the timer
 */
import React, { useEffect, useRef, useState } from 'react'

// Play a short beep using the Web Audio API (no audio file needed)
function beep() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.frequency.value = 880
    osc.type = 'sine'
    gain.gain.setValueAtTime(0.3, ctx.currentTime)
    osc.start()
    // Fade out and stop after 0.4s
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.4)
    osc.stop(ctx.currentTime + 0.4)
  } catch (_) {
    // Audio may be blocked until first user interaction — ignore silently
  }
}

function notify(text) {
  if ('Notification' in window && Notification.permission === 'granted') {
    new Notification('Rest complete', { body: text })
  }
}

function fmt(total) {
  const m = Math.floor(total / 60)
  const s = total % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

export default function RestTimer({ seconds, onDone, onClose }) {
  const [remaining, setRemaining] = useState(seconds)
  const [paused, setPaused] = useState(false)
  const [addInput, setAddInput] = useState('')   // custom seconds to add while paused
  const firedRef = useRef(false)

  function addCustom() {
    const n = parseInt(addInput, 10)
    if (n) setRemaining(r => Math.max(0, r + n))
    setAddInput('')
  }

  useEffect(() => {
    // Tick every second; a paused timer keeps its remaining time.
    if (paused) return undefined
    const id = setInterval(() => {
      setRemaining(r => r - 1)
    }, 1000)
    return () => clearInterval(id)
  }, [paused])

  useEffect(() => {
    if (remaining <= 0 && !firedRef.current) {
      firedRef.current = true
      beep()
      notify('Time to start your next set.')
      onDone?.()
    }
  }, [remaining, onDone])

  const isDone = remaining <= 0

  return (
    <div
      style={{
        position: 'fixed',
        bottom: 'calc(86px + env(safe-area-inset-bottom))',
        left: 14,
        right: 14,
        maxWidth: 560,
        margin: '0 auto',
        background: isDone ? 'var(--color-success)' : 'var(--color-primary)',
        color: 'var(--color-on-primary)',
        opacity: paused ? 0.85 : 1,
        padding: '0.55rem 0.6rem 0.55rem 1.2rem',
        borderRadius: 'var(--radius-pill)',
        display: 'flex',
        alignItems: 'center',
        gap: '0.45rem',
        zIndex: 150,
        boxShadow: 'var(--shadow-lg)',
        animation: 'rise-in 0.22s var(--ease)',
      }}
    >
      <span style={{ fontSize: '1.35rem', fontWeight: 500, fontVariantNumeric: 'tabular-nums', minWidth: 64 }}>
        {isDone ? 'Done' : fmt(remaining)}
      </span>
      <span style={{ fontSize: '0.72rem', letterSpacing: '0.1em', textTransform: 'uppercase', opacity: 0.65 }}>
        {paused && !isDone ? 'paused' : 'rest'}
      </span>
      <span className="spacer" />
      {!isDone && !paused && (
        <>
          <button
            style={{ background: 'rgba(27,33,29,0.10)', color: 'var(--color-on-primary)', minWidth: 56, boxShadow: 'none' }}
            onClick={() => setRemaining(r => Math.max(0, r - 15))}
          >
            −15
          </button>
          <button
            style={{ background: 'rgba(27,33,29,0.10)', color: 'var(--color-on-primary)', minWidth: 56, boxShadow: 'none' }}
            onClick={() => setRemaining(r => r + 15)}
          >
            +15
          </button>
        </>
      )}
      {!isDone && paused && (
        <>
          <input
            type="number" inputMode="numeric" min="0" value={addInput}
            onChange={e => setAddInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') addCustom() }}
            placeholder="sec" aria-label="Seconds to add"
            style={{
              width: 58, padding: '0.35rem 0.4rem', boxShadow: 'none', margin: 0,
              background: 'rgba(27,33,29,0.14)', color: 'var(--color-on-primary)',
              border: '1px solid rgba(27,33,29,0.2)', borderRadius: 'var(--radius-sm)',
              fontVariantNumeric: 'tabular-nums',
            }}
          />
          <button
            style={{ background: 'rgba(27,33,29,0.10)', color: 'var(--color-on-primary)', minWidth: 52, boxShadow: 'none' }}
            onClick={addCustom}
          >
            Add
          </button>
        </>
      )}
      {!isDone && (
        <button
          aria-label={paused ? 'Resume timer' : 'Pause timer'}
          style={{ background: 'rgba(27,33,29,0.10)', color: 'var(--color-on-primary)', minWidth: 52, boxShadow: 'none' }}
          onClick={() => setPaused(p => !p)}
        >
          {paused ? '▶' : '⏸'}
        </button>
      )}
      <button
        style={{ background: 'rgba(27,33,29,0.18)', color: 'var(--color-on-primary)', boxShadow: 'none' }}
        onClick={onClose}
      >
        {isDone ? 'Dismiss' : 'Skip'}
      </button>
    </div>
  )
}

/**
 * RestTimer — a sticky countdown bar shown after completing a set.
 *
 * Behaviour:
 *  - Counts down from `seconds`
 *  - Shows remaining time large and tappable (+15s / -15s / skip)
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
  const firedRef = useRef(false)

  useEffect(() => {
    // Tick every second
    const id = setInterval(() => {
      setRemaining(r => r - 1)
    }, 1000)
    return () => clearInterval(id)
  }, [])

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
        bottom: 'calc(70px + env(safe-area-inset-bottom))',
        left: 0,
        right: 0,
        background: isDone ? 'var(--color-success)' : 'var(--color-primary)',
        color: '#fff',
        padding: '0.75rem 1rem',
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem',
        zIndex: 150,
        boxShadow: '0 -2px 10px rgba(0,0,0,0.3)',
      }}
    >
      <span style={{ fontSize: '1.4rem', fontWeight: 700, fontVariantNumeric: 'tabular-nums', minWidth: 64 }}>
        {isDone ? 'Done!' : fmt(remaining)}
      </span>
      <span className="spacer" />
      {!isDone && (
        <>
          <button
            className="secondary"
            style={{ background: 'rgba(255,255,255,0.2)', color: '#fff', minWidth: 56 }}
            onClick={() => setRemaining(r => Math.max(0, r - 15))}
          >
            −15
          </button>
          <button
            className="secondary"
            style={{ background: 'rgba(255,255,255,0.2)', color: '#fff', minWidth: 56 }}
            onClick={() => setRemaining(r => r + 15)}
          >
            +15
          </button>
        </>
      )}
      <button
        className="secondary"
        style={{ background: 'rgba(0,0,0,0.25)', color: '#fff' }}
        onClick={onClose}
      >
        {isDone ? 'Dismiss' : 'Skip'}
      </button>
    </div>
  )
}

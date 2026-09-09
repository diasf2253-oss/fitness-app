/**
 * RestTimer — a sticky countdown bar shown after completing a set.
 *
 * Deliberately minimal: the countdown plus exactly two controls, Pause/Resume
 * and Skip. There is no −15/+15 or "add seconds" — the owner asked for a bar
 * that doesn't need reading mid-set. Rest duration comes from the routine's
 * rest_seconds when set, otherwise the Settings default (see restForExercise
 * in pages/Workout.jsx); it is not adjusted from here.
 *
 * Props:
 *   seconds  — starting duration in seconds
 *   onDone   — called once when the timer hits zero
 *   onClose  — called when the user dismisses/skips the timer
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

// Two short pulses; no-ops where the Vibration API is unsupported (iOS Safari)
function vibrate() {
  try { navigator.vibrate?.([200, 100, 200]) } catch (_) { /* ignore */ }
}

function fmt(total) {
  const m = Math.floor(total / 60)
  const s = total % 60
  return `${m}:${String(s).padStart(2, '0')}`
}

// Ghost button on the coloured bar. Generous height for gym thumbs; the two
// buttons sit at a fixed width so the row never overflows a ~360px phone.
const ctrlBtn = {
  flex: '0 0 auto',
  minWidth: 92,
  minHeight: 44,
  background: 'rgba(27,33,29,0.14)',
  color: 'var(--color-on-primary)',
  boxShadow: 'none',
  padding: '0.4rem 0.6rem',
}

export default function RestTimer({ seconds, onDone, onClose }) {
  const [remaining, setRemaining] = useState(seconds)
  const [paused, setPaused] = useState(false)
  const firedRef = useRef(false)

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
      vibrate()
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
        opacity: paused && !isDone ? 0.9 : 1,
        padding: '0.5rem 0.6rem 0.5rem 1.1rem',
        borderRadius: 'var(--radius-pill)',
        display: 'flex',
        alignItems: 'center',
        gap: '0.5rem',
        zIndex: 150,
        boxShadow: 'var(--shadow-lg)',
        animation: 'rise-in 0.22s var(--ease)',
      }}
    >
      <span style={{ fontSize: '1.5rem', fontWeight: 500, fontVariantNumeric: 'tabular-nums', minWidth: 66 }}>
        {isDone ? 'Done' : fmt(remaining)}
      </span>
      <span style={{ fontSize: '0.72rem', letterSpacing: '0.1em', textTransform: 'uppercase', opacity: 0.65 }}>
        {paused && !isDone ? 'paused' : 'rest'}
      </span>
      <span className="spacer" />
      {!isDone && (
        <button
          aria-label={paused ? 'Resume timer' : 'Pause timer'}
          style={ctrlBtn}
          onClick={() => setPaused(p => !p)}
        >
          {paused ? '▶ Resume' : '⏸ Pause'}
        </button>
      )}
      <button
        style={{ ...ctrlBtn, minWidth: 76, background: 'rgba(27,33,29,0.22)' }}
        onClick={onClose}
      >
        {isDone ? 'Dismiss' : 'Skip'}
      </button>
    </div>
  )
}

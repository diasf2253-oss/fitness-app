/**
 * RestTimer — a sticky countdown bar shown after completing a set.
 *
 * Behaviour:
 *  - Counts down from `seconds`
 *  - −15 / +15 quick adjust; pause/resume; while paused, add a custom amount
 *  - Plays a beep + vibration + browser notification when it reaches zero
 *
 * Mobile-first layout: the time sits on its own row, and the controls share a
 * full-width row below (each button flex:1), so nothing overflows a ~360px
 * phone — the old single-row pill pushed −15/+15 off-screen.
 *
 * Props:
 *   seconds  — starting duration in seconds
 *   onDone   — called once when the timer hits zero
 *   onClose  — called when user dismisses/skips the timer
 *   onAdjust — called with the delta (±seconds) on every manual adjustment,
 *              so the caller can learn real rest habits per exercise
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

// Shared style for the bar's ghost buttons — flex:1 so a row shares width evenly
// and never overflows the phone, with a comfortable tap height.
const ctrlBtn = {
  flex: 1,
  minHeight: 42,
  background: 'rgba(27,33,29,0.12)',
  color: 'var(--color-on-primary)',
  boxShadow: 'none',
  padding: '0.4rem 0.3rem',
  fontSize: '0.95rem',
}

export default function RestTimer({ seconds, onDone, onClose, onAdjust }) {
  const [remaining, setRemaining] = useState(seconds)
  const [paused, setPaused] = useState(false)
  const [addInput, setAddInput] = useState('')   // custom seconds to add while paused
  const firedRef = useRef(false)

  function adjust(delta) {
    setRemaining(r => Math.max(0, r + delta))
    onAdjust?.(delta)
  }

  function addCustom() {
    const n = parseInt(addInput, 10)
    if (n) adjust(n)
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
        padding: '0.6rem 0.7rem',
        borderRadius: 'var(--radius-lg)',
        display: 'flex',
        flexDirection: 'column',
        gap: '0.5rem',
        zIndex: 150,
        boxShadow: 'var(--shadow-lg)',
        animation: 'rise-in 0.22s var(--ease)',
      }}
    >
      {/* Row 1 — time + status + skip/dismiss */}
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', paddingLeft: '0.35rem' }}>
        <span style={{ fontSize: '1.7rem', fontWeight: 500, fontVariantNumeric: 'tabular-nums', minWidth: 70 }}>
          {isDone ? 'Done' : fmt(remaining)}
        </span>
        <span style={{ fontSize: '0.72rem', letterSpacing: '0.1em', textTransform: 'uppercase', opacity: 0.65 }}>
          {paused && !isDone ? 'paused' : 'rest'}
        </span>
        <span className="spacer" />
        <button
          style={{ ...ctrlBtn, flex: '0 0 auto', minWidth: 76, background: 'rgba(27,33,29,0.2)' }}
          onClick={onClose}
        >
          {isDone ? 'Dismiss' : 'Skip'}
        </button>
      </div>

      {/* Row 2 — controls; full-width buttons that never overflow */}
      {!isDone && !paused && (
        <div style={{ display: 'flex', gap: '0.4rem' }}>
          <button style={ctrlBtn} onClick={() => adjust(-15)}>−15s</button>
          <button style={ctrlBtn} onClick={() => adjust(15)}>+15s</button>
          <button style={ctrlBtn} onClick={() => setPaused(true)}>⏸ Pause</button>
        </div>
      )}
      {!isDone && paused && (
        <div style={{ display: 'flex', gap: '0.4rem' }}>
          <input
            type="number" inputMode="numeric" min="0" value={addInput}
            onChange={e => setAddInput(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') addCustom() }}
            placeholder="+ sec" aria-label="Seconds to add"
            style={{
              flex: '0 0 78px', padding: '0.4rem', boxShadow: 'none', margin: 0,
              background: 'rgba(27,33,29,0.16)', color: 'var(--color-on-primary)',
              border: '1px solid rgba(27,33,29,0.22)', borderRadius: 'var(--radius-sm)',
              fontVariantNumeric: 'tabular-nums', textAlign: 'center',
            }}
          />
          <button style={ctrlBtn} onClick={addCustom}>Add</button>
          <button style={ctrlBtn} onClick={() => setPaused(false)}>▶ Resume</button>
        </div>
      )}
    </div>
  )
}

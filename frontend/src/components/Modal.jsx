/**
 * Bottom-sheet modal, mobile-first.
 *
 * Built to the apple-design skill's rules for sheets:
 *  - Materializes in (slide + fade) and leaves along the SAME path (§7).
 *  - Drag the header down to dismiss: the sheet tracks the finger 1:1, rubber-bands
 *    upward (§9), and on release projects where the flick was heading (§6) to
 *    decide dismiss vs. spring back — carrying the release velocity (§5).
 *  - Interruptible: grabbing it mid-animation starts from its live on-screen
 *    position, never from the target (§3).
 *  - Backdrop dims as the sheet moves; Esc and backdrop-tap also close it.
 *  - prefers-reduced-motion: a short cross-fade instead of sliding.
 *
 * The parent still just renders <Modal onClose={...}> and unmounts it in onClose;
 * we delay calling onClose until the exit animation has finished.
 */
import React, { useCallback, useEffect, useLayoutEffect, useRef } from 'react'

const EASE_OUT = 'cubic-bezier(0.32, 0.72, 0, 1)'
const DECEL = 0.998 // Apple's "normal" scroll deceleration rate

// Where a flick of `v` px/s would come to rest (exponential decay, WWDC 2018).
const project = (v) => ((v / 1000) * DECEL) / (1 - DECEL)

// Progressive resistance past an edge: the further you pull, the less it follows.
const rubberband = (over, dim, c = 0.55) => (over * dim * c) / (dim + c * Math.abs(over))

const prefersReducedMotion = () =>
  typeof window !== 'undefined' &&
  window.matchMedia?.('(prefers-reduced-motion: reduce)').matches

// The sheet's live translateY, even mid-animation (the "presentation" value).
function liveY(el) {
  const t = getComputedStyle(el).transform
  if (!t || t === 'none') return 0
  try { return new DOMMatrixReadOnly(t).m42 } catch { return 0 }
}

export default function Modal({ title, onClose, children }) {
  const sheetRef = useRef(null)
  const backdropRef = useRef(null)
  const anims = useRef([])      // running Web Animations, so a grab can cancel them
  const closing = useRef(false)
  const drag = useRef(null)     // { startY, startOffset, samples: [{y, t}] }

  const stopAnims = () => {
    anims.current.forEach(a => { try { a.cancel() } catch { /* already done */ } })
    anims.current = []
  }

  // Run sheet + backdrop animations together from the current values.
  const play = useCallback((fromY, toY, duration, backdropTo, done) => {
    const sheet = sheetRef.current, back = backdropRef.current
    if (!sheet || !back) return
    const h = sheet.offsetHeight || 1
    const backFrom = parseFloat(back.style.opacity || '1')
    stopAnims()
    sheet.style.transform = `translateY(${toY}px)`
    back.style.opacity = String(backdropTo)
    const a1 = sheet.animate(
      [{ transform: `translateY(${fromY}px)` }, { transform: `translateY(${toY}px)` }],
      { duration, easing: EASE_OUT })
    const a2 = back.animate(
      [{ opacity: Math.min(1, Math.max(0, backFrom)) }, { opacity: backdropTo }],
      { duration, easing: 'ease-out' })
    anims.current = [a1, a2]
    if (done) a1.onfinish = done
    return h
  }, [])

  const dismiss = useCallback((velocity = 0) => {
    if (closing.current) return
    closing.current = true
    const sheet = sheetRef.current
    if (!sheet) { onClose?.(); return }
    if (prefersReducedMotion()) {
      stopAnims()
      const a = backdropRef.current?.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 150 })
      sheet.animate([{ opacity: 1 }, { opacity: 0 }], { duration: 150, fill: 'forwards' })
      if (a) a.onfinish = () => onClose?.(); else onClose?.()
      return
    }
    const y = liveY(sheet)
    const h = sheet.offsetHeight
    // Faster flick → shorter trip, but never jarringly brief or sluggish.
    const dur = Math.round(Math.min(340, Math.max(180, (h - y) / Math.max(velocity / 1000, 1.4))))
    play(y, h, dur, 0, () => onClose?.())
  }, [onClose, play])

  // Entrance: materialize from below.
  useLayoutEffect(() => {
    const sheet = sheetRef.current, back = backdropRef.current
    if (!sheet || !back) return
    if (prefersReducedMotion()) {
      anims.current = [
        back.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 150 }),
        sheet.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 150 }),
      ]
      return
    }
    const h = sheet.offsetHeight
    sheet.style.transform = 'translateY(0px)'
    back.style.opacity = '1'
    anims.current = [
      sheet.animate(
        [{ transform: `translateY(${h}px)`, opacity: 0.6 }, { transform: 'translateY(0px)', opacity: 1 }],
        { duration: 380, easing: EASE_OUT }),
      back.animate([{ opacity: 0 }, { opacity: 1 }], { duration: 260, easing: 'ease-out' }),
    ]
  }, [])

  // Esc closes; also lock page scroll while the sheet is open.
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') dismiss() }
    window.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      window.removeEventListener('keydown', onKey)
      document.body.style.overflow = prev
      stopAnims()
    }
  }, [dismiss])

  // ---- Drag to dismiss (header = grab area) ----
  const onPointerDown = (e) => {
    if (closing.current || e.button > 0) return
    if (e.target.closest('button, a, input, select, textarea')) return
    const sheet = sheetRef.current
    const start = liveY(sheet)          // respect where the sheet really is right now
    stopAnims()                          // grabbing interrupts any running animation
    sheet.style.transform = `translateY(${start}px)`
    e.currentTarget.setPointerCapture(e.pointerId)
    drag.current = { startY: e.clientY, startOffset: start, samples: [{ y: e.clientY, t: e.timeStamp }] }
  }

  const onPointerMove = (e) => {
    const d = drag.current
    if (!d) return
    const sheet = sheetRef.current
    const h = sheet.offsetHeight
    d.samples.push({ y: e.clientY, t: e.timeStamp })
    if (d.samples.length > 6) d.samples.shift()
    let y = d.startOffset + (e.clientY - d.startY)
    if (y < 0) y = -rubberband(-y, h) // pulling up past the top resists
    sheet.style.transform = `translateY(${y}px)`
    backdropRef.current.style.opacity = String(Math.max(0.15, 1 - Math.max(0, y) / h))
  }

  const onPointerUp = () => {
    const d = drag.current
    if (!d) return
    drag.current = null
    const sheet = sheetRef.current
    const h = sheet.offsetHeight
    const y = liveY(sheet)
    const first = d.samples[0], last = d.samples[d.samples.length - 1]
    const dt = Math.max(last.t - first.t, 1)
    const v = ((last.y - first.y) / dt) * 1000 // px/s, positive = downward
    // Decide from where the flick was *going*, not just where the finger let go.
    if (y + project(v) > h * 0.5) dismiss(Math.max(v, 0))
    else play(y, 0, 320, 1) // spring back from the live position
  }

  return (
    <div
      ref={backdropRef}
      className="sheet-backdrop"
      onClick={() => dismiss()}
    >
      <div
        ref={sheetRef}
        className="sheet"
        role="dialog"
        aria-modal="true"
        aria-label={title}
        onClick={e => e.stopPropagation()}  // don't close when clicking inside
      >
        <div
          className="sheet-grip"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
          onPointerCancel={onPointerUp}
        >
          <div className="sheet-handle" aria-hidden="true" />
          <div className="row" style={{ marginBottom: '0.75rem' }}>
            <h2 style={{ margin: 0 }}>{title}</h2>
            <span className="spacer" />
            <button className="secondary" onClick={() => dismiss()} aria-label="Close" style={{ minWidth: 44 }}>✕</button>
          </div>
        </div>
        {children}
      </div>
    </div>
  )
}

/**
 * In-app confirmation sheet — replaces the browser's window.confirm().
 *
 * Why: window.confirm() is a blocking browser popup. Some browsers and embedded
 * views (in-app browsers, previews, some installed-PWA contexts) suppress it and
 * it silently returns `false`, which made Finish / Discard workout look dead.
 * It also can't be styled. This sheet works everywhere and matches the app.
 *
 * Usage, from any async handler (no hook needed):
 *   if (!(await confirmAction({
 *     title: 'Discard workout?',
 *     message: 'All logged sets will be deleted.',
 *     confirmLabel: 'Discard',
 *     danger: true,
 *   }))) return
 *
 * <ConfirmHost /> is mounted once in App.jsx. If it isn't mounted (e.g. a unit
 * test rendering one page on its own), confirmAction falls back to
 * window.confirm so behaviour stays testable.
 */
import React, { useEffect, useState } from 'react'
import Modal from './Modal'

let showSheet = null   // set by the mounted <ConfirmHost>

export function confirmAction(opts) {
  const o = typeof opts === 'string' ? { message: opts } : opts
  if (!showSheet) {
    return Promise.resolve(window.confirm([o.title, o.message].filter(Boolean).join('\n\n')))
  }
  return new Promise(resolve => showSheet({ ...o, resolve }))
}

export function ConfirmHost() {
  const [req, setReq] = useState(null)

  useEffect(() => {
    showSheet = next => setReq(prev => {
      prev?.resolve(false)          // a second request cancels the first
      return next
    })
    return () => { showSheet = null }
  }, [])

  if (!req) return null
  const done = value => { req.resolve(value); setReq(null) }

  return (
    <Modal title={req.title || 'Are you sure?'} onClose={() => done(false)}>
      {req.message && <p className="muted" style={{ marginBottom: '1.1rem', lineHeight: 1.5 }}>{req.message}</p>}
      <div className="col" style={{ gap: '0.6rem' }}>
        <button
          type="button"
          className={req.danger ? 'danger confirm-danger' : undefined}
          onClick={() => done(true)}
          autoFocus
          style={{ width: '100%' }}
        >
          {req.confirmLabel || 'Confirm'}
        </button>
        <button type="button" className="secondary" onClick={() => done(false)} style={{ width: '100%' }}>
          {req.cancelLabel || 'Cancel'}
        </button>
      </div>
    </Modal>
  )
}

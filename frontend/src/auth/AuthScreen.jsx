/**
 * Shared pieces for the screens shown before the app proper: the full-screen
 * frame, the "Continue with Google" button, and the little "or" divider.
 */
import React, { useState } from 'react'
import { appRedirectUrl, supabase } from '../lib/supabase'

/** Full-screen frame for signed-out / not-yet-let-in screens. */
export default function AuthScreen({ title, subtitle, children }) {
  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 300, overflowY: 'auto',
      background: 'var(--color-bg)', padding: '2rem 1rem calc(2rem + env(safe-area-inset-bottom))',
    }}>
      <div style={{ maxWidth: 380, margin: '3rem auto 0' }}>
        {title && <h1 style={{ marginBottom: '0.25rem' }}>{title}</h1>}
        {subtitle && <p className="muted" style={{ marginBottom: '1.25rem' }}>{subtitle}</p>}
        {children}
      </div>
    </div>
  )
}

/**
 * Sends the browser to Google; Supabase brings it back to the app signed in
 * (src/lib/supabase.js picks the session up from the URL). `beforeRedirect` runs
 * first — Join uses it to remember the invite code across the round trip.
 */
export function GoogleButton({ label = 'Continue with Google', beforeRedirect, onError }) {
  const [busy, setBusy] = useState(false)

  async function go() {
    setBusy(true)
    beforeRedirect?.()
    const { error } = await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: appRedirectUrl() },
    })
    if (error) {
      setBusy(false)
      onError?.(error.message)
    }
    // On success the page is already navigating to Google.
  }

  return (
    <button type="button" className="secondary" onClick={go} disabled={busy} style={{ width: '100%' }}>
      {busy ? 'Opening Google…' : label}
    </button>
  )
}

export function OrDivider() {
  return (
    <div className="muted" style={{ textAlign: 'center', fontSize: '0.8rem', margin: '0.9rem 0' }}>
      or
    </div>
  )
}

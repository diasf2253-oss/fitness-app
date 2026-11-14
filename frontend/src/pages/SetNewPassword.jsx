/**
 * Choose a new password — shown after opening a password-reset link (from
 * "Forgot password?" on the login screen, or one the admin passed on). The
 * link has already signed you in; this sets the new password with Supabase
 * and then carries on into the app.
 */
import React, { useState } from 'react'
import { friendlyAuthError, useAuth } from '../auth'
import AuthScreen from '../components/AuthScreen'
import { ErrorBox } from '../components/States'
import { supabase } from '../supabase'

export default function SetNewPassword() {
  const { finishRecovery, logout } = useAuth()
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function submit(e) {
    e.preventDefault()
    setError(null)
    if (password !== confirm) return setError('Passwords do not match.')
    if (password.length < 8) return setError('Password must be at least 8 characters.')
    setBusy(true)
    const { error: err } = await supabase.auth.updateUser({ password })
    if (err) {
      setBusy(false)
      return setError(friendlyAuthError(err))
    }
    await finishRecovery()
  }

  return (
    <AuthScreen title="Set a new password" subtitle="Choose a new password to finish resetting it.">
      <form onSubmit={submit} className="col" style={{ gap: '0.9rem' }}>
        <ErrorBox error={error} />
        <div className="form-group">
          <label htmlFor="new-password">New password</label>
          <input id="new-password" type="password" autoComplete="new-password"
            value={password} onChange={e => setPassword(e.target.value)} required minLength={8} />
        </div>
        <div className="form-group">
          <label htmlFor="confirm-password">Confirm password</label>
          <input id="confirm-password" type="password" autoComplete="new-password"
            value={confirm} onChange={e => setConfirm(e.target.value)} required minLength={8} />
        </div>
        <button type="submit" disabled={busy || !password}>
          {busy ? 'Saving…' : 'Set password'}
        </button>
      </form>
      <p className="muted" style={{ marginTop: '1.25rem', fontSize: '0.85rem' }}>
        <button type="button" className="link-button" onClick={logout}>Cancel and log out</button>
      </p>
    </AuthScreen>
  )
}

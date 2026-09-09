/**
 * Forced password change — shown whenever the logged-in account has
 * must_change_password set (an admin-issued temp password). This is the
 * one route require_auth still allows through in that state (see
 * backend/app/auth.py's _PASSWORD_CHANGE_EXEMPT_PATHS).
 */
import React, { useState } from 'react'
import { apiFetch } from '../api'
import { useAuth } from '../auth'
import { ErrorBox } from '../components/States'

export default function ChangePassword() {
  const { refresh } = useAuth()
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function submit(e) {
    e.preventDefault()
    setError(null)
    if (password !== confirm) {
      setError('Passwords do not match.')
      return
    }
    if (password.length < 8) {
      setError('Password must be at least 8 characters.')
      return
    }
    setBusy(true)
    try {
      await apiFetch('/api/auth/change-password', {
        method: 'POST',
        body: JSON.stringify({ new_password: password }),
      })
      await refresh()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 300, overflowY: 'auto',
      background: 'var(--color-bg)', padding: '2rem 1rem calc(2rem + env(safe-area-inset-bottom))',
    }}>
      <div style={{ maxWidth: 380, margin: '3rem auto 0' }}>
        <h1 style={{ marginBottom: '0.25rem' }}>Set a new password</h1>
        <p className="muted" style={{ marginBottom: '1.25rem' }}>
          You're logging in with a temporary password — choose a new one to continue.
        </p>
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
      </div>
    </div>
  )
}

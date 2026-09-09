/**
 * Login screen — the first thing shown whenever the app is opened without
 * an active session. "Stay signed in" controls the login request's
 * `remember` flag: unchecked, the session cookie dies when the browser
 * closes; checked, it persists ~30 days (see backend/app/auth.py).
 */
import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../api'
import { useAuth } from '../auth'
import { ErrorBox } from '../components/States'

export default function Login() {
  const { refresh } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [remember, setRemember] = useState(true)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [pending, setPending] = useState(false)

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    setPending(false)
    try {
      await apiFetch('/api/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email: email.trim().toLowerCase(), password, remember }),
      })
      await refresh()
    } catch (err) {
      if (err.message === 'pending_approval') setPending(true)
      else setError(err.message === 'account_disabled'
        ? 'This account has been disabled.'
        : 'Incorrect email or password.')
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
        <h1 style={{ marginBottom: '0.25rem' }}>Log in</h1>
        <p className="muted" style={{ marginBottom: '1.25rem' }}>
          Welcome back.
        </p>

        {pending ? (
          <div className="card">
            <h2 style={{ marginTop: 0 }}>Waiting for approval</h2>
            <p className="muted">
              Your account is created but not approved yet. You'll be let in
              personally once it's ready — try again a bit later.
            </p>
          </div>
        ) : (
          <form onSubmit={submit} className="col" style={{ gap: '0.9rem' }}>
            <ErrorBox error={error} />
            <div className="form-group">
              <label htmlFor="login-email">Email</label>
              <input
                id="login-email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={e => setEmail(e.target.value)}
                required
              />
            </div>
            <div className="form-group">
              <label htmlFor="login-password">Password</label>
              <input
                id="login-password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={e => setPassword(e.target.value)}
                required
              />
            </div>
            <label className="row" style={{ alignItems: 'center', gap: '0.5rem', fontSize: '0.9rem' }}>
              <input
                type="checkbox"
                checked={remember}
                onChange={e => setRemember(e.target.checked)}
                style={{ width: 'auto' }}
              />
              Stay signed in
            </label>
            <button type="submit" disabled={busy || !email || !password}>
              {busy ? 'Logging in…' : 'Log in'}
            </button>
          </form>
        )}

        <p className="muted" style={{ marginTop: '1.25rem', fontSize: '0.85rem' }}>
          Have an invite link? <Link to="/join">Create an account</Link>
        </p>
      </div>
    </div>
  )
}

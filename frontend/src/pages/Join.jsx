/**
 * Signup — reads the invite code from ?code= in the URL. Without a valid
 * code the backend rejects account creation outright (see
 * backend/app/routers/auth.py's /join), so this screen also fails closed:
 * no app-revealing content, just a generic message.
 */
import React, { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { apiFetch } from '../api'
import { ErrorBox } from '../components/States'

export default function Join() {
  const [params] = useSearchParams()
  const code = params.get('code') || ''

  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(false)

  const wrap = (children) => (
    <div style={{
      position: 'fixed', inset: 0, zIndex: 300, overflowY: 'auto',
      background: 'var(--color-bg)', padding: '2rem 1rem calc(2rem + env(safe-area-inset-bottom))',
    }}>
      <div style={{ maxWidth: 380, margin: '3rem auto 0' }}>{children}</div>
    </div>
  )

  if (!code) {
    return wrap(
      <div className="card">
        <p className="muted">This link is invalid or missing an invite code.</p>
      </div>
    )
  }

  if (done) {
    return wrap(
      <div className="card">
        <h2 style={{ marginTop: 0 }}>Waiting for approval</h2>
        <p className="muted">
          Your account is created. You'll be let in personally once it's
          approved — check back soon, or just try logging in later.
        </p>
        <Link to="/login"><button className="secondary" style={{ width: '100%', marginTop: '0.75rem' }}>Go to login</button></Link>
      </div>
    )
  }

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
      await apiFetch('/api/auth/join', {
        method: 'POST',
        body: JSON.stringify({ code, name: name.trim(), email: email.trim().toLowerCase(), password }),
      })
      setDone(true)
    } catch (err) {
      setError(err.message === 'An account with that email already exists'
        ? err.message
        : 'This invite link is no longer valid.')
    } finally {
      setBusy(false)
    }
  }

  return wrap(
    <>
      <h1 style={{ marginBottom: '0.25rem' }}>Create your account</h1>
      <p className="muted" style={{ marginBottom: '1.25rem' }}>You've been invited.</p>

      <form onSubmit={submit} className="col" style={{ gap: '0.9rem' }}>
        <ErrorBox error={error} />
        <div className="form-group">
          <label htmlFor="join-name">Name</label>
          <input id="join-name" value={name} onChange={e => setName(e.target.value)} required />
        </div>
        <div className="form-group">
          <label htmlFor="join-email">Email</label>
          <input id="join-email" type="email" autoComplete="email"
            value={email} onChange={e => setEmail(e.target.value)} required />
        </div>
        <div className="form-group">
          <label htmlFor="join-password">Password</label>
          <input id="join-password" type="password" autoComplete="new-password"
            value={password} onChange={e => setPassword(e.target.value)} required minLength={8} />
        </div>
        <div className="form-group">
          <label htmlFor="join-confirm">Confirm password</label>
          <input id="join-confirm" type="password" autoComplete="new-password"
            value={confirm} onChange={e => setConfirm(e.target.value)} required minLength={8} />
        </div>
        <button type="submit" disabled={busy || !name || !email || !password}>
          {busy ? 'Creating account…' : 'Create account'}
        </button>
      </form>

      <p className="muted" style={{ marginTop: '1.25rem', fontSize: '0.85rem' }}>
        Already have an account? <Link to="/login">Log in</Link>
      </p>
    </>
  )
}

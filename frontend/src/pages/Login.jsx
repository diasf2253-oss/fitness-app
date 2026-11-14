/**
 * Sign-in screen — shown whenever nobody is signed in. Signing in happens
 * against Supabase (email + password, or Google); once it succeeds,
 * src/auth.jsx hears about it and asks the backend who you are. "Forgot
 * password?" has Supabase email a reset link that brings you back to the
 * app's SetNewPassword screen.
 */
import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { friendlyAuthError } from '../auth'
import AuthScreen, { GoogleButton, OrDivider } from '../components/AuthScreen'
import { ErrorBox } from '../components/States'
import { appRedirectUrl, landing, supabase } from '../supabase'

export default function Login() {
  const [mode, setMode] = useState('signin')   // 'signin' | 'forgot'
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(landing.error)
  const [resetSent, setResetSent] = useState(false)

  async function signIn(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    const { error: err } = await supabase.auth.signInWithPassword({
      email: email.trim().toLowerCase(),
      password,
    })
    setBusy(false)
    if (err) setError(friendlyAuthError(err))
    // On success AuthProvider hears SIGNED_IN and takes it from there.
  }

  async function sendReset(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    const { error: err } = await supabase.auth.resetPasswordForEmail(email.trim().toLowerCase(), {
      redirectTo: appRedirectUrl(),
    })
    setBusy(false)
    if (err) setError(friendlyAuthError(err))
    else setResetSent(true)
  }

  if (mode === 'forgot') {
    return (
      <AuthScreen title="Reset your password" subtitle="We'll email you a link to set a new one.">
        {resetSent ? (
          <div className="card">
            <p className="muted" style={{ margin: 0 }}>
              If there's an account for <strong>{email.trim()}</strong>, a reset link is on
              its way. Open it on this device to choose a new password.
            </p>
          </div>
        ) : (
          <form onSubmit={sendReset} className="col" style={{ gap: '0.9rem' }}>
            <ErrorBox error={error} />
            <div className="form-group">
              <label htmlFor="reset-email">Email</label>
              <input id="reset-email" type="email" autoComplete="email"
                value={email} onChange={e => setEmail(e.target.value)} required />
            </div>
            <button type="submit" disabled={busy || !email}>
              {busy ? 'Sending…' : 'Send reset link'}
            </button>
          </form>
        )}
        <p className="muted" style={{ marginTop: '1.25rem', fontSize: '0.85rem' }}>
          <button type="button" className="link-button"
            onClick={() => { setMode('signin'); setError(null); setResetSent(false) }}>
            Back to sign in
          </button>
        </p>
      </AuthScreen>
    )
  }

  return (
    <AuthScreen title="Log in" subtitle="Welcome back.">
      <ErrorBox error={error} />
      <GoogleButton onError={setError} />
      <OrDivider />
      <form onSubmit={signIn} className="col" style={{ gap: '0.9rem' }}>
        <div className="form-group">
          <label htmlFor="login-email">Email</label>
          <input id="login-email" type="email" autoComplete="email"
            value={email} onChange={e => setEmail(e.target.value)} required />
        </div>
        <div className="form-group">
          <label htmlFor="login-password">Password</label>
          <input id="login-password" type="password" autoComplete="current-password"
            value={password} onChange={e => setPassword(e.target.value)} required />
        </div>
        <button type="submit" disabled={busy || !email || !password}>
          {busy ? 'Logging in…' : 'Log in'}
        </button>
      </form>

      <p className="muted" style={{ marginTop: '1rem', fontSize: '0.85rem' }}>
        <button type="button" className="link-button" onClick={() => { setMode('forgot'); setError(null) }}>
          Forgot password?
        </button>
      </p>
      <p className="muted" style={{ marginTop: '0.5rem', fontSize: '0.85rem' }}>
        New here, or have an invite? <Link to="/join">Create an account</Link>
      </p>
      <p className="muted" style={{ marginTop: '1.25rem', fontSize: '0.78rem' }}>
        Used the app before the login update? Create your account again with the
        same email — or use Continue with Google — and all your data comes with you.
      </p>
    </AuthScreen>
  )
}

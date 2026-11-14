/**
 * Create an account — step 1 of 2. This creates the *login* (at Supabase:
 * email + password, or Google). Step 2, FinishJoin, redeems the invite code
 * with the app's backend, which is what actually creates the account
 * (pending until an admin approves it).
 *
 * The invite code and name typed here are remembered on the device, so they
 * survive the "confirm your email" or Google round trip and FinishJoin can
 * prefill them. Someone who had an account before the login update skips the
 * code: signing in with the same email reconnects their existing account.
 */
import React, { useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { friendlyAuthError, stashPendingJoin } from '../auth'
import AuthScreen, { GoogleButton, OrDivider } from '../components/AuthScreen'
import { ErrorBox } from '../components/States'
import { appRedirectUrl, supabase } from '../supabase'

export default function Join() {
  const [params] = useSearchParams()
  const [code, setCode] = useState(params.get('code') || '')
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [checkEmail, setCheckEmail] = useState(false)

  const remember = () => stashPendingJoin({ code: code.trim(), name: name.trim() })

  async function submit(e) {
    e.preventDefault()
    setError(null)
    if (password !== confirm) return setError('Passwords do not match.')
    if (password.length < 8) return setError('Password must be at least 8 characters.')
    setBusy(true)
    remember()
    const { data, error: err } = await supabase.auth.signUp({
      email: email.trim().toLowerCase(),
      password,
      options: { emailRedirectTo: appRedirectUrl(), data: { name: name.trim() } },
    })
    setBusy(false)
    if (err) return setError(friendlyAuthError(err))
    // No session means Supabase wants the email confirmed first. With one,
    // AuthProvider hears SIGNED_IN and moves on to FinishJoin.
    if (!data?.session) setCheckEmail(true)
  }

  if (checkEmail) {
    return (
      <AuthScreen title="Check your email">
        <div className="card">
          <p className="muted" style={{ marginTop: 0 }}>
            We sent a confirmation link to <strong>{email.trim()}</strong>. Open it on this
            device — it brings you back here, signed in, for the last step.
          </p>
          <p className="muted" style={{ marginBottom: 0, fontSize: '0.85rem' }}>
            Nothing after a few minutes? Check spam, or <Link to="/login">try logging in</Link>.
          </p>
        </div>
      </AuthScreen>
    )
  }

  return (
    <AuthScreen title="Create your account" subtitle="Step 1 of 2 — your login.">
      <ErrorBox error={error} />
      <form onSubmit={submit} className="col" style={{ gap: '0.9rem' }}>
        <div className="form-group">
          <label htmlFor="join-code">Invite code</label>
          <input id="join-code" autoCapitalize="none" autoCorrect="off" spellCheck={false}
            value={code} onChange={e => setCode(e.target.value)}
            placeholder="Skip if you had an account before" />
        </div>
        <div className="form-group">
          <label htmlFor="join-name">Name</label>
          <input id="join-name" autoComplete="name" autoCapitalize="words"
            value={name} onChange={e => setName(e.target.value)} required />
        </div>

        <GoogleButton label="Sign up with Google" beforeRedirect={remember} onError={setError} />
        <OrDivider />

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
    </AuthScreen>
  )
}

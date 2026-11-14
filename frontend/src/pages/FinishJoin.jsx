/**
 * Create an account — step 2 of 2. Shown when someone is signed in with
 * Supabase but has no account in the app yet (GET /api/auth/me answered 403
 * "no_account"). Redeeming an invite code here (POST /api/auth/join) creates
 * the account, pending until an admin approves it. The code is checked by
 * the backend, never just here.
 */
import React, { useState } from 'react'
import { apiFetch } from '../lib/api'
import { clearPendingJoin, readPendingJoin, useAuth } from '../auth/auth'
import AuthScreen from '../auth/AuthScreen'
import { ErrorBox } from '../components/ui/States'

function codeFromUrl() {
  try { return new URLSearchParams(window.location.search).get('code') || '' } catch { return '' }
}

export default function FinishJoin() {
  const { session, refresh, logout } = useAuth()
  const stash = readPendingJoin()
  const meta = session?.user?.user_metadata || {}
  const [name, setName] = useState(stash?.name || meta.name || meta.full_name || '')
  const [code, setCode] = useState(stash?.code || codeFromUrl())
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function submit(e) {
    e.preventDefault()
    setBusy(true)
    setError(null)
    try {
      await apiFetch('/api/auth/join', {
        method: 'POST',
        body: JSON.stringify({ code: code.trim(), name: name.trim() }),
      })
      clearPendingJoin()
      await refresh()   // → "waiting for approval" (or straight in, for a reconnected account)
    } catch (err) {
      setError(err.message === 'Invalid or expired invite code'
        ? "That invite code isn't valid, or it's been used up."
        : err.message)
      setBusy(false)
    }
  }

  return (
    <AuthScreen title="One last step" subtitle="Step 2 of 2 — your invite.">
      <p className="muted" style={{ marginTop: 0, fontSize: '0.9rem' }}>
        You're signed in as <strong>{session?.user?.email || 'your new login'}</strong>. Enter
        the invite code you were given to join.
      </p>
      <form onSubmit={submit} className="col" style={{ gap: '0.9rem' }}>
        <ErrorBox error={error} />
        <div className="form-group">
          <label htmlFor="finish-name">Name</label>
          <input id="finish-name" autoComplete="name" autoCapitalize="words"
            value={name} onChange={e => setName(e.target.value)} required maxLength={200} />
        </div>
        <div className="form-group">
          <label htmlFor="finish-code">Invite code</label>
          <input id="finish-code" autoCapitalize="none" autoCorrect="off" spellCheck={false}
            value={code} onChange={e => setCode(e.target.value)} required maxLength={64} />
        </div>
        <button type="submit" disabled={busy || !name.trim() || !code.trim()}>
          {busy ? 'Joining…' : 'Join'}
        </button>
      </form>
      <p className="muted" style={{ marginTop: '1.25rem', fontSize: '0.85rem' }}>
        Wrong account? <button type="button" className="link-button" onClick={logout}>Log out</button>
      </p>
    </AuthScreen>
  )
}

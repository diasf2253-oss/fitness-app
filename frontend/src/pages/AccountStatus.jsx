/**
 * The "you're signed in, but not in the app (yet)" screens: waiting for
 * approval, account disabled, server unreachable, and a build with no
 * Supabase settings. Which one is picked by src/auth/auth.jsx's `status`.
 */
import React, { useState } from 'react'
import { useAuth } from '../auth/auth'
import AuthScreen from '../auth/AuthScreen'

const COPY = {
  pending: {
    title: 'Waiting for approval',
    body: "You're in the queue. You'll be let in personally once your account is approved — check back a bit later.",
    retry: 'Check again',
  },
  disabled: {
    title: 'Account disabled',
    body: 'This account has been switched off. If that seems wrong, ask whoever invited you.',
  },
  unreachable: {
    title: "Can't reach the server",
    body: "You're signed in, but the app's server didn't answer. Check your connection and try again.",
    retry: 'Try again',
  },
  server_error: {
    title: 'Something went wrong on our side',
    body: "You're signed in, but the app's server hit an error. It's not your connection — try again in a moment, and if it keeps happening, tell whoever invited you.",
    retry: 'Try again',
  },
  unconfigured: {
    title: "Login isn't set up",
    body: 'This build has no Supabase settings (VITE_SUPABASE_URL and VITE_SUPABASE_PUBLISHABLE_KEY). See notes/runbooks/SUPABASE.md.',
  },
}

export default function AccountStatus({ kind }) {
  const { refresh, logout } = useAuth()
  const [busy, setBusy] = useState(false)
  const copy = COPY[kind] || COPY.unreachable

  async function retry() {
    setBusy(true)
    await refresh()
    setBusy(false)
  }

  return (
    <AuthScreen title={copy.title}>
      <div className="card">
        <p className="muted" style={{ marginTop: 0 }}>{copy.body}</p>
        {copy.retry && (
          <button style={{ width: '100%' }} onClick={retry} disabled={busy}>
            {busy ? 'Checking…' : copy.retry}
          </button>
        )}
        {kind !== 'unconfigured' && (
          <button className="secondary" style={{ width: '100%', marginTop: '0.6rem' }} onClick={logout}>
            Log out
          </button>
        )}
      </div>
    </AuthScreen>
  )
}

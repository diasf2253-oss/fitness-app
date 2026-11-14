/**
 * Auth state — two questions, answered in order:
 *
 *   1. Is someone signed in with Supabase? supabase-js keeps the session on
 *      this device and renews it (see src/lib/supabase.js).
 *   2. What does this app's backend say about them? GET /api/auth/me returns
 *      the account and its status — or 403 "no_account" (signed in, but no
 *      invite code redeemed yet), or 401 (the token is no good).
 *
 * `status` picks the screen App.jsx shows:
 *   'loading'      still working it out — render nothing
 *   'signed_out'   Login / Join
 *   'needs_invite' FinishJoin — enter an invite code
 *   'pending'      waiting for an admin to approve
 *   'disabled'     the account has been switched off
 *   'recovery'     arrived from a password-reset link — SetNewPassword
 *   'unreachable'  signed in, but the server can't be reached and there's no
 *                  saved copy of the account on this device to fall back on
 *   'server_error' same, but the server answered with an error (5xx) — a
 *                  problem on our side, not the person's connection
 *   'unconfigured' this build has no Supabase settings
 *   'ready'        the app
 *
 * Offline: the last good /me answer is saved on the device (minus the ingest
 * token), so the installed phone app still opens straight into the app —
 * whose data lives on the phone anyway — when there's no network.
 */
import React, { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import { apiFetch } from '../lib/api'
import { landing, supabase } from '../lib/supabase'

const AuthContext = createContext(null)

const NO_AUTOLOGIN_KEY = 'dev_no_autologin'
const CACHED_ACCOUNT_KEY = 'auth_me_v1'
const PENDING_JOIN_KEY = 'pending_join_v1'

/* ------------------------------------------------------------------ */
/* Small pure helpers (exported for tests)                             */
/* ------------------------------------------------------------------ */

export function statusFromAccount(me) {
  if (me?.status === 'active') return 'ready'
  if (me?.status === 'pending') return 'pending'
  return 'disabled'
}

/** The saved /me answer — only if it belongs to `uid` when one is given. */
export function readCachedAccount(uid) {
  try {
    const saved = JSON.parse(localStorage.getItem(CACHED_ACCOUNT_KEY) || 'null')
    if (!saved?.me) return null
    if (uid && saved.uid !== uid) return null
    return saved.me
  } catch {
    return null
  }
}

export function saveCachedAccount(me, uid) {
  try {
    // The ingest token is a long-lived credential: never park it in storage.
    const { ingest_token: _omit, ...safe } = me || {}
    localStorage.setItem(CACHED_ACCOUNT_KEY, JSON.stringify({ uid: uid || null, me: safe }))
  } catch { /* private mode / full storage — the cache is optional */ }
}

export function clearCachedAccount() {
  try { localStorage.removeItem(CACHED_ACCOUNT_KEY) } catch { /* ignore */ }
}

/** Invite code + name typed on the Join screen, kept across the email
 *  confirmation (or Google) round trip so FinishJoin can prefill them. */
export function stashPendingJoin({ code, name }) {
  try { localStorage.setItem(PENDING_JOIN_KEY, JSON.stringify({ code: code || '', name: name || '' })) } catch { /* optional */ }
}

export function readPendingJoin() {
  try { return JSON.parse(localStorage.getItem(PENDING_JOIN_KEY) || 'null') } catch { return null }
}

export function clearPendingJoin() {
  try { localStorage.removeItem(PENDING_JOIN_KEY) } catch { /* ignore */ }
}

/** Supabase's sign-in errors, in plain words. */
export function friendlyAuthError(error) {
  const code = error?.code || ''
  if (code === 'invalid_credentials') return 'Incorrect email or password.'
  if (code === 'email_not_confirmed') {
    return 'Confirm your email first — open the link we sent you, then sign in.'
  }
  if (code === 'weak_password') return 'Pick a stronger password (8+ characters).'
  if (code.startsWith('over_') || error?.status === 429) {
    return 'Too many attempts — wait a minute and try again.'
  }
  // supabase-js reports "no network / host unreachable" as a retryable fetch error.
  if (error?.name === 'AuthRetryableFetchError' || error?.message === 'Failed to fetch') {
    return "Couldn't reach the login service — check your connection and try again."
  }
  return error?.message || 'Something went wrong — try again.'
}

function devAutoLoginAllowed() {
  if (!import.meta.env.DEV) return false
  if (!import.meta.env.VITE_DEV_AUTOLOGIN_EMAIL || !import.meta.env.VITE_DEV_AUTOLOGIN_PASSWORD) return false
  try { return !sessionStorage.getItem(NO_AUTOLOGIN_KEY) } catch { return true }
}

/* ------------------------------------------------------------------ */
/* Provider                                                            */
/* ------------------------------------------------------------------ */

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [status, setStatus] = useState(supabase ? 'loading' : 'unconfigured')
  const [session, setSession] = useState(null)
  const recovering = useRef(landing.recovery)   // came in through a reset link
  const autoLoginTried = useRef(false)
  const latest = useRef(0)                      // ignore answers from superseded refreshes

  const refresh = useCallback(async () => {
    if (!supabase) { setStatus('unconfigured'); return null }
    const run = ++latest.current
    const show = (nextStatus, nextUser = null) => {
      if (run !== latest.current) return
      setUser(nextUser)
      setStatus(nextStatus)
    }

    let current = null
    let sessionError = null
    try {
      const { data, error } = await supabase.auth.getSession()
      current = data?.session ?? null
      sessionError = error ?? null
    } catch (err) {
      sessionError = err
    }
    if (run === latest.current) setSession(current)

    if (!current) {
      // A renewal that failed for lack of network leaves the session saved
      // but unusable for now: keep the person in on their saved account.
      const cached = sessionError ? readCachedAccount() : null
      if (cached) { show(statusFromAccount(cached), cached); return cached }

      if (devAutoLoginAllowed() && !autoLoginTried.current) {
        // Dev-only shortcut past the login screen while designing the UI.
        // import.meta.env.DEV is false in every production build, so this
        // whole branch is stripped from what ships. The SIGNED_IN event that
        // follows runs refresh() again. Details: notes/runbooks/DEV_HANDBOOK.md.
        autoLoginTried.current = true
        const { error } = await supabase.auth.signInWithPassword({
          email: import.meta.env.VITE_DEV_AUTOLOGIN_EMAIL,
          password: import.meta.env.VITE_DEV_AUTOLOGIN_PASSWORD,
        })
        if (!error) return null
      }
      clearCachedAccount()
      show('signed_out')
      return null
    }

    if (recovering.current) { show('recovery'); return null }

    try {
      const me = await apiFetch('/api/auth/me')
      saveCachedAccount(me, current.user?.id)
      show(statusFromAccount(me), me)
      return me
    } catch (err) {
      if (err.status === 403 && err.message === 'no_account') { show('needs_invite'); return null }
      if (err.status === 401) {
        // Supabase says signed in, the backend disagrees (revoked, or a token
        // from another project): start over.
        clearCachedAccount()
        try { await supabase.auth.signOut({ scope: 'local' }) } catch { /* already gone */ }
        show('signed_out')
        return null
      }
      // Network / server trouble: carry on with this person's saved account.
      const cached = readCachedAccount(current.user?.id)
      if (cached) { show(statusFromAccount(cached), cached); return cached }
      // An HTTP status means the server *did* answer — with an error on its
      // side (e.g. a missed database migration). Don't send people off to
      // check their Wi-Fi for that.
      show(err.status >= 500 ? 'server_error' : 'unreachable')
      return null
    }
  }, [])

  useEffect(() => {
    refresh()
    if (!supabase) return undefined
    const { data } = supabase.auth.onAuthStateChange((event) => {
      if (event === 'PASSWORD_RECOVERY') {
        recovering.current = true
        setStatus('recovery')
        return
      }
      if (event === 'SIGNED_IN' || event === 'SIGNED_OUT') {
        // Run outside this callback: supabase-js holds a lock while it
        // notifies, and awaiting its own methods in here can deadlock.
        setTimeout(() => { refresh() }, 0)
      }
    })
    return () => data.subscription.unsubscribe()
  }, [refresh])

  /** Password set after a reset link — carry on into the app. */
  const finishRecovery = useCallback(() => {
    recovering.current = false
    return refresh()
  }, [refresh])

  const logout = useCallback(async () => {
    // After an explicit log-out, don't auto-sign-in again this browser session.
    try { sessionStorage.setItem(NO_AUTOLOGIN_KEY, '1') } catch { /* private mode */ }
    clearCachedAccount()
    recovering.current = false
    latest.current++   // anything still in flight is now stale
    try {
      // 'local' = just this device, like the old per-device log-out
      // (supabase-js would otherwise sign out every device by default).
      await supabase?.auth.signOut({ scope: 'local' })
    } catch {
      // Even if the request fails, treat the session here as gone.
    }
    setSession(null)
    setUser(null)
    setStatus('signed_out')
  }, [])

  return (
    <AuthContext.Provider value={{ user, status, session, refresh, logout, finishRecovery }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

/**
 * Auth state (Phase 1-2 friends beta) — who's logged in, via the session
 * cookie set by POST /api/auth/login. A 401 from GET /api/auth/me is the
 * normal logged-out state, not an error.
 */
import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { apiFetch } from './api'

const AuthContext = createContext(null)

const NO_AUTOLOGIN_KEY = 'dev_no_autologin'

function devAutoLoginAllowed() {
  if (!import.meta.env.DEV) return false
  if (!import.meta.env.VITE_DEV_AUTOLOGIN_EMAIL || !import.meta.env.VITE_DEV_AUTOLOGIN_PASSWORD) return false
  try { return !sessionStorage.getItem(NO_AUTOLOGIN_KEY) } catch { return true }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  // 'loading' | 'authed' | 'anon'
  const [status, setStatus] = useState('loading')

  const refresh = useCallback(async () => {
    try {
      let me
      try {
        me = await apiFetch('/api/auth/me')
      } catch (err) {
        // Dev-only shortcut: skip the login screen while the UI is being designed.
        // `import.meta.env.DEV` is false in every production build, so this whole
        // branch is stripped out of what ships. Logging out sets a flag so you can
        // still reach /login on purpose. Details: docs/DEV_HANDBOOK.md.
        if (!devAutoLoginAllowed()) throw err
        await apiFetch('/api/auth/login', {
          method: 'POST',
          body: JSON.stringify({
            email: import.meta.env.VITE_DEV_AUTOLOGIN_EMAIL,
            password: import.meta.env.VITE_DEV_AUTOLOGIN_PASSWORD,
            remember: true,
          }),
        })
        me = await apiFetch('/api/auth/me')
      }
      setUser(me)
      setStatus('authed')
      return me
    } catch {
      setUser(null)
      setStatus('anon')
      return null
    }
  }, [])

  useEffect(() => { refresh() }, [refresh])

  const logout = useCallback(async () => {
    try {
      await apiFetch('/api/auth/logout', { method: 'POST' })
    } catch {
      // Even if the request fails, treat the local session as gone.
    }
    // After an explicit log-out, don't auto-sign-in again this browser session.
    try { sessionStorage.setItem(NO_AUTOLOGIN_KEY, '1') } catch { /* private mode */ }
    setUser(null)
    setStatus('anon')
  }, [])

  return (
    <AuthContext.Provider value={{ user, status, refresh, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}

/**
 * Auth state (Phase 1-2 friends beta) — who's logged in, via the session
 * cookie set by POST /api/auth/login. A 401 from GET /api/auth/me is the
 * normal logged-out state, not an error.
 */
import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { apiFetch } from './api'

const AuthContext = createContext(null)

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  // 'loading' | 'authed' | 'anon'
  const [status, setStatus] = useState('loading')

  const refresh = useCallback(async () => {
    try {
      const me = await apiFetch('/api/auth/me')
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

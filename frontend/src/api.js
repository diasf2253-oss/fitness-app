/**
 * Fetch wrapper that automatically attaches the bearer token from
 * localStorage (key: "app_token") to every request.
 *
 * Usage:
 *   import { apiFetch } from './api'
 *   const data = await apiFetch('/api/exercises')
 *   const created = await apiFetch('/api/exercises', { method: 'POST', body: JSON.stringify({...}) })
 */

// The token is stored in localStorage so it survives page reloads.
// The user sets it once on the Settings page (or we default to 'changeme' for dev).
function getToken() {
  return localStorage.getItem('app_token') || 'changeme'
}

export function setToken(token) {
  localStorage.setItem('app_token', token)
}

/**
 * Core fetch wrapper.
 * - Adds Authorization header automatically
 * - Sets Content-Type: application/json when a body is provided
 * - Throws an Error with the response detail on non-2xx responses
 */
export async function apiFetch(path, options = {}) {
  const headers = {
    'Authorization': `Bearer ${getToken()}`,
    ...(options.body ? { 'Content-Type': 'application/json' } : {}),
    ...(options.headers || {}),
  }

  const response = await fetch(path, { ...options, headers })

  if (!response.ok) {
    // Try to parse a FastAPI {"detail": "..."} error body
    let detail = `HTTP ${response.status}`
    try {
      const err = await response.json()
      detail = err.detail || JSON.stringify(err)
    } catch (_) {
      // ignore JSON parse errors on error responses
    }
    throw new Error(detail)
  }

  // 204 No Content — return null instead of trying to parse empty body
  if (response.status === 204) return null

  return response.json()
}

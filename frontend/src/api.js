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
import { dispatchLocal } from './local/api'
import { isLocalFirst } from './local/mode'

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
 *
 * Local-first mode: requests are offered to the on-device API first
 * (IndexedDB-backed twin of the backend). Matched routes never touch the
 * network; unmatched ones (Coach, ingest, sync, dev) fall through to it.
 */
export async function apiFetch(path, options = {}) {
  if (isLocalFirst()) {
    const { handled, result } = await dispatchLocal(path, options)
    if (handled) return result
  }
  return networkFetch(path, options)
}

async function networkFetch(path, options = {}) {
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

/**
 * Multipart upload variant (file uploads). Same auth handling, but no
 * Content-Type header — the browser must set the multipart boundary.
 */
export async function apiUpload(path, formData) {
  const response = await fetch(path, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${getToken()}` },
    body: formData,
  })

  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      const err = await response.json()
      detail = err.detail || JSON.stringify(err)
    } catch (_) {
      // ignore JSON parse errors on error responses
    }
    throw new Error(detail)
  }

  return response.json()
}

/**
 * Streaming POST — the backend replies with a text/plain stream (the AI
 * Coach chat). Calls onChunk(text) for each chunk as it arrives.
 * Returns the full concatenated text when the stream ends.
 */
export async function apiStream(path, body, onChunk) {
  const response = await fetch(path, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${getToken()}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(body),
  })

  if (!response.ok) {
    let detail = `HTTP ${response.status}`
    try {
      const err = await response.json()
      detail = err.detail || JSON.stringify(err)
    } catch (_) {
      // ignore JSON parse errors on error responses
    }
    throw new Error(detail)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let full = ''
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    const text = decoder.decode(value, { stream: true })
    full += text
    onChunk(text)
  }
  return full
}

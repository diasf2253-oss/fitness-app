/**
 * Fetch wrapper for the multi-user friends beta — auth is a same-origin
 * httpOnly session cookie (see src/auth.js), never a bearer token, so every
 * request just needs `credentials: 'include'` and the browser does the rest.
 *
 * Usage:
 *   import { apiFetch } from './api'
 *   const data = await apiFetch('/api/exercises')
 *   const created = await apiFetch('/api/exercises', { method: 'POST', body: JSON.stringify({...}) })
 */
import { dispatchLocal } from './local/api'
import { isLocalFirst } from './local/mode'
import { apiUrl } from './env'

/**
 * Core fetch wrapper.
 * - Sends the session cookie automatically (credentials: 'include')
 * - Sets Content-Type: application/json when a body is provided
 * - Throws an Error with the response detail on non-2xx responses
 *
 * Local-first mode: requests are offered to the on-device API first
 * (IndexedDB-backed twin of the backend). Matched routes never touch the
 * network; unmatched ones (Coach, ingest, sync, dev, auth, admin) fall
 * through to it.
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
    ...(options.body ? { 'Content-Type': 'application/json' } : {}),
    ...(options.headers || {}),
  }

  const response = await fetch(apiUrl(path), { ...options, headers, credentials: 'include' })

  if (!response.ok) {
    // Try to parse a FastAPI {"detail": "..."} error body
    let detail = `HTTP ${response.status}`
    try {
      const err = await response.json()
      detail = err.detail || JSON.stringify(err)
    } catch (_) {
      // ignore JSON parse errors on error responses
    }
    const error = new Error(detail)
    error.status = response.status
    throw error
  }

  // 204 No Content — return null instead of trying to parse empty body
  if (response.status === 204) return null

  return response.json()
}

/**
 * Multipart upload variant (file uploads). Same cookie auth, but no
 * Content-Type header — the browser must set the multipart boundary.
 */
export async function apiUpload(path, formData) {
  const response = await fetch(apiUrl(path), {
    method: 'POST',
    credentials: 'include',
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
  const response = await fetch(apiUrl(path), {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
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

/**
 * Fetch wrapper. Auth is a Supabase access token sent as
 * `Authorization: Bearer <token>` on every network request (see
 * src/lib/supabase.js) — no cookies involved, so it works the same whether the
 * API is on this origin or another one.
 *
 * Usage:
 *   import { apiFetch } from './api'
 *   const data = await apiFetch('/api/exercises')
 *   const created = await apiFetch('/api/exercises', { method: 'POST', body: JSON.stringify({...}) })
 */
import { dispatchLocal } from '../local/api'
import { isLocalFirst } from '../local/mode'
import { apiUrl } from './env'
import { getAccessToken } from './supabase'

/** The signed-in user's bearer header, or {} when signed out. */
async function authHeaders() {
  const token = await getAccessToken()
  return token ? { Authorization: `Bearer ${token}` } : {}
}

async function errorFrom(response) {
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
  return error
}

/**
 * Core fetch wrapper.
 * - Sends the Supabase access token when someone is signed in
 * - Sets Content-Type: application/json when a body is provided
 * - Throws an Error (with .status) carrying the response detail on non-2xx
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
    ...(await authHeaders()),
    ...(options.headers || {}),
  }

  const response = await fetch(apiUrl(path), { ...options, headers })
  if (!response.ok) throw await errorFrom(response)

  // 204 No Content — return null instead of trying to parse empty body
  if (response.status === 204) return null

  return response.json()
}

/**
 * Multipart upload variant (file uploads). No Content-Type header — the
 * browser must set the multipart boundary.
 *
 * Its one caller (the export.zip history backfill) hits an ingest endpoint,
 * and every ingest endpoint authenticates via the per-user `ingest_token`
 * bearer (require_ingest_auth), not the Supabase token — pass
 * { Authorization: `Bearer ${ingestToken}` } as `extraHeaders`; it takes
 * precedence over the signed-in user's token.
 */
export async function apiUpload(path, formData, extraHeaders = {}) {
  const response = await fetch(apiUrl(path), {
    method: 'POST',
    headers: { ...(await authHeaders()), ...extraHeaders },
    body: formData,
  })
  if (!response.ok) throw await errorFrom(response)
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
    headers: { 'Content-Type': 'application/json', ...(await authHeaders()) },
    body: JSON.stringify(body),
  })
  if (!response.ok) throw await errorFrom(response)

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

/**
 * The fetch wrappers' auth headers. Since the switch to Supabase Auth every
 * request carries the signed-in user's access token as a bearer header — no
 * cookies. Ingest uploads pass their own bearer (the per-user ingest token,
 * which require_ingest_auth expects), and that one must win: the export.zip
 * backfill once 401'd on every attempt because its header never got sent.
 */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

let accessToken = null
vi.mock('./supabase', () => ({ getAccessToken: async () => accessToken }))
vi.mock('./local/mode', () => ({ isLocalFirst: () => false }))

import { apiFetch, apiUpload } from './api'

beforeEach(() => { accessToken = null })
afterEach(() => vi.unstubAllGlobals())

function stubFetch(status = 200, body = { status: 'ok' }) {
  const calls = []
  vi.stubGlobal('fetch', (url, opts) => {
    calls.push({ url, opts })
    return Promise.resolve({
      ok: status < 300,
      status,
      json: () => Promise.resolve(body),
    })
  })
  return calls
}

describe('apiFetch', () => {
  it('sends the Supabase access token when signed in, and no cookies', async () => {
    accessToken = 'supabase-token'
    const calls = stubFetch()
    await apiFetch('/api/settings')

    expect(calls[0].opts.headers.Authorization).toBe('Bearer supabase-token')
    expect(calls[0].opts.credentials).toBeUndefined()
  })

  it('sends no Authorization header when signed out', async () => {
    const calls = stubFetch()
    await apiFetch('/api/ping')
    expect(calls[0].opts.headers.Authorization).toBeUndefined()
  })

  it('throws the FastAPI detail with the HTTP status attached', async () => {
    stubFetch(403, { detail: 'no_account' })
    await expect(apiFetch('/api/auth/me')).rejects.toMatchObject({ message: 'no_account', status: 403 })
  })
})

describe('apiUpload', () => {
  it('sends no extra headers when signed out', async () => {
    const calls = stubFetch()
    await apiUpload('/api/ingest/health-export', new FormData())

    expect(calls).toHaveLength(1)
    expect(calls[0].opts.headers).toEqual({})
  })

  it("an explicit bearer (the ingest token) wins over the user's token", async () => {
    accessToken = 'supabase-token'
    const calls = stubFetch()
    await apiUpload('/api/ingest/health-export', new FormData(), { Authorization: 'Bearer abc123' })

    expect(calls[0].opts.headers).toEqual({ Authorization: 'Bearer abc123' })
  })

  it('never sets Content-Type — the browser must own the multipart boundary', async () => {
    const calls = stubFetch()
    await apiUpload('/api/ingest/health-export', new FormData(), { Authorization: 'Bearer abc123' })

    expect(calls[0].opts.headers['Content-Type']).toBeUndefined()
  })
})

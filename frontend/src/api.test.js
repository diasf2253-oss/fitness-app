/**
 * apiUpload's Authorization-header passthrough — the bug this covers: the
 * export.zip history backfill hits an ingest endpoint (require_ingest_auth,
 * a bearer token), but apiUpload only ever sent the session cookie, so
 * backfill 401'd with "missing bearer token" on every attempt.
 */
import { afterEach, describe, expect, it, vi } from 'vitest'
import { apiUpload } from './api'

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

describe('apiUpload', () => {
  it('sends no extra headers by default (cookie-only, as before)', async () => {
    const calls = stubFetch()
    const form = new FormData()
    await apiUpload('/api/ingest/health-export', form)

    expect(calls).toHaveLength(1)
    expect(calls[0].opts.credentials).toBe('include')
    expect(calls[0].opts.headers).toEqual({})
  })

  it('attaches an Authorization bearer header when passed', async () => {
    const calls = stubFetch()
    const form = new FormData()
    await apiUpload('/api/ingest/health-export', form, { Authorization: 'Bearer abc123' })

    expect(calls[0].opts.headers).toEqual({ Authorization: 'Bearer abc123' })
    // Still sends the cookie too — ingest is bearer-only server-side, but
    // nothing stops the cookie riding along, and other callers still rely on it
    expect(calls[0].opts.credentials).toBe('include')
  })

  it('never sets Content-Type — the browser must own the multipart boundary', async () => {
    const calls = stubFetch()
    const form = new FormData()
    await apiUpload('/api/ingest/health-export', form, { Authorization: 'Bearer abc123' })

    expect(calls[0].opts.headers['Content-Type']).toBeUndefined()
  })
})

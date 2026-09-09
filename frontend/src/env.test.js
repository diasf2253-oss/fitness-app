/**
 * env.js — API base resolution + staging detection.
 * The module reads import.meta.env at load time, so each case stubs the
 * env and re-imports a fresh copy.
 */
import { describe, it, expect, vi, afterEach } from 'vitest'

async function loadEnv(vars = {}) {
  vi.resetModules()
  for (const [k, v] of Object.entries(vars)) vi.stubEnv(k, v)
  return import('./env')
}

afterEach(() => {
  vi.unstubAllEnvs()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('apiUrl', () => {
  it('leaves paths relative when no base is configured (same-origin default)', async () => {
    const { apiUrl, API_BASE } = await loadEnv()
    expect(API_BASE).toBe('')
    expect(apiUrl('/api/exercises')).toBe('/api/exercises')
  })

  it('prefixes the configured API origin', async () => {
    const { apiUrl } = await loadEnv({ VITE_API_BASE_URL: 'https://api.example.com' })
    expect(apiUrl('/api/sync/pull?since=x')).toBe('https://api.example.com/api/sync/pull?since=x')
  })

  it('tolerates a trailing slash on the configured base', async () => {
    const { apiUrl } = await loadEnv({ VITE_API_BASE_URL: 'https://api.example.com/' })
    expect(apiUrl('/api/ping')).toBe('https://api.example.com/api/ping')
  })
})

describe('isStagingBuild', () => {
  it('is false by default', async () => {
    const { isStagingBuild } = await loadEnv()
    expect(isStagingBuild()).toBe(false)
  })

  it('is true when VITE_APP_ENV=staging', async () => {
    const { isStagingBuild } = await loadEnv({ VITE_APP_ENV: 'staging' })
    expect(isStagingBuild()).toBe(true)
  })

  it('is true when the API base host contains "staging"', async () => {
    const { isStagingBuild } = await loadEnv({
      VITE_API_BASE_URL: 'https://fitness-staging.up.railway.app',
    })
    expect(isStagingBuild()).toBe(true)
  })

  it('is false for a production API base', async () => {
    const { isStagingBuild } = await loadEnv({
      VITE_API_BASE_URL: 'https://fitness.up.railway.app',
    })
    expect(isStagingBuild()).toBe(false)
  })
})

describe('probeStagingApi', () => {
  it('resolves true only when the API reports env=staging', async () => {
    const { probeStagingApi } = await loadEnv()
    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true,
      json: async () => ({ status: 'ok', env: 'staging' }),
    })))
    await expect(probeStagingApi()).resolves.toBe(true)

    vi.stubGlobal('fetch', vi.fn(async () => ({
      ok: true,
      json: async () => ({ status: 'ok', env: 'production' }),
    })))
    await expect(probeStagingApi()).resolves.toBe(false)
  })

  it('resolves false when the API is unreachable', async () => {
    const { probeStagingApi } = await loadEnv()
    vi.stubGlobal('fetch', vi.fn(async () => { throw new Error('offline') }))
    await expect(probeStagingApi()).resolves.toBe(false)
  })
})

/**
 * Deployment-environment helpers.
 *
 * Normally the app lives on the same origin as its API (FastAPI serves the
 * built frontend), so API paths are relative. The Vercel staging/preview
 * frontends are the exception: they are static hosts whose API lives on the
 * staging Railway origin, configured at build time via VITE_API_BASE_URL.
 * apiUrl() prefixes every API path with it; with no base configured it is a
 * no-op and nothing changes for the laptop, the phone PWA, or dev.
 *
 * STAGING detection — the badge must show whenever we talk to the staging
 * API, whichever build this is:
 *  - build-time: VITE_APP_ENV=staging (Vercel Preview env vars; also passed
 *    into the staging Railway image as a Docker build arg), or an API base /
 *    page host containing "staging";
 *  - runtime fallback: /api/ping reports env=staging (probeStagingApi) —
 *    catches a staging host with no "staging" in its domain name.
 */

const RAW_BASE = import.meta.env.VITE_API_BASE_URL || ''

/** Absolute origin of the API, no trailing slash. '' ⇒ same origin. */
export const API_BASE = RAW_BASE.replace(/\/+$/, '')

/** Prefix an '/api/...' path with the configured API origin, if any. */
export function apiUrl(path) {
  return API_BASE ? API_BASE + path : path
}

/** True when the build itself (or its hosts) declares staging. Synchronous —
 *  this is what mounts the badge instantly, before any network round-trip. */
export function isStagingBuild() {
  if (import.meta.env.VITE_APP_ENV === 'staging') return true
  try {
    if (API_BASE && new URL(API_BASE).hostname.includes('staging')) return true
  } catch { /* unparsable base — fall through to the other signals */ }
  if (typeof window !== 'undefined'
      && window.location.hostname.includes('staging')) return true
  return false
}

/** Ask the API which environment it is. Resolves true only on a confirmed
 *  staging answer; unreachable/odd responses resolve false (never throws). */
export async function probeStagingApi() {
  try {
    const controller = new AbortController()
    const timer = setTimeout(() => controller.abort(), 4000)
    const res = await fetch(apiUrl('/api/ping'), { signal: controller.signal })
    clearTimeout(timer)
    if (!res.ok) return false
    const data = await res.json()
    return data.env === 'staging'
  } catch {
    return false
  }
}

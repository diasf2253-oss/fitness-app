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

/**
 * Absolute API origin, always — what the iOS Shortcut must POST to.
 *
 * apiUrl() returns a relative path when the API is same-origin, which is
 * right for fetch() but useless to paste into Shortcuts. This resolves it
 * against the page. Note it deliberately does NOT use window.location.origin
 * unconditionally: on the Vercel frontends the API lives on the Railway
 * origin, and a Shortcut pointed at the frontend host would silently 404.
 */
export function absoluteApiUrl(path) {
  if (API_BASE) return API_BASE + path
  if (typeof window === 'undefined') return path
  return window.location.origin + path
}

/**
 * iCloud link to the shared "Tracker Health Sync" Shortcut. A PWA cannot read
 * HealthKit, so this Shortcut is how health data leaves the phone at all —
 * one build of it, installed by everyone, prompting each person for their own
 * server URL and ingest token at install time.
 *
 * Overridable per deployment (VITE_HEALTH_SHORTCUT_URL) so the link can be
 * replaced without a code change. Empty ⇒ the UI falls back to the manual
 * build recipe in docs/HEALTH_INGEST_SHORTCUT.md.
 */
export const HEALTH_SHORTCUT_URL = import.meta.env.VITE_HEALTH_SHORTCUT_URL || ''

/** Shortcut name the deep link runs. Must match the shared Shortcut exactly. */
export const HEALTH_SHORTCUT_NAME = 'Tracker Health Sync'

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

/**
 * Apple Health sync plumbing shared by the Settings card and the stale-data
 * banner.
 *
 * Why any of this exists: iOS gives web apps no HealthKit access at all, so
 * this PWA can never read weight/steps/sleep itself. The only way that data
 * reaches the server is the phone pushing it — an iOS Shortcut posting to
 * /api/ingest/health/shortcut, run by a daily automation or by hand.
 *
 * `runHealthShortcut()` is the "by hand" path: iOS exposes a `shortcuts://`
 * URL scheme, so a button in the web app really can start the sync. It is
 * the closest thing to an in-app sync button that the platform allows.
 */
import { useEffect, useState } from 'react'
import { apiFetch } from '../api'
import { HEALTH_SHORTCUT_NAME, HEALTH_SHORTCUT_URL } from '../env'
import { SYNC_COMPLETE_EVENT } from '../local/sync'

/**
 * iOS/iPadOS detection. The second clause catches modern iPadOS, which
 * reports itself as "MacIntel" — the touch-point count is what gives it away.
 */
export function isIOS() {
  if (typeof navigator === 'undefined') return false
  if (/iP(hone|ad|od)/.test(navigator.userAgent)) return true
  return navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1
}

export const hasShortcutLink = () => Boolean(HEALTH_SHORTCUT_URL)

/**
 * Run the shared Shortcut on this phone.
 *
 * x-callback-url's `x-success` sends the user back here when the push
 * finishes, instead of stranding them in the Shortcuts app. iOS shows a
 * one-time confirmation the first time a site opens Shortcuts.
 */
export function shortcutRunUrl(returnUrl, name = HEALTH_SHORTCUT_NAME) {
  return 'shortcuts://x-callback-url/run-shortcut'
    + `?name=${encodeURIComponent(name)}`
    + `&x-success=${encodeURIComponent(returnUrl)}`
}

// Must match main.jsx's FORCE_RESYNC_KEY exactly — there's no shared module
// between them (main.jsx runs its sync setup before React mounts), so this
// string is the entire contract between the two files. Change one, change
// both — see the export in HealthSync.test.js for the value this pins.
export const FORCE_RESYNC_KEY = 'force_resync_on_resume'

export function runHealthShortcut() {
  // Without this, main.jsx's resync throttle (2 minutes from app-open) would
  // silently swallow the visibilitychange that fires when iOS bounces back
  // from Shortcuts via x-success — the "Sync now" tap would appear to do
  // nothing on the most common path: opening the app, seeing it's stale, and
  // immediately tapping the fix.
  try { sessionStorage.setItem(FORCE_RESYNC_KEY, '1') } catch { /* private mode */ }
  window.location.href = shortcutRunUrl(window.location.href)
}

/** Human phrasing for a staleness in days. */
export function freshnessLabel(days) {
  if (days === null || days === undefined) return 'no data'
  if (days <= 0) return 'today'
  if (days === 1) return 'yesterday'
  return `${days} days ago`
}

/**
 * Shared sync-status store — one fetch, one set of listeners, no matter how
 * many components call useSyncStatus() below.
 *
 * Up to three places want this at once (the sidebar, the stale-data banner,
 * and the Settings card), all mounted together for the lifetime of a session.
 * Without a shared store, each held its own visibilitychange/SYNC_COMPLETE_EVENT
 * listener and its own fetch — every tab switch or Shortcut round-trip fired
 * 2-3 concurrent GET /api/health/sync-status calls (4 IndexedDB table scans
 * apiece in local-first mode) to answer the exact same question.
 *
 * `error` is exposed but deliberately never clears `status` — a transient
 * failure keeps showing the last-known freshness (stale-but-real beats
 * nothing), and a component that has *never* had a successful fetch can
 * still tell `error && !status` apart from "still loading" to show something
 * rather than silently vanishing, which is what a status/banner component
 * whose entire job is "tell the user when something is wrong" must not do.
 */
let cachedStatus = null
let cachedError = null
let inFlight = null
let lastFetchAt = 0
const listeners = new Set()

// Rapid tab-switching (or several mounted consumers hitting visibilitychange
// at once) shouldn't each trigger a fresh request — a few seconds of slack
// is invisible to a person reading a freshness number in days.
const MIN_REFETCH_INTERVAL_MS = 5000

function notify() {
  for (const fn of listeners) fn()
}

async function refreshSyncStatus({ force = false } = {}) {
  if (inFlight) return inFlight
  if (!force && Date.now() - lastFetchAt < MIN_REFETCH_INTERVAL_MS) return null
  inFlight = apiFetch('/api/health/sync-status')
    .then(s => { cachedStatus = s; cachedError = null })
    .catch(e => { cachedError = e })
    .finally(() => { inFlight = null; lastFetchAt = Date.now(); notify() })
  return inFlight
}

/**
 * Poll-free sync status, shared across every caller (see above).
 *
 * Refetches on `visibilitychange` because that is exactly when the answer
 * changes: the user taps "Sync now", iOS switches to Shortcuts, the push
 * lands, and x-success brings them back — no reload, so nothing else would
 * notice the new data.
 *
 * Also refetches when a device sync completes. In local-first mode this
 * status is computed from IndexedDB, which on a cold open is still empty
 * while the pull is in flight — without this the app briefly claims there is
 * no health data at all.
 */
export function useSyncStatus() {
  const [, forceRender] = useState(0)

  useEffect(() => {
    const onChange = () => forceRender(n => n + 1)
    listeners.add(onChange)
    if (!cachedStatus && !inFlight) refreshSyncStatus({ force: true })

    const onVisible = () => { if (!document.hidden) refreshSyncStatus() }
    const onSyncComplete = () => refreshSyncStatus({ force: true })
    document.addEventListener('visibilitychange', onVisible)
    window.addEventListener(SYNC_COMPLETE_EVENT, onSyncComplete)
    return () => {
      listeners.delete(onChange)
      document.removeEventListener('visibilitychange', onVisible)
      window.removeEventListener(SYNC_COMPLETE_EVENT, onSyncComplete)
    }
  }, [])

  return {
    status: cachedStatus,
    error: cachedError,
    // True only when every attempt so far has failed — a stale-but-real
    // status is not "unreachable," it's just stale, which the freshness
    // numbers themselves already say.
    unreachable: Boolean(cachedError) && !cachedStatus,
    refresh: () => refreshSyncStatus({ force: true }),
  }
}

/**
 * The "Sync now" button. iOS only — everywhere else the Shortcut can't run,
 * and a dead button is worse than no button.
 */
export function SyncNowButton({ className = 'secondary', style, label = 'Sync Health now' }) {
  if (!isIOS()) return null
  return (
    <button className={className} style={style} onClick={runHealthShortcut}>
      {label}
    </button>
  )
}

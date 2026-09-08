import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'
import { isLocalFirst } from './local/mode'
import { syncNow } from './local/sync'
import { installUnlockListeners, playAppOpen, playTap, preload } from './audio'

// Link-based onboarding via URL params, then strip them so they aren't left
// in the address bar or history:
//   ?local=1  — make THIS device local-first: it runs on its own on-device
//               copy of the data and only syncs when it can reach the API.
//               Set once on the phone; other devices, opened without it,
//               keep talking straight to the server.
;(function adoptSettingsFromUrl() {
  const params = new URLSearchParams(window.location.search)
  let changed = false

  if (params.get('local') === '1') {
    try { localStorage.setItem('local_first', '1') } catch { /* private mode */ }
    params.delete('local')
    changed = true
  }

  if (changed) {
    const qs = params.toString()
    window.history.replaceState(
      {}, '',
      window.location.pathname + (qs ? `?${qs}` : '') + window.location.hash,
    )
  }
})()

ReactDOM.createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </React.StrictMode>
)

// Register the service worker (versioned offline app shell) — makes the
// installed PWA open and work with no server reachable.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {})
  })
}

// Audio cue layer. Fetch the clips now (best-effort, no AudioContext yet), arm
// the iOS unlock (first gesture resumes audio), and request the app-open cue —
// it no-ops until unlock, then plays on that first tap. The subtle tap cue is a
// single delegated listener on `document`: it sits earlier in the bubble path
// than the window unlock listener, so the very first tap unlocks + plays
// app-open WITHOUT also firing a tap.
preload()
installUnlockListeners()
playAppOpen()
document.addEventListener('pointerdown', (e) => {
  const el = e.target.closest?.('button, [role="button"], a[href]')
  if (el && !el.disabled && el.getAttribute('aria-disabled') !== 'true') playTap()
}, { passive: true })

// Sync on open (local-first mode): if the server answers, exchange changes;
// if not, carry on fully local. Never blocks the UI.
//
// "On open" has to mean more than module load. An installed PWA is usually
// *resumed*, not reloaded — iOS keeps the page alive in the background — so a
// load-time-only sync would run once on install day and then effectively
// never again. Re-running on visibilitychange is what makes reopening the app
// actually fetch what the phone pushed overnight.
if (isLocalFirst()) {
  // Enough to catch a genuine reopen, short enough that a tab switch or a
  // trip out to Shortcuts and back doesn't hammer the API.
  const RESYNC_AFTER_MS = 2 * 60 * 1000
  let lastSyncAt = 0
  let inFlight = false

  // Set by HealthSync.jsx's runHealthShortcut() right before it navigates to
  // shortcuts://, so the visibilitychange that fires when iOS bounces back
  // (via x-success) isn't swallowed by the throttle above — see runSync.
  const FORCE_RESYNC_KEY = 'force_resync_on_resume'
  function consumeForcedResync() {
    try {
      if (sessionStorage.getItem(FORCE_RESYNC_KEY) !== '1') return false
      sessionStorage.removeItem(FORCE_RESYNC_KEY)
      return true
    } catch {
      return false  // private mode / blocked storage — falls back to the throttle
    }
  }

  const runSync = (reason) => {
    // An explicit user tap (e.g. "Sync now", returning from the Shortcut)
    // bypasses the throttle — the throttle exists to stop passive foreground
    // events from hammering the API, not to ignore the one action whose
    // entire point is "sync right now." See FORCE_RESYNC_KEY below.
    const forced = reason === 'resume' && consumeForcedResync()
    if (!forced && (inFlight || Date.now() - lastSyncAt < RESYNC_AFTER_MS)) return
    inFlight = true
    syncNow()
      .then(r => {
        if (r.reachable) console.info(`[sync:${reason}] pushed ${r.pushed}, pulled ${r.pulled}`)
        else console.info(`[sync:${reason}] API not reachable or not logged in — staying local`)
      })
      .catch(err => console.warn(`[sync:${reason}] failed:`, err))
      // Throttle from the attempt, not the success — an offline phone would
      // otherwise retry on every single foreground.
      .finally(() => { inFlight = false; lastSyncAt = Date.now() })
  }

  runSync('open')
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) runSync('resume')
  })
}

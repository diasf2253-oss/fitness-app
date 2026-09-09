/**
 * "Your health data is stale" nudge, shown on every page.
 *
 * The app is a body-recomposition instrument first: without weight, steps and
 * sleep flowing in, most of it is guessing. But a PWA can't read HealthKit, so
 * data only arrives when the phone pushes it — and when that quietly stops
 * (automation off, token rotated, Shortcut never installed) nothing else in
 * the UI says so. The charts just thin out. This is the thing that says so.
 *
 * On iOS it offers a real one-tap fix, because `shortcuts://` lets a web page
 * start the sync. Elsewhere it points at the setup instructions instead.
 */
import React, { useState } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { useAuth } from '../auth'
import { SyncNowButton, useSyncStatus } from './HealthSync'

// Data older than this is worth interrupting the user about. One day of lag is
// normal — a morning automation hasn't run yet when you open the app at 07:00.
const STALE_AFTER_DAYS = 2

const DISMISS_KEY_PREFIX = 'health_sync_banner_dismissed:'

// Scoped by user id: this is an invite-only beta where switching accounts on
// a shared device is a documented, expected flow (CLAUDE.md). An unscoped
// key would let one person's dismissal hide the banner for the next person
// who logs in on the same tab — logout doesn't clear sessionStorage.
function dismissedThisSession(userId) {
  try {
    return sessionStorage.getItem(DISMISS_KEY_PREFIX + userId) === '1'
  } catch {
    return false  // private mode / blocked storage — just show it
  }
}

export default function HealthSyncBanner() {
  const { user } = useAuth()
  const { status, unreachable } = useSyncStatus()
  const { pathname } = useLocation()
  const [dismissed, setDismissed] = useState(() => dismissedThisSession(user.id))

  function dismiss() {
    setDismissed(true)
    try { sessionStorage.setItem(DISMISS_KEY_PREFIX + user.id, '1') } catch { /* non-critical */ }
  }

  // Settings is where the fix lives — no point nagging someone already there.
  if (dismissed || pathname === '/settings') return null

  // Every attempt to check has failed — surface that distinctly rather than
  // rendering nothing, which is exactly the "sync silently died and nothing
  // says so" failure this banner exists to catch.
  if (unreachable) {
    return (
      <div className="sync-banner" role="status">
        <span className="sync-banner-text">Couldn't check your health sync status.</span>
        <div className="sync-banner-actions">
          <button className="sync-banner-close" onClick={dismiss} aria-label="Dismiss">×</button>
        </div>
      </div>
    )
  }

  if (!status) return null  // still loading — nothing to say yet

  const never = !status.has_any_data
  const stale = status.stalest_days !== null && status.stalest_days >= STALE_AFTER_DAYS
  if (!never && !stale) return null

  const message = never
    ? 'No health data yet. Connect Apple Health to track weight, steps and sleep.'
    : `Health data is ${status.stalest_days} days old.`

  return (
    <div className="sync-banner" role="status">
      <span className="sync-banner-text">{message}</span>
      <div className="sync-banner-actions">
        <SyncNowButton className="secondary sync-banner-btn" label="Sync now" />
        <Link to="/settings">
          <button className="secondary sync-banner-btn">
            {never ? 'Set up' : 'Fix'}
          </button>
        </Link>
        <button
          className="sync-banner-close"
          onClick={dismiss}
          aria-label="Dismiss"
        >
          ×
        </button>
      </div>
    </div>
  )
}

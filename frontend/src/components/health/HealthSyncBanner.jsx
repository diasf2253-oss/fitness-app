/**
 * Daily weigh-in nudge, shown at the top of every page.
 *
 * The app is a body-recomposition instrument first, and the weight trend is
 * its spine. Apple Health sync is paused (a web app can't read HealthKit), so
 * weight arrives by hand — and a missed weigh-in is the one gap that quietly
 * degrades everything downstream (trend, adaptive calories, ranks).
 *
 * So: when today's weight isn't logged yet, offer a one-tap "Log weight" that
 * opens the quick-log sheet. Dismissible for the rest of the day. Freshness
 * comes from GET /api/health/sync-status (real readings only — estimates and
 * sample rows never count as logged), refreshed after every quick-log save.
 */
import React, { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { useAuth } from '../../auth/auth'
import { useSyncStatus } from './HealthSync'
import { openQuickLog } from '../training/QuickLog'

const DISMISS_KEY_PREFIX = 'weighin_nudge_dismissed:'

function localToday() {
  const d = new Date()
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 10)
}

// Scoped by user AND day: a dismissal lasts until tomorrow, and switching
// accounts on a shared device (a documented flow) never hides it for someone else.
const dismissKey = userId => `${DISMISS_KEY_PREFIX}${userId}:${localToday()}`

function dismissedToday(userId) {
  try { return localStorage.getItem(dismissKey(userId)) === '1' } catch { return false }
}

export default function HealthSyncBanner() {
  const { user } = useAuth()
  const { status } = useSyncStatus()
  const { pathname } = useLocation()
  const [dismissed, setDismissed] = useState(() => dismissedToday(user.id))

  function dismiss() {
    setDismissed(true)
    try { localStorage.setItem(dismissKey(user.id), '1') } catch { /* non-critical */ }
  }

  // Already on the full log page — no need to nudge.
  if (dismissed || pathname === '/log' || !status) return null

  const weighedToday = status.weight?.last_date === localToday()
  if (weighedToday) return null

  return (
    <div className="sync-banner" role="status">
      <span className="sync-banner-text">Weight not logged today.</span>
      <div className="sync-banner-actions">
        <button className="secondary sync-banner-btn" onClick={() => openQuickLog('weight')}>
          Log weight
        </button>
        <button className="sync-banner-close" onClick={dismiss} aria-label="Dismiss for today">×</button>
      </div>
    </div>
  )
}

import React, { useEffect, useState } from 'react'
import { Routes, Route, Navigate, NavLink, useLocation } from 'react-router-dom'
import { apiFetch } from './api'
import { AuthProvider, useAuth } from './auth'
import Dashboard from './pages/Dashboard'
import Workout from './pages/Workout'
import Routines from './pages/Routines'
import Exercises from './pages/Exercises'
import History from './pages/History'
import ExerciseDetail from './pages/ExerciseDetail'
import Settings from './pages/Settings'
import Log from './pages/Log'
import Insights from './pages/Insights'
import Ranks from './pages/Ranks'
import Generator from './pages/Generator'
import Report from './pages/Report'
import Diet from './pages/Diet'
// Coach page killed per workbook H9 (grade D) — code kept at pages/Coach.jsx
import Login from './pages/Login'
import Join from './pages/Join'
import ChangePassword from './pages/ChangePassword'
import Admin from './pages/Admin'
import Onboarding from './components/Onboarding'
import StagingBadge from './components/StagingBadge'
import HealthSyncBanner from './components/HealthSyncBanner'
import { freshnessLabel, useSyncStatus } from './components/HealthSync'

// Crisp stroke icons (inherit currentColor → active state recolors for free)
const Icon = {
  home: (
    <path d="m3 9 9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z M9 22V12h6v10" />
  ),
  workout: (
    <path d="M4 9v6 M7 7v10 M17 7v10 M20 9v6 M7 12h10" />
  ),
  routines: (
    <path d="M8 3h8v3H8z M9 4H7a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V6a2 2 0 0 0-2-2h-2 M9 12h6 M9 16h6" />
  ),
  history: (
    <path d="M22 12h-4l-3 8L9 4l-3 8H2" />
  ),
  settings: (
    <path d="M4 21v-7 M4 10V3 M12 21v-9 M12 8V3 M20 21v-5 M20 12V3 M1 14h6 M9 8h6 M17 16h6" />
  ),
  exercises: (
    <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20 M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
  ),
  log: (
    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7 M18.5 2.5a2.12 2.12 0 0 1 3 3L12 15l-4 1 1-4z" />
  ),
  insights: (
    <path d="M3 3v18h18 M7 14l4-4 3 3 5-6" />
  ),
  coach: (
    <path d="M21 11.5a8.38 8.38 0 0 1-.9 3.8 8.5 8.5 0 0 1-7.6 4.7 8.38 8.38 0 0 1-3.8-.9L3 21l1.9-5.7a8.38 8.38 0 0 1-.9-3.8 8.5 8.5 0 0 1 4.7-7.6 8.38 8.38 0 0 1 3.8-.9h.5a8.48 8.48 0 0 1 8 8z" />
  ),
  ranks: (
    <path d="M8 21h8 M12 17v4 M7 4h10v6a5 5 0 0 1-10 0z M7 6H4a1 1 0 0 0-1 1 4 4 0 0 0 4 4 M17 6h3a1 1 0 0 1 1 1 4 4 0 0 1-4 4" />
  ),
  diet: (
    <path d="M12 8c-1.5-3-6-3-7 0-1 3 2 8 5 11 1 1 3 1 4 0 3-3 6-8 5-11-1-3-5.5-3-7 0 M12 8V4 M12 4c0-1 1-2 2-2" />
  ),
  admin: (
    <path d="M12 2 4 6v6c0 5 3.5 8.5 8 10 4.5-1.5 8-5 8-10V6z M9 12l2 2 4-4" />
  ),
}

function NavIcon({ name }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {Icon[name]}
    </svg>
  )
}

// Bottom navigation (phone) — the five primary destinations
const NAV_ITEMS = [
  { to: '/',        label: 'Home',     icon: 'home' },
  { to: '/workout', label: 'Workout',  icon: 'workout' },
  { to: '/diet',    label: 'Diet',     icon: 'diet' },
  { to: '/history', label: 'History',  icon: 'history' },
  { to: '/settings',label: 'Settings', icon: 'settings' },
]

// Sidebar (desktop ≥1024px) — same destinations, grouped like a workspace
const SIDEBAR_SECTIONS = [
  {
    label: 'General',
    items: [
      { to: '/',         label: 'Dashboard', icon: 'home' },
      { to: '/workout',  label: 'Workout',   icon: 'workout' },
      { to: '/routines', label: 'Routines',  icon: 'routines' },
      { to: '/history',  label: 'History',   icon: 'history' },
      { to: '/diet',     label: 'Diet',      icon: 'diet' },
      { to: '/insights', label: 'Insights',  icon: 'insights' },
      { to: '/report',   label: 'Report',    icon: 'insights' },
      { to: '/ranks',    label: 'Ranks',     icon: 'ranks' },
    ],
  },
  {
    label: 'Tools',
    items: [
      { to: '/generator', label: 'Workout generator', icon: 'workout' },
      { to: '/exercises', label: 'Exercise library',  icon: 'exercises' },
      { to: '/log',       label: 'Manual log',        icon: 'log' },
      { to: '/settings',  label: 'Settings',          icon: 'settings' },
    ],
  },
]

/**
 * Quiet "is data flowing" line at the sidebar foot.
 *
 * Reads /api/health/sync-status rather than settings.health_last_ingest: the
 * latter is served from IndexedDB in local-first mode, where it defaults to
 * null, so this used to read "Not synced yet" even on a perfectly synced
 * phone. Freshness of the actual rows is both truer and computable offline.
 */
function SyncStatus() {
  const { status, unreachable } = useSyncStatus()

  // Every check has failed — say so rather than disappearing, which would
  // otherwise look identical to "still loading" forever.
  if (unreachable) {
    return (
      <div className="sidebar-sync">
        <span className="sync-dot" style={{ background: 'var(--color-warning)' }} />
        Sync check failed
      </div>
    )
  }
  if (!status) return null
  const days = status.stalest_days
  const fresh = days !== null && days <= 1
  return (
    <div className="sidebar-sync">
      <span
        className="sync-dot"
        style={{
          background: fresh ? 'var(--color-success)'
            : days === null ? 'var(--color-muted)' : 'var(--color-warning)',
        }}
      />
      {status.has_any_data ? `Health ${freshnessLabel(days)}` : 'Not synced yet'}
    </div>
  )
}

// Navigating to a new page should land at the top, not inherit scroll depth
function ScrollToTop() {
  const { pathname } = useLocation()
  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])
  return null
}

function Sidebar({ isAdmin }) {
  return (
    <aside className="sidebar">
      {/* Wordmark — placeholder name, easy to rebrand later */}
      <div className="wordmark">tracker<span className="text-primary">.</span></div>
      {SIDEBAR_SECTIONS.map(section => (
        <nav key={section.label}>
          <div className="sidebar-label">{section.label}</div>
          {section.items.map(({ to, label, icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) => isActive ? 'active' : undefined}
            >
              <NavIcon name={icon} />
              {label}
            </NavLink>
          ))}
        </nav>
      ))}
      {isAdmin && (
        <nav>
          <div className="sidebar-label">Admin</div>
          <NavLink to="/admin" className={({ isActive }) => isActive ? 'active' : undefined}>
            <NavIcon name="admin" />
            Admin
          </NavLink>
        </nav>
      )}
      <SyncStatus />
    </aside>
  )
}

/** Everything shown once a session is confirmed active. */
function AuthedApp({ user }) {
  // First-run gate: show the onboarding wizard only when settings say the
  // user hasn't onboarded. `null` = still loading (render nothing wizard-wise).
  // Declared before any conditional return — hooks must run unconditionally.
  const [onboarded, setOnboarded] = useState(null)

  useEffect(() => {
    if (user.must_change_password) return   // settings 403s until the password is set
    apiFetch('/api/settings')
      .then(s => setOnboarded(s.onboarded !== false))
      .catch(() => setOnboarded(true))   // never block the app on a settings error
  }, [user.must_change_password])

  // Forced password change (admin-issued temp password) — the only screen
  // reachable until it's done; require_auth blocks every other route too.
  if (user.must_change_password) {
    return (
      <>
        <StagingBadge />
        <ChangePassword />
      </>
    )
  }

  if (onboarded === false) {
    return (
      <>
        <StagingBadge />
        <Onboarding onDone={() => setOnboarded(true)} />
      </>
    )
  }

  const isAdmin = user.role === 'admin'

  return (
    <>
      <StagingBadge />
      <ScrollToTop />
      <Sidebar isAdmin={isAdmin} />

      <div className="main-content">
        <HealthSyncBanner />
        <Routes>
          <Route path="/"             element={<Dashboard />} />
          <Route path="/workout"      element={<Workout />} />
          <Route path="/routines"     element={<Routines />} />
          <Route path="/exercises"    element={<Exercises />} />
          <Route path="/history"      element={<History />} />
          <Route path="/exercise/:id" element={<ExerciseDetail />} />
          <Route path="/log"          element={<Log />} />
          <Route path="/insights"     element={<Insights />} />
          <Route path="/ranks"        element={<Ranks />} />
          <Route path="/generator"    element={<Generator />} />
          <Route path="/report"       element={<Report />} />
          <Route path="/diet"         element={<Diet />} />
          <Route path="/settings"     element={<Settings />} />
          <Route path="/admin"        element={isAdmin ? <Admin /> : <Navigate to="/" replace />} />
          <Route path="/login"        element={<Navigate to="/" replace />} />
          <Route path="/join"         element={<Navigate to="/" replace />} />
          <Route path="*"             element={<Navigate to="/" replace />} />
        </Routes>
      </div>

      {/* Fixed bottom navigation bar (phone only — hidden at desktop) */}
      <nav className="nav">
        {NAV_ITEMS.map(({ to, label, icon }) => (
          <NavLink
            key={to}
            to={to}
            end={to === '/'}
            className={({ isActive }) => isActive ? 'active' : undefined}
          >
            <span className="nav-icon"><NavIcon name={icon} /></span>
            {label}
          </NavLink>
        ))}
      </nav>
    </>
  )
}

/** Everything shown while logged out — no data, no sidebar, no nav. */
function AnonApp() {
  return (
    <>
      <StagingBadge />
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/join"  element={<Join />} />
        <Route path="*"      element={<Navigate to="/login" replace />} />
      </Routes>
    </>
  )
}

function AppShell() {
  const { status, user } = useAuth()
  if (status === 'loading') return null
  if (status === 'anon') return <AnonApp />
  return <AuthedApp user={user} />
}

export default function App() {
  return (
    <AuthProvider>
      <AppShell />
    </AuthProvider>
  )
}

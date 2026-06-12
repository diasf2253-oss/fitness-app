import React, { useEffect, useState } from 'react'
import { Routes, Route, NavLink, useLocation } from 'react-router-dom'
import { apiFetch } from './api'
import Dashboard from './pages/Dashboard'
import Workout from './pages/Workout'
import Routines from './pages/Routines'
import Exercises from './pages/Exercises'
import History from './pages/History'
import ExerciseDetail from './pages/ExerciseDetail'
import Settings from './pages/Settings'
import Log from './pages/Log'
import Insights from './pages/Insights'

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
  { to: '/routines',label: 'Routines', icon: 'routines' },
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
      { to: '/insights', label: 'Insights',  icon: 'insights' },
    ],
  },
  {
    label: 'Tools',
    items: [
      { to: '/exercises', label: 'Exercise library', icon: 'exercises' },
      { to: '/log',       label: 'Manual log',       icon: 'log' },
      { to: '/settings',  label: 'Settings',         icon: 'settings' },
    ],
  },
]

/**
 * Quiet "is data flowing" line at the sidebar foot — last Apple Health
 * ingest time, or a nudge when nothing has ever synced. Fails silent.
 */
function SyncStatus() {
  const [last, setLast] = useState(undefined)

  useEffect(() => {
    apiFetch('/api/settings')
      .then(s => setLast(s.health_last_ingest))
      .catch(() => setLast(null))
  }, [])

  if (last === undefined) return null
  const label = last
    ? `Synced ${new Date(last + 'Z').toLocaleDateString(undefined, { day: 'numeric', month: 'short' })}`
    : 'Not synced yet'
  return (
    <div className="sidebar-sync">
      <span
        className="sync-dot"
        style={{ background: last ? 'var(--color-success)' : 'var(--color-muted)' }}
      />
      {label}
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

function Sidebar() {
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
      <SyncStatus />
    </aside>
  )
}

export default function App() {
  return (
    <>
      <ScrollToTop />
      <Sidebar />

      <div className="main-content">
        <Routes>
          <Route path="/"             element={<Dashboard />} />
          <Route path="/workout"      element={<Workout />} />
          <Route path="/routines"     element={<Routines />} />
          <Route path="/exercises"    element={<Exercises />} />
          <Route path="/history"      element={<History />} />
          <Route path="/exercise/:id" element={<ExerciseDetail />} />
          <Route path="/log"          element={<Log />} />
          <Route path="/insights"     element={<Insights />} />
          <Route path="/settings"     element={<Settings />} />
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

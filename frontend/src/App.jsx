import React from 'react'
import { Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Workout from './pages/Workout'
import Routines from './pages/Routines'
import Exercises from './pages/Exercises'
import History from './pages/History'
import ExerciseDetail from './pages/ExerciseDetail'
import Settings from './pages/Settings'

// Crisp stroke icons (inherit currentColor → active tab turns orange for free)
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
}

function NavIcon({ name }) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth="1.75" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      {Icon[name]}
    </svg>
  )
}

// Bottom navigation items
const NAV_ITEMS = [
  { to: '/',        label: 'Home',     icon: 'home' },
  { to: '/workout', label: 'Workout',  icon: 'workout' },
  { to: '/routines',label: 'Routines', icon: 'routines' },
  { to: '/history', label: 'History',  icon: 'history' },
  { to: '/settings',label: 'Settings', icon: 'settings' },
]

export default function App() {
  return (
    <>
      <div className="main-content">
        <Routes>
          <Route path="/"             element={<Dashboard />} />
          <Route path="/workout"      element={<Workout />} />
          <Route path="/routines"     element={<Routines />} />
          <Route path="/exercises"    element={<Exercises />} />
          <Route path="/history"      element={<History />} />
          <Route path="/exercise/:id" element={<ExerciseDetail />} />
          <Route path="/settings"     element={<Settings />} />
        </Routes>
      </div>

      {/* Fixed bottom navigation bar */}
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

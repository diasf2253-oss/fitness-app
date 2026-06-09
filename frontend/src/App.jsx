import React from 'react'
import { Routes, Route, NavLink } from 'react-router-dom'
import Dashboard from './pages/Dashboard'
import Workout from './pages/Workout'
import Routines from './pages/Routines'
import History from './pages/History'
import Settings from './pages/Settings'

// Bottom navigation items
const NAV_ITEMS = [
  { to: '/',        label: 'Home',     icon: '🏠' },
  { to: '/workout', label: 'Workout',  icon: '💪' },
  { to: '/routines',label: 'Routines', icon: '📋' },
  { to: '/history', label: 'History',  icon: '📈' },
  { to: '/settings',label: 'Settings', icon: '⚙️' },
]

export default function App() {
  return (
    <>
      <div className="main-content">
        <Routes>
          <Route path="/"         element={<Dashboard />} />
          <Route path="/workout"  element={<Workout />} />
          <Route path="/routines" element={<Routines />} />
          <Route path="/history"  element={<History />} />
          <Route path="/settings" element={<Settings />} />
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
            <span className="nav-icon">{icon}</span>
            {label}
          </NavLink>
        ))}
      </nav>
    </>
  )
}

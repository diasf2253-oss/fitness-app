import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'
import { setToken } from './api'
import { isLocalFirst } from './local/mode'
import { syncNow } from './local/sync'

// Link-based onboarding: opening `…/?token=XYZ` (e.g. by scanning the
// "Add a device" QR) logs this device in, then strips the token from the
// URL so it isn't left in the address bar or history.
;(function adoptTokenFromUrl() {
  const params = new URLSearchParams(window.location.search)
  const token = params.get('token')
  if (token) {
    setToken(token)
    params.delete('token')
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

// Sync on open (local-first mode): if the laptop answers on this network,
// exchange changes; if not, carry on fully local. Never blocks the UI.
if (isLocalFirst()) {
  syncNow()
    .then(r => {
      if (r.reachable) console.info(`[sync] pushed ${r.pushed}, pulled ${r.pulled}`)
      else console.info('[sync] laptop not reachable — staying local')
    })
    .catch(err => console.warn('[sync] failed:', err))
}

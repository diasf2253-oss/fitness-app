import React from 'react'
import ReactDOM from 'react-dom/client'
import { BrowserRouter } from 'react-router-dom'
import App from './App'
import './index.css'
import { setToken } from './api'

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

// Register the minimal service worker (no caching) — required for the
// PWA install prompt on Android; harmless in dev.
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/sw.js').catch(() => {})
  })
}

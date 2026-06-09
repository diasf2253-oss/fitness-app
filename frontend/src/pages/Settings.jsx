/**
 * Settings page — Phase 0: shows token config.
 * Phase 2+: edit nutrition targets, unit system, trigger YAZIO sync.
 */
import React, { useState } from 'react'
import { setToken } from '../api'

export default function Settings() {
  const [token, setTokenState] = useState(localStorage.getItem('app_token') || 'changeme')
  const [saved, setSaved] = useState(false)

  function handleSave(e) {
    e.preventDefault()
    setToken(token)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  return (
    <div className="page">
      <h1>Settings</h1>

      <div className="card">
        <h2>API Token</h2>
        <p className="muted" style={{ marginBottom: '0.75rem' }}>
          Must match the APP_TOKEN value in your backend <code>.env</code> file.
        </p>
        <form onSubmit={handleSave} className="col">
          <div className="form-group">
            <label htmlFor="token-input">Bearer Token</label>
            <input
              id="token-input"
              type="password"
              value={token}
              onChange={e => setTokenState(e.target.value)}
              placeholder="changeme"
            />
          </div>
          <button type="submit">{saved ? '✓ Saved' : 'Save Token'}</button>
        </form>
      </div>

      <div className="card">
        <p className="muted" style={{ textAlign: 'center', padding: '0.5rem 0' }}>
          Nutrition targets, unit system, and YAZIO sync status coming in Phase 2.
        </p>
      </div>
    </div>
  )
}

/**
 * Settings page.
 * - API token config
 * - Health data: link to the manual Log page; Apple Health sync lands in
 *   Phase 3 (YAZIO feeds Apple Health, so no separate nutrition sync).
 * - Developer utilities: load/clear ~30 days of sample health data to
 *   preview the dashboard before real data exists.
 */
import React, { useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch, setToken } from '../api'

export default function Settings() {
  const [token, setTokenState] = useState(localStorage.getItem('app_token') || 'changeme')
  const [saved, setSaved] = useState(false)
  const [sampleBusy, setSampleBusy] = useState(false)
  const [sampleMsg, setSampleMsg] = useState(null)

  function handleSave(e) {
    e.preventDefault()
    setToken(token)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  async function loadSample() {
    setSampleBusy(true)
    setSampleMsg(null)
    try {
      const r = await apiFetch('/api/dev/seed-sample-health', { method: 'POST' })
      setSampleMsg(`Loaded ${r.days_seeded} days of sample data (${r.from} → ${r.to}).`)
    } catch (err) {
      setSampleMsg(`Error: ${err.message}`)
    } finally {
      setSampleBusy(false)
    }
  }

  async function clearSample() {
    setSampleBusy(true)
    setSampleMsg(null)
    try {
      const r = await apiFetch('/api/dev/seed-sample-health', { method: 'DELETE' })
      setSampleMsg(`Removed ${r.rows_deleted} sample rows. Manual and synced data untouched.`)
    } catch (err) {
      setSampleMsg(`Error: ${err.message}`)
    } finally {
      setSampleBusy(false)
    }
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
        <h2>Health data</h2>
        <p className="muted">
          Weight, steps, sleep and nutrition will sync automatically from
          Apple Health in Phase 3 — YAZIO already writes into it. Until then,
          add or correct days by hand.
        </p>
        <Link to="/log">
          <button className="secondary" style={{ width: '100%', marginTop: '0.75rem' }}>
            Open manual log
          </button>
        </Link>
      </div>

      <div className="card">
        <h3>Developer</h3>
        <p className="muted" style={{ marginBottom: '0.75rem' }}>
          Sample data fills the dashboard with ~30 days of plausible numbers
          (tagged <code>source: sample</code>) so you can preview it before real
          data exists. Clearing removes only those rows.
        </p>
        <div className="row">
          <button className="secondary" onClick={loadSample} disabled={sampleBusy} style={{ flex: 1 }}>
            Load sample data
          </button>
          <button className="danger" onClick={clearSample} disabled={sampleBusy} style={{ flex: 1 }}>
            Clear sample data
          </button>
        </div>
        {sampleMsg && (
          <p className="muted" style={{ marginTop: '0.6rem', fontSize: '0.8rem' }}>{sampleMsg}</p>
        )}
      </div>
    </div>
  )
}

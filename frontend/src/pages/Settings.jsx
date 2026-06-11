/**
 * Settings page.
 * - API token config
 * - Apple Health sync: last-sync status, Health Auto Export setup steps,
 *   and the one-time export.zip history backfill upload
 * - Manual log link
 * - Developer utilities: load/clear sample health data
 */
import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch, apiUpload, setToken } from '../api'

const TRACKER_KINDS = [
  { value: 'habit', label: 'Habit — done / not done, with streaks' },
  { value: 'number', label: 'Number — any metric with a unit' },
  { value: 'scale', label: 'Scale — rate 1 to 5' },
  { value: 'text', label: 'Text — a journal-style note' },
]

/**
 * Manage the generic trackers that power the daily check-in.
 * Archive keeps history but removes the tracker from the check-in;
 * delete removes everything.
 */
function TrackersCard() {
  const [trackers, setTrackers] = useState([])
  const [name, setName] = useState('')
  const [kind, setKind] = useState('habit')
  const [unit, setUnit] = useState('')
  const [error, setError] = useState(null)

  const load = useCallback(() => {
    apiFetch('/api/trackers?include_archived=true')
      .then(setTrackers)
      .catch(err => setError(err.message))
  }, [])

  useEffect(load, [load])

  async function add(e) {
    e.preventDefault()
    setError(null)
    try {
      await apiFetch('/api/trackers', {
        method: 'POST',
        body: JSON.stringify({
          name: name.trim(),
          kind,
          unit: kind === 'number' && unit.trim() ? unit.trim() : null,
        }),
      })
      setName('')
      setUnit('')
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  async function toggleArchive(t) {
    try {
      await apiFetch(`/api/trackers/${t.id}`, {
        method: 'PATCH',
        body: JSON.stringify({ is_archived: !t.is_archived }),
      })
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  async function remove(t) {
    if (!confirm(`Delete "${t.name}" and all of its history?`)) return
    try {
      await apiFetch(`/api/trackers/${t.id}`, { method: 'DELETE' })
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="card">
      <h2>Trackers</h2>
      <p className="muted" style={{ marginBottom: '0.75rem' }}>
        Anything worth tracking gets a tracker — habits, a 1–5 mood, numbers
        like reading minutes, or a daily journal line. They appear in the
        dashboard check-in and on the calendar.
      </p>

      {error && <p className="muted" style={{ color: 'var(--color-danger)' }}>{error}</p>}

      <div className="col" style={{ gap: '0.4rem', marginBottom: '0.9rem' }}>
        {trackers.map(t => (
          <div key={t.id} className="row" style={{ opacity: t.is_archived ? 0.5 : 1 }}>
            <span style={{ flex: 1, fontSize: '0.9rem' }}>
              {t.name}
              {t.unit && <span className="muted" style={{ fontSize: '0.75rem' }}> · {t.unit}</span>}
            </span>
            <span className="badge">{t.kind}</span>
            <button
              className="secondary"
              style={{ minWidth: 76, padding: '0.3rem 0.6rem', minHeight: 36, fontSize: '0.75rem' }}
              onClick={() => toggleArchive(t)}
            >
              {t.is_archived ? 'Restore' : 'Archive'}
            </button>
            <button
              className="danger"
              style={{ minWidth: 40, padding: '0.3rem 0.5rem', minHeight: 36 }}
              onClick={() => remove(t)}
              title="Delete tracker and history"
            >
              ✕
            </button>
          </div>
        ))}
        {trackers.length === 0 && <p className="muted">No trackers yet.</p>}
      </div>

      <form onSubmit={add} className="col">
        <div className="form-row">
          <div className="form-group" style={{ margin: 0 }}>
            <label>Name</label>
            <input value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Meditate" />
          </div>
          <div className="form-group" style={{ margin: 0 }}>
            <label>Type</label>
            <select value={kind} onChange={e => setKind(e.target.value)}>
              {TRACKER_KINDS.map(k => <option key={k.value} value={k.value}>{k.label}</option>)}
            </select>
          </div>
        </div>
        {kind === 'number' && (
          <div className="form-group" style={{ margin: 0 }}>
            <label>Unit (optional)</label>
            <input value={unit} onChange={e => setUnit(e.target.value)} placeholder="e.g. min, pages, mg" />
          </div>
        )}
        <button type="submit" disabled={!name.trim()}>Add tracker</button>
      </form>
    </div>
  )
}

function fmtTimestamp(iso) {
  if (!iso) return null
  // Backend stores naive UTC — mark it so the browser converts to local
  return new Date(iso + 'Z').toLocaleString(undefined, {
    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
  })
}

export default function Settings() {
  const [token, setTokenState] = useState(localStorage.getItem('app_token') || 'changeme')
  const [saved, setSaved] = useState(false)

  const [lastIngest, setLastIngest] = useState(null)
  const [importFile, setImportFile] = useState(null)
  const [importBusy, setImportBusy] = useState(false)
  const [importMsg, setImportMsg] = useState(null)
  const fileRef = useRef(null)

  const [sampleBusy, setSampleBusy] = useState(false)
  const [sampleMsg, setSampleMsg] = useState(null)

  useEffect(() => {
    apiFetch('/api/settings')
      .then(s => setLastIngest(s.health_last_ingest))
      .catch(() => {})  // non-critical; card just shows "never"
  }, [])

  function handleSave(e) {
    e.preventDefault()
    setToken(token)
    setSaved(true)
    setTimeout(() => setSaved(false), 2000)
  }

  async function runImport() {
    if (!importFile) return
    setImportBusy(true)
    setImportMsg(null)
    try {
      const form = new FormData()
      form.append('file', importFile)
      const r = await apiUpload('/api/ingest/health-export', form)
      if (r.status === 'ok') {
        const d = r.days
        setImportMsg(
          `Imported ${r.date_range.from ?? '—'} → ${r.date_range.to ?? '—'}: ` +
          `${d.weight} weight, ${d.steps} step, ${d.sleep} sleep, ${d.nutrition} nutrition days ` +
          `(${r.rows_created} new rows).`
        )
        const s = await apiFetch('/api/settings')
        setLastIngest(s.health_last_ingest)
      } else {
        setImportMsg(`Error: ${r.detail || 'import failed'}`)
      }
      setImportFile(null)
      if (fileRef.current) fileRef.current.value = ''
    } catch (err) {
      setImportMsg(`Error: ${err.message}`)
    } finally {
      setImportBusy(false)
    }
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
        <div className="row" style={{ marginBottom: '0.5rem' }}>
          <h2 style={{ margin: 0, flex: 1 }}>Apple Health sync</h2>
          <span className={`badge${lastIngest ? ' success' : ''}`}>
            {lastIngest ? `synced ${fmtTimestamp(lastIngest)}` : 'never synced'}
          </span>
        </div>
        <p className="muted">
          Everything — weight, steps, sleep, and nutrition down to
          micronutrients (YAZIO writes into Apple Health) — syncs from your
          phone. Set up the <strong>Health Auto Export</strong> app once:
        </p>
        <ol className="muted" style={{ fontSize: '0.85rem', paddingLeft: '1.25rem', margin: '0.6rem 0' }}>
          <li>Automations → new automation, format <strong>JSON</strong></li>
          <li>URL: <code>{window.location.origin}/api/ingest/health</code> (use your tunnel URL from the phone)</li>
          <li>Header: <code>Authorization: Bearer &lt;your token&gt;</code></li>
          <li>Select metrics: steps, weight, sleep, plus the dietary ones</li>
          <li>Schedule it daily</li>
        </ol>

        <hr />

        <h3>History backfill</h3>
        <p className="muted" style={{ marginBottom: '0.6rem' }}>
          Import your full history once: Health app → profile picture →
          “Export All Health Data”, then upload the <code>export.zip</code> here.
          Days you corrected manually are never overwritten.
        </p>
        <input
          ref={fileRef}
          type="file"
          accept=".zip,.xml"
          style={{ display: 'none' }}
          onChange={e => setImportFile(e.target.files?.[0] || null)}
        />
        <div className="row">
          <button className="secondary" style={{ flex: 1 }} onClick={() => fileRef.current?.click()}>
            {importFile ? importFile.name : 'Choose export.zip'}
          </button>
          <button onClick={runImport} disabled={!importFile || importBusy} style={{ minWidth: 110 }}>
            {importBusy ? 'Importing…' : 'Import'}
          </button>
        </div>
        {importBusy && (
          <p className="muted" style={{ marginTop: '0.5rem', fontSize: '0.8rem' }}>
            Large exports can take a minute — leave this page open.
          </p>
        )}
        {importMsg && (
          <p className="muted" style={{ marginTop: '0.6rem', fontSize: '0.8rem' }}>{importMsg}</p>
        )}
      </div>

      <TrackersCard />

      <div className="card">
        <h2>Manual log</h2>
        <p className="muted">
          Add or correct individual days by hand — manual entries always win
          over synced data.
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

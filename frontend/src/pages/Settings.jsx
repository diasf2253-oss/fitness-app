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
import { apiFetch, apiUpload } from '../api'
import { useAuth } from '../auth'
import { isMuted, setMuted, subscribeMuted, playTap } from '../audio'

// Copy-paste starter body for the iOS Shortcut push (see the Apple Health
// sync card + docs/HEALTH_INGEST_SHORTCUT.md). Swap the dates for today.
const SHORTCUT_JSON_TEMPLATE = `{
  "weight": [{ "date": "2026-07-18", "kg": 82.4 }],
  "steps":  [{ "date": "2026-07-18", "count": 11205 }],
  "sleep":  [{ "date": "2026-07-18", "asleep_minutes": 427, "in_bed_minutes": 465 }]
}`

/**
 * Sound on/off. The switch reads "Sound effects" (checked = audible), which is
 * friendlier than a "Mute" negative. State lives in the audio service (backed
 * by localStorage), so it persists across sessions and any other surface that
 * reads it stays in sync via subscribeMuted.
 */
function SoundCard() {
  const [soundOn, setSoundOn] = useState(!isMuted())

  // Reflect changes made elsewhere (defensive; today only this toggles it).
  useEffect(() => subscribeMuted(m => setSoundOn(!m)), [])

  function toggle() {
    const next = !soundOn
    setSoundOn(next)
    setMuted(!next)
    if (next) playTap()  // brief confirmation that sound is back on
  }

  return (
    <div className="card">
      <div className="row" style={{ alignItems: 'center', gap: '0.75rem' }}>
        <div style={{ flex: 1 }}>
          <h2 style={{ margin: 0 }}>Sound effects</h2>
          <p className="muted" style={{ margin: '0.35rem 0 0', fontSize: '0.85rem' }}>
            Subtle cues on taps, finishing a workout, and ranking up.
          </p>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={soundOn}
          aria-label="Sound effects"
          className="switch"
          onClick={toggle}
        />
      </div>
    </div>
  )
}

/**
 * A small "tap to copy" button. Shows a brief ✓ after copying.
 */
function CopyButton({ text, label = 'Copy' }) {
  const [done, setDone] = useState(false)
  return (
    <button
      type="button"
      className="secondary"
      style={{ minWidth: 70, padding: '0.3rem 0.7rem', minHeight: 36, fontSize: '0.78rem' }}
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text)
          setDone(true)
          setTimeout(() => setDone(false), 1500)
        } catch (_) { /* clipboard blocked (insecure origin) — ignore */ }
      }}
    >
      {done ? '✓ Copied' : label}
    </button>
  )
}

/**
 * Account — who's logged in, and the log-out button. Each device now logs
 * in independently (that's what accounts are for), replacing the old
 * shared-token "Add a device" QR flow.
 */
function AccountCard() {
  const { user, logout } = useAuth()
  const [busy, setBusy] = useState(false)

  return (
    <div className="card">
      <h2>Account</h2>
      <p className="muted" style={{ marginBottom: '0.85rem' }}>
        {user.name} · {user.email}
      </p>
      <button
        className="secondary"
        style={{ width: '100%' }}
        disabled={busy}
        onClick={async () => { setBusy(true); await logout() }}
      >
        {busy ? 'Logging out…' : 'Log out'}
      </button>
    </div>
  )
}

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

/** Profile — sex + age drive the Ranks references and the RDA targets. */
function ProfileCard() {
  const [sex, setSex] = useState(null)
  const [age, setAge] = useState(null)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    apiFetch('/api/settings')
      .then(s => { setSex(s.sex || 'male'); setAge(s.age ?? 19) })
      .catch(e => setError(e.message))
  }, [])

  async function save() {
    setError(null)
    try {
      await apiFetch('/api/settings', {
        method: 'PUT', body: JSON.stringify({ sex, age: Number(age) }),
      })
      setSaved(true); setTimeout(() => setSaved(false), 1800)
    } catch (e) { setError(e.message) }
  }

  if (sex == null) return null
  return (
    <div className="card">
      <h2>Profile</h2>
      <p className="muted" style={{ marginBottom: '0.75rem' }}>
        Used to scale the Ranks strength references and the micronutrient targets on the Diet tab.
      </p>
      {error && <p className="muted" style={{ color: 'var(--color-danger)' }}>{error}</p>}
      <div className="row" style={{ alignItems: 'center', gap: '0.5rem' }}>
        <label style={{ flex: 1 }}>Sex</label>
        <select value={sex} onChange={e => setSex(e.target.value)} style={{ width: 120 }}>
          <option value="male">Male</option>
          <option value="female">Female</option>
        </select>
      </div>
      <div className="row" style={{ alignItems: 'center', gap: '0.5rem', marginTop: '0.5rem' }}>
        <label style={{ flex: 1 }}>Age</label>
        <input type="number" inputMode="numeric" min="10" max="100" value={age} onChange={e => setAge(e.target.value)} style={{ width: 80 }} />
        <button onClick={save} style={{ minWidth: 90 }}>{saved ? '✓ Saved' : 'Save'}</button>
      </div>
    </div>
  )
}

/** Default rest-timer countdown after each set. */
function RestTimerSettingsCard() {
  const [mins, setMins] = useState(null)
  const [secs, setSecs] = useState(null)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    apiFetch('/api/settings')
      .then(s => { const t = s.default_rest_seconds ?? 120; setMins(Math.floor(t / 60)); setSecs(t % 60) })
      .catch(e => setError(e.message))
  }, [])

  async function save() {
    setError(null)
    const total = Math.max(5, (Number(mins) || 0) * 60 + (Number(secs) || 0))
    try {
      await apiFetch('/api/settings', { method: 'PUT', body: JSON.stringify({ default_rest_seconds: total }) })
      setSaved(true); setTimeout(() => setSaved(false), 1800)
    } catch (e) { setError(e.message) }
  }

  if (mins == null) return null
  return (
    <div className="card">
      <h2>Rest timer</h2>
      <p className="muted" style={{ marginBottom: '0.75rem' }}>
        Default countdown after each set. Routines with their own rest time use that instead;
        during a set you can still adjust or pause it.
      </p>
      {error && <p className="muted" style={{ color: 'var(--color-danger)' }}>{error}</p>}
      <div className="row" style={{ alignItems: 'center', gap: '0.4rem' }}>
        <label style={{ flex: 1 }}>Default rest</label>
        <input type="number" inputMode="numeric" min="0" max="20" value={mins} onChange={e => setMins(e.target.value)}
          aria-label="Minutes" style={{ width: 64 }} />
        <span className="muted">min</span>
        <input type="number" inputMode="numeric" min="0" max="59" value={secs} onChange={e => setSecs(e.target.value)}
          aria-label="Seconds" style={{ width: 64 }} />
        <span className="muted">sec</span>
        <button onClick={save} style={{ minWidth: 90 }}>{saved ? '✓ Saved' : 'Save'}</button>
      </div>
    </div>
  )
}

/** Allowed rest days between workouts before the training streak breaks. */
function StreakSettingsCard() {
  const [gap, setGap] = useState(null)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState(null)

  useEffect(() => {
    apiFetch('/api/settings').then(s => setGap(s.streak_rest_gap)).catch(e => setError(e.message))
  }, [])

  async function save() {
    setError(null)
    try {
      await apiFetch('/api/settings', { method: 'PUT', body: JSON.stringify({ streak_rest_gap: Number(gap) }) })
      setSaved(true); setTimeout(() => setSaved(false), 1800)
    } catch (e) { setError(e.message) }
  }

  if (gap == null) return null
  return (
    <div className="card">
      <h2>Training streak</h2>
      <p className="muted" style={{ marginBottom: '0.75rem' }}>
        How many rest days are allowed between workouts before the streak breaks (default 1 — a normal rest day is fine).
      </p>
      {error && <p className="muted" style={{ color: 'var(--color-danger)' }}>{error}</p>}
      <div className="row" style={{ alignItems: 'center', gap: '0.5rem' }}>
        <label style={{ flex: 1 }}>Allowed rest days</label>
        <input type="number" inputMode="numeric" min="0" max="7" value={gap} onChange={e => setGap(e.target.value)} style={{ width: 80 }} />
        <button onClick={save} style={{ minWidth: 90 }}>{saved ? '✓ Saved' : 'Save'}</button>
      </div>
    </div>
  )
}

/** Edit the weekly working-set target ranges per muscle group. Both the
 * sets-per-week view and the workout generator read this single table. */
function VolumeTargetsCard() {
  const [targets, setTargets] = useState(null)   // {muscle: {low, high}}
  const [error, setError] = useState(null)
  const [saved, setSaved] = useState(false)
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => {
    apiFetch('/api/stats/volume-targets').then(setTargets).catch(e => setError(e.message))
  }, [])
  useEffect(load, [load])

  function setField(m, key, value) {
    setTargets(t => ({ ...t, [m]: { ...t[m], [key]: value } }))
  }

  async function save() {
    setBusy(true); setError(null)
    try {
      const payload = {}
      for (const [m, { low, high }] of Object.entries(targets)) payload[m] = [Number(low), Number(high)]
      await apiFetch('/api/settings', { method: 'PUT', body: JSON.stringify({ volume_targets: payload }) })
      setSaved(true); setTimeout(() => setSaved(false), 1800)
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  async function resetDefaults() {
    setBusy(true); setError(null)
    try {
      await apiFetch('/api/settings', { method: 'PUT', body: JSON.stringify({ volume_targets: null }) })
      load()
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  if (!targets) return null
  return (
    <div className="card">
      <h2>Weekly volume targets</h2>
      <p className="muted" style={{ marginBottom: '0.75rem' }}>
        Working sets per muscle per week. The sets-per-week view and the workout generator both read these ranges.
      </p>
      {error && <p className="muted" style={{ color: 'var(--color-danger)' }}>{error}</p>}
      <div className="col" style={{ gap: '0.4rem' }}>
        {Object.entries(targets).map(([m, { low, high }]) => (
          <div key={m} className="row" style={{ alignItems: 'center', gap: '0.5rem' }}>
            <span style={{ flex: 1, fontSize: '0.88rem' }}>{m}</span>
            <input type="number" inputMode="numeric" min="0" value={low} onChange={e => setField(m, 'low', e.target.value)}
              aria-label={`${m} minimum sets`} style={{ width: 66 }} />
            <span className="muted">–</span>
            <input type="number" inputMode="numeric" min="0" value={high} onChange={e => setField(m, 'high', e.target.value)}
              aria-label={`${m} maximum sets`} style={{ width: 66 }} />
          </div>
        ))}
      </div>
      <div className="row" style={{ marginTop: '0.85rem', gap: '0.5rem' }}>
        <button onClick={save} disabled={busy} style={{ flex: 1 }}>{saved ? '✓ Saved' : 'Save targets'}</button>
        <button className="secondary" onClick={resetDefaults} disabled={busy}>Reset to defaults</button>
      </div>
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
  const { user } = useAuth()
  const ingestToken = user.ingest_token

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

      <AccountCard />

      <SoundCard />

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
          <li style={{ marginTop: '0.4rem' }}>
            <div className="row" style={{ gap: '0.5rem' }}>
              <span style={{ flex: 1 }}>URL: <code style={{ fontSize: '0.72rem' }}>{window.location.origin}/api/ingest/health</code></span>
              <CopyButton text={`${window.location.origin}/api/ingest/health`} />
            </div>
          </li>
          <li style={{ marginTop: '0.4rem' }}>
            <div className="row" style={{ gap: '0.5rem' }}>
              <span style={{ flex: 1 }}>Header: <code style={{ fontSize: '0.72rem' }}>Authorization: Bearer {ingestToken}</code></span>
              <CopyButton text={`Bearer ${ingestToken}`} />
            </div>
          </li>
          <li style={{ marginTop: '0.4rem' }}>Select metrics: steps, weight, sleep, plus the dietary ones</li>
          <li>Schedule it daily</li>
        </ol>

        <hr />

        <h3>iOS Shortcut push</h3>
        <p className="muted" style={{ marginBottom: '0.6rem' }}>
          More reliable than Health Auto Export's background pushes: an iOS
          Shortcut automation posts weight, steps, and sleep straight here on
          the phone's own schedule. Same validated pipeline, so manual
          corrections still win. Full recipe in{' '}
          <code style={{ fontSize: '0.72rem' }}>docs/HEALTH_INGEST_SHORTCUT.md</code>.
        </p>
        <div className="row" style={{ gap: '0.5rem', marginBottom: '0.4rem' }}>
          <span style={{ flex: 1 }}>POST: <code style={{ fontSize: '0.72rem' }}>{window.location.origin}/api/ingest/health/shortcut</code></span>
          <CopyButton text={`${window.location.origin}/api/ingest/health/shortcut`} />
        </div>
        <div className="row" style={{ gap: '0.5rem', marginBottom: '0.4rem' }}>
          <span style={{ flex: 1 }}>Header: <code style={{ fontSize: '0.72rem' }}>Authorization: Bearer {ingestToken}</code></span>
          <CopyButton text={`Bearer ${ingestToken}`} />
        </div>
        <div className="row" style={{ gap: '0.5rem', alignItems: 'flex-start' }}>
          <pre style={{
            flex: 1, margin: 0, padding: '0.5rem', borderRadius: 6,
            background: 'var(--surface-2, rgba(127,127,127,0.12))',
            fontSize: '0.68rem', overflowX: 'auto', whiteSpace: 'pre',
          }}>{SHORTCUT_JSON_TEMPLATE}</pre>
          <CopyButton text={SHORTCUT_JSON_TEMPLATE} label="Copy JSON" />
        </div>

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

      <ProfileCard />
      <RestTimerSettingsCard />
      <StreakSettingsCard />
      <VolumeTargetsCard />

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

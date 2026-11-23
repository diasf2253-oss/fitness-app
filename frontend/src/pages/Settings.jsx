/**
 * Settings page — iOS-style grouped lists.
 *
 * Every group is a small title ABOVE a rounded card; the card holds the rows
 * (label left, control right, hairline dividers). Groups, top to bottom:
 *   Account      name, email, password, log out
 *   Profile      sex, age, height (scale the Ranks references + RDA targets)
 *   Preferences  sound, default rest timer, streak rest days
 *   Training     weekly volume targets
 *   Trackers     the generic daily trackers
 *   Data         manual log
 *
 * Simple fields save themselves when you leave them (blur / change) — there is
 * no per-card Save button. Password change is the one explicit form.
 *
 * The Apple Health setup (Shortcut link, ingest token, export.zip backfill)
 * used to live here; it was removed from this page on purpose. The backend
 * ingest endpoints are untouched.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { apiFetch } from '../lib/api'
import { friendlyAuthError, useAuth } from '../auth/auth'
import { supabase } from '../lib/supabase'
import { isMuted, setMuted, subscribeMuted, playTap } from '../lib/audio'
import { confirmAction } from '../components/ui/ConfirmSheet'

/* ------------------------------------------------------------------ */
/* Building blocks                                                     */
/* ------------------------------------------------------------------ */

/** Title above, rounded card below, optional footnote under the card. */
function Section({ title, footer, aside, children }) {
  return (
    <section className="set-section">
      <div className="set-head">
        <h2 className="set-title">{title}</h2>
        {aside}
      </div>
      <div className="set-card">{children}</div>
      {footer && <p className="set-footer">{footer}</p>}
    </section>
  )
}

/** One row: label (+ optional hint) on the left, control on the right. */
function Row({ label, hint, children, htmlFor }) {
  return (
    <div className="set-row">
      <div className="set-row-text">
        <label htmlFor={htmlFor} className="set-row-label">{label}</label>
        {hint && <span className="set-row-hint">{hint}</span>}
      </div>
      <div className="set-row-control">{children}</div>
    </div>
  )
}

const Chevron = () => (
  <svg width="8" height="14" viewBox="0 0 8 14" aria-hidden="true" className="set-chevron">
    <path d="M1 1l6 6-6 6" fill="none" stroke="currentColor" strokeWidth="1.8"
      strokeLinecap="round" strokeLinejoin="round" />
  </svg>
)

/** Small "Saved" confirmation that fades next to a section title. */
function SavedTick({ show }) {
  return <span className={`set-saved${show ? ' on' : ''}`} aria-live="polite">{show ? '✓ Saved' : ''}</span>
}

/** Load /api/settings once and save one field at a time. */
function useSettings() {
  const [s, setS] = useState(null)
  const [error, setError] = useState(null)
  const [savedAt, setSavedAt] = useState(0)

  useEffect(() => {
    apiFetch('/api/settings').then(setS).catch(e => setError(e.message))
  }, [])

  const save = useCallback(async (patch) => {
    setError(null)
    try {
      const next = await apiFetch('/api/settings', { method: 'PUT', body: JSON.stringify(patch) })
      setS(next)
      setSavedAt(Date.now())
      return true
    } catch (e) {
      setError(e.message)
      return false
    }
  }, [])

  return { s, save, error, savedAt }
}

/** True for ~1.8s after `stamp` changes — drives the "✓ Saved" tick. */
function useFlash(stamp) {
  const [on, setOn] = useState(false)
  useEffect(() => {
    if (!stamp) return
    setOn(true)
    const t = setTimeout(() => setOn(false), 1800)
    return () => clearTimeout(t)
  }, [stamp])
  return on
}

/* ------------------------------------------------------------------ */
/* Account                                                             */
/* ------------------------------------------------------------------ */

/* Password changes go straight to Supabase (the login service) — there's
   no app endpoint. Works for Google sign-ins too: it adds a password they
   can use alongside the Google button. */
function PasswordRows() {
  const [open, setOpen] = useState(false)
  const [next, setNext] = useState('')
  const [confirmPw, setConfirmPw] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [done, setDone] = useState(false)

  function reset() { setNext(''); setConfirmPw(''); setError(null) }

  async function submit(e) {
    e.preventDefault()
    setError(null)
    if (next.length < 8) return setError('New password must be at least 8 characters.')
    if (next !== confirmPw) return setError('The new passwords do not match.')
    setBusy(true)
    try {
      const { error: err } = await supabase.auth.updateUser({ password: next })
      if (err) return setError(friendlyAuthError(err))
      // Like before: changing the password signs out your other devices.
      await supabase.auth.signOut({ scope: 'others' }).catch(() => {})
      reset(); setOpen(false); setDone(true)
      setTimeout(() => setDone(false), 3000)
    } finally {
      setBusy(false)
    }
  }

  return (
    <>
      <button type="button" className="set-row set-row-button" aria-expanded={open}
        onClick={() => { setOpen(o => !o); setDone(false) }}>
        <span className="set-row-label">Password</span>
        <span className="set-row-control muted">
          {done ? '✓ Updated' : 'Change'}
          <Chevron />
        </span>
      </button>
      {open && (
        <form onSubmit={submit} className="set-expand">
          <Row label="New" htmlFor="pw-new">
            <input id="pw-new" className="set-input" type="password" autoComplete="new-password"
              value={next} onChange={e => setNext(e.target.value)} required minLength={8} placeholder="8+ characters" />
          </Row>
          <Row label="Confirm" htmlFor="pw-confirm">
            <input id="pw-confirm" className="set-input" type="password" autoComplete="new-password"
              value={confirmPw} onChange={e => setConfirmPw(e.target.value)} required placeholder="Repeat it" />
          </Row>
          {error && <p className="set-error" role="alert">{error}</p>}
          <div className="set-pad">
            <button type="submit" disabled={busy || !next || !confirmPw} style={{ width: '100%' }}>
              {busy ? 'Updating…' : 'Update password'}
            </button>
            <p className="muted" style={{ fontSize: '0.78rem', marginTop: '0.6rem' }}>
              Your other signed-in devices will be logged out.
            </p>
          </div>
        </form>
      )}
    </>
  )
}

function AccountSection() {
  const { user, refresh, logout } = useAuth()
  const [name, setName] = useState(user.name)
  const [error, setError] = useState(null)
  const [stamp, setStamp] = useState(0)
  const [busy, setBusy] = useState(false)
  const flash = useFlash(stamp)

  async function saveName() {
    const trimmed = name.trim()
    if (!trimmed) { setName(user.name); return }
    if (trimmed === user.name) { setName(trimmed); return }
    setError(null)
    try {
      await apiFetch('/api/auth/me', { method: 'PATCH', body: JSON.stringify({ name: trimmed }) })
      await refresh()
      setName(trimmed)
      setStamp(Date.now())
    } catch (e) {
      setError(e.message)
      setName(user.name)
    }
  }

  return (
    <Section title="Account" aside={<SavedTick show={flash} />}>
      <Row label="Name" htmlFor="acc-name">
        <input id="acc-name" className="set-input" value={name} maxLength={200}
          autoComplete="name" onChange={e => setName(e.target.value)} onBlur={saveName}
          onKeyDown={e => { if (e.key === 'Enter') e.currentTarget.blur() }} />
      </Row>
      <Row label="Email">
        <span className="set-value">{user.email}</span>
      </Row>
      <PasswordRows />
      {error && <p className="set-error" role="alert">{error}</p>}
      <button type="button" className="set-row set-row-button set-row-danger" disabled={busy}
        onClick={async () => { setBusy(true); await logout() }}>
        <span className="set-row-label">{busy ? 'Logging out…' : 'Log out'}</span>
      </button>
    </Section>
  )
}

/* ------------------------------------------------------------------ */
/* Profile                                                             */
/* ------------------------------------------------------------------ */

function ProfileSection({ s, save, savedAt }) {
  const [age, setAge] = useState(String(s.age ?? ''))
  const [height, setHeight] = useState(s.height_cm == null ? '' : String(s.height_cm))
  const flash = useFlash(savedAt)

  const commitAge = () => {
    const n = Number(age)
    if (!Number.isFinite(n) || n < 10 || n > 100) { setAge(String(s.age ?? '')); return }
    if (n !== s.age) save({ age: Math.round(n) })
  }
  const commitHeight = () => {
    if (height.trim() === '') return
    const n = Number(height.replace(',', '.'))
    if (!Number.isFinite(n) || n < 100 || n > 250) { setHeight(s.height_cm == null ? '' : String(s.height_cm)); return }
    if (n !== s.height_cm) save({ height_cm: n })
  }

  return (
    <Section title="Profile" aside={<SavedTick show={flash} />}
      footer="Used to scale the Ranks strength references and the micronutrient targets on the Diet tab.">
      <Row label="Sex" htmlFor="pf-sex">
        <select id="pf-sex" className="set-input set-select" value={s.sex || 'male'}
          onChange={e => save({ sex: e.target.value })}>
          <option value="male">Male</option>
          <option value="female">Female</option>
        </select>
      </Row>
      <Row label="Age" htmlFor="pf-age">
        <input id="pf-age" className="set-input set-narrow" type="number" inputMode="numeric"
          min="10" max="100" value={age} onChange={e => setAge(e.target.value)} onBlur={commitAge} />
      </Row>
      <Row label="Height" htmlFor="pf-height">
        <input id="pf-height" className="set-input set-narrow" type="text" inputMode="decimal"
          placeholder="—" value={height} onChange={e => setHeight(e.target.value)} onBlur={commitHeight}
          onKeyDown={e => { if (e.key === 'Enter') e.currentTarget.blur() }} />
        <span className="set-unit">cm</span>
      </Row>
    </Section>
  )
}

/* ------------------------------------------------------------------ */
/* Preferences                                                         */
/* ------------------------------------------------------------------ */

/** Sound on/off. State lives in the audio service (localStorage-backed). */
function SoundRow() {
  const [soundOn, setSoundOn] = useState(!isMuted())
  useEffect(() => subscribeMuted(m => setSoundOn(!m)), [])

  function toggle() {
    const next = !soundOn
    setSoundOn(next)
    setMuted(!next)
    if (next) playTap() // brief confirmation that sound is back on
  }

  return (
    <Row label="Sound effects" hint="Taps, finishing a workout, ranking up" htmlFor="pref-sound">
      <button id="pref-sound" type="button" role="switch" aria-checked={soundOn}
        className="switch" onClick={toggle} />
    </Row>
  )
}

function PreferencesSection({ s, save, savedAt }) {
  const rest = s.default_rest_seconds ?? 120
  const [mins, setMins] = useState(String(Math.floor(rest / 60)))
  const [secs, setSecs] = useState(String(rest % 60))
  const [gap, setGap] = useState(String(s.streak_rest_gap ?? 1))
  const flash = useFlash(savedAt)

  const commitRest = () => {
    const total = Math.max(5, (Number(mins) || 0) * 60 + (Number(secs) || 0))
    setMins(String(Math.floor(total / 60))); setSecs(String(total % 60))
    if (total !== rest) save({ default_rest_seconds: total })
  }
  const commitGap = () => {
    const n = Math.min(7, Math.max(0, Math.round(Number(gap) || 0)))
    setGap(String(n))
    if (n !== s.streak_rest_gap) save({ streak_rest_gap: n })
  }

  return (
    <Section title="Preferences" aside={<SavedTick show={flash} />}
      footer="Routines with their own rest time use that instead of the default. The streak survives this many rest days between workouts.">
      <SoundRow />
      <Row label="Rest timer">
        <input className="set-input set-narrow" type="number" inputMode="numeric" min="0" max="20"
          aria-label="Minutes" value={mins} onChange={e => setMins(e.target.value)} onBlur={commitRest} />
        <span className="set-unit">min</span>
        <input className="set-input set-narrow" type="number" inputMode="numeric" min="0" max="59"
          aria-label="Seconds" value={secs} onChange={e => setSecs(e.target.value)} onBlur={commitRest} />
        <span className="set-unit">sec</span>
      </Row>
      <Row label="Allowed rest days" htmlFor="pref-gap">
        <input id="pref-gap" className="set-input set-narrow" type="number" inputMode="numeric" min="0" max="7"
          value={gap} onChange={e => setGap(e.target.value)} onBlur={commitGap} />
      </Row>
    </Section>
  )
}

/* ------------------------------------------------------------------ */
/* Training — weekly volume targets                                    */
/* ------------------------------------------------------------------ */

/** Weekly working-set target ranges per muscle group. The sets-per-week view
 * and the workout generator both read this single table. */
function VolumeTargetsSection() {
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
    <Section title="Weekly volume targets"
      footer="Working sets per muscle per week. The sets-per-week view and the workout generator both read these ranges.">
      {Object.entries(targets).map(([m, { low, high }]) => (
        <div key={m} className="set-row">
          <span className="set-row-label" style={{ textTransform: 'capitalize' }}>{m}</span>
          <div className="set-row-control">
            <input className="set-input set-narrow" type="number" inputMode="numeric" min="0" value={low}
              onChange={e => setField(m, 'low', e.target.value)} aria-label={`${m} minimum sets`} />
            <span className="set-unit">–</span>
            <input className="set-input set-narrow" type="number" inputMode="numeric" min="0" value={high}
              onChange={e => setField(m, 'high', e.target.value)} aria-label={`${m} maximum sets`} />
          </div>
        </div>
      ))}
      {error && <p className="set-error" role="alert">{error}</p>}
      <div className="set-pad row" style={{ gap: '0.5rem' }}>
        <button onClick={save} disabled={busy} style={{ flex: 1 }}>{saved ? '✓ Saved' : 'Save targets'}</button>
        <button className="secondary" onClick={resetDefaults} disabled={busy}>Reset</button>
      </div>
    </Section>
  )
}

/* ------------------------------------------------------------------ */
/* Trackers                                                            */
/* ------------------------------------------------------------------ */

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
function TrackersSection() {
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
    if (!(await confirmAction({
      title: `Delete "${t.name}"?`, message: 'The tracker and all of its history will be removed.',
      confirmLabel: 'Delete tracker', danger: true,
    }))) return
    try {
      await apiFetch(`/api/trackers/${t.id}`, { method: 'DELETE' })
      load()
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <Section title="Trackers"
      footer="Anything worth tracking gets a tracker — habits, a 1–5 mood, numbers like reading minutes, or a daily journal line. They appear in the dashboard check-in and on the calendar.">
      {trackers.map(t => (
        <div key={t.id} className="set-row" style={{ opacity: t.is_archived ? 0.5 : 1 }}>
          <span className="set-row-label">
            {t.name}
            {t.unit && <span className="muted" style={{ fontSize: '0.75rem' }}> · {t.unit}</span>}
          </span>
          <div className="set-row-control" style={{ gap: '0.4rem' }}>
            <span className="badge">{t.kind}</span>
            <button className="secondary" style={{ minWidth: 76, padding: '0.3rem 0.6rem', minHeight: 36, fontSize: '0.75rem' }}
              onClick={() => toggleArchive(t)}>
              {t.is_archived ? 'Restore' : 'Archive'}
            </button>
            <button className="danger" style={{ minWidth: 40, padding: '0.3rem 0.5rem', minHeight: 36 }}
              onClick={() => remove(t)} title="Delete tracker and history" aria-label={`Delete ${t.name}`}>
              ✕
            </button>
          </div>
        </div>
      ))}
      {trackers.length === 0 && <p className="set-pad muted">No trackers yet.</p>}
      {error && <p className="set-error" role="alert">{error}</p>}

      <form onSubmit={add} className="set-pad col">
        <div className="form-row">
          <div className="form-group" style={{ margin: 0 }}>
            <label htmlFor="tr-name">Name</label>
            <input id="tr-name" value={name} onChange={e => setName(e.target.value)} placeholder="e.g. Meditate" />
          </div>
          <div className="form-group" style={{ margin: 0 }}>
            <label htmlFor="tr-kind">Type</label>
            <select id="tr-kind" value={kind} onChange={e => setKind(e.target.value)}>
              {TRACKER_KINDS.map(k => <option key={k.value} value={k.value}>{k.label}</option>)}
            </select>
          </div>
        </div>
        {kind === 'number' && (
          <div className="form-group" style={{ margin: 0 }}>
            <label htmlFor="tr-unit">Unit (optional)</label>
            <input id="tr-unit" value={unit} onChange={e => setUnit(e.target.value)} placeholder="e.g. min, pages, mg" />
          </div>
        )}
        <button type="submit" disabled={!name.trim()}>Add tracker</button>
      </form>
    </Section>
  )
}

/* ------------------------------------------------------------------ */
/* Page                                                                */
/* ------------------------------------------------------------------ */

export default function Settings() {
  const { s, save, error, savedAt } = useSettings()

  return (
    <div className="page">
      <h1>Settings</h1>

      <AccountSection />

      {error && <p className="set-error" role="alert">{error}</p>}
      {s && <ProfileSection s={s} save={save} savedAt={savedAt} />}
      {s && <PreferencesSection s={s} save={save} savedAt={savedAt} />}

      <VolumeTargetsSection />
      <TrackersSection />

      <Section title="Data" footer="Add or correct individual days by hand — manual entries always win over synced data.">
        <Link to="/log" className="set-row set-row-button">
          <span className="set-row-label">Manual log</span>
          <span className="set-row-control muted"><Chevron /></span>
        </Link>
      </Section>
    </div>
  )
}

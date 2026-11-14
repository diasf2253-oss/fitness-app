/**
 * Admin panel (Phase 1-2 friends beta) — signups, invite codes and user
 * management only, no
 * per-user fitness-data drill-down. Route-guarded to role === 'admin' in
 * App.jsx; every call below is also enforced server-side regardless.
 */
import React, { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../lib/api'
import { ErrorBox } from '../components/ui/States'
import { confirmAction } from '../components/ui/ConfirmSheet'

function fmtTimestamp(iso) {
  if (!iso) return '—'
  return new Date(iso + 'Z').toLocaleString(undefined, {
    day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit',
  })
}

function PendingCard({ pending, onChange }) {
  const [busyId, setBusyId] = useState(null)
  const [error, setError] = useState(null)

  async function act(id, action) {
    setBusyId(id)
    setError(null)
    try {
      await apiFetch(`/api/admin/users/${id}/${action}`, { method: 'POST' })
      onChange()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="card">
      <h2>Pending signups</h2>
      {error && <p className="muted" style={{ color: 'var(--color-danger)' }}>{error}</p>}
      {pending.length === 0 && <p className="muted">Nothing waiting on approval.</p>}
      <div className="col" style={{ gap: '0.5rem' }}>
        {pending.map(u => (
          <div key={u.id} className="row" style={{ alignItems: 'center', gap: '0.5rem' }}>
            <div style={{ flex: 1 }}>
              <div>{u.name}</div>
              <div className="muted" style={{ fontSize: '0.8rem' }}>{u.email}</div>
            </div>
            <button
              style={{ minWidth: 84 }}
              disabled={busyId === u.id}
              onClick={() => act(u.id, 'approve')}
            >
              Approve
            </button>
            <button
              className="danger"
              style={{ minWidth: 76 }}
              disabled={busyId === u.id}
              onClick={() => act(u.id, 'reject')}
            >
              Reject
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

/** "2 of 5 used" / "2 used · no limit" — exported for tests. */
export function usageText(code) {
  return code.max_uses == null
    ? `${code.uses} used · no limit`
    : `${code.uses} of ${code.max_uses} used`
}

/** The sign-up link for a code — Join prefills the code from ?code=. */
export function inviteLink(code, origin = window.location.origin) {
  return `${origin}/join?code=${encodeURIComponent(code.code)}`
}

function InviteCodesCard({ codes, onChange }) {
  const [label, setLabel] = useState('')
  const [maxUses, setMaxUses] = useState('')
  const [busy, setBusy] = useState(false)
  const [busyId, setBusyId] = useState(null)
  const [copied, setCopied] = useState(null)   // `${id}:code` or `${id}:link`
  const [error, setError] = useState(null)

  async function create(e) {
    e.preventDefault()
    const limit = maxUses.trim() === '' ? null : Number(maxUses)
    if (limit !== null && !(Number.isInteger(limit) && limit >= 1)) {
      setError('Max uses must be a whole number, 1 or more — or leave it empty for no limit.')
      return
    }
    setBusy(true)
    setError(null)
    try {
      await apiFetch('/api/admin/invite-codes', {
        method: 'POST',
        body: JSON.stringify({ label: label.trim() || null, max_uses: limit }),
      })
      setLabel('')
      setMaxUses('')
      onChange()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  async function setActive(code, active) {
    if (!active && !(await confirmAction({
      title: 'Switch this code off?',
      message: `Nobody new can join with ${code.code}. People who already joined keep their accounts. You can switch it back on later.`,
      confirmLabel: 'Switch off',
    }))) return
    setBusyId(code.id)
    setError(null)
    try {
      await apiFetch(`/api/admin/invite-codes/${code.id}`, {
        method: 'PATCH', body: JSON.stringify({ active }),
      })
      onChange()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }

  async function copy(code, what) {
    try {
      await navigator.clipboard.writeText(what === 'link' ? inviteLink(code) : code.code)
      setCopied(`${code.id}:${what}`)
    } catch { /* clipboard blocked — the code is selectable on screen */ }
  }

  return (
    <div className="card">
      <h2>Invite codes</h2>
      <p className="muted" style={{ marginTop: 0 }}>
        New people need a code to sign up. Send a friend the invite link — it
        opens the sign-up screen with the code already filled in. Their account
        then waits for your approval above.
      </p>
      {error && <p className="muted" style={{ color: 'var(--color-danger)' }}>{error}</p>}

      <form onSubmit={create} className="row" style={{ gap: '0.5rem', alignItems: 'flex-end', flexWrap: 'wrap' }}>
        <div className="col" style={{ flex: 2, minWidth: 160, gap: '0.25rem' }}>
          <label htmlFor="invite-label">Label (optional)</label>
          <input
            id="invite-label"
            value={label}
            maxLength={60}
            placeholder="e.g. gym friends"
            onChange={e => setLabel(e.target.value)}
          />
        </div>
        <div className="col" style={{ flex: 1, minWidth: 110, gap: '0.25rem' }}>
          <label htmlFor="invite-max">Max uses</label>
          <input
            id="invite-max"
            inputMode="numeric"
            value={maxUses}
            placeholder="no limit"
            onChange={e => setMaxUses(e.target.value)}
          />
        </div>
        <button type="submit" disabled={busy} style={{ minWidth: 120 }}>
          {busy ? 'Creating…' : 'Create code'}
        </button>
      </form>

      {codes.length === 0 && <p className="muted">No codes yet — create one to invite someone.</p>}
      <div className="col" style={{ gap: '0.75rem', marginTop: '1rem' }}>
        {codes.map(c => {
          const usedUp = c.max_uses != null && c.uses >= c.max_uses
          return (
            <div key={c.id} className="row" style={{ alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap', opacity: c.active ? 1 : 0.6 }}>
              <div style={{ flex: 1, minWidth: 180 }}>
                <div>
                  <code style={{ fontSize: '0.95rem', userSelect: 'all' }}>{c.code}</code>{' '}
                  {!c.active && <span className="badge">off</span>}
                  {c.active && usedUp && <span className="badge">used up</span>}
                </div>
                <div className="muted" style={{ fontSize: '0.8rem' }}>
                  {c.label ? `${c.label} · ` : ''}{usageText(c)} · created {fmtTimestamp(c.created_at)}
                </div>
              </div>
              {c.active && (
                <>
                  <button className="secondary" style={{ minWidth: 92 }} onClick={() => copy(c, 'link')}>
                    {copied === `${c.id}:link` ? 'Copied' : 'Copy invite link'}
                  </button>
                  <button className="secondary" style={{ minWidth: 92 }} onClick={() => copy(c, 'code')}>
                    {copied === `${c.id}:code` ? 'Copied' : 'Copy code'}
                  </button>
                </>
              )}
              {c.active ? (
                <button className="danger" style={{ minWidth: 92 }} disabled={busyId === c.id}
                  onClick={() => setActive(c, false)}>
                  Switch off
                </button>
              ) : (
                <button style={{ minWidth: 92 }} disabled={busyId === c.id}
                  onClick={() => setActive(c, true)}>
                  Switch on
                </button>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

function ResetLinkResult({ result, onDismiss }) {
  const [copied, setCopied] = useState(false)
  if (!result) return null

  async function copy() {
    try {
      await navigator.clipboard.writeText(result.action_link)
      setCopied(true)
    } catch { /* clipboard blocked — the link is selectable below */ }
  }

  return (
    <div className="card" style={{ borderColor: 'var(--color-primary)' }}>
      <h3 style={{ marginTop: 0 }}>Password reset link for {result.email}</h3>
      <p className="muted" style={{ marginBottom: '0.6rem' }}>
        Send it to them directly — opening it signs them in and asks for a new
        password. It works once and expires; anyone holding it can get into
        their account, so send it only to them.
      </p>
      <code style={{
        display: 'block', padding: '0.5rem 0.75rem', borderRadius: 6, wordBreak: 'break-all',
        background: 'var(--surface-2, rgba(127,127,127,0.12))', fontSize: '0.8rem',
      }}>{result.action_link}</code>
      <div className="row" style={{ gap: '0.5rem', marginTop: '0.75rem' }}>
        <button style={{ flex: 1 }} onClick={copy}>{copied ? 'Copied' : 'Copy link'}</button>
        <button className="secondary" style={{ flex: 1 }} onClick={onDismiss}>Done</button>
      </div>
    </div>
  )
}

function UsersCard({ users, onChange }) {
  const [busyId, setBusyId] = useState(null)
  const [error, setError] = useState(null)
  const [resetResult, setResetResult] = useState(null)

  async function setStatus(u, status) {
    setBusyId(u.id)
    setError(null)
    try {
      await apiFetch(`/api/admin/users/${u.id}`, {
        method: 'PATCH', body: JSON.stringify({ status }),
      })
      onChange()
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }

  async function createResetLink(u) {
    if (!(await confirmAction({
      title: 'Create a password reset link?',
      message: `For ${u.email}. Anyone with the link can get into their account — send it only to them.`,
      confirmLabel: 'Create link',
    }))) return
    setBusyId(u.id)
    setError(null)
    try {
      setResetResult(await apiFetch(`/api/admin/users/${u.id}/reset-link`, { method: 'POST' }))
    } catch (err) {
      setError(err.message)
    } finally {
      setBusyId(null)
    }
  }

  return (
    <div className="card">
      <h2>All users</h2>
      {error && <p className="muted" style={{ color: 'var(--color-danger)' }}>{error}</p>}
      <ResetLinkResult result={resetResult} onDismiss={() => setResetResult(null)} />
      <div className="col" style={{ gap: '0.6rem', marginTop: resetResult ? '0.75rem' : 0 }}>
        {users.map(u => (
          <div key={u.id} className="row" style={{ alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: 160 }}>
              <div>{u.name} {u.role === 'admin' && <span className="badge">admin</span>}</div>
              <div className="muted" style={{ fontSize: '0.8rem' }}>
                {u.email} · {u.status} · last seen {fmtTimestamp(u.last_login_at)}
                {!u.login_linked && ' · not on the new login yet'}
              </div>
            </div>
            {u.status !== 'disabled' ? (
              <button
                className="danger"
                style={{ minWidth: 84 }}
                disabled={busyId === u.id}
                onClick={() => setStatus(u, 'disabled')}
              >
                Disable
              </button>
            ) : (
              <button
                style={{ minWidth: 84 }}
                disabled={busyId === u.id}
                onClick={() => setStatus(u, 'active')}
              >
                Enable
              </button>
            )}
            <button
              className="secondary"
              style={{ minWidth: 140 }}
              disabled={busyId === u.id}
              onClick={() => createResetLink(u)}
            >
              Reset link
            </button>
          </div>
        ))}
      </div>
    </div>
  )
}

export default function Admin() {
  const [pending, setPending] = useState([])
  const [users, setUsers] = useState([])
  const [codes, setCodes] = useState([])
  const [error, setError] = useState(null)

  const load = useCallback(() => {
    Promise.all([
      apiFetch('/api/admin/pending'),
      apiFetch('/api/admin/users'),
      apiFetch('/api/admin/invite-codes'),
    ])
      .then(([p, u, c]) => { setPending(p); setUsers(u); setCodes(c) })
      .catch(err => setError(err.message))
  }, [])

  useEffect(load, [load])

  return (
    <div className="page">
      <h1>Admin</h1>
      <ErrorBox error={error} />
      <PendingCard pending={pending} onChange={load} />
      <InviteCodesCard codes={codes} onChange={load} />
      <UsersCard users={users} onChange={load} />
    </div>
  )
}

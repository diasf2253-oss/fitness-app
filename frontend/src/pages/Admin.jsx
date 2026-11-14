/**
 * Admin panel (Phase 1-2 friends beta) — user management only, no
 * per-user fitness-data drill-down. Route-guarded to role === 'admin' in
 * App.jsx; every call below is also enforced server-side regardless.
 */
import React, { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../api'
import { ErrorBox } from '../components/States'
import { confirmAction } from '../components/ConfirmSheet'

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
  const [error, setError] = useState(null)

  const load = useCallback(() => {
    Promise.all([
      apiFetch('/api/admin/pending'),
      apiFetch('/api/admin/users'),
    ])
      .then(([p, u]) => { setPending(p); setUsers(u) })
      .catch(err => setError(err.message))
  }, [])

  useEffect(load, [load])

  return (
    <div className="page">
      <h1>Admin</h1>
      <ErrorBox error={error} />
      <PendingCard pending={pending} onChange={load} />
      <UsersCard users={users} onChange={load} />
    </div>
  )
}

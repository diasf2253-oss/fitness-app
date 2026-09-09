/**
 * Admin panel (Phase 1-2 friends beta) — user management only, no
 * per-user fitness-data drill-down. Route-guarded to role === 'admin' in
 * App.jsx; every call below is also enforced server-side regardless.
 */
import React, { useCallback, useEffect, useState } from 'react'
import { apiFetch } from '../api'
import { ErrorBox } from '../components/States'

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

function TempPasswordResult({ result, onDismiss }) {
  if (!result) return null
  return (
    <div className="card" style={{ borderColor: 'var(--color-primary)' }}>
      <h3 style={{ marginTop: 0 }}>Temporary password for {result.email}</h3>
      <p className="muted" style={{ marginBottom: '0.6rem' }}>
        Shown once — send it to them directly. They'll be forced to set a new
        password on first login, and their other sessions are now signed out.
      </p>
      <code style={{
        display: 'block', padding: '0.5rem 0.75rem', borderRadius: 6,
        background: 'var(--surface-2, rgba(127,127,127,0.12))', fontSize: '0.95rem',
      }}>{result.temp_password}</code>
      <button className="secondary" style={{ width: '100%', marginTop: '0.75rem' }} onClick={onDismiss}>
        Done
      </button>
    </div>
  )
}

function UsersCard({ users, onChange }) {
  const [busyId, setBusyId] = useState(null)
  const [error, setError] = useState(null)
  const [tempResult, setTempResult] = useState(null)

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

  async function issueTempPassword(u) {
    if (!confirm(`Issue a temporary password for ${u.email}? Their other sessions will be signed out.`)) return
    setBusyId(u.id)
    setError(null)
    try {
      const r = await apiFetch(`/api/admin/users/${u.id}/temp-password`, { method: 'POST' })
      setTempResult({ email: u.email, temp_password: r.temp_password })
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
      <TempPasswordResult result={tempResult} onDismiss={() => setTempResult(null)} />
      <div className="col" style={{ gap: '0.6rem', marginTop: tempResult ? '0.75rem' : 0 }}>
        {users.map(u => (
          <div key={u.id} className="row" style={{ alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
            <div style={{ flex: 1, minWidth: 160 }}>
              <div>{u.name} {u.role === 'admin' && <span className="badge">admin</span>}</div>
              <div className="muted" style={{ fontSize: '0.8rem' }}>
                {u.email} · {u.status} · last login {fmtTimestamp(u.last_login_at)}
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
              onClick={() => issueTempPassword(u)}
            >
              Set temp password
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

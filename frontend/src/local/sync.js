/**
 * Sync client (P2 slice) — talks to the laptop's /api/sync endpoints when
 * it can reach them; silently does nothing when it can't. Called on app
 * open, so being near the laptop is all it takes to stay in sync.
 *
 * Protocol (see backend/app/routers/sync.py + app/sync.py):
 *   1. GET  /api/sync/manifest — cheap reachability probe (short timeout)
 *   2. POST /api/sync/push     — send locally-dirty rows; server merges
 *      last-write-wins with health source precedence
 *   3. GET  /api/sync/pull?since=<last server_time> — fetch what changed
 *      on the laptop; merge into IndexedDB with the same rules
 *   4. Remember the server_time for the next incremental pull
 *
 * Only weight_log syncs for now — tables are added here as domains go
 * local-first (P3/P4).
 */
import { db, getMeta, setMeta } from './db'
import { writeBlocked } from './weights'

const PROBE_TIMEOUT_MS = 3000

function authHeaders() {
  return { Authorization: `Bearer ${localStorage.getItem('app_token') || 'changeme'}` }
}

async function probe() {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), PROBE_TIMEOUT_MS)
  try {
    const r = await fetch('/api/sync/manifest', { headers: authHeaders(), signal: controller.signal })
    return r.ok
  } catch {
    return false
  } finally {
    clearTimeout(timer)
  }
}

async function pushDirty() {
  const dirty = await db.weight_log.where('_dirty').equals(1).toArray()
  if (dirty.length === 0) return 0
  const rows = dirty.map(({ _dirty, ...row }) => row)
  const r = await fetch('/api/sync/push', {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ tables: { weight_log: rows } }),
  })
  if (!r.ok) throw new Error(`push failed: HTTP ${r.status}`)
  await db.weight_log.where('_dirty').equals(1).modify({ _dirty: 0 })
  return dirty.length
}

async function pullSince(since) {
  const qs = since ? `?since=${encodeURIComponent(since)}` : ''
  const r = await fetch(`/api/sync/pull${qs}`, { headers: authHeaders() })
  if (!r.ok) throw new Error(`pull failed: HTTP ${r.status}`)
  const body = await r.json()

  let applied = 0
  for (const incoming of body.tables.weight_log || []) {
    const existing = await db.weight_log.get(incoming.date)
    // Same merge rules as the server: precedence first, then last-write-wins
    if (existing && writeBlocked(existing, incoming.source)) continue
    if (existing && incoming.updated_at <= existing.updated_at) continue
    await db.weight_log.put({ ...incoming, _dirty: 0 })
    applied++
  }
  return { applied, serverTime: body.server_time }
}

/**
 * Full sync pass. Returns a small result object for the UI, or
 * { reachable: false } when the laptop isn't there — never throws
 * for unreachability, only for real protocol errors.
 */
export async function syncNow() {
  if (!(await probe())) return { reachable: false }
  const pushed = await pushDirty()
  const { applied, serverTime } = await pullSince(await getMeta('last_sync_at'))
  await setMeta('last_sync_at', serverTime)
  await setMeta('last_sync_result', {
    at: serverTime, pushed, pulled: applied,
  })
  return { reachable: true, pushed, pulled: applied }
}

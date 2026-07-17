/**
 * Sync client — talks to the laptop's /api/sync endpoints when it can
 * reach them; silently does nothing when it can't. Called on app open,
 * so being near the laptop is all it takes to stay in sync.
 *
 * Protocol (see backend/app/routers/sync.py + app/sync.py):
 *   1. GET  /api/sync/manifest — cheap reachability probe (short timeout)
 *   2. POST /api/sync/push     — send locally-dirty rows; server merges
 *      last-write-wins with health source precedence
 *   3. GET  /api/sync/pull?since=<last server_time> — fetch what changed
 *      on the laptop; merge into IndexedDB with the same rules
 *   4. Remember the server_time for the next incremental pull
 *
 * Tables mirror app/sync.py SYNC_TABLES: parents before children so the
 * server can resolve FK uuids on push, and rows land locally in an order
 * that keeps references intact.
 */
import { db, getMeta, setMeta } from './db'
import { writeBlocked } from './weights'
import { apiUrl } from '../env'

const PROBE_TIMEOUT_MS = 3000

// Bump when SYNC_TABLES widens: a device that last synced under a narrower
// scope must do one full pull (since=null) to backfill the new tables —
// its incremental cursor predates them.
const SYNC_SCOPE_VERSION = 3

// table name -> { key, health } (health tables get source-precedence checks)
const SYNC_TABLES = {
  exercise: { key: 'uuid' },
  routine: { key: 'uuid' },
  routine_exercise: { key: 'uuid' },
  session: { key: 'uuid' },
  session_exercise: { key: 'uuid' },
  set: { key: 'uuid' },
  routine_note: { key: 'uuid' },
  activity: { key: 'uuid' },
  plan_item: { key: 'uuid' },
  tracker: { key: 'uuid' },
  tracker_log: { key: 'uuid' },
  weight_log: { key: 'date', health: true },
  steps_log: { key: 'date', health: true },
  sleep_log: { key: 'date', health: true },
  nutrition_day: { key: 'date', health: true },
  settings: { key: 'singleton' },
}

function authHeaders() {
  return { Authorization: `Bearer ${localStorage.getItem('app_token') || 'changeme'}` }
}

async function probe() {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), PROBE_TIMEOUT_MS)
  try {
    const r = await fetch(apiUrl('/api/sync/manifest'), { headers: authHeaders(), signal: controller.signal })
    return r.ok
  } catch {
    return false
  } finally {
    clearTimeout(timer)
  }
}

async function pushDirty() {
  const tables = {}
  let total = 0
  for (const name of Object.keys(SYNC_TABLES)) {
    const dirty = await db.table(name).where('_dirty').equals(1).toArray()
    if (dirty.length === 0) continue
    // _dirty is local bookkeeping; settings' local pk stays off the wire too
    tables[name] = dirty.map(({ _dirty, id, ...row }) => row)
    total += dirty.length
  }
  if (total === 0) return 0

  const r = await fetch(apiUrl('/api/sync/push'), {
    method: 'POST',
    headers: { ...authHeaders(), 'Content-Type': 'application/json' },
    body: JSON.stringify({ tables }),
  })
  if (!r.ok) throw new Error(`push failed: HTTP ${r.status}`)
  for (const name of Object.keys(tables)) {
    await db.table(name).where('_dirty').equals(1).modify({ _dirty: 0 })
  }
  return total
}

async function applyTable(name, rows) {
  const spec = SYNC_TABLES[name]
  let applied = 0
  for (const incoming of rows) {
    let existing
    if (spec.key === 'singleton') existing = await db.settings.get(1)
    else if (spec.key === 'date') existing = await db.table(name).get(incoming.date)
    else existing = await db.table(name).get(incoming.uuid)

    // Same merge rules as the server: precedence first, then last-write-wins
    if (spec.health && existing && writeBlocked(existing, incoming.source)) continue
    if (existing && existing.updated_at && incoming.updated_at <= existing.updated_at) continue

    const row = { ...incoming, _dirty: 0 }
    if (spec.key === 'singleton') row.id = 1
    await db.table(name).put(row)
    applied++
  }
  return applied
}

async function pullSince(since) {
  const qs = since ? `?since=${encodeURIComponent(since)}` : ''
  const r = await fetch(apiUrl(`/api/sync/pull${qs}`), { headers: authHeaders() })
  if (!r.ok) throw new Error(`pull failed: HTTP ${r.status}`)
  const body = await r.json()

  let applied = 0
  for (const name of Object.keys(SYNC_TABLES)) {   // parents before children
    if (body.tables[name]) applied += await applyTable(name, body.tables[name])
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
  const scopeCurrent = (await getMeta('sync_scope_version')) === SYNC_SCOPE_VERSION
  const since = scopeCurrent ? await getMeta('last_sync_at') : null
  const { applied, serverTime } = await pullSince(since)
  await setMeta('last_sync_at', serverTime)
  await setMeta('sync_scope_version', SYNC_SCOPE_VERSION)
  await setMeta('last_sync_result', { at: serverTime, pushed, pulled: applied })
  return { reachable: true, pushed, pulled: applied }
}

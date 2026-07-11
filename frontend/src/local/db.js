/**
 * On-device database (P1) — IndexedDB via Dexie.
 *
 * This is the phone's copy of the data: the app reads and writes here in
 * local-first mode, and the sync client exchanges rows with the laptop's
 * /api/sync endpoints. Row shapes mirror the backend sync payload exactly
 * (dates/datetimes as ISO strings), so rows travel unmodified.
 *
 * `_dirty` marks rows changed locally since the last successful push —
 * deterministic, no clock comparison needed to decide what to send.
 *
 * Schema versions are append-only: bump .version(n) and add tables as
 * more domains go local (P3/P4) — Dexie migrates automatically.
 */
import Dexie from 'dexie'

export const db = new Dexie('tracker')

db.version(1).stores({
  // Weight vertical slice (P2). Primary key = ISO date, like the backend.
  weight_log: 'date, _dirty',
  // Sync bookkeeping: { key, value } — e.g. last_sync_at, last_sync_result
  sync_meta: 'key',
})

export async function getMeta(key) {
  const row = await db.sync_meta.get(key)
  return row ? row.value : null
}

export async function setMeta(key, value) {
  await db.sync_meta.put({ key, value })
}

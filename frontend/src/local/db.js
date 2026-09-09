/**
 * On-device database (P1) — IndexedDB via Dexie.
 *
 * This is the phone's copy of the data: the app reads and writes here in
 * local-first mode, and the sync client exchanges rows with the laptop's
 * /api/sync endpoints. Row shapes mirror the backend sync payload exactly
 * (dates/datetimes as ISO strings, foreign keys as parent uuids), so rows
 * travel unmodified between IndexedDB and the wire.
 *
 * `_dirty` marks rows changed locally since the last successful push —
 * deterministic, no clock comparison needed to decide what to send.
 *
 * Schema versions are append-only: v1 was the weight slice, v2 adds every
 * synced table (P3/P4), v3 adds the restored features (routine notes +
 * activities; the streak is recomputed on read, so it needs no table).
 * Dexie migrates automatically.
 */
import Dexie from 'dexie'

export const db = new Dexie('tracker')

db.version(1).stores({
  weight_log: 'date, _dirty',
  sync_meta: 'key',
})

db.version(2).stores({
  // Date-keyed health tables (one row per day, merge on date)
  weight_log: 'date, _dirty',
  steps_log: 'date, _dirty',
  sleep_log: 'date, _dirty',
  nutrition_day: 'date, _dirty',
  // Entity tables (uuid identity; FKs stored as parent uuids)
  exercise: 'uuid, name, _dirty',
  routine: 'uuid, _dirty',
  routine_exercise: 'uuid, routine_uuid, _dirty',
  session: 'uuid, started_at, _dirty',
  session_exercise: 'uuid, session_uuid, exercise_uuid, _dirty',
  set: 'uuid, session_exercise_uuid, _dirty',
  plan_item: 'uuid, date, _dirty',
  tracker: 'uuid, _dirty',
  tracker_log: 'uuid, tracker_uuid, date, [tracker_uuid+date], _dirty',
  // Singleton (id=1 always, like the backend)
  settings: 'id, _dirty',
  sync_meta: 'key',
})

db.version(3).stores({
  // Carry every v2 table forward unchanged…
  weight_log: 'date, _dirty',
  steps_log: 'date, _dirty',
  sleep_log: 'date, _dirty',
  nutrition_day: 'date, _dirty',
  exercise: 'uuid, name, _dirty',
  routine: 'uuid, _dirty',
  routine_exercise: 'uuid, routine_uuid, _dirty',
  session: 'uuid, started_at, _dirty',
  session_exercise: 'uuid, session_uuid, exercise_uuid, _dirty',
  set: 'uuid, session_exercise_uuid, _dirty',
  plan_item: 'uuid, date, _dirty',
  tracker: 'uuid, _dirty',
  tracker_log: 'uuid, tracker_uuid, date, [tracker_uuid+date], _dirty',
  settings: 'id, _dirty',
  sync_meta: 'key',
  // …and add the restored feature tables.
  routine_note: 'uuid, routine_uuid, surfaced_in_session_uuid, _dirty',
  activity: 'uuid, date, _dirty',
})

// v4 groups routines under splits: a new split table, and routine gains a
// split_uuid index so a split's days can be looked up directly.
db.version(4).stores({
  weight_log: 'date, _dirty',
  steps_log: 'date, _dirty',
  sleep_log: 'date, _dirty',
  nutrition_day: 'date, _dirty',
  exercise: 'uuid, name, _dirty',
  split: 'uuid, _dirty',
  routine: 'uuid, split_uuid, _dirty',
  routine_exercise: 'uuid, routine_uuid, _dirty',
  session: 'uuid, started_at, _dirty',
  session_exercise: 'uuid, session_uuid, exercise_uuid, _dirty',
  set: 'uuid, session_exercise_uuid, _dirty',
  plan_item: 'uuid, date, _dirty',
  tracker: 'uuid, _dirty',
  tracker_log: 'uuid, tracker_uuid, date, [tracker_uuid+date], _dirty',
  settings: 'id, _dirty',
  sync_meta: 'key',
  routine_note: 'uuid, routine_uuid, surfaced_in_session_uuid, _dirty',
  activity: 'uuid, date, _dirty',
})

export function newUuid() {
  return crypto.randomUUID()
}

export function nowIso() {
  // Matches the backend's naive-UTC isoformat *including* microsecond
  // padding (Python emits .%f six digits) so echoes compare as equal
  // instead of lexically newer.
  return new Date().toISOString().replace('Z', '') + '000'
}

export async function getMeta(key) {
  const row = await db.sync_meta.get(key)
  return row ? row.value : null
}

export async function setMeta(key, value) {
  await db.sync_meta.put({ key, value })
}

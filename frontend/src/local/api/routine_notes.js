/**
 * Next-session notes, local-first — mirrors backend routers/routine_notes.py.
 *
 * A note is written against a routine (training day); it surfaces once at the
 * next session of that routine, then auto-archives. Session references are
 * stored locally as uuids (they are excluded from sync — archived_at is what
 * keeps a note from resurfacing on another device).
 */
import { db, newUuid, nowIso } from '../db'
import { LocalApiError, notFound } from './util'

const stamp = (row) => ({ ...row, updated_at: nowIso(), _dirty: 1 })

const present = (n) => ({
  id: n.uuid, routine_id: n.routine_uuid, text: n.text,
  created_at: n.created_at,
  created_in_session_id: n.created_in_session_uuid ?? null,
  surfaced_in_session_id: n.surfaced_in_session_uuid ?? null,
  archived_at: n.archived_at ?? null,
})

/** Surface + archive a routine's pending notes onto the session starting now. */
export async function consumePendingNotes(routineUuid, sessionUuid) {
  const pending = (await db.routine_note.where('routine_uuid').equals(routineUuid).toArray())
    .filter(n => !n.archived_at)
  const now = nowIso()
  for (const n of pending) {
    await db.routine_note.put(stamp({ ...n, surfaced_in_session_uuid: sessionUuid, archived_at: now }))
  }
  return pending
}

/** Notes surfaced at the start of a given session (for SessionOut). */
export async function nextSessionNotesFor(sessionUuid) {
  const notes = await db.routine_note.where('surfaced_in_session_uuid').equals(sessionUuid).toArray()
  notes.sort((a, b) => (a.created_at < b.created_at ? -1 : 1))
  return notes.map(present)
}

async function createNote(routineUuid, body) {
  if (!(await db.routine.get(routineUuid))) throw notFound('Routine')
  const text = (body.text || '').trim()
  if (!text) throw new LocalApiError(422, 'Note text is required')
  const note = stamp({
    uuid: newUuid(), routine_uuid: routineUuid, text, created_at: nowIso(),
    created_in_session_uuid: body.created_in_session_id ?? null,
    surfaced_in_session_uuid: null, archived_at: null,
  })
  await db.routine_note.put(note)
  return present(note)
}

async function listNotes(routineUuid, includeArchived) {
  if (!(await db.routine.get(routineUuid))) throw notFound('Routine')
  let notes = await db.routine_note.where('routine_uuid').equals(routineUuid).toArray()
  if (!includeArchived) notes = notes.filter(n => !n.archived_at)
  notes.sort((a, b) => (a.created_at < b.created_at ? 1 : -1))   // newest first
  return notes.map(present)
}

async function updateNote(noteUuid, body) {
  const n = await db.routine_note.get(noteUuid)
  if (!n) throw notFound('Note')
  const patch = { ...n }
  if (body.text != null) patch.text = body.text.trim()
  if (body.archived != null) patch.archived_at = body.archived ? nowIso() : null
  const row = stamp(patch)
  await db.routine_note.put(row)
  return present(row)
}

async function deleteNote(noteUuid) {
  if (!(await db.routine_note.get(noteUuid))) throw notFound('Note')
  await db.routine_note.delete(noteUuid)
  return null
}

export const routineNoteRoutes = [
  {
    method: 'POST', pattern: /^\/api\/routines\/([^/]+)\/notes$/,
    handler: (m, _q, body) => createNote(m[1], body),
  },
  {
    method: 'GET', pattern: /^\/api\/routines\/([^/]+)\/notes$/,
    handler: (m, q) => listNotes(m[1], q.get('include_archived') !== 'false'),
  },
  {
    method: 'PATCH', pattern: /^\/api\/routine-notes\/([^/]+)$/,
    handler: (m, _q, body) => updateNote(m[1], body),
  },
  {
    method: 'DELETE', pattern: /^\/api\/routine-notes\/([^/]+)$/,
    handler: (m) => deleteNote(m[1]),
  },
]

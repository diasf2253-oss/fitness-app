"""Next-session notes — one-shot notes per training day (routine).

POST   /api/routines/{routine_id}/notes   — add a pending note ("squats +1 set")
GET    /api/routines/{routine_id}/notes    — list (pending + archived history)
PATCH  /api/routine-notes/{note_id}        — edit text / (un)archive
DELETE /api/routine-notes/{note_id}        — delete

Pending notes are consumed (surfaced + archived) when the next session of the
routine starts — see sessions.start_session, which calls consume_pending_notes.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session as DBSession

from app.auth import require_auth
from app.db import get_db
from app.models import Routine, RoutineNote, User
from app.schemas import RoutineNoteCreate, RoutineNoteOut, RoutineNoteUpdate

router = APIRouter(tags=["routine-notes"])


def consume_pending_notes(db: DBSession, routine_id: int, session_id: int, user_id: int) -> list[RoutineNote]:
    """Surface and archive a routine's pending next-session notes onto the
    session that's starting, so they show once and never resurface."""
    pending = (
        db.query(RoutineNote)
        .filter(
            RoutineNote.user_id == user_id,
            RoutineNote.routine_id == routine_id,
            RoutineNote.archived_at.is_(None),
        )
        .all()
    )
    now = datetime.utcnow()
    for note in pending:
        note.surfaced_in_session_id = session_id
        note.archived_at = now
    return pending


@router.post("/api/routines/{routine_id}/notes", response_model=RoutineNoteOut, status_code=201)
def create_routine_note(
    routine_id: int,
    body: RoutineNoteCreate,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    routine = db.get(Routine, routine_id)
    if not routine or routine.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Routine not found")
    text = (body.text or "").strip()
    if not text:
        raise HTTPException(status_code=422, detail="Note text is required")
    note = RoutineNote(
        user_id=current_user.id, routine_id=routine_id, text=text,
        created_in_session_id=body.created_in_session_id,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.get("/api/routines/{routine_id}/notes", response_model=list[RoutineNoteOut])
def list_routine_notes(
    routine_id: int,
    include_archived: bool = Query(True),
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    routine = db.get(Routine, routine_id)
    if not routine or routine.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Routine not found")
    q = db.query(RoutineNote).filter(
        RoutineNote.user_id == current_user.id, RoutineNote.routine_id == routine_id
    )
    if not include_archived:
        q = q.filter(RoutineNote.archived_at.is_(None))
    return q.order_by(RoutineNote.created_at.desc()).all()


@router.patch("/api/routine-notes/{note_id}", response_model=RoutineNoteOut)
def update_routine_note(
    note_id: int,
    body: RoutineNoteUpdate,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    note = db.get(RoutineNote, note_id)
    if not note or note.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Note not found")
    if body.text is not None:
        note.text = body.text.strip()
    if body.archived is not None:
        note.archived_at = datetime.utcnow() if body.archived else None
    db.commit()
    db.refresh(note)
    return note


@router.delete("/api/routine-notes/{note_id}", status_code=204)
def delete_routine_note(
    note_id: int,
    db: DBSession = Depends(get_db),
    current_user: User = Depends(require_auth),
):
    note = db.get(RoutineNote, note_id)
    if not note or note.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Note not found")
    db.delete(note)
    db.commit()
